"""Tests für den Generator (ohne Home Assistant, ohne ESPHome)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from helpers import load_core  # noqa: E402

boards, components, gen = load_core()
STORED = {"wifi_ssid": "Mein WLAN", "wifi_password": "pw", "ap_password": "hotspot-pw-123"}


def proj(board="d1_mini", comps=None, **kw):
    p = gen.default_project(board)
    p["name"] = "test-geraet"
    p["components"] = comps or []
    p.update(kw)
    return p


def comp(t, name, pins=None, **opts):
    c = gen.new_component(t, name, pins)
    c["options"].update(opts)
    return c


def errors(p):
    return gen.generate(p, STORED)["errors"]


def test_minimal_ok():
    r = gen.generate(proj(), STORED)
    assert r["ok"], r["errors"]
    assert "!secret wifi_ssid" in r["yaml"]
    assert 'wifi_ssid: "Mein WLAN"' in r["secrets"]
    assert "test_geraet_api_key" in r["secrets"]
    assert "encryption: {}" in r["yaml"]  # OTA übernimmt den API-Schlüssel


def test_invalid_device_name():
    for bad in ["Test", "test_geraet", "-x", "x-", "a" * 32, ""]:
        p = proj()
        p["name"] = bad
        assert any("Gerätename" in e for e in errors(p)), bad


def test_pin_conflict_and_duplicate_name():
    p = proj(comps=[comp("switch", "A", {"pin": "GPIO5"}), comp("switch", "a", {"pin": "GPIO5"})])
    e = errors(p)
    assert any("doppelt belegt" in x for x in e)
    assert any("doppelt" in x and "Name" in x for x in e)


def test_flash_and_input_only_pins():
    p = proj("esp32dev", [comp("switch", "S", {"pin": "GPIO6"}), comp("switch", "T", {"pin": "GPIO34"})])
    e = errors(p)
    assert any("Flash" in x for x in e)
    assert any("kann nur lesen" in x for x in e)


def test_input_only_pin_without_pullup():
    p = proj("esp32dev", [comp("binary_sensor", "B", {"pin": "GPIO34"})])  # Standard: INPUT_PULLUP
    assert any("Pull-up" in x for x in errors(p))
    p = proj("esp32dev", [comp("binary_sensor", "B", {"pin": "GPIO34"}, mode="INPUT")])
    assert errors(p) == []


def test_adc_rules():
    assert any("kein Analog-Pin" in x for x in errors(proj(comps=[comp("adc", "A", {"pin": "GPIO5"})])))
    assert errors(proj(comps=[comp("adc", "A", {"pin": "A0"})])) == []
    assert any("nur ein Analog-Eingang" in x for x in errors(proj(comps=[comp("switch", "S", {"pin": "A0"})])))


def test_esp8266_gpio16_pwm_and_pullup():
    assert any("PWM" in x for x in errors(proj(comps=[comp("light_pwm", "L", {"pin": "GPIO16"})])))
    assert any("Pull-up" in x for x in errors(proj(comps=[comp("binary_sensor", "B", {"pin": "GPIO16"})])))


def test_platform_only_esp32():
    e = errors(proj("d1_mini", [comp("light_strip", "S", {"pin": "GPIO5"})]))
    assert any("bei ESP8266 nicht" in x for x in e)


def test_uart_pin_turns_logger_off():
    r = gen.generate(proj("esp01_1m", [comp("switch", "S", {"pin": "GPIO3"})]), STORED)
    assert r["ok"]
    assert "baud_rate: 0" in r["yaml"]
    assert any("UART" in w for w in r["warnings"])


def test_i2c_pins_checked_against_components():
    p = proj(comps=[comp("bme280", "B"), comp("switch", "S", {"pin": "GPIO4"})])
    assert any("doppelt belegt" in x for x in errors(p))


def test_singletons():
    p = proj("esp32dev", [comp("ir_receiver", "A", {"pin": "GPIO4"}), comp("ir_receiver", "B", {"pin": "GPIO5"})])
    assert any("nur einmal" in x for x in errors(p))


def test_toggle_target_and_pulse():
    sw = comp("switch", "Relais", {"pin": "GPIO5"}, pulse_ms=300)
    b = comp("binary_sensor", "Taster", {"pin": "GPIO14"}, toggle_target=sw["uid"])
    y = gen.generate(proj(comps=[sw, b]), STORED)["yaml"]
    assert "switch.toggle: relais" in y
    assert "delay: 300ms" in y
    assert "switch.turn_off: relais" in y


def test_ota_modes():
    p = proj()
    p["api"]["encryption"] = False
    assert any("OTA-Verschlüsselung" in x for x in errors(p))
    p["ota"]["mode"] = "password"
    r = gen.generate(p, STORED)
    assert r["ok"] and "test_geraet_ota_password" in r["secrets"]


def test_inline_secrets_mode():
    p = proj(use_secrets=False)
    r = gen.generate(p, STORED)
    assert "!secret" not in r["yaml"]
    assert "Mein WLAN" in r["yaml"]
    assert r["secrets"] == ""


def test_missing_wifi_is_warning_with_secrets_and_error_without():
    r = gen.generate(proj(), {})
    assert r["ok"] and r["warnings"]
    assert not gen.generate(proj(use_secrets=False), {})["ok"]


def test_quoting_of_special_names():
    c = comp("switch", "Küche: Licht #1", {"pin": "GPIO5"})
    y = gen.generate(proj(comps=[c]), STORED)["yaml"]
    assert 'name: "Küche: Licht #1"' in y
    c = comp("switch", "123", {"pin": "GPIO5"})
    assert 'name: "123"' in gen.generate(proj(comps=[c]), STORED)["yaml"]
    c = comp("switch", "Ja", {"pin": "GPIO5"})
    assert "name: Ja" in gen.generate(proj(comps=[c]), STORED)["yaml"]  # "ja" ist kein YAML-1.1-Bool


def test_garbage_input_does_not_crash():
    for bad in [{}, {"board": "gibts-nicht"}, {"board": "d1_mini", "components": [None, 5, {"type": "x"}]},
                {"board": "d1_mini", "wifi": None, "api": None, "ota": None, "components": [
                    {"type": "switch", "name": None, "pins": None, "options": None}]}]:
        r = gen.generate(bad, STORED)
        assert "ok" in r and "errors" in r


def test_every_board_pin_list_is_consistent():
    for b in boards.BOARDS.values():
        ids = [p["id"] for p in b["pins"]]
        assert len(ids) == len(set(ids)), b["key"]
        for k in ("sda", "scl"):
            assert b["i2c_default"][k] in ids, (b["key"], k)


def test_gateway_must_be_in_same_network():
    p = proj()
    p["wifi"]["static_ip"].update(enabled=True, ip="192.168.3.71", gateway="192.168.1.1", subnet="255.255.255.0")
    assert any("nicht im selben Netz" in x for x in errors(p))
    p["wifi"]["static_ip"]["subnet"] = "255.255.252.0"  # /22: 192.168.0.0 - 192.168.3.255
    assert errors(p) == []
    p["wifi"]["static_ip"]["subnet"] = "255.0.255.0"
    assert any("Netzmaske" in x for x in errors(p))
    p["wifi"]["static_ip"].update(subnet="255.255.255.0", gateway="192.168.3.71")
    assert any("gleich" in x for x in errors(p))


def test_gpio16_warns_boot_high():
    r = gen.generate(proj(comps=[comp("switch", "R", {"pin": "GPIO16"})]), STORED)
    assert r["ok"] and any("kurz auf HIGH" in w for w in r["warnings"])


def test_substitutions_and_comment():
    p = proj(substitutions=True, comment="Aquarium im Wohnzimmer")
    y = gen.generate(p, STORED)["yaml"]
    assert y.index("substitutions:") < y.index("esphome:")
    assert "devicename: test-geraet" in y and "name: $devicename" in y
    assert "comment: ${device_description}" in y
    y2 = gen.generate(proj(comment="Nur Text"), STORED)["yaml"]
    assert "substitutions" not in y2 and "comment: Nur Text" in y2


def test_esp8266_and_wifi_options():
    p = proj(flash_mode="dout", early_pin_init="false")
    p["wifi"]["min_auth_mode"] = "WPA2"
    y = gen.generate(p, STORED)["yaml"]
    assert "board_flash_mode: dout" in y and "early_pin_init: false" in y and "min_auth_mode: WPA2" in y
    y = gen.generate(proj("esp32dev", flash_mode="dout"), STORED)["yaml"]
    assert "board_flash_mode" not in y  # nur ESP8266


def test_light_effects_and_name_none():
    c = comp("light_rgb", "Licht", {"red": "GPIO5", "green": "GPIO4", "blue": "GPIO14"},
             name_none=True, fx_pulse=True, fx_strobe=True)
    r = gen.generate(proj(comps=[c], friendly_name="Aquarium"), STORED)
    assert r["ok"], r["errors"]
    assert "name: None" in r["yaml"] and "Schnelles Pulsieren" in r["yaml"] and "Blitzen" in r["yaml"]
    assert any("Anzeigenamen" in e for e in errors(proj(comps=[c], friendly_name="")))
    c2 = comp("light_pwm", "Zwei", {"pin": "GPIO12"}, name_none=True)
    assert any("nur bei einer Entität" in e for e in errors(proj(comps=[c, c2], friendly_name="X")))


def test_dallas_filters_and_resolution():
    c = comp("dallas", "T", {"pin": "GPIO4"}, throttle="30s", delta="0,2", resolution=10)
    y = gen.generate(proj(comps=[c]), STORED)["yaml"]
    assert "resolution: 10" in y and "- or:" in y and "throttle: 30s" in y and "delta: 0.2" in y
    assert any("Zahl" in e for e in errors(proj(comps=[comp("dallas", "T", {"pin": "GPIO4"}, delta="viel")])))
    assert any("Mindestpause" in e for e in errors(proj(comps=[comp("dallas", "T", {"pin": "GPIO4"}, throttle="bald")])))
    y = gen.generate(proj(comps=[comp("dallas", "T", {"pin": "GPIO4"}, delta="0.5")]), STORED)["yaml"]
    assert "resolution" not in y and "- or:" not in y and "delta: 0.5" in y


def test_diagnostics_merged_and_debug():
    p = proj()
    p["diag"] = {"ip": True, "ssid": True, "bssid": True, "mac": True, "status": True, "uptime_text": True,
                 "debug_heap": True, "debug_reset": True}
    r = gen.generate(p, STORED)
    y = r["yaml"]
    assert y.count("platform: wifi_info") == 1
    assert all(k in y for k in ("ip_address:", "ssid:", "bssid:", "mac_address:", "platform: status", "format:",
                                "free:", "block:", "reset_reason:"))
    assert y.index("\ndebug:") < y.index("\nwifi:")
    assert any("Debug" in w for w in r["warnings"])
    p["debug_interval"] = "oft"
    assert any("Debug-Intervall" in e for e in errors(p))


def test_gpio16_i2c_warning():
    p = proj(comps=[comp("bme280", "B")])
    p["i2c"] = {"sda": "GPIO4", "scl": "GPIO16"}
    assert any("kein I²C" in w for w in gen.generate(p, STORED)["warnings"])


# ------------------------------------------------------------ Alle Boards ---


def test_all_boards_load_and_are_consistent():
    assert len(boards.BOARDS) > 500
    plats = {b["platform"] for b in boards.BOARDS.values()}
    assert plats == {"esp8266", "esp32", "rp2", "bk72xx", "rtl87xx", "ln882x"}
    for b in boards.BOARDS.values():
        ids = [p["id"] for p in b["pins"]]
        assert ids and len(ids) == len(set(ids)), b["key"]
        assert b["i2c_default"]["sda"] in ids and b["i2c_default"]["scl"] in ids, b["key"]


def test_every_board_generates_a_valid_minimal_yaml():
    for key in boards.BOARDS:
        p = gen.default_project(key)
        p["name"] = "t"
        r = gen.generate(p, STORED)
        assert r["yaml"].strip(), key
        if key in ("esp32-h2-devkitm-1",):
            assert any("kein eigenes WLAN" in e for e in r["errors"])


def test_beken_board_cb2s():
    b = boards.BOARDS["cb2s"]
    assert b["platform"] == "bk72xx" and "BK7231N" in b["label"]
    assert {"P6", "P7", "P8", "P24", "P26"} <= set(b["pin_map"])
    assert b["pin_map"]["P0"].get("uart") and b["pin_map"]["P23"].get("adc")
    r = gen.generate(proj("cb2s", [comp("light_pwm", "L", {"pin": "P6"}), comp("switch", "S", {"pin": "P24"})]), STORED)
    assert r["ok"], r["errors"]
    assert "bk72xx:" in r["yaml"] and "board: cb2s" in r["yaml"] and "libretiny_pwm" in r["yaml"]
    assert any("PWM" in e for e in errors(proj("cb2s", [comp("light_pwm", "L", {"pin": "P21"})])))
    assert any("kein Analog-Pin" in e for e in errors(proj("cb2s", [comp("adc", "A", {"pin": "P6"})])))
    assert any("nicht" in e for e in errors(proj("cb2s", [comp("bme280", "B")])))  # kein I²C bei LibreTiny


def test_rp2_and_esp32_variants():
    r = gen.generate(proj("rpipicow", [comp("light_pwm", "L", {"pin": "GPIO15"})]), STORED)
    assert r["ok"], r["errors"]
    assert "rp2:" in r["yaml"] and "rp2040_pwm" in r["yaml"]
    assert any("keinen WLAN-Chip" in e for e in errors(proj("rpipico")))
    assert boards.BOARDS["rpipico2w"]["has_wifi"]
    assert boards.BOARDS["esp32-s3-devkitc-1"]["i2c_default"] == {"sda": "GPIO8", "scl": "GPIO9"}
    assert any("RMT" in e for e in errors(proj("esp32-c2-devkitm-1", [comp("light_strip", "S", {"pin": "GPIO2"})])))


def test_board_search_meta_is_light():
    import json
    meta = boards.boards_meta()
    assert len(json.dumps(meta)) < 150_000 and "pins" not in meta[0]
    assert boards.board_detail("gibts-nicht") is None and boards.board_detail("d1_mini")["pins"]
