"""Beschreibung aller Komponenten-Typen (Daten für Generator und Panel).

``pins``    – Liste der Pins eines Typs. ``kind`` bestimmt, welche Board-Pins passen:
              out  = Ausgang möglich, in = lesbar, io = Ein- und Ausgang,
              pwm  = Ausgang mit PWM, adc = Analog-Eingang.
``options`` – Einstellungen; Typen: bool, select, number, text, ref.
``needs_i2c`` – Komponente hängt am I²C-Bus (Pins werden global gewählt).
``singleton`` – darf pro Gerät nur einmal vorkommen.
``platforms`` – auf welchen Plattformen der Typ verfügbar ist.
"""

from __future__ import annotations

from typing import Any

ALL = ["esp8266", "esp32", "bk72xx", "rtl87xx", "ln882x", "rp2"]
ESP32 = ["esp32"]
# I²C gibt es bei ESPHome nicht für LibreTiny (Beken, Realtek, Lightning)
# ESP32-Varianten ohne RMT-Hardware (kein LED-Streifen, kein IR-Sender)
NO_RMT = ["esp32c2", "esp32c61"]
NO_LT = ["esp8266", "esp32", "rp2"]

GROUP_OUT = "Ausgänge"
GROUP_LIGHT = "Lichter"
GROUP_IN = "Eingänge"
GROUP_SENSOR = "Sensoren"
GROUP_I2C = "I²C-Sensoren"
GROUP_IR = "Infrarot"
GROUP_MISC = "Sonstiges"


def _bool(key: str, label: str, default: bool = False, help: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "type": "bool", "default": default, "help": help}


def _select(key: str, label: str, choices: list[Any], default: Any, help: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "type": "select", "choices": choices, "default": default, "help": help}


def _num(key: str, label: str, default: Any, minimum: float | None = None, maximum: float | None = None,
         unit: str = "", help: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "type": "number", "default": default, "min": minimum,
            "max": maximum, "unit": unit, "help": help}


def _text(key: str, label: str, default: str = "", help: str = "", placeholder: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "type": "text", "default": default, "help": help,
            "placeholder": placeholder}


def _pin(key: str, label: str, kind: str) -> dict[str, str]:
    return {"key": key, "label": label, "kind": kind}


INVERTED = _bool("inverted", "Invertiert", False, "Relais/LED schaltet bei LOW statt bei HIGH.")
NAME_NONE = _bool("name_none", "Name = Gerätename", False,
                  "Das Licht heißt in Home Assistant wie das Gerät (name: None). Nur bei einer Entität pro Gerät.")
FX_PULSE = _bool("fx_pulse", "Effekte: Pulsieren (schnell + langsam)", False)
FX_RANDOM = _bool("fx_random", "Effekte: Zufällig (schnell + langsam)", False)
FX_STROBE = _bool("fx_strobe", "Effekt: Blitzen", False)
FREQUENCY = _num("frequency", "PWM-Frequenz", "", 1, 40000, "Hz",
                 "Leer lassen = Standard (1000 Hz). Höher = weniger Flackern, z. B. 19531 Hz.")
UPDATE60 = _text("update_interval", "Messintervall", "60s", "z. B. 10s, 60s, 5min", "60s")
I2C_ADDR = lambda choices, default: _select("address", "I²C-Adresse", choices, default)  # noqa: E731

