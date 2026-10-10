"""Board-Definitionen für ESPHome Studio.

Die Daten stammen aus ``boards_data.json``. Die Datei wird mit ``tools/gen_boards.py``
direkt aus der installierten ESPHome-Version erzeugt (alle Boards von ESP8266, ESP32,
RP2040/RP2350 und LibreTiny: Beken BK72xx, Realtek RTL87xx, Lightning LN882x).

Jedes Board hat eine Pin-Liste mit Eigenschaften (Flags), die der Generator zur
Prüfung und das Panel zur Anzeige benutzt:

* input_only  – Pin kann nur lesen (kein Ausgang)
* no_pullup   – keine internen Pull-ups
* no_pwm      – kein PWM möglich
* flash       – hängt am Flash-Speicher, darf nicht benutzt werden
* strapping   – Boot-Pin; Text sagt, was beim Start beachtet werden muss
* uart        – Pin gehört zur Standard-UART (Logger)
* usb         – Pin gehört zum nativen USB
* psram       – kann je nach Modul vom PSRAM belegt sein
* adc         – "adc1" / "adc2" (ESP32) oder "adc"
* adc_only    – Pin ist ausschließlich ein Analog-Eingang (ESP8266 A0)
* short       – Aufdruck auf dem Board (z. B. "D1"), erscheint als YAML-Kommentar
* note        – freier Hinweistext
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

_DATA = json.loads((Path(__file__).parent / "boards_data.json").read_text(encoding="utf-8"))
ESPHOME_DATA_VERSION: str = _DATA["esphome"]
_CHIPS: dict[str, dict[str, Any]] = _DATA["chips"]
_RAW: dict[str, dict[str, Any]] = {b["key"]: b for b in _DATA["boards"]}

# Chips ohne eigenes WLAN (ESPHome braucht dort Ethernet oder ein WLAN-Zusatzmodul)
NO_WIFI_CHIPS = {"esp32h2", "esp32p4"}

PLATFORM_LABEL = {
    "esp8266": "ESP8266", "esp32": "ESP32", "rp2": "Raspberry Pi Pico (RP2040/RP2350)",
    "bk72xx": "Beken BK72xx", "rtl87xx": "Realtek RTL87xx", "ln882x": "Lightning LN882x",
}
# Reihenfolge der Gruppen im Board-Auswahlfenster
GROUP_ORDER = ["esp8266", "esp32", "bk72xx", "rtl87xx", "ln882x", "rp2"]

# Pins, die als „frei“ gelten, wenn ein Standard-I²C gesucht wird
_BAD_FOR_I2C = ("flash", "uart", "strapping", "input_only", "adc_only", "usb", "psram", "boot_high", "no_i2c")
_I2C_DEFAULTS = {"esp32": ("GPIO21", "GPIO22"), "esp32s2": ("GPIO8", "GPIO9"), "esp32s3": ("GPIO8", "GPIO9"),
                 "esp32c3": ("GPIO4", "GPIO5"), "esp8266": ("GPIO4", "GPIO5"), "rp2040": ("GPIO4", "GPIO5"),
                 "rp2350": ("GPIO4", "GPIO5"), "rp2350b": ("GPIO4", "GPIO5")}
_SHORT_ORDER = (r"D\d+", r"A\d+", r"GP\d+", r"[A-Z]+\d*")


def _short(names: list[str], pid: str) -> str | None:
    names = [n for n in names if n != pid and not re.fullmatch(r"GPIO\d+", n) and n not in ("SDA", "SCL")]
    for rx in _SHORT_ORDER:
        for n in sorted(names):
            if re.fullmatch(rx, n):
                return n
    return None


def _build(raw: dict[str, Any]) -> dict[str, Any]:
    chip = _CHIPS[raw["chip"]]
    base = raw.get("pins") if raw.get("pins") is not None else chip["pins"]
    aliases = raw.get("aliases") or {}
    only = set(raw.get("only") or [])
    pins: list[dict[str, Any]] = []
    for src in base:
        if only and src["id"] not in only:
            continue
        pin = dict(src)
        names = aliases.get(pin["id"], [])
        short = pin.get("short") or _short(names, pin["id"])
        if short:
            pin["short"] = short
        pin["label"] = f"{short} · {pin['id']}" if short and short != pin["id"] else pin["id"]
        pins.append(pin)
    pin_map = {p["id"]: p for p in pins}
    # Alle Schreibweisen eines Pins (D1, GPIO5, P6, PWM0 …) -> Pin-Kennung, für den YAML-Import
    alias_to_id: dict[str, str] = {}
    for pid, names in aliases.items():
        if pid in pin_map:
            for n in names:
                alias_to_id.setdefault(n.upper(), pid)
    for pid in pin_map:
        alias_to_id[pid.upper()] = pid

    # Standard-I²C: Alias SDA/SCL des Boards (wenn brauchbar), sonst Chip-Standard, sonst die ersten freien Pins
    def usable(pid: str | None) -> bool:
        return bool(pid) and pid in pin_map and not any(
            pin_map[pid].get(f) for f in ("flash", "uart", "input_only", "adc_only", "usb", "psram", "no_i2c"))

    sda = scl = None
    for pid, names in aliases.items():
        if "SDA" in names and usable(pid):
            sda = sda or pid
        if "SCL" in names and usable(pid):
            scl = scl or pid
    if not (sda and scl):
        d = raw.get("i2c") or _I2C_DEFAULTS.get(raw["chip"])
        if d and usable(d[0]) and usable(d[1]):
            sda, scl = d
    if not (sda and scl):
        free = [p["id"] for p in pins if not any(p.get(f) for f in _BAD_FOR_I2C)]
        if len(free) >= 2:
            sda, scl = free[0], free[1]
        else:
            ids = [p["id"] for p in pins]
            sda, scl = (ids + ids)[:2] if len(ids) >= 2 else (ids[0], ids[0])

    spi: dict[str, str] = {}
    for pid, names in aliases.items():
        for key, alias in (("clk", "SCK"), ("mosi", "MOSI"), ("miso", "MISO")):
            if alias in names and usable(pid) and key not in spi:
                spi[key] = pid
    if len(spi) < 3:  # Chip-Standard, sonst die nächsten freien Pins
        free = [p["id"] for p in pins if p["id"] not in (sda, scl) and usable(p["id"]) and not any(p.get(f) for f in _BAD_FOR_I2C)]
        for key in ("clk", "mosi", "miso"):
            if key not in spi and free:
                spi[key] = next((f for f in free if f not in spi.values()), "")
    plat = raw["platform"]
    note = ""
    has_wifi = True
    if raw["chip"] in NO_WIFI_CHIPS:
        has_wifi = False
        note = "Dieser Chip hat kein eigenes WLAN. ESPHome braucht hier Ethernet oder ein WLAN-Zusatzmodul."
    elif plat == "rp2" and not raw.get("wifi"):
        has_wifi = False
        note = "Dieses Board hat keinen WLAN-Chip (nur Pico W / Pico 2 W und ähnliche). ESPHome lehnt wifi: hier ab."
    elif raw["key"].startswith("esp01"):
        note = "Nur 4 Pins. Für TX/RX als GPIO wird der Logger über UART abgeschaltet."
    elif plat == "bk72xx":
        note = ("Beken-Chip (LibreTiny): Das erste Flashen geht per UART1 (RX1/TX1) mit einem USB-Seriell-Adapter, "
                "danach per WLAN. Pin-Namen sind P-Nummern. Das Board muss zur Chip-Variante passen "
                f"({raw['label'].rsplit('(', 1)[-1].rstrip(')')}), sonst startet es nicht.")
    return {
        "key": raw["key"], "label": raw["label"], "platform": plat, "chip": raw["chip"],
        "group": chip["label"], "board": raw["board"], "pins": pins, "pin_map": pin_map, "alias_to_id": alias_to_id,
        "i2c_default": {"sda": sda, "scl": scl}, "spi_default": spi, "note": note, "has_wifi": has_wifi,
    }


class _Boards(Mapping):
    """Boards, erst beim ersten Zugriff aufgebaut (es sind über 500)."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def __getitem__(self, key: str) -> dict[str, Any]:
        if key not in _RAW:
            raise KeyError(key)
        if key not in self._cache:
            self._cache[key] = _build(_RAW[key])
        return self._cache[key]

    def __iter__(self) -> Iterator[str]:
        return iter(_RAW)

    def __len__(self) -> int:
        return len(_RAW)


