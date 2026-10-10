"""Profi-Einstellungen: Entitäts-Eigenschaften und Filter."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate_with_esphome as v  # noqa: E402

gen = v.gen


def _gen(key, mutate=None):
    p = json.loads(json.dumps(v.SAMPLES[key]))
    if mutate:
        mutate(p)
    return gen.generate(p, v.STORED)


def test_eigenschaften_und_filter():
    r = _gen("profi-d1")
    assert r["errors"] == [], r["errors"]
    y = r["yaml"]
    assert "name: Raumtemperatur" in y and "device_class: temperature" in y and "accuracy_decimals: 1" in y
    assert "- sliding_window_moving_average:" in y and "- lambda: !lambda" in y and "- invert" in y
    assert "internal: true" in y and "disabled_by_default: true" in y


def test_katalog_filter_text_roh():
    y = _gen("profi-katalog")["yaml"]
    assert '- append: " x"' in y and '- prepend: "v "' in y


def test_fehler_werden_gemeldet():
    def m(p):
        t = p["components"][0]["options"]["ent"]["temperature"]
        t["icon"] = "thermometer"
        t["device_class"] = "quatsch"
        t["accuracy_decimals"] = "x"
        t["filters"] = [{"t": "offset", "v": {"value": "abc"}}, {"t": "throttle", "v": {"value": "schnell"}},
                        {"t": "calibrate_linear", "v": {"datapoints": "0 -> 0"}}, {"t": "clamp", "v": {}}]
    errs = _gen("profi-d1", m)["errors"]
    joined = " | ".join(errs)
    for part in ("Icon", "Geräteklasse", "Nachkommastellen", "Zahl", "Zeit", "Wertepaare", "Begrenzen"):
        assert part in joined, (part, errs)


def test_ohne_einstellungen_keine_aenderung():
    def m(p):
        for c in p["components"]:
            c["options"].pop("ent", None)
    plain = _gen("profi-d1", m)["yaml"]
    assert "sliding_window" not in plain and "Raumtemperatur" not in plain


def test_unbekanntes_ziel_wird_ignoriert():
    def m(p):
        p["components"][0]["options"]["ent"]["gibts_nicht"] = {"icon": "mdi:x"}
    assert _gen("profi-d1", m)["errors"] == []
