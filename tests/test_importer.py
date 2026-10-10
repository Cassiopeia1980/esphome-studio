"""Tests für den YAML-Import."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from helpers import load_core  # noqa: E402

boards, components, gen = load_core()
import importlib  # noqa: E402

imp = importlib.import_module("esphome_studio.importer")
STORED = {"wifi_ssid": "Mein WLAN", "wifi_password": "supergeheim"}


def roundtrip(project):
    r = gen.generate(project, STORED)
    assert r["ok"], r["errors"]
    res = imp.import_yaml(r["yaml"], r["secrets"])
    assert res["ok"], res["errors"]
    return r, res


def test_roundtrip_simple():
    p = gen.default_project("d1_mini")
    p["name"] = "kueche"
    p["friendly_name"] = "Küche"
    p["components"] = [gen.new_component("switch", "Relais", {"pin": "GPIO5"}),
                       gen.new_component("dht", "Klima", {"pin": "GPIO4"})]
    r, res = roundtrip(p)
    q = res["project"]
    assert q["name"] == "kueche" and q["friendly_name"] == "Küche" and q["board"] == "d1_mini"
    assert [c["type"] for c in q["components"]] == ["switch", "dht"]
    assert res["unmapped"] == [], res["unmapped"]
    r2 = gen.generate(q, STORED)
    assert r2["errors"] == [], r2["errors"]
    assert r2["yaml"] == r["yaml"]
    assert r2["secrets"] == r["secrets"]


def test_roundtrip_all_samples():
    import validate_with_esphome as v  # noqa: PLC0415

    bad = []
    for key, proj in v.SAMPLES.items():
        if key == "web-v3-auth" or key.startswith(("katalog", "profi")):  # werden bewusst als Zusatz-YAML übernommen; Katalog-Bausteine werden nicht zurückgelesen
            continue
        r = gen.generate(proj, STORED)
        assert r["ok"], (key, r["errors"])
        res = imp.import_yaml(r["yaml"], r["secrets"])
        assert res["ok"], (key, res["errors"])
        r2 = gen.generate(res["project"], STORED)
        if r2["yaml"] != r["yaml"] or res["unmapped"]:
            bad.append((key, res["unmapped"], r2["errors"]))
    assert not bad, bad


SAMPLES = Path(__file__).parent / "samples"


def _messy():
    return imp.import_yaml((SAMPLES / "messy.yaml").read_text(), (SAMPLES / "messy_secrets.yaml").read_text())


def test_messy_yaml_keeps_everything():
    res = _messy()
    assert res["ok"], res["errors"]
    q = res["project"]
    assert q["name"] == "terrasse" and q["friendly_name"] == "Terrasse" and q["board"] == "d1_mini"
    assert q["log_level"] == "DEBUG"
    assert {c["name"] for c in q["components"]} == {"Licht Relais", "Taster"}
    taster = next(c for c in q["components"] if c["name"] == "Taster")
    assert taster["pins"] == {"pin": "GPIO14"} and taster["options"]["debounce_ms"] == 50
    assert taster["options"]["toggle_target"] == next(c["uid"] for c in q["components"] if c["name"] == "Licht Relais")
    assert res["secrets"] == {"wifi_ssid": "Heimnetz", "wifi_password": "geheim1234"}
    assert q["ota"]["mode"] == "password" and q["ota"]["password"] == "otapass"
    assert q["wifi"]["ap_password"] == "appass1234"
    extra = q["extra_yaml"]
    for must in ("on_boot:", "globals:", "script:", "interval:", "gamma_correct", "template", "Pumpe", "esp8266_pwm"):
        assert must in extra or must in gen.generate(q, res["secrets"])["yaml"], must
    r = gen.generate(q, res["secrets"])
    assert r["ok"], r["errors"]
    y = r["yaml"]
    assert y.index("substitutions:") < y.index("esphome:")
    assert "restore_from_flash: true" in y and "fast_connect: true" in y and "reboot_timeout: 30min" in y
    assert 'ESP_LOGI(\\"boot\\", \\"bereit\\");' in y or 'ESP_LOGI("boot", "bereit");' in y
    assert y.count("platform: gpio") >= 4


def test_import_is_stable_when_imported_twice():
    res = _messy()
    r1 = gen.generate(res["project"], res["secrets"])
    res2 = imp.import_yaml(r1["yaml"], r1["secrets"])
    assert res2["ok"], res2["errors"]
    r2 = gen.generate(res2["project"], res["secrets"])
    assert r2["yaml"] == r1["yaml"]
    assert r2["secrets"] == r1["secrets"]


def test_import_without_secrets_file_reports_gaps():
    res = imp.import_yaml((SAMPLES / "messy.yaml").read_text())
    assert res["ok"]
    assert res["project"]["api"]["key"] == ""
    assert any("API-Schlüssel" in n for n in res["notes"])
    assert any("Secrets" in n for n in res["notes"])
    assert any("API-Schlüssel" in e for e in gen.generate(res["project"], {})["errors"])


def test_import_errors_are_readable():
    assert not imp.import_yaml("")["ok"]
    assert "lesen" in imp.import_yaml("a: [1, 2")["errors"][0]
    assert not imp.import_yaml("foo: bar")["ok"]
    assert "esphome" in imp.import_yaml("wifi:\n  ssid: x")["errors"][0]
    assert "Plattform" in imp.import_yaml("esphome:\n  name: x")["errors"][0]
    r = imp.import_yaml("esphome:\n  name: x\nesp32:\n  board: gibts-nicht-xyz\n")
    assert r["ok"] and r["project"]["board"] == "esp32dev" and any("kennt das Studio nicht" in n for n in r["notes"])
    for junk in ("- a\n- b", "esphome: 5", "esphome:\n  name: [1]\nesp8266: {}\n", "!!python/object:os.system x"):
        assert "ok" in imp.import_yaml(junk)


def test_import_beken_cb2s_and_rp2():
    y = ("esphome:\n  name: bk-licht\nbk72xx:\n  board: cb2s\nlogger:\nwifi:\n  ssid: a\n  password: b\n"
         "output:\n  - platform: libretiny_pwm\n    id: o\n    pin: P6\nlight:\n  - platform: monochromatic\n"
         "    name: Lampe\n    output: o\nswitch:\n  - platform: gpio\n    name: Relais\n    pin: P24\n")
    res = imp.import_yaml(y)
    assert res["ok"] and res["project"]["board"] == "cb2s", res
    assert [c["type"] for c in res["project"]["components"]] == ["light_pwm", "switch"]
    assert res["project"]["components"][0]["pins"] == {"pin": "P6"}
    assert gen.generate(res["project"], STORED)["ok"]
    y2 = "esphome:\n  name: pico\nrp2:\n  board: rpipicow\nswitch:\n  - platform: gpio\n    name: R\n    pin: GPIO15\n"
    r2 = imp.import_yaml(y2)
    assert r2["ok"] and r2["project"]["board"] == "rpipicow" and r2["project"]["components"][0]["pins"] == {"pin": "GPIO15"}


def test_extra_yaml_in_generator():
    p = gen.default_project("d1_mini")
    p["name"] = "x"
    p["extra_yaml"] = "script:\n  - id: s\n    then:\n      - lambda: |-\n          int a = 1;\n          a++;\nlogger:\n  level: WARN\n"
    r = gen.generate(p, STORED)
    assert r["ok"], r["errors"]
    assert "script:" in r["yaml"] and "- lambda: |-" in r["yaml"] and "          int a = 1;" in r["yaml"].replace("  int", "          int", 1) or "int a = 1;" in r["yaml"]
    assert any("logger.level" in w for w in r["warnings"])  # Studio setzt die Log-Stufe selbst
    p["extra_yaml"] = "a: [1, 2"
    assert any("Zusatz-YAML" in e for e in gen.generate(p, STORED)["errors"])
    p["extra_yaml"] = "- nur eine liste"
    assert any("Zusatz-YAML" in e for e in gen.generate(p, STORED)["errors"])
