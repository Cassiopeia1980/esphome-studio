"""Katalog-Bausteine: Erzeugung, Fehlermeldungen, Busse."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate_with_esphome as v  # noqa: E402

gen = v.gen


def _gen(key, mutate=None):
    p = v.SAMPLES[key]
    p = __import__("json").loads(__import__("json").dumps(p))
    if mutate:
        mutate(p)
    return gen.generate(p, v.STORED)


def test_esp32_mix_erzeugt_yaml():
    r = _gen("katalog-esp32")
    assert r["errors"] == [], r["errors"]
    y = r["yaml"]
    assert "platform: bme680" in y and "iir_filter: 3X" in y and "update_interval: 30s" in y
    assert "uart_id: uart_feinstaub" in y and "baud_rate: 9600" in y
    assert "ads1115:\n  id: wandler\n  address: 0x49" in y
    assert "ld2410:\n  id: radar\n  uart_id: uart_radar" in y and "ld2410_id: radar" in y
    assert "device_class: door" in y
    assert y.count("i2c:") == 1


def test_standardwerte_werden_nicht_ausgegeben():
    def m(p):
        p["components"][0]["options"] = {"s_temperature": True, "f_iir_filter": "OFF", "f_address": "118", "interval": "60s"}
    y = _gen("katalog-esp32", m)["yaml"]
    assert "iir_filter" not in y and "address: 118" not in y.split("ads1115")[0]


def test_fehler_hub_fehlt_und_pflichtfeld():
    def m(p):
        for c in p["components"]:
            if c["cat"] == "ld2410.sensor":
                c["options"]["hub"] = ""
            if c["cat"] == "pmsx003.sensor":
                c["options"]["f_type"] = ""
                c["pins"] = {}
    r = _gen("katalog-esp32", m)
    assert any("zugehörigen Baustein" in e for e in r["errors"]), r["errors"]
    assert any("muss ausgefüllt" in e for e in r["errors"]), r["errors"]
    assert any("kein Pin" in e for e in r["errors"]), r["errors"]


def test_unbekannter_baustein_und_falsche_plattform():
    def m(p):
        p["components"].append({"uid": "x1", "type": "generic", "cat": "gibt-es-nicht", "name": "Quatsch", "pins": {}, "options": {}})
    assert any("nicht im Katalog" in e for e in _gen("katalog-esp32", m)["errors"])

    def m2(p):
        p["board"] = "generic-bk7231n-qfn32-tuya"
    r = _gen("katalog-esp32", m2)
    assert any("gibt es bei" in e for e in r["errors"]) or any("Pin" in e for e in r["errors"])


def test_intervall_und_extra_yaml_fehler():
    def m(p):
        p["components"][0]["options"]["interval"] = "schnell"
        p["components"][5]["options"]["extra"] = "a: [1"
    r = _gen("katalog-esp32", m)
    assert any("ungültig" in e for e in r["errors"]) and any("Zusatz-YAML" in e for e in r["errors"]), r["errors"]


def test_doppelter_hub():
    def m(p):
        p["components"].append(dict(p["components"][3], uid="zweiter", name="Radar 2"))
    r = _gen("katalog-esp32", m)
    assert any("nur einmal" in e for e in r["errors"]), r["errors"]


def test_katalog_ist_konsistent():
    from esphome_studio import catalog  # noqa: PLC0415

    cat = catalog.catalog()
    ids = {e["id"] for e in cat["entries"]}
    assert len(ids) == len(cat["entries"]) > 400
    for e in cat["entries"]:
        assert e["domain"] in cat["domains"], e["id"]
        if e["hub"]:
            assert e["hub"] in ids or e["unsupported"], e["id"]
