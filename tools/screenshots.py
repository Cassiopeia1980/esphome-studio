"""Erzeugt die Screenshots für die README aus dem echten Panel (Chromium + Playwright).

Aufruf:  python3 tools/screenshots.py
Das Panel läuft mit dem echten Generator (tests/bridge.py), nur Home Assistant selbst wird nachgebaut.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PANEL = (ROOT / "custom_components/esphome_studio/frontend/esphome-studio-panel.js").read_text(encoding="utf-8")
STATE = Path("/tmp/esphome-studio-shot-state.json")
OUT = ROOT / "docs" / "screenshots"

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
:root { --primary-color:#03a9f4; --app-header-background-color:#03a9f4; --app-header-text-color:#fff;
  --primary-background-color:#fafafa; --card-background-color:#fff; --secondary-background-color:#f1f3f4;
  --primary-text-color:#212121; --secondary-text-color:#727272; --divider-color:#e0e0e0; }
html,body{margin:0;height:100%;font-family:Roboto,Arial,sans-serif} esphome-studio-panel{display:block;height:100vh}
</style></head><body></body></html>"""


def bridge(msg: dict) -> dict:
    out = subprocess.run([sys.executable, "-I", str(ROOT / "tests/bridge.py"), str(STATE)], input=json.dumps(msg).encode(),
                         capture_output=True, check=True)
    return json.loads(out.stdout)


def shoot(page, name, lang, mode, setup=None, clip_selector=None):
    page.goto("http://studio.test/")
    page.evaluate(f"""() => {{ localStorage.setItem('esphome_studio_lang','{lang}'); localStorage.setItem('esphome_studio_mode','{mode}'); }}""")
    page.evaluate("""(panelSrc) => { (0, eval)(panelSrc); }""", PANEL)
    page.evaluate("""() => {
      const hass = { language: 'de', connection: { sendMessagePromise: (m) => window.bridge(m) } };
      const el = document.createElement('esphome-studio-panel'); document.body.append(el); el.hass = hass; window.panel = el; }""")
    page.wait_for_timeout(300)
    page.evaluate("() => { window.panel.meta.version = '0.9.0'; window.panel._buildHead(); }")
    page.wait_for_timeout(2500)
    if setup:
        setup(page)
        page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / f"{name}-{lang}.png"), full_page=False)


def main() -> None:
    if STATE.exists():
        STATE.unlink()
    bridge({"type": "esphome_studio/set_secrets", "secrets": {"wifi_ssid": "Mein-WLAN", "wifi_password": "geheim-1234"}})
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"))
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.expose_function("bridge", bridge)
        page.route("http://studio.test/", lambda route: route.fulfill(status=200, content_type="text/html", body=HTML))
        for lang in ("de", "en"):
            STATE.write_text(json.dumps({"projects": {}, "secrets": {"wifi_ssid": "Mein-WLAN", "wifi_password": "geheim-1234"}}))
            shoot(page, "wizard", lang, "simple")

            def fill(pg):
                pg.evaluate("""async () => { const el = window.panel;
                  const tpl = el.constructor && null; el._wizardOff = true; el._addComponent('switch', {pin: 'GPIO5'});
                  el._addComponent('binary_sensor', {pin: 'GPIO14'}); el._addComponent('dht', {pin: 'GPIO12'});
                  el.p.friendly_name = 'Gartenhaus'; el.p.name = 'gartenhaus'; el._changed(true); }""")
            shoot(page, "project", lang, "pro", fill)
        browser.close()


if __name__ == "__main__":
    main()
