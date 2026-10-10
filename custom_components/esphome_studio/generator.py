"""YAML-Generator für ESPHome Studio.

Reines Python ohne Home-Assistant-Abhängigkeit, damit er sich testen und mit
``esphome config`` prüfen lässt.

``generate(project, stored_secrets)`` liefert ein Dict::

    {"yaml": str, "secrets": str, "warnings": [str], "errors": [str], "ok": bool}
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import secrets as _secrets
from typing import Any

from .boards import BOARDS, NO_WIFI_CHIPS, PLATFORM_LABEL, board_has_wifi
from .entity import apply_entity
from .catalog import entry as catalog_entry, spec_for_entry
from .components import ENT_META, COMPONENTS, default_options
from .yamlutil import Tag, load_text

DEVICE_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,29}[a-z0-9])?$")
INTERVAL_RE = re.compile(r"^\d+(\.\d+)?(ms|s|min|h)$")
HEX_RE = re.compile(r"^0x[0-9a-fA-F]{1,16}$")
LOG_LEVELS = ["NONE", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE", "VERY_VERBOSE"]

# ------------------------------------------------------------- YAML-Ausgabe --


class Raw(str):
    """Wird unverändert ins YAML geschrieben (z. B. ``!secret key``)."""


class Cm:
    """Skalar mit Kommentar am Zeilenende."""

    def __init__(self, value: Any, comment: str) -> None:
        self.value = value
        self.comment = comment


_PLAIN_RE = re.compile(r"^[A-Za-z0-9_äöüÄÖÜß][A-Za-z0-9_äöüÄÖÜß ./%()+\-°²³µ]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "none", "~", "y", "n"}
_NUMBERISH = re.compile(r"^[-+]?(\d[\d_]*)(\.\d*)?([eE][-+]?\d+)?$|^0x[0-9a-fA-F]+$|^0o?[0-7]+$")


def _str(s: str) -> str:
    if (
        s
        and _PLAIN_RE.match(s)
        and s.lower() not in _RESERVED
        and not _NUMBERISH.match(s)
        and not s.endswith(" ")
        and ": " not in s
        and " #" not in s
    ):
        return s
    return json.dumps(s, ensure_ascii=False)


def _scalar(v: Any) -> str:
    if isinstance(v, Cm):
        return f"{_scalar(v.value)}  # {v.comment}"
    if isinstance(v, Raw):
        return str(v)
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return repr(v)
    return _str(str(v))


def _inline(v: Any) -> str:
    if isinstance(v, dict):
        return "{}"
    if isinstance(v, list):
        return "[]"
    return _scalar(v)


_TAG_PLAIN = re.compile(r"^[A-Za-z0-9_./@:-]+$")


def _block_ok(v: Any) -> bool:
    """Mehrzeilige Texte (z. B. Lambdas) lesbar als Blockstil ausgeben."""
    return (isinstance(v, str) and "\n" in v.rstrip("\n") and not v.startswith((" ", "\t", "\n"))
            and "\r" not in v and all(ch == "\n" or ch == "\t" or ch >= " " for ch in v))


def _block_lines(head: str, v: str, ind: int) -> list[str]:
    body = v[:-1] if v.endswith("\n") else v
    if v.endswith("\n\n"):  # mehrere Zeilenenden am Schluss: "|+"
        return [head + " |+"] + [(" " * (ind + 2) + ln) if ln else "" for ln in v[:-1].split("\n")]
    return [head + (" |" if v.endswith("\n") else " |-")] + [(" " * (ind + 2) + ln) if ln else "" for ln in body.split("\n")]


def _tag_lines(prefix: str, tag: Tag, ind: int) -> list[str]:
    """Zeilen für einen getaggten Wert; ``prefix`` ist z. B. ``"key:"`` oder ``"-"``."""
    v = tag.value
    if isinstance(v, str):
        if "\n" in v:
            head = f"{prefix} {tag.tag} " + ("|" if v.endswith("\n") else "|-")
            body = v[:-1] if v.endswith("\n") else v
            return [head] + [(" " * (ind + 2) + ln) if ln else "" for ln in body.split("\n")]
        return [f"{prefix} {tag.tag} " + (v if _TAG_PLAIN.match(v) else json.dumps(v, ensure_ascii=False))]
    if isinstance(v, (dict, list)) and v:
        return [f"{prefix} {tag.tag}"] + _lines(v, ind + 2)
    return [f"{prefix} {tag.tag} {_inline(v)}"]


def _lines(obj: Any, ind: int = 0) -> list[str]:
    pad = " " * ind
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Tag):
                out.extend(_tag_lines(f"{pad}{k}:", v, ind))
            elif _block_ok(v):
                out.extend(_block_lines(f"{pad}{k}:", v, ind))
            elif isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:")
                out.extend(_lines(v, ind + 2))
            else:
                out.append(f"{pad}{k}: {_inline(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, Tag):
                out.extend(_tag_lines(f"{pad}-", item, ind))
            elif _block_ok(item):
                out.extend(_block_lines(f"{pad}-", item, ind))
            elif isinstance(item, (dict, list)) and item:
                sub = _lines(item, ind + 2)
                sub[0] = pad + "- " + sub[0][ind + 2:]
                out.extend(sub)
            else:
                out.append(f"{pad}- {_inline(item)}")
    return out


def dump_yaml(data: dict[str, Any], blank_between_top: bool = True) -> str:
    chunks = []
    for k, v in data.items():
        chunks.append("\n".join(_lines({k: v})))
    return ("\n\n" if blank_between_top else "\n").join(chunks) + "\n"


# -------------------------------------------------------------- Helfer ------

_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}


def slug(text: str) -> str:
    for a, b in _UMLAUTS.items():
        text = text.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not s:
        s = "x"
    if s[0].isdigit():
        s = "x_" + s
    return s


_RESERVED_IDS: set[str] | None = None


def _reserved_ids() -> set[str]:
    """Namen von ESPHome-Integrationen: als ID nicht erlaubt (z. B. „display“)."""
    global _RESERVED_IDS
    if _RESERVED_IDS is None:
        r = {"display", "light", "switch", "sensor", "fan", "cover", "climate", "output",
             "time", "wifi", "api", "ota", "logger", "esphome", "mqtt", "web_server",
             "i2c", "spi", "uart", "button", "number", "select", "text", "lock", "remote"}
        try:
            from . import catalog as _cat
            for e in _cat.catalog().get("entries", []):
                r.add(e.get("platform", ""))
                r.add(e.get("domain", ""))
        except Exception:  # noqa: BLE001
            pass
        r.discard("")
        _RESERVED_IDS = r
    return _RESERVED_IDS


def new_api_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def new_password() -> str:
    return _secrets.token_hex(16)


def new_ap_password() -> str:
    return _secrets.token_urlsafe(12)


def new_uid() -> str:
    return _secrets.token_hex(4)


def default_project(board: str = "d1_mini") -> dict[str, Any]:
    b = BOARDS.get(board) or BOARDS["d1_mini"]
    return {
        "name": "neues-geraet",
        "friendly_name": "Neues Gerät",
        "board": b["key"],
        "framework": "esp-idf",
        "log_level": "INFO",
        "use_secrets": True,
        "wifi": {
            "fallback_ap": True,
            "ap_password": new_ap_password(),
            "min_auth_mode": "",
            "static_ip": {"enabled": False, "ip": "", "gateway": "", "subnet": "255.255.255.0", "dns": ""},
        },
        "api": {"enabled": True, "encryption": True, "key": new_api_key()},
        "ota": {"enabled": True, "mode": "encryption", "password": new_password()},
        "web_server": False,
        "time_ha": False,
        "diag": {"wifi_signal": True, "uptime": True, "ip": False, "restart": True},
        "comment": "",
        "extra_yaml": "",
        "substitutions": False,
        "flash_mode": "",
        "early_pin_init": "",
        "debug_interval": "30s",
        "i2c": dict(b["i2c_default"]),
        "components": [],
    }


def new_component(type_key: str, name: str, pins: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "uid": new_uid(),
        "type": type_key,
        "name": name,
        "pins": dict(pins or {}),
        "options": default_options(type_key),
    }


# -------------------------------------------------------------- Kontext -----


def spec_for(c: dict[str, Any]) -> dict[str, Any]:
    """Beschreibung des Bausteins; bei Katalog-Bausteinen aus catalog.json."""
    if c.get("type") == "generic":
        e = catalog_entry(str(c.get("cat") or ""))
        if e:
            return spec_for_entry(e)
        return {"label": "Katalog-Baustein", "platforms": [], "pins": [], "options": []}
    return COMPONENTS[c["type"]]


class Ctx:
    def __init__(self, project: dict[str, Any], stored: dict[str, Any]) -> None:
        self.p = project
        self.stored = stored or {}
        self.board = BOARDS.get(str(project.get("board")))
        self.platform = self.board["platform"] if self.board else "esp8266"
        self.domains: dict[str, list[Any]] = {}
        self.top: dict[str, Any] = {}
        self.hubs: dict[str, dict[str, Any]] = {}
        self.referenced: set[str] = set()
        self.secret_values: dict[str, str] = {}
        self.used: dict[str, str] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.ids: set[str] = set()
        self.logger_off = False
        self.uid_map: dict[str, dict[str, Any]] = {}
        self.use_secrets = bool(project.get("use_secrets", True))
        self.friendly = str(project.get("friendly_name") or "").strip()
        self.name_none_count = 0

    # --- Meldungen ---
    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def err(self, msg: str) -> None:
        if msg not in self.errors:
            self.errors.append(msg)

    # --- IDs ---
    def uid(self, base: str) -> str:
        s = slug(base)
        if s in _reserved_ids():
            s += "_id"
        cand, n = s, 2
        while cand in self.ids:
            cand = f"{s}_{n}"
            n += 1
        self.ids.add(cand)
        return cand

    def cid(self, c: dict[str, Any]) -> str:
        if "_id" not in c:
            c["_id"] = self.uid(str(c.get("id") or c["name"]))
        return c["_id"]

    # --- Domains ---
    def add(self, domain: str, item: Any) -> None:
        self.domains.setdefault(domain, []).append(item)

    # --- Secrets ---
    def secret(self, key: str, value: str) -> Any:
        if self.use_secrets:
            self.secret_values[key] = value
            return Raw(f"!secret {key}")
        return value

    # --- Pins ---
    def pin_cfg(self, pin: dict[str, Any], mode: Any = None, inverted: bool = False) -> Any:
        if pin.get("ext"):
            d_: dict[str, Any] = {pin["ext"]["key"]: self.cid(pin["ext"]["comp"]), "number": pin["number"]}
            m_ = mode or {"out": "OUTPUT", "in": "INPUT"}.get(pin.get("kind"))
            if m_ == "INPUT_PULLUP" and not pin["ext"]["pullup"]:
                m_ = "INPUT"
                self.warn(f"{pin['ext']['comp']['name']} Pin {pin['number']}: Dieser Port-Expander hat keine Pull-ups. Extern einen Widerstand nach 3,3 V anschließen.")
            if m_:
                d_["mode"] = m_
            if inverted:
                d_["inverted"] = True
            return d_
        short = pin.get("short")
        number: Any = Cm(pin["id"], short) if short and short != pin["id"] else pin["id"]
        if mode is None and not inverted:
            return number
        d: dict[str, Any] = {"number": number}
        if mode is not None:
            d["mode"] = mode
        if inverted:
            d["inverted"] = True
        return d

    def _ext_pin(self, pid: str, kind: str, who: str) -> dict[str, Any] | None:
        """Pin eines Port-Expanders (Auswahlwert ``x:<uid>:<nr>``)."""
        parts = pid.split(":")
        comp = self.uid_map.get(parts[1]) if len(parts) == 3 else None
        e = catalog_entry(str(comp.get("cat") or "")) if comp and comp.get("type") == "generic" else None
        if not e or not e.get("expander") or not parts[2].isdigit():
            self.err(f"{who}: Der gewählte Erweiterungs-Pin gehört zu keinem Port-Expander im Projekt.")
            return None
        n = int(parts[2])
        if n >= e["expander"]:
            self.err(f"{who}: „{comp['name']}“ hat nur {e['expander']} Pins (0 bis {e['expander'] - 1}).")
            return None
        if e.get("expander_kinds") and kind not in e["expander_kinds"] and not (kind == "io" and len(e["expander_kinds"]) == 1):
            self.err(f"{who}: „{comp['name']}“ kann nur {'Eingänge' if e['expander_kinds'] == ['in'] else 'Ausgänge'}.")
            return None
        if kind in ("pwm", "adc"):
            self.err(f"{who}: Ein Port-Expander kann kein {'PWM' if kind == 'pwm' else 'Analog'}.")
            return None
        if pid in self.used:
            self.err(f"{comp['name']} Pin {n} ist doppelt belegt: {self.used[pid]} und {who}.")
            return None
        self.used[pid] = who
        return {"id": pid, "ext": {"key": e.get("expander_key") or e["id"], "comp": comp, "pullup": e.get("pullup", True)}, "number": n, "kind": kind}

    def claim_pin(self, pid: Any, kind: str, who: str) -> dict[str, Any] | None:
        if not self.board:
            return None
        if isinstance(pid, str) and pid.startswith("x:"):
            return self._ext_pin(pid, kind, who)
        if not pid:
            self.err(f"{who}: kein Pin gewählt.")
            return None
        pin = self.board["pin_map"].get(str(pid))
        if not pin:
            self.err(f"{who}: Pin {pid} gibt es auf diesem Board nicht.")
            return None
        if pin.get("flash"):
            self.err(f"{who}: {pin['id']} hängt am Flash-Speicher und darf nicht benutzt werden.")
            return None
        if pin.get("adc_only") and kind != "adc":
            self.err(f"{who}: {pin['id']} ist nur ein Analog-Eingang.")
            return None
        if kind == "adc" and not pin.get("adc"):
            self.err(f"{who}: {pin['id']} ist kein Analog-Pin.")
            return None
        if kind in ("out", "pwm", "io") and pin.get("input_only"):
            self.err(f"{who}: {pin['id']} kann nur lesen und ist als Ausgang nicht möglich.")
            return None
        if kind == "pwm" and pin.get("no_pwm"):
            self.err(f"{who}: {pin['id']} unterstützt kein PWM.")
            return None
        if pid in self.used:
            self.err(f"{pin['id']} ist doppelt belegt: {self.used[pid]} und {who}.")
            return None
        self.used[pid] = who
        if pin.get("strapping"):
            self.warn(f"{who}: {pin['id']} ist ein Boot-Pin. {pin['strapping']}")
        if pin.get("boot_high") and kind in ("out", "pwm", "io"):
            self.warn(f"{who}: {pin['id']} liegt beim Start kurz auf HIGH. Ein Relais oder Licht kann dabei einmal schalten.")
        if pin.get("uart"):
            self.logger_off = True
            self.warn(f"{who}: {pin['id']} gehört zur UART. Der Logger über UART wird abgeschaltet, "
                      "Logs gibt es dann nur noch über WLAN/API.")
        if pin.get("usb"):
            self.warn(f"{who}: {pin['id']} wird für USB gebraucht. Das Flashen/Loggen über USB kann dadurch ausfallen.")
        if pin.get("psram"):
            self.warn(f"{who}: {pin['id']} ist je nach Modul vom PSRAM belegt. {pin.get('note', '')}".strip())
        if kind == "adc" and pin.get("adc") == "adc2" and self.platform == "esp32":
            self.warn(f"{who}: {pin['id']} liegt am ADC2, der parallel zu WLAN unzuverlässig misst. ADC1-Pins sind besser.")
        return pin

    def claim(self, c: dict[str, Any], key: str, kind: str) -> dict[str, Any] | None:
        spec = next(p for p in spec_for(c)["pins"] if p["key"] == key)
        who = f"„{c['name']}“ ({spec['label']})"
        return self.claim_pin((c.get("pins") or {}).get(key), kind, who)


# ------------------------------------------------------------- Optionen ----


def _interval(ctx: Ctx, c: dict[str, Any], key: str = "update_interval", default: str = "60s") -> str:
    v = str((c["options"].get(key) or default)).strip()
    if not INTERVAL_RE.match(v):
        ctx.err(f"„{c['name']}“: ungültiges Intervall „{v}“ (erlaubt z. B. 500ms, 10s, 5min, 1h).")
        return default
    return v


def _freq(ctx: Ctx, c: dict[str, Any]) -> str | None:
    raw = c["options"].get("frequency")
    if raw in (None, ""):
        return None
    try:
        f = int(float(raw))
        if f < 1:
            raise ValueError
    except (TypeError, ValueError):
        ctx.err(f"„{c['name']}“: ungültige PWM-Frequenz „{raw}“.")
        return None
    return f"{f}Hz"


def _opt(c: dict[str, Any], key: str) -> Any:
    return c["options"].get(key)


# ------------------------------------------------------------- Emitter -----


PWM_PLATFORM = {"esp32": "ledc", "esp8266": "esp8266_pwm", "rp2": "rp2040_pwm", "bk72xx": "libretiny_pwm",
                "rtl87xx": "libretiny_pwm", "ln882x": "libretiny_pwm"}


def _pwm_output(ctx: Ctx, c: dict[str, Any], key: str, kind_label: str = "") -> str | None:
    pin = ctx.claim(c, key, "pwm")
    if pin is None:
        return None
    oid = ctx.uid(f"out_{c['name']}_{key}")
    plat = PWM_PLATFORM.get(ctx.platform, "ledc")
    out: dict[str, Any] = {"platform": plat, "id": oid, "pin": ctx.pin_cfg(pin, inverted=bool(_opt(c, "inverted")))}
    f = _freq(ctx, c)
    if f:
        out["frequency"] = f
    ctx.add("output", out)
    return oid


def e_switch(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "out")
    d: dict[str, Any] = {"platform": "gpio", "name": c["name"], "id": ctx.cid(c)}
    if pin:
        d["pin"] = ctx.pin_cfg(pin, inverted=bool(_opt(c, "inverted")))
    rm = _opt(c, "restore_mode")
    if rm and rm != "RESTORE_DEFAULT_OFF":
        d["restore_mode"] = rm
    try:
        pulse = int(float(_opt(c, "pulse_ms") or 0))
    except (TypeError, ValueError):
        pulse = 0
        ctx.err(f"„{c['name']}“: ungültige Impulsdauer.")
    if pulse > 0:
        d["on_turn_on"] = [{"delay": f"{pulse}ms"}, {"switch.turn_off": ctx.cid(c)}]
    ctx.add("switch", d)


def e_status_led(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "out")
    if pin:
        ctx.top["status_led"] = {"pin": ctx.pin_cfg(pin, inverted=bool(_opt(c, "inverted")))}


def e_light_binary(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "out")
    oid = ctx.uid(f"out_{c['name']}")
    if pin:
        ctx.add("output", {"platform": "gpio", "id": oid,
                           "pin": ctx.pin_cfg(pin, inverted=bool(_opt(c, "inverted")))})
    ctx.add("light", {"platform": "binary", "name": _light_name(ctx, c), "id": ctx.cid(c), "output": oid})


def e_light_pwm(ctx: Ctx, c: dict[str, Any]) -> None:
    oid = _pwm_output(ctx, c, "pin")
    d: dict[str, Any] = {"platform": "monochromatic", "name": _light_name(ctx, c), "id": ctx.cid(c),
                         "output": oid or "FEHLT"}
    fx = _effects(c, False)
    if fx:
        d["effects"] = fx
    ctx.add("light", d)


def _effects(c: dict[str, Any], color: bool) -> list[dict[str, Any]]:
    fx: list[dict[str, Any]] = []
    if _opt(c, "fx_pulse"):
        fx.append({"pulse": {"name": "Schnelles Pulsieren", "transition_length": "0.5s", "update_interval": "0.5s"}})
        fx.append({"pulse": {"name": "Langsames Pulsieren", "transition_length": "1s", "update_interval": "2s"}})
    if _opt(c, "fx_random"):
        fx.append({"random": {"name": "Langsam zufällig", "transition_length": "30s", "update_interval": "30s"}})
        fx.append({"random": {"name": "Schnell zufällig", "transition_length": "4s", "update_interval": "5s"}})
    if _opt(c, "fx_strobe"):
        on: dict[str, Any] = {"state": True, "brightness": "100%"}
        if color:
            on.update({"red": "100%", "green": "90%", "blue": "0%"})
        on["duration"] = "500ms"
        fx.append({"strobe": {"name": "Blitzen", "colors": [on, {"state": False, "duration": "250ms"}]}})
    return fx


def _light_name(ctx: Ctx, c: dict[str, Any]) -> Any:
    if _opt(c, "name_none"):
        if not ctx.friendly:
            ctx.err(f"„{c['name']}“: „Name = Gerätename“ braucht einen Anzeigenamen im Bereich „Gerät“.")
        ctx.name_none_count += 1
        if ctx.name_none_count > 1:
            ctx.err("„Name = Gerätename“ darf nur bei einer Entität pro Gerät gewählt werden.")
        return Raw("None")
    return c["name"]


def _color_light(ctx: Ctx, c: dict[str, Any], platform: str, channels: list[tuple[str, str]]) -> None:
    d: dict[str, Any] = {"platform": platform, "name": _light_name(ctx, c), "id": ctx.cid(c)}
    for pin_key, conf_key in channels:
        d[conf_key] = _pwm_output(ctx, c, pin_key) or "FEHLT"
    if platform == "rgbww":
        for k, conf in (("cold_temp", "cold_white_color_temperature"), ("warm_temp", "warm_white_color_temperature")):
            try:
                d[conf] = f"{int(float(_opt(c, k)))} K"
            except (TypeError, ValueError):
                ctx.err(f"„{c['name']}“: ungültige Farbtemperatur.")
    if platform in ("rgbw", "rgbww") and _opt(c, "color_interlock"):
        d["color_interlock"] = True
    fx = _effects(c, True)
    if fx:
        d["effects"] = fx
    ctx.add("light", d)


def e_light_rgb(ctx, c):
    _color_light(ctx, c, "rgb", [("red", "red"), ("green", "green"), ("blue", "blue")])


def e_light_rgbw(ctx, c):
    _color_light(ctx, c, "rgbw", [("red", "red"), ("green", "green"), ("blue", "blue"), ("white", "white")])


def e_light_rgbww(ctx, c):
    _color_light(ctx, c, "rgbww", [("red", "red"), ("green", "green"), ("blue", "blue"),
                                    ("cold_white", "cold_white"), ("warm_white", "warm_white")])


def e_light_strip(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "out")
    d: dict[str, Any] = {"platform": "esp32_rmt_led_strip", "name": c["name"], "id": ctx.cid(c)}
    if pin:
        d["pin"] = ctx.pin_cfg(pin)
    try:
        n = int(float(_opt(c, "num_leds")))
        if n < 1:
            raise ValueError
    except (TypeError, ValueError):
        ctx.err(f"„{c['name']}“: ungültige LED-Anzahl.")
        n = 1
    d["num_leds"] = n
    d["channel_colors"] = str(_opt(c, "rgb_order") or "GRB")
    d["chipset"] = str(_opt(c, "chipset") or "WS2812")
    ctx.add("light", d)


def e_binary_sensor(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "in")
    mode = str(_opt(c, "mode") or "INPUT_PULLUP")
    d: dict[str, Any] = {"platform": "gpio", "name": c["name"]}
    if pin:
        if mode == "INPUT_PULLUP" and pin.get("no_pullup"):
            ctx.err(f"„{c['name']}“: {pin['id']} hat keinen internen Pull-up. Modus INPUT wählen und extern "
                    "mit einem Widerstand beschalten.")
        if mode == "INPUT_PULLDOWN" and ctx.platform == "esp8266":
            ctx.err(f"„{c['name']}“: INPUT_PULLDOWN gibt es nur beim ESP32.")
        d["pin"] = ctx.pin_cfg(pin, mode=mode, inverted=bool(_opt(c, "inverted")))
    dc = _opt(c, "device_class")
    if dc and dc != "none":
        d["device_class"] = dc
    try:
        db = int(float(_opt(c, "debounce_ms") or 0))
    except (TypeError, ValueError):
        db = 0
        ctx.err(f"„{c['name']}“: ungültige Entprellzeit.")
    if db > 0:
        d["filters"] = [{"delayed_on_off": f"{db}ms"}]
    target = ctx.uid_map.get(str(_opt(c, "toggle_target") or ""))
    if _opt(c, "toggle_target") and not target:
        ctx.err(f"„{c['name']}“: das Ziel zum Umschalten gibt es nicht mehr.")
    if target:
        domain = "switch" if target["type"] == "switch" else "light"
        d["on_press"] = [{f"{domain}.toggle": ctx.cid(target)}]
    ctx.add("binary_sensor", d)


def e_ir_receiver(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "in")
    d: dict[str, Any] = {}
    if pin:
        mode: dict[str, bool] = {"input": True}
        if not pin.get("no_pullup"):
            mode["pullup"] = True
        d["pin"] = ctx.pin_cfg(pin, mode=mode, inverted=bool(_opt(c, "inverted")))
    if _opt(c, "dump") in ("all",):
        d["dump"] = "all"
    ctx.top["remote_receiver"] = d


def e_ir_transmitter(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "out")
    d: dict[str, Any] = {}
    if pin:
        d["pin"] = ctx.pin_cfg(pin)
    try:
        d["carrier_duty_percent"] = f"{int(float(_opt(c, 'duty') or 50))}%"
    except (TypeError, ValueError):
        ctx.err(f"„{c['name']}“: ungültiges Tastverhältnis.")
    if ctx.platform == "esp32":
        d["non_blocking"] = True
    ctx.top["remote_transmitter"] = d


def e_dht(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "io")
    d: dict[str, Any] = {"platform": "dht"}
    if pin:
        d["pin"] = ctx.pin_cfg(pin)
    d["model"] = str(_opt(c, "model") or "DHT22")
    d["temperature"] = {"name": f"{c['name']} Temperatur"}
    d["humidity"] = {"name": f"{c['name']} Luftfeuchte"}
    d["update_interval"] = _interval(ctx, c)
    ctx.add("sensor", d)


def e_dallas(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "io")
    bus = ctx.uid(f"onewire_{c['name']}")
    bus_cfg: dict[str, Any] = {"platform": "gpio"}
    if pin:
        bus_cfg["pin"] = ctx.pin_cfg(pin)
    bus_cfg["id"] = bus
    ctx.add("one_wire", bus_cfg)
    d: dict[str, Any] = {"platform": "dallas_temp", "one_wire_id": bus, "name": c["name"]}
    addr = str(_opt(c, "address") or "").strip()
    if addr:
        if HEX_RE.match(addr):
            d["address"] = Raw(addr)
        else:
            ctx.err(f"„{c['name']}“: Adresse „{addr}“ ist keine Hex-Zahl wie 0x1c0000031edd2a28.")
    try:
        res = int(float(_opt(c, "resolution") or 12))
        if res not in (9, 10, 11, 12):
            raise ValueError
    except (TypeError, ValueError):
        ctx.err(f"„{c['name']}“: Auflösung muss 9, 10, 11 oder 12 Bit sein.")
        res = 12
    if res != 12:
        d["resolution"] = res
    d["update_interval"] = _interval(ctx, c)
    filters: list[dict[str, Any]] = []
    throttle = str(_opt(c, "throttle") or "").strip()
    if throttle:
        if INTERVAL_RE.match(throttle):
            filters.append({"throttle": throttle})
        else:
            ctx.err(f"„{c['name']}“: ungültige Mindestpause „{throttle}“ (z. B. 30s).")
    delta = str(_opt(c, "delta") or "").strip().replace(",", ".")
    if delta:
        try:
            filters.append({"delta": float(delta)})
        except ValueError:
            ctx.err(f"„{c['name']}“: Änderungsschwelle „{delta}“ ist keine Zahl.")
    if len(filters) == 2:
        d["filters"] = [{"or": filters}]
    elif filters:
        d["filters"] = filters
    ctx.add("sensor", d)


def e_adc(ctx: Ctx, c: dict[str, Any]) -> None:
    pin = ctx.claim(c, "pin", "adc")
    d: dict[str, Any] = {"platform": "adc"}
    if pin:
        d["pin"] = pin["id"]
    d["name"] = c["name"]
    if ctx.platform == "esp32" and _opt(c, "attenuation"):
        d["attenuation"] = str(_opt(c, "attenuation"))
    unit = str(_opt(c, "unit") or "").strip()
    if unit:
        d["unit_of_measurement"] = unit
    mult = str(_opt(c, "multiply") or "").strip().replace(",", ".")
    if mult:
        try:
            m = float(mult)
            d["filters"] = [{"multiply": m}]
        except ValueError:
            ctx.err(f"„{c['name']}“: Faktor „{mult}“ ist keine Zahl.")
    d["update_interval"] = _interval(ctx, c)
    ctx.add("sensor", d)


def e_ultrasonic(ctx: Ctx, c: dict[str, Any]) -> None:
    trig = ctx.claim(c, "trigger", "out")
    echo = ctx.claim(c, "echo", "in")
    d: dict[str, Any] = {"platform": "ultrasonic"}
    if trig:
        d["trigger_pin"] = ctx.pin_cfg(trig)
    if echo:
        d["echo_pin"] = ctx.pin_cfg(echo)
    d["name"] = c["name"]
    t = str(_opt(c, "timeout") or "2m").strip()
    if re.match(r"^\d+(\.\d+)?(m|cm|mm)$", t):
        d["timeout"] = t
    else:
        ctx.err(f"„{c['name']}“: ungültige Entfernung „{t}“ (z. B. 2m oder 50cm).")
    d["update_interval"] = _interval(ctx, c, default="10s")
    ctx.add("sensor", d)
    ctx.warn(f"„{c['name']}“: Der HC-SR04 liefert am Echo-Pin 5 V. Spannungsteiler verwenden oder die "
             "3,3-V-Variante (HC-SR04P) nehmen.")


def _i2c_sensor(ctx: Ctx, c: dict[str, Any], d: dict[str, Any]) -> None:
    ctx.add("sensor", d)


def e_bme280(ctx: Ctx, c: dict[str, Any]) -> None:
    _i2c_sensor(ctx, c, {
        "platform": "bme280_i2c",
        "temperature": {"name": f"{c['name']} Temperatur"},
        "pressure": {"name": f"{c['name']} Druck"},
        "humidity": {"name": f"{c['name']} Luftfeuchte"},
        "address": Raw(str(_opt(c, "address") or "0x76")),
        "update_interval": _interval(ctx, c),
    })


def e_bmp280(ctx: Ctx, c: dict[str, Any]) -> None:
    _i2c_sensor(ctx, c, {
        "platform": "bmp280_i2c",
        "temperature": {"name": f"{c['name']} Temperatur"},
        "pressure": {"name": f"{c['name']} Druck"},
        "address": Raw(str(_opt(c, "address") or "0x76")),
        "update_interval": _interval(ctx, c),
    })


def e_sht3xd(ctx: Ctx, c: dict[str, Any]) -> None:
    _i2c_sensor(ctx, c, {
        "platform": "sht3xd",
        "temperature": {"name": f"{c['name']} Temperatur"},
        "humidity": {"name": f"{c['name']} Luftfeuchte"},
        "address": Raw(str(_opt(c, "address") or "0x44")),
        "update_interval": _interval(ctx, c),
    })


def e_aht10(ctx: Ctx, c: dict[str, Any]) -> None:
    _i2c_sensor(ctx, c, {
        "platform": "aht10",
        "variant": str(_opt(c, "variant") or "AHT20"),
        "temperature": {"name": f"{c['name']} Temperatur"},
        "humidity": {"name": f"{c['name']} Luftfeuchte"},
        "update_interval": _interval(ctx, c),
    })


def e_bh1750(ctx: Ctx, c: dict[str, Any]) -> None:
    _i2c_sensor(ctx, c, {
        "platform": "bh1750",
        "name": c["name"],
        "address": Raw(str(_opt(c, "address") or "0x23")),
        "update_interval": _interval(ctx, c),
    })



# ------------------------------------------------------ Katalog-Bausteine ----

_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?\d+\.\d+$")
HUB_ORDER = ["uart", "spi"]
DOMAIN_DE = {"display": "Display", "touchscreen": "Touchscreen", "time": "Uhrzeit", "one_wire": "1-Wire-Bus"}


def _auto(v: Any) -> Any:
    """Eingabe als YAML-Wert: Zahlen als Zahlen, Hex roh, true/false als Wahrheitswert."""
    if isinstance(v, (bool, int, float)):
        return v
    t = str(v).strip()
    if HEX_RE.match(t):
        return Raw(t)
    if _INT_RE.match(t):
        return int(t)
    if _FLOAT_RE.match(t):
        return float(t)
    if t.lower() in ("true", "false"):
        return t.lower() == "true"
    return t


def _same(a: Any, b: Any) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


PRIORITY_SUBS = ["temperature", "humidity", "pressure", "co2", "voltage", "current", "power", "energy", "pm_2_5",
                 "illuminance", "distance", "moisture"]


def default_subs(e: dict[str, Any]) -> list[str]:
    """Welche Messwerte ein neuer Katalog-Baustein zuerst einschaltet."""
    keys = [s["key"] for s in e.get("subs", [])]
    on = [s["key"] for s in e.get("subs", []) if s.get("required")]
    for k in PRIORITY_SUBS:
        if k in keys and k not in on:
            on.append(k)
    if not on and keys:
        on.append(keys[0])
    return on


def e_generic(ctx: Ctx, c: dict[str, Any]) -> None:
    e = catalog_entry(str(c.get("cat") or ""))
    if not e:
        return
    o = c.get("options") or {}
    who = f"„{c['name']}“"
    is_hub = e["domain"] == "hub"
    d: dict[str, Any] = {} if is_hub else {"platform": e["platform"]}
    if is_hub or c.get("uid") in ctx.referenced or (not e.get("self_entity") and not e.get("subs") and not e.get("no_id")):
        d["id"] = ctx.cid(c)
    if e.get("self_entity"):
        d["name"] = c["name"]
    # Hub-Verweis (z. B. ld2410_id)
    if e.get("hub"):
        ref = ctx.uid_map.get(str(o.get("hub") or ""))
        if not ref or ref.get("type") != "generic" or ref.get("cat") != e["hub"]:
            ctx.err(f"{who}: Bitte den zugehörigen Baustein „{e['hub']}“ auswählen (zuerst im Katalog hinzufügen).")
        else:
            d[e.get("hub_key") or f"{e['hub']}_id"] = Raw(ctx.cid(ref))
    for nid in e.get("needs_cat") or []:
        if not any(x.get("type") == "generic" and x.get("cat") == nid for x in ctx.p.get("components") or []):
            ctx.err(f"{who}: Braucht zusätzlich den Katalog-Baustein „{nid}“.")
    for dom in e.get("needs_dom") or []:
        if not any(catalog_entry(str(x.get("cat") or "")) and catalog_entry(str(x.get("cat")))["domain"] == dom
                   for x in ctx.p.get("components") or [] if x.get("type") == "generic"):
            ctx.err(f"{who}: Braucht zusätzlich einen Baustein der Art „{DOMAIN_DE.get(dom, dom)}“ (Katalog).")
    for need in e.get("needs") or []:
        if need == "ir_transmitter" and not any(x.get("type") == "ir_transmitter" for x in ctx.p.get("components") or []):
            ctx.err(f"{who}: Braucht zusätzlich den Baustein „IR-Sender“ (Komponenten hinzufügen).")
        if need == "time" and not ctx.p.get("time_ha"):
            ctx.err(f"{who}: Braucht die Uhrzeit von Home Assistant (WLAN & Secrets → „Uhrzeit von Home Assistant“).")
    # Verweise auf Ausgänge (z. B. Lüfter, Schloss)
    for r in e.get("refs", []):
        target = ctx.uid_map.get(str(o.get("ref_" + r["key"]) or ""))
        if not target:
            if r["required"]:
                ctx.err(f"{who}: „{r['label']}“ fehlt. Zuerst einen Ausgang im Katalog hinzufügen und hier wählen.")
            continue
        te = catalog_entry(str(target.get("cat") or "")) if target.get("type") == "generic" else None
        if not te or r["cls"] not in te.get("provides", []):
            ctx.err(f"{who}: „{r['label']}“ zeigt auf einen Baustein, der nicht passt.")
            continue
        d[r["key"]] = Raw(ctx.cid(target))
    # Bus
    if e.get("bus") == "uart":
        rx = (c.get("pins") or {}).get("_rx")
        tx = (c.get("pins") or {}).get("_tx")
        u: dict[str, Any] = {"id": ctx.uid(f"uart_{c['name']}")}
        if tx:
            t = ctx.claim_pin(tx, "out", f"{who} (TX)")
            if t:
                u["tx_pin"] = ctx.pin_cfg(t)
        r = ctx.claim_pin(rx, "in", f"{who} (RX)")
        if r:
            u["rx_pin"] = ctx.pin_cfg(r)
        for k_, v_ in (e.get("uart") or {}).items():  # feste UART-Vorgaben des Bauteils (Parität, Stop-Bits …)
            u[k_] = v_
        baud = str(o.get("baud") or "").strip()
        if not _INT_RE.match(baud):
            ctx.err(f"{who}: Baudrate fehlt (Zahl, z. B. 9600).")
        else:
            u["baud_rate"] = int(baud)
        ctx.top.setdefault("uart", []).append(u)
        d["uart_id"] = Raw(u["id"])
    # Pins
    for ps in e["pins"]:
        val = (c.get("pins") or {}).get(ps["key"])
        if not val and not ps["required"]:
            continue
        pin = ctx.claim(c, ps["key"], ps["kind"])
        if pin:
            d[ps["key"]] = ctx.pin_cfg(pin)
    # Felder
    for f in e["fields"]:
        raw = o.get("f_" + f["key"])
        if f["type"] == "bool":
            if raw is None or raw == "":
                continue
            val = bool(raw)
            if f["required"] or val != (str(f["default"]).lower() == "true"):
                d[f["key"]] = val
            continue
        if raw is None or str(raw).strip() == "":
            if f["required"]:
                ctx.err(f"{who}: „{f['label']}“ muss ausgefüllt werden.")
            continue
        if not f["required"] and f["default"] != "" and _same(raw, f["default"]):
            continue
        d[f["key"]] = str(raw).strip() if f.get("as") == "str" else _auto(raw)
    # Messwerte
    if e.get("subs"):
        on = [s for s in e["subs"] if s.get("required") or o.get("s_" + s["key"])]
        if not on and not e.get("self_entity"):
            ctx.err(f"{who}: Mindestens ein Messwert muss eingeschaltet sein.")
        for s in on:
            sub: dict[str, Any] = {"name": f"{c['name']} {s['label']}"}
            d[s["key"]] = sub
    # Intervall
    if e.get("has_interval"):
        iv = str(o.get("interval") or "").strip()
        if iv:
            if not INTERVAL_RE.match(iv):
                ctx.err(f"{who}: Aktualisierung „{iv}“ ist ungültig (z. B. 30s oder 5min).")
            elif not _same(iv, e.get("interval_default") or ""):
                d["update_interval"] = iv
    for k_, v_ in (e.get("force") or {}).items():  # Pflichtvorgaben des Bauteils (z. B. optimistic)
        d.setdefault(k_, v_)
    # Zusatz-YAML des Bausteins
    extra = str(o.get("extra") or "").strip()
    if extra:
        try:
            ex = load_text(extra)
        except ValueError as exc:
            ctx.err(f"{who}: Zusatz-YAML: {exc}")
        else:
            if isinstance(ex, dict):
                d.update(ex)
            else:
                ctx.err(f"{who}: Zusatz-YAML muss Schlüssel enthalten.")
    if is_hub:
        if e["id"] in ctx.hubs:
            ctx.err(f"{who}: „{e['id']}“ kann nur einmal pro Gerät vorkommen.")
        else:
            ctx.hubs[e["id"]] = d
        return
    ctx.add(e["domain"], d)


def _profi(ctx: Ctx, c: dict[str, Any], before: dict[str, int]) -> None:
    """Profi-Einstellungen (Name, Icon, Einheit, Filter …) in die gerade erzeugten Entitäten schreiben."""
    ent = (c.get("options") or {}).get("ent")
    if not isinstance(ent, dict) or not ent:
        return
    who = f"„{c['name']}“"
    if c["type"] == "generic":
        e = catalog_entry(str(c.get("cat") or ""))
        if not e or e["domain"] == "hub":
            return
        domain = e["domain"]
        subdom = {s["key"]: s["domain"] for s in e.get("subs", [])}
    else:
        meta = ENT_META.get(c["type"])
        if not meta:
            return
        domain, subdom = meta["domain"], {t["key"]: meta["domain"] for t in meta["targets"] if t["key"]}
    items = ctx.domains.get(domain, [])[before.get(domain, 0):]
    item = next((i for i in items if isinstance(i, dict)), None)
    if item is None:
        return
    for target, cfg in ent.items():
        if target == "":
            apply_entity(item, domain, cfg, who, ctx.errors)
        elif isinstance(item.get(target), dict) and target in subdom:
            apply_entity(item[target], subdom[target], cfg, f"{who} ({target})", ctx.errors)


EMITTERS = {
    "generic": e_generic,
    "switch": e_switch,
    "status_led": e_status_led,
    "light_binary": e_light_binary,
    "light_pwm": e_light_pwm,
    "light_rgb": e_light_rgb,
    "light_rgbw": e_light_rgbw,
    "light_rgbww": e_light_rgbww,
    "light_strip": e_light_strip,
    "binary_sensor": e_binary_sensor,
    "ir_receiver": e_ir_receiver,
    "ir_transmitter": e_ir_transmitter,
    "dht": e_dht,
    "dallas": e_dallas,
    "adc": e_adc,
    "ultrasonic": e_ultrasonic,
    "bme280": e_bme280,
    "bmp280": e_bmp280,
    "sht3xd": e_sht3xd,
    "aht10": e_aht10,
    "bh1750": e_bh1750,
}

DOMAIN_ORDER = ["output", "one_wire", "light", "fan", "cover", "climate", "valve", "lock", "switch", "number", "select",
                "binary_sensor", "sensor", "text_sensor", "button"]
TOP_ORDER_AFTER_I2C = ["spi", "uart", "status_led", "remote_transmitter", "remote_receiver"]


# ------------------------------------------------------------ Hauptfunktion --


def _check_ip(ctx: Ctx, label: str, value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        ctx.err(f"Statische IP: {label} „{value}“ ist keine gültige IPv4-Adresse.")
        return False


WEB_DEFAULTS = {"version": "2", "port": 80, "local": False, "include_internal": False, "log": True,
                "compression": "gzip", "auth": False, "auth_user": "", "auth_password": "", "auth_type": "basic",
                "ota_web": False, "css_url": "", "js_url": "", "private_network": False, "allowed_origins": ""}


def default_web() -> dict[str, Any]:
    return dict(WEB_DEFAULTS)


def _web_server(ctx: Ctx, p: dict[str, Any], dev_slug: str, out: dict[str, Any]) -> None:
    """Webserver (Version 1, 2 oder 3) mit Zugangsschutz und allen gängigen Optionen."""
    if not p.get("web_server"):
        return
    w = p.get("web")
    if not isinstance(w, dict):  # alte Projekte: Port 80, kein OTA
        out["web_server"] = {"port": 80, "ota": False}
        return
    w = {**WEB_DEFAULTS, **w}
    ws: dict[str, Any] = {}
    try:
        port = int(float(w["port"]))
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        ctx.err("Webserver: ungültiger Port.")
        port = 80
    ws["port"] = port
    version = str(w["version"])
    if version not in ("1", "2", "3"):
        ctx.err("Webserver: Version muss 1, 2 oder 3 sein.")
        version = "2"
    if version != "2":
        ws["version"] = int(version)
    if version == "1":
        ctx.warn("Webserver Version 1 ist veraltet und wird in ESPHome 2027.1 entfernt. Version 2 oder 3 nehmen.")
    if w["local"]:
        ws["local"] = True
    if w["include_internal"]:
        ws["include_internal"] = True
    if not w["log"]:
        ws["log"] = False
    if str(w["compression"]) == "br":
        ws["compression"] = "br"
    origins = [o.strip() for o in re.split(r"[,\s]+", str(w.get("allowed_origins") or "")) if o.strip()]
    if origins:
        ws["allowed_origins"] = origins
    if w["private_network"]:
        ws["enable_private_network_access"] = True
        if not origins:
            ctx.err("Webserver: Für den Zugriff aus dem privaten Netz müssen erlaubte Herkunftsadressen (allowed_origins) angegeben sein.")
    for key, conf in (("css_url", "css_url"), ("js_url", "js_url")):
        val = str(w.get(key) or "").strip()
        if val:
            if version == "1":
                ctx.warn(f"Webserver: {conf} gibt es erst ab Version 2.")
            ws[conf] = val
    if w["auth"]:
        user, pw = str(w["auth_user"] or "").strip(), str(w["auth_password"] or "")
        if not user or not pw:
            ctx.err("Webserver: Benutzername und Passwort für den Zugangsschutz fehlen.")
        auth: dict[str, Any] = {"username": ctx.secret(f"{dev_slug}_web_user", user),
                                "password": ctx.secret(f"{dev_slug}_web_password", pw)}
        if str(w["auth_type"]) == "digest":
            auth["type"] = "digest"
        ws["auth"] = auth
    if not w["ota_web"]:
        ws["ota"] = False
    else:
        ota = out.setdefault("ota", [])
        if isinstance(ota, list):
            ota.append({"platform": "web_server"})
        if not w["auth"]:
            ctx.warn("Webserver-OTA ohne Zugangsschutz: Jeder im WLAN kann Firmware hochladen.")
        ctx.warn("Webserver-OTA ist nicht verschlüsselt (die OTA-Verschlüsselung gilt nur für ESPHome-OTA).")
    out["web_server"] = ws


def _merge_extra(ctx: Ctx, base: dict[str, Any], extra: dict[str, Any], path: str) -> None:
    """Mischt das Zusatz-YAML in den erzeugten Aufbau: Abschnitte werden ergänzt, Listen angehängt.
    Was das Studio schon selbst setzt, bleibt unverändert (mit Hinweis)."""
    for key, val in extra.items():
        here = f"{path}{key}"
        if key not in base:
            base[key] = val
            continue
        cur = base[key]
        if isinstance(cur, dict) and isinstance(val, dict):
            _merge_extra(ctx, cur, val, here + ".")
        elif isinstance(cur, list) and isinstance(val, list):
            cur.extend(val)
        elif val is None or (isinstance(val, (dict, list)) and not val):
            continue
        elif isinstance(cur, (dict, list)) and not cur:
            base[key] = val
        elif str(cur) == str(val):
            continue
        else:
            ctx.warn(f"Zusatz-YAML: „{here}“ setzt das Studio selbst. Der Wert aus dem Zusatz-YAML wird ignoriert.")


def _generate(project: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    ctx = Ctx(project, stored)
    p = project
    name = str(p.get("name") or "").strip()
    if not ctx.board:
        ctx.err("Bitte ein Board auswählen.")
        return {"yaml": "", "secrets": "", "warnings": ctx.warnings, "errors": ctx.errors, "ok": False}
    board = ctx.board

    # --- Gerät ---
    if not DEVICE_NAME_RE.match(name):
        ctx.err("Gerätename: nur Kleinbuchstaben, Ziffern und Bindestriche, höchstens 31 Zeichen, "
                "kein Bindestrich am Anfang oder Ende (z. B. wohnzimmer-licht).")
    friendly = str(p.get("friendly_name") or "").strip()
    dev_slug = (name or "geraet").replace("-", "_")

    comps = [c for c in (p.get("components") or []) if isinstance(c, dict) and c.get("type") in COMPONENTS]
    for c in comps:
        c.setdefault("pins", {})
        c.setdefault("options", {})
        c["options"] = {**default_options(c["type"]), **(c["options"] or {})}
        if c["type"] == "generic" and not catalog_entry(str(c.get("cat") or "")):
            ctx.err(f"„{c.get('name') or '?'}“: Baustein „{c.get('cat')}“ ist nicht im Katalog.")
        c["name"] = str(c.get("name") or "").strip()
        ctx.uid_map[str(c.get("uid") or "")] = c

    for c in comps:
        o_ = c["options"]
        if c["type"] == "generic":
            for k_, v_ in o_.items():
                if (k_ == "hub" or k_.startswith("ref_")) and v_:
                    ctx.referenced.add(str(v_))
        for v_ in (c.get("pins") or {}).values():
            if isinstance(v_, str) and v_.startswith("x:") and v_.count(":") == 2:
                ctx.referenced.add(v_.split(":")[1])

    # --- Namen / Plattform prüfen ---
    seen: dict[str, str] = {}
    singletons: set[str] = set()
    for c in comps:
        spec = spec_for(c)
        if not c["name"]:
            ctx.err(f"Eine Komponente vom Typ „{spec['label']}“ hat keinen Namen.")
            c["name"] = spec["label"]
        low = c["name"].lower()
        if low in seen:
            ctx.err(f"Der Name „{c['name']}“ kommt doppelt vor.")
        seen[low] = c["name"]
        if board["platform"] not in spec["platforms"]:
            ctx.err(f"„{c['name']}“: „{spec['label']}“ gibt es bei {PLATFORM_LABEL.get(board['platform'], board['platform'])} "
                    "nicht (nur: " + ", ".join(PLATFORM_LABEL.get(x, x) for x in spec["platforms"]) + ").")
        if board["chip"] in spec.get("not_chips", ()):
            ctx.err(f"„{c['name']}“: „{spec['label']}“ geht beim {board['group']} nicht (keine RMT-Hardware).")
        if spec.get("singleton"):
            if c["type"] in singletons:
                ctx.err(f"„{spec['label']}“ kann nur einmal pro Gerät vorkommen.")
            singletons.add(c["type"])

    # --- I²C ---
    if any(spec_for(c).get("needs_i2c") for c in comps):
        i2c = p.get("i2c") or {}
        sda = ctx.claim_pin(i2c.get("sda"), "io", "I²C SDA")
        scl = ctx.claim_pin(i2c.get("scl"), "io", "I²C SCL")
        for pin_, who_ in ((sda, "SDA"), (scl, "SCL")):
            if pin_ and pin_.get("no_i2c"):
                ctx.warn(f"I²C {who_}: {pin_['id']} unterstützt kein I²C zuverlässig. Besser D1/D2 (GPIO5/GPIO4) nehmen.")
        if sda and scl:
            ctx.top["i2c"] = {"sda": ctx.pin_cfg(sda), "scl": ctx.pin_cfg(scl), "scan": True}

    # --- SPI ---
    if any(spec_for(c).get("needs_spi") for c in comps):
        spi_p = {**(board.get("spi_default") or {}), **{k: v for k, v in (p.get("spi") or {}).items() if v}}
        clk = ctx.claim_pin(spi_p.get("clk"), "io", "SPI CLK")
        mosi = ctx.claim_pin(spi_p.get("mosi"), "io", "SPI MOSI") if spi_p.get("mosi") else None
        miso = ctx.claim_pin(spi_p.get("miso"), "in", "SPI MISO") if spi_p.get("miso") else None
        if clk:
            spi_out: dict[str, Any] = {"clk_pin": ctx.pin_cfg(clk)}
            if mosi:
                spi_out["mosi_pin"] = ctx.pin_cfg(mosi)
            if miso:
                spi_out["miso_pin"] = ctx.pin_cfg(miso)
            ctx.top["spi"] = spi_out

    # --- Komponenten ---
    for c in comps:
        if board["platform"] not in spec_for(c)["platforms"]:
            continue
        before = {k: len(v) for k, v in ctx.domains.items()}
        try:
            EMITTERS[c["type"]](ctx, c)
            _profi(ctx, c, before)
        except Exception as exc:  # noqa: BLE001 - Eingaben sind frei, Generator darf nie abstürzen
            ctx.err(f"„{c['name']}“: interner Fehler ({exc}).")

    # --- WLAN ---
    wifi_p = p.get("wifi") or {}
    ssid = str(ctx.stored.get("wifi_ssid") or "")
    pwd = str(ctx.stored.get("wifi_password") or "")
    wifi: dict[str, Any] = {
        "ssid": ctx.secret("wifi_ssid", ssid or "HIER_WLAN_NAME_EINTRAGEN"),
        "password": ctx.secret("wifi_password", pwd or "HIER_WLAN_PASSWORT_EINTRAGEN"),
    }
    if not ssid or not pwd:
        if ctx.use_secrets:
            ctx.warn("WLAN-Name oder -Passwort sind noch leer. Im secrets.yaml-Block stehen Platzhalter.")
        else:
            ctx.err("WLAN-Name und -Passwort fehlen (Bereich „WLAN & Secrets“).")
    st = wifi_p.get("static_ip") or {}
    if st.get("enabled"):
        ok = all(_check_ip(ctx, lbl, str(st.get(k) or "")) for lbl, k in
                 (("IP", "ip"), ("Gateway", "gateway"), ("Subnetz", "subnet")))
        manual: dict[str, Any] = {"static_ip": str(st.get("ip") or ""), "gateway": str(st.get("gateway") or ""),
                                  "subnet": str(st.get("subnet") or "")}
        if st.get("dns"):
            if _check_ip(ctx, "DNS", str(st["dns"])):
                manual["dns1"] = str(st["dns"])
        if ok:
            try:
                net = ipaddress.IPv4Network(f"{manual['static_ip']}/{manual['subnet']}", strict=False)
                if ipaddress.IPv4Address(manual["gateway"]) not in net:
                    ctx.err(f"Statische IP: Das Gateway {manual['gateway']} liegt nicht im selben Netz wie "
                            f"{manual['static_ip']} (Subnetz {manual['subnet']}).")
                elif manual["static_ip"] == manual["gateway"]:
                    ctx.err("Statische IP: IP-Adresse und Gateway sind gleich.")
            except ValueError:
                ctx.err(f"Statische IP: Das Subnetz „{manual['subnet']}“ ist keine gültige Netzmaske (z. B. 255.255.255.0).")
            wifi["manual_ip"] = manual
    if wifi_p.get("min_auth_mode") in ("WPA", "WPA2", "WPA3"):
        wifi["min_auth_mode"] = wifi_p["min_auth_mode"]
    if wifi_p.get("fallback_ap", True):
        ap_pw = str(wifi_p.get("ap_password") or "")
        if len(ap_pw) < 8:
            ctx.err("Fallback-Hotspot: Das Passwort braucht mindestens 8 Zeichen.")
        wifi["ap"] = {"password": ctx.secret(f"{dev_slug}_ap_password", ap_pw)}

    # --- Gesamtaufbau ---
    out: dict[str, Any] = {}
    comment = " ".join(str(p.get("comment") or "").split())
    use_subst = bool(p.get("substitutions"))
    if use_subst:
        subst: dict[str, Any] = {"devicename": name or "geraet"}
        if comment:
            subst["device_description"] = comment
        out["substitutions"] = subst
    esphome_block: dict[str, Any] = {"name": Raw("$devicename") if use_subst else (name or "geraet")}
    if friendly:
        esphome_block["friendly_name"] = friendly
    if comment:
        esphome_block["comment"] = Raw("${device_description}") if use_subst else comment
    out["esphome"] = esphome_block
    plat_name = board["platform"]
    if plat_name == "esp8266":
        esp8266: dict[str, Any] = {"board": board["board"]}
        if p.get("flash_mode") in ("dout", "dio", "qio", "qout"):
            esp8266["board_flash_mode"] = p["flash_mode"]
        if p.get("early_pin_init") in ("true", "false"):
            esp8266["early_pin_init"] = p["early_pin_init"] == "true"
        out["esp8266"] = esp8266
    elif plat_name == "esp32":
        fw = "arduino" if p.get("framework") == "arduino" else "esp-idf"
        out["esp32"] = {"board": board["board"], "framework": {"type": fw}}
    else:  # rp2, bk72xx, rtl87xx, ln882x
        out[plat_name] = {"board": board["board"]}
    if not board_has_wifi(board):
        if board["chip"] in NO_WIFI_CHIPS:
            ctx.err(f"{board['group']} hat kein eigenes WLAN. Dafür braucht ESPHome Ethernet oder ein WLAN-Zusatzmodul, "
                    "das ESPHome Studio noch nicht erzeugt.")
        else:
            ctx.err("Dieses Board hat keinen WLAN-Chip (nur Pico W / Pico 2 W und ähnliche). "
                    "Bitte ein Board mit WLAN wählen.")

    level = str(p.get("log_level") or "INFO").upper()
    logger: dict[str, Any] = {"level": level if level in LOG_LEVELS else "INFO"}
    if ctx.logger_off:
        logger["baud_rate"] = 0
    out["logger"] = logger

    api_p = p.get("api") or {}
    if api_p.get("enabled", True):
        if api_p.get("encryption", True):
            key = str(api_p.get("key") or "")
            if len(key) < 40:
                ctx.err("API-Schlüssel fehlt oder ist zu kurz. Bitte neu erzeugen.")
            out["api"] = {"encryption": {"key": ctx.secret(f"{dev_slug}_api_key", key)}}
        else:
            out["api"] = {}
            ctx.warn("Die API läuft ohne Verschlüsselung.")
    else:
        ctx.warn("Ohne API findet Home Assistant das Gerät nicht.")

    ota_p = p.get("ota") or {}
    if ota_p.get("enabled", True):
        mode = ota_p.get("mode")
        if mode not in ("encryption", "password", "none"):
            mode = "password" if ota_p.get("password_enabled") else "encryption"
        ota: dict[str, Any] = {"platform": "esphome"}
        if mode == "encryption":
            if api_p.get("enabled", True) and api_p.get("encryption", True):
                ota["encryption"] = {}
            else:
                ctx.err("OTA-Verschlüsselung nutzt den API-Schlüssel. Entweder die API-Verschlüsselung "
                        "einschalten oder beim OTA „Passwort“ bzw. „Keine Absicherung“ wählen.")
        elif mode == "password":
            ota["password"] = ctx.secret(f"{dev_slug}_ota_password", str(ota_p.get("password") or ""))
        else:
            ctx.warn("Das OTA-Update ist nicht abgesichert. Jeder im WLAN kann neue Firmware aufspielen.")
        out["ota"] = [ota]

    out["wifi"] = wifi
    if wifi_p.get("fallback_ap", True):
        out["captive_portal"] = {}
    _web_server(ctx, p, dev_slug, out)
    if p.get("time_ha"):
        out["time"] = [{"platform": "homeassistant", "id": "homeassistant_time"}]

    if "i2c" in ctx.top:
        out["i2c"] = ctx.top["i2c"]
    for k in TOP_ORDER_AFTER_I2C:
        if k in ctx.top:
            out[k] = ctx.top[k]
    for k, v in ctx.hubs.items():
        if k in out:
            ctx.err(f"„{k}“ kommt doppelt vor (Katalog-Baustein und Studio-Funktion).")
        else:
            out[k] = v

    # Diagnose-Entitäten
    diag = p.get("diag") or {}
    if diag.get("wifi_signal"):
        ctx.add("sensor", {"platform": "wifi_signal", "name": "WLAN-Signal", "update_interval": "60s",
                           "entity_category": "diagnostic"})
    if diag.get("uptime"):
        ctx.add("sensor", {"platform": "uptime", "name": "Laufzeit", "entity_category": "diagnostic"})
    if diag.get("uptime_text"):
        ctx.add("text_sensor", {
            "platform": "uptime", "name": "Betriebszeit", "icon": "mdi:clock-start", "update_interval": "60s",
            "entity_category": "diagnostic",
            "format": {"separator": " ", "days": "T", "hours": "Std", "minutes": "Min", "seconds": "Sek"}})
    wifi_info: dict[str, Any] = {"platform": "wifi_info"}
    for key, conf, label, icon in (("ip", "ip_address", "IP-Adresse", "mdi:ip-network"),
                                   ("ssid", "ssid", "Verbunden mit (SSID)", "mdi:access-point-network"),
                                   ("bssid", "bssid", "Verbunden mit (BSSID)", "mdi:access-point"),
                                   ("mac", "mac_address", "MAC-Adresse", "mdi:ip")):
        if diag.get(key):
            wifi_info[conf] = {"name": label, "icon": icon, "entity_category": "diagnostic"}
    if len(wifi_info) > 1:
        ctx.add("text_sensor", wifi_info)
    if diag.get("status"):
        ctx.add("binary_sensor", {"platform": "status", "name": "Status", "entity_category": "diagnostic"})
    if diag.get("restart"):
        ctx.add("button", {"platform": "restart", "name": "Neustart", "entity_category": "config"})
    if diag.get("debug_heap") or diag.get("debug_loop") or diag.get("debug_reset"):
        interval = str(p.get("debug_interval") or "30s").strip()
        if not INTERVAL_RE.match(interval):
            ctx.err(f"Debug-Intervall „{interval}“ ist ungültig (z. B. 30s oder 1min).")
            interval = "30s"
        out_debug: dict[str, Any] = {"update_interval": interval}
        dbg: dict[str, Any] = {"platform": "debug"}
        if diag.get("debug_heap"):
            dbg["free"] = {"name": "Freier Heap", "entity_category": "diagnostic"}
            dbg["block"] = {"name": "Größter Heap-Block", "entity_category": "diagnostic"}
        if diag.get("debug_loop"):
            dbg["loop_time"] = {"name": "Loop-Zeit", "entity_category": "diagnostic"}
        if len(dbg) > 1:
            ctx.add("sensor", dbg)
        if diag.get("debug_reset"):
            ctx.add("text_sensor", {"platform": "debug",
                                    "reset_reason": {"name": "Reset-Grund", "entity_category": "diagnostic"}})
        out["debug"] = out_debug
        ctx.warn("Die Debug-Sensoren sind zur Fehlersuche gedacht (Neustarts, Speicher). Danach wieder abschalten.")

    for dom in [*DOMAIN_ORDER, *[d_ for d_ in ctx.domains if d_ not in DOMAIN_ORDER]]:
        if dom in ctx.domains:
            out[dom] = (out.get(dom) or []) + ctx.domains[dom] if isinstance(out.get(dom), list) else ctx.domains[dom]
    if "debug" in out:  # direkt hinter den Grundblöcken, nicht ans Ende
        dbg_block = out.pop("debug")
        reordered: dict[str, Any] = {}
        for k, v in out.items():
            reordered[k] = v
            if k == "api" or (k == "logger" and "api" not in out):
                reordered["debug"] = dbg_block
        if "debug" not in reordered:
            reordered["debug"] = dbg_block
        out = reordered

    extra_text = str(p.get("extra_yaml") or "").strip()
    if extra_text:
        try:
            extra = load_text(extra_text)
        except ValueError as exc:
            ctx.err(f"Zusatz-YAML: {exc}")
        else:
            if isinstance(extra, dict):
                _merge_extra(ctx, out, extra, "")
            elif extra is not None:
                ctx.err("Zusatz-YAML: Es muss ein YAML-Abschnitt mit Schlüsseln sein (z. B. „script:“ oder „globals:“).")

    if "substitutions" in out and next(iter(out)) != "substitutions":
        out = {"substitutions": out.pop("substitutions"), **out}

    header = [
        f"# ESPHome Studio · Gerät „{name}“",
        f"# Board: {board['label']}",
        "# Zugangsdaten und Schlüssel stehen in der secrets.yaml (siehe zweiter Reiter)."
        if ctx.use_secrets else "# Achtung: Zugangsdaten stehen direkt in dieser Datei.",
        "",
    ]
    yaml_text = "\n".join(header) + "\n" + dump_yaml(out)

    secrets_lines: list[str] = []
    if ctx.use_secrets and ctx.secret_values:
        secrets_lines.append("# In die secrets.yaml von ESPHome einfügen.")
        secrets_lines.append("# wifi_ssid und wifi_password gelten für alle Geräte und müssen nur einmal vorkommen.")
        for k, v in ctx.secret_values.items():
            secrets_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    secrets_text = "\n".join(secrets_lines) + ("\n" if secrets_lines else "")

    return {"yaml": yaml_text, "secrets": secrets_text, "warnings": ctx.warnings, "errors": ctx.errors,
            "ok": not ctx.errors}


def generate(project: dict[str, Any], stored_secrets: dict[str, Any] | None = None) -> dict[str, Any]:
    """Erzeugt YAML + secrets.yaml-Block. Wirft keine Ausnahmen."""
    try:
        return _generate(json.loads(json.dumps(project)), stored_secrets or {})
    except Exception as exc:  # noqa: BLE001
        return {"yaml": "", "secrets": "", "warnings": [], "errors": [f"Interner Fehler: {exc}"], "ok": False}
