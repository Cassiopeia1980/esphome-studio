"""Baut aus dem ESPHome-Schema den Baustein-Katalog (catalog.json).

Schritt 1 – Schema von ESPHome erzeugen lassen (mit dem Python, in dem ESPHome installiert ist):

    curl -sSO https://raw.githubusercontent.com/esphome/esphome/dev/script/build_language_schema.py
    python build_language_schema.py --output-path schema_out

Schritt 2 – Katalog daraus bauen:

    python tools/gen_catalog.py schema_out

Schritt 3 – Jeden Baustein mit `esphome config` prüfen und die unterstützten Plattformen eintragen:

    python tools/verify_catalog.py /pfad/zu/esphome

Danach liegt custom_components/esphome_studio/catalog.json bereit. ESPHome wird zur Laufzeit nicht gebraucht.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "esphome_studio" / "catalog.json"

# Komponenten, die das Studio selbst erzeugt oder die keine eigenen Bausteine sein können
SYSTEM_COMPONENTS = {
    "api", "bk72xx", "captive_portal", "dashboard_import", "esp32", "esp8266", "esphome", "external_components", "i2c", "spi", "uart",
    "libretiny", "ln882x", "nrf52", "packages", "rp2", "rp2040", "status_led", "substitutions", "web_server", "wifi", "async_tcp",
    "socket", "preferences", "json", "sha256", "hmac_md5", "hmac_sha256", "bytebuffer", "split_buffer", "web_server_base",
    "web_server_idf", "host", "zephyr_ble_server", "demo", "factory_reset", "network", "mdns", "logger", "ota", "time", "debug",
    "remote_transmitter", "remote_receiver", "mapping", "noise", "esp32_hosted", "tinyusb", "usb_host", "esp_ldo", "psram",
    "rp2040_ble", "rp2_ble_tracker", "bk72xx_ble", "bk72xx_ble_tracker", "ln882h_ble", "ln882h_ble_tracker",
}
# Port-Expander: Anzahl der Pins. Sie erscheinen in der Pin-Auswahl anderer Bausteine.
EXPANDERS = {"mcp23008": 8, "mcp23016": 16, "mcp23017": 16, "mcp23s08": 8, "mcp23s17": 16, "pca6416a": 16, "pca9554": 8,
             "tca9555": 16, "pcf8574": 8, "pi4ioe5v6408": 8, "ch422g": 8, "xl9535": 16, "sn74hc595": 8, "sn74hc165": 8, "ch423": 16}

DOMAINS = {
    "sensor": "Sensor", "binary_sensor": "Binär-Sensor", "text_sensor": "Text-Sensor", "switch": "Schalter",
    "output": "Ausgang", "light": "Licht", "fan": "Lüfter", "cover": "Rollladen/Tor", "climate": "Klima",
    "button": "Taster-Aktion", "number": "Zahl", "select": "Auswahl", "lock": "Schloss", "valve": "Ventil",
    "display": "Display", "touchscreen": "Touchscreen", "time": "Uhrzeit", "datetime": "Datum/Uhrzeit-Eingabe", "text": "Texteingabe",
    "event": "Ereignis", "update": "Update", "water_heater": "Warmwasser", "canbus": "CAN-Bus", "stepper": "Schrittmotor",
    "microphone": "Mikrofon", "speaker": "Lautsprecher", "media_player": "Mediaplayer", "audio_dac": "Audio-DAC",
    "audio_adc": "Audio-ADC", "packet_transport": "Datenübertragung", "one_wire": "1-Wire-Bus", "alarm_control_panel": "Alarmanlage",
    "image": "Bild", "infrared": "Infrarot", "radio_frequency": "Funk (RF)", "motion": "Bewegung",
}
# Entitäts-Grundfelder, die das Studio selbst setzt oder die in einen eigenen Abschnitt gehören
SKIP_KEYS = {
    "id", "name", "icon", "internal", "disabled_by_default", "entity_category", "state_class", "device_class",
    "unit_of_measurement", "accuracy_decimals", "filters", "mqtt_id", "web_server", "publish_initial_state",
    "setup_priority", "update_interval", "area_id", "device_id", "translation_key", "ble_client_id",
}
SUB_EXTENDS = {
    "sensor._SENSOR_SCHEMA": "sensor",
    "binary_sensor._BINARY_SENSOR_SCHEMA": "binary_sensor",
    "text_sensor._TEXT_SENSOR_SCHEMA": "text_sensor",
}
BUS_PARENTS = {"i2c::I2CDevice": "i2c", "uart::UARTDevice": "uart", "spi::SPIDevice": "spi"}
BUS_IDS = {"i2c_id", "uart_id", "spi_id"}

DE = {
    "temperature": "Temperatur", "humidity": "Luftfeuchte", "pressure": "Druck", "co2": "CO₂", "tvoc": "TVOC",
    "voltage": "Spannung", "current": "Strom", "power": "Leistung", "energy": "Energie", "frequency": "Frequenz",
    "power_factor": "Leistungsfaktor", "bus_voltage": "Busspannung", "shunt_voltage": "Shunt-Spannung",
    "battery_level": "Akkustand", "battery_voltage": "Akkuspannung", "illuminance": "Helligkeit",
    "distance": "Abstand", "moisture": "Feuchte", "uv_index": "UV-Index", "lux": "Helligkeit", "ph": "pH",
    "gas_resistance": "Gasswiderstand", "altitude": "Höhe", "dew_point": "Taupunkt", "iaq": "Luftqualität",
    "eco2": "eCO₂", "aqi": "Luftqualitätsindex", "pm_1_0": "PM1,0", "pm_2_5": "PM2,5", "pm_10_0": "PM10",
    "pm_4_0": "PM4,0", "ambient_light": "Umgebungslicht", "proximity": "Näherung", "rssi": "Signalstärke",
    "weight": "Gewicht", "speed": "Geschwindigkeit", "state": "Zustand", "moving": "Bewegung", "occupancy": "Belegung",
    "presence": "Anwesenheit", "motion": "Bewegung", "total": "Gesamt", "total_energy": "Gesamtenergie",
    "reactive_power": "Blindleistung", "apparent_power": "Scheinleistung", "ct_clamp": "Stromzange",
    "accel_x": "Beschleunigung X", "accel_y": "Beschleunigung Y", "accel_z": "Beschleunigung Z",
    "gyro_x": "Gyro X", "gyro_y": "Gyro Y", "gyro_z": "Gyro Z", "version": "Version", "mac_address": "MAC-Adresse",
    "status": "Status", "light": "Licht", "has_target": "Ziel erkannt", "external_temperature": "Außentemperatur",
    "internal_temperature": "Innentemperatur", "outdoor_temperature": "Außentemperatur", "factory_reset": "Werkseinstellung",
    "signal_strength": "Signalstärke", "iaq_accuracy": "Luftqualität Genauigkeit", "restart": "Neustart",
    "conductivity": "Leitfähigkeit", "flow": "Durchfluss", "active_power": "Wirkleistung", "heading": "Richtung",
    "has_moving_target": "Bewegtes Ziel", "has_still_target": "Ruhendes Ziel", "moving_distance": "Entfernung bewegt",
    "still_distance": "Entfernung ruhend", "moving_energy": "Energie bewegt", "still_energy": "Energie ruhend",
    "detection_distance": "Erfassungsentfernung", "target_count": "Anzahl Ziele", "sensitivity": "Empfindlichkeit",
    "radon": "Radon", "radon_long_term": "Radon langfristig", "total_power": "Gesamtleistung",
    "carbon_monoxide": "Kohlenmonoxid", "nitrogen_dioxide": "Stickstoffdioxid", "ethanol": "Ethanol",
    "breath_voc_equivalent": "Atem-VOC", "co2_equivalent": "CO₂-Äquivalent", "voc_index": "VOC-Index", "nox_index": "NOx-Index",
    "acceleration_x": "Beschleunigung X", "acceleration_y": "Beschleunigung Y", "acceleration_z": "Beschleunigung Z",
    "current_l1": "Strom L1", "current_l2": "Strom L2", "current_l3": "Strom L3", "voltage_l1": "Spannung L1",
    "voltage_l2": "Spannung L2", "voltage_l3": "Spannung L3", "current_1": "Strom 1", "current_2": "Strom 2",
    "active_power_1": "Wirkleistung 1", "active_power_2": "Wirkleistung 2", "timestamp": "Zeitstempel",
    "energy_production_day": "Tagesertrag", "total_energy_production": "Gesamtertrag", "timeout": "Zeitüberschreitung",
    "presence_timeout": "Anwesenheits-Timeout", "fan_speed": "Lüfterstufe", "level": "Pegel", "t_room": "Raumtemperatur",
    "t_room_set": "Raum-Solltemperatur", "infrared": "Infrarot", "full_spectrum": "Gesamtspektrum", "resistance": "Widerstand",
    "export_active_energy": "Export Wirkenergie", "import_active_energy": "Import Wirkenergie",
    "forward_active_energy": "Bezug Wirkenergie", "reverse_active_energy": "Einspeisung Wirkenergie",
    "pmc_0_3": "Partikel >0,3 µm", "pmc_0_5": "Partikel >0,5 µm", "pmc_1_0": "Partikel >1,0 µm", "pmc_2_5": "Partikel >2,5 µm",
    "pmc_5_0": "Partikel >5 µm", "pmc_10_0": "Partikel >10 µm", "battery_type": "Batterietyp", "bluetooth": "Bluetooth",
    "ip_address": "IP-Adresse", "ssid": "SSID", "uptime": "Laufzeit", "formaldehyde": "Formaldehyd",
}


def load(schema_dir: str) -> dict:
    d: dict = {}
    for f in glob.glob(str(Path(schema_dir) / "*.json")):
        d.update(json.loads(Path(f).read_text(encoding="utf-8")))
    return d


def pretty(key: str) -> str:
    return DE.get(key) or key.replace("_", " ").strip().capitalize()


def pin_kind(modes: list[str]) -> str:
    if "output" in modes and "input" not in modes:
        return "out"
    if "input" in modes and "output" not in modes:
        return "in"
    return "io"


def to_default(v):
    if v in (None, ""):
        return ""
    return v


_D: dict = {}
_SKIP_EXT = {"core", "esphome"}


def resolved_vars(sch: dict, depth: int = 0) -> dict:
    """config_vars samt den Variablen aus erweiterten Schemas desselben ESPHome-Bauteils (z. B. pipsolar.PIPSOLAR_COMPONENT_SCHEMA)."""
    cvars = dict(sch.get("config_vars") or {})
    if depth > 4:
        return cvars
    for ext in sch.get("extends") or []:
        comp, _, name = ext.partition(".")
        if not name or comp in _SKIP_EXT or comp in DOMAINS:
            continue
        sub = (((_D.get(comp) or {}).get("schemas") or {}).get(name) or {}).get("schema")
        if isinstance(sub, dict):
            for k, v in resolved_vars(sub, depth + 1).items():
                cvars.setdefault(k, v)
    return cvars


def build_entry(key: str, data: dict, class_to_hub: dict[str, str]) -> dict | None:
    comp, domain = key.rsplit(".", 1) if "." in key else (key, "hub")
    cs = data.get("schemas", {}).get("CONFIG_SCHEMA", {})
    sch = cs.get("schema")
    if not isinstance(sch, dict):
        return None
    extends = sch.get("extends") or []
    cvars = resolved_vars(sch)
    entry: dict = {
        "id": key, "domain": domain, "platform": comp, "label": comp, "pins": [], "fields": [], "subs": [],
        "bus": None, "hub": None, "hub_key": None, "refs": [],
        "self_entity": domain not in ("hub", "output") and (any(e.split(".")[0] == domain and "SCHEMA" in e for e in extends) or "name" in cvars),
        "has_interval": "update_interval" in cvars, "interval_default": (cvars.get("update_interval") or {}).get("default"),
        "unsupported": "",
    }
    idv = cvars.get("id", {})
    entry["cls"] = (idv.get("id_type") or {}).get("class") or ""
    entry["provides"] = ([entry["cls"]] if entry["cls"] else []) + list((idv.get("id_type") or {}).get("parents", []))
    for parent in (idv.get("id_type") or {}).get("parents", []):
        if parent in BUS_PARENTS:
            entry["bus"] = BUS_PARENTS[parent]
    for k, v in cvars.items():
        if k in BUS_IDS and entry["bus"] is None:
            entry["bus"] = k[:-3]
    for k, v in cvars.items():
        if k in SKIP_KEYS or k.startswith("on_"):
            continue
        t = v.get("type")
        req = v.get("key") == "Required"
        if v.get("key") == "GeneratedID" or t == "use_id" or "use_id_type" in v:
            if k in BUS_IDS or k == "id":
                continue
            cls = v.get("use_id_type") or ""
            if cls in class_to_hub and entry["hub"] is None and class_to_hub[cls] != key:
                entry["hub"], entry["hub_key"] = class_to_hub[cls], k
            elif cls:
                entry["refs"].append({"key": k, "label": pretty(k), "cls": cls, "required": req})
            elif req:
                entry["unsupported"] = f"braucht {k}"
            continue
        if t == "trigger" or t == "registry":
            continue
        if t == "schema":
            ext = (v.get("schema") or {}).get("extends") or []
            sub_domain = next((e.split(".")[0] for e in ext
                               if e.split(".")[0] in DOMAINS and "SCHEMA" in e and "." in e), None)
            if sub_domain:
                entry["subs"].append({"key": k, "label": pretty(k), "domain": sub_domain, "required": req})
            elif req:
                entry["unsupported"] = f"braucht Abschnitt {k}"
            continue
        if t == "pin" or (t is None and (k == "pin" or k.endswith("_pin"))):
            entry["pins"].append({"key": k, "label": k.replace("_pin", "").replace("_", " ") or k, "kind": pin_kind(v.get("modes") or []),
                                  "required": req, "modes": v.get("modes") or []})
            continue
        f: dict = {"key": k, "label": k.replace("_", " "), "required": req, "default": to_default(v.get("default"))}
        if t == "enum":
            f["type"] = "enum"
            f["choices"] = list((v.get("values") or {}).keys())
        elif t == "boolean":
            f["type"] = "bool"
        else:
            f["type"] = "text"
        entry["fields"].append(f)
    # Reihenfolge: Pflicht zuerst
    entry["fields"].sort(key=lambda f: not f["required"])
    entry["pins"].sort(key=lambda p: not p["required"])
    if entry["bus"] == "spi":
        pass
    return entry


def main() -> int:
    schema_dir = sys.argv[1] if len(sys.argv) > 1 else "schema_out"
    D = load(schema_dir)
    _D.update(D)
    # Hubs: Bauteile mit eigenem Abschnitt (z. B. ld2410, ads1115). Plattformen verweisen per use_id-Klasse darauf.
    BUS_CLASSES = {"uart::UARTComponent", "i2c::I2CBus", "spi::SPIComponent"}
    comp_class: dict[str, str] = {}
    # sortiert: mehrere Komponenten teilen sich manchmal dieselbe Klasse (z. B. LibreTiny), die Reihenfolge der Schema-Dateien ist aber zufällig
    for key, data in sorted(D.items()):
        if "." in key or key in DOMAINS:
            continue
        sch = (data.get("schemas", {}).get("CONFIG_SCHEMA", {}) or {}).get("schema") or {}
        cls = (resolved_vars(sch).get("id", {}).get("id_type") or {}).get("class")
        if cls and cls not in BUS_CLASSES:
            comp_class[cls] = key
    referenced = set()
    for key, data in D.items():
        if "." in key and key.rsplit(".", 1)[1] in DOMAINS:
            for k, v in resolved_vars(data.get("schemas", {}).get("CONFIG_SCHEMA", {}).get("schema") or {}).items():
                cls = v.get("use_id_type")
                if cls in comp_class and k not in BUS_IDS:
                    referenced.add(comp_class[cls])
    hubs = referenced
    class_to_hub = {c: h for c, h in comp_class.items() if h in hubs}
    entries = []
    for h in sorted(hubs):
        try:
            e = build_entry(h, D[h], class_to_hub)
        except Exception as exc:  # noqa: BLE001
            print("Fehler bei Hub", h, exc)
            continue
        if e:
            e["id"] = h
            e["domain"] = "hub"
            e["label"] = h
            entries.append(e)
    for key, data in sorted(D.items()):
        if "." not in key:
            continue
        domain = key.rsplit(".", 1)[1]
        if domain not in DOMAINS:
            continue
        try:
            e = build_entry(key, data, class_to_hub)
        except Exception as exc:  # noqa: BLE001
            print("Fehler bei", key, exc)
            continue
        if e:
            entries.append(e)
    providers: set[str] = set()
    for e in entries:
        providers.update(e["provides"])
    for e in entries:  # Verweise nur behalten, wenn es im Katalog einen Baustein gibt, der die Klasse liefert
        keep = []
        for r in e["refs"]:
            if r["cls"] in providers:
                keep.append(r)
            elif r["required"] and not e["unsupported"]:
                e["unsupported"] = f"braucht {r['label']}"
        e["refs"] = keep
    ids = {e["id"] for e in entries}
    for e in entries:
        if e["hub"] and e["hub"] not in ids:
            e["unsupported"] = e["unsupported"] or f"Hub {e['hub']} nicht darstellbar"
    # Weitere Komponenten ohne Plattform (Port-Expander, Deep Sleep, Servo, RFID-Leser, Bluetooth …)
    have = {e["id"] for e in entries}
    for key, data in sorted(D.items()):
        if "." in key or key in DOMAINS or key in have or key in SYSTEM_COMPONENTS:
            continue
        try:
            e = build_entry(key, data, class_to_hub)
        except Exception as exc:  # noqa: BLE001
            print("Fehler bei", key, exc)
            continue
        if e:
            e.update(id=key, domain="hub", label=key, top=True)
            entries.append(e)
    for e in entries:
        if e["id"] in EXPANDERS:
            e["expander"] = EXPANDERS[e["id"]]
            e["expander_key"] = "mcp23xxx" if e["id"].startswith("mcp23") and e["id"] != "mcp23016" else e["id"]  # Schlüssel in der Pin-Angabe
            if e["id"] == "sn74hc165":
                e["expander_kinds"] = ["in"]
            if e["id"] == "sn74hc595":
                e["expander_kinds"] = ["out"]
            e["pullup"] = e["id"].startswith("mcp23") or e["id"] in ("pca6416a", "pi4ioe5v6408")  # kann INPUT_PULLUP
    DOMAINS_OUT = dict(DOMAINS, hub="Hubs & weitere Komponenten")
    cat = {"domains": DOMAINS_OUT, "entries": entries}
    # Prüfergebnisse früherer Läufe (tools/verify_catalog.py) behalten, wenn der Baustein gleich geblieben ist
    if OUT.exists():
        try:
            old = {e["id"]: e for e in json.loads(OUT.read_text(encoding="utf-8"))["entries"]}
        except (ValueError, KeyError):
            old = {}
        for e in entries:
            o = old.get(e["id"])
            if not o or "verified" not in o:
                continue
            e["platforms"], e["verified"], e["note"] = o.get("platforms", []), o["verified"], o.get("note", "")
            for k_ in ("baud_default", "uart", "needs", "needs_cat", "needs_dom", "no_id", "force"):
                if o.get(k_):
                    e[k_] = o[k_]
            if o.get("self_entity") is False:
                e["self_entity"] = False
            old_f = {x["key"]: x for x in o["fields"]}
            for x in e["fields"]:
                of = old_f.get(x["key"])
                if not of:
                    continue
                for k_ in ("as", "fill"):
                    if of.get(k_):
                        x[k_] = of[k_]
                if of.get("type") == "enum" and x["type"] != "enum":
                    x["type"], x["choices"] = "enum", of["choices"]
            for lst in ("fields", "pins"):  # beim Prüfen gelernte Pflichtfelder/-pins behalten
                have = {x["key"] for x in e[lst]}
                e[lst].extend(x for x in o[lst] if x["key"] not in have and x.get("required"))
            for lst in ("fields", "pins"):
                req = {x["key"] for x in o[lst] if x.get("required")}
                for x in e[lst]:
                    if x["key"] in req:
                        x["required"] = True
    OUT.write_text(json.dumps(cat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sup = [e for e in entries if not e["unsupported"]]
    print(f"{len(entries)} Bausteine, davon {len(sup)} ohne Sonderbedarf -> {OUT}")
    import collections
    print(collections.Counter(e["domain"] for e in sup))
    print("Busse:", collections.Counter(e["bus"] for e in sup), "Hubs:", collections.Counter(bool(e["hub"]) for e in sup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
