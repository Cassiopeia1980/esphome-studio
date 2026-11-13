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

from .generator import new_api_key, slug
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


def apply_patch(project: dict[str, Any], patch: dict[str, Any]) -> list[str]:
    """Mischt ``patch`` in das Projekt. Dicts werden verschmolzen, alles andere ersetzt.

    ``patch["components"]`` ist eine Liste von Einträgen ``{"name": …, "options": {…}}`` (oder ``uid``/``type``/``pins``),
    die auf vorhandene Bausteine angewendet werden. Liefert Meldungen für Einträge ohne Treffer.
    """
    problems: list[str] = []
    patch = dict(patch or {})
    comp_patch = patch.pop("components", None)
    _merge(project, patch)
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
