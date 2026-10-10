"""Profi-Einstellungen pro Entität: Name, Icon, Einheit, Geräteklasse, Filter …

Die Geräteklassen stammen aus ESPHome 2026.9.1 (``tools/gen_entity_options.py``). Filter sind hier von Hand beschrieben und
mit ``esphome config`` geprüft (``tests/validate_with_esphome.py``).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .yamlutil import Tag

_TIME_RE = re.compile(r"^\d+(\.\d+)?(ms|s|min|h)$")
_NUM_RE = re.compile(r"^[-+]?\d+(\.\d+)?$")
_INT_RE = re.compile(r"^[-+]?\d+$")

# Eigenschaften je Art der Entität
PROPS = {
    "sensor": ["name", "icon", "device_class", "unit_of_measurement", "state_class", "accuracy_decimals", "entity_category",
               "internal", "disabled_by_default"],
    "binary_sensor": ["name", "icon", "device_class", "entity_category", "internal", "disabled_by_default"],
    "text_sensor": ["name", "icon", "entity_category", "internal", "disabled_by_default"],
}
OTHER_PROPS = ["name", "icon", "device_class", "entity_category", "internal", "disabled_by_default"]

# Filter: key, Bezeichnung, Parameter (key, Bezeichnung, Typ float|int|time|text|lambda|list), scalar = Wert direkt hinter dem Schlüssel
FILTERS = {
    "sensor": [
        {"key": "offset", "label": "Offset addieren", "scalar": True, "params": [{"key": "value", "label": "Wert", "type": "float"}]},
        {"key": "multiply", "label": "Multiplizieren", "scalar": True, "params": [{"key": "value", "label": "Faktor", "type": "float"}]},
        {"key": "calibrate_linear", "label": "Kalibrieren (Wertepaare)", "scalar": True,
         "params": [{"key": "datapoints", "label": "Gemessen -> Echt, z. B. 0 -> 0, 100 -> 98", "type": "list"}]},
        {"key": "clamp", "label": "Begrenzen", "params": [{"key": "min_value", "label": "Min", "type": "float", "optional": True},
                                                          {"key": "max_value", "label": "Max", "type": "float", "optional": True}]},
        {"key": "round", "label": "Runden (Nachkommastellen)", "scalar": True, "params": [{"key": "value", "label": "Stellen", "type": "int"}]},
        {"key": "sliding_window_moving_average", "label": "Gleitender Mittelwert",
         "params": [{"key": "window_size", "label": "Fenster", "type": "int"}, {"key": "send_every", "label": "Senden alle", "type": "int"}]},
        {"key": "exponential_moving_average", "label": "Exponentieller Mittelwert",
         "params": [{"key": "alpha", "label": "Alpha (0–1)", "type": "float"}, {"key": "send_every", "label": "Senden alle", "type": "int"}]},
        {"key": "median", "label": "Median",
         "params": [{"key": "window_size", "label": "Fenster", "type": "int"}, {"key": "send_every", "label": "Senden alle", "type": "int"}]},
        {"key": "max", "label": "Maximum im Fenster",
         "params": [{"key": "window_size", "label": "Fenster", "type": "int"}, {"key": "send_every", "label": "Senden alle", "type": "int"}]},
        {"key": "min", "label": "Minimum im Fenster",
         "params": [{"key": "window_size", "label": "Fenster", "type": "int"}, {"key": "send_every", "label": "Senden alle", "type": "int"}]},
        {"key": "throttle", "label": "Mindestpause", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 30s)", "type": "time"}]},
        {"key": "throttle_average", "label": "Mittelwert über Zeit", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 60s)", "type": "time"}]},
        {"key": "delta", "label": "Nur bei Änderung", "scalar": True, "params": [{"key": "value", "label": "Mindeständerung (Zahl oder 5%)", "type": "text"}]},
        {"key": "heartbeat", "label": "Wert regelmäßig erneut senden", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 5min)", "type": "time"}]},
        {"key": "debounce", "label": "Entprellen", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 1s)", "type": "time"}]},
        {"key": "timeout", "label": "Ersatzwert bei Ausfall",
         "params": [{"key": "timeout", "label": "Nach (z. B. 10min)", "type": "time"}, {"key": "value", "label": "Wert (NAN = ungültig)", "type": "text"}]},
        {"key": "skip_initial", "label": "Erste Werte überspringen", "scalar": True, "params": [{"key": "value", "label": "Anzahl", "type": "int"}]},
        {"key": "filter_out", "label": "Wert ausfiltern", "scalar": True, "params": [{"key": "value", "label": "Wert (z. B. 85 oder NAN)", "type": "text"}]},
        {"key": "lambda", "label": "Eigene Formel (C++)", "tag": True, "params": [{"key": "value", "label": "z. B. return x * 2;", "type": "lambda"}]},
    ],
    "binary_sensor": [
        {"key": "invert", "label": "Umkehren", "bare": True, "params": []},
        {"key": "delayed_on", "label": "Einschalten verzögern", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 100ms)", "type": "time"}]},
        {"key": "delayed_off", "label": "Ausschalten verzögern", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 1s)", "type": "time"}]},
        {"key": "delayed_on_off", "label": "Ein und Aus verzögern", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 50ms)", "type": "time"}]},
        {"key": "settle", "label": "Beruhigen", "scalar": True, "params": [{"key": "value", "label": "Zeit (z. B. 250ms)", "type": "time"}]},
        {"key": "lambda", "label": "Eigene Formel (C++)", "tag": True, "params": [{"key": "value", "label": "z. B. return x;", "type": "lambda"}]},
    ],
    "text_sensor": [
        {"key": "to_upper", "label": "Großbuchstaben", "bare": True, "params": []},
        {"key": "to_lower", "label": "Kleinbuchstaben", "bare": True, "params": []},
        {"key": "append", "label": "Text anhängen", "scalar": True, "params": [{"key": "value", "label": "Text (Leerzeichen zählen)", "type": "raw"}]},
        {"key": "prepend", "label": "Text voranstellen", "scalar": True, "params": [{"key": "value", "label": "Text (Leerzeichen zählen)", "type": "raw"}]},
        {"key": "lambda", "label": "Eigene Formel (C++)", "tag": True, "params": [{"key": "value", "label": "z. B. return x;", "type": "lambda"}]},
    ],
}
UNITS = ["°C", "°F", "K", "%", "hPa", "Pa", "bar", "mbar", "V", "mV", "A", "mA", "W", "kW", "Wh", "kWh", "VA", "var", "Hz", "lx",
         "ppm", "ppb", "µg/m³", "mg/m³", "dB", "dBm", "m", "cm", "mm", "km", "L", "mL", "L/min", "m³", "m³/h", "kg", "g",
         "s", "min", "h", "d", "km/h", "m/s", "°", "µS/cm", "Ω", "pH"]


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    return json.loads((Path(__file__).parent / "entity_options.json").read_text(encoding="utf-8"))


def entity_meta() -> dict[str, Any]:
    r = _raw()
    return {"device_classes": r["device_classes"], "state_classes": r["state_classes"], "props": PROPS, "other_props": OTHER_PROPS,
            "filters": FILTERS, "units": UNITS}


def props_for(domain: str) -> list[str]:
    return PROPS.get(domain, [p for p in OTHER_PROPS if p != "device_class" or domain in _raw()["device_classes"]])


def _val(ptype: str, raw: Any, who: str, what: str, errs: list[str]) -> Any:
    t = str(raw if raw is not None else "").strip().replace(",", ".") if ptype in ("float", "int") else str(raw if raw is not None else "").strip()
    if ptype == "float":
        if not _NUM_RE.match(t):
            errs.append(f"{who}: {what} muss eine Zahl sein.")
            return 0
        return float(t) if "." in t else int(t)
    if ptype == "int":
        if not _INT_RE.match(t):
            errs.append(f"{who}: {what} muss eine ganze Zahl sein.")
            return 0
        return int(t)
    if ptype == "time":
        if not _TIME_RE.match(t):
            errs.append(f"{who}: {what} ist keine Zeit (z. B. 30s oder 5min).")
        return t
    if ptype == "raw":
        if raw is None or str(raw) == "":
            errs.append(f"{who}: {what} fehlt.")
        return str(raw or "")
    if ptype == "list":
        items = [x.strip() for x in re.split(r"[,;\n]+", t) if x.strip()]
        if len(items) < 2 or not all(re.match(r"^[-+]?\d+(\.\d+)?\s*->\s*[-+]?\d+(\.\d+)?$", i) for i in items):
            errs.append(f"{who}: {what} braucht mindestens zwei Paare wie „0 -> 0, 100 -> 98“.")
        return items
    if not t:
        errs.append(f"{who}: {what} fehlt.")
    if ptype == "text" and _NUM_RE.match(t.replace("%", "")) and not t.endswith("%"):
        return float(t) if "." in t else int(t)
    return t


def build_filters(domain: str, rows: list[dict[str, Any]], who: str, errs: list[str]) -> list[Any]:
    defs = {f["key"]: f for f in FILTERS.get(domain, [])}
    out: list[Any] = []
    for row in rows or []:
        f = defs.get(str(row.get("t") or ""))
        if not f:
            continue
        vals = row.get("v") or {}
        if f.get("bare"):
            out.append(f["key"])
            continue
        built: dict[str, Any] = {}
        for p in f["params"]:
            raw = vals.get(p["key"])
            if p.get("optional") and str(raw or "").strip() == "":
                continue
            built[p["key"]] = _val(p["type"], raw, who, f"{f['label']}: „{p['label']}“", errs)
        if f.get("tag"):
            out.append({"lambda": Tag("!lambda", built["value"])})
        elif f.get("scalar"):
            out.append({f["key"]: built["value"] if len(f["params"]) == 1 and f["params"][0]["key"] == "value" else built[f["params"][0]["key"]]})
        else:
            if f["key"] == "clamp" and not built:
                errs.append(f"{who}: Begrenzen braucht Min oder Max.")
            out.append({f["key"]: built})
    return out


def apply_entity(item: dict[str, Any], domain: str, cfg: dict[str, Any], who: str, errs: list[str]) -> None:
    """Schreibt die Profi-Einstellungen in die Entität ``item``."""
    if not isinstance(cfg, dict):
        return
    allowed = props_for(domain)
    classes = _raw()["device_classes"].get(domain, [])

    def txt(k: str) -> str:
        return str(cfg.get(k) or "").strip()

    if "name" in allowed and txt("name"):
        item["name"] = txt("name")
    if "icon" in allowed and txt("icon"):
        if not re.match(r"^[a-z0-9-]+:[a-z0-9-]+$", txt("icon")):
            errs.append(f"{who}: Icon „{txt('icon')}“ muss wie mdi:thermometer aussehen.")
        item["icon"] = txt("icon")
    if "device_class" in allowed and txt("device_class"):
        if txt("device_class") not in classes:
            errs.append(f"{who}: Geräteklasse „{txt('device_class')}“ gibt es für diese Art nicht.")
        item["device_class"] = txt("device_class")
    if "unit_of_measurement" in allowed and txt("unit_of_measurement"):
        item["unit_of_measurement"] = txt("unit_of_measurement")
    if "state_class" in allowed and txt("state_class"):
        if txt("state_class") not in _raw()["state_classes"]:
            errs.append(f"{who}: Zustandsklasse „{txt('state_class')}“ ist ungültig.")
        item["state_class"] = txt("state_class")
    if "accuracy_decimals" in allowed and txt("accuracy_decimals") != "":
        if not re.match(r"^\d+$", txt("accuracy_decimals")):
            errs.append(f"{who}: Nachkommastellen müssen eine ganze Zahl sein.")
        else:
            item["accuracy_decimals"] = int(txt("accuracy_decimals"))
    if "entity_category" in allowed and txt("entity_category"):
        if txt("entity_category") not in ("config", "diagnostic"):
            errs.append(f"{who}: Kategorie muss config oder diagnostic sein.")
        item["entity_category"] = txt("entity_category")
    if "internal" in allowed and cfg.get("internal"):
        item["internal"] = True
    if "disabled_by_default" in allowed and cfg.get("disabled_by_default"):
        item["disabled_by_default"] = True
    if domain in FILTERS and cfg.get("filters"):
        fl = build_filters(domain, cfg["filters"], who, errs)
        if fl:
            item["filters"] = list(item.get("filters") or []) + fl
