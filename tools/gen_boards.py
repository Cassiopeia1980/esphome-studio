"""Liest alle Boards und Pin-Eigenschaften aus einer installierten ESPHome-Version aus
und schreibt custom_components/esphome_studio/boards_data.json.

Aufruf (mit dem Python, in dem ESPHome installiert ist):

    python tools/gen_boards.py

Die erzeugte Datei wird mitgeliefert, ESPHome selbst wird zur Laufzeit nicht gebraucht.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import sys
from pathlib import Path

import esphome
from esphome.const import __version__ as ESPHOME_VERSION

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "esphome_studio" / "boards_data.json"

# ----------------------------------------------------------------- Helfer ----


def pin(gpio, pid=None, short=None, **flags):
    pid = pid or f"GPIO{gpio}"
    d = {"id": pid, "gpio": gpio}
    d.update({k: v for k, v in flags.items() if v not in (None, False, "")})
    return d


def resolve(table, key):
    v = table.get(key)
    seen = 0
    while isinstance(v, str) and seen < 10:
        v = table.get(v)
        seen += 1
    return v if isinstance(v, dict) else {}


# --------------------------------------------------------------- ESP8266 -----

ESP8266_CHIP = {
    "label": "ESP8266", "platform": "esp8266", "i2c": ["GPIO4", "GPIO5"],
    "pins": [
        pin(0, strapping="LOW beim Start = Flash-Modus. Taster/Relais hier können das Booten stören."),
        pin(1, uart=True, note="UART0 TX (Logger)"),
        pin(2, strapping="Muss beim Start HIGH sein. Blaue Onboard-LED auf vielen Boards (invertiert)."),
        pin(3, uart=True, note="UART0 RX (Logger)"),
        pin(4, note="Standard-I²C SDA"),
        pin(5, note="Standard-I²C SCL"),
        pin(12), pin(13), pin(14),
        pin(15, strapping="Muss beim Start LOW sein (Pull-down auf den meisten Boards)."),
        pin(16, no_pwm=True, no_pullup=True, boot_high=True, no_i2c=True,
            note="Kein PWM, kein Pull-up, kein I²C. Liegt beim Start kurz auf HIGH (Deep-Sleep-Wecken): "
                 "ein Relais kann dabei einmal klicken."),
        pin(17, "A0", adc="adc", adc_only=True, input_only=True,
            note="Analog-Eingang, 0–1 V (D1 Mini mit Spannungsteiler bis 3,2 V)"),
    ],
}
ESP8266_CHIP["pins"][-1]["gpio"] = 99
ESP01_ONLY = {"GPIO0", "GPIO1", "GPIO2", "GPIO3"}
ESP01_BOARDS = {"esp01", "esp01_1m"}

# ----------------------------------------------------------------- ESP32 -----

GENERIC_STRAP = "Boot-Pin (Strapping): Beim Start nicht von außen belasten, Pegel siehe Datenblatt."

NOTES = {
    "ESP32": {
        0: "Boot-Taster. LOW beim Start = Flash-Modus.",
        2: "Beim Start LOW/offen lassen. Onboard-LED auf vielen Boards.",
        5: "Gibt beim Start kurz ein PWM-Signal aus.",
        12: "MTDI: HIGH beim Start verstellt die Flash-Spannung, das Board bootet dann nicht.",
        14: "Gibt beim Start kurz ein PWM-Signal aus.",
        15: "Beim Start HIGH = Boot-Meldungen am UART; Pin gibt kurz PWM aus.",
        16: "Bei WROVER-Modulen (PSRAM) nicht nutzbar.",
        17: "Bei WROVER-Modulen (PSRAM) nicht nutzbar.",
        21: "Standard-I²C SDA", 22: "Standard-I²C SCL", 25: "DAC 1", 26: "DAC 2",
    },
    "ESP32C3": {
        2: "Muss beim Start HIGH oder offen sein.",
        8: "Muss beim Start HIGH sein. Onboard-LED auf vielen Boards.",
        9: "Boot-Taster. LOW beim Start = Flash-Modus.",
    },
    "ESP32S3": {
        0: "Boot-Taster. LOW beim Start = Flash-Modus.",
        3: "Legt die JTAG-Quelle fest; beim Start offen lassen.",
        45: "Legt die VDD_SPI-Spannung fest; beim Start LOW lassen.",
        46: "Beim Start LOW lassen (ROM-Log).",
        48: "RGB-LED auf DevKitC-1 v1.0 (v1.1: GPIO38).",
    },
}
# Standard-UART0-Pins (TX, RX) des Loggers je Variante
UART0 = {"ESP32": (1, 3), "ESP32S2": (43, 44), "ESP32S3": (43, 44), "ESP32C3": (21, 20), "ESP32C6": (16, 17),
         "ESP32H2": (24, 23)}
I2C_DEFAULT = {"ESP32": (21, 22), "ESP32S2": (8, 9), "ESP32S3": (8, 9), "ESP32C3": (4, 5)}
ESP32_LABEL = {"ESP32": "ESP32", "ESP32S2": "ESP32-S2", "ESP32S3": "ESP32-S3", "ESP32C2": "ESP32-C2",
               "ESP32C3": "ESP32-C3", "ESP32C5": "ESP32-C5", "ESP32C6": "ESP32-C6", "ESP32C61": "ESP32-C61",
               "ESP32H2": "ESP32-H2", "ESP32H21": "ESP32-H21", "ESP32H4": "ESP32-H4", "ESP32P4": "ESP32-P4",
               "ESP32S31": "ESP32-S31"}


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


def build_esp32_chip(variant: str):
    from esphome.components import adc as adc_mod
    from esphome.const import (CONF_IGNORE_STRAPPING_WARNING, CONF_INPUT, CONF_MODE, CONF_NUMBER, CONF_OUTPUT,
                               CONF_PULLDOWN, CONF_PULLUP)
    modname = "gpio_esp32" if variant == "ESP32" else "gpio_esp32_" + variant[5:].lower()
    mod = importlib.import_module(f"esphome.components.esp32.{modname}")
    validate_pin = next(getattr(mod, n) for n in dir(mod) if n.endswith("_validate_gpio_pin"))
    validate_sup = next(getattr(mod, n) for n in dir(mod) if n.endswith("_validate_supports"))
    strapping = next((getattr(mod, n) for n in dir(mod) if n.endswith("STRAPPING_PINS")), set())
    psram_octal = next((getattr(mod, n) for n in dir(mod) if "R8_PSRAM" in n), {})
    adc1 = getattr(adc_mod, "ESP32_VARIANT_ADC1_PIN_TO_CHANNEL", {}).get(variant, {})
    adc2 = getattr(adc_mod, "ESP32_VARIANT_ADC2_PIN_TO_CHANNEL", {}).get(variant, {})
    cap = _Capture()
    logging.getLogger().addHandler(cap)
    notes = NOTES.get(variant, {})
    pins = []
    try:
        for n in range(0, 64):
            cap.msgs.clear()
            try:
                validate_pin(n)
            except Exception as exc:  # noqa: BLE001
                if "Invalid pin number" in str(exc):
                    continue
                pins.append(pin(n, flash=True, note="Hängt am Flash-/PSRAM-Speicher und ist nicht nutzbar."))
                continue
            usb = any("USB" in m for m in cap.msgs)
            flags = {}
            if variant == "ESP32" and n in (9, 10):
                pins.append(pin(n, flash=True, note="Hängt bei den meisten Modulen am Flash-Speicher."))
                continue

            def sup(out=False, pull=False):
                mode = {CONF_INPUT: not out, CONF_OUTPUT: out, CONF_PULLUP: pull, CONF_PULLDOWN: False,
                        "open_drain": False, "analog": False}
                try:
                    validate_sup({CONF_NUMBER: n, CONF_MODE: mode, CONF_IGNORE_STRAPPING_WARNING: n in strapping})
                    return True
                except Exception:  # noqa: BLE001
                    return False

            if not sup(out=True):
                flags["input_only"] = True
            if not sup(pull=True):
                flags["no_pullup"] = True
            if n in strapping:
                flags["strapping"] = notes.get(n, GENERIC_STRAP)
            if usb:
                flags["usb"] = True
                flags["note"] = "USB (Serial/JTAG). Frei nutzbar, wenn nicht über USB geflasht oder geloggt wird."
            if n in psram_octal:
                flags["psram"] = True
                flags["note"] = "Bei Modulen mit Octal-PSRAM (N8R8, N16R8) belegt."
            if variant == "ESP32" and n in (16, 17):
                flags["psram"] = True
            if n in adc1:
                flags["adc"] = "adc1"
            elif n in adc2:
                flags["adc"] = "adc2"
            uart = UART0.get(variant)
            if uart and n in uart:
                flags["uart"] = True
                flags["note"] = f"UART0 {'TX' if n == uart[0] else 'RX'} (Logger)"
            if n in notes and "strapping" not in flags and "note" not in flags:
                flags["note"] = notes[n]
            elif n in notes and "note" not in flags:
                pass
            if variant == "ESP32" and n in (34, 35, 36, 39):
                flags["note"] = flags.get("note") or "Nur Eingang, keine Pull-ups."
            pins.append(pin(n, **flags))
    finally:
        logging.getLogger().removeHandler(cap)
    return {"label": ESP32_LABEL.get(variant, variant), "platform": "esp32", "variant": variant, "pins": pins}


# ------------------------------------------------------------------- RP2 -----


def build_rp2_chip(mcu: str, max_pin: int):
    adc_pins = {26, 27, 28, 29} if max_pin < 40 else {40, 41, 42, 43, 44, 45, 46, 47}
    pins = []
    for n in range(0, max_pin + 1):
        flags = {}
        if n in adc_pins:
            flags["adc"] = "adc"
        if n in (0, 1):
            flags["uart"] = True
            flags["note"] = f"UART0 {'TX' if n == 0 else 'RX'} (Logger)"
        pins.append(pin(n, **flags))
    label = {"rp2040": "RP2040", "rp2350": "RP2350"}[mcu] + (" (RP2350B)" if max_pin >= 40 else "")
    return {"label": label, "platform": "rp2", "pins": pins, "i2c": ["GPIO4", "GPIO5"]}


# ------------------------------------------------------------- LibreTiny -----

LT_LABEL = {"BK7231N": "Beken BK7231N", "BK7231T": "Beken BK7231T", "BK7231Q": "Beken BK7231Q",
            "BK7238": "Beken BK7238", "BK7251": "Beken BK7251", "RTL8710B": "Realtek RTL8710B",
            "RTL8720C": "Realtek RTL8720C", "LN882H": "Lightning LN882H"}
LT_LOG_SERIAL = {"bk72xx": 2, "rtl87xx": 2, "ln882x": 0}
PIN_NAME = re.compile(r"^P[A-Z]?\d+$")


def lt_pins(platform: str, names: dict):
    has_pwm = any(re.fullmatch(r"PWM\d+", n) for n in names)  # LN882x: Tabelle kennt keine PWM-Pins
    by_num = {}
    for name, num in names.items():
        by_num.setdefault(num, []).append(name)
    pins = []
    for num in sorted(by_num):
        ns = by_num[num]
        ids = sorted((n for n in ns if PIN_NAME.match(n)), key=lambda x: (len(x), x))
        if not ids:
            continue
        pid = ids[0]
        funcs = []
        flags = {}
        for n in sorted(ns):
            if re.fullmatch(r"PWM\d+", n):
                funcs.append(n)
                flags["pwm_ok"] = True
            elif re.fullmatch(r"ADC\d+", n):
                funcs.append(n)
                flags["adc"] = "adc"
            m = re.fullmatch(r"SERIAL(\d+)_(RX|TX)", n)
            if m:
                funcs.append(f"{m.group(2)}{m.group(1)}")
                if int(m.group(1)) == LT_LOG_SERIAL[platform]:
                    flags["uart"] = True
                    flags["note"] = f"UART{m.group(1)} {m.group(2)} (Logger)"
                elif int(m.group(1)) == 1 and platform == "bk72xx":
                    flags["note"] = "UART1: wird zum Flashen per Kabel gebraucht (Flash-Adapter)."
        funcs = list(dict.fromkeys(funcs))
        p = {"id": pid, "gpio": num}
        if funcs:
            p["short"] = "/".join(funcs[:2])
        if has_pwm and not flags.get("pwm_ok"):
            p["no_pwm"] = True
        flags.pop("pwm_ok", None)
        p.update(flags)
        pins.append(p)
    return pins


# --------------------------------------------------------------- Aliase ------


def short_name(names: list[str], exclude: str) -> str | None:
    names = [n for n in names if n != exclude and not re.fullmatch(r"GPIO\d+", n)]
    for rx in (r"D\d+", r"A\d+", r"GP\d+"):
        for n in names:
            if re.fullmatch(rx, n):
                return n
    return names[0] if names else None


def alias_map(table: dict, base: dict) -> dict[int, list[str]]:
    by_num: dict[int, list[str]] = {}
    for name, num in {**base, **table}.items():
        by_num.setdefault(num, []).append(name)
    return by_num


# ------------------------------------------------------------------ Main -----


def main() -> None:
    chips: dict[str, dict] = {"esp8266": ESP8266_CHIP}
    boards: list[dict] = []
    seen_keys: set[str] = set()

    def add_board(key, platform, chip, label, board_id, aliases=None, **extra):
        k = key
        if k in seen_keys:
            k = f"{platform}/{key}"
        seen_keys.add(k)
        b = {"key": k, "label": label, "platform": platform, "chip": chip, "board": board_id}
        if aliases:
            b["aliases"] = aliases
        b.update(extra)
        boards.append(b)

    # ESP8266
    from esphome.components.esp8266.boards import BOARDS as B8, ESP8266_BASE_PINS, ESP8266_BOARD_PINS
    for key, info in sorted(B8.items(), key=lambda kv: kv[1]["name"].lower()):
        table = resolve(ESP8266_BOARD_PINS, key)
        by_num = alias_map(table, ESP8266_BASE_PINS)
        al = {}
        for num, names in by_num.items():
            pid = "A0" if num == 17 else f"GPIO{num}"
            al[pid] = sorted(names)
        extra = {"only": sorted(ESP01_ONLY)} if key in ESP01_BOARDS else {}
        add_board(key, "esp8266", "esp8266", info["name"], key, al, **extra)

    # ESP32
    from esphome.components.esp32.boards import BOARDS as B32, ESP32_BASE_PINS, ESP32_BOARD_PINS
    variants = sorted({b["variant"] for b in B32.values()})
    for v in variants:
        chips[v.lower()] = build_esp32_chip(v)
    for key, info in sorted(B32.items(), key=lambda kv: kv[1]["name"].lower()):
        table = resolve(ESP32_BOARD_PINS, key)
        by_num = alias_map(table, ESP32_BASE_PINS)
        al = {f"GPIO{num}": sorted(names) for num, names in by_num.items()}
        add_board(key, "esp32", info["variant"].lower(), info["name"], key, al)

    # RP2
    from esphome.components.rp2.boards import BOARDS as BR, RP2_BASE_PINS, RP2_BOARD_PINS
    for key, info in sorted(BR.items(), key=lambda kv: kv[1]["name"].lower()):
        mcu, mp = info["mcu"], info.get("max_pin", 29)
        ck = f"{mcu}" + ("b" if mp >= 40 else "")
        if ck not in chips:
            chips[ck] = build_rp2_chip(mcu, mp)
        table = resolve(RP2_BOARD_PINS, key)
        by_num = alias_map(table, RP2_BASE_PINS)
        al = {f"GPIO{num}": sorted(names) for num, names in by_num.items() if num <= mp}
        add_board(key, "rp2", ck, info["name"], key, al, wifi=bool(info.get("wifi")))

    # LibreTiny
    for platform, modname, boards_attr, pins_attr in (
            ("bk72xx", "bk72xx", "BK72XX_BOARDS", "BK72XX_BOARD_PINS"),
            ("rtl87xx", "rtl87xx", "RTL87XX_BOARDS", "RTL87XX_BOARD_PINS"),
            ("ln882x", "ln882x", "LN882X_BOARDS", "LN882X_BOARD_PINS")):
        m = importlib.import_module(f"esphome.components.{modname}.boards")
        BL, PL = getattr(m, boards_attr), getattr(m, pins_attr)
        for key, info in sorted(BL.items(), key=lambda kv: (kv[1]["family"], kv[1]["name"].lower())):
            names = resolve(PL, key)
            fam = info["family"]
            ck = fam.lower()
            if ck not in chips:
                chips[ck] = {"label": LT_LABEL.get(fam, fam), "platform": platform, "pins": []}
            pins = lt_pins(platform, names)
            i2c = None
            for sda, scl in (("WIRE1_SDA", "WIRE1_SCL"), ("WIRE0_SDA_0", "WIRE0_SCL_0"), ("WIRE2_SDA", "WIRE2_SCL")):
                if sda in names and scl in names:
                    ids = {p["gpio"]: p["id"] for p in pins}
                    if names[sda] in ids and names[scl] in ids:
                        i2c = [ids[names[sda]], ids[names[scl]]]
                        break
            by_num = {}
            for n_, num_ in names.items():
                by_num.setdefault(num_, []).append(n_)
            ids_ = {p_["gpio"]: p_["id"] for p_ in pins}
            al = {ids_[num_]: sorted(ns_) for num_, ns_ in by_num.items() if num_ in ids_}
            add_board(key, platform, ck, f"{info['name']} ({fam})", key, al, pins=pins, **({"i2c": i2c} if i2c else {}))

    data = {"esphome": ESPHOME_VERSION, "chips": chips, "boards": boards}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print("ESPHome", ESPHOME_VERSION, "->", OUT, f"({OUT.stat().st_size // 1024} KB)")
    print(Counter(b["platform"] for b in boards), "Chips:", len(chips))


if __name__ == "__main__":
    sys.exit(main())