COMPONENTS: dict[str, dict[str, Any]] = {
    # ----------------------------------------------------------- Ausgänge ---
    "switch": {
        "label": "Relais / Schalter", "group": GROUP_OUT, "platforms": ALL, "icon": "mdi:toggle-switch",
        "pins": [_pin("pin", "Pin", "out")],
        "options": [
            INVERTED,
            _select("restore_mode", "Zustand nach Neustart",
                    ["RESTORE_DEFAULT_OFF", "RESTORE_DEFAULT_ON", "ALWAYS_OFF", "ALWAYS_ON"],
                    "RESTORE_DEFAULT_OFF", "Wiederherstellen (Standard aus), immer aus oder immer an."),
            _num("pulse_ms", "Impuls statt Dauer-An", 0, 0, 60000, "ms",
                 "0 = normaler Schalter. Sonst schaltet er nach dieser Zeit selbst wieder aus (Garagentor, Türöffner)."),
        ],
    },
    "status_led": {
        "label": "Status-LED (blinkt bei WLAN/API-Problemen)", "group": GROUP_OUT, "platforms": ALL,
        "icon": "mdi:led-on", "singleton": True,
        "pins": [_pin("pin", "Pin", "out")],
        "options": [INVERTED],
    },
    # ------------------------------------------------------------- Lichter ---
    "light_binary": {
        "label": "Licht an/aus", "group": GROUP_LIGHT, "platforms": ALL, "icon": "mdi:lightbulb",
        "pins": [_pin("pin", "Pin", "out")],
        "options": [INVERTED, NAME_NONE],
    },
    "light_pwm": {
        "label": "Licht dimmbar (PWM)", "group": GROUP_LIGHT, "platforms": ALL, "icon": "mdi:lightbulb-on",
        "pins": [_pin("pin", "Pin", "pwm")],
        "options": [INVERTED, FREQUENCY, NAME_NONE, FX_PULSE, FX_RANDOM, FX_STROBE],
    },
    "light_rgb": {
        "label": "RGB-Licht (3 PWM-Kanäle)", "group": GROUP_LIGHT, "platforms": ALL, "icon": "mdi:palette",
        "pins": [_pin("red", "Rot", "pwm"), _pin("green", "Grün", "pwm"), _pin("blue", "Blau", "pwm")],
        "options": [INVERTED, FREQUENCY, NAME_NONE, FX_PULSE, FX_RANDOM, FX_STROBE],
    },
    "light_rgbw": {
        "label": "RGBW-Licht (4 PWM-Kanäle)", "group": GROUP_LIGHT, "platforms": ALL, "icon": "mdi:palette",
        "pins": [_pin("red", "Rot", "pwm"), _pin("green", "Grün", "pwm"), _pin("blue", "Blau", "pwm"),
                 _pin("white", "Weiß", "pwm")],
        "options": [INVERTED, FREQUENCY, NAME_NONE, FX_PULSE, FX_RANDOM, FX_STROBE,
                    _bool("color_interlock", "Weiß und Farbe nicht gleichzeitig", False)],
    },
    "light_rgbww": {
        "label": "RGBWW-Licht (5 PWM-Kanäle)", "group": GROUP_LIGHT, "platforms": ALL, "icon": "mdi:palette",
        "pins": [_pin("red", "Rot", "pwm"), _pin("green", "Grün", "pwm"), _pin("blue", "Blau", "pwm"),
                 _pin("cold_white", "Kaltweiß", "pwm"), _pin("warm_white", "Warmweiß", "pwm")],
        "options": [INVERTED, FREQUENCY,
                    _num("cold_temp", "Farbtemperatur Kaltweiß", 6500, 1000, 10000, "K"),
                    _num("warm_temp", "Farbtemperatur Warmweiß", 2700, 1000, 10000, "K"),
                    NAME_NONE, FX_PULSE, FX_RANDOM, FX_STROBE,
                    _bool("color_interlock", "Weiß und Farbe nicht gleichzeitig", False)],
    },
    "light_strip": {
        "not_chips": NO_RMT,
        "label": "LED-Streifen adressierbar (WS2812, SK6812, SM16703 …)", "group": GROUP_LIGHT,
        "platforms": ESP32, "icon": "mdi:led-strip-variant",
        "pins": [_pin("pin", "Datenpin", "out")],
        "options": [
            _num("num_leds", "Anzahl LEDs", 30, 1, 2000),
            _select("chipset", "Chip", ["WS2812", "WS2811", "SK6812", "SM16703", "APA106"], "WS2812"),
            _select("rgb_order", "Farbreihenfolge", ["GRB", "RGB", "BRG", "RBG", "BGR", "GBR"], "GRB"),
        ],
    },
    # ------------------------------------------------------------ Eingänge ---
    "binary_sensor": {
        "label": "Taster / Schalter / Kontakt", "group": GROUP_IN, "platforms": ALL, "icon": "mdi:gesture-tap-button",
        "pins": [_pin("pin", "Pin", "in")],
        "options": [
            _select("mode", "Eingangsmodus", ["INPUT_PULLUP", "INPUT", "INPUT_PULLDOWN"], "INPUT_PULLUP",
                    "INPUT_PULLUP: Taster gegen GND. INPUT_PULLDOWN gibt es nur beim ESP32."),
            _bool("inverted", "Invertiert", True, "Bei Taster gegen GND mit Pull-up: an."),
            _num("debounce_ms", "Entprellen", 50, 0, 2000, "ms"),
            _select("device_class", "Geräteklasse",
                    ["none", "door", "window", "motion", "occupancy", "opening", "moisture", "smoke", "presence"],
                    "none"),
            {"key": "toggle_target", "label": "Schaltet bei Druck um", "type": "ref",
             "ref_types": ["switch", "light_binary", "light_pwm", "light_rgb", "light_rgbw", "light_rgbww",
                           "light_strip"],
             "default": "", "help": "Optional: Taster schaltet direkt ein Relais/Licht auf diesem Gerät um."},
        ],
    },
    "ir_receiver": {
        "label": "IR-Empfänger (z. B. TSOP, VS1838)", "group": GROUP_IR, "platforms": ALL, "icon": "mdi:remote",
        "singleton": True,
        "pins": [_pin("pin", "Pin", "in")],
        "options": [
            _bool("inverted", "Invertiert", True, "TSOP/VS1838 sind meist active-low: an."),
            _select("dump", "Codes ins Log schreiben", ["all", "none"], "all",
                    "all = jedes empfangene Signal erscheint im Log (zum Einlernen)."),
        ],
    },
    "ir_transmitter": {
        "not_chips": NO_RMT,
        "label": "IR-Sender (IR-LED)", "group": GROUP_IR, "platforms": ALL, "icon": "mdi:remote",
        "singleton": True,
        "pins": [_pin("pin", "Pin", "out")],
        "options": [_num("duty", "Trägersignal-Tastverhältnis", 50, 10, 100, "%")],
    },
    # ------------------------------------------------------------ Sensoren ---
    "dht": {
        "label": "DHT11 / DHT22 / AM2302 (Temperatur + Feuchte)", "group": GROUP_SENSOR, "platforms": ALL,
        "icon": "mdi:thermometer-water",
        "pins": [_pin("pin", "Datenpin", "io")],
        "options": [_select("model", "Modell", ["DHT22", "DHT11", "AM2302", "AUTO_DETECT"], "DHT22"), UPDATE60],
    },
    "dallas": {
        "label": "DS18B20 (Temperatur, 1-Wire)", "group": GROUP_SENSOR, "platforms": ALL,
        "icon": "mdi:thermometer",
        "pins": [_pin("pin", "Datenpin", "io")],
        "options": [
            _text("address", "Adresse (optional)", "",
                  "Nur nötig bei mehreren DS18B20 am selben Pin. Erscheint beim ersten Start im Log, z. B. 0x1c0000031edd2a28.",
                  "0x…"),
            _select("resolution", "Auflösung (Bit)", [12, 11, 10, 9], 12,
                    "12 Bit = 0,0625 °C, braucht ca. 750 ms pro Messung. Weniger Bit = schneller, gröber."),
            UPDATE60,
            _text("throttle", "Höchstens alle (Filter, optional)", "",
                  "Zusammen mit der Änderungsschwelle: melden, wenn diese Zeit vergangen ist ODER sich der Wert ändert.", "30s"),
            _text("delta", "Änderungsschwelle in °C (Filter, optional)", "",
                  "Meldet sofort, wenn sich der Wert um mindestens so viel ändert, z. B. 0.2.", "0.2"),
        ],
    },
    "adc": {
        "label": "Analog-Eingang (ADC)", "group": GROUP_SENSOR, "platforms": ALL, "icon": "mdi:sine-wave",
        "pins": [_pin("pin", "Pin", "adc")],
        "options": [
            _select("attenuation", "Dämpfung (nur ESP32)", ["12db", "6db", "2.5db", "0db"], "12db",
                    "12db = Messbereich bis ca. 3,1 V."),
            _text("multiply", "Faktor (optional)", "", "Wert wird damit multipliziert, z. B. 3.2 bei Spannungsteiler.",
                  "1.0"),
            _text("unit", "Einheit (optional)", "V", "", "V"),
            UPDATE60,
        ],
    },
    "ultrasonic": {
        "label": "Ultraschall HC-SR04 (Abstand)", "group": GROUP_SENSOR, "platforms": ALL,
        "icon": "mdi:signal-distance-variant",
        "pins": [_pin("trigger", "Trigger", "out"), _pin("echo", "Echo", "in")],
        "options": [
            _text("timeout", "Maximale Entfernung", "2m", "", "2m"),
            _text("update_interval", "Messintervall", "10s", "", "10s"),
        ],
    },
    # ---------------------------------------------------------- I²C-Sensoren ---
    "bme280": {
        "label": "BME280 (Temperatur, Druck, Feuchte)", "group": GROUP_I2C, "platforms": ALL, "needs_i2c": True,
        "icon": "mdi:thermometer-lines", "pins": [],
        "options": [I2C_ADDR(["0x76", "0x77"], "0x76"), UPDATE60],
    },
    "bmp280": {
        "label": "BMP280 (Temperatur, Druck)", "group": GROUP_I2C, "platforms": ALL, "needs_i2c": True,
        "icon": "mdi:gauge", "pins": [],
        "options": [I2C_ADDR(["0x76", "0x77"], "0x76"), UPDATE60],
    },
    "sht3xd": {
        "label": "SHT30 / SHT31 (Temperatur, Feuchte)", "group": GROUP_I2C, "platforms": ALL, "needs_i2c": True,
        "icon": "mdi:thermometer-water", "pins": [],
        "options": [I2C_ADDR(["0x44", "0x45"], "0x44"), UPDATE60],
    },
    "aht10": {
        "label": "AHT10 / AHT20 / AHT21 (Temperatur, Feuchte)", "group": GROUP_I2C, "platforms": ALL,
        "needs_i2c": True, "icon": "mdi:thermometer-water", "pins": [],
        "options": [_select("variant", "Typ", ["AHT20", "AHT10"], "AHT20"), UPDATE60],
    },
    "bh1750": {
        "label": "BH1750 (Helligkeit)", "group": GROUP_I2C, "platforms": ALL, "needs_i2c": True,
        "icon": "mdi:brightness-5", "pins": [],
        "options": [I2C_ADDR(["0x23", "0x5C"], "0x23"), UPDATE60],
    },
}

