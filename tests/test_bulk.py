"""Sammel-Umbau: Änderungen einmischen, Sicherheit modernisieren, Round-Trip prüfen."""

from __future__ import annotations

import sys
import types

import pytest
from helpers import PKG_DIR, load_core

boards, components, gen = load_core()
if "esphome_studio.bulk" not in sys.modules:  # bulk braucht nur generator + yamlutil
    pass
from esphome_studio import bulk, importer  # noqa: E402

ACE2 = """\
substitutions:
  devicename: "acepro2"

esphome:
  name: $devicename
  friendly_name: "ACE Pro 2"

esp8266:
  board: d1_mini
  board_flash_mode: dout

logger:
  level: INFO

api:

ota:
  - platform: esphome
    password: !secret ota

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  manual_ip:
    static_ip: 192.168.3.77
    gateway: 192.168.1.1
    subnet: 255.255.252.0
  ap:
    ssid: "${devicename} Fallback AP"
    password: !secret ap_password

captive_portal:

button:
  - platform: restart
    name: "Reboot"

binary_sensor:
  - platform: status
    name: "Status"

light:
  - platform: monochromatic
    name: "Lampe"
    id: lampe
    output: output_component1
    restore_mode: RESTORE_DEFAULT_OFF

output:
  - platform: esp8266_pwm
    id: output_component1
    pin: GPIO5

sensor:
  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s
"""

SECRETS = 'ota: "geheim-ota"\nwifi_ssid: "netz"\nwifi_password: "passwort1234"\nap_password: "hotspot1234"\n'


def _imported(text=ACE2):
    res = importer.import_yaml(text, SECRETS)
    assert res["ok"], res
    return res["project"]


def test_modernize_password_to_encryption_with_migration():
    p = _imported()
    assert p["api"]["encryption"] is False and p["ota"]["mode"] == "password"
    changes = bulk.modernize(p)
    assert "API verschlüsselt" in changes
    assert any("einmalige Umstellung" in c for c in changes)
    assert p["api"]["encryption"] is True and len(p["api"]["key"]) >= 40
    assert p["ota"]["mode"] == "encryption" and p["ota"]["migrate"] is True
    assert p["ota"]["password"] == "geheim-ota"


def test_migration_yaml_has_password_and_plaintext_flag():
    p = _imported()
    bulk.modernize(p)
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    assert out["ok"], out["errors"]
    text = out["yaml"]
    assert "allow_plaintext_upload: true" in text
    assert "!secret acepro2_ota_password" in text
    assert "acepro2_ota_password: " in out["secrets"]
    assert "acepro2_api_key: " in out["secrets"]


def test_migration_off_gives_plain_encryption():
    p = _imported()
    bulk.modernize(p)
    p["ota"]["migrate"] = False
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    assert out["ok"], out["errors"]
    assert "allow_plaintext_upload" not in out["yaml"]
    assert "encryption: {}" in out["yaml"]
    assert "ota_password" not in out["yaml"]


def test_migration_without_old_password_is_an_error():
    p = _imported()
    bulk.modernize(p)
    p["ota"]["password"] = ""
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    assert not out["ok"]
    assert any("OTA-Passwort" in e for e in out["errors"])


def test_import_reads_migration_back():
    p = _imported()
    bulk.modernize(p)
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    back = importer.import_yaml(out["yaml"], out["secrets"] + SECRETS)
    assert back["ok"], back
    assert back["project"]["ota"]["mode"] == "encryption"
    assert back["project"]["ota"].get("migrate") is True


def test_modernize_keeps_existing_api_key():
    p = _imported()
    p["api"].update({"encryption": True, "key": "k" * 44})
    p["ota"] = {"enabled": True, "mode": "encryption"}
    assert bulk.modernize(p) == []
    assert p["api"]["key"] == "k" * 44


def test_apply_patch_merges_dicts_and_components_by_name():
    p = _imported()
    problems = bulk.apply_patch(p, {"wifi": {"static_ip": {"ip": "192.168.3.99"}},
                                    "components": [{"name": "Lampe", "options": {"restore_mode": "ALWAYS_OFF"}}]})
    assert problems == []
    assert p["wifi"]["static_ip"]["ip"] == "192.168.3.99"
    assert p["wifi"]["static_ip"]["gateway"] == "192.168.1.1"  # Rest bleibt
    lamp = next(c for c in p["components"] if c["name"] == "Lampe")
    assert lamp["options"]["restore_mode"] == "ALWAYS_OFF"
    assert lamp["options"]["frequency"] == ""  # andere Optionen bleiben


