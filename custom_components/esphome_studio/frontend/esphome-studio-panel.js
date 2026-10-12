/* ESPHome Studio – Panel für Home Assistant (reines JavaScript, keine Abhängigkeiten) */

const DEFAULT_NAMES = {
  switch: "Relais", status_led: "Status-LED", light_binary: "Licht", light_pwm: "Dimmer",
  light_rgb: "RGB-Licht", light_rgbw: "RGBW-Licht", light_rgbww: "RGBWW-Licht", light_strip: "LED-Streifen",
  binary_sensor: "Taster", ir_receiver: "IR-Empfänger", ir_transmitter: "IR-Sender", dht: "Klima",
  dallas: "Temperatur", adc: "Analog", ultrasonic: "Abstand", bme280: "BME280", bmp280: "BMP280",
  sht3xd: "SHT3x", aht10: "AHT", bh1750: "Helligkeit",
};

// Vorlagen für den Start-Assistenten. Pins wählt das Studio selbst; "@0" verweist auf die erste Komponente der Vorlage.
const TEMPLATES = [
  { id: "relay", icon: "🔌", title: "Steckdose / Relais schalten", text: "Ein Relais ein- und ausschalten, z. B. Steckdose, Pumpe oder Lüfter.",
    name: "steckdose", friendly: "Steckdose", comps: [{ type: "switch", name: "Steckdose" }] },
  { id: "relay_btn", icon: "🔘", title: "Relais mit Taster", text: "Wie oben, dazu ein Taster am Gerät, der das Relais umschaltet.",
    name: "schalter", friendly: "Schalter", comps: [{ type: "switch", name: "Relais" }, { type: "binary_sensor", name: "Taster", options: { toggle_target: "@0", device_class: "none" } }] },
  { id: "light", icon: "💡", title: "Licht an/aus", text: "Eine einfache Lampe über einen Schaltausgang.",
    name: "licht", friendly: "Licht", comps: [{ type: "light_binary", name: "Licht" }] },
  { id: "dimmer", icon: "🔆", title: "Dimmbares Licht", text: "Eine Lampe oder ein einfarbiger LED-Streifen, stufenlos dimmbar (PWM).",
    name: "dimmer", friendly: "Dimmer", comps: [{ type: "light_pwm", name: "Licht" }] },
  { id: "rgb", icon: "🌈", title: "RGB-Licht", text: "Farbiger LED-Streifen mit drei Kanälen (rot, grün, blau).",
    name: "rgb-licht", friendly: "RGB-Licht", comps: [{ type: "light_rgb", name: "RGB-Licht" }] },
  { id: "strip", icon: "✨", title: "LED-Streifen (WS2812 & Co.)", text: "Einzeln ansteuerbare LEDs mit Effekten (nur ESP32).",
    name: "led-streifen", friendly: "LED-Streifen", comps: [{ type: "light_strip", name: "LED-Streifen" }] },
  { id: "dht", icon: "🌡️", title: "Temperatur & Luftfeuchte (DHT22)", text: "Ein DHT22-Sensor, einfach und günstig.",
    name: "klima-sensor", friendly: "Klima-Sensor", comps: [{ type: "dht", name: "Klima" }] },
  { id: "bme", icon: "⛅", title: "Wetterstation (BME280)", text: "Temperatur, Luftfeuchte und Luftdruck über I²C.",
    name: "wetterstation", friendly: "Wetterstation", comps: [{ type: "bme280", name: "Wetter" }] },
  { id: "ds", icon: "🧪", title: "Temperaturfühler (DS18B20)", text: "Wasserdichter Fühler, z. B. für Vorlauf, Pool oder Aquarium.",
    name: "temperatur", friendly: "Temperatur", comps: [{ type: "dallas", name: "Temperatur" }] },
  { id: "door", icon: "🚪", title: "Türkontakt / Taster", text: "Meldet, ob ein Kontakt oder Taster geschlossen ist.",
    name: "kontakt", friendly: "Kontakt", comps: [{ type: "binary_sensor", name: "Tür", options: { device_class: "door" } }] },
  { id: "ir", icon: "📡", title: "Infrarot-Sender", text: "Sendet IR-Befehle, z. B. für Klimaanlage, TV oder Soundbar.",
    name: "ir-sender", friendly: "IR-Sender", comps: [{ type: "ir_transmitter", name: "IR-Sender" }] },
  { id: "pir", icon: "🚶", title: "Bewegungsmelder (PIR)", text: "Meldet Bewegung, z. B. mit einem HC-SR501-Modul.",
    name: "bewegungsmelder", friendly: "Bewegungsmelder", comps: [{ type: "binary_sensor", name: "Bewegung", options: { device_class: "motion" } }] },
  { id: "relay2", icon: "🔌", title: "Zwei Relais", text: "Zwei getrennt schaltbare Ausgänge, z. B. ein Doppelrelais-Modul.",
    name: "doppelrelais", friendly: "Doppelrelais", comps: [{ type: "switch", name: "Relais 1" }, { type: "switch", name: "Relais 2" }] },
  { id: "sht", icon: "💧", title: "Temperatur & Luftfeuchte (SHT3x)", text: "Genauer I²C-Sensor, die bessere Alternative zum DHT22.",
    name: "sht-sensor", friendly: "SHT-Sensor", comps: [{ type: "sht3xd", name: "Klima" }] },
  { id: "lux", icon: "☀️", title: "Helligkeit (BH1750)", text: "Misst die Helligkeit in Lux über I²C.",
    name: "lichtsensor", friendly: "Lichtsensor", comps: [{ type: "bh1750", name: "Helligkeit" }] },
  { id: "dist", icon: "📏", title: "Abstand / Füllstand (HC-SR04)", text: "Ultraschall-Entfernungsmesser, z. B. für Füllstand von Zisterne oder Tank.",
    name: "abstandssensor", friendly: "Abstandssensor", comps: [{ type: "ultrasonic", name: "Abstand" }] },
  { id: "volt", icon: "🔋", title: "Spannung messen (Analog)", text: "Liest den Analog-Eingang, z. B. für Akku oder Potentiometer.",
    name: "spannungsmesser", friendly: "Spannungsmesser", comps: [{ type: "adc", name: "Analog" }] },
];
const QUICK_BOARDS = [["d1_mini", "Wemos D1 Mini (ESP8266)"], ["nodemcuv2", "NodeMCU (ESP8266)"], ["esp01_1m", "ESP-01 (ESP8266)"],
  ["esp32dev", "ESP32 DevKit"], ["esp32-c3-devkitm-1", "ESP32-C3"], ["cb2s", "Tuya CB2S (Beken)"], ["rpipicow", "Raspberry Pi Pico W"]];
// In der Einfach-Ansicht sichtbare Einstellungen der Bausteine, der Rest steht unter „Weitere Einstellungen“
const ESSENTIAL_OPTS = new Set(["inverted", "model", "device_class", "toggle_target", "num_leds", "chipset", "rgb_order", "pulse_ms",
  "restore_mode", "variant", "address", "name_none"]);

const LOG_LEVELS = ["NONE", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE", "VERY_VERBOSE"];

const CSS = `
  :host { display: block; height: 100%; overflow: auto; background: var(--primary-background-color);
          color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          --es-gap: 16px; }
  * { box-sizing: border-box; }
  .toolbar { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 8px; height: 56px;
             padding: 0 12px; background: var(--app-header-background-color, var(--primary-color));
             color: var(--app-header-text-color, #fff); }
  .toolbar .title { font-size: 20px; font-weight: 500; flex: 1; }
  .toolbar .ver { opacity: .7; font-size: 12px; }
  .layout { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: var(--es-gap);
            padding: var(--es-gap); max-width: 1700px; margin: 0 auto; align-items: start; }
  @media (max-width: 1100px) { .layout { grid-template-columns: minmax(0, 1fr); } .out { position: static !important; } }
  .col { display: flex; flex-direction: column; gap: var(--es-gap); min-width: 0; }
  .card { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); padding: 16px; min-width: 0; }
  .card h2 { margin: 0 0 12px; font-size: 17px; font-weight: 500; display: flex; align-items: center; gap: 8px; }
  .card h3 { margin: 16px 0 8px; font-size: 14px; font-weight: 500; color: var(--secondary-text-color); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }
  .field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .field > label { font-size: 12px; color: var(--secondary-text-color); }
  .field .help { font-size: 11px; color: var(--secondary-text-color); line-height: 1.3; }
  textarea.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; min-height: 80px; resize: vertical; }
  input[type=text], input[type=search], input[type=number], input[type=password], select, textarea {
    width: 100%; padding: 8px 10px; font: inherit; font-size: 14px; color: var(--primary-text-color);
    background: var(--secondary-background-color, #f4f4f4); border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px; min-width: 0; }
  input:focus, select:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
  input[readonly] { opacity: .75; }
  .check { display: flex; align-items: flex-start; gap: 8px; font-size: 14px; padding: 4px 0; cursor: pointer; }
  .check input { margin-top: 3px; }
  .check small { display: block; color: var(--secondary-text-color); font-size: 11px; }
  button { font: inherit; font-size: 14px; padding: 8px 14px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc);
           background: var(--secondary-background-color, #f4f4f4); color: var(--primary-text-color); cursor: pointer; }
  button:hover:not(:disabled) { border-color: var(--primary-color); }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  button.danger { color: var(--error-color, #db4437); }
  button.small { padding: 4px 9px; font-size: 12px; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .row.grow > * { flex: 1; min-width: 120px; }
  .spacer { flex: 1; }
  .hint { font-size: 12px; color: var(--secondary-text-color); margin: 6px 0 0; line-height: 1.4; }
  .badge { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 10px; margin-right: 4px;
           background: var(--secondary-background-color); color: var(--secondary-text-color); white-space: nowrap; }
  .badge.warn { background: #ffecb3; color: #7a5200; }
  .badge.bad { background: #ffcdd2; color: #8a1c1c; }
  .badge.ok { background: #c8e6c9; color: #1b5e20; }
  @media (prefers-color-scheme: dark) { .badge.warn { background: #5d4a00; color: #ffe08a; }
    .badge.bad { background: #5a1f1f; color: #ffb4b4; } .badge.ok { background: #1f4a25; color: #b7e4bc; } }
  table.pins { width: 100%; border-collapse: collapse; font-size: 13px; }
  table.pins th { text-align: left; font-weight: 500; font-size: 12px; color: var(--secondary-text-color);
                  padding: 4px 6px; border-bottom: 1px solid var(--divider-color); }
  table.pins td { padding: 4px 6px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; }
  table.pins tr.used td:first-child { font-weight: 600; }
  table.pins tr.blocked { opacity: .55; }
  table.pins select { padding: 4px 8px; font-size: 13px; }
  .pinnote { font-size: 11px; color: var(--secondary-text-color); }
  .comp, .catalog { border: 1px solid var(--divider-color); border-radius: 10px; padding: 12px; margin-top: 12px; }
  .catalog summary { cursor: pointer; }
  .ent { border-top: 1px dashed var(--divider-color); padding-top: 8px; margin-top: 8px; }
  .frow { display: flex; flex-wrap: wrap; gap: 6px; align-items: flex-start; margin: 6px 0; }
  .frow select, .frow input, .frow textarea { flex: 1 1 140px; min-width: 0; }
  .mode { margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
  .tpl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; margin-top: 8px; }
  .tpl { text-align: left; padding: 12px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--card-background-color, transparent);
         color: inherit; cursor: pointer; font: inherit; }
  .tpl:hover { border-color: var(--primary-color); }
  .tpl[disabled] { opacity: .45; cursor: not-allowed; }
  .tpl b { display: block; margin-bottom: 4px; }
  .tpl small { display: block; opacity: .75; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  .chip { padding: 6px 12px; border: 1px solid var(--divider-color); border-radius: 16px; background: transparent; color: inherit; cursor: pointer; font: inherit; }
  .chip.on { background: var(--primary-color); color: #fff; border-color: var(--primary-color); }
  .steps li { margin: 4px 0; }
  .comp.bad { border-color: var(--error-color, #db4437); }
  .comp-head { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
  .comp-head .tname { flex: 1; min-width: 160px; }
  .comp-type { font-size: 12px; color: var(--secondary-text-color); }
  .out { position: sticky; top: 72px; }
  .tabs { display: flex; gap: 4px; margin-bottom: 8px; border-bottom: 1px solid var(--divider-color); }
  .tab { padding: 8px 14px; cursor: pointer; border-bottom: 2px solid transparent; font-size: 14px;
         color: var(--secondary-text-color); background: none; border-radius: 0; border-top: none; border-left: none; border-right: none; }
  .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
  pre.code { margin: 0; padding: 12px; max-height: calc(100vh - 330px); min-height: 220px; overflow: auto; font-size: 12.5px;
             line-height: 1.45; background: var(--code-editor-background-color, var(--secondary-background-color));
             border-radius: 8px; font-family: var(--code-font-family, ui-monospace, Menlo, Consolas, monospace);
             white-space: pre; tab-size: 2; user-select: text; }
  .msgs { margin-bottom: 8px; display: flex; flex-direction: column; gap: 4px; }
  .msg { font-size: 13px; padding: 6px 10px; border-radius: 8px; line-height: 1.35; }
  .msg.err { background: #ffcdd2; color: #7f1d1d; }
  .msg.warn { background: #fff3cd; color: #6b4e00; }
  .msg.ok { background: #c8e6c9; color: #1b5e20; }
  .deploybox { margin-top: 10px; } .deploybox summary { cursor: pointer; font-size: 13px; opacity: .8; }
  .deploybox input { width: 100%; margin: 4px 0 8px; }
  @media (prefers-color-scheme: dark) { .msg.err { background: #4a1a1a; color: #ffc9c9; }
    .msg.warn { background: #46380a; color: #ffe49a; } .msg.ok { background: #1c3d22; color: #bfe8c4; } }
  .banner { margin: 12px 16px 0; padding: 10px 14px; border-radius: 8px; background: #ffcdd2; color: #7f1d1d; }
  .empty { padding: 14px; text-align: center; color: var(--secondary-text-color); font-size: 13px; }
`;

// --- Mehrsprachigkeit: deutsche Texte sind die Schlüssel, das englische Wörterbuch kommt vom Backend (Befehl "i18n") ---
const I18N = { lang: "de", dict: {}, pats: [] };
function i18nSetDict(dict) {
  I18N.dict = { ...(dict || {}) };
  for (const [k, v] of Object.entries(dict || {})) { const kt = k.trim(); if (kt && kt !== k && !(kt in I18N.dict)) I18N.dict[kt] = v.trim(); }
  I18N.pats = Object.keys(I18N.dict).filter((k) => /\{\d+\}/.test(k)).map((k) => {
    const esc = k.split(/\{\d+\}/).map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const order = [...k.matchAll(/\{(\d+)\}/g)].map((m) => Number(m[1]));
    return { re: new RegExp(`^${esc.join("([\\s\\S]+?)")}$`), order, en: I18N.dict[k], w: k.replace(/\{\d+\}/g, "").length };
  }).sort((a, b) => b.w - a.w);
}
function tx(text) {
  if (I18N.lang === "de" || typeof text !== "string" || !text) return text;
  const hit = I18N.dict[text];
  if (hit !== undefined) return hit;
  for (const p of I18N.pats) {
    const m = p.re.exec(text);
    if (m) return p.en.replace(/\{(\d+)\}/g, (_, n) => { const idx = p.order.indexOf(Number(n)); return tx(m[idx + 1] ?? ""); });
  }
  const sym = /^([^\p{L}\p{N}"„(]+)(\S[\s\S]*)$/u.exec(text);
  if (sym) { const r = tx(sym[2]); if (r !== sym[2]) return sym[1] + r; }
  const sentences = text.split(/(?<=[.!?:]) +/);
  if (sentences.length > 1) {
    const out = sentences.map((x) => tx(x));
    if (out.some((x, i) => x !== sentences[i])) return out.join(" ");
  }
  const lead = /^(\s*)([\s\S]*?)(\s*)$/.exec(text);
  if (lead && (lead[1] || lead[3]) && lead[2]) return lead[1] + tx(lead[2]) + lead[3];
  return text;
}
const TR_ATTRS = new Set(["title", "placeholder", "aria-label", "alt"]);

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  let value;
  let hasValue = false;
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "value") { value = v; hasValue = true; }
    else if (k === "checked" || k === "disabled" || k === "selected" || k === "readOnly") el[k] = !!v;
    else el.setAttribute(k, v === true ? "" : TR_ATTRS.has(k) ? tx(String(v)) : String(v));
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(tx(String(kid))));
  }
  if (hasValue) el.value = value;
  return el;
}

