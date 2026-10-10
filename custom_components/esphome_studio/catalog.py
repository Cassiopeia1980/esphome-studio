"""Katalog aller ESPHome-Bausteine (Sensoren, Schalter, Lichter …).

``catalog.json`` wird mit ``tools/gen_catalog.py`` aus dem ESPHome-Schema erzeugt und mit
``tools/verify_catalog.py`` gegen ``esphome config`` geprüft (Feld ``verified``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .components import ALL

_FILE = Path(__file__).parent / "catalog.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"domains": {}, "entries": []}


def catalog() -> dict[str, Any]:
    return _load()


@lru_cache(maxsize=1)
def by_id() -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in _load()["entries"]}


def entry(cat_id: str) -> dict[str, Any] | None:
    return by_id().get(cat_id)


UART_PINS = [
    {"key": "_rx", "label": "RX (Daten vom Sensor)", "kind": "in", "required": True},
    {"key": "_tx", "label": "TX (zum Sensor, optional)", "kind": "out", "required": False},
]


def spec_for_entry(e: dict[str, Any], name: str = "") -> dict[str, Any]:
    pins = [{"key": p["key"], "label": p["label"], "kind": p["kind"], "required": p["required"]} for p in e["pins"]]
    if e.get("bus") == "uart":
        pins = UART_PINS + pins
    return {
        "label": e["label"], "platforms": e.get("platforms") or ALL, "pins": pins,
        "needs_i2c": e.get("bus") == "i2c", "needs_spi": e.get("bus") == "spi", "options": [], "generic": True,
    }
