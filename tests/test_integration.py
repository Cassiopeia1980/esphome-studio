"""Integrationstest mit echtem Home Assistant (pytest-homeassistant-custom-component).

Aufruf:  pytest tests/test_integration.py
Braucht:  pip install pytest-homeassistant-custom-component
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOMAIN = "esphome_studio"


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Lässt Home Assistant custom_components aus dem Projektordner laden."""


@pytest.fixture
async def setup(hass, hass_ws_client, hass_admin_user):
    hass.config.components.add("frontend")
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="ESPHome Studio")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, await hass_ws_client(hass)


async def call(ws, type_, **payload):
    await ws.send_json({"id": call.n, "type": f"{DOMAIN}/{type_}", **payload})
    call.n += 1
    return await ws.receive_json()


call.n = 1


async def test_meta(setup):
    _, ws = setup
    res = await call(ws, "meta")
    assert res["success"]
    keys = {b["key"] for b in res["result"]["boards"]}
    assert {"d1_mini", "esp32dev", "esp32-c3-devkitm-1", "esp32-s3-devkitc-1", "esp01_1m"} <= keys
    assert any(t["type"] == "light_rgbww" for t in res["result"]["types"])


async def test_project_lifecycle_and_generate(setup, hass):
    _, ws = setup
    res = await call(ws, "new", board="esp32-c3-devkitm-1")
    project = res["result"]["project"]
    assert project["board"] == "esp32-c3-devkitm-1"
    project["name"] = "test-c3"

    secrets = await call(ws, "set_secrets", secrets={"wifi_ssid": "Netz", "wifi_password": "pw", "boese": "x"})
    assert secrets["result"]["secrets"] == {"wifi_ssid": "Netz", "wifi_password": "pw"}

    gen = await call(ws, "generate", project=project)
    assert gen["success"] and gen["result"]["ok"], gen
    assert "esp32-c3-devkitm-1" in gen["result"]["yaml"]
    assert 'wifi_ssid: "Netz"' in gen["result"]["secrets"]

    saved = await call(ws, "save", project=project)
    pid = saved["result"]["project"]["id"]
    assert pid

    listing = await call(ws, "list")
    assert [p["id"] for p in listing["result"]["projects"]] == [pid]
    assert listing["result"]["secrets"]["wifi_ssid"] == "Netz"

    got = await call(ws, "get", project_id=pid)
    assert got["result"]["project"]["name"] == "test-c3"

    # Speichern unter derselben ID überschreibt
    project["friendly_name"] = "Anders"
    again = await call(ws, "save", project={**project, "id": pid})
    assert again["result"]["project"]["id"] == pid
    assert len((await call(ws, "list"))["result"]["projects"]) == 1

    # Persistenz im Store
    store_data = hass.data[DOMAIN]["data"]
    assert pid in store_data["projects"]

    assert (await call(ws, "delete", project_id=pid))["success"]
    assert (await call(ws, "list"))["result"]["projects"] == []
    missing = await call(ws, "get", project_id=pid)
    assert not missing["success"] and missing["error"]["code"] == "not_found"


async def test_invalid_projects_are_rejected(setup):
    _, ws = setup
    res = await call(ws, "save", project={"board": "gibt-es-nicht", "components": []})
    assert not res["success"] and res["error"]["code"] == "invalid_board"
    res = await call(ws, "save", project={"board": "d1_mini", "components": [{}] * 500})
    assert not res["success"] and res["error"]["code"] == "invalid_project"


async def test_random_keys(setup):
    _, ws = setup
    api = (await call(ws, "random", kind="api"))["result"]["value"]
    assert len(api) == 44 and api.endswith("=")
    assert len((await call(ws, "random", kind="ota"))["result"]["value"]) == 32
    assert len((await call(ws, "random", kind="ap"))["result"]["value"]) >= 8
    bad = await call(ws, "random", kind="evil")
    assert not bad["success"]


async def test_non_admin_is_refused(hass, hass_ws_client, hass_read_only_access_token):
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="ESPHome Studio")
    entry.add_to_hass(hass)
    hass.config.components.add("frontend")
    assert await hass.config_entries.async_setup(entry.entry_id)
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    res = await call(ws, "meta")
    assert not res["success"] and res["error"]["code"] == "unauthorized"


