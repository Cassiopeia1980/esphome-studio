"""Hilfen für Tests: lädt den Generator ohne Home Assistant."""

from __future__ import annotations

import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "esphome_studio"


def load_core():
    """Importiert boards/components/generator als Paket „esphome_studio“,
    ohne die __init__.py (die Home Assistant braucht) auszuführen."""
    if "esphome_studio" not in sys.modules:
        pkg = types.ModuleType("esphome_studio")
        pkg.__path__ = [str(PKG_DIR)]
        sys.modules["esphome_studio"] = pkg
    from esphome_studio import boards, components, generator  # noqa: PLC0415

    return boards, components, generator
