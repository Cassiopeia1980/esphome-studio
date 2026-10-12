"""Prüft jede Komponente auf jeder Plattform mit `esphome config` (echte ESPHome-Validierung)."""
import json, subprocess, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from helpers import load_core
boards, components, gen = load_core()
ESPHOME = sys.argv[1] if len(sys.argv) > 1 else "esphome"
REPS = sys.argv[2].split(",")

def pins_for(spec, b):
    free = [p["id"] for p in b["pins"] if not any(p.get(f) for f in ("flash","uart","strapping","input_only","adc_only","usb","psram","boot_high","no_pwm","no_i2c"))]
    adc = [p["id"] for p in b["pins"] if p.get("adc")]
    out = {}
    for i, ps in enumerate(spec["pins"]):
        if spec["type"] == "adc" if "type" in spec else False: pass
        out[ps["key"]] = free[(i + 2) % len(free)] if len(free) > 1 else (free[0] if free else "")
    return out

res = {}
tmp = pathlib.Path(tempfile.mkdtemp())
for key in REPS:
    b = boards.BOARDS[key]
    for t, spec in components.COMPONENTS.items():
        p = gen.default_project(key)
        p["name"] = "matrix"
        pins = pins_for({**spec, "type": t}, b)
        if t == "adc":
            ap = [x["id"] for x in b["pins"] if x.get("adc")]
            if ap: pins = {"pin": ap[0]}
        c = gen.new_component(t, "Test", pins)
        p["components"] = [c]
        # I2C-Pins eindeutig wählen
        r = gen.generate(p, {"wifi_ssid": "a", "wifi_password": "12345678", "ap_password": "hotspot-pw-123"})
        f = tmp / f"{key}_{t}.yaml"
        (tmp / "secrets.yaml").write_text(r["secrets"] or "x: 1\n")
        f.write_text(r["yaml"])
        proc = subprocess.run([ESPHOME, "config", str(f)], capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0
        res[(key, t)] = (ok, r["errors"], (proc.stdout + proc.stderr)[-600:] if not ok else "")
        print(("OK  " if ok else "FAIL"), key, t, (r["errors"][:1] if r["errors"] else ""), flush=True)
json.dump({f"{k[0]}|{k[1]}": v for k, v in res.items()}, open(tmp / "matrix.json", "w"), ensure_ascii=False, indent=1)
print(tmp / "matrix.json")
