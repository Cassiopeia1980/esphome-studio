"""Macht dem Home-Assistant-Testpaket den Ordner custom_components dieses Projekts bekannt."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import custom_components  # vom Testpaket mit eigenem Pfad vorbelegt
except ImportError:  # reine Generator-Tests ohne HA
    custom_components = None

if custom_components is not None:
    mine = str(ROOT / "custom_components")
    if mine not in list(custom_components.__path__):
        custom_components.__path__.append(mine)
