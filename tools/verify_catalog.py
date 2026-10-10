"""Prüft jeden Katalog-Baustein mit dem echten ``esphome config`` und trägt die Ergebnisse in catalog.json ein.

    python tools/verify_catalog.py /pfad/zu/esphome [--boards d1_mini,esp32dev,...] [--only bme680.sensor] [--jobs 2]

Pro Baustein und Plattform wird ein Minimal-Gerät erzeugt (Pins und Pflichtfelder automatisch gefüllt) und mit
``esphome config`` geprüft. Eingetragen werden ``platforms`` (wo es geht), ``verified`` und bei Fehlern ``note``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from helpers import load_core  # noqa: E402

boards, components, gen = load_core()
CAT_FILE = ROOT / "custom_components" / "esphome_studio" / "catalog.json"
STORED = {"wifi_ssid": "Test WLAN", "wifi_password": "geheim-1234"}
TEST_BOARDS = {"esp8266": "d1_mini", "esp32": "esp32dev", "rp2": "rpipicow", "bk72xx": "generic-bk7231n-qfn32-tuya",
               "rtl87xx": "generic-rtl8710bn-2mb-788k", "ln882x": "generic-ln882h"}


def free_pins(board: dict, kind: str, used: set[str]) -> list[str]:
    bad = ("flash", "uart", "strapping", "usb", "psram", "boot_high", "no_i2c")
    out = []
    for p in board["pins"]:
        if p["id"] in used or any(p.get(f) for f in bad):
            continue
        if kind in ("out", "io", "pwm") and p.get("input_only"):
            continue
        if kind != "adc" and p.get("adc_only"):
            continue
        if kind == "adc" and not p.get("adc"):
            continue
        out.append(p["id"])
    return out


def guess(key: str, f: dict) -> str:
    """Brauchbarer Wert für ein Pflichtfeld, damit `esphome config` das Gerät prüfen kann."""
    if f.get("default") not in ("", None):
        return str(f["default"])
    if f.get("choices"):
        return str(f["choices"][0])
    k = key.lower()
    if k in ("private_key", "peer_public_key", "peer_preshared_key") or k.endswith("wireguard_key"):
        return "A" * 43 + "="
    if k == "frequency":
        return "1000"
    if "uuid" in k:
        return "180F"
    if k.startswith("cold") and k.endswith("temperature"):
        return "6500 K"
    if f.get("fill"):
        return str(f["fill"])
    if k == "dimensions":
        return "16x2"
    if k == "min_value":
        return "0"
    if k == "max_value":
        return "100"
    if k.endswith("temperature"):
        return "2700 K"
    if k == "entity_id":
        return "sensor.test"
    if "mac" in k:
        return "AA:BB:CC:DD:EE:FF"
    if "key" in k:
        return "00" * 16
    if k == "address" or k.endswith("_address"):
        return "0x10"
    return "1"


def provider(cls: str, exclude: str = "") -> dict | None:
    """Einfachster Katalog-Baustein, der die Klasse liefert (bevorzugt geprüfte, mit wenig Pflichtangaben)."""
    cands = [e for e in entries() if cls in e.get("provides", []) and e["id"] != exclude and not e["unsupported"]]
    if not cands:
        return None
    cands.sort(key=lambda e: (e["domain"] != "output" and e["id"] != "gpio.output" and 1, not e.get("verified"),
                              sum(1 for f in e["fields"] if f["required"]) + sum(1 for p in e["pins"] if p["required"]) + (3 if e["bus"] else 0)
                              + (5 if e["hub"] else 0) + (5 if e.get("refs") else 0), e["id"]))
    return cands[0]


def simplest(domain: str, chain: tuple = ()) -> dict | None:
    cands = [e for e in entries() if e["domain"] == domain and not e["unsupported"] and e["id"] not in chain and e.get("verified")]
    cands.sort(key=lambda e: (sum(1 for f in e["fields"] if f["required"]) + sum(1 for p in e["pins"] if p["required"]) + (3 if e["bus"] else 0)
                              + (5 if e["hub"] else 0) + 5 * len(e.get("refs", [])), e["id"]))
    return cands[0] if cands else None


def entries() -> list[dict]:
    return sys.modules["esphome_studio.catalog"].catalog()["entries"]


def by_id() -> dict[str, dict]:
    return sys.modules["esphome_studio.catalog"].by_id()


def fill(entry: dict, board_key: str, used: set[str] | None = None, comps: list | None = None, top: bool = True, chain: tuple = ()) -> dict:
    """Baut die Komponenten (inkl. Hubs und Ausgängen) für einen Katalogeintrag; liefert den Hauptbaustein."""
    board = boards.BOARDS[board_key]
    cat = by_id()
    chain = (*chain, entry["id"])
    if used is None:
        used = {board["i2c_default"]["sda"], board["i2c_default"]["scl"]}
    if comps is None:
        comps = []
    if entry["bus"] == "spi":
        used |= set(board.get("spi_default", {}).values())
    c = {"uid": gen.new_uid(), "type": "generic", "cat": entry["id"], "name": "Test" if top else f"Dep {len(comps)} {entry['id']}",
         "pins": {}, "options": {}}
    o = c["options"]
    if entry["bus"] == "uart":
        o["baud"] = str(entry.get("baud_default") or 9600)
        rx = free_pins(board, "in", used)
        if rx:
            c["pins"]["_rx"] = rx[0]
            used.add(rx[0])
        tx = free_pins(board, "out", used)
        if tx:
            c["pins"]["_tx"] = tx[0]
            used.add(tx[0])
    for ps in entry["pins"]:
        if ps["required"]:
            cands = free_pins(board, ps["kind"], used)
            if cands:
                c["pins"][ps["key"]] = cands[0]
                used.add(cands[0])
    for f in entry["fields"]:
        if f["required"]:
            o["f_" + f["key"]] = guess(f["key"], f)
    for k in gen.default_subs(entry):
        o["s_" + k] = True
    if entry["hub"] and entry["hub"] in cat and entry["hub"] not in chain[:-1]:
        o["hub"] = fill(cat[entry["hub"]], board_key, used, comps, False, chain)["uid"]
    for r in entry.get("refs", []):
        if r["required"]:
            tgt = provider(r["cls"], entry["id"])
            if tgt and tgt["id"] not in chain:
                o["ref_" + r["key"]] = fill(tgt, board_key, used, comps, False, chain)["uid"]
    for nid in entry.get("needs_cat") or []:
        if nid in cat and nid not in chain and not any(x["cat"] == nid for x in comps if x.get("type") == "generic"):
            fill(cat[nid], board_key, used, comps, False, chain)
    for dom in entry.get("needs_dom") or []:
        if not any(by_id().get(x.get("cat"), {}).get("domain") == dom for x in comps if x.get("type") == "generic"):
            prov = simplest(dom, chain)
            if prov:
                fill(prov, board_key, used, comps, False, chain)
    for need in entry.get("needs") or []:
        if need == "ir_transmitter" and not any(x["type"] == "ir_transmitter" for x in comps):
            pin = free_pins(board, "out", used)
            if pin:
                used.add(pin[0])
                comps.append(gen.new_component("ir_transmitter", "IR", {"pin": pin[0]}))
        if need == "time":
            c["_needs_time"] = True
    comps.append(c)
    return c


def check(esphome_bin: str, entry: dict, plat: str) -> tuple[bool, str, str]:
    """Prüft einen Baustein; lernt dabei fehlende Pflichtfelder und Baudraten und trägt sie in den Eintrag ein."""
    board_key = TEST_BOARDS[plat]
    msg = out = ""
    for _ in range(5):
        p = gen.default_project(board_key)
        p["name"] = "verify"
        comps: list = []
        fill(entry, board_key, None, comps)
        if any(x.pop("_needs_time", False) for x in comps):
            p["time_ha"] = True
        p["components"] = comps
        r = gen.generate(p, STORED)
        if r["errors"]:
            return False, "Studio: " + "; ".join(r["errors"])[:300], r["yaml"]
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "verify.yaml").write_text(r["yaml"], encoding="utf-8")
            (d / "secrets.yaml").write_text(r["secrets"], encoding="utf-8")
            try:
                pr = subprocess.run([esphome_bin, "config", str(d / "verify.yaml")], capture_output=True, text=True, timeout=240)
            except subprocess.TimeoutExpired:
                return False, "Zeitüberschreitung", r["yaml"]
        out = pr.stdout + pr.stderr
        if pr.returncode == 0:
            return True, "", r["yaml"]
        learned = False
        m = re.search(r"Component (\S+) requires baud rate (\d+)", out)
        if m:
            tgt = by_id().get(m.group(1)) or entry
            if tgt["bus"] == "uart" and tgt.get("baud_default") != int(m.group(2)):
                tgt["baud_default"] = int(m.group(2))
                learned = True
        for name, par, parv, num, what in re.findall(r"Component (\S+) requires (?:(parity) (\w+)|(\d) (stop bits|data bits))", out):
            tgt = by_id().get(name) or entry
            key = "parity" if par else {"stop bits": "stop_bits", "data bits": "data_bits"}[what]
            v_ = parv if par else int(num)
            if tgt["bus"] == "uart" and (tgt.get("uart") or {}).get(key) != v_:
                tgt.setdefault("uart", {})[key] = v_
                learned = True
        for need, studio in (("remote_transmitter", "ir_transmitter"), ("time::RealTimeClock", "time"), ("requires component time", "time")):
            if need in out and studio not in (entry.get("needs") or []) and not (need == "remote_transmitter" and "requires component remote_transmitter" not in out):
                entry.setdefault("needs", []).append(studio)
                learned = True
        cat = by_id()
        from_domains = {e["domain"] for e in entries()}
        for y in dict.fromkeys(re.findall(r"Component \S+ requires component (\w+)", out)):
            if y not in cat and y in from_domains and y != entry["domain"] and y not in (entry.get("needs_dom") or []):
                entry.setdefault("needs_dom", []).append(y)
                learned = True
                continue
            cand = y if y in cat else (entry["platform"] if entry["platform"] in cat and entry["domain"] != "hub" else None)
            if cand and cand != entry["id"] and cand not in (entry.get("needs_cat") or []) and not cat[cand]["unsupported"]:
                entry.setdefault("needs_cat", []).append(cand)
                learned = True
        for cls in dict.fromkeys(re.findall(r"Couldn't find any component that can be used for '([^']+)'", out)):
            prov = provider(cls, entry["id"])
            if prov and prov["id"] not in (entry.get("needs_cat") or []):
                entry.setdefault("needs_cat", []).append(prov["id"])
                learned = True
        if "No BLE tracker configured" in out and "esp32_ble_tracker" in cat and entry["id"] != "esp32_ble_tracker" \
                and "esp32_ble_tracker" not in (entry.get("needs_cat") or []):
            entry.setdefault("needs_cat", []).append("esp32_ble_tracker")
            learned = True
        if re.search(r"\[name\] is an invalid option", out) and entry.get("self_entity"):
            entry["self_entity"] = False
            learned = True
        if "optimistic mode must be enabled" in out:
            f_ = next((x for x in entry["fields"] if x["key"] == "optimistic"), None)
            if f_ is not None and (entry.get("force") or {}).get("optimistic") is not True:
                entry.setdefault("force", {})["optimistic"] = True
                learned = True
        if re.search(r"\[id\] is an invalid option", out) and not entry.get("no_id"):
            entry["no_id"] = True
            learned = True
        olines = out.splitlines()
        for i, ln in enumerate(olines):  # Hinweise von ESPHome stehen direkt VOR dem betroffenen Schlüssel
            if i + 1 >= len(olines):
                continue
            km = re.match(r"\s*(\w+):", olines[i + 1])
            f = next((x for x in entry["fields"] if km and x["key"] == km.group(1)), None)
            if not f:
                continue
            if re.search(r"must be (a )?string|Must be string", ln, re.I) and f.get("as") != "str":
                f["as"] = "str"
                learned = True
            m3 = re.search(r"value must be at least (-?[\d.]+)", ln)
            if m3 and f.get("fill") != m3.group(1):
                f["fill"] = m3.group(1)
                learned = True
            m2 = re.search(r"Unknown value '[^']*', valid options are (.+)", ln)
            if m2 and f.get("type") != "enum":
                choices = re.findall(r"'([^']+)'", m2.group(1))
                if choices:
                    f["type"], f["choices"] = "enum", choices
                    learned = True
        keys = re.findall(r"'(\w+)' is a required option", out) + [m.lower() for m in re.findall(r"\b([A-Z][a-z_]+) is required", out)]
        for key in dict.fromkeys(keys):
            if key.endswith("_pin") or key == "pin":
                if not any(p_["key"] == key for p_ in entry["pins"]):
                    entry["pins"].append({"key": key, "label": key.replace("_pin", "").replace("_", " ") or key, "kind": "io", "required": True, "modes": []})
                    learned = True
                continue
            f = next((x for x in entry["fields"] if x["key"] == key), None)
            if f is None:
                if any(x["key"] == key for x in entry["subs"]) or key in ("name", "id"):
                    continue
                entry["fields"].append({"key": key, "label": key.replace("_", " "), "required": True, "default": "", "type": "text"})
                learned = True
            elif not f["required"]:
                f["required"] = True
                learned = True
        if not learned:
            break
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith(("INFO", "WARNING"))]
    keep = [ln for ln in lines if re.search(r"(required|invalid|Unable|Unknown|Expected|supported|requires|Couldn|must)", ln, re.I)]
    return False, " | ".join(keep or lines[:3])[:300], r["yaml"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("esphome")
    ap.add_argument("--platforms", default="esp32,esp8266,rp2,bk72xx,rtl87xx,ln882x")
    ap.add_argument("--only", default="")
    ap.add_argument("--failed", action="store_true", help="nur Bausteine ohne Prüfergebnis oder mit Fehler")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    plats = a.platforms.split(",")
    allowed = set(a.only.split(",")) if a.only else None
    todo = [e for e in entries() if not e["unsupported"] and (allowed is None or e["id"] in allowed)
            and (not a.failed or not e.get("verified"))]
    for e in todo:  # frühere Ergebnisse dürfen die Prüfung nicht einschränken
        e.pop("platforms", None)

    def one(e: dict) -> tuple[str, list[str], str]:
        ok_plats, note = [], ""
        for i, plat in enumerate(plats):
            if i == 3 and not ok_plats:  # läuft auf ESP32, ESP8266 und Pico nicht: auf LibreTiny sicher auch nicht
                break
            ok, msg, _ = check(a.esphome, e, plat)
            if ok:
                ok_plats.append(plat)
            elif not note:
                note = f"{plat}: {msg}"
        return e["id"], ok_plats, note

    results: dict[str, tuple[list[str], str]] = {}
    with ThreadPoolExecutor(a.jobs) as ex:
        for i, (eid, ok_plats, note) in enumerate(ex.map(one, todo), 1):
            results[eid] = (ok_plats, note)
            print(f"[{i}/{len(todo)}] {eid}: {','.join(ok_plats) or 'FEHLER'} {note[:160] if not ok_plats else ''}", flush=True)
            if i % 25 == 0:
                _save(results)
    _save(results)
    allv = sum(1 for e in entries() if e.get("verified"))
    print(f"\n{allv} von {sum(1 for e in entries() if not e['unsupported'])} Bausteinen verifiziert.")
    return 0


def _save(results: dict) -> None:
    cat = sys.modules["esphome_studio.catalog"].catalog()
    for e in cat["entries"]:
        if e["id"] in results:
            ok_plats, note = results[e["id"]]
            e["platforms"] = ok_plats
            e["verified"] = bool(ok_plats)
            e["note"] = "" if ok_plats else note
    tmp = CAT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(CAT_FILE)


if __name__ == "__main__":
    sys.exit(main())