const uid = () => (globalThis.crypto?.randomUUID?.() || Math.random().toString(16).slice(2) + Date.now().toString(16)).replace(/-/g, "").slice(0, 8);
const clone = (o) => JSON.parse(JSON.stringify(o));

class ESPHomeStudioPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.meta = null;
    this.projects = [];
    this.secrets = {};
    this.p = null;
    this.pid = null;
    this.dirty = false;
    this.out = { yaml: "", secrets: "", warnings: [], errors: [], ok: true };
    this.tab = "yaml";
    this.fatal = "";
    this._seq = 0;
    this._narrow = false;
    this._showPw = false;
    this.simple = true;
    try { this.simple = globalThis.localStorage?.getItem("esphome_studio_mode") !== "pro"; } catch { /* Speicher gesperrt */ }
    try { this._savedLang = globalThis.localStorage?.getItem("esphome_studio_lang") || ""; } catch { this._savedLang = ""; }
  }

  // Sprache: gespeicherte Wahl, sonst die Sprache von Home Assistant (Deutsch → Deutsch, sonst Englisch)
  _initialLang() {
    if (this._savedLang === "de" || this._savedLang === "en") return this._savedLang;
    const ha = String(this._hass?.locale?.language || this._hass?.language || "de").toLowerCase();
    return ha.startsWith("de") ? "de" : "en";
  }

  async _loadLang(lang) {
    I18N.lang = lang;
    i18nSetDict({});
    if (lang !== "de") {
      try { i18nSetDict((await this._ws("i18n")).dict); } catch { I18N.lang = "de"; }
    }
    document.documentElement.setAttribute("data-esphome-studio-lang", I18N.lang);
  }

  async _setLang(lang) {
    if (lang === I18N.lang) return;
    this._savedLang = lang;
    try { globalThis.localStorage?.setItem("esphome_studio_lang", lang); } catch { /* egal */ }
    await this._loadLang(lang);
    try {
      this.meta = await this._ws("meta");
      const c = await this._ws("catalog");
      this.catalog = { ...c, byId: Object.fromEntries(c.entries.map((e) => [e.id, e])) };
      this.boardCache = {};
      await this._ensureBoard(this.p.board);
    } catch { /* alte Daten bleiben */ }
    this._buildHead();
    this._renderAll();
    this._generate();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._menu) this._menu.hass = hass;
    if (first) this._boot();
  }

  set narrow(v) {
    this._narrow = v;
    if (this._menu) this._menu.narrow = v;
  }

  set panel(_) {}
  set route(_) {}

  // ------------------------------------------------------------ Backend ---
  _ws(type, payload = {}) {
    return this._hass.connection.sendMessagePromise({ type: `esphome_studio/${type}`, lang: I18N.lang, ...payload });
  }

  async _boot() {
    try {
      await this._loadLang(this._initialLang());
      this._buildHead();
      this.meta = await this._ws("meta");
      this.catalog = { domains: {}, entries: [], byId: {} };
      this._ws("catalog").then((c) => {
        this.catalog = { ...c, byId: Object.fromEntries(c.entries.map((e) => [e.id, e])) };
        if (this.p) this._renderAll();
      }).catch(() => {});
      await this._reloadList();
      if (this.projects.length) await this._open(this.projects[0].id, true);
      else await this._newProject();
    } catch (err) {
      this.fatal = tx("ESPHome Studio konnte nicht starten:") + ` ${err?.message || JSON.stringify(err)}`;
    }
    this._renderAll();
    this._generate();
  }

  async _reloadList() {
    const res = await this._ws("list");
    this.projects = res.projects;
    this.secrets = res.secrets || {};
  }

  async _open(id, silent = false) {
    const res = await this._ws("get", { project_id: id });
    this.p = res.project;
    delete this.p.updated;
    await this._ensureBoard(this.p.board);
    this.pid = id;
    this.dirty = false;
    if (!silent) { this._renderAll(); this._generate(); }
  }

  async _newProject(board) {
    const res = await this._ws("new", { board: board || "d1_mini" });
    this.p = res.project;
    await this._ensureBoard(this.p.board);
    this.pid = null;
    this.dirty = true;
  }

  async _save() {
    try {
      const res = await this._ws("save", { project: { ...this.p, id: this.pid || undefined } });
      this.pid = res.project.id;
      this.dirty = false;
      await this._reloadList();
      this._renderAll();
    } catch (err) {
      this._toast(`Speichern fehlgeschlagen: ${err?.message || tx("Fehler")}`);
    }
  }

  async _delete() {
    if (!this.pid) { await this._newProject(); this._renderAll(); this._generate(); return; }
    if (!confirm(tx(`Projekt „${this.p.name}“ wirklich löschen?`))) return;
    await this._ws("delete", { project_id: this.pid });
    await this._reloadList();
    if (this.projects.length) await this._open(this.projects[0].id, true);
    else await this._newProject();
    this._renderAll();
    this._generate();
  }

  async _duplicate() {
    const copy = clone(this.p);
    copy.name = this._suffixName(copy.name, "-kopie");
    copy.friendly_name = copy.friendly_name ? `${copy.friendly_name}${tx(" (Kopie)")}` : "";
    copy.api.key = (await this._ws("random", { kind: "api" })).value;
    copy.ota.password = (await this._ws("random", { kind: "ota" })).value;
    copy.wifi.ap_password = (await this._ws("random", { kind: "ap" })).value;
    this.p = copy;
    this.pid = null;
    this.dirty = true;
    this._renderAll();
    this._generate();
  }

  // Projekt als Datei sichern (ohne Schlüssel und Passwörter, die werden beim Laden neu erzeugt)
  _exportProject() {
    const proj = clone(this.p);
    if (proj.api) proj.api.key = "";
    if (proj.ota) proj.ota.password = "";
    if (proj.wifi) proj.wifi.ap_password = "";
    if (proj.web) proj.web.auth_password = "";
    delete proj.id;
    delete proj.updated;
    const file = `${proj.name || tx("projekt")}.esphome-studio.json`;
    this._download(file, JSON.stringify({ format: "esphome-studio-project", version: this.meta?.version || "", project: proj }, null, 2));
    this._toast("Projekt exportiert. Schlüssel und Passwörter sind nicht enthalten.");
  }

  async _importProjectFile(file) {
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const src = data?.format === "esphome-studio-project" ? data.project : null;
      if (!src || typeof src !== "object" || !Array.isArray(src.components) || typeof src.board !== "string") throw new Error("format");
      const base = (await this._ws("new", { board: src.board })).project;
      const merge = (a, b) => {
        for (const [k, v] of Object.entries(b)) {
          if (v && typeof v === "object" && !Array.isArray(v) && a[k] && typeof a[k] === "object" && !Array.isArray(a[k])) merge(a[k], v);
          else a[k] = v;
        }
        return a;
      };
      const proj = merge(base, src);
      proj.api = proj.api || {};
      proj.ota = proj.ota || {};
      proj.wifi = proj.wifi || {};
      proj.api.key = (await this._ws("random", { kind: "api" })).value;
      proj.ota.password = (await this._ws("random", { kind: "ota" })).value;
      proj.wifi.ap_password = (await this._ws("random", { kind: "ap" })).value;
      if (proj.web && proj.web.auth) proj.web.auth_password = "";
      delete proj.id;
      this.p = proj;
      this.pid = null;
      await this._ensureBoard(this.p.board);
      this.dirty = true;
      this._wizardOff = true;
      this._renderAll();
      this._generate();
      this._toast("Projekt geladen. Neue Schlüssel wurden erzeugt, bitte speichern.");
    } catch {
      this._toast("Die Datei ist kein ESPHome-Studio-Projekt.");
    }
  }

  // WLAN-Zugangsdaten zuerst speichern, dann neu erzeugen (der Generator liest sie aus dem Speicher)
  _saveSecretsSoon() {
    clearTimeout(this._secTimer);
    this._secTimer = setTimeout(async () => {
      try {
        const res = await this._ws("set_secrets", { secrets: { wifi_ssid: this.secrets.wifi_ssid || "", wifi_password: this.secrets.wifi_password || "", ap_password: this.secrets.ap_password || "" } });
        this.secrets = res.secrets || this.secrets;
      } catch (err) {
        this._toast(`Zugangsdaten konnten nicht gespeichert werden: ${err?.message || tx("Fehler")}`);
      }
      this._generate();
    }, 400);
  }

  _suffixName(name, suffix) {
    return (name + suffix).slice(0, 31).replace(/-+$/, "");
  }

  // ------------------------------------------------------------ Zustand ---
  _changed(structural = false) {
    this.dirty = true;
    if (structural) this._renderAll();
    else this._updateDirty();
    this._generate();
  }

  _generate() {
    clearTimeout(this._genTimer);
    this._genTimer = setTimeout(async () => {
      const seq = ++this._seq;
      try {
        const res = await this._ws("generate", { project: this.p });
        if (seq !== this._seq) return;
        this.out = res;
      } catch (err) {
        this.out = { yaml: "", secrets: "", warnings: [], errors: [`${tx("Fehler beim Erzeugen:")} ${err?.message || err}`], ok: false };
      }
      this._renderOutput();
    }, 150);
  }

  _toast(text) {
    this._toastText = text;
    if (this._banner) { this._banner.textContent = tx(text); this._banner.style.display = "block"; }
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { if (this._banner) this._banner.style.display = "none"; }, 6000);
  }

  type(key) { return this.meta.types.find((t) => t.type === key); }
  // Beschreibung eines Bausteins; Katalog-Bausteine kommen aus dem Katalog
  spec(c) {
    if (c.type !== "generic") return this.type(c.type);
    const e = this.catalog?.byId?.[c.cat];
    if (!e) return { label: tx(`Unbekannt (${c.cat})`), pins: [], options: [], platforms: [] };
    const uart = e.bus === "uart" ? [
      { key: "_rx", label: tx("RX (Daten vom Sensor)"), kind: "in", required: true },
      { key: "_tx", label: tx("TX (zum Sensor, optional)"), kind: "out", required: false }] : [];
    return { label: e.label, pins: [...uart, ...e.pins.map((p) => ({ key: p.key, label: p.label, kind: p.kind, required: p.required }))],
      needs_i2c: e.bus === "i2c", needs_spi: e.bus === "spi", options: [], platforms: e.platforms || [] };
  }
  board() { return this.boardCache?.[this.p.board]; }

  async _ensureBoard(key) {
    this.boardCache = this.boardCache || {};
    if (this.boardCache[key]) return;
    try {
      this.boardCache[key] = (await this._ws("board", { key })).board;
    } catch {
      // Board gibt es nicht mehr (z. B. aus einem alten Projekt): auf den Standard zurückfallen
      const fallback = "d1_mini";
      if (key === this.p.board) { this.p.board = fallback; this._toast("Das gespeicherte Board gibt es nicht mehr. Ersatz: Wemos D1 Mini."); }
      await this._ensureBoard(fallback);
    }
  }
  _needsI2c() { return this.p.components.some((c) => this.spec(c)?.needs_i2c); }
  _needsSpi() { return this.p.components.some((c) => this.spec(c)?.needs_spi); }

  _usage() {
    const u = {};
    for (const c of this.p.components) {
      const spec = this.spec(c);
      if (!spec) continue;
      for (const ps of spec.pins) {
        const pid = c.pins?.[ps.key];
        if (pid) u[pid] = { comp: c, pin: ps };
      }
    }
    if (this._needsI2c()) {
      for (const k of ["sda", "scl"]) if (this.p.i2c?.[k]) u[this.p.i2c[k]] = { i2c: k };
    }
    if (this._needsSpi()) {
      const sp = { ...(this.board()?.spi_default || {}), ...(this.p.spi || {}) };
      for (const k of ["clk", "mosi", "miso"]) if (sp[k]) u[sp[k]] = { i2c: `SPI ${k}` };
    }
    return u;
  }

  _incompat(pin, kind) {
    if (pin.flash) return "Flash";
    if (pin.adc_only) return kind === "adc" ? null : "nur Analog";
    if (kind === "adc" && !pin.adc) return "kein ADC";
    if (["out", "pwm", "io"].includes(kind) && pin.input_only) return "nur Eingang";
    if (kind === "pwm" && pin.no_pwm) return "kein PWM";
    return null;
  }

  _uniqueName(base) {
    const names = new Set(this.p.components.map((c) => c.name.toLowerCase()));
    if (!names.has(base.toLowerCase())) return base;
    let n = 2;
    while (names.has(`${base} ${n}`.toLowerCase())) n++;
    return `${base} ${n}`;
  }

  _addComponent(typeKey, pins = {}) {
    const spec = this.type(typeKey);
    const options = {};
    for (const o of spec.options) options[o.key] = o.default;
    this.p.components.push({ uid: uid(), type: typeKey, name: this._uniqueName(tx(DEFAULT_NAMES[typeKey]) || spec.label), pins, options });
  }

  _removeComponent(c) {
    this.p.components = this.p.components.filter((x) => x !== c);
    for (const o of this.p.components) {
      for (const [k, v] of Object.entries(o.options || {})) if (v === c.uid) o.options[k] = "";
    }
  }

  async _changeBoard(key) {
    const old = this.board();
    await this._ensureBoard(key);
    this.p.board = key;
    const b = this.board();
    const ids = new Set(b.pins.map((p) => p.id));
    for (const c of this.p.components) {
      for (const [k, v] of Object.entries(c.pins || {})) if (v && !ids.has(v)) c.pins[k] = "";
    }
    this.p.spi = {};
    if (!ids.has(this.p.i2c?.sda) || !ids.has(this.p.i2c?.scl) || old.platform !== b.platform) this.p.i2c = { ...b.i2c_default };
    this._changed(true);
  }

  // ------------------------------------------------------------ Rendern ---
  connectedCallback() {
    if (this._built) return;
    this._built = true;
    const style = document.createElement("style");
    style.textContent = CSS;
    this._menu = document.createElement("ha-menu-button");
    this._menu.hass = this._hass;
    this._menu.narrow = this._narrow;
    this._banner = h("div", { class: "banner", style: "display:none" });
    this._left = h("div", { class: "col" });
    this._outEl = h("div", { class: "card out" });
    this._layout = h("div", { class: "layout" }, this._left, h("div", { class: "col" }, this._outEl));
    this._head = h("div", { class: "toolbar" });
    this._buildHead();
    this.shadowRoot.append(style, this._head, this._banner, this._layout);
    if (this.meta && this.p) { this._renderAll(); this._generate(); }
    else this._left.append(h("div", { class: "card" }, this.fatal || "Lade …"));
  }

  _buildHead() {
    if (!this._head) return;
    this._head.replaceChildren(this._menu, h("div", { class: "title" }, "ESPHome Studio"), h("span", { class: "ver" }, `v${this.meta?.version || ""}`),
      h("label", { class: "mode", title: "Der einfache Modus zeigt nur das Wichtigste. Profi-Optionen sind dann ausgeblendet." },
        this._modeBox = h("input", { type: "checkbox", checked: this.simple, onChange: (e) => this._setSimple(e.target.checked) }), "Einfacher Modus"),
      h("label", { class: "mode lang", title: "Sprache / Language" }, "🌐 ",
        this._langSel = h("select", { class: "langsel", onChange: (e) => this._setLang(e.target.value) },
          h("option", { value: "de" }, "Deutsch"), h("option", { value: "en" }, "English"))));
    this._langSel.value = I18N.lang;
  }

  _setSimple(v) {
    this.simple = v;
    try { globalThis.localStorage?.setItem("esphome_studio_mode", v ? "simple" : "pro"); } catch { /* egal */ }
    if (this._modeBox) this._modeBox.checked = v;
    this._renderAll();
  }

  _renderAll() {
    if (!this._built) return;
    const scroll = this.scrollTop;
    this._head.querySelector(".ver").textContent = `v${this.meta?.version || ""}`;
    this._left.replaceChildren();
    if (this.fatal) {
      this._left.append(h("div", { class: "card" }, this.fatal));
      return;
    }
    this._left.append(...[this._secWizard(), this._secProject(), this._importOpen ? this._secImport() : null, this._importReport ? this._secReport() : null,
      this._secDevice(), this._secNetwork(), this.simple ? null : this._secPins(), this._secComponents(), this._secNext()].filter(Boolean));
    this._renderOutput();
    this.scrollTop = scroll;
  }

  // --- Bausteine ---
  _field(label, control, help) {
    return h("div", { class: "field" }, h("label", {}, label), control, help ? h("div", { class: "help" }, help) : null);
  }

  _text(path, label, opts = {}) {
    const el = h("input", {
      type: opts.password && !this._showPw ? "password" : "text", value: this._get(path) ?? "", placeholder: opts.placeholder || "",
      readOnly: opts.readOnly, autocomplete: "off",
      onInput: (e) => { this._setPath(path, e.target.value); if (opts.onInput) opts.onInput(e.target.value); this._changed(false); },
    });
    return this._field(label, el, opts.help);
  }

  _check(path, label, help, structural = false) {
    return h("label", { class: "check" },
      h("input", { type: "checkbox", checked: !!this._get(path),
        onChange: (e) => { this._setPath(path, e.target.checked); this._changed(structural); } }),
      h("span", {}, label, help ? h("small", {}, help) : null));
  }

  _select(path, label, choices, help, structural = false) {
    const el = h("select", { onChange: (e) => { this._setPath(path, e.target.value); this._changed(structural); } },
      choices.map((c) => { const [v, t] = Array.isArray(c) ? c : [c, c]; return h("option", { value: v }, t); }));
    el.value = this._get(path) ?? "";
    return this._field(label, el, help);
  }

  _get(path) { return path.split(".").reduce((o, k) => (o == null ? o : o[k]), this.p); }

  _setPath(path, value) {
    const keys = path.split(".");
    let o = this.p;
    for (const k of keys.slice(0, -1)) { o[k] = o[k] ?? {}; o = o[k]; }
    o[keys.at(-1)] = value;
  }

  _updateDirty() {
    const d = this._left.querySelector(".dirty");
    if (d) { d.textContent = tx(this.dirty ? "Nicht gespeichert" : "Gespeichert"); d.className = `badge dirty ${this.dirty ? "warn" : "ok"}`; }
  }

  // --- Start-Assistent (Einfach-Modus) ---
  _autoPins(spec, extraUsed = new Set()) {
    const b = this.board();
    const used = new Set([...Object.keys(this._usage()), ...extraUsed]);
    if (spec.needs_i2c) { for (const k of ["sda", "scl"]) if (this.p.i2c?.[k]) used.add(this.p.i2c[k]); }
    const out = {};
    for (const ps of spec.pins) {
      const bad = (x) => used.has(x.id) || this._incompat(x, ps.kind) || x.strapping || x.uart || x.usb || x.psram || x.flash
        || (["out", "pwm", "io"].includes(ps.kind) && x.boot_high);
      const pin = b.pins.find((x) => !bad(x));
      if (!pin) return null;
      out[ps.key] = pin.id;
      used.add(pin.id);
    }
    return out;
  }

  _tplUsable(tpl) {
    const b = this.board();
    if (!b) return false;
    const taken = new Set();
    for (const c of tpl.comps) {
      const spec = this.type(c.type);
      if (!spec || !spec.platforms.includes(b.platform) || (spec.not_chips || []).includes(b.chip)) return false;
      if (spec.needs_i2c) {
        const bad = (id) => { const pin = b.pins.find((x) => x.id === id); return !pin || pin.uart || pin.flash || pin.strapping || pin.usb || pin.psram || pin.input_only || pin.adc_only; };
        if (bad(b.i2c_default?.sda) || bad(b.i2c_default?.scl)) return false;
      }
      const pins = this._autoPins(spec, taken);
      if (!pins) return false;
      Object.values(pins).forEach((id) => taken.add(id));
    }
    return true;
  }

  _applyTemplate(tpl) {
    const created = [];
    for (const c of tpl.comps) {
      const spec = this.type(c.type);
      const pins = this._autoPins(spec, new Set(created.flatMap((x) => Object.values(x.pins))));
      this._addComponent(c.type, pins || {});
      const comp = this.p.components.at(-1);
      comp.name = this._uniqueName(tx(c.name));
      for (const [k, v] of Object.entries(c.options || {})) {
        const o = spec.options.find((x) => x.key === k);
        if (!o) continue;
        if (v === "@0") comp.options[k] = created[0]?.uid || "";
        else if (!o.choices || o.choices.includes(v)) comp.options[k] = v;
      }
      created.push(comp);
    }
    if (!this.pid) {
      if (!this.p.name || this.p.name === "neues-geraet" || this.p.name === "new-device") this.p.name = tx(tpl.name);
      if (!this.p.friendly_name || this.p.friendly_name === "Neues Gerät" || this.p.friendly_name === "New device") this.p.friendly_name = tx(tpl.friendly);
    }
    this._wizardOff = true;
    this._changed(true);
  }

  _secWizard() {
    if (!this.simple || this.p.components.length || this._wizardOff) return null;
    const b = this.board();
    const hasWifi = !!(this.secrets.wifi_ssid && this.secrets.wifi_password);
    return h("div", { class: "card wizard" }, h("h2", {}, "Los geht’s – in drei Schritten"),
      h("p", { class: "hint" }, "Hier entsteht die Konfiguration für dein ESP-Gerät. Du musst nichts von YAML wissen: Wähle Board und Vorlage, am Ende kopierst du das Ergebnis nach ESPHome."),
      h("h3", {}, "1. Welches Board hast du?"),
      h("div", { class: "chips" },
        QUICK_BOARDS.filter(([k]) => this.meta.boards.some((x) => x.key === k)).map(([k, label]) =>
          h("button", { class: `chip ${this.p.board === k ? "on" : ""}`, onClick: () => this._changeBoard(k) }, label))),
      h("p", { class: "hint" }, "Anderes Board? Unten in der Karte „Gerät“ gibt es eine Suche mit über 500 Boards. Weißt du es nicht, nimm ESP32 DevKit oder Wemos D1 Mini."),
      h("h3", {}, "2. Was soll das Gerät tun?"),
      h("div", { class: "tpl-grid" }, TEMPLATES.map((t) => {
        const ok = this._tplUsable(t);
        return h("button", { class: "tpl", disabled: !ok, title: ok ? "" : `Mit ${b?.label || "diesem Board"} nicht möglich`, onClick: () => this._applyTemplate(t) },
          h("b", {}, `${t.icon} ${t.title}`), h("small", {}, ok ? t.text : "Mit diesem Board nicht möglich."));
      })),
      h("h3", {}, "3. WLAN eintragen"),
      h("p", { class: "hint" }, hasWifi ? "✓ WLAN-Name und Passwort sind schon gespeichert." : "Trage unten in der Karte „WLAN, Secrets & Sicherheit“ deinen WLAN-Namen und das Passwort ein. Das Gerät braucht sie, um sich zu verbinden."),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onClick: () => { this._wizardOff = true; this._renderAll(); } }, "Ohne Vorlage starten")));
  }

  _secNext() {
    if (!this.simple || !this.p.components.length) return null;
    return h("details", { class: "card", open: true },
      h("summary", {}, h("strong", {}, "Fertig? So geht’s weiter")),
      h("ol", { class: "steps hint" },
        h("li", {}, "Prüfe oben bei jedem Baustein den gewählten Pin. Das Studio hat freie Pins ausgesucht, sie müssen zu deiner Verdrahtung passen."),
        h("li", {}, "Trage das WLAN ein und achte rechts auf rote Fehler. Erst ohne Fehler lässt sich das Ergebnis kopieren."),
        h("li", {}, "Rechts auf „Kopieren“ klicken, in ESPHome ein neues Gerät anlegen und den Inhalt einfügen."),
        h("li", {}, "Die Zeilen aus dem Reiter „secrets.yaml“ in die secrets.yaml von ESPHome einfügen (WLAN nur einmal)."),
        h("li", {}, "In ESPHome „Installieren“ wählen. Das erste Mal per USB, danach geht es per WLAN.")),
      h("p", { class: "hint" }, "Mehr Einstellungen (Pin-Tabelle, YAML-Import, Zusatz-YAML)? Oben rechts den „Einfachen Modus“ abschalten."));
  }

  // --- Projekte ---
  _secProject() {
    const sel = h("select", { onChange: async (e) => { if (e.target.value) await this._open(e.target.value); } },
      this.pid ? null : h("option", { value: "" }, "(neues Projekt)"),
      this.projects.map((p) => h("option", { value: p.id }, `${p.friendly_name || p.name} · ${p.name}`)));
    sel.value = this.pid || "";
    return h("div", { class: "card" },
      h("h2", {}, "Projekte", h("span", { class: `badge dirty ${this.dirty ? "warn" : "ok"}` }, this.dirty ? "Nicht gespeichert" : "Gespeichert")),
      h("div", { class: "row grow" }, sel),
      h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "primary", onClick: () => this._save() }, "Speichern"),
        h("button", { onClick: async () => { await this._newProject(); this._renderAll(); this._generate(); } }, "Neu"),
        h("button", { onClick: () => this._duplicate() }, "Duplizieren"),
        h("button", { title: "Projekt als Datei sichern (ohne Schlüssel und Passwörter)", onClick: () => this._exportProject() }, "Exportieren"),
        h("button", { title: "Projekt aus einer Datei laden", onClick: () => this._projFile.click() }, "Aus Datei laden"),
        this._projFile = h("input", { type: "file", accept: ".json,application/json", style: "display:none",
          onChange: (e) => { this._importProjectFile(e.target.files[0]); e.target.value = ""; } }),
        h("button", { title: "Bestehende Geräte-YAML aus dem ESPHome Device Builder oder Ordner laden und auf den aktuellen Stand bringen",
          onClick: () => { this._importOpen = true; this._renderAll(); this._loadSourceList(); this._loadStoreInfo(); } }, "Aus ESPHome laden"),
        this.simple ? null : h("button", { onClick: () => { this._importOpen = !this._importOpen; this._renderAll(); if (this._importOpen) this._loadStoreInfo(); } }, "YAML importieren"),
        h("span", { class: "spacer" }),
        h("button", { class: "danger", onClick: () => this._delete() }, "Löschen")),
      h("p", { class: "hint" }, "Projekte bleiben in Home Assistant gespeichert. Die erzeugte YAML-Datei kopierst du in ESPHome."));
  }

  // --- Import ---
  _secImport() {
    const yaml = h("textarea", { class: "mono", rows: "12", placeholder: "Inhalt einer bestehenden ESPHome-YAML hier einfügen …",
      value: this._importText || "", onInput: (e) => { this._importText = e.target.value; } });
    const sec = h("textarea", { class: "mono", rows: "4", placeholder: "wifi_ssid: \"…\"\nwifi_password: \"…\"\napi_key: …",
      value: this._importSecrets || "", onInput: (e) => { this._importSecrets = e.target.value; } });
    const src = this._sourceBox();
    const store = this._storeBox();
    const norm = h("label", { class: "check" },
      h("input", { type: "checkbox", checked: this._importNormalize !== false,
        onChange: (e) => { this._importNormalize = e.target.checked; } }),
      h("span", {}, "Namen der Diagnose-Entitäten und Lichteffekte auf den Studio-Standard vereinheitlichen",
        h("small", {}, "z. B. „Reboot“ wird „Neustart“. In Home Assistant ändern sich dadurch die Entity-IDs. Ohne Haken bleiben deine Namen.")));
    if (this.simple) {
      return h("div", { class: "card" }, h("h2", {}, "Bestehende YAML importieren"), src, store, norm,
        h("div", { class: "row", style: "margin-top:10px" }, h("button", { onClick: () => { this._importOpen = false; this._renderAll(); } }, "Abbrechen")),
        this._importError ? h("div", { class: "msg err" }, this._importError) : null);
    }
    return h("div", { class: "card" }, h("h2", {}, "Bestehende YAML importieren"), src,
      h("p", { class: "hint" }, "Das Studio übernimmt Gerät, WLAN, Sicherheit und alles, was es selbst erzeugen kann (Schalter, Lichter, Taster, Sensoren …). " +
        "Alles andere (Skripte, Lambdas, Display, eigene Sensoren) bleibt unverändert im „Zusatz-YAML“. Kommentare gehen verloren."),
      this._field("ESPHome-YAML", yaml),
      this._field("secrets.yaml (optional)", sec, "Damit werden !secret-Werte (WLAN, API-Schlüssel, Passwörter) aufgelöst. Ohne sie bleiben Schlüssel leer."),
      norm,
      h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "primary", onClick: () => this._doImport() }, "Importieren"),
        h("button", { onClick: () => { this._importOpen = false; this._renderAll(); } }, "Abbrechen")),
      store,
      this._importError ? h("div", { class: "msg err" }, this._importError) : null);
  }

  _sourceBox() {
    const L = this._srcList;
    const body = [];
    if (this._srcBusy) body.push(h("p", { class: "hint" }, "Lade …"));
    else if (L && L.items.length) {
      const sel = h("select", { onChange: (e) => { this._srcPick = e.target.value; } },
        ...L.items.map((d) => h("option", { value: d.configuration, selected: d.configuration === (this._srcPick || L.items[0].configuration) },
          d.friendly_name ? `${d.friendly_name} · ${d.configuration}` : d.configuration)));
      body.push(h("div", { class: "row grow" }, sel,
        h("button", { class: "primary", onClick: () => this._loadSource(this._srcPick || L.items[0].configuration) }, "Laden")),
        h("p", { class: "hint" }, L.source === "dashboard"
          ? "Quelle: ESPHome Device Builder. Die Werte der Secrets verrät der Device Builder nicht; WLAN und Schlüssel müssen ggf. ergänzt werden."
          : "Quelle: ESPHome-Ordner. Benutzte Secrets werden aus der secrets.yaml mit übernommen."));
    } else if (L) body.push(h("p", { class: "hint" }, "Keine Geräte-YAMLs gefunden."));
    if (this._srcError) body.push(h("div", { class: "msg err" }, this._srcError));
    body.push(h("button", { onClick: () => this._loadSourceList() }, "Liste aktualisieren"));
    if (this._srcLoaded && (this._importText || "").trim()) body.push(this._secretReview());
    return h("div", { class: "field" }, h("label", {}, "Aus ESPHome laden"), ...body);
  }

  _storeBox() {
    const n = (this._storeKeys || []).length;
    const text = h("textarea", { class: "mono", rows: "5", placeholder: "wifi_ssid: \"…\"\napi_key: …\nota_password: …",
      value: this._storeText || "", onInput: (e) => { this._storeText = e.target.value; } });
    const ok = h("input", { type: "checkbox", checked: !!this._storeOk, onChange: (e) => { this._storeOk = e.target.checked; this._renderAll(); } });
    const save = h("button", { class: "primary", onClick: () => this._storeSave() }, "Im Secrets-Speicher sichern");
    if (!this._storeOk) save.disabled = true;
    return h("details", { class: "field", open: !!this._storeOpen || undefined,
      onToggle: (e) => { this._storeOpen = e.target.open; } },
      h("summary", {}, `${tx("Secrets-Speicher (optional, auf eigene Gefahr)")}${n ? ` · ${n} ${tx("Einträge")}` : ""}`),
      h("p", { class: "hint" }, "Hier kannst du deine ganze secrets.yaml einmal ablegen. Bei jedem Import werden die benutzten !secret-Werte daraus ergänzt, auch gemeinsame API-Schlüssel und Passwörter. Die Werte liegen im Klartext im Speicher von Home Assistant (.storage, also auch in Backups). Das Panel zeigt sie nie wieder an."),
      text,
      h("label", { class: "check" }, ok, "Ich verstehe das Risiko und möchte meine Secrets hier speichern"),
      h("div", { class: "row", style: "margin-top:10px" }, save,
        n ? h("button", { class: "danger", onClick: () => this._storeClear() }, "Secrets-Speicher leeren") : null),
      this._storeError ? h("div", { class: "msg err" }, this._storeError) : null);
  }

  async _loadStoreInfo() {
    try { this._storeKeys = (await this._ws("secret_store", { action: "info" })).keys; } catch { this._storeKeys = []; }
    this._renderAll();
  }

  async _storeSave() {
    this._storeError = "";
    try {
      this._storeKeys = (await this._ws("secret_store", { action: "set", text: this._storeText || "" })).keys;
      this._storeText = ""; this._storeOk = false;
    } catch (err) { this._storeError = err?.message || tx("Fehler"); }
    this._renderAll();
  }

  async _storeClear() {
    this._storeError = "";
    try { this._storeKeys = (await this._ws("secret_store", { action: "clear" })).keys; } catch (err) { this._storeError = err?.message || tx("Fehler"); }
    this._renderAll();
  }

  async _loadSourceList() {
    this._srcBusy = true; this._srcError = ""; this._renderAll();
    try {
      this._srcList = await this._ws("source_list");
      this._srcPick = this._srcList.items[0]?.configuration || "";
    } catch (err) {
      this._srcList = null;
      this._srcError = err?.message || tx("Fehler");
    }
    this._srcBusy = false; this._renderAll();
  }

  async _loadSource(configuration) {
    this._srcError = ""; this._srcBusy = true; this._renderAll();
    try {
      const r = await this._ws("source_get", { configuration });
      this._importText = r.yaml || "";
      this._importSecrets = r.secrets || "";
      this._srcLoaded = configuration;
    } catch (err) {
      this._srcError = err?.message || tx("Fehler");
      this._srcBusy = false; this._renderAll();
      return;
    }
    this._srcBusy = false; this._renderAll();
  }

  // Welche !secret-Schlüssel nutzt die YAML, und welche Werte sind schon bekannt?
  _secretStatus() {
    const keys = [...new Set([...(this._importText || "").matchAll(/!secret\s+([A-Za-z0-9_]+)/g)].map((m) => m[1]))];
    const given = new Set([...(this._importSecrets || "").matchAll(/^\s*([A-Za-z0-9_]+)\s*:\s*\S/gm)].map((m) => m[1]));
    const have = this.secrets || {};
    return keys.map((k) => ({
      key: k,
      known: given.has(k) || (this._storeKeys || []).includes(k) || (k === "wifi_ssid" && !!have.wifi_ssid) || (k === "wifi_password" && !!have.wifi_password),
    }));
  }

  _secretReview() {
    const st = this._secretStatus();
    const parts = [h("p", { class: "hint" }, `„${this._srcLoaded}“ ist geladen. Prüfe die Secrets, dann importieren.`)];
    if (st.length) {
      parts.push(h("ul", {}, st.map((x) => h("li", {}, `${x.key}: ${x.known ? tx("bekannt") : tx("fehlt")}`))));
      if (st.some((x) => !x.known)) {
        parts.push(h("p", { class: "hint" }, "Fehlende Werte als Zeilen „schlüssel: wert“ aus deiner secrets.yaml einfügen. Es werden nur die benutzten Schlüssel übernommen."));
      }
    } else parts.push(h("p", { class: "hint" }, "Die YAML benutzt keine Secrets."));
    if (this.simple) {
      parts.push(h("textarea", { class: "mono", rows: "4", placeholder: "api_key: …\nota_password: …", value: this._importSecrets || "",
        onInput: (e) => { this._importSecrets = e.target.value; } }));
      parts.push(h("div", { class: "row", style: "margin-top:10px" },
        h("button", { class: "primary", onClick: () => this._doImport() }, "Importieren")));
    }
    return h("div", { class: "field" }, ...parts);
  }

  async _doImport() {
    this._importError = "";
    if (!(this._importText || "").trim()) { this._importError = "Bitte zuerst die YAML einfügen."; this._renderAll(); return; }
    let res;
    try {
      res = await this._ws("import", { yaml: this._importText, secrets: this._importSecrets || "", normalize: this._importNormalize !== false });
    } catch (err) {
      this._importError = `Import fehlgeschlagen: ${err?.message || tx("Fehler")}`;
      this._renderAll();
      return;
    }
    if (!res.ok) { this._importError = res.errors.join(" "); this._renderAll(); return; }
    this.p = res.project;
    await this._ensureBoard(this.p.board);
    this.pid = null;
    this.dirty = true;
    const notes = [...res.notes];
    const found = res.secrets || {};
    const have = this.secrets || {};
    if (found.wifi_ssid || found.wifi_password) {
      if (!have.wifi_ssid && !have.wifi_password) {
        try {
          const r = await this._ws("set_secrets", { secrets: { wifi_ssid: found.wifi_ssid || "", wifi_password: found.wifi_password || "" } });
          this.secrets = r.secrets || this.secrets;
          notes.push("WLAN-Name und -Passwort aus der YAML wurden als Zugangsdaten gespeichert.");
        } catch { /* wird unten gemeldet */ }
      } else if (found.wifi_ssid !== have.wifi_ssid || found.wifi_password !== have.wifi_password) {
        notes.push("Die WLAN-Zugangsdaten in der YAML weichen von den gespeicherten ab. Das Studio benutzt die gespeicherten (Bereich „WLAN“).");
      }
    }
    if (found.ap_password) {
      if (!have.ap_password) {
        try {
          const r = await this._ws("set_secrets", { secrets: { ap_password: found.ap_password } });
          this.secrets = r.secrets || this.secrets;
          notes.push("Das gemeinsame Hotspot-Passwort aus der YAML wurde als Zugangsdatum gespeichert.");
        } catch { /* wird unten gemeldet */ }
      } else if (found.ap_password !== have.ap_password) {
        notes.push("Das Hotspot-Passwort in der YAML weicht vom gespeicherten ab. Das Studio benutzt das gespeicherte (Bereich „WLAN“).");
      }
    }
    if (res.project.use_secrets && res.project.api?.encryption) {
      notes.push("Das Studio nennt die Schlüssel im secrets.yaml-Block nach dem Gerät (z. B. gerät_api_key). Die Zeilen aus dem Reiter „secrets.yaml“ bitte in deine secrets.yaml übernehmen.");
    } else if (res.project.use_secrets) {
      notes.push("Die Zugangsdaten stehen als Einträge im Reiter „secrets.yaml“. Fehlende Zeilen bitte in deine secrets.yaml übernehmen.");
    }
    const empty = this._srcLoaded ? this._secretStatus().filter((x) => !x.known).map((x) => x.key) : [];
    if (empty.length) notes.push(`${tx("Diese Secrets sind leer geblieben und müssen ergänzt werden:")} ${empty.join(", ")}`);
    this._srcLoaded = "";
    this._importReport = { notes, unmapped: res.unmapped, extra: !!res.project.extra_yaml };
    this._importOpen = false;
    this._importText = "";
    this._importSecrets = "";
    this._renderAll();
    this._generate();
  }

  _secReport() {
    const r = this._importReport;
    return h("div", { class: "card" }, h("h2", {}, "Import abgeschlossen"),
      h("p", { class: "hint" }, `${this.p.components.length} Komponenten wurden übernommen.${r.extra ? " Der Rest steht unter „Gerät“ im Zusatz-YAML." : ""}`),
      r.unmapped.length ? h("div", {}, h("strong", {}, "Unverändert als Zusatz-YAML behalten:"),
        h("ul", {}, r.unmapped.map((u) => h("li", {}, u)))) : null,
      r.notes.length ? h("div", {}, h("strong", {}, "Hinweise:"), h("ul", {}, r.notes.map((n) => h("li", {}, n)))) : null,
      h("div", { class: "row" }, h("button", { onClick: () => { this._importReport = null; this._renderAll(); } }, "Ausblenden")));
  }

  // --- Gerät ---
  _secDevice() {
    const boardSel = h("select", { onChange: (e) => this._changeBoard(e.target.value) });
    const count = h("small", {});
    const fill = (filter) => {
      const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
      const match = (b) => b.key === this.p.board || words.every((w) => `${b.label} ${b.key} ${b.group} ${b.board}`.toLowerCase().includes(w));
      const groups = new Map();
      let n = 0;
      for (const b of this.meta.boards) {
        if (!match(b)) continue;
        n++;
        if (!groups.has(b.group)) groups.set(b.group, []);
        groups.get(b.group).push(b);
      }
      boardSel.replaceChildren(...[...groups].map(([g, list]) => h("optgroup", { label: g },
        list.map((b) => h("option", { value: b.key }, b.label)))));
      boardSel.value = this.p.board;
      count.textContent = words.length ? tx(`${n} Treffer von ${this.meta.boards.length} Boards`) : tx(`${this.meta.boards.length} Boards`);
    };
    const search = h("input", { type: "search", class: "board-search", placeholder: "Board suchen, z. B. d1, cb2s, esp32-s3, pico, wb2s …",
      onInput: (e) => fill(e.target.value) });
    fill("");
    const boardField = h("div", {}, boardSel, h("div", { style: "margin-top:6px" }, search), count);
    const b = this.board();
    const nameOk = /^[a-z0-9]([a-z0-9-]{0,29}[a-z0-9])?$/.test(this.p.name || "");
    return h("div", { class: "card" }, h("h2", {}, "Gerät"),
      h("div", { class: "grid" },
        this._text("name", "Gerätename (Hostname)", { help: nameOk ? "Kleinbuchstaben, Ziffern, Bindestriche." : "⚠ Nur Kleinbuchstaben, Ziffern und Bindestriche, höchstens 31 Zeichen." }),
        this._text("friendly_name", "Anzeigename in Home Assistant"),
        this._field("Board", boardField, b?.note || ""),
        !this.simple && b?.platform === "esp32"
          ? this._select("framework", "Framework", [["esp-idf", "ESP-IDF (empfohlen)"], ["arduino", "Arduino"]]) : null,
        this.simple ? null : this._select("log_level", "Log-Stufe", LOG_LEVELS),
        this.simple ? null : this._text("comment", "Beschreibung (comment)", { placeholder: "Aquarium im Wohnzimmer", help: "Erscheint in ESPHome und Home Assistant als Gerätebeschreibung." }),
        !this.simple && b?.platform === "esp8266"
          ? this._select("flash_mode", "Flash-Modus (ESP8266)", [["", "Standard"], ["dout", "dout"], ["dio", "dio"], ["qio", "qio"], ["qout", "qout"]], "dout hilft bei manchen Boards, die nach dem Flashen nicht starten.") : null,
        !this.simple && b?.platform === "esp8266"
          ? this._select("early_pin_init", "Pins früh initialisieren (ESP8266)", [["", "Standard"], ["false", "aus"], ["true", "an"]], "„aus“ verhindert, dass Ausgänge beim Start kurz schalten.") : null),
      this.simple ? null : this._check("substitutions", "Platzhalter verwenden (substitutions)",
        "Schreibt Gerätename und Beschreibung oben als devicename und device_description ins YAML und nutzt sie weiter unten."),
      this.simple ? null : h("details", { open: this._extraOpen || !!this.p.extra_yaml, onToggle: (e) => { this._extraOpen = e.target.open; }, style: "margin-top:10px" },
        h("summary", {}, "Zusatz-YAML (wird unverändert eingemischt)"),
        h("textarea", { class: "mono", rows: "8", placeholder: "script:\n  - id: mein_skript\n    then: …",
          value: this.p.extra_yaml || "", onInput: (e) => { this.p.extra_yaml = e.target.value; this._changed(false); } }),
        h("div", { class: "help" }, "Eigene ESPHome-Abschnitte, die das Studio nicht kennt (script, globals, interval, display …). " +
          "Listen werden an die erzeugten angehängt, Abschnitte ergänzt. Was das Studio selbst setzt, hat Vorrang.")));
  }

  _webBox() {
    if (!this.p.web) this.p.web = { version: "2", port: 80, local: false, include_internal: false, log: true, compression: "gzip",
      auth: false, auth_user: "", auth_password: "", auth_type: "basic", ota_web: false, css_url: "", js_url: "", private_network: false, allowed_origins: "" };
    const v = this.p.web.version;
    return h("div", { class: "comp" }, h("div", { class: "comp-head" }, h("strong", {}, "Webserver"),
        h("span", { class: "comp-type" }, "Seite des Geräts im Browser")),
      h("div", { class: "grid" },
        this._select("web.version", "Version", [["2", "2 – Standard"], ["3", "3 – neue Oberfläche"], ["1", "1 – veraltet"]],
          "Version 1 wird in ESPHome 2027.1 entfernt. Version 3 hat die modernste Oberfläche."),
        this._text("web.port", "Port", { placeholder: "80" }),
        this._select("web.compression", "Komprimierung", [["gzip", "gzip (Standard)"], ["br", "Brotli (kleiner)"]])),
      this._check("web.include_internal", "Auch interne Entitäten anzeigen", "Zeigt auch Entitäten, die nicht an Home Assistant gehen."),
      this._check("web.log", "Log-Anzeige auf der Webseite"),
      v !== "1" ? this._check("web.local", "Dateien vom Gerät statt aus dem Internet laden", "Nötig, wenn der Browser keinen Internetzugang hat (Version 2).") : null,
      this._check("web.ota_web", "Firmware-Upload über die Webseite", "Fügt OTA über den Webserver hinzu (Plattform web_server)."),
      this._text("web.allowed_origins", "Erlaubte Herkunftsadressen (optional, mit Komma trennen)", { placeholder: "https://example.com" }),
      this._check("web.private_network", "Zugriff aus dem privaten Netz erlauben (Private Network Access)", "Nur zusammen mit erlaubten Herkunftsadressen möglich."),
      this._check("web.auth", "Zugangsschutz (Benutzername + Passwort)", "Empfohlen, vor allem mit Firmware-Upload.", true),
      this.p.web.auth ? h("div", { class: "grid" },
        this._text("web.auth_user", "Benutzername"),
        this._text("web.auth_password", "Passwort", { password: true }),
        this._select("web.auth_type", "Verfahren", [["basic", "basic"], ["digest", "digest (sicherer)"]])) : null,
      v !== "1" ? h("div", { class: "grid" },
        this._text("web.css_url", "Eigenes Stylesheet (URL, optional)", { placeholder: "https://…/style.css" }),
        this._text("web.js_url", "Eigenes Skript (URL, optional)", { placeholder: "https://…/app.js" })) : null);
  }

  // --- Netzwerk / Secrets ---
  _secNetwork() {
    const secretText = (key, label, password) => {
      const el = h("input", { type: password && !this._showPw ? "password" : "text", value: this.secrets[key] || "", autocomplete: "off",
        onInput: (e) => { this.secrets[key] = e.target.value; this._saveSecretsSoon(); } });
      return this._field(label, el);
    };
    const randomBtn = (kind, path) => h("button", { class: "small", onClick: async () => {
      this._setPath(path, (await this._ws("random", { kind })).value); this._changed(true); } }, "Neu erzeugen");
    const st = this.p.wifi.static_ip;
    return h("div", { class: "card" }, h("h2", {}, "WLAN, Secrets & Sicherheit"),
      h("div", { class: "grid" }, secretText("wifi_ssid", "WLAN-Name (SSID)"), secretText("wifi_password", "WLAN-Passwort", true)),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: this._showPw, onChange: (e) => { this._showPw = e.target.checked; this._renderAll(); } }), "Passwort anzeigen"),
      this._check("use_secrets", "Zugangsdaten in secrets.yaml auslagern (empfohlen)",
        "Das YAML enthält nur „!secret …“. Ohne Haken stehen WLAN-Daten und Schlüssel direkt in der Datei."),
      h("p", { class: "hint" }, "WLAN-Name und -Passwort werden einmal in Home Assistant gespeichert und für alle Projekte benutzt. Sie liegen unverschlüsselt im Speicher von Home Assistant (.storage), wie andere Integrationen auch."),
      ...(() => {
        const rest = [
      h("h3", {}, "WLAN-Optionen"),
        h("div", { class: "grid" }, this._select("wifi.min_auth_mode", "Mindest-Verschlüsselung des WLANs",
          [["", "Standard"], ["WPA", "WPA"], ["WPA2", "WPA2"], ["WPA3", "WPA3"]],
          "WPA2 verhindert, dass sich das Gerät mit unsicheren Netzen verbindet.")),
        this._check("wifi.fallback_ap", "Fallback-Hotspot + Captive Portal", "Falls das WLAN fehlt, öffnet das Gerät einen eigenen Hotspot zur Einrichtung.", true),
        this.p.wifi.fallback_ap ? this._check("wifi.ap_shared", "Ein Hotspot-Passwort für alle Geräte (empfohlen)",
          "Das Passwort wird wie das WLAN-Passwort einmal gespeichert und im secrets.yaml-Block als „ap_password“ ausgegeben. Nimm mindestens 12 Zeichen, merkbar und nicht dein WLAN-Passwort. Ohne Haken bekommt jedes Gerät ein eigenes.", true) : null,
        this.p.wifi.fallback_ap && this.p.wifi.ap_shared ? h("div", { class: "grid" }, secretText("ap_password", "Hotspot-Passwort (für alle Geräte)", true)) : null,
        this.p.wifi.fallback_ap && !this.p.wifi.ap_shared ? h("div", { class: "grid" }, this._field("Hotspot-Passwort",
          h("div", { class: "row" }, h("input", { type: "text", value: this.p.wifi.ap_password, onInput: (e) => { this.p.wifi.ap_password = e.target.value; this._changed(false); } }), randomBtn("ap", "wifi.ap_password")))) : null,
        this._check("wifi.static_ip.enabled", "Feste IP-Adresse", "", true),
        st.enabled ? h("div", { class: "grid" },
          this._text("wifi.static_ip.ip", "IP-Adresse", { placeholder: "192.168.1.50" }),
          this._text("wifi.static_ip.gateway", "Gateway", { placeholder: "192.168.1.1" }),
          this._text("wifi.static_ip.subnet", "Subnetz", { placeholder: "255.255.255.0" }),
          this._text("wifi.static_ip.dns", "DNS (optional)", { placeholder: "192.168.1.1" })) : null,
        h("h3", {}, "Home Assistant & Updates"),
        this._check("api.enabled", "Home-Assistant-API", "Nötig, damit Home Assistant das Gerät findet.", true),
        this.p.api.enabled ? this._check("api.encryption", "API verschlüsseln", "", true) : null,
        this.p.api.enabled && this.p.api.encryption ? h("div", { class: "grid" }, this._field("API-Schlüssel",
          h("div", { class: "row" }, h("input", { type: "text", value: this.p.api.key, readOnly: true }), randomBtn("api", "api.key")))) : null,
        this._check("ota.enabled", "Updates über WLAN (OTA)", "", true),
        this.p.ota.enabled ? this._select("ota.mode", "OTA-Absicherung",
          [["encryption", "Verschlüsselt mit API-Schlüssel (empfohlen, ab ESPHome 2026.9)"], ["password", "Passwort (für ältere ESPHome-Versionen)"], ["none", "Keine"]], "Hast du ESPHome älter als 2026.9 (steht unten im Device Builder), bitte „Passwort“ wählen. Sonst meldet ESPHome „encryption is an invalid option“.", true) : null,
        this.p.ota.enabled && this.p.ota.mode === "password" ? h("div", { class: "grid" }, this._field("OTA-Passwort",
          h("div", { class: "row" }, h("input", { type: "text", value: this.p.ota.password, readOnly: true }), randomBtn("ota", "ota.password")))) : null,
        h("h3", {}, "Zusätze"),
        this._check("web_server", "Webserver", "Zeigt die Entitäten auf einer Webseite des Geräts.", true),
        this.p.web_server ? this._webBox() : null,
        this._check("time_ha", "Uhrzeit von Home Assistant"),
        h("h3", {}, "Diagnose-Entitäten"),
        Object.keys(this.p.diag_custom || {}).length
          ? h("p", { class: "hint" }, "Eigene Namen, Symbole und Formate aus dem Import bleiben für diese Diagnose-Entitäten erhalten.") : null,
        this._check("diag.status", "Status (verbunden/getrennt)", "Binärer Sensor „Status“, zeigt, ob das Gerät erreichbar ist."),
        this._check("diag.wifi_signal", "WLAN-Signal"),
        this._check("diag.uptime", "Laufzeit (Sekunden)"),
        this._check("diag.uptime_text", "Betriebszeit als Text", "z. B. „2T 4Std 12Min 3Sek“."),
        this._check("diag.ip", "IP-Adresse"),
        this._check("diag.ssid", "Verbundenes WLAN (SSID)"),
        this._check("diag.bssid", "Verbundener Access Point (BSSID)", "Praktisch, um zu sehen, an welcher FRITZ!Box das Gerät hängt."),
        this._check("diag.mac", "MAC-Adresse"),
        this._check("diag.restart", "Knopf „Neustart“"),
        h("h3", {}, "Fehlersuche (Debug)"),
        this._check("diag.debug_heap", "Freier Speicher (Heap) und größter Block", "", true),
        this._check("diag.debug_loop", "Loop-Zeit", "", true),
        this._check("diag.debug_reset", "Grund des letzten Neustarts", "", true),
        (this.p.diag?.debug_heap || this.p.diag?.debug_loop || this.p.diag?.debug_reset)
          ? h("div", { class: "grid" }, this._text("debug_interval", "Debug-Intervall", { placeholder: "30s" })) : null];
        return this.simple
          ? [h("details", { style: "margin-top:12px", open: !!this._advOpen, onToggle: (e) => { this._advOpen = e.target.open; } },
               h("summary", {}, h("strong", {}, "Weitere Einstellungen (für Fortgeschrittene)")), ...rest)]
          : rest;
      })());
  }

  // --- GPIO-Tabelle (wie bei Tasmota) ---
  _secPins() {
    const b = this.board();
    const usage = this._usage();
    const present = new Set(this.p.components.map((c) => c.type));
    const singles = this.meta.types.filter((t) => t.pins.length === 1 && t.platforms.includes(b.platform) && !(t.not_chips || []).includes(b.chip));
    const rows = b.pins.map((pin) => {
      const u = usage[pin.id];
      const badges = [];
      if (pin.flash) badges.push(h("span", { class: "badge bad" }, "Flash"));
      if (pin.strapping) badges.push(h("span", { class: "badge warn", title: pin.strapping }, "Boot-Pin"));
      if (pin.uart) badges.push(h("span", { class: "badge warn" }, "UART"));
      if (pin.usb) badges.push(h("span", { class: "badge warn" }, "USB"));
      if (pin.psram) badges.push(h("span", { class: "badge warn", title: pin.note }, "PSRAM?"));
      if (pin.input_only && !pin.adc_only) badges.push(h("span", { class: "badge" }, "nur Eingang"));
      if (pin.boot_high) badges.push(h("span", { class: "badge warn", title: pin.note }, "HIGH beim Start"));
      if (pin.no_pwm && !pin.adc_only) badges.push(h("span", { class: "badge", title: pin.note }, "kein PWM"));
      if (pin.no_pullup && !pin.input_only) badges.push(h("span", { class: "badge", title: pin.note }, "kein Pull-up"));
      if (pin.adc) badges.push(h("span", { class: "badge" }, pin.adc === "adc" ? "ADC" : pin.adc.toUpperCase()));
      let cell;
      if (pin.flash) cell = h("span", { class: "pinnote" }, "gesperrt");
      else if (u?.i2c) cell = h("span", {}, `I²C ${u.i2c.toUpperCase()}`);
      else if (u?.comp && this.spec(u.comp).pins.length > 1) cell = h("span", {}, `${u.comp.name} (${u.pin.label})`);
      else {
        const opts = singles.filter((t) => this._incompat(pin, t.pins[0].kind) === null
          && (!t.singleton || !present.has(t.type) || u?.comp?.type === t.type));
        const sel = h("select", { onChange: (e) => this._pinFunction(pin, e.target.value, u?.comp) },
          h("option", { value: "" }, "— frei —"),
          this.meta.group_order.map((g) => {
            const list = opts.filter((t) => t.group === g);
            return list.length ? h("optgroup", { label: g }, list.map((t) => h("option", { value: t.type }, t.label))) : null;
          }));
        sel.value = u?.comp?.type || "";
        cell = h("div", {}, sel, u?.comp ? h("div", { class: "pinnote" }, u.comp.name) : null);
      }
      return h("tr", { class: u ? "used" : pin.flash ? "blocked" : "", title: pin.note || pin.strapping || "" },
        h("td", {}, pin.label), h("td", {}, badges), h("td", {}, cell));
    });
    return h("div", { class: "card" }, h("h2", {}, "GPIO-Zuordnung"),
      h("p", { class: "hint", style: "margin-top:0" }, "Wähle pro Pin, was daran hängt. Mehrpolige Bauteile (RGB-Licht, Ultraschall, I²C-Sensoren) fügst du unten als Komponente hinzu, ihre Pins erscheinen dann hier."),
      h("div", { style: "overflow:auto" }, h("table", { class: "pins" },
        h("thead", {}, h("tr", {}, h("th", {}, "Pin"), h("th", {}, "Eigenschaften"), h("th", {}, "Funktion"))), h("tbody", {}, rows))));
  }

  _pinFunction(pin, typeKey, existing) {
    if (existing) {
      if (existing.type === typeKey) return;
      this._removeComponent(existing);
    }
    if (typeKey) {
      const spec = this.type(typeKey);
      this._addComponent(typeKey, { [spec.pins[0].key]: pin.id });
    }
    this._changed(true);
  }

  // --- Komponenten ---
  _secComponents() {
    const b = this.board();
    const adder = h("select", {},
      this.meta.group_order.map((g) => {
        const list = this.meta.types.filter((t) => t.group === g && t.platforms.includes(b.platform) && !(t.not_chips || []).includes(b.chip));
        return list.length ? h("optgroup", { label: g }, list.map((t) => h("option", { value: t.type }, t.label))) : null;
      }));
    const cards = this.p.components.map((c) => this._compCard(c));
    return h("div", { class: "card" }, h("h2", {}, `Komponenten (${this.p.components.length})`),
      h("div", { class: "row grow" }, adder, h("button", { class: "primary", style: "flex:0 0 auto", onClick: () => { this._addComponent(adder.value); this._changed(true); } }, "Hinzufügen")),
      this._catalogAdder(),
      this._needsI2c() ? this._i2cBox() : null,
      this._needsSpi() ? this._spiBox() : null,
      cards.length ? cards : h("div", { class: "empty" }, "Noch nichts hinzugefügt. Wähle oben eine Komponente oder weise in der GPIO-Tabelle einem Pin eine Funktion zu."));
  }

  _spiBox() {
    const b = this.board();
    const usage = this._usage();
    const cur = { ...(b.spi_default || {}), ...(this.p.spi || {}) };
    const pinSel = (key, label, kind) => {
      const sel = h("select", { onChange: (e) => { this.p.spi = { ...(this.p.spi || {}), [key]: e.target.value }; this._changed(true); } },
        key === "clk" ? null : h("option", { value: "" }, "— nicht benutzt —"),
        b.pins.map((pin) => {
          const bad = this._incompat(pin, kind);
          const other = usage[pin.id] && usage[pin.id].i2c !== `SPI ${key}`;
          return h("option", { value: pin.id, disabled: !!bad || !!other }, `${pin.label}${bad ? ` (${tx(bad)})` : other ? tx(" (belegt)") : pin.strapping ? " ⚠" : ""}`);
        }));
      sel.value = cur[key] || "";
      return this._field(label, sel);
    };
    return h("div", { class: "comp" }, h("div", { class: "comp-head" }, h("strong", {}, "SPI-Bus"), h("span", { class: "comp-type" }, "gemeinsam für alle SPI-Bausteine")),
      h("div", { class: "grid" }, pinSel("clk", "CLK", "io"), pinSel("mosi", "MOSI (Daten raus)", "io"), pinSel("miso", "MISO (Daten rein)", "in")));
  }

  _i2cBox() {
    const b = this.board();
    const usage = this._usage();
    const pinSel = (key, label) => {
      const sel = h("select", { onChange: (e) => { this.p.i2c[key] = e.target.value; this._changed(true); } },
        b.pins.map((pin) => {
          const bad = this._incompat(pin, "io");
          const other = usage[pin.id] && !(usage[pin.id].i2c === key);
          return h("option", { value: pin.id, disabled: !!bad || !!other }, `${pin.label}${bad ? ` (${tx(bad)})` : other ? tx(" (belegt)") : pin.strapping ? " ⚠" : ""}`);
        }));
      sel.value = this.p.i2c[key] || "";
      return this._field(label, sel);
    };
    return h("div", { class: "comp" }, h("div", { class: "comp-head" }, h("strong", {}, "I²C-Bus"), h("span", { class: "comp-type" }, "gemeinsam für alle I²C-Sensoren")),
      h("div", { class: "grid" }, pinSel("sda", "SDA"), pinSel("scl", "SCL")));
  }

  _pinSelect(c, ps) {
    const b = this.board();
    const usage = this._usage();
    const sel = h("select", { onChange: (e) => { c.pins[ps.key] = e.target.value; this._changed(true); } },
      h("option", { value: "" }, "— wählen —"),
      b.pins.map((pin) => {
        const bad = this._incompat(pin, ps.kind);
        const u = usage[pin.id];
        const mine = u?.comp === c && u?.pin?.key === ps.key;
        const other = u && !mine;
        const warn = pin.strapping || pin.uart || pin.usb || pin.psram;
        const suffix = bad ? ` (${tx(bad)})` : other ? tx(` (belegt: ${u.comp ? u.comp.name : "I²C"})`) : warn ? " ⚠" : "";
        return h("option", { value: pin.id, disabled: !!bad || !!other, title: pin.note || pin.strapping || "" }, `${pin.label}${suffix}`);
      }));
    // Pins von Port-Expandern (MCP23017, PCF8574 …), die im Projekt vorkommen
    if (!ps.key.startsWith("_") && !["pwm", "adc"].includes(ps.kind)) {
      for (const x of this.p.components) {
        const en = x.type === "generic" && x !== c ? this.catalog?.byId?.[x.cat] : null;
        if (!en?.expander || (en.expander_kinds && !en.expander_kinds.includes(ps.kind))) continue;
        sel.append(h("optgroup", { label: `${x.name} (${en.id})` }, Array.from({ length: en.expander }, (_, n) => {
          const id = `x:${x.uid}:${n}`;
          const u = usage[id];
          const other = u && !(u.comp === c && u.pin?.key === ps.key);
          return h("option", { value: id, disabled: !!other }, `Pin ${n}${other ? tx(` (belegt: ${u.comp?.name})`) : ""}`);
        })));
      }
    }
    sel.value = c.pins?.[ps.key] || "";
    return this._field(ps.label, sel);
  }

  _optControl(c, o) {
    const set = (v) => { c.options[o.key] = v; this._changed(false); };
    if (o.type === "bool") {
      return h("label", { class: "check" }, h("input", { type: "checkbox", checked: !!c.options[o.key], onChange: (e) => set(e.target.checked) }),
        h("span", {}, o.label, o.help ? h("small", {}, o.help) : null));
    }
    if (o.type === "select") {
      const sel = h("select", { onChange: (e) => set(e.target.value) }, o.choices.map((v) => h("option", { value: v }, v)));
      sel.value = c.options[o.key] ?? o.default;
      return this._field(o.label, sel, o.help);
    }
    if (o.type === "ref") {
      const targets = this.p.components.filter((x) => x !== c && o.ref_types.includes(x.type));
      const sel = h("select", { onChange: (e) => set(e.target.value) }, h("option", { value: "" }, "— nichts —"),
        targets.map((x) => h("option", { value: x.uid }, x.name)));
      sel.value = c.options[o.key] || "";
      return this._field(o.label, sel, o.help);
    }
    const el = h("input", { type: o.type === "number" ? "number" : "text", value: c.options[o.key] ?? "", placeholder: o.placeholder || "",
      min: o.min ?? undefined, max: o.max ?? undefined, onInput: (e) => set(o.type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value) });
    return this._field(o.unit ? `${o.label} (${o.unit})` : o.label, el, o.help);
  }

  _optionsBlock(c, spec) {
    const show = this.simple ? spec.options.filter((o) => ESSENTIAL_OPTS.has(o.key)) : spec.options;
    const more = this.simple ? spec.options.filter((o) => !ESSENTIAL_OPTS.has(o.key)) : [];
    return [
      show.length ? h("div", { class: "grid", style: "margin-top:10px" }, show.map((o) => this._optControl(c, o))) : null,
      more.length ? h("details", { style: "margin-top:8px" }, h("summary", { class: "hint" }, "Weitere Einstellungen"),
        h("div", { class: "grid", style: "margin-top:8px" }, more.map((o) => this._optControl(c, o)))) : null];
  }

  _compCard(c) {
    if (c.type === "generic") return this._genericCard(c);
    const spec = this.type(c.type);
    if (!spec) return null;
    const idx = this.p.components.indexOf(c);
    const move = (d) => { const a = this.p.components; const j = idx + d; if (j < 0 || j >= a.length) return; [a[idx], a[j]] = [a[j], a[idx]]; this._changed(true); };
    const hasErr = this.out.errors.some((e) => e.includes(`„${c.name}“`));
    return h("div", { class: `comp ${hasErr ? "bad" : ""}` },
      h("div", { class: "comp-head" },
        h("input", { type: "text", class: "tname", value: c.name, onInput: (e) => { c.name = e.target.value; this._changed(false); } }),
        h("span", { class: "comp-type" }, spec.label),
        h("button", { class: "small", disabled: idx === 0, onClick: () => move(-1), title: "Nach oben" }, "↑"),
        h("button", { class: "small", disabled: idx === this.p.components.length - 1, onClick: () => move(1), title: "Nach unten" }, "↓"),
        h("button", { class: "small danger", onClick: () => { this._removeComponent(c); this._changed(true); }, title: "Entfernen" }, "✕")),
      spec.pins.length ? h("div", { class: "grid" }, spec.pins.map((ps) => this._pinSelect(c, ps))) : null,
      spec.needs_i2c ? h("p", { class: "hint", style: "margin:0 0 8px" }, "Hängt am I²C-Bus (siehe oben).") : null,
      this._optionsBlock(c, spec), this._profiBlock(c));
  }

  // --- Katalog (alle ESPHome-Bausteine) ---
  _catalogAdder() {
    const b = this.board();
    const cat = this.catalog;
    if (!cat || !cat.entries.length) return null;
    const st = (this._catUi = this._catUi || { q: "", domain: "", unverified: false });
    const usable = (e) => !e.unsupported && (st.unverified && !this.simple ? true : e.verified) && (!e.verified || (e.platforms || []).includes(b.platform));
    const list = cat.entries.filter((e) => usable(e) && (!st.domain || e.domain === st.domain)
      && (!st.q || `${e.id} ${e.label} ${(e.subs || []).map((s) => s.label).join(" ")}`.toLowerCase().includes(st.q.toLowerCase())));
    const sel = h("select", { size: 1 });
    const order = Object.keys(cat.domains);
    for (const d of order) {
      const items = list.filter((e) => e.domain === d);
      if (items.length) sel.append(h("optgroup", { label: `${cat.domains[d]} (${items.length})` },
        items.map((e) => h("option", { value: e.id }, `${e.label}${e.bus ? ` · ${e.bus.toUpperCase()}` : ""}${e.verified ? "" : " ?"}`))));
    }
    const domSel = h("select", { onChange: (e) => { st.domain = e.target.value; this._renderAll(); } },
      h("option", { value: "" }, "Alle Arten"), order.map((d) => h("option", { value: d }, cat.domains[d])));
    domSel.value = st.domain;
    const q = h("input", { type: "search", placeholder: "Suchen, z. B. bme680, Strom, CO₂ …", value: st.q,
      onInput: (e) => { st.q = e.target.value; clearTimeout(this._catT); this._catT = setTimeout(() => { this._renderAll(); this.shadowRoot.querySelector("input[type=search]")?.focus(); }, 250); } });
    return h("details", { class: "catalog", open: !!(st.q || this.p.components.some((c) => c.type === "generic")) },
      h("summary", {}, h("strong", {}, "Weitere Bausteine (Katalog mit allen ESPHome-Sensoren und mehr)")),
      h("div", { class: "row grow", style: "margin-top:8px" }, q, domSel),
      h("div", { class: "row grow", style: "margin-top:8px" }, sel,
        h("button", { class: "primary", style: "flex:0 0 auto", disabled: !list.length, onClick: () => { if (sel.value) { this._addCatalog(sel.value); this._changed(true); } } }, "Hinzufügen")),
      this.simple ? null : h("label", { class: "check" }, h("input", { type: "checkbox", checked: st.unverified, onChange: (e) => { st.unverified = e.target.checked; this._renderAll(); } }),
        h("span", {}, "Auch ungeprüfte Bausteine zeigen", h("small", {}, "Mit „?“ markiert. Der Generator erzeugt sie, sie wurden aber nicht mit ESPHome getestet."))),
      h("p", { class: "hint" }, `${list.length} Bausteine passen zu diesem Board. Weniger gibt es nur, weil nicht jeder Baustein auf jedem Chip läuft.`));
  }

  _addCatalog(id) {
    const e = this.catalog.byId[id];
    const mk = (en) => {
      const o = { interval: "", extra: "" };
      if (en.bus === "uart") o.baud = String(en.baud_default || 9600);
      for (const f of en.fields) if (f.required) o["f_" + f.key] = f.default !== "" ? String(f.default) : (f.choices?.[0] ?? "");
      for (const k of this._defaultSubs(en)) o["s_" + k] = true;
      return { uid: uid(), type: "generic", cat: en.id, name: this._uniqueName(en.label), pins: {}, options: o };
    };
    const c = mk(e);
    if (e.hub) {
      let hub = this.p.components.find((x) => x.type === "generic" && x.cat === e.hub);
      if (!hub && this.catalog.byId[e.hub]) { hub = mk(this.catalog.byId[e.hub]); this.p.components.push(hub); }
      if (hub) c.options.hub = hub.uid;
    }
    for (const nid of e.needs_cat || []) {
      if (!this.p.components.some((x) => x.type === "generic" && x.cat === nid) && this.catalog.byId[nid]) this.p.components.push(mk(this.catalog.byId[nid]));
    }
    this.p.components.push(c);
  }

  _defaultSubs(e) {
    const keys = (e.subs || []).map((s) => s.key);
    const on = (e.subs || []).filter((s) => s.required).map((s) => s.key);
    for (const k of ["temperature", "humidity", "pressure", "co2", "voltage", "current", "power", "energy", "pm_2_5", "illuminance", "distance", "moisture"]) {
      if (keys.includes(k) && !on.includes(k)) on.push(k);
    }
    if (!on.length && keys.length) on.push(keys[0]);
    return on;
  }

  _genericCard(c) {
    const e = this.catalog?.byId?.[c.cat];
    const spec = this.spec(c);
    const idx = this.p.components.indexOf(c);
    const move = (d) => { const a = this.p.components; const j = idx + d; if (j < 0 || j >= a.length) return; [a[idx], a[j]] = [a[j], a[idx]]; this._changed(true); };
    const hasErr = this.out.errors.some((x) => x.includes(`„${c.name}“`));
    const head = h("div", { class: "comp-head" },
      h("input", { type: "text", class: "tname", value: c.name, onInput: (ev) => { c.name = ev.target.value; this._changed(false); } }),
      h("span", { class: "comp-type" }, e ? `${this.catalog.domains[e.domain] || e.domain}: ${e.platform}` : spec.label),
      h("button", { class: "small", disabled: idx === 0, onClick: () => move(-1), title: "Nach oben" }, "↑"),
      h("button", { class: "small", disabled: idx === this.p.components.length - 1, onClick: () => move(1), title: "Nach unten" }, "↓"),
      h("button", { class: "small danger", onClick: () => { this._removeComponent(c); this._changed(true); }, title: "Entfernen" }, "✕"));
    if (!e) return h("div", { class: "comp bad" }, head, h("p", { class: "hint" }, "Dieser Baustein ist im Katalog nicht (mehr) vorhanden."));
    const o = c.options;
    const set = (k, v) => { o[k] = v; this._changed(false); };
    const body = [];
    if (spec.pins.length) body.push(h("div", { class: "grid" }, spec.pins.map((ps) => this._pinSelect(c, ps))));
    if (e.bus === "i2c") body.push(h("p", { class: "hint", style: "margin:0 0 8px" }, "Hängt am I²C-Bus (siehe oben)."));
    if (e.bus === "spi") body.push(h("p", { class: "hint", style: "margin:0 0 8px" }, "Hängt am SPI-Bus (siehe oben). Der CS-Pin gehört zu diesem Baustein."));
    const ctl = [];
    const needTxt = { ir_transmitter: "den Baustein „IR-Sender“ (Komponenten)", time: "die „Uhrzeit von Home Assistant“ (WLAN & Secrets)" };
    if ((e.needs || []).length) body.push(h("p", { class: "hint", style: "margin:0 0 8px" }, `Braucht zusätzlich ${e.needs.map((n) => needTxt[n] || n).join(" und ")}.`));
    if ((e.needs_dom || []).length) body.push(h("p", { class: "hint", style: "margin:0 0 8px" }, `Braucht zusätzlich einen Baustein der Art ${e.needs_dom.map((d) => this.catalog.domains[d] || d).join(" und ")} (im Katalog hinzufügen).`));
    if (e.hub) {
      const hubs = this.p.components.filter((x) => x.type === "generic" && x.cat === e.hub);
      const sel = h("select", { onChange: (ev) => set("hub", ev.target.value) }, h("option", { value: "" }, "— wählen —"), hubs.map((x) => h("option", { value: x.uid }, x.name)));
      sel.value = o.hub || "";
      ctl.push(this._field(`Gehört zu (${e.hub})`, sel, "Der Hauptbaustein, an dem dieser Messwert hängt."));
    }
    for (const r of e.refs || []) {
      const targets = this.p.components.filter((x) => x !== c && x.type === "generic" && (this.catalog.byId[x.cat]?.provides || []).includes(r.cls));
      const sel = h("select", { onChange: (ev) => set("ref_" + r.key, ev.target.value) }, h("option", { value: "" }, "— wählen —"), targets.map((x) => h("option", { value: x.uid }, x.name)));
      sel.value = o["ref_" + r.key] || "";
      ctl.push(this._field(`${r.label}${r.required ? " *" : ""}`, sel, "Ein passender Baustein aus dem Katalog (zuerst dort hinzufügen, z. B. einen Ausgang oder Sensor)."));
    }
    if (e.bus === "uart") ctl.push(this._field("Baudrate", h("input", { type: "text", value: o.baud ?? "", onInput: (ev) => set("baud", ev.target.value) }), "Steht im Datenblatt des Sensors (häufig 9600)."));
    for (const f of e.fields) {
      const k = "f_" + f.key;
      const lbl = f.required ? `${f.label} *` : f.label;
      const def = f.default !== "" && f.default != null ? tx(`Standard: ${f.default}`) : "";
      if (f.type === "bool") {
        ctl.push(h("label", { class: "check" }, h("input", { type: "checkbox", checked: o[k] === undefined || o[k] === "" ? String(f.default).toLowerCase() === "true" : !!o[k], onChange: (ev) => set(k, ev.target.checked) }), h("span", {}, lbl)));
      } else if (f.type === "enum") {
        const sel = h("select", { onChange: (ev) => set(k, ev.target.value) }, f.required ? null : h("option", { value: "" }, def || "(Standard)"), f.choices.map((v) => h("option", { value: v }, v)));
        sel.value = o[k] ?? "";
        ctl.push(this._field(lbl, sel));
      } else {
        ctl.push(this._field(lbl, h("input", { type: "text", value: o[k] ?? "", placeholder: def, onInput: (ev) => set(k, ev.target.value) })));
      }
    }
    if (e.has_interval) ctl.push(this._field("Aktualisierung", h("input", { type: "text", value: o.interval ?? "", placeholder: e.interval_default ? tx(`Standard: ${e.interval_default}`) : "z. B. 60s", onInput: (ev) => set("interval", ev.target.value) })));
    if (ctl.length) body.push(h("div", { class: "grid", style: "margin-top:10px" }, ctl));
    if (e.subs?.length) {
      body.push(h("div", { class: "subs" }, h("small", { class: "hint" }, e.self_entity ? "Zusätzliche Werte:" : "Messwerte (jeder wird eine eigene Entität in Home Assistant):"),
        h("div", { class: "grid" }, e.subs.map((s) => h("label", { class: "check" },
          h("input", { type: "checkbox", checked: !!s.required || !!o["s_" + s.key], disabled: !!s.required, onChange: (ev) => { set("s_" + s.key, ev.target.checked); } }),
          h("span", {}, s.label))))));
    }
    body.push(this._profiBlock(c));
    body.push(h("details", { style: "margin-top:8px" }, h("summary", { class: "hint" }, "Weitere Einstellungen als YAML (z. B. filters, device_class)"),
      h("textarea", { class: "mono", rows: 3, placeholder: "device_class: temperature\nfilters:\n  - offset: -1.5", value: o.extra ?? "", onInput: (ev) => set("extra", ev.target.value) })));
    if (!e.verified) body.push(h("p", { class: "hint", style: "color:var(--warning-color,#b26a00)" }, "Dieser Baustein wurde noch nicht mit ESPHome getestet."));
    return h("div", { class: `comp ${hasErr ? "bad" : ""}` }, head, body);
  }

  // --- Profi-Einstellungen pro Entität ---
  _entTargets(c) {
    if (c.type === "generic") {
      const e = this.catalog?.byId?.[c.cat];
      if (!e || e.domain === "hub") return [];
      const out = [];
      if (e.self_entity || !(e.subs || []).length) out.push({ key: "", label: e.self_entity ? "Entität" : "Baustein", domain: e.domain });
      for (const sub of e.subs || []) if (sub.required || c.options["s_" + sub.key]) out.push({ key: sub.key, label: sub.label, domain: sub.domain });
      return out;
    }
    const ent = this.type(c.type)?.ent;
    return ent ? ent.targets.map((t) => ({ key: t.key, label: t.label, domain: ent.domain })) : [];
  }

  _entProps(domain) {
    const m = this.meta.entity;
    if (m.props[domain]) return m.props[domain];
    return m.other_props.filter((p) => p !== "device_class" || (m.device_classes[domain] || []).length);
  }

  _profiBlock(c) {
    if (this.simple || !this.meta.entity) return null;
    const targets = this._entTargets(c);
    if (!targets.length) return null;
    this._profiOpen = this._profiOpen || new Set();
    const m = this.meta.entity;
    const ent = (c.options.ent = c.options.ent || {});
    const body = targets.map((t) => {
      const cfg = (ent[t.key] = ent[t.key] || {});
      const props = this._entProps(t.domain);
      const set = (k, v, structural = false) => { cfg[k] = v; this._changed(structural); };
      const txt = (k, label, ph = "", list = "") => this._field(label, h("input", { type: "text", value: cfg[k] ?? "", placeholder: ph, list: list || undefined, onInput: (ev) => set(k, ev.target.value) }));
      const sel = (k, label, opts) => {
        const el = h("select", { onChange: (ev) => set(k, ev.target.value) }, h("option", { value: "" }, "(Standard)"), opts.map((v) => h("option", { value: v }, v)));
        el.value = cfg[k] ?? "";
        return this._field(label, el);
      };
      const fields = [];
      if (props.includes("name")) fields.push(txt("name", "Name (statt Standard)"));
      if (props.includes("icon")) fields.push(txt("icon", "Icon", "mdi:thermometer"));
      if (props.includes("device_class")) fields.push(sel("device_class", "Geräteklasse", m.device_classes[t.domain] || []));
      if (props.includes("unit_of_measurement")) fields.push(txt("unit_of_measurement", "Einheit", "°C", "es-units"));
      if (props.includes("state_class")) fields.push(sel("state_class", "Zustandsklasse (Statistik)", m.state_classes));
      if (props.includes("accuracy_decimals")) fields.push(txt("accuracy_decimals", "Nachkommastellen", "1"));
      if (props.includes("entity_category")) fields.push(sel("entity_category", "Kategorie", ["config", "diagnostic"]));
      const checks = [];
      if (props.includes("internal")) checks.push(h("label", { class: "check" }, h("input", { type: "checkbox", checked: !!cfg.internal, onChange: (ev) => set("internal", ev.target.checked) }),
        h("span", {}, "Intern", h("small", {}, "Nicht an Home Assistant melden, nur im Gerät nutzen."))));
      if (props.includes("disabled_by_default")) checks.push(h("label", { class: "check" }, h("input", { type: "checkbox", checked: !!cfg.disabled_by_default, onChange: (ev) => set("disabled_by_default", ev.target.checked) }),
        h("span", {}, "In Home Assistant standardmäßig deaktiviert")));
      const defs = m.filters[t.domain] || [];
      let filters = null;
      if (defs.length) {
        cfg.filters = cfg.filters || [];
        const rows = cfg.filters.map((row, i) => {
          const def = defs.find((d) => d.key === row.t);
          const typeSel = h("select", { onChange: (ev) => { row.t = ev.target.value; row.v = {}; this._changed(true); } }, defs.map((d) => h("option", { value: d.key }, d.label)));
          typeSel.value = row.t;
          const inputs = (def?.params || []).map((p) => {
            row.v = row.v || {};
            const el = p.type === "lambda"
              ? h("textarea", { class: "mono", rows: 2, placeholder: p.label, value: row.v[p.key] ?? "", onInput: (ev) => { row.v[p.key] = ev.target.value; this._changed(false); } })
              : h("input", { type: "text", placeholder: p.label, title: p.label, value: row.v[p.key] ?? "", onInput: (ev) => { row.v[p.key] = ev.target.value; this._changed(false); } });
            return el;
          });
          return h("div", { class: "frow" }, typeSel, ...inputs,
            h("button", { class: "small", disabled: i === 0, onClick: () => { const a = cfg.filters; [a[i - 1], a[i]] = [a[i], a[i - 1]]; this._changed(true); }, title: "Nach oben" }, "↑"),
            h("button", { class: "small danger", onClick: () => { cfg.filters.splice(i, 1); this._changed(true); }, title: "Filter entfernen" }, "✕"));
        });
        const add = h("select", { onChange: (ev) => { if (ev.target.value) { cfg.filters.push({ t: ev.target.value, v: {} }); this._changed(true); } } },
          h("option", { value: "" }, "＋ Filter hinzufügen …"), defs.map((d) => h("option", { value: d.key }, d.label)));
        filters = h("div", { class: "filters" }, h("small", { class: "hint" }, "Filter laufen in dieser Reihenfolge, bevor der Wert gemeldet wird."), rows, add);
      }
      return h("div", { class: "ent" }, targets.length > 1 || t.key ? h("strong", {}, t.label) : null,
        fields.length ? h("div", { class: "grid" }, fields) : null, checks, filters);
    });
    return h("details", { style: "margin-top:8px", open: this._profiOpen.has(c.uid), onToggle: (ev) => { ev.target.open ? this._profiOpen.add(c.uid) : this._profiOpen.delete(c.uid); } },
      h("summary", { class: "hint" }, "Profi-Einstellungen (Name, Icon, Einheit, Filter …)"),
      h("datalist", { id: "es-units" }, m.units.map((u) => h("option", { value: u }))), body);
  }

  // --- Ausgabe ---
  _renderOutput() {
    if (!this._outEl) return;
    const o = this.out;
    const isYaml = this.tab === "yaml";
    const text = isYaml ? o.yaml : (o.secrets || "# Nicht nötig: Die Zugangsdaten stehen direkt im YAML.\n");
    const tabBtn = (id, label) => h("button", { class: `tab ${this.tab === id ? "active" : ""}`, onClick: () => { this.tab = id; this._renderOutput(); } }, label);
    const filename = isYaml ? `${this.p?.name || tx("geraet")}.yaml` : "secrets-ergaenzung.yaml";
    const copyBtn = h("button", { class: "primary", disabled: !o.ok && isYaml, onClick: async () => {
      const okc = await this._copy(text); copyBtn.textContent = tx(okc ? "Kopiert ✓" : "Markiere den Text und kopiere ihn von Hand");
      setTimeout(() => { copyBtn.textContent = tx("Kopieren"); }, 2000); } }, "Kopieren");
    this._outEl.replaceChildren(...[
      h("h2", {}, "Ergebnis", h("span", { class: `badge ${o.ok ? "ok" : "bad"}` }, o.ok ? "bereit" : `${o.errors.length} Fehler`)),
      h("div", { class: "tabs" }, tabBtn("yaml", "ESPHome YAML"), tabBtn("secrets", "secrets.yaml")),
      h("div", { class: "msgs" },
        o.errors.map((e) => h("div", { class: "msg err" }, e)),
        o.warnings.map((w) => h("div", { class: "msg warn" }, w))),
      h("pre", { class: "code" }, text || "(noch nichts)"),
      h("div", { class: "row", style: "margin-top:10px" }, copyBtn,
        h("button", { disabled: !o.ok && isYaml, onClick: () => this._download(filename, text) }, "Herunterladen"),
        isYaml ? h("button", { class: "primary", disabled: !o.ok, onClick: () => this._deploy() }, "In ESPHome speichern") : null,
        h("span", { class: "spacer" }), h("span", { class: "pinnote" }, filename)),
      this._deployMsg ? h("div", { class: `msg ${this._deployMsg.err ? "err" : "ok"}`, style: "margin-top:8px" }, this._deployMsg.text) : null,
      this._prevBackup ? h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onClick: () => this._download(this._prevBackup.name, this._prevBackup.text) }, "Vorherige Version herunterladen")) : null,
      isYaml ? this._deployBox() : null,
      h("p", { class: "hint" }, isYaml
        ? "In ESPHome ein neues Gerät anlegen (oder ein vorhandenes bearbeiten), den Inhalt ersetzen und installieren. Erstes Flashen per USB, danach per WLAN."
        : "Diese Zeilen in die secrets.yaml von ESPHome einfügen. WLAN-Name und -Passwort nur einmal, die Schlüssel mit Gerätenamen gelten pro Gerät.")].filter(Boolean));
    this._updateDirty();
  }

  _deployBox() {
    const st = this._deploySet;
    const dir = h("input", { type: "text", value: st?.target_dir ?? "/config/esphome", placeholder: "/config/esphome" });
    const url = h("input", { type: "text", value: st?.dashboard_url ?? "", placeholder: "http://homeassistant.local:6052 (optional)" });
    const usr = h("input", { type: "text", value: st?.dashboard_user ?? "", placeholder: "Benutzername", autocomplete: "off" });
    const pwd = h("input", { type: "password", value: "", placeholder: st?.has_password ? "Passwort gespeichert (leer lassen = unverändert)" : "Passwort", autocomplete: "new-password" });
    const d = h("details", { class: "deploybox", open: !!this._deployOpen, onToggle: (ev) => { this._deployOpen = ev.target.open; if (ev.target.open && !this._deploySet) this._loadDeploy(); } },
      h("summary", {}, "Ziel für „In ESPHome speichern“"),
      h("label", { class: "pinnote" }, "Ordner mit den ESPHome-Dateien"), dir,
      h("label", { class: "pinnote" }, "oder Adresse des ESPHome Device Builders (hat Vorrang, nur ohne Anmeldung), z. B. http://homeassistant.local:6052"), url,
      h("label", { class: "pinnote" }, "Anmeldung am Device Builder (nur falls dort eingerichtet)"), usr, pwd,
      h("div", { class: "row", style: "margin-top:8px" }, h("button", { onClick: async () => {
        try { this._deploySet = await this._ws("deploy_settings", { target_dir: dir.value, dashboard_url: url.value, dashboard_user: usr.value, dashboard_password: pwd.value });
          this._deployMsg = { text: "Ziel gespeichert." + (!this._deploySet.dashboard_url && !this._deploySet.dir_exists ? " Achtung: Der Ordner existiert nicht." : "") };
        } catch (e) { this._deployMsg = { err: true, text: e.message || "Speichern fehlgeschlagen." }; }
        this._renderOutput(); } }, "Ziel speichern")),
      h("p", { class: "hint" }, "Im Ordner-Modus werden vorhandene Dateien als .bak gesichert, beim Device Builder kannst du die vorherige Version nach dem Speichern herunterladen. In die secrets.yaml werden nur fehlende Einträge ergänzt, nichts wird überschrieben. Hinweis: Das ESPHome-Add-on liegt bei Home Assistant OS meist nicht im Ordner /config/esphome. Dann die Adresse des Device Builders eintragen (im Add-on den Port 6052 freigeben). Vorhandene Secrets bleiben unangetastet. Das Passwort wird im Speicher von Home Assistant abgelegt (.storage, auch in Backups) und nie wieder im Panel angezeigt."));
    return d;
  }

  async _loadDeploy() {
    try { this._deploySet = await this._ws("deploy_settings"); this._renderOutput(); } catch { /* egal */ }
  }

  async _deploy() {
    this._deployMsg = { text: "Speichere …" };
    this._renderOutput();
    try {
      await this._save?.();
    } catch { /* Projekt-Speichern ist optional */ }
    try {
      const r = await this._ws("deploy", { project: this.p });
      const parts = [`${tx("Gespeichert:")} ${r.where}${r.backup ? tx(" (alte Datei als .bak gesichert)") : ""}.`];
      this._prevBackup = r.previous ? { name: `${this.p.name}.vorher.yaml`, text: r.previous } : null;
      if (r.previous) parts.push(tx("Die vorherige Version der Datei wurde überschrieben. Du kannst sie unten herunterladen."));
      if (r.secrets_added?.length) parts.push(`secrets.yaml ergänzt: ${r.secrets_added.join(", ")}.`);
      if (r.secrets_conflicts?.length) parts.push(`Nicht überschrieben (anderer Wert in der secrets.yaml): ${r.secrets_conflicts.join(", ")}. Gerät dann ggf. von Hand angleichen.`);
      this._deployMsg = { text: parts.join(" ") };
      if (r.warning) this._deployMsg = { err: true, text: `${parts.join(" ")} ${tx("ACHTUNG:")} ${r.warning}` };
    } catch (e) {
      this._deployMsg = { err: true, text: e?.message || "Speichern in ESPHome ist fehlgeschlagen." };
    }
    this._renderOutput();
  }

  async _copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch { /* Fallback */ }
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      this.shadowRoot.append(ta); ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch { return false; }
  }

  _download(name, text) {
    const url = URL.createObjectURL(new Blob([text], { type: name.endsWith(".json") ? "application/json" : "text/yaml;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = name;
    this.shadowRoot.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

if (!customElements.get("esphome-studio-panel")) customElements.define("esphome-studio-panel", ESPHomeStudioPanel);
