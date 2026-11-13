"""Hilfen zum Umbauen bestehender Geräte: Änderungen einmischen, auf den aktuellen Stand heben, Ergebnis prüfen.

Reine Logik ohne Home Assistant, damit sie sich testen lässt.
"""

from __future__ import annotations

import copy
import difflib
import json
import re
from typing import Any

import yaml

from .generator import dump_yaml, new_api_key, slug
from .yamlutil import Tag, load_text


def _match_component(components: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any] | None:
    """Findet den Baustein zu einem Patch-Eintrag: über uid, sonst über Name (und optional type)."""
    uid = item.get("uid")
    name = item.get("name")
    typ = item.get("type")
    for c in components:
        if uid and c.get("uid") == uid:
            return c
    hits = [c for c in components if name is not None and c.get("name") == name and (not typ or c.get("type") == typ)]
    return hits[0] if len(hits) == 1 else None


def _merge(dst: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            _merge(dst[key], val)
        else:
            dst[key] = copy.deepcopy(val)


def apply_patch(project: dict[str, Any], patch: dict[str, Any], notes: list[str] | None = None) -> list[str]:
    """Mischt ``patch`` in das Projekt. Dicts werden verschmolzen, alles andere ersetzt.

    ``patch["components"]`` ist eine Liste von Einträgen ``{"name": …, "options": {…}}`` (oder ``uid``/``type``/``pins``),
    die auf vorhandene Bausteine angewendet werden. Liefert Meldungen für Einträge ohne Treffer.
    """
    problems: list[str] = []
    patch = dict(patch or {})
    comp_patch = patch.pop("components", None)
    do_cleanup = patch.pop("cleanup", False)
    _merge(project, patch)
    if do_cleanup:
        found = cleanup_diagnostics(project)
        if notes is not None:
            notes.extend(found)
    if comp_patch:
        comps = project.setdefault("components", [])
        for item in comp_patch:
            if not isinstance(item, dict):
                problems.append("Baustein-Änderung ist kein Objekt.")
                continue
            target = _match_component(comps, item)
            if target is None:
                problems.append(f"Baustein „{item.get('name') or item.get('uid')}“ nicht eindeutig gefunden.")
                continue
            _merge(target, {k: v for k, v in item.items() if k not in ("uid", "type")})
    return problems


def modernize(project: dict[str, Any]) -> list[str]:
    """Hebt ein importiertes Gerät auf API- und OTA-Verschlüsselung. Liefert die vorgenommenen Änderungen als Text.

    - API ohne Verschlüsselung: Verschlüsselung an, neuer Schlüssel (der Import liefert dafür schon einen).
    - OTA mit Passwort oder ohne Absicherung: Verschlüsselung mit einmaliger Umstellung (``migrate``), damit das Gerät
      noch per OTA erreichbar bleibt. Das alte Passwort bleibt dafür im Projekt.
    - Ist die API schon verschlüsselt, bleibt der Schlüssel unangetastet.
    """
    changes: list[str] = []
    api = project.setdefault("api", {})
    ota = project.setdefault("ota", {})
    if api.get("enabled", True) and not api.get("encryption"):
        api["encryption"] = True
        if len(str(api.get("key") or "")) < 40:
            api["key"] = new_api_key()
        changes.append("API verschlüsselt")
    if ota.get("enabled", True) and ota.get("mode") != "encryption" and api.get("enabled", True):
        ota["migrate"] = ota.get("mode") == "password"
        ota["mode"] = "encryption"
        changes.append("OTA verschlüsselt" + (" (einmalige Umstellung)" if ota["migrate"] else ""))
        if ota["migrate"] and not ota.get("password"):
            changes.append("Achtung: altes OTA-Passwort unbekannt")
    return changes


# --------------------------------------------------------- Round-Trip-Prüfung --


def _collect_ids(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "id" and isinstance(v, str):
                out.add(v)
            else:
                _collect_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_ids(v, out)


def _plain(obj: Any, ids: frozenset[str] = frozenset()) -> Any:
    """Tags, Reihenfolge und interne IDs so glätten, dass zwei gleichwertige YAMLs gleich aussehen.

    ``id:``-Schlüssel entfallen, Verweise auf eine ID werden zu ``<id>``. Dadurch fallen reine Umbenennungen
    interner IDs (z. B. ``output_component1`` → ``out_lampe_pin``) nicht auf.
    """
    if isinstance(obj, Tag):
        return f"{obj.tag} {_plain(obj.value, ids)}"
    if isinstance(obj, dict):
        skip = {"id"}
        if obj.get("platform") == "dallas_temp" and obj.get("resolution") == 12:
            skip.add("resolution")  # 12 Bit ist der Standard
        if obj.get("platform") == "dallas_temp":
            skip.add("one_wire_id")  # bei einem einzigen Bus ohne Bedeutung
        if obj.get("platform") in ("wifi_signal", "dallas_temp") and str(obj.get("update_interval")) == "60s":
            skip.add("update_interval")  # 60 s ist der Standard
        return {str(k): _plain(v, ids) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0])) if k not in skip}
    if isinstance(obj, list):
        items = [_plain(v, ids) for v in obj]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False, default=str))
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, (int, float)):
        return obj
    return "<id>" if str(obj) in ids else str(obj)


