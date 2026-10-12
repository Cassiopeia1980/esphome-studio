"""Importiert eine bestehende ESPHome-YAML in ein ESPHome-Studio-Projekt.

Grundsatz: Es wird nur übernommen, was das Studio beim Erzeugen genauso wieder ausgeben würde.
Alles andere (eigene Skripte, Lambdas, Display, andere Sensoren …) bleibt unverändert erhalten und
landet im Feld „Zusatz-YAML“, das der Generator wieder einmischt. So geht nichts verloren.
Kommentare lassen sich nicht erhalten.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any

from . import boards as B
from .components import COMPONENTS, LIGHT_RESTORE_MODES
from .catalog import catalog as _catalog
from .i18n import T, tr, use_lang
from .generator import _cur_lang, uptime_format, LOG_LEVELS, spec_for, PWM_PLATFORM, _effects, default_project, dump_yaml, new_component, slug
from .yamlutil import Tag, load_text

PLATFORM_KEYS = ("esp8266", "esp32", "rp2", "rp2040", "bk72xx", "rtl87xx", "ln882x")
FX_FLAGS = ("fx_pulse", "fx_random", "fx_strobe")
def wifi_info_map() -> dict[str, tuple[str, str, str]]:
    return {"ip": ("ip_address", T("IP-Adresse"), "mdi:ip-network"),
            "ssid": ("ssid", T("Verbunden mit (SSID)"), "mdi:access-point-network"),
            "bssid": ("bssid", T("Verbunden mit (BSSID)"), "mdi:access-point"),
            "mac": ("mac_address", T("MAC-Adresse"), "mdi:ip")}
INTERVAL_RE = re.compile(r"^\d+(\.\d+)?(ms|s|min|h)$")


class Unmapped(Exception):
    """Dieses Element kann das Studio nicht (genau so) abbilden und gibt es unverändert weiter."""


def _only(item: dict[str, Any], allowed: set[str]) -> None:
    extra = [k for k in item if k not in allowed]
    if extra:
        raise Unmapped("nicht abbildbar: " + ", ".join(str(k) for k in extra))


class _Importer:
    def __init__(self, text: str, secrets_text: str) -> None:
        self.notes: list[str] = []
        self.unmapped: list[str] = []
        self.errors: list[str] = []
        self.secrets_found: dict[str, str] = {}
        self.cfg: dict[str, Any] = {}
        self.extra: dict[str, Any] = {}
        self.sec: dict[str, Any] = {}
        self.subs: dict[str, Any] = {}
        self.missing_secrets: set[str] = set()
        self.board: dict[str, Any] = {}
        self.p: dict[str, Any] = {}
        self.refs: Counter[str] = Counter()
        self.text = text
        self.secrets_text = secrets_text

    # ------------------------------------------------------------ Hilfen ---
    def note(self, msg: str) -> None:
        if msg not in self.notes:
            self.notes.append(msg)

    def sub(self, v: Any) -> Any:
        """Ersetzt ${name} / $name durch den Wert aus ``substitutions``."""
        if not isinstance(v, str) or "$" not in v:
            return v

        def rep(m: re.Match[str]) -> str:
            k = m.group(1) or m.group(2)
            return str(self.subs[k]) if k in self.subs else m.group(0)

        return re.sub(r"\$\{([A-Za-z0-9_]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", rep, v)

    def val(self, v: Any) -> Any:
        """Löst !secret und Substitutionen auf. Unbekanntes Secret -> None."""
        if isinstance(v, Tag):
            if v.tag == "!secret":
                if v.value in self.sec:
                    return self.sec[v.value]
                self.missing_secrets.add(str(v.value))
                return None
            raise Unmapped(f"{v.tag} wird nicht unterstützt")
        return self.sub(v)

    def is_secret(self, v: Any) -> bool:
        return isinstance(v, Tag) and v.tag == "!secret"

    def extra_set(self, path: list[str], value: Any) -> None:
        d = self.extra
        for k in path[:-1]:
            d = d.setdefault(k, {})
        d[path[-1]] = value

    def extra_add(self, domain: str, item: Any) -> None:
        self.extra.setdefault(domain, []).append(item)

    def describe(self, domain: str, item: Any) -> str:
        if isinstance(item, dict):
            plat = item.get("platform")
            name = item.get("name")
            if isinstance(name, str):
                return f"{domain}: {plat or '?'} „{name}“" if plat else f"{domain}: „{name}“"
            return f"{domain}: {plat}" if plat else domain
        return domain

    def count_refs(self, node: Any, key: str | None = None) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                self.count_refs(v, str(k))
        elif isinstance(node, list):
            for v in node:
                self.count_refs(v, key)
        elif isinstance(node, Tag):
            if isinstance(node.value, str):
                for m in re.finditer(r"\bid\(\s*([A-Za-z0-9_]+)\s*\)", node.value):
                    self.refs[m.group(1)] += 1
            else:
                self.count_refs(node.value, key)
        elif isinstance(node, str) and key != "id":
            self.refs[node] += 1

    # -------------------------------------------------------------- Pins ---
    def pin(self, raw: Any, modes: bool = False) -> tuple[str, bool, str | None]:
        """Liefert (Pin-Kennung, invertiert, Modus). Unbekanntes -> Unmapped."""
        inverted = False
        mode: str | None = None
        number = raw
        if isinstance(raw, dict):
            _only(raw, {"number", "inverted", "mode"})
            number = raw.get("number")
            inverted = bool(self.val(raw.get("inverted", False)))
            m = raw.get("mode")
            if isinstance(m, str):
                mode = m.upper()
            elif isinstance(m, dict):
                _only(m, {"input", "output", "pullup", "pulldown"})
                if m.get("output"):
                    mode = "OUTPUT"
                elif m.get("input") and m.get("pullup"):
                    mode = "INPUT_PULLUP"
                elif m.get("input") and m.get("pulldown"):
                    mode = "INPUT_PULLDOWN"
                elif m.get("input"):
                    mode = "INPUT"
                else:
                    raise Unmapped("Pin-Modus unbekannt")
            elif m is not None:
                raise Unmapped("Pin-Modus unbekannt")
            if mode and not modes and mode not in ("OUTPUT", "INPUT"):
                raise Unmapped(f"Pin-Modus {mode}")
        number = self.val(number)
        pid: str | None = None
        table = self.board["alias_to_id"]
        if isinstance(number, str):
            pid = table.get(number.strip().upper())
            if pid is None and number.strip().isdigit():
                number = int(number.strip())
        if pid is None and isinstance(number, int) and not isinstance(number, bool):
            pid = next((p["id"] for p in self.board["pins"] if p.get("gpio") == number and p["id"] != "A0"), None)
        if pid is None:
            raise Unmapped(f"Pin „{number}“ gibt es auf diesem Board nicht")
        return pid, inverted, mode

    def plain_pin(self, raw: Any) -> tuple[str, bool]:
        pid, inv, mode = self.pin(raw)
        if mode == "INPUT":
            raise Unmapped("Pin-Modus INPUT")
        return pid, inv

    # ------------------------------------------------------- Komponenten ---
    def new(self, type_key: str, name: str, item: dict[str, Any], pins: dict[str, str]) -> dict[str, Any]:
        c = new_component(type_key, name, pins)
        if isinstance(item.get("id"), str):
            c["id"] = item["id"]
        return c

    # ------------------------------------------------- Katalog-Bausteine ---
    def _cat_index(self) -> dict[tuple[str, str], dict[str, Any]]:
        idx = getattr(self, "_cat_idx", None)
        if idx is None:
            idx = {}
            for e in _catalog().get("entries", []):
                if e.get("unsupported") or e.get("domain") == "hub":
                    continue
                idx.setdefault((e["domain"], e["platform"]), e)
            self._cat_idx = idx
        return idx

    def catalog_item(self, domain: str, item: dict[str, Any]) -> dict[str, Any]:
        """Wandelt einen Eintrag in einen Katalog-Baustein um, sonst Unmapped (bleibt dann Zusatz-YAML)."""
        e = self._cat_index().get((domain, str(item.get("platform"))))
        if not e:
            raise Unmapped("nicht im Katalog")
        if e.get("bus") in ("uart", "spi") or e.get("hub") or e.get("refs") or e.get("needs") \
                or e.get("needs_cat") or e.get("needs_dom"):
            raise Unmapped("braucht weitere Bausteine (Hub, UART, SPI oder Verweise)")
        pins = {ps["key"]: ps for ps in e["pins"]}
        fields = {f["key"]: f for f in e["fields"]}
        subs = {sb["key"]: sb for sb in e.get("subs", [])}
        allowed = {"platform", "id", "name", "update_interval"} | set(pins) | set(fields) | set(subs)
        extra = [k for k in item if k not in allowed]
        if extra:
            raise Unmapped("enthält Einstellungen, die das Studio nicht abbildet: " + ", ".join(sorted(map(str, extra))))
        if "update_interval" in item and not e.get("has_interval"):
            raise Unmapped("update_interval nicht abbildbar")
        name = item.get("name")
        if e.get("self_entity"):
            if not isinstance(name, str) or not name.strip():
                raise Unmapped("Name fehlt")
        else:
            if not (isinstance(name, str) and name.strip()):
                name = None
                for k, sb in subs.items():  # Name aus den Messwert-Namen ableiten („Bad Temperatur“ -> „Bad“)
                    sv = item.get(k)
                    n = sv.get("name") if isinstance(sv, dict) else None
                    if isinstance(n, str) and n.endswith(" " + sb["label"]) and n[: -len(sb["label"]) - 1].strip():
                        name = n[: -len(sb["label"]) - 1].strip()
                        break
                if not name:
                    name = str(item.get("id") or e["label"])
        o: dict[str, Any] = {}
        cpins: dict[str, str] = {}
        for k, ps in pins.items():
            if k not in item:
                continue
            pid, inv, mode = self.pin(self.val(item[k]), modes=True)
            if inv or mode not in (None, "INPUT", "OUTPUT"):
                raise Unmapped(f"Pin {k}: invertiert oder besonderer Modus")
            cpins[k] = pid
        for k, f in fields.items():
            if k not in item:
                continue
            if "lambda" in k or k.startswith("on_"):
                raise Unmapped(f"{k}: Lambda/Automation nicht abbildbar")
            v = self.val(item[k])
            if v is None or isinstance(v, (dict, list)) or isinstance(item[k], Tag):
                raise Unmapped(f"{k}: Wert nicht abbildbar")
            if f["type"] == "bool":
                if not isinstance(v, bool):
                    raise Unmapped(f"{k}: kein Ja/Nein-Wert")
                o["f_" + k] = v
            else:
                if f["type"] == "enum" and str(v) not in [str(x) for x in f.get("choices", [])] and f.get("choices"):
                    raise Unmapped(f"{k}: Wert nicht in der Auswahl")
                o["f_" + k] = str(v)
        for k, sb in subs.items():
            if k not in item:
                continue
            sv = item[k]
            want = {"name": f"{name} {sb['label']}"}
            if sv not in (want, None) and not (isinstance(sv, dict) and sv == want):
                raise Unmapped(f"{k}: eigene Einstellungen/Name abweichend")
            o["s_" + k] = True
        for sb in subs.values():
            if sb.get("required") and "s_" + sb["key"] not in o:
                raise Unmapped("Pflicht-Messwert fehlt")
        if "update_interval" in item:
            iv = self.val(item["update_interval"])
            if not isinstance(iv, str) or not INTERVAL_RE.match(iv):
                raise Unmapped("update_interval ungültig")
            o["interval"] = iv
        iid = item.get("id")
        if isinstance(iid, str) and iid:
            if self.refs.get(iid, 0) > 0 and (e.get("self_entity") or e.get("subs") or e.get("no_id")):
                raise Unmapped("die ID wird anderswo verwendet")
        c = new_component("generic", name, cpins)
        c["cat"] = e["id"]
        c["options"].update(o)
        if isinstance(iid, str) and iid:
            c["id"] = iid
        return c

    def freq(self, v: Any) -> str:
        if v in (None, ""):
            return ""
        if isinstance(v, (int, float)):
            return str(int(v))
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:Hz)?\s*", str(v))
        if not m:
            raise Unmapped("PWM-Frequenz unbekannt")
        return str(int(float(m.group(1))))

    def text_name(self, v: Any) -> str:
        v = self.val(v)
        if not isinstance(v, str) or not v.strip():
            raise Unmapped("Name fehlt oder ist kein Text")
        return v

    def interval(self, v: Any, default: str) -> str:
        if v in (None, ""):
            return default
        v = self.val(v)
        if not isinstance(v, str) or not INTERVAL_RE.match(v):
            raise Unmapped("Intervall unbekannt")
        return v

    def hexaddr(self, v: Any, default: str, width: bool = True) -> str:
        if v is None:
            return default
        if isinstance(v, int) and not isinstance(v, bool):
            return f"0x{v:02X}" if width else f"0x{v:x}"
        if isinstance(v, str) and re.fullmatch(r"0x[0-9a-fA-F]+", v):
            return v
        raise Unmapped("Adresse unbekannt")

    def _name_pair(self, item: dict[str, Any], pairs: list[tuple[str, str]]) -> str:
        """Bei Sensoren mit mehreren Messwerten: Namen müssen „<Name> <Suffix>“ heißen."""
        base: str | None = None
        for key, suffix in pairs:
            sub = item.get(key)
            if not isinstance(sub, dict):
                raise Unmapped(f"{key} fehlt")
            _only(sub, {"name"})
            nm = self.text_name(sub.get("name"))
            if not nm.endswith(" " + suffix):
                raise Unmapped("Namen passen nicht zum Studio-Schema")
            b = nm[: -len(suffix) - 1]
            if base is not None and b != base:
                raise Unmapped("Namen passen nicht zum Studio-Schema")
            base = b
        return base or ""

    # --- Ausgänge / Lichter ---
    def collect_outputs(self) -> dict[str, dict[str, Any]]:
        outs: dict[str, dict[str, Any]] = {}
        raw = self.cfg.get("output")
        if not isinstance(raw, list):
            return outs
        for it in raw:
            if isinstance(it, dict) and isinstance(it.get("id"), str):
                outs[it["id"]] = it
        return outs

    def pwm_channel(self, oid: Any, outs: dict[str, dict[str, Any]]) -> tuple[str, bool, str, dict[str, Any]]:
        if not isinstance(oid, str) or oid not in outs:
            raise Unmapped("Ausgang nicht gefunden")
        it = outs[oid]
        _only(it, {"platform", "id", "pin", "frequency"})
        if it.get("platform") != PWM_PLATFORM.get(self.board["platform"]):
            raise Unmapped("PWM-Plattform passt nicht zum Board")
        if self.refs[oid] != 1:
            raise Unmapped("Ausgang wird noch anderweitig benutzt")
        pid, inv = self.plain_pin(it.get("pin"))
        return pid, inv, self.freq(it.get("frequency")), it

    def map_effects(self, item: dict[str, Any], color: bool, opts: dict[str, Any]) -> None:
        fx = item.get("effects")
        if fx is None:
            return
        def bare(lst: Any) -> Any:  # Struktur ohne Effektnamen vergleichen
            if not isinstance(lst, list):
                return None
            out_ = []
            for e in lst:
                if not isinstance(e, dict) or len(e) != 1:
                    return None
                (kind, conf), = e.items()
                if not isinstance(conf, dict):
                    return None
                out_.append({kind: {k: v for k, v in conf.items() if k != "name"}})
            return out_

        want = bare(fx)
        for combo in range(8):
            flags = {FX_FLAGS[i]: bool(combo >> i & 1) for i in range(3)}
            fake = {"options": flags}
            std = None
            for lg in ("de", "en"):
                with use_lang(lg):
                    std = _effects(fake, color)
                if std == fx:
                    opts.update(flags)
                    return
            with use_lang("de"):
                std = _effects(fake, color)
            if want is not None and bare(std) == want:
                names = [next(iter(e.values())).get("name") for e in fx]
                if all(isinstance(n, str) and n for n in names):
                    opts.update(flags)
                    opts["fx_names"] = names  # eigene Effektnamen bleiben erhalten
                    return
        raise Unmapped("eigene Lichteffekte")

    def light(self, item: dict[str, Any], outs: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
        plat = item.get("platform")
        restore = None
        if plat in ("binary", "monochromatic", "rgb", "rgbw", "rgbww"):
            restore = item.get("restore_mode")
            if restore is not None:
                if restore not in LIGHT_RESTORE_MODES:
                    raise Unmapped("restore_mode nicht abbildbar")
                item = {k: v for k, v in item.items() if k != "restore_mode"}
        consumed: list[str] = []
        name_raw = item.get("name")
        name_none = (name_raw is None and "name" in item) or str(name_raw) == "None"
        nm = (self.p.get("friendly_name") or "Licht") if name_none else self.text_name(name_raw)
        base_keys = {"platform", "name", "id", "effects"}
        if plat == "binary":
            _only(item, base_keys - {"effects"} | {"output"})
            oid = item.get("output")
            o = outs.get(oid) if isinstance(oid, str) else None
            if not o:
                raise Unmapped("Ausgang nicht gefunden")
            _only(o, {"platform", "id", "pin"})
            if o.get("platform") != "gpio" or self.refs[oid] != 1:
                raise Unmapped("Ausgang passt nicht")
            pid, inv = self.plain_pin(o.get("pin"))
            c = self.new("light_binary", nm, item, {"pin": pid})
            c["options"]["inverted"] = inv
            c["options"]["name_none"] = name_none
            if restore:
                c["options"]["restore_mode"] = restore
            return c, [oid]
        if plat == "monochromatic":
            _only(item, base_keys | {"output"})
            pid, inv, fr, _ = self.pwm_channel(item.get("output"), outs)
            c = self.new("light_pwm", nm, item, {"pin": pid})
            c["options"].update(inverted=inv, frequency=fr, name_none=name_none)
            if restore:
                c["options"]["restore_mode"] = restore
            self.map_effects(item, False, c["options"])
            return c, [item["output"]]
        chans = {"rgb": [("red", "red"), ("green", "green"), ("blue", "blue")],
                 "rgbw": [("red", "red"), ("green", "green"), ("blue", "blue"), ("white", "white")],
                 "rgbww": [("red", "red"), ("green", "green"), ("blue", "blue"), ("cold_white", "cold_white"),
                           ("warm_white", "warm_white")]}.get(str(plat))
        if chans:
            allowed = base_keys | {k for k, _ in chans}
            if plat in ("rgbw", "rgbww"):
                allowed |= {"color_interlock"}
            if plat == "rgbww":
                allowed |= {"cold_white_color_temperature", "warm_white_color_temperature"}
            _only(item, allowed)
            pins: dict[str, str] = {}
            invs: set[bool] = set()
            freqs: set[str] = set()
            for pin_key, conf in chans:
                pid, inv, fr, _ = self.pwm_channel(item.get(conf), outs)
                pins[pin_key] = pid
                invs.add(inv)
                freqs.add(fr)
                consumed.append(item[conf])
            if len(invs) > 1 or len(freqs) > 1:
                raise Unmapped("Kanäle haben unterschiedliche Invertierung/Frequenz")
            c = self.new(f"light_{plat}", nm, item, pins)
            c["options"].update(inverted=invs.pop(), frequency=freqs.pop(), name_none=name_none)
            if restore:
                c["options"]["restore_mode"] = restore
            if plat in ("rgbw", "rgbww"):
                c["options"]["color_interlock"] = bool(item.get("color_interlock", False))
            if plat == "rgbww":
                for k, conf in (("cold_temp", "cold_white_color_temperature"), ("warm_temp", "warm_white_color_temperature")):
                    m = re.fullmatch(r"\s*(\d+)\s*K", str(item.get(conf, "")))
                    if not m:
                        raise Unmapped("Farbtemperatur nicht in Kelvin")
                    c["options"][k] = int(m.group(1))
            self.map_effects(item, True, c["options"])
            return c, consumed
        if plat == "esp32_rmt_led_strip":
            _only(item, {"platform", "name", "id", "pin", "num_leds", "channel_colors", "rgb_order", "chipset"})
            pid, _ = self.plain_pin_out(item.get("pin"))
            c = self.new("light_strip", nm, item, {"pin": pid})
            c["options"]["name_none"] = False
            if name_none:
                raise Unmapped("name: None")
            n = item.get("num_leds")
            if not isinstance(n, int):
                raise Unmapped("LED-Anzahl")
            c["options"]["num_leds"] = n
            order = item.get("channel_colors") or item.get("rgb_order") or "GRB"
            chipset = item.get("chipset") or "WS2812"
            specs = {o["key"]: o for o in COMPONENTS["light_strip"]["options"]}
            if order not in specs["rgb_order"]["choices"] or chipset not in specs["chipset"]["choices"]:
                raise Unmapped("Chipsatz/Farbreihenfolge")
            c["options"]["rgb_order"] = order
            c["options"]["chipset"] = chipset
            return c, []
        raise Unmapped(f"Licht-Plattform {plat}")

    def plain_pin_out(self, raw: Any) -> tuple[str, bool]:
        pid, inv, mode = self.pin(raw, modes=True)
        if mode not in (None, "OUTPUT"):
            raise Unmapped("Pin-Modus")
        return pid, inv

    def switch(self, item: dict[str, Any]) -> dict[str, Any]:
        _only(item, {"platform", "name", "id", "pin", "restore_mode", "on_turn_on"})
        if item.get("platform") != "gpio":
            raise Unmapped(f"Schalter-Plattform {item.get('platform')}")
        pid, inv = self.plain_pin_out(item.get("pin"))
        c = self.new("switch", self.text_name(item.get("name")), item, {"pin": pid})
        c["options"]["inverted"] = inv
        rm = item.get("restore_mode")
        if rm is not None:
            if rm not in ("RESTORE_DEFAULT_OFF", "RESTORE_DEFAULT_ON", "ALWAYS_OFF", "ALWAYS_ON"):
                raise Unmapped("restore_mode")
            c["options"]["restore_mode"] = rm
        t = item.get("on_turn_on")
        if t is not None:
            m = None
            if isinstance(t, list) and len(t) == 2 and isinstance(t[0], dict) and isinstance(t[1], dict):
                m = re.fullmatch(r"(\d+)ms", str(t[0].get("delay", "")))
                tgt = t[1].get("switch.turn_off")
                ident = item.get("id")
                if not (m and len(t[0]) == 1 and len(t[1]) == 1 and tgt and tgt == ident):
                    m = None
            if not m:
                raise Unmapped("eigene Aktion bei on_turn_on")
            c["options"]["pulse_ms"] = int(m.group(1))
        return c

    def binary_sensor(self, item: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        _only(item, {"platform", "name", "id", "pin", "device_class", "filters", "on_press"})
        pid, inv, mode = self.pin(item.get("pin"), modes=True)
        c = self.new("binary_sensor", self.text_name(item.get("name")), item, {"pin": pid})
        c["options"]["mode"] = mode or "INPUT"
        c["options"]["inverted"] = inv
        dc = item.get("device_class")
        choices = [o for o in COMPONENTS["binary_sensor"]["options"] if o["key"] == "device_class"][0]["choices"]
        if dc is not None:
            if dc not in choices:
                raise Unmapped("device_class")
            c["options"]["device_class"] = dc
        f = item.get("filters")
        c["options"]["debounce_ms"] = 0
        if f is not None:
            if not (isinstance(f, list) and len(f) == 1 and isinstance(f[0], dict) and set(f[0]) == {"delayed_on_off"}):
                raise Unmapped("eigene Filter")
            m = re.fullmatch(r"(\d+)ms", str(f[0]["delayed_on_off"]))
            if not m:
                raise Unmapped("Filter-Zeit")
            c["options"]["debounce_ms"] = int(m.group(1))
        target = None
        op = item.get("on_press")
        if op is not None:
            if not (isinstance(op, list) and len(op) == 1 and isinstance(op[0], dict) and len(op[0]) == 1):
                raise Unmapped("eigene Aktion bei on_press")
            (k, v), = op[0].items()
            if k not in ("switch.toggle", "light.toggle") or not isinstance(v, str):
                raise Unmapped("eigene Aktion bei on_press")
            target = v
        return c, target

    def sensor(self, item: dict[str, Any]) -> dict[str, Any]:
        plat = item.get("platform")
        if plat == "dht":
            _only(item, {"platform", "pin", "model", "temperature", "humidity", "update_interval"})
            pid, _ = self.plain_pin_io(item.get("pin"))
            name = self._name_pair(item, [("temperature", "Temperatur"), ("humidity", "Luftfeuchte")])
            model = str(item.get("model", "DHT22"))
            if model not in ("DHT22", "DHT11", "AM2302", "AUTO_DETECT"):
                raise Unmapped("DHT-Modell")
            c = new_component("dht", name, {"pin": pid})
            c["options"].update(model=model, update_interval=self.interval(item.get("update_interval"), "60s"))
            return c
        if plat == "adc":
            _only(item, {"platform", "pin", "name", "attenuation", "unit_of_measurement", "filters", "update_interval"})
            pid, _ = self.plain_pin_io(item.get("pin"), adc=True)
            c = self.new("adc", self.text_name(item.get("name")), item, {"pin": pid})
            att = item.get("attenuation")
            if att is not None:
                if str(att) not in ("12db", "6db", "2.5db", "0db"):
                    raise Unmapped("Dämpfung")
                c["options"]["attenuation"] = str(att)
            c["options"]["unit"] = str(item.get("unit_of_measurement", ""))
            f = item.get("filters")
            c["options"]["multiply"] = ""
            if f is not None:
                if not (isinstance(f, list) and len(f) == 1 and isinstance(f[0], dict) and set(f[0]) == {"multiply"}
                        and isinstance(f[0]["multiply"], (int, float))):
                    raise Unmapped("eigene Filter")
                c["options"]["multiply"] = str(f[0]["multiply"])
            c["options"]["update_interval"] = self.interval(item.get("update_interval"), "60s")
            return c
        if plat == "ultrasonic":
            _only(item, {"platform", "trigger_pin", "echo_pin", "name", "timeout", "update_interval"})
            trig, _ = self.plain_pin_out(item.get("trigger_pin"))
            echo, _ = self.plain_pin_io(item.get("echo_pin"))
            c = self.new("ultrasonic", self.text_name(item.get("name")), item, {"trigger": trig, "echo": echo})
            to = str(item.get("timeout", "2m"))
            if not re.fullmatch(r"\d+(\.\d+)?(m|cm|mm)", to):
                raise Unmapped("Timeout")
            c["options"].update(timeout=to, update_interval=self.interval(item.get("update_interval"), "10s"))
            return c
        if plat == "dallas_temp":
            return self.dallas(item)
        i2c = {"bme280_i2c": "bme280", "bmp280_i2c": "bmp280", "sht3xd": "sht3xd", "aht10": "aht10", "bh1750": "bh1750"}
        if plat in i2c:
            return self.i2c_sensor(item, i2c[plat])
        raise Unmapped(f"Sensor-Plattform {plat}")

    def plain_pin_io(self, raw: Any, adc: bool = False) -> tuple[str, bool]:
        if adc and isinstance(raw, (str, int)):
            pid, inv, mode = self.pin(raw, modes=True)
            return pid, inv
        pid, inv, mode = self.pin(raw, modes=True)
        if mode not in (None, "INPUT", "OUTPUT"):
            raise Unmapped("Pin-Modus")
        return pid, inv

    def dallas(self, item: dict[str, Any]) -> dict[str, Any]:
        _only(item, {"platform", "one_wire_id", "name", "address", "resolution", "update_interval", "filters", "id"})
        bus_id = item.get("one_wire_id")
        buses = self.cfg.get("one_wire")
        bus = None
        if isinstance(buses, list):
            bus = next((b for b in buses if isinstance(b, dict) and b.get("id") == bus_id), None)
        if not bus:
            raise Unmapped("1-Wire-Bus nicht gefunden")
        _only(bus, {"platform", "pin", "id"})
        if bus.get("platform") != "gpio" or self.refs[bus_id] != 1:
            raise Unmapped("1-Wire-Bus wird mehrfach benutzt")
        pid, _ = self.plain_pin_io(bus.get("pin"))
        c = self.new("dallas", self.text_name(item.get("name")), item, {"pin": pid})
        c["options"]["address"] = self.hexaddr(item.get("address"), "", width=False) if "address" in item else ""
        res = item.get("resolution", 12)
        if res not in (9, 10, 11, 12):
            raise Unmapped("Auflösung")
        c["options"]["resolution"] = res
        c["options"]["update_interval"] = self.interval(item.get("update_interval"), "60s")
        thr = delta = ""
        f = item.get("filters")
        if f is not None:
            if not (isinstance(f, list) and len(f) == 1 and isinstance(f[0], dict)):
                raise Unmapped("eigene Filter")
            combined = set(f[0]) == {"or"}
            flt = f[0]["or"] if combined else f
            if not isinstance(flt, list) or len(flt) != (2 if combined else 1):
                raise Unmapped("eigene Filter")
            for e in flt:
                if not isinstance(e, dict) or len(e) != 1:
                    raise Unmapped("eigene Filter")
                (k, v), = e.items()
                if k == "throttle" and isinstance(v, str) and INTERVAL_RE.match(v) and not thr:
                    thr = v
                elif k == "delta" and isinstance(v, (int, float)) and not isinstance(v, bool) and not delta:
                    delta = str(v)
                else:
                    raise Unmapped("eigene Filter")
        c["options"].update(throttle=thr, delta=delta)
        self.consume_bus = bus_id
        return c

    def i2c_sensor(self, item: dict[str, Any], t: str) -> dict[str, Any]:
        if t == "bme280":
            _only(item, {"platform", "temperature", "pressure", "humidity", "address", "update_interval"})
            name = self._name_pair(item, [("temperature", "Temperatur"), ("pressure", "Druck"), ("humidity", "Luftfeuchte")])
            default = "0x76"
        elif t == "bmp280":
            _only(item, {"platform", "temperature", "pressure", "address", "update_interval"})
            name = self._name_pair(item, [("temperature", "Temperatur"), ("pressure", "Druck")])
            default = "0x76"
        elif t == "sht3xd":
            _only(item, {"platform", "temperature", "humidity", "address", "update_interval"})
            name = self._name_pair(item, [("temperature", "Temperatur"), ("humidity", "Luftfeuchte")])
            default = "0x44"
        elif t == "aht10":
            _only(item, {"platform", "variant", "temperature", "humidity", "update_interval"})
            name = self._name_pair(item, [("temperature", "Temperatur"), ("humidity", "Luftfeuchte")])
            default = ""
        else:
            _only(item, {"platform", "name", "address", "update_interval"})
            name = self.text_name(item.get("name"))
            default = "0x23"
        c = new_component(t, name, {})
        if t == "aht10":
            v = str(item.get("variant", "AHT20"))
            if v not in ("AHT20", "AHT10"):
                raise Unmapped("AHT-Typ")
            c["options"]["variant"] = v
        else:
            addr = self.hexaddr(item.get("address"), default)
            choices = [o for o in COMPONENTS[t]["options"] if o["key"] == "address"][0]["choices"]
            if addr.lower() not in [x.lower() for x in choices]:
                raise Unmapped("I²C-Adresse")
            c["options"]["address"] = next(x for x in choices if x.lower() == addr.lower())
        c["options"]["update_interval"] = self.interval(item.get("update_interval"), "60s")
        return c

    # --------------------------------------------------------------- Lauf ---
    def run(self) -> dict[str, Any]:
        try:
            cfg = load_text(self.text)
        except ValueError as exc:
            return self.fail(f"Die YAML lässt sich nicht lesen: {exc}")
        if not isinstance(cfg, dict) or not cfg:
            return self.fail("Die YAML ist leer oder hat keine Abschnitte wie „esphome:“.")
        if self.secrets_text.strip():
            try:
                s = load_text(self.secrets_text)
                self.sec = s if isinstance(s, dict) else {}
            except ValueError as exc:
                self.note(f"secrets.yaml konnte nicht gelesen werden ({exc}). Secrets bleiben unaufgelöst.")
        self.cfg = cfg = copy.deepcopy(cfg)
        self.count_refs(cfg)
        for k in ("packages", "<<"):
            if k in cfg:
                self.note("„packages“ werden nicht aufgelöst; der Abschnitt bleibt unverändert im Zusatz-YAML.")
        if "esphome" not in cfg or not isinstance(cfg["esphome"], dict):
            return self.fail("Im YAML fehlt der Abschnitt „esphome:“ mit dem Gerätenamen.")
        subs = cfg.pop("substitutions", None)
        self.subs = {str(k): v for k, v in subs.items()} if isinstance(subs, dict) else {}

        # --- Plattform / Board ---
        plat_key = next((k for k in PLATFORM_KEYS if k in cfg), None)
        if not plat_key:
            return self.fail("Es fehlt der Plattform-Abschnitt (esp32:, esp8266:, rp2:, bk72xx: …).")
        pblock = cfg.pop(plat_key)
        pblock = dict(pblock) if isinstance(pblock, dict) else {}
        out_key = "rp2" if plat_key == "rp2040" else plat_key
        board_id = self.val(pblock.pop("board", None)) if "board" in pblock else None
        variant = str(pblock.get("variant", "")) if plat_key == "esp32" else ""
        key = B.find_board(plat_key, str(board_id)) if board_id else None
        if key is None:
            key = B.default_board(plat_key, variant)
            self.note(f"Das Board „{board_id or '(keins)'}“ kennt das Studio nicht. Ersatz: „{key}“. "
                      "Bitte das richtige Board unter „Gerät“ wählen und die Pins prüfen.")
            if board_id:
                self.extra_set([out_key, "board"], board_id)
        self.board = B.BOARDS[key]
        self.p = default_project(key)
        p = self.p
        p["components"] = []
        if plat_key == "esp8266":
            fm = pblock.pop("board_flash_mode", None)
            if fm in ("dout", "dio", "qio", "qout"):
                p["flash_mode"] = fm
            elif fm is not None:
                pblock["board_flash_mode"] = fm
            ep = pblock.pop("early_pin_init", None)
            if isinstance(ep, bool):
                p["early_pin_init"] = "true" if ep else "false"
            elif ep is not None:
                pblock["early_pin_init"] = ep
        if plat_key == "esp32":
            fw = pblock.get("framework")
            if isinstance(fw, dict):
                ftype = fw.pop("type", "esp-idf")
                p["framework"] = "arduino" if ftype == "arduino" else "esp-idf"
                if ftype not in ("arduino", "esp-idf"):
                    fw["type"] = ftype
                if not fw:
                    pblock.pop("framework")
        if pblock:
            self.extra_set([out_key], pblock)

        # --- esphome:-Block ---
        es = dict(cfg.pop("esphome"))
        raw_name = es.pop("name", None)
        name = self.val(raw_name)
        if isinstance(name, str):
            p["name"] = name.strip()
        else:
            return self.fail("Der Gerätename unter „esphome: name:“ fehlt.")
        if str(raw_name) in ("$devicename", "${devicename}") and "devicename" in self.subs:
            p["substitutions"] = True
        if "friendly_name" in es:
            p["friendly_name"] = str(self.val(es.pop("friendly_name")) or "")
        else:
            p["friendly_name"] = ""
        if "comment" in es:
            raw_c = es.pop("comment")
            p["comment"] = str(self.val(raw_c) or "")
            if p["substitutions"] and str(raw_c) not in ("${device_description}", "$device_description"):
                p["substitutions"] = bool(p["substitutions"])
        if es:
            self.extra_set(["esphome"], es)
        if self.subs:
            rest = dict(self.subs)
            if p["substitutions"]:
                rest.pop("devicename", None)
                rest.pop("device_description", None)
            if rest:
                self.extra_set(["substitutions"], rest)

        self.network(cfg)
        self.logger_and_misc(cfg)
        self.components(cfg)
        # Alles Übrige unverändert weitergeben
        for k, v in cfg.items():
            if k in self.extra and isinstance(self.extra[k], dict) and isinstance(v, dict):
                self.extra[k].update({kk: vv for kk, vv in v.items() if kk not in self.extra[k]})
            elif k in self.extra and isinstance(self.extra[k], list) and isinstance(v, list):
                self.extra[k].extend(v)
            else:
                self.extra[k] = v
                self.unmapped.append(f"{k}: unverändert als Zusatz-YAML übernommen")
        if self.extra:
            p["extra_yaml"] = dump_yaml(self.extra, blank_between_top=True).rstrip() + "\n"
        else:
            p["extra_yaml"] = ""
        if self.missing_secrets:
            self.note("Diese Secrets sind in der eingefügten secrets.yaml nicht zu finden und bleiben offen: "
                      + ", ".join(sorted(self.missing_secrets)))
        return {"ok": True, "project": p, "notes": self.notes, "unmapped": self.unmapped,
                "secrets": self.secrets_found, "errors": []}

    def fail(self, msg: str) -> dict[str, Any]:
        return {"ok": False, "project": None, "notes": [], "unmapped": [], "secrets": {}, "errors": [msg]}

    # ---------------------------------------------------------- Netzwerk ---
    def network(self, cfg: dict[str, Any]) -> None:
        p = self.p
        wifi = cfg.pop("wifi", None)
        wifi = dict(wifi) if isinstance(wifi, dict) else {}
        ssid_raw, pw_raw = wifi.get("ssid"), wifi.get("password")
        if ssid_raw is not None and pw_raw is not None:
            p["use_secrets"] = self.is_secret(ssid_raw) or self.is_secret(pw_raw)
            ssid, pw = self.val(ssid_raw), self.val(pw_raw)
            if isinstance(ssid, str) and ssid:
                self.secrets_found["wifi_ssid"] = ssid
            if isinstance(pw, str) and pw:
                self.secrets_found["wifi_password"] = pw
            wifi.pop("ssid")
            wifi.pop("password")
        elif "networks" in wifi:
            self.note("Das WLAN ist als Liste „networks“ angegeben. Das Studio kennt nur ein Netz; "
                      "die Liste bleibt im Zusatz-YAML, die Zugangsdaten bitte unter „WLAN“ eintragen.")
        ap = wifi.pop("ap", None)
        p["wifi"]["fallback_ap"] = ap is not None
        if isinstance(ap, dict):
            ap = dict(ap)
            pwd = ap.pop("password", None)
            val = self.val(pwd) if pwd is not None else None
            if isinstance(val, str) and len(val) >= 8:
                p["wifi"]["ap_password"] = val
            elif pwd is not None:
                self.note("Das Passwort des Fallback-Hotspots konnte nicht gelesen werden; es wurde ein neues erzeugt.")
            if ap:
                self.extra_set(["wifi", "ap"], ap)
        cp = cfg.get("captive_portal", "__none__")
        if cp in ({}, None) and "captive_portal" in cfg:
            cfg.pop("captive_portal")
        mip = wifi.pop("manual_ip", None)
        if isinstance(mip, dict):
            mip = dict(mip)
            si = p["wifi"]["static_ip"]
            si.update(enabled=True, ip=str(self.val(mip.pop("static_ip", "")) or ""),
                      gateway=str(self.val(mip.pop("gateway", "")) or ""),
                      subnet=str(self.val(mip.pop("subnet", "255.255.255.0")) or ""))
            if "dns1" in mip:
                si["dns"] = str(self.val(mip.pop("dns1")) or "")
            if mip:
                self.extra_set(["wifi", "manual_ip"], mip)
        mam = wifi.pop("min_auth_mode", None)
        if mam in ("WPA", "WPA2", "WPA3"):
            p["wifi"]["min_auth_mode"] = mam
        elif mam is not None:
            wifi["min_auth_mode"] = mam
        if wifi:
            self.extra_set(["wifi"], {**self.extra.get("wifi", {}), **wifi})

        # --- API ---
        if "api" in cfg:
            api = cfg.pop("api")
            api = dict(api) if isinstance(api, dict) else {}
            enc = api.pop("encryption", None)
            p["api"]["enabled"] = True
            if enc is None:
                p["api"]["encryption"] = False
            else:
                p["api"]["encryption"] = True
                key_raw = enc.get("key") if isinstance(enc, dict) else None
                key = self.val(key_raw) if key_raw is not None else None
                if isinstance(key, str) and len(key) >= 40:
                    p["api"]["key"] = key
                else:
                    p["api"]["key"] = ""
                    self.note("Der API-Schlüssel der Verschlüsselung ist nicht lesbar (Secret fehlt). "
                              "Entweder die secrets.yaml mit einfügen oder den Schlüssel unter „Sicherheit“ eintragen. "
                              "Ein neuer Schlüssel würde die Verbindung zu Home Assistant trennen.")
                if isinstance(enc, dict) and set(enc) - {"key"}:
                    self.extra_set(["api", "encryption"], {k: v for k, v in enc.items() if k != "key"})
            if api:
                self.extra_set(["api"], {**self.extra.get("api", {}), **api})
        else:
            p["api"]["enabled"] = False

        # --- OTA ---
        ota = cfg.pop("ota", "__none__")
        p["ota"]["enabled"] = ota != "__none__"
        if ota != "__none__":
            items = ota if isinstance(ota, list) else [ota]
            rest = []
            done = False
            for it in items:
                if isinstance(it, dict) and it.get("platform") == "esphome" and not done:
                    it = dict(it)
                    it.pop("platform")
                    pw = it.pop("password", None)
                    encr = it.pop("encryption", None)
                    if pw is not None:
                        p["ota"]["mode"] = "password"
                        v = self.val(pw)
                        if isinstance(v, str) and v:
                            p["ota"]["password"] = v
                        else:
                            self.note("Das OTA-Passwort ist nicht lesbar (Secret fehlt) und wurde neu erzeugt. "
                                      "Beim nächsten OTA-Update bitte das alte Passwort verwenden oder neu flashen.")
                    elif encr is not None:
                        p["ota"]["mode"] = "encryption"
                    else:
                        p["ota"]["mode"] = "none"
                    if it:
                        self.note(f"OTA-Einstellungen ({', '.join(map(str, it))}) werden nicht abgebildet und gehen verloren.")
                    done = True
                else:
                    rest.append(it)
            if not done:
                p["ota"]["enabled"] = False
            if rest:
                self.extra_set(["ota"], rest)

        # --- Webserver / Uhrzeit ---
        ws = cfg.get("web_server", "__none__")
        if ws == {"port": 80, "ota": False}:
            p["web_server"] = True
            cfg.pop("web_server")
        elif isinstance(ws, dict) and ws.get("ota") is False and "port" in ws and set(ws) <= {
                "port", "ota", "version", "local", "include_internal", "log", "compression",
                "enable_private_network_access", "css_url", "js_url", "allowed_origins"}:
            ok = isinstance(ws["port"], int) and not isinstance(ws["port"], bool) and 1 <= ws["port"] <= 65535
            ok = ok and ws.get("version", 2) in (1, 2, 3) and ws.get("compression", "gzip") in ("gzip", "br")
            ok = ok and all(isinstance(ws.get(k, False), bool) for k in ("local", "include_internal", "log", "enable_private_network_access"))
            ok = ok and all(isinstance(ws.get(k, ""), str) for k in ("css_url", "js_url"))
            ao = ws.get("allowed_origins", [])
            ok = ok and isinstance(ao, list) and all(isinstance(o, str) and "," not in o and " " not in o for o in ao)
            if ok:
                p["web_server"] = True
                p["web"] = {
                    "version": str(ws.get("version", 2)), "port": ws["port"], "local": ws.get("local", False),
                    "include_internal": ws.get("include_internal", False), "log": ws.get("log", True),
                    "compression": ws.get("compression", "gzip"), "auth": False, "auth_user": "", "auth_password": "",
                    "auth_type": "basic", "ota_web": False, "css_url": ws.get("css_url", ""), "js_url": ws.get("js_url", ""),
                    "private_network": ws.get("enable_private_network_access", False),
                    "allowed_origins": ", ".join(ao),
                }
                cfg.pop("web_server")
        t = cfg.get("time")
        if isinstance(t, list):
            for it in list(t):
                if isinstance(it, dict) and it.get("platform") == "homeassistant" and set(it) <= {"platform", "id"} \
                        and it.get("id", "homeassistant_time") == "homeassistant_time" and not p["time_ha"]:
                    p["time_ha"] = True
                    t.remove(it)
            if not t:
                cfg.pop("time")

    def logger_and_misc(self, cfg: dict[str, Any]) -> None:
        lg = cfg.pop("logger", None)
        if isinstance(lg, dict):
            lg = dict(lg)
            lvl = lg.pop("level", None)
            if lvl in LOG_LEVELS:
                self.p["log_level"] = lvl
            elif lvl is not None:
                lg["level"] = lvl
            if lg:
                self.extra_set(["logger"], lg)

    # ------------------------------------------------------ Komponenten ---
    def components(self, cfg: dict[str, Any]) -> None:
        p = self.p
        outs = self.collect_outputs()
        self.consume_bus = None
        consumed_outputs: set[str] = set()
        consumed_buses: set[str] = set()
        comps: list[dict[str, Any]] = []
        targets: list[tuple[dict[str, Any], str]] = []
        keep: dict[str, list[Any]] = {}
        diag = p["diag"] = {"wifi_signal": False, "uptime": False, "restart": False, "ip": False, "ssid": False,
                            "bssid": False, "mac": False, "status": False, "uptime_text": False,
                            "debug_heap": False, "debug_loop": False, "debug_reset": False}

        custom: dict[str, dict[str, Any]] = {}
        p["diag_custom"] = custom

        def ent(d: Any, name: str, icon: str | None = None, cat: str | None = "diagnostic",
                lenient: bool = False) -> dict[str, Any] | None:
            """Prüft Name/Symbol/Kategorie eines Diagnose-Eintrags. Streng: nur Standard. Sonst werden eigene Werte gemerkt."""
            if not isinstance(d, dict) or set(d) - {"name", "icon", "entity_category"}:
                return None
            cust: dict[str, Any] = {}
            n = d.get("name")
            if not isinstance(n, str) or not n:
                return None
            if n != name:
                cust["name"] = n
            ic = d.get("icon")
            if ic != icon:
                if ic is not None and not isinstance(ic, str):
                    return None
                cust["icon"] = ic or ""
            ca = d.get("entity_category")
            if ca != cat:
                if ca is not None and ca not in ("diagnostic", "config"):
                    return None
                cust["category"] = ca or ""
            return None if cust and not lenient else cust

        def diag_one(domain: str, item: dict[str, Any], lenient: bool = False) -> bool:
            plat = item.get("platform")
            found: dict[str, bool] = {}
            cust: dict[str, dict[str, Any]] = {}

            def done() -> bool:
                diag.update(found)
                custom.update({k: v for k, v in cust.items() if v})
                return True

            if domain == "sensor" and plat == "wifi_signal" and set(item) <= {"platform", "name", "update_interval", "entity_category"}:
                c = ent({k: v for k, v in item.items() if k not in ("platform", "update_interval")}, T("WLAN-Signal"), None,
                        "diagnostic", lenient)
                if c is not None and item.get("update_interval") == "60s":
                    found["wifi_signal"], cust["wifi_signal"] = True, c
                    return done()
                return False
            if domain == "sensor" and plat == "uptime" and set(item) <= {"platform", "name", "entity_category"}:
                c = ent({k: v for k, v in item.items() if k != "platform"}, T("Laufzeit"), None, "diagnostic", lenient)
                if c is not None:
                    found["uptime"], cust["uptime"] = True, c
                    return done()
                return False
            if domain == "text_sensor" and plat == "uptime" and set(item) <= {
                    "platform", "name", "icon", "update_interval", "entity_category", "format"}:
                c = ent({k: v for k, v in item.items() if k not in ("platform", "update_interval", "format")},
                        T("Betriebszeit"), "mdi:clock-start", "diagnostic", lenient)
                fmt = item.get("format")
                if c is None or item.get("update_interval") != "60s" or not isinstance(fmt, dict):
                    return False
                if fmt != uptime_format(_cur_lang()):
                    if (not lenient or not fmt or set(fmt) - {"separator", "days", "hours", "minutes", "seconds"}
                            or not all(isinstance(v, str) for v in fmt.values())):
                        return False
                    c = {**c, "format": dict(fmt)}
                found["uptime_text"], cust["uptime_text"] = True, c
                return done()
            if domain == "text_sensor" and plat == "wifi_info":
                for flag, (conf, label, icon) in wifi_info_map().items():
                    if conf in item:
                        c = ent(item[conf], label, icon, "diagnostic", lenient)
                        if c is None:
                            return False
                        found[flag], cust[flag] = True, c
                if set(item) - {"platform"} - {c_ for c_, _, _ in wifi_info_map().values()} or not found:
                    return False
                return done()
            if domain == "binary_sensor" and plat == "status" and set(item) <= {"platform", "name", "entity_category"}:
                c = ent({k: v for k, v in item.items() if k != "platform"}, "Status", None, "diagnostic", lenient)
                if c is not None:
                    found["status"], cust["status"] = True, c
                    return done()
                return False
            if domain == "button" and plat == "restart" and set(item) <= {"platform", "name", "entity_category"}:
                c = ent({k: v for k, v in item.items() if k != "platform"}, T("Neustart"), None, "config", lenient)
                if c is not None:
                    found["restart"], cust["restart"] = True, c
                    return done()
                return False
            if domain == "sensor" and plat == "debug":
                got = {k: v for k, v in item.items() if k != "platform"}
                names = {"free": T("Freier Heap"), "block": T("Größter Heap-Block"), "loop_time": T("Loop-Zeit")}
                if got and set(got) <= set(names):
                    if ("free" in got) != ("block" in got):
                        return False
                    for k, v in got.items():
                        c = ent(v, names[k], None, "diagnostic", lenient)
                        if c is None:
                            return False
                        cust["debug_loop" if k == "loop_time" else f"debug_{k}"] = c
                    if "free" in got:
                        found["debug_heap"] = True
                    if "loop_time" in got:
                        found["debug_loop"] = True
                    return done()
                return False
            if domain == "text_sensor" and plat == "debug" and set(item) == {"platform", "reset_reason"}:
                c = ent(item["reset_reason"], T("Reset-Grund"), None, "diagnostic", lenient)
                if c is not None:
                    found["debug_reset"], cust["debug_reset"] = True, c
                    return done()
            return False

        def diag_try(domain: str, item: dict[str, Any]) -> bool:
            for lg in ("de", "en"):  # Standard-Diagnose-Entitäten in beiden Sprachen erkennen
                with use_lang(lg):
                    if diag_one(domain, item):
                        return True
            with use_lang("de"):  # sonst eigene Namen/Symbole/Format übernehmen
                return diag_one(domain, item, lenient=True)

        fixed_doms = ("output", "one_wire", "light", "switch", "binary_sensor", "sensor", "text_sensor", "button")
        cat_doms = sorted({d for (d, _pl) in self._cat_index()
                           if d not in fixed_doms and isinstance(cfg.get(d), list)})
        all_doms = fixed_doms + tuple(cat_doms)
        for domain in all_doms:
            items = cfg.get(domain)
            if not isinstance(items, list):
                continue
            for item in items:
                if domain in ("output", "one_wire"):
                    keep.setdefault(domain, []).append(item)
                    continue
                if not isinstance(item, dict):
                    keep.setdefault(domain, []).append(item)
                    continue
                try:
                    if diag_try(domain, item):
                        continue
                    if domain == "light":
                        c, used = self.light(item, outs)
                        consumed_outputs.update(used)
                        comps.append(c)
                    elif domain == "switch":
                        comps.append(self.switch(item))
                    elif domain == "binary_sensor":
                        c, tgt = self.binary_sensor(item)
                        comps.append(c)
                        if tgt:
                            targets.append((c, tgt))
                    elif domain == "sensor":
                        self.consume_bus = None
                        c = self.sensor(item)
                        if self.consume_bus:
                            consumed_buses.add(self.consume_bus)
                        comps.append(c)
                    else:
                        raise Unmapped("nicht abbildbar")
                except Unmapped as exc:
                    if domain in ("output", "one_wire"):
                        keep.setdefault(domain, []).append(item)
                        self.unmapped.append(f"{self.describe(domain, item)} – {exc}")
                        continue
                    try:
                        comps.append(self.catalog_item(domain, item))
                        self.note(f"{self.describe(domain, item)} wurde als Katalog-Baustein übernommen.")
                    except Unmapped as exc2:
                        keep.setdefault(domain, []).append(item)
                        generic = str(exc2) == "nicht im Katalog" or str(exc2).startswith("braucht weitere Bausteine")
                        why = str(exc) if generic and str(exc) != "nicht abbildbar" else (
                            str(exc) if str(exc2) == "nicht im Katalog" else str(exc2))
                        self.unmapped.append(f"{self.describe(domain, item)} – {why}")
        # Ausgänge / 1-Wire, die verbraucht wurden, nicht weitergeben
        for dom, used in (("output", consumed_outputs), ("one_wire", consumed_buses)):
            rest = [i for i in keep.get(dom, []) if not (isinstance(i, dict) and i.get("id") in used)]
            if rest:
                keep[dom] = rest
            else:
                keep.pop(dom, None)
        for dom in all_doms:
            cfg.pop(dom, None)
        for dom, items in keep.items():
            self.extra[dom] = items

        # Toggle-Ziele auflösen
        by_id = {c.get("id") or slug(c["name"]): c for c in comps
                 if c["type"] in ("switch", "light_binary", "light_pwm", "light_rgb", "light_rgbw", "light_rgbww",
                                  "light_strip")}
        for c, tgt in targets:
            t = by_id.get(tgt)
            if t is not None:
                c["options"]["toggle_target"] = t["uid"]
            else:
                self.note(f"Der Taster „{c['name']}“ schaltet „{tgt}“ um. Das Ziel ist nicht abbildbar; "
                          "bitte das Umschalten im Zusatz-YAML ergänzen.")
        # Komponenten, die eine ID brauchen, behalten ihre ursprüngliche ID
        for c in comps:
            if c.get("id") and c["id"] == slug(c["name"]):
                c.pop("id")

        # --- Top-Level-Komponenten ---
        sl = cfg.get("status_led")
        if isinstance(sl, dict) and set(sl) == {"pin"}:
            try:
                pid, inv = self.plain_pin_out(sl["pin"])
                c = new_component("status_led", "Status-LED", {"pin": pid})
                c["options"]["inverted"] = inv
                comps.append(c)
                cfg.pop("status_led")
            except Unmapped as exc:
                self.unmapped.append(f"status_led – {exc}")
        rr = cfg.get("remote_receiver")
        if isinstance(rr, dict) and set(rr) <= {"pin", "dump"} and "pin" in rr and rr.get("dump", "none") in ("all", "none"):
            try:
                pid, inv, mode = self.pin(rr["pin"], modes=True)
                c = new_component("ir_receiver", "IR-Empfänger", {"pin": pid})
                c["options"].update(inverted=inv, dump=rr.get("dump", "none"))
                comps.append(c)
                cfg.pop("remote_receiver")
            except Unmapped as exc:
                self.unmapped.append(f"remote_receiver – {exc}")
        rt = cfg.get("remote_transmitter")
        if isinstance(rt, dict) and set(rt) <= {"pin", "carrier_duty_percent", "non_blocking"} and "pin" in rt:
            try:
                pid, _ = self.plain_pin_out(rt["pin"])
                m = re.fullmatch(r"(\d+)%", str(rt.get("carrier_duty_percent", "50%")))
                if not m:
                    raise Unmapped("Tastverhältnis")
                c = new_component("ir_transmitter", "IR-Sender", {"pin": pid})
                c["options"]["duty"] = int(m.group(1))
                comps.append(c)
                cfg.pop("remote_transmitter")
            except Unmapped as exc:
                self.unmapped.append(f"remote_transmitter – {exc}")

        # i2c-Bus
        i2c = cfg.get("i2c")
        needs = any(spec_for(c).get("needs_i2c") for c in comps)
        if isinstance(i2c, dict) and needs and set(i2c) <= {"sda", "scl", "scan"} and "sda" in i2c and "scl" in i2c \
                and i2c.get("scan", True) is True:
            try:
                sda, _ = self.plain_pin_io(i2c["sda"])
                scl, _ = self.plain_pin_io(i2c["scl"])
                p["i2c"] = {"sda": sda, "scl": scl}
                cfg.pop("i2c")
            except Unmapped as exc:
                self.unmapped.append(f"i2c – {exc}")

        # debug:-Block
        dbg = cfg.get("debug")
        if any(diag[k] for k in ("debug_heap", "debug_loop", "debug_reset")):
            if isinstance(dbg, dict) and set(dbg) <= {"update_interval"}:
                iv = dbg.get("update_interval", "30s")
                if isinstance(iv, str) and INTERVAL_RE.match(iv):
                    p["debug_interval"] = iv
                cfg.pop("debug")
            elif dbg is None and "debug" in cfg:
                cfg.pop("debug")
        # Debug-Sensoren ohne zugehörigen Block bleiben bestehen -> Studio erzeugt den Block selbst
        p["components"] = comps


def import_yaml(text: str, secrets_text: str = "", lang: str = "de") -> dict[str, Any]:
    """Liest eine ESPHome-YAML und liefert ``{ok, project, notes, unmapped, secrets, errors}``."""
    with use_lang(lang):
        try:
            res = _Importer(text, secrets_text).run()
        except Unmapped as exc:  # pragma: no cover - sollte intern abgefangen sein
            res = {"ok": False, "project": None, "notes": [], "unmapped": [], "secrets": {}, "errors": [str(exc)]}
        except Exception as exc:  # noqa: BLE001 - beliebige Benutzer-YAML darf nie abstürzen
            res = {"ok": False, "project": None, "notes": [], "unmapped": [], "secrets": {},
                   "errors": [T("Der Import ist fehlgeschlagen: {0}: {1}", type(exc).__name__, exc)]}
        if lang == "en":
            for k in ("notes", "unmapped", "errors"):
                res[k] = [tr(m) for m in res.get(k, [])]
        return res