def test_apply_patch_reports_unknown_component():
    p = _imported()
    problems = bulk.apply_patch(p, {"components": [{"name": "Gibt es nicht", "options": {"x": 1}}]})
    assert problems and "Gibt es nicht" in problems[0]


def test_roundtrip_of_plain_import_is_equivalent():
    p = _imported()
    p["restore_state_syntax"] = False
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    diff = bulk.roundtrip_diff(ACE2, out["yaml"])
    joined = "\n".join(diff)
    # Lichter, Ausgänge, Sensoren, Knöpfe müssen gleichwertig sein (interne IDs spielen keine Rolle)
    for section in ("## light", "## sensor", "## output", "## binary_sensor", "## button"):
        assert section not in joined, joined


def test_roundtrip_detects_real_difference():
    p = _imported()
    out = gen.generate(p, {"wifi_ssid": "netz", "wifi_password": "passwort1234", "ap_password": "hotspot1234"})
    changed = out["yaml"].replace("GPIO5", "GPIO4")
    diff = bulk.roundtrip_diff(ACE2, changed)
    assert any("GPIO" in line for line in diff)


def test_roundtrip_ignores_order_and_comments():
    a = "sensor:\n  - platform: a\n  - platform: b\n# Kommentar\n"
    b = "sensor:\n  - platform: b\n  - platform: a\n"
    assert bulk.roundtrip_diff(a, b) == []


SONOFF_OLD = """\
substitutions:
  devicename: "dachboden"
esphome:
  name: $devicename
esp8266:
  board: esp01_1m
logger:
api:
ota:
  platform: esphome
  password: !secret ota
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
binary_sensor:
  - platform: gpio
    pin:
      number: GPIO0
      mode: INPUT_PULLUP
      inverted: true
    name: "Taster"
    filters:
      - delayed_on: 50ms
      - delayed_off: 50ms
    on_press:
      - light.toggle: light1
light:
  - platform: binary
    name: "Lampe"
    id: light1
    output: relay
output:
  - platform: gpio
    pin: GPIO12
    id: relay
"""

DALLAS_OLD = """\
substitutions:
  devicename: "aq"
esphome:
  name: $devicename
esp8266:
  board: d1_mini
logger:
api:
ota:
  platform: esphome
  password: !secret ota
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
one_wire:
  platform: gpio
  pin: GPIO2
sensor:
  - platform: dallas_temp
    address: 0x740119380813e928
    name: "Temperatur"
"""

WIFI = {"wifi_ssid": "netz", "wifi_password": "passwort1234"}


def test_toggle_with_unmappable_target_is_kept_in_extra_yaml():
    res = importer.import_yaml(SONOFF_OLD, SECRETS)
    assert res["ok"], res
    p = res["project"]
    out = gen.generate(p, {**WIFI, "ap_password": "hotspot1234"})
    assert out["ok"], out["errors"]
    diff = "\n".join(bulk.roundtrip_diff(SONOFF_OLD, out["yaml"]))
    assert "light.toggle" not in diff, diff  # Aktion darf nicht verloren gehen
    assert "light.toggle" in out["yaml"]


def test_old_style_one_wire_dict_is_not_lost():
    res = importer.import_yaml(DALLAS_OLD, SECRETS)
    assert res["ok"], res
    out = gen.generate(res["project"], {**WIFI, "ap_password": "hotspot1234"})
    assert out["ok"], out["errors"]
    assert "one_wire" in out["yaml"] and "dallas_temp" in out["yaml"]
    diff = "\n".join(bulk.roundtrip_diff(DALLAS_OLD, out["yaml"]))
    assert "## one_wire" not in diff and "## sensor" not in diff, diff