def normalize(text: str) -> dict[str, str]:
    """YAML → je Top-Level-Schlüssel ein geglätteter Text. Kommentare und Reihenfolge spielen keine Rolle."""
    data = load_text(text) or {}
    ids: set[str] = set()
    _collect_ids(data, ids)
    frozen = frozenset(ids)
    out: dict[str, str] = {}
    for key, val in data.items():
        if key in ("one_wire", "ota") and isinstance(val, dict):  # alte Schreibweise: ein Eintrag statt Liste
            val = [val]
        out[str(key)] = yaml.safe_dump(_plain(val, frozen), allow_unicode=True, sort_keys=True, default_flow_style=False)
    return out


def roundtrip_diff(original: str, generated: str, ignore: tuple[str, ...] = ("substitutions",), limit: int = 60) -> list[str]:
    """Vergleicht Original und neu erzeugte YAML. Leere Liste = gleichwertig, sonst Diff-Zeilen (gekürzt)."""
    a, b = normalize(original), normalize(generated)
    lines: list[str] = []
    for key in sorted(set(a) | set(b)):
        if key in ignore or a.get(key) == b.get(key):
            continue
        lines.append(f"## {key}")
        lines.extend(l for l in difflib.unified_diff((a.get(key) or "").splitlines(), (b.get(key) or "").splitlines(),
                                                      "original", "neu", lineterm="", n=0) if not l.startswith(("---", "+++", "@@")))
    return lines[:limit] + (["…"] if len(lines) > limit else [])


# ------------------------------------------------ Verweise auf IDs prüfen --

_ACTION_KEY = re.compile(r"^(binary_sensor|sensor|text_sensor|switch|light|button|number|select|text|fan|cover|climate|lock|"
                         r"script|output|globals|display|datetime|valve|media_player)\.[a-z_.]+$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LAMBDA_ID = re.compile(r"\bid\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")


def undefined_ids(text: str) -> list[str]:
    """IDs, auf die das YAML verweist (Lambdas, Aktionen, Bedingungen, ``…_id``), die es aber nirgends definiert.

    Einfache Plausibilitätsprüfung, ersetzt kein ``esphome config``; sie fängt aber den häufigsten Importfehler ab
    (Verweis im Zusatz-YAML auf eine ID, die der erzeugte Baustein nicht mehr trägt).
    """
    data = load_text(text) or {}
    defined: set[str] = set()
    refs: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, Tag):
            return
        if isinstance(obj, dict):
            nm = obj.get("name")
            if isinstance(nm, str) and "id" not in obj and "$" not in nm:
                defined.add(slug(nm))  # ESPHome leitet die ID aus dem Namen ab
            for k, v in obj.items():
                ks = str(k)
                if ks == "variables":
                    continue  # Typangaben von API-Diensten (z. B. „string“), keine Verweise
                if ks == "id" and isinstance(v, str):
                    defined.add(v)
                elif isinstance(v, str) and not v.startswith("$") and _IDENT.match(v) and (
                        _ACTION_KEY.match(ks) or (ks.endswith("_id") and ks != "id")):
                    refs.add(v)
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            refs.update(_LAMBDA_ID.findall(obj))

    walk(data)
    return sorted(refs - defined)


