"""Startseite: Version parsen und Geräte mit HA-Daten abgleichen."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "devices_mod", Path(__file__).parent.parent / "custom_components" / "esphome_studio" / "devices.py")
dv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dv)


def test_parse_version():
    assert dv.parse_version("2026.11.0 (Nov 23 2026, 12:00:00)") == (2026, 11, 0)
    assert dv.parse_version("2026.10") == (2026, 10, 0)
    assert dv.parse_version("") is None


def test_rows():
    projects = {
        "a": {"name": "Lampe", "board": "d1_mini", "components": [1, 2], "ota": {"migrate": True},
              "wifi": {"static_ip": {"enabled": True, "ip": "192.168.3.5"}}},
        "b": {"name": "alt", "board": "esp32dev"},
        "c": {"name": "fehlt"},
    }
    projects["d"] = {"name": "acepro1", "friendly_name": "ACE Pro 1"}
    ha = {dv.norm("ACE Pro 1"): {"sw_version": "2026.11.0", "online": True}, "lampe": {"sw_version": "2026.10.2 (x)", "online": True}, "alt": {"sw_version": "2026.11.0 (y)", "online": False}}
    out = dv.device_rows(projects, ha)
    assert out["latest"] == "2026.11.0"
    rows = {r["name"]: r for r in out["devices"]}
    assert rows["Lampe"]["outdated"] and rows["Lampe"]["migrate_open"] and rows["Lampe"]["ip"] == "192.168.3.5"
    assert not rows["alt"]["outdated"] and rows["alt"]["online"] is False
    assert not rows["fehlt"]["in_ha"]
    assert rows["acepro1"]["in_ha"]