# Platzhalter für Katalog-Bausteine (Daten stehen in catalog.json, siehe catalog.py)
COMPONENTS["generic"] = {"label": "Katalog-Baustein", "group": "Katalog", "platforms": ALL, "pins": [],
                         "options": [], "hidden": True, "icon": "mdi:puzzle"}

for _spec in COMPONENTS.values():
    if _spec.get("needs_i2c"):
        _spec["platforms"] = NO_LT

GROUP_ORDER = [GROUP_OUT, GROUP_LIGHT, GROUP_IN, GROUP_IR, GROUP_SENSOR, GROUP_I2C]


# Welche Entitäten ein Typ erzeugt (für die Profi-Einstellungen): Art und Ziele (Schlüssel im YAML, "" = die Entität selbst)
_T = lambda *pairs: [{"key": k, "label": l} for k, l in pairs]  # noqa: E731
ENT_META: dict[str, dict[str, Any]] = {
    "switch": {"domain": "switch", "targets": _T(("", "Relais"))},
    "light_binary": {"domain": "light", "targets": _T(("", "Licht"))},
    "light_pwm": {"domain": "light", "targets": _T(("", "Licht"))},
    "light_rgb": {"domain": "light", "targets": _T(("", "Licht"))},
    "light_rgbw": {"domain": "light", "targets": _T(("", "Licht"))},
    "light_rgbww": {"domain": "light", "targets": _T(("", "Licht"))},
    "light_strip": {"domain": "light", "targets": _T(("", "Licht"))},
    "binary_sensor": {"domain": "binary_sensor", "targets": _T(("", "Taster"))},
    "dht": {"domain": "sensor", "targets": _T(("temperature", "Temperatur"), ("humidity", "Luftfeuchte"))},
    "dallas": {"domain": "sensor", "targets": _T(("", "Temperatur"))},
    "adc": {"domain": "sensor", "targets": _T(("", "Messwert"))},
    "ultrasonic": {"domain": "sensor", "targets": _T(("", "Abstand"))},
    "bme280": {"domain": "sensor", "targets": _T(("temperature", "Temperatur"), ("pressure", "Druck"), ("humidity", "Luftfeuchte"))},
    "bmp280": {"domain": "sensor", "targets": _T(("temperature", "Temperatur"), ("pressure", "Druck"))},
    "sht3xd": {"domain": "sensor", "targets": _T(("temperature", "Temperatur"), ("humidity", "Luftfeuchte"))},
    "aht10": {"domain": "sensor", "targets": _T(("temperature", "Temperatur"), ("humidity", "Luftfeuchte"))},
    "bh1750": {"domain": "sensor", "targets": _T(("", "Helligkeit"))},
}


def components_meta() -> list[dict[str, Any]]:
    out = []
    for key, spec in COMPONENTS.items():
        if spec.get("hidden"):
            continue
        item = {"type": key}
        item.update(spec)
        if key in ENT_META:
            item["ent"] = ENT_META[key]
        out.append(item)
    return out


def default_options(type_key: str) -> dict[str, Any]:
    return {o["key"]: o["default"] for o in COMPONENTS[type_key]["options"]}