async def test_panel_registered_and_unloaded(setup, hass):
    entry, _ = setup
    assert "esphome-studio" in hass.data["frontend_panels"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert "esphome-studio" not in hass.data["frontend_panels"]
    # erneutes Laden (Reload) darf nicht an doppelter Registrierung scheitern
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "esphome-studio" in hass.data["frontend_panels"]


async def test_board_detail_and_import(setup):
    _, ws = setup
    res = await call(ws, "board", key="cb2s")
    assert res["success"] and res["result"]["board"]["platform"] == "bk72xx"
    assert any(p["id"] == "P6" for p in res["result"]["board"]["pins"])
    assert "pin_map" not in res["result"]["board"]
    res = await call(ws, "board", key="gibts-nicht")
    assert not res["success"]

    meta = (await call(ws, "meta"))["result"]
    assert len(meta["boards"]) > 500 and "pins" not in meta["boards"][0]

    yaml_text = ("esphome:\n  name: aus-yaml\nesp8266:\n  board: d1_mini\nwifi:\n  ssid: a\n  password: b\n"
                 "switch:\n  - platform: gpio\n    name: R\n    pin: D1\nscript:\n  - id: x\n    then:\n      - delay: 1s\n")
    res = await call(ws, "import", yaml=yaml_text)
    assert res["success"] and res["result"]["ok"]
    proj = res["result"]["project"]
    assert proj["name"] == "aus-yaml" and proj["components"][0]["pins"] == {"pin": "GPIO5"}
    assert "script:" in proj["extra_yaml"]
    gen = await call(ws, "generate", project=proj)
    assert "script:" in gen["result"]["yaml"]
    bad = await call(ws, "import", yaml="a: [")
    assert bad["success"] and not bad["result"]["ok"]


async def test_catalog_und_generieren(setup):
    _, ws = setup
    res = await call(ws, "catalog")
    assert res["success"]
    entries = {e["id"]: e for e in res["result"]["entries"]}
    assert len(entries) > 500 and entries["bme680.sensor"]["verified"]
    proj = (await call(ws, "new", board="d1_mini"))["result"]["project"]
    proj["components"] = [{"uid": "a1", "type": "generic", "cat": "bme680.sensor", "name": "Wetter", "pins": {},
                           "options": {"s_temperature": True}}]
    gen = await call(ws, "generate", project=proj)
    assert gen["success"] and "platform: bme680" in gen["result"]["yaml"] and gen["result"]["ok"]


OLD_DEVICE = """\
esphome:
  name: keller
  friendly_name: Keller

esp8266:
  board: d1_mini

logger:

api:

ota:
  - platform: esphome
    password: !secret ota

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

light:
  - platform: monochromatic
    name: "Lampe"
    id: lampe
    output: out1
    restore_mode: RESTORE_DEFAULT_OFF

output:
  - platform: esp8266_pwm
    id: out1
    pin: GPIO5
"""


@pytest.fixture
async def folder_target(setup, hass, tmp_path):
    """Device-Builder-Ordner mit einem Altgerät, dessen Dateiname vom Gerätenamen abweicht."""
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    (tmp_path / "kellerlicht.yaml").write_text(OLD_DEVICE, encoding="utf-8")
    (tmp_path / "secrets.yaml").write_text('ota: "altes-passwort"\nwifi_ssid: "netz"\nwifi_password: "pw12345678"\n',
                                           encoding="utf-8")
    _, ws = setup
    res = await call(ws, "deploy_settings", target_dir=str(tmp_path))
    assert res["success"]
    return ws, tmp_path


async def test_source_import_upgrade_deploy_backup_and_restore(folder_target):
    ws, folder = folder_target
    res = await call(ws, "source_import", configuration="kellerlicht.yaml", upgrade=True, deploy=True,
                     patch={"components": [{"name": "Lampe", "options": {"restore_mode": "ALWAYS_OFF"}}]})
    assert res["success"], res
    r = res["result"]
    assert "errors" not in r, r
    assert r["name"] == "keller" and r["file_name"] == "kellerlicht"
    assert r["deployed"] is True
    assert "API verschlüsselt" in r["changes"] and any("Umstellung" in c for c in r["changes"])
    assert len(r["api_key"]) >= 40
    # Es wird dieselbe Datei überschrieben, keine zweite angelegt
    assert not (folder / "keller.yaml").exists()
    new_yaml = (folder / "kellerlicht.yaml").read_text(encoding="utf-8")
    assert "allow_plaintext_upload: true" in new_yaml
    assert "restore_from_flash" not in new_yaml  # ALWAYS_OFF braucht keinen Flash
    assert "keller_api_key" in (folder / "secrets.yaml").read_text(encoding="utf-8")
    # Das alte Passwort bleibt für die Umstellung als eigenes Secret erhalten
    assert "keller_ota_password" in (folder / "secrets.yaml").read_text(encoding="utf-8")

    # Sicherung: Liste, Original, Zurückschreiben
    listing = await call(ws, "backup_get")
    assert [i["name"] for i in listing["result"]["items"]] == ["kellerlicht"]
    orig = await call(ws, "backup_get", name="kellerlicht", which="original")
    assert orig["result"]["yaml"] == OLD_DEVICE
    back = await call(ws, "backup_restore", name="kellerlicht")
    assert back["success"], back
    assert (folder / "kellerlicht.yaml").read_text(encoding="utf-8") == OLD_DEVICE


async def test_source_import_skip_existing_and_patch_finalize(folder_target):
    ws, folder = folder_target
    first = await call(ws, "source_import", configuration="kellerlicht.yaml", upgrade=True)
    assert first["result"]["id"]
    again = await call(ws, "source_import", configuration="kellerlicht.yaml", existing="skip")
    assert again["result"]["skipped"] is True
    # Umstellung abschließen: Flag aus, deployen
    fin = await call(ws, "project_patch", name="keller", patch={"ota": {"migrate": False}}, deploy=True)
    assert fin["success"] and fin["result"]["deployed"] is True, fin
    text = (folder / "kellerlicht.yaml").read_text(encoding="utf-8")
    assert "allow_plaintext_upload" not in text and "encryption: {}" in text


async def test_source_import_unknown_file_reports_error(folder_target):
    ws, _ = folder_target
    res = await call(ws, "source_import", configuration="gibt-es-nicht.yaml")
    assert res["success"] and res["result"].get("errors")


async def test_backup_restore_without_backup(setup):
    _, ws = setup
    res = await call(ws, "backup_restore", name="nichts")
    assert not res["success"]
