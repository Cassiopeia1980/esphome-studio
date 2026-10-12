"""ESPHome Studio – grafischer ESPHome-Konfigurator als Panel in Home Assistant."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .catalog import catalog
from .entity import entity_meta
from .boards import BOARDS, board_detail, boards_meta
from .components import GROUP_ORDER, components_meta
from .const import (
    DOMAIN,
    MAX_COMPONENTS,
    MAX_PROJECTS,
    PANEL_ELEMENT,
    PANEL_URL_PATH,
    STATIC_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    VERSION,
)
from .generator import default_project, generate, new_ap_password, new_api_key, new_password
from .deploy import (DEFAULT_DIR, DeployError, list_from_dashboard, list_from_folder, read_from_dashboard,
                     read_from_folder, read_secrets_from_folder, version_tuple, write_to_dashboard, write_to_folder)
from .i18n import LANGS, tr, tr_struct, ui_dictionary, use_lang
from .importer import import_yaml

_LOGGER = logging.getLogger(__name__)

STATIC_REGISTERED = f"{DOMAIN}_static_registered"
WS_REGISTERED = f"{DOMAIN}_ws_registered"
MAX_PROJECT_BYTES = 300_000
SECRET_KEYS = ("wifi_ssid", "wifi_password")


# --------------------------------------------------------------- Einrichtung --


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    data.setdefault("projects", {})
    data.setdefault("secrets", {})
    hass.data[DOMAIN] = {"store": store, "data": data}

    if not hass.data.get(WS_REGISTERED):
        for handler in (ws_meta, ws_board, ws_catalog, ws_import, ws_list, ws_get, ws_save, ws_delete, ws_new, ws_generate, ws_set_secrets,
                        ws_random, ws_deploy_settings, ws_deploy, ws_i18n, ws_source_list, ws_source_get):
            websocket_api.async_register_command(hass, handler)
        hass.data[WS_REGISTERED] = True

    if not hass.data.get(STATIC_REGISTERED):
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(frontend_dir), False)])
        hass.data[STATIC_REGISTERED] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=f"{STATIC_URL}/esphome-studio-panel.js?v={VERSION}",
        sidebar_title="ESPHome Studio",
        sidebar_icon="mdi:chip",
        require_admin=True,
        config={},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data.pop(DOMAIN, None)
    return True


# ------------------------------------------------------------------- Helfer --


def _lang(msg: dict[str, Any]) -> str:
    lg = str(msg.get("lang") or "de")
    return lg if lg in LANGS else "de"


def _state(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int, lang: str = "de"):
    st = hass.data.get(DOMAIN)
    if not st:
        connection.send_error(msg_id, "not_loaded", tr("ESPHome Studio ist nicht geladen.", lang))
        return None
    return st


def _summary(pid: str, p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pid,
        "name": p.get("name", ""),
        "friendly_name": p.get("friendly_name", ""),
        "board": p.get("board", ""),
        "updated": p.get("updated", ""),
        "components": len(p.get("components") or []),
    }


def _clean_project(project: dict[str, Any]) -> dict[str, Any] | None:
    """Prüft Größe und JSON-Tauglichkeit; entfernt interne Felder."""
    try:
        raw = json.dumps(project, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    if len(raw) > MAX_PROJECT_BYTES:
        return None
    clean = json.loads(raw)
    comps = clean.get("components")
    if not isinstance(comps, list) or len(comps) > MAX_COMPONENTS:
        return None
    for c in comps:
        if isinstance(c, dict):
            c.pop("_id", None)
    return clean


# --------------------------------------------------------- Websocket-Befehle --


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/meta", vol.Optional("lang"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_meta(hass, connection, msg):
    lg = _lang(msg)
    connection.send_result(msg["id"], tr_struct({
        "version": VERSION,
        "boards": boards_meta(),
        "types": components_meta(),
        "group_order": GROUP_ORDER,
        "entity": entity_meta(),
    }, lg))


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/i18n", vol.Optional("lang"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_i18n(hass, connection, msg):
    """Wörterbuch für die Oberfläche (deutscher Text -> Zielsprache)."""
    connection.send_result(msg["id"], {"dict": ui_dictionary(_lang(msg))})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/catalog", vol.Optional("lang"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_catalog(hass, connection, msg):
    cat = await hass.async_add_executor_job(catalog)
    lg = _lang(msg)
    if lg == "en":
        cache = hass.data[DOMAIN].setdefault("catalog_en", {})
        if "v" not in cache:
            cache["v"] = await hass.async_add_executor_job(lambda: tr_struct(cat, "en"))
        cat = cache["v"]
    connection.send_result(msg["id"], cat)


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/board", vol.Optional("lang"): str, vol.Required("key"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_board(hass, connection, msg):
    detail = board_detail(msg["key"])
    if detail is None:
        connection.send_error(msg["id"], "invalid_board", tr("Unbekanntes Board.", _lang(msg)))
        return
    connection.send_result(msg["id"], {"board": tr_struct(detail, _lang(msg))})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/list", vol.Optional("lang"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    projects = [_summary(pid, p) for pid, p in st["data"]["projects"].items()]
    projects.sort(key=lambda x: x.get("updated", ""), reverse=True)
    connection.send_result(msg["id"], {"projects": projects, "secrets": st["data"]["secrets"]})


# Hinweis: "id" ist bei Home Assistant die Nachrichten-ID, die Projekt-ID heißt deshalb "project_id".
@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/get", vol.Optional("lang"): str, vol.Required("project_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    project = st["data"]["projects"].get(msg["project_id"])
    if project is None:
        connection.send_error(msg["id"], "not_found", tr("Projekt nicht gefunden.", _lang(msg)))
        return
    connection.send_result(msg["id"], {"project": {**project, "id": msg["project_id"]}})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/save", vol.Optional("lang"): str, vol.Required("project"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    project = _clean_project(msg["project"])
    if project is None:
        connection.send_error(msg["id"], "invalid_project", tr("Das Projekt ist ungültig oder zu groß.", _lang(msg)))
        return
    if project.get("board") not in BOARDS:
        connection.send_error(msg["id"], "invalid_board", tr("Unbekanntes Board.", _lang(msg)))
        return
    projects = st["data"]["projects"]
    pid = str(project.pop("id", "") or "")
    if not pid or pid not in projects:
        if len(projects) >= MAX_PROJECTS:
            connection.send_error(msg["id"], "too_many", tr("Zu viele Projekte gespeichert.", _lang(msg)))
            return
        pid = new_password()[:12]
    project["updated"] = dt_util.utcnow().isoformat()
    projects[pid] = project
    await st["store"].async_save(st["data"])
    connection.send_result(msg["id"], {"project": {**project, "id": pid}})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/delete", vol.Optional("lang"): str, vol.Required("project_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    if st["data"]["projects"].pop(msg["project_id"], None) is not None:
        await st["store"].async_save(st["data"])
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/new", vol.Optional("lang"): str, vol.Optional("board"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_new(hass, connection, msg):
    with use_lang(_lang(msg)):
        connection.send_result(msg["id"], {"project": default_project(msg.get("board") or "d1_mini")})


@websocket_api.websocket_command({
    vol.Required("type"): "esphome_studio/import",
    vol.Optional("lang"): str,
    vol.Required("yaml"): str,
    vol.Optional("secrets"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import(hass, connection, msg):
    if len(msg["yaml"]) > MAX_PROJECT_BYTES or len(msg.get("secrets", "")) > MAX_PROJECT_BYTES:
        connection.send_error(msg["id"], "too_large", tr("Die YAML ist zu groß.", _lang(msg)))
        return
    connection.send_result(msg["id"], await hass.async_add_executor_job(import_yaml, msg["yaml"], msg.get("secrets", ""), _lang(msg)))


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/generate", vol.Optional("lang"): str, vol.Required("project"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_generate(hass, connection, msg):
    st = hass.data.get(DOMAIN)
    secrets = st["data"]["secrets"] if st else {}
    connection.send_result(msg["id"], generate(msg["project"], secrets, _lang(msg)))


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/set_secrets", vol.Optional("lang"): str, vol.Required("secrets"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_secrets(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    for key in SECRET_KEYS:
        if key in msg["secrets"]:
            st["data"]["secrets"][key] = str(msg["secrets"][key])[:200]
    await st["store"].async_save(st["data"])
    connection.send_result(msg["id"], {"secrets": st["data"]["secrets"]})


@websocket_api.websocket_command({
    vol.Required("type"): "esphome_studio/random",
    vol.Optional("lang"): str,
    vol.Required("kind"): vol.In(["api", "ota", "ap"]),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_random(hass, connection, msg):
    value = {"api": new_api_key, "ota": new_password, "ap": new_ap_password}[msg["kind"]]()
    connection.send_result(msg["id"], {"value": value})


def _settings(st: dict[str, Any]) -> dict[str, str]:
    s = st["data"].setdefault("settings", {})
    return {"target_dir": str(s.get("target_dir", DEFAULT_DIR)), "dashboard_url": str(s.get("dashboard_url", "")),
            "dashboard_user": str(s.get("dashboard_user", "")), "dashboard_password": str(s.get("dashboard_password", ""))}


@websocket_api.websocket_command({
    vol.Required("type"): "esphome_studio/deploy_settings",
    vol.Optional("lang"): str,
    vol.Optional("target_dir"): str,
    vol.Optional("dashboard_url"): str,
    vol.Optional("dashboard_user"): str,
    vol.Optional("dashboard_password"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_deploy_settings(hass, connection, msg):
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    changed = False
    for key in ("target_dir", "dashboard_url", "dashboard_user"):
        if key in msg:
            st["data"].setdefault("settings", {})[key] = msg[key].strip()[:300]
            changed = True
    if msg.get("dashboard_password"):  # leer = unverändert lassen
        st["data"].setdefault("settings", {})["dashboard_password"] = msg["dashboard_password"][:300]
        changed = True
    if msg.get("dashboard_user") == "" and "dashboard_user" in msg:
        st["data"].setdefault("settings", {})["dashboard_password"] = ""  # ohne Benutzer kein Passwort
    if changed:
        await st["store"].async_save(st["data"])
    cur = _settings(st)
    cur["has_password"] = bool(cur.pop("dashboard_password"))  # Passwort nie ans Panel zurückgeben
    cur["dir_exists"] = await hass.async_add_executor_job(lambda: Path(cur["target_dir"]).is_dir()) if cur["target_dir"] else False
    connection.send_result(msg["id"], cur)


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/deploy", vol.Optional("lang"): str, vol.Required("project"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_deploy(hass, connection, msg):
    """Fertige YAML in den ESPHome-Ordner (oder per Dashboard) schreiben; secrets.yaml nur ergänzen."""
    st = _state(hass, connection, msg["id"], _lang(msg))
    if not st:
        return
    lg = _lang(msg)
    res = generate(msg["project"], st["data"]["secrets"], lg)
    if not res.get("ok"):
        connection.send_error(msg["id"], "invalid", tr("Die Konfiguration hat noch Fehler. Erst beheben, dann speichern.", _lang(msg)))
        return
    name = str(msg["project"].get("name") or "")
    cfg = _settings(st)
    try:
        if cfg["dashboard_url"]:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: PLC0415

            out = await write_to_dashboard(async_get_clientsession(hass), cfg["dashboard_url"], name, res["yaml"],
                                           res.get("secrets", ""), cfg["dashboard_user"], cfg["dashboard_password"])
        else:
            folder = cfg["target_dir"]
            if not folder:
                raise DeployError("Kein Ziel eingestellt. Ordner oder Dashboard-Adresse eintragen.")
            if not hass.config.is_allowed_path(folder):
                raise DeployError(f"Der Ordner „{folder}“ ist für Home Assistant nicht freigegeben "
                                  "(allowlist_external_dirs). Ordner unterhalb von /config verwenden.")
            out = await hass.async_add_executor_job(write_to_folder, folder, name, res["yaml"], res.get("secrets", ""), lg)
    except DeployError as exc:
        connection.send_error(msg["id"], "deploy_failed", tr(str(exc), lg))
        return
    except OSError as exc:
        connection.send_error(msg["id"], "deploy_failed", tr(f"Schreiben fehlgeschlagen: {exc.strerror or exc}", lg))
        return
    ota_mode = (msg["project"].get("ota") or {}).get("mode", "encryption")
    if (ota_mode == "encryption" and msg["project"].get("ota", {}).get("enabled", True)
            and out.get("esphome_version") and version_tuple(out["esphome_version"]) < (2026, 9)):
        out["warning"] = tr(f"Dein ESPHome ist Version {out['esphome_version']}. Die OTA-Verschlüsselung („ota: encryption“) gibt es erst "
                            "ab 2026.9. Stelle unter „WLAN, Secrets & Sicherheit“ die OTA-Absicherung auf „Passwort“, "
                            "sonst meldet ESPHome einen Fehler.", lg)
    connection.send_result(msg["id"], out)


async def _source_call(hass, connection, msg, lg, dash_fn, folder_fn):
    """Gemeinsame Quelle für die Lese-Befehle: Dashboard hat Vorrang, sonst der Ordner (wie beim Speichern)."""
    st = _state(hass, connection, msg["id"], lg)
    if not st:
        return None
    cfg = _settings(st)
    try:
        if cfg["dashboard_url"]:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: PLC0415

            return "dashboard", cfg["dashboard_url"], await dash_fn(async_get_clientsession(hass), cfg)
        folder = cfg["target_dir"]
        if not folder:
            raise DeployError("Kein Ziel eingestellt. Ordner oder Dashboard-Adresse eintragen.")
        if not hass.config.is_allowed_path(folder):
            raise DeployError(f"Der Ordner „{folder}“ ist für Home Assistant nicht freigegeben "
                              "(allowlist_external_dirs). Ordner unterhalb von /config verwenden.")
        return "folder", folder, await hass.async_add_executor_job(folder_fn, folder)
    except DeployError as exc:
        connection.send_error(msg["id"], "source_failed", tr(str(exc), lg))
    except (OSError, UnicodeDecodeError) as exc:
        connection.send_error(msg["id"], "source_failed", tr(f"Lesen fehlgeschlagen: {getattr(exc, 'strerror', None) or exc}", lg))
    return None


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/source_list", vol.Optional("lang"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_source_list(hass, connection, msg):
    """Vorhandene Geräte-YAMLs aus Device Builder bzw. ESPHome-Ordner auflisten."""
    lg = _lang(msg)
    got = await _source_call(
        hass, connection, msg, lg,
        lambda sess, c: list_from_dashboard(sess, c["dashboard_url"], c["dashboard_user"], c["dashboard_password"]),
        list_from_folder)
    if got:
        connection.send_result(msg["id"], {"source": got[0], "where": got[1], "items": got[2]})


@websocket_api.websocket_command({vol.Required("type"): "esphome_studio/source_get", vol.Optional("lang"): str,
                                  vol.Required("configuration"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_source_get(hass, connection, msg):
    """Eine YAML laden (plus im Ordner-Modus die darin benutzten Secrets)."""
    lg = _lang(msg)
    conf = msg["configuration"]

    def folder_fn(folder):
        text = read_from_folder(folder, conf)
        return {"yaml": text, "secrets": read_secrets_from_folder(folder, text)}

    async def dash_fn(sess, c):
        return {"yaml": await read_from_dashboard(sess, c["dashboard_url"], conf, c["dashboard_user"], c["dashboard_password"]),
                "secrets": ""}

    got = await _source_call(hass, connection, msg, lg, dash_fn, folder_fn)
    if got:
        connection.send_result(msg["id"], {"source": got[0], **got[2]})
