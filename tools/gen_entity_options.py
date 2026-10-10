"""Liest die Geräteklassen aus ESPHome und schreibt entity_options.json (mit dem Python von ESPHome starten)."""
import json
from pathlib import Path

from esphome.components import binary_sensor, button, cover, number, sensor, switch, text_sensor, valve

mods = {"sensor": sensor, "binary_sensor": binary_sensor, "switch": switch, "number": number, "cover": cover,
        "button": button, "valve": valve, "text_sensor": text_sensor}
out = {"device_classes": {k: sorted(x for x in m.DEVICE_CLASSES if x) for k, m in mods.items()},
       "state_classes": [x for x in sorted(sensor.STATE_CLASSES) if x]}
dest = Path(__file__).resolve().parent.parent / "custom_components" / "esphome_studio" / "entity_options.json"
dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(dest)