# ------------------------------------------- Diagnose aufräumen (Sammelumbau) --

def _tval(v: Any) -> Any:
    return v.value if isinstance(v, Tag) else v


def cleanup_diagnostics(project: dict[str, Any]) -> list[str]:
    """Web-Server aus, Debug-Sensoren bis auf den Reset-Grund aus, beide Uptime-Sensoren (Zahl und Text) vom Studio.

    Räumt auch das Zusatz-YAML auf: ``web_server``, Sensoren der Plattform ``uptime``, Debug-Sensoren und alte
    Template-Sensoren, die per Lambda eine Betriebszeit berechnen. Name, Symbol und Kategorie der alten Text-Betriebszeit
    bleiben erhalten (``diag_custom``), damit die Entität in Home Assistant dieselbe bleibt.
    """
    notes: list[str] = []
    diag = project.setdefault("diag", {})
    if project.get("web_server"):
        project["web_server"] = False
        notes.append("Web-Server ausgeschaltet")
    had_debug = any(diag.get(k) for k in ("debug_heap", "debug_loop", "debug_reset"))
    for k in ("debug_heap", "debug_loop"):
        if diag.get(k):
            diag[k] = False
            notes.append("Debug-Sensor aus (" + k + ")")
    if had_debug:
        diag["debug_reset"] = True

    uptime_removed = False
    numeric_info: dict[str, Any] = {}
    candidates: list[dict[str, Any]] = []
    text = str(project.get("extra_yaml") or "").strip()
    if text:
        extra = load_text(text)
        if isinstance(extra, dict):
            changed = False
            if "web_server" in extra:
                del extra["web_server"]
                changed = True
                notes.append("web_server aus dem Zusatz-YAML entfernt")
            sensors = extra.get("sensor")
            uptime_items: list[dict[str, Any]] = []
            uptime_ids: set[str] = set()
            if isinstance(sensors, list):
                for it in sensors:
                    if isinstance(it, dict) and it.get("platform") == "uptime":
                        uptime_items.append(it)
                        if isinstance(it.get("id"), str):
                            uptime_ids.add(it["id"])
            # Textsensoren: alte Betriebszeit (Plattform uptime oder Lambda über einen Uptime-Sensor) entfernen
            tsens = extra.get("text_sensor")
            if isinstance(tsens, list):
                keep = []
                for it in tsens:
                    plat = it.get("platform") if isinstance(it, dict) else None
                    lam = str(_tval(it.get("lambda")) or "") if isinstance(it, dict) else ""
                    if plat == "uptime" or (plat == "template" and any(re.search(rf"\bid\(\s*{re.escape(i)}\s*\)", lam)
                                                                      for i in uptime_ids)):
                        candidates.append(it)
                        changed = True
                        notes.append(f"Betriebszeit „{it.get('name', '')}“ aus dem Zusatz-YAML entfernt (kommt jetzt vom Studio)")
                        continue
                    if plat == "debug":
                        rest = {k: v for k, v in it.items() if k in ("platform", "reset_reason")}
                        if len(rest) != len(it):
                            changed = True
                            notes.append("Debug-Text-Sensoren bis auf den Reset-Grund entfernt")
                        if len(rest) > 1:
                            keep.append(rest)
                        continue
                    keep.append(it)
                if len(keep) != len(tsens):
                    extra["text_sensor"] = keep
            # Uptime-Sensoren nur entfernen, wenn nichts anderes auf ihre ID verweist (z. B. Start-Sperre im Schalter)
            if isinstance(sensors, list):
                without = [it for it in sensors if not any(it is u for u in uptime_items)]
                blob = dump_yaml({**extra, "sensor": without}) + json.dumps(project.get("components") or [], default=str)
                keep = []
                for it in sensors:
                    if isinstance(it, dict) and it.get("platform") == "uptime":
                        iid = it.get("id")
                        if isinstance(iid, str) and re.search(rf"\bid\(\s*{re.escape(iid)}\s*\)", blob):
                            keep.append(it)
                            continue
                        uptime_removed = True
                        changed = True
                        if isinstance(it.get("name"), str) and it["name"].strip() and not it.get("internal"):
                            numeric_info = {k: it[k] for k in ("name", "icon") if isinstance(it.get(k), str)}
                            if isinstance(it.get("entity_category"), str):
                                numeric_info["category"] = it["entity_category"]
                        notes.append(f"Uptime-Sensor „{it.get('name', '')}“ in die Studio-Laufzeit übernommen")
                        continue
                    if isinstance(it, dict) and it.get("platform") == "debug":
                        changed = True
                        notes.append("Debug-Sensoren aus dem Zusatz-YAML entfernt")
                        continue
                    keep.append(it)
                if len(keep) != len(sensors):
                    extra["sensor"] = keep
            for dom in ("sensor", "text_sensor"):
                if dom in extra and not extra[dom]:
                    del extra[dom]
            if changed:
                project["extra_yaml"] = dump_yaml(extra).rstrip("\n") + "\n" if extra else ""

    if not diag.get("uptime"):
        diag["uptime"] = True
        notes.append("Laufzeit als Zahl eingeschaltet")
    if not diag.get("uptime_text"):
        diag["uptime_text"] = True
        notes.append("Betriebszeit als Text eingeschaltet")
    if numeric_info:
        project.setdefault("diag_custom", {}).setdefault("uptime", {}).update(numeric_info)
    if candidates:
        c = candidates[0]
        custom = project.setdefault("diag_custom", {}).setdefault("uptime_text", {})
        if isinstance(c.get("name"), str):
            custom["name"] = c["name"]
        if isinstance(c.get("icon"), str):
            custom["icon"] = c["icon"]
        if isinstance(c.get("entity_category"), str):
            custom["category"] = c["entity_category"]
        if isinstance(c.get("format"), dict):
            custom["format"] = {k: _tval(v) for k, v in c["format"].items()}
    return notes