def test_roundtrip_ignores_default_resolution_and_wifi_interval():
    a = "sensor:\n  - platform: dallas_temp\n    resolution: 12\n  - platform: wifi_signal\n    update_interval: 60s\n"
    b = "sensor:\n  - platform: dallas_temp\n  - platform: wifi_signal\n"
    assert bulk.roundtrip_diff(a, b) == []
    c = "sensor:\n  - platform: dallas_temp\n    resolution: 10\n"
    assert bulk.roundtrip_diff(c, b)


HDMI_LIKE = """\
substitutions:
  devicename: "hdmi"
esphome:
  name: $devicename
esp32:
  board: esp32dev
logger:
api:
ota:
  platform: esphome
  password: !secret ota
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
binary_sensor:
  - platform: gpio
    id: a_hdmi1
    name: "Out A = HDMI 1"
    pin:
      number: GPIO22
      mode: INPUT_PULLDOWN
      inverted: true
text_sensor:
  - platform: template
    name: "aktueller Eingang"
    lambda: |-
      if (id(a_hdmi1).state) return {"HDMI 1"};
      return {"unbekannt"};
script:
  - id: waehle
    then:
      - if:
          condition:
            binary_sensor.is_on: a_hdmi1
          then:
            - logger.log: "an"
"""


def test_imported_id_is_kept_when_extra_yaml_refers_to_it():
    res = importer.import_yaml(HDMI_LIKE, SECRETS)
    assert res["ok"], res
    out = gen.generate(res["project"], {**WIFI, "ap_password": "hotspot1234"})
    assert out["ok"], out["errors"]
    assert "id: a_hdmi1" in out["yaml"]
    diff = "\n".join(bulk.roundtrip_diff(HDMI_LIKE, out["yaml"]))
    assert "binary_sensor.is_on: a_hdmi1" not in diff, diff


def test_undefined_ids_detects_missing_reference():
    from custom_components.esphome_studio.bulk import undefined_ids
    ok = "binary_sensor:\n  - platform: gpio\n    id: a\n    pin: 1\nscript:\n  - id: s\n    then:\n      - lambda: 'return id(a).state;'\n"
    assert undefined_ids(ok) == []
    bad = ok.replace("    id: a\n", "")
    assert undefined_ids(bad) == ["a"]


def test_undefined_ids_ignores_name_derived_ids_and_service_variables():
    from custom_components.esphome_studio.bulk import undefined_ids
    y = ("number:\n  - platform: template\n    name: Display Brightness\n"
         "api:\n  services:\n    - service: s\n      variables:\n        x: string\n      then:\n"
         "        - lambda: 'return id(display_brightness).state;'\n")
    assert undefined_ids(y) == []


def test_cleanup_diagnostics_moves_uptime_to_text_and_keeps_entity_name():
    from custom_components.esphome_studio.bulk import cleanup_diagnostics
    p = {
        "web_server": True,
        "diag": {"uptime": False, "debug_heap": True, "debug_loop": True, "debug_reset": True},
        "extra_yaml": (
            "web_server:\n  port: 80\n"
            "sensor:\n  - platform: uptime\n    name: Uptime\n    id: uptime_s\n"
            "  - platform: template\n    name: Keep\n    lambda: 'return 1;'\n"
            "text_sensor:\n  - platform: template\n    name: Uhr Betriebszeit\n    icon: mdi:clock-start\n"
            "    lambda: |-\n      uint32_t dur = id(uptime_s).state;\n      return {\"x\"};\n"
            "  - platform: debug\n    reset_reason:\n      name: Reset\n    foo: 1\n"),
    }
    notes = cleanup_diagnostics(p)
    assert notes
    assert p["web_server"] is False
    assert p["diag"]["debug_heap"] is False and p["diag"]["debug_loop"] is False and p["diag"]["debug_reset"] is True
    assert p["diag"]["uptime_text"] is True and p["diag"]["uptime"] is False
    assert p["diag_custom"]["uptime_text"]["name"] == "Uhr Betriebszeit"
    assert p["diag_custom"]["uptime_text"]["icon"] == "mdi:clock-start"
    assert "web_server" not in p["extra_yaml"] and "uptime_s" not in p["extra_yaml"]
    assert "Keep" in p["extra_yaml"] and "foo" not in p["extra_yaml"]
    assert cleanup_diagnostics(p) == []  # idempotent