BOARDS: Mapping[str, dict[str, Any]] = _Boards()


def board_has_wifi(board: dict[str, Any]) -> bool:
    return bool(board.get("has_wifi", True))


def boards_meta() -> list[dict[str, Any]]:
    """Schlanke Board-Liste für die Auswahl im Frontend (ohne Pins)."""
    order = {p: i for i, p in enumerate(GROUP_ORDER)}
    rows = [
        {"key": b["key"], "label": b["label"], "platform": b["platform"], "chip": b["chip"],
         "group": _CHIPS[b["chip"]]["label"], "board": b["board"]}
        for b in _RAW.values()
    ]
    rows.sort(key=lambda r: (order.get(r["platform"], 9), r["group"], r["label"].lower()))
    return rows


def board_detail(key: str) -> dict[str, Any] | None:
    """Alle Daten eines Boards inklusive Pins (ohne pin_map)."""
    if key not in BOARDS:
        return None
    return {k: v for k, v in BOARDS[key].items() if k not in ("pin_map", "alias_to_id")}


_PLATFORM_ALIAS = {"rp2040": "rp2"}


def find_board(platform: str, board_id: str, variant: str = "") -> str | None:
    """Sucht das Studio-Board zu ``board:`` aus einer ESPHome-YAML."""
    platform = _PLATFORM_ALIAS.get(platform, platform)
    for b in _RAW.values():
        if b["platform"] == platform and b["board"] == board_id:
            return b["key"]
    return None


def default_board(platform: str, variant: str = "") -> str | None:
    """Ersatz-Board, wenn die YAML ein unbekanntes Board nennt."""
    platform = _PLATFORM_ALIAS.get(platform, platform)
    preferred = {"esp8266": "d1_mini", "esp32": "esp32dev", "rp2": "rpipicow", "bk72xx": "generic-bk7231n-qfn32-tuya",
                 "rtl87xx": "generic-rtl8710bn-2mb-788k", "ln882x": "generic-ln882h"}
    if variant:
        want = variant.lower().replace("-", "")
        for b in _RAW.values():
            if b["platform"] == platform and b["chip"] == want:
                return b["key"]
    k = preferred.get(platform)
    if k in _RAW:
        return k
    return next((b["key"] for b in _RAW.values() if b["platform"] == platform), None)