def _expand(text: str, subs: dict[str, Any]) -> str:
    def rep(m: re.Match[str]) -> str:
        key = m.group(1) or m.group(2)
        return str(subs[key]) if key in subs else m.group(0)
    return re.sub(r"\$\{(\w+)\}|\$(\w+)", rep, text)


def uptime_entity_from_yaml(yaml_text: str) -> dict[str, Any]:
    """Name, Symbol und Kategorie des sichtbaren Uptime-Sensors (Zahl) aus einer älteren YAML. Leer, wenn es keinen gibt.

    Substitutionen im Namen (``${friendly_name}``) werden aufgelöst, damit der Name in jedem Fall derselbe Text ist.
    """
    data = load_text(yaml_text) or {}
    if not isinstance(data, dict):
        return {}
    subs = data.get("substitutions") if isinstance(data.get("substitutions"), dict) else {}
    subs = {str(k): _tval(v) for k, v in subs.items()}
    sensors = data.get("sensor")
    for it in sensors if isinstance(sensors, list) else []:
        if isinstance(it, dict) and it.get("platform") == "uptime" and not it.get("internal") and isinstance(it.get("name"), str) \
                and it["name"].strip():
            out: dict[str, Any] = {"name": _expand(it["name"], subs)}
            if isinstance(it.get("icon"), str):
                out["icon"] = it["icon"]
            if isinstance(it.get("entity_category"), str):
                out["category"] = it["entity_category"]
            return out
    return {}
