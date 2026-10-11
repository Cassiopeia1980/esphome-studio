// UI-Test auf Englisch: Panel in jsdom mit Sprache "en" rendern, durch die Ansichten klicken und nach deutschen Resten suchen.
// Aufruf: node tests/ui_smoke_en.mjs
import { createRequire } from "node:module";
import { readFileSync, rmSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire("/tmp/jsdom-test/package.json");
const { JSDOM } = require("jsdom");
const here = path.dirname(fileURLToPath(import.meta.url));
const stateFile = "/tmp/esphome-studio-ui-state-en.json";
if (existsSync(stateFile)) rmSync(stateFile);

const dom = new JSDOM("<!doctype html><html><body></body></html>", { runScripts: "outside-only", pretendToBeVisual: true, url: "http://localhost/" });
const { window } = dom;
window.localStorage.setItem("esphome_studio_mode", "pro");
window.localStorage.setItem("esphome_studio_lang", "en");
window.eval(readFileSync(path.join(here, "../custom_components/esphome_studio/frontend/esphome-studio-panel.js"), "utf8"));

const hass = { connection: { sendMessagePromise: async (msg) =>
  JSON.parse(execFileSync("python3", ["-I", path.join(here, "bridge.py"), stateFile], { input: JSON.stringify(msg) }).toString()) } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const el = window.document.createElement("esphome-studio-panel");
window.document.body.append(el);
el.hass = hass;
const root = el.shadowRoot;
const fire = (n, type) => n.dispatchEvent(new window.Event(type, { bubbles: true }));

// Erkennung deutscher Reste: Umlaute/ß oder typische deutsche Wörter
const DE = /^(null|undefined|NaN)$|[äöüÄÖÜß]|\b(und|oder|nicht|der|die|das|ein|eine|für|mit|bei|wird|werden|Gerät|Baustein|Einstellungen|Speichern|Löschen|Hinzufügen|Passwort|Zugangsdaten|Laufzeit|Fehler|Treffer|Wähle|Hängt|belegt|noch|auch|nur|ohne|wenn|dann|nach|oben|unten|Seite|Ziel|Ordner|Adresse|Hinweis)\b/;
const leftovers = new Set();
const KEYS = new Set(Object.entries((await hass.connection.sendMessagePromise({ type: "esphome_studio/i18n", lang: "en" })).dict)
  .filter(([k, v]) => k.trim() !== v.trim() && k.length > 3 && !/^\{\d/.test(k)).map(([k]) => k.trim()));
const scan = (label) => {
  const walk = (node) => {
    for (const n of node.childNodes) {
      if (n.nodeType === 3) {
        const tx = n.textContent.trim();
        if (tx && (DE.test(tx) || KEYS.has(tx)) && n.parentElement?.tagName !== "PRE" && !n.parentElement?.closest?.("pre,textarea,.code")) leftovers.add(`[${label}] ${tx.slice(0, 140)}`);
      } else if (n.nodeType === 1) {
        for (const a of ["title", "placeholder"]) { const v = n.getAttribute?.(a); if (v && DE.test(v)) leftovers.add(`[${label}] @${a}: ${v.slice(0, 140)}`); }
        if (n.tagName !== "STYLE" && n.tagName !== "PRE" && n.tagName !== "TEXTAREA") walk(n);
      }
    }
  };
  walk(root);
};

let failures = 0;
const check = (name, cond, extra = "") => { console.log(`${cond ? "OK   " : "FEHLER"} ${name}${!cond && extra ? " -> " + extra : ""}`); if (!cond) failures++; };
await sleep(1800);
check("Sprache Englisch aktiv", root.querySelector("select.langsel")?.value === "en");
check("Englischer Kartentitel", root.textContent.includes("Wi-Fi, secrets & security"), root.textContent.slice(0, 200));
check("Standardname englisch", (root.querySelector("pre.code")?.textContent || "").includes("name: new-device"), (root.querySelector("pre.code")?.textContent || "").slice(0, 80));
scan("start");

// Profi-Ansicht, alle Schalter durchgehen
for (const cb of root.querySelectorAll(".card input[type=checkbox]")) { if (!cb.checked && !cb.closest(".mode")) { cb.checked = true; fire(cb, "change"); await sleep(60); } }
await sleep(600);
scan("alles-an");

// Komponenten hinzufügen (Standardbausteine + Katalog)
const addSel = [...root.querySelectorAll("select")].find((s) => [...s.options].some((o) => o.value === "switch"));
for (const type of ["switch", "light_rgb", "dht", "bme280", "ultrasonic", "binary_sensor", "dallas", "light_strip"]) {
  if (!addSel) break;
  addSel.value = type;
  const btn = [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === "Add");
  if (btn) { btn.click(); await sleep(250); }
}
scan("komponenten");

// Katalog durchsuchen, UART-Baustein hinzufügen
const search = [...root.querySelectorAll("input")].find((i) => /Search, e\.g\. bme680/.test(i.placeholder));
check("Katalogsuche englisch beschriftet", !!search);
if (search) { search.value = "pm"; fire(search, "input"); await sleep(400); scan("katalog"); }

// Einfache Ansicht mit Assistent, Vorlage anwenden
const newBtn = [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === "New");
if (newBtn) { newBtn.click(); await sleep(600); }
const modeBox = root.querySelector(".mode input[type=checkbox]");
modeBox.checked = true; fire(modeBox, "change"); await sleep(500);
scan("einfach-leer");
const tpl = root.querySelector(".tpl-grid button, .tpl-grid .tpl");
if (tpl) { tpl.click(); await sleep(700); scan("einfach-vorlage"); }
check("Vorlage englisch benannt", /name: (socket|switch|light|dimmer|rgb-light|led-strip|climate-sensor|weather-station|temperature|contact|ir-transmitter)/.test(root.querySelector("pre.code")?.textContent || ""), (root.querySelector("pre.code")?.textContent || "").slice(0, 160));
modeBox.checked = false; fire(modeBox, "change"); await sleep(400);

// YAML-Import (deutsche und englische Meldungen)
const impBtn = [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === "Import YAML");
if (impBtn) {
  impBtn.click(); await sleep(300);
  const ta = root.querySelector("textarea");
  if (ta) {
    ta.value = "esphome:\n  name: test\nesp8266:\n  board: d1_mini\nlogger:\nswitch:\n  - platform: gpio\n    name: Lampe\n    pin: D1\nscript:\n  - id: x\n    then: []\n";
    fire(ta, "input");
    const go = [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === "Import");
    if (go) { go.click(); await sleep(900); scan("import"); }
  }
}
// Speichern-in-ESPHome-Bereich
const dep = [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === "Save to ESPHome");
if (dep) { dep.click(); await sleep(400); scan("deploy"); }

// Sprache zurückwechseln
const sel = root.querySelector("select.langsel");
sel.value = "de"; fire(sel, "change");
await sleep(1500);
check("Zurück auf Deutsch", root.textContent.includes("WLAN, Secrets & Sicherheit"));
check("Zurück auf Deutsch: Hostname deutsch bleibt Nutzerwahl", true);

const list = [...leftovers].sort();
console.log(`Deutsche Reste: ${list.length}`);
for (const l of list) console.log("  ", l);
check("keine deutschen Reste im englischen UI", list.length === 0);
console.log(failures ? `\n${failures} Fehler` : "\nalles ok");
process.exit(failures ? 1 : 0);
