"""Erzeugt Beispielprojekte für jedes Board und prüft sie mit `esphome config`.

Aufruf:  python tests/validate_with_esphome.py [pfad/zu/esphome] [--lang=en]
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from helpers import load_core  # noqa: E402

boards, components, gen = load_core()
STORED = {"wifi_ssid": "Test WLAN", "wifi_password": "geheim-1234"}


def comp(type_key, name, pins=None, **options):
    c = gen.new_component(type_key, name, pins)
    c["options"].update(options)
    return c


def project(board, name, comps, **extra):
    p = gen.default_project(board)
    p["name"] = name
    p["friendly_name"] = name.title()
    p["components"] = comps
    p.update(extra)
    return p


SAMPLES = {}

# --- ESP8266 -----------------------------------------------------------------
relay = comp("switch", "Relais 1", {"pin": "GPIO5"})
btn = comp("binary_sensor", "Taster", {"pin": "GPIO14"}, toggle_target=relay["uid"], device_class="none")
SAMPLES["d1-basis"] = project("d1_mini", "d1-basis", [
    relay, btn,
    comp("dht", "Wohnzimmer", {"pin": "GPIO12"}, model="DHT22"),
    comp("dallas", "Vorlauf", {"pin": "GPIO13"}),
    comp("adc", "Akku", {"pin": "A0"}, multiply="3.2"),
    comp("status_led", "Status", {"pin": "GPIO2"}, inverted=True),
], web_server=True, time_ha=True, diag={"wifi_signal": True, "uptime": True, "ip": True, "restart": True})

SAMPLES["web-v3-auth"] = project("d1_mini", "web-v3-auth", [comp("switch", "Relais", {"pin": "GPIO5"})],
    web_server=True, web={"version": "3", "port": 8080, "local": True, "include_internal": True, "log": False,
                          "compression": "br", "auth": True, "auth_user": "admin", "auth_password": "geheim",
                          "auth_type": "digest", "ota_web": True, "css_url": "", "js_url": "", "private_network": True, "allowed_origins": "https://example.com"})
SAMPLES["web-v1"] = project("d1_mini", "web-v1", [comp("switch", "Relais", {"pin": "GPIO5"})],
    web_server=True, web={"version": "1", "port": 80})

def gcomp(cat, name, pins=None, **options):
    return {"uid": gen.new_uid(), "type": "generic", "cat": cat, "name": name, "pins": dict(pins or {}), "options": options}


_hub = gcomp("ld2410", "Radar", {"_rx": "GPIO16", "_tx": "GPIO17"}, baud="256000")
SAMPLES["katalog-esp32"] = project("esp32dev", "katalog-esp32", [
    gcomp("bme680.sensor", "Wetter", s_temperature=True, s_humidity=True, s_pressure=True, f_iir_filter="3X", interval="30s"),
    gcomp("pmsx003.sensor", "Feinstaub", {"_rx": "GPIO26"}, baud="9600", f_type="PMSX003", s_pm_2_5=True, s_pm_10_0=True),
    gcomp("ads1115", "Wandler", f_address="0x49"),
    _hub,
    gcomp("ld2410.sensor", "Radar-Werte", {}, hub=_hub["uid"], s_moving_distance=True),
    gcomp("gpio.binary_sensor", "Tür", {"pin": "GPIO4"}, extra="device_class: door"),
])
_exp = gcomp("pcf8574", "Erweiterung", f_address="0x21")
_out = gcomp("ledc.output", "Gebläse-Ausgang", {"pin": "GPIO18"})
_tpl = gcomp("template.sensor", "Quelle")
SAMPLES["katalog-erweitert"] = project("esp32dev", "katalog-erweitert", [
    _exp,
    comp("switch", "Relais extern", {"pin": f"x:{_exp['uid']}:3"}),
    comp("binary_sensor", "Taster extern", {"pin": f"x:{_exp['uid']}:5"}),
    gcomp("ssd1306_i2c.display", "Display", f_model="SSD1306_128X64"),
    _out, gcomp("speed.fan", "Gebläse", {}, ref_output=_out["uid"]),
    _tpl, gcomp("copy.sensor", "Kopie", {}, ref_source_id=_tpl["uid"]),
    gcomp("deep_sleep", "Schlaf"),
])
SAMPLES["katalog-d1"] = project("d1_mini", "katalog-d1", [
    gcomp("sht4x.sensor", "Bad", s_temperature=True, s_humidity=True),
    gcomp("pulse_counter.sensor", "Zähler", {"pin": "GPIO13"}, f_count_mode_rising_edge="INCREMENT"),
])

def F(t, **v):
    return {"t": t, "v": {k: str(x) for k, x in v.items()}}


_all_sensor_filters = [
    F("offset", value=-1.5), F("multiply", value=2), F("calibrate_linear", datapoints="0 -> 0, 100 -> 98"),
    F("clamp", min_value=-20, max_value=80), F("round", value=1),
    F("sliding_window_moving_average", window_size=10, send_every=5), F("exponential_moving_average", alpha=0.1, send_every=2),
    F("median", window_size=5, send_every=5), F("max", window_size=5, send_every=5), F("min", window_size=5, send_every=5),
    F("throttle", value="30s"), F("throttle_average", value="60s"), F("delta", value="0.5"), F("heartbeat", value="5min"),
    F("debounce", value="1s"), F("timeout", timeout="10min", value="NAN"), F("skip_initial", value=2),
    F("filter_out", value="85"), F("lambda", value="return x * 2;"),
]
_dht = comp("dht", "Klima", {"pin": "GPIO12"})
_dht["options"]["ent"] = {
    "temperature": {"name": "Raumtemperatur", "icon": "mdi:thermometer", "device_class": "temperature", "unit_of_measurement": "°C",
                    "state_class": "measurement", "accuracy_decimals": "1", "filters": _all_sensor_filters},
    "humidity": {"entity_category": "diagnostic", "internal": True, "disabled_by_default": True, "filters": [F("offset", value=3)]},
}
_btn = comp("binary_sensor", "Taster", {"pin": "GPIO14"})
_btn["options"]["ent"] = {"": {"filters": [F("invert"), F("delayed_on", value="50ms"), F("delayed_off", value="1s"),
                                           F("delayed_on_off", value="20ms"), F("settle", value="250ms"), F("lambda", value="return x;")]}}
_sw = comp("switch", "Pumpe", {"pin": "GPIO5"})
_sw["options"]["ent"] = {"": {"icon": "mdi:pump", "entity_category": "config"}}
SAMPLES["profi-d1"] = project("d1_mini", "profi-d1", [_dht, _btn, _sw])
_g = gcomp("bme680.sensor", "Wetter", s_temperature=True, s_humidity=True)
_g["options"]["ent"] = {"temperature": {"name": "Außen", "filters": [F("offset", value=-0.5), F("sliding_window_moving_average", window_size=5, send_every=5)]}}
_ts = gcomp("version.text_sensor", "Version")
_ts["options"]["ent"] = {"": {"icon": "mdi:information", "entity_category": "diagnostic",
                              "filters": [F("to_upper"), F("to_lower"), F("append", value=" x"), F("prepend", value="v "), F("lambda", value="return x;")]}}
SAMPLES["profi-katalog"] = project("esp32dev", "profi-katalog", [_g, _ts])

SAMPLES["d1-rgbww"] = project("d1_mini", "d1-rgbww", [
    comp("light_rgbww", "Kinderzimmer", {"red": "GPIO5", "green": "GPIO4", "blue": "GPIO14",
                                         "cold_white": "GPIO12", "warm_white": "GPIO13"}, frequency="1000"),
    comp("bme280", "Raum"), comp("bh1750", "Licht"),
])
SAMPLES["d1-rgbww"]["i2c"] = {"sda": "GPIO0", "scl": "GPIO16"}

SAMPLES["nodemcu-i2c"] = project("nodemcuv2", "nodemcu-i2c", [
    comp("bme280", "Wetter", address="0x77"),
    comp("sht3xd", "Bad"), comp("aht10", "Keller"), comp("bmp280", "Dach"),
    comp("ultrasonic", "Zisterne", {"trigger": "GPIO12", "echo": "GPIO13"}),
    comp("light_pwm", "Lampe", {"pin": "GPIO14"}, inverted=True),
    comp("light_binary", "Spot", {"pin": "GPIO15"}),
])

SAMPLES["nodemcu-pw"] = project("nodemcuv2", "nodemcu-pw", [comp("switch", "R", {"pin": "GPIO4"})])
SAMPLES["nodemcu-pw"]["ota"]["mode"] = "password"
SAMPLES["aquarium"] = project("d1_mini", "aquarium", [
    comp("status_led", "Status-LED", {"pin": "GPIO2"}, inverted=True),
    comp("light_rgbw", "Aquarium", {"red": "GPIO5", "green": "GPIO13", "blue": "GPIO15", "white": "GPIO12"},
         name_none=True, fx_pulse=True, fx_random=True, fx_strobe=True),
    comp("dallas", "Temperatur", {"pin": "GPIO4"}, address="0x740119380813e928", resolution=12,
         update_interval="10s", throttle="30s", delta="0.2"),
], friendly_name="Aquarium", comment="Aquarium im Wohnzimmer", substitutions=True, flash_mode="dout",
    early_pin_init="false",
    diag={"wifi_signal": True, "uptime": False, "uptime_text": True, "ip": True, "ssid": True, "bssid": True,
          "mac": True, "restart": True, "status": True, "debug_heap": True, "debug_loop": True, "debug_reset": True})
SAMPLES["aquarium"]["wifi"]["min_auth_mode"] = "WPA2"
SAMPLES["aquarium"]["wifi"]["static_ip"].update(enabled=True, ip="192.168.3.71", gateway="192.168.1.1",
                                                 subnet="255.255.252.0", dns="192.168.1.1")
SAMPLES["mono-fx"] = project("d1_mini", "mono-fx", [
    comp("light_pwm", "Lampe", {"pin": "GPIO14"}, fx_pulse=True, fx_random=True, fx_strobe=True),
    comp("dallas", "Sonde", {"pin": "GPIO4"}, resolution=10, delta="0.5"),
    comp("dallas", "Sonde 2", {"pin": "GPIO12"}, throttle="1min"),
])
SAMPLES["esp01-tv"] = project("esp01_1m", "esp01-tv", [
    comp("binary_sensor", "TV Status", {"pin": "GPIO2"}, mode="INPUT", inverted=False),
    comp("switch", "Relais", {"pin": "GPIO0"}, pulse_ms=500),
], use_secrets=False)

# --- ESP32 -------------------------------------------------------------------
SAMPLES["esp32-voll"] = project("esp32dev", "esp32-voll", [
    comp("switch", "Pumpe", {"pin": "GPIO23"}),
    comp("light_rgb", "Regal", {"red": "GPIO25", "green": "GPIO26", "blue": "GPIO27"}),
    comp("light_rgbw", "Tisch", {"red": "GPIO18", "green": "GPIO19", "blue": "GPIO32", "white": "GPIO33"},
         color_interlock=True),
    comp("light_strip", "Band", {"pin": "GPIO13"}, num_leds=60, chipset="SM16703", rgb_order="GRB"),
    comp("binary_sensor", "PIR", {"pin": "GPIO34"}, mode="INPUT", inverted=False, device_class="motion"),
    comp("adc", "Boden", {"pin": "GPIO35"}, attenuation="12db"),
    comp("ir_receiver", "IR", {"pin": "GPIO4"}),
    comp("bme280", "Klima"),
    comp("dallas", "Sonde", {"pin": "GPIO16"}, address="0x1c0000031edd2a28"),
], framework="arduino")

SAMPLES["c3-ir"] = project("esp32-c3-devkitm-1", "c3-ir", [
    comp("ir_transmitter", "IR Sender", {"pin": "GPIO3"}),
    comp("ir_receiver", "IR Empfang", {"pin": "GPIO10"}),
    comp("light_pwm", "Dimmer", {"pin": "GPIO6"}, frequency="19531"),
    comp("aht10", "Raum"),
    comp("binary_sensor", "Boot", {"pin": "GPIO9"}),
], static_ip_test=None)
SAMPLES["c3-ir"]["wifi"]["static_ip"].update(enabled=True, ip="192.168.3.50", gateway="192.168.3.1",
                                              dns="192.168.3.1")

SAMPLES["s3-voll"] = project("esp32-s3-devkitc-1", "s3-voll", [
    comp("light_strip", "Streifen", {"pin": "GPIO48"}, num_leds=24),
    comp("dht", "Draussen", {"pin": "GPIO4"}, model="DHT11"),
    comp("switch", "Relais A", {"pin": "GPIO5"}),
    comp("switch", "Relais B", {"pin": "GPIO6"}),
    comp("adc", "Poti", {"pin": "GPIO1"}),
    comp("status_led", "Status", {"pin": "GPIO38"}),
])
SAMPLES["s3-voll"]["i2c"] = {"sda": "GPIO8", "scl": "GPIO9"}
SAMPLES["s3-voll"]["components"].append(comp("bh1750", "Licht"))


# --- Weitere Plattformen (Beken, Realtek, Lightning, RP2040, ESP32-Varianten) ----------------
def free(board, n, pwm=False, skip=0):
    bad = ("flash", "uart", "strapping", "input_only", "adc_only", "usb", "psram", "boot_high", "no_i2c")
    first_adc = next((p["id"] for p in boards.BOARDS[board]["pins"] if p.get("adc")), None)
    ids = [p["id"] for p in boards.BOARDS[board]["pins"]
           if not any(p.get(f) for f in bad) and not (pwm and p.get("no_pwm")) and p["id"] != first_adc]
    return ids[skip:skip + n]


# --- Vorlagen des Start-Assistenten (0.9.0) ---------------------------------------
_f32 = [x for x in free("esp32dev", 12) if x not in ("GPIO33", "GPIO21", "GPIO22")][:6]
SAMPLES["vorlagen-esp32"] = project("esp32dev", "vorlagen-esp32", [
    comp("binary_sensor", "Bewegung", {"pin": _f32[0]}, device_class="motion"),
    comp("switch", "Relais 1", {"pin": _f32[1]}),
    comp("switch", "Relais 2", {"pin": _f32[2]}),
    comp("sht3xd", "Klima"),
    comp("bh1750", "Helligkeit"),
    comp("ultrasonic", "Abstand", {"trigger": _f32[3], "echo": _f32[4]}),
    comp("adc", "Analog", {"pin": "GPIO33"}),
])
_f8266 = ["GPIO12", "GPIO13", "GPIO14"]
SAMPLES["vorlagen-d1"] = project("d1_mini", "vorlagen-d1", [
    comp("binary_sensor", "Bewegung", {"pin": _f8266[0]}, device_class="motion"),
    comp("sht3xd", "Klima"),
    comp("bh1750", "Helligkeit"),
    comp("ultrasonic", "Abstand", {"trigger": _f8266[1], "echo": _f8266[2]}),
    comp("adc", "Analog", {"pin": "A0"}),
])


def lt_sample(key, board):
    pw = free(board, 4, pwm=True)
    used = set(pw)
    others = [x for x in free(board, 20) if x not in used]
    SAMPLES[key] = project(board, key, [
        comp("light_rgb", "Farbe", {"red": pw[0], "green": pw[1], "blue": pw[2]}, fx_pulse=True),
        comp("light_pwm", "Weiss", {"pin": pw[3]}),
        comp("switch", "Relais", {"pin": others[0]}),
    ])
    if len(others) >= 4:  # (Taster, DHT, DS18B20 – nur wenn genug Pins da sind)
        SAMPLES[key]["components"] += [
            comp("binary_sensor", "Taster", {"pin": others[1]}),
            comp("dht", "Klima", {"pin": others[2]}),
            comp("dallas", "Wasser", {"pin": others[3]}, resolution=10),
        ]
    adc = [p["id"] for p in boards.BOARDS[board]["pins"] if p.get("adc")]
    if adc:
        SAMPLES[key]["components"].append(comp("adc", "Messung", {"pin": adc[0]}))


lt_sample("beken-cb2s", "cb2s")
lt_sample("beken-wb2s", "wb2s")
lt_sample("beken-tuya-n", "generic-bk7231n-qfn32-tuya")
lt_sample("realtek", "generic-rtl8710bn-2mb-788k")
lt_sample("lightning", "generic-ln882h")
SAMPLES["pico-w"] = project("rpipicow", "pico-w", [
    comp("light_rgbw", "Band", {"red": "GPIO10", "green": "GPIO11", "blue": "GPIO12", "white": "GPIO13"}),
    comp("binary_sensor", "Taster", {"pin": "GPIO14"}),
    comp("bme280", "Wetter"), comp("dallas", "Teich", {"pin": "GPIO15"}),
    comp("adc", "Pegel", {"pin": "GPIO26"}),
], i2c={"sda": "GPIO4", "scl": "GPIO5"})
SAMPLES["c6"] = project("esp32-c6-devkitc-1", "c6", [
    comp("light_strip", "Band", {"pin": "GPIO5"}, num_leds=10),
    comp("ir_transmitter", "IR", {"pin": "GPIO6"}), comp("bme280", "Wetter"),
])
SAMPLES["s2"] = project("esp32-s2-saola-1", "s2", [
    comp("switch", "R", {"pin": "GPIO1"}), comp("adc", "A", {"pin": "GPIO2"}), comp("bh1750", "L")])


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lang = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--lang=")), "de")
    esphome_bin = args[0] if args else "esphome"
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for key, proj in SAMPLES.items():
            res = gen.generate(proj, STORED, lang=lang)
            print(f"== {key}: ok={res['ok']} warnungen={len(res['warnings'])} fehler={len(res['errors'])}")
            for e in res["errors"]:
                print("   FEHLER:", e)
            for w in res["warnings"]:
                print("   warn:", w)
            if not res["ok"]:
                failed += 1
                continue
            d = tmpdir / key
            d.mkdir()
            (d / f"{key}.yaml").write_text(res["yaml"], encoding="utf-8")
            sec = res["secrets"] or "unused: 1\n"
            (d / "secrets.yaml").write_text(sec, encoding="utf-8")
            r = subprocess.run([esphome_bin, "config", str(d / f"{key}.yaml")], capture_output=True, text=True,
                               timeout=300)
            out = (r.stdout + r.stderr)
            for line in out.splitlines():
                if line.startswith(("WARNING", "ERROR")) or (r.returncode != 0 and line.strip()):
                    if r.returncode == 0 or True:
                        print("   esphome:", line[:300])
            if r.returncode != 0:
                print(f"   -> esphome config FEHLGESCHLAGEN ({key})")
                failed += 1
            else:
                print("   -> esphome config OK" + (" (mit Warnungen)" if any(l.startswith("WARNING") for l in out.splitlines()) else ""))
    print("\nFehlgeschlagen:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
