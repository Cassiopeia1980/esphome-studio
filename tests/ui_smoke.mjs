// UI-Rauchtest: lädt das Panel in jsdom und spricht über tests/bridge.py mit dem echten Generator.
// Aufruf: node tests/ui_smoke.mjs   (jsdom muss unter /tmp/jsdom-test installiert sein)
import { createRequire } from "node:module";
import { readFileSync, rmSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire("/tmp/jsdom-test/package.json");
const { JSDOM } = require("jsdom");
const here = path.dirname(fileURLToPath(import.meta.url));
const stateFile = "/tmp/esphome-studio-ui-state.json";
if (existsSync(stateFile)) rmSync(stateFile);

const dom = new JSDOM("<!doctype html><html><body></body></html>", { runScripts: "outside-only", pretendToBeVisual: true, url: "http://localhost/" });
dom.window.localStorage.setItem("esphome_studio_mode", "pro"); // die bisherigen Prüfungen laufen in der Profi-Ansicht
const { window } = dom;
window.eval(readFileSync(path.join(here, "../custom_components/esphome_studio/frontend/esphome-studio-panel.js"), "utf8"));

let calls = 0;
const hass = {
  connection: {
    sendMessagePromise: async (msg) => {
      calls++;
      const out = execFileSync("python3", ["-I", path.join(here, "bridge.py"), stateFile], { input: JSON.stringify(msg) });
      return JSON.parse(out.toString());
    },
  },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const el = window.document.createElement("esphome-studio-panel");
window.document.body.append(el);
el.hass = hass;
const root = el.shadowRoot;

let failures = 0;
const check = (name, cond, extra = "") => {
  console.log(`${cond ? "OK   " : "FEHLER"} ${name}${!cond && extra ? " -> " + extra : ""}`);
  if (!cond) failures++;
};
const fire = (node, type) => node.dispatchEvent(new window.Event(type, { bubbles: true }));
const setValue = (node, v, type = "input") => { node.value = v; fire(node, type); };
const yamlText = () => root.querySelector("pre.code")?.textContent || "";
const card = (title) => [...root.querySelectorAll(".card")].find((c) => c.querySelector("h2")?.textContent.startsWith(title));
const button = (scope, text) => [...scope.querySelectorAll("button")].find((b) => b.textContent.trim() === text);
const settle = async () => { await sleep(500); };

await sleep(1500);
check("Panel gestartet, Karten vorhanden", root.querySelectorAll(".card").length >= 5, root.textContent.slice(0, 200));
check("YAML erzeugt", yamlText().includes("esphome:") && yamlText().includes("name: neues-geraet"), yamlText().slice(0, 100));

// Gerätename ändern
const devCard = card("Gerät");
const nameInput = devCard.querySelector("input[type=text]");
setValue(nameInput, "kueche-licht");
await settle();
check("Gerätename im YAML", yamlText().includes("name: kueche-licht"));

// Komponente hinzufügen
const compCard = card("Komponenten");
const adder = compCard.querySelector("select");
adder.value = "switch";
button(compCard, "Hinzufügen").click();
await settle();
check("Relais-Karte erscheint", !!card("Komponenten (1)"), card("Komponenten")?.querySelector("h2")?.textContent);
check("Fehler wegen fehlendem Pin", root.querySelector(".msg.err")?.textContent.includes("kein Pin"), root.querySelector(".msg.err")?.textContent);
check("Kopieren gesperrt bei Fehler", button(root.querySelector(".out"), "Kopieren").disabled === true);

// Pin wählen
const pinSel = card("Komponenten").querySelector(".comp .grid select");
setValue(pinSel, "GPIO5", "change");
await settle();
check("Pin GPIO5 im YAML", /platform: gpio[\s\S]*GPIO5/.test(yamlText()), yamlText().slice(-400));
check("Keine Fehler mehr", !root.querySelector(".msg.err"), root.querySelector(".msg.err")?.textContent);
check("Kopieren aktiv", button(root.querySelector(".out"), "Kopieren").disabled === false);

// Pin-Tabelle: D5 (GPIO14) als Taster
const rows = [...root.querySelectorAll("table.pins tbody tr")];
const d5 = rows.find((r) => r.firstChild.textContent.includes("D5"));
const fsel = d5.querySelector("select");
check("Pin-Tabelle hat Auswahl für D5", !!fsel);
setValue(fsel, "binary_sensor", "change");
await settle();
check("Taster im YAML", yamlText().includes("binary_sensor:") && yamlText().includes("GPIO14"), yamlText().slice(-300));

// Belegter Pin ist in der Auswahl gesperrt
const sw = card("Komponenten").querySelectorAll(".comp")[0];
const optBusy = [...sw.querySelectorAll("select")[0].options].find((o) => o.value === "GPIO14");
check("Von Taster belegter Pin ist gesperrt", optBusy?.disabled === true, optBusy?.textContent);

// I²C-Komponente
const adder2 = card("Komponenten").querySelector("select");
adder2.value = "bme280";
button(card("Komponenten"), "Hinzufügen").click();
await settle();
check("I²C-Box erscheint", [...root.querySelectorAll(".comp strong")].some((s) => s.textContent.includes("I²C")));
check("i2c im YAML", yamlText().includes("i2c:") && yamlText().includes("bme280_i2c"), yamlText().slice(-200));

// Board wechseln
const boardSel = card("Gerät").querySelectorAll("select")[0];
setValue(boardSel, "esp32dev", "change");
await settle();
check("ESP32-Block im YAML", yamlText().includes("esp32:") && yamlText().includes("esp32dev") && yamlText().includes("esp-idf"), yamlText().slice(0, 300));
check("I²C-Pins an ESP32 angepasst", yamlText().includes("GPIO21") && yamlText().includes("GPIO22"));
check("Pin GPIO5 bleibt erhalten", yamlText().includes("GPIO5"));

// Doppelte Pinbelegung über Tastatur-Weg ist nicht möglich -> Fehler per Namensdoppelung prüfen
const nameInputs = card("Komponenten").querySelectorAll(".tname");
setValue(nameInputs[1], nameInputs[0].value);
await settle();
check("Doppelter Name wird gemeldet", [...root.querySelectorAll(".msg.err")].some((m) => m.textContent.includes("doppelt")));
setValue(nameInputs[1], "Taster");
await settle();

// Secrets-Tab
const secTab = button(root.querySelector(".out"), "secrets.yaml");
secTab.click();
await sleep(100);
check("secrets-Reiter zeigt API-Schlüssel", yamlText().includes("kueche_licht_api_key"), yamlText());
const wifi = card("WLAN").querySelectorAll("input[type=password], input[type=text]");
console.log("wifi inputs:", wifi.length, wifi[0].type, wifi[1].type);
setValue(wifi[0], "Mein Netz");
setValue(wifi[1], "supergeheim");
await sleep(1300);
check("WLAN-Name im secrets-Reiter", yamlText().includes('wifi_ssid: "Mein Netz"'), yamlText());
const state1 = JSON.parse(readFileSync(stateFile, "utf8"));
check("Secrets im Speicher abgelegt", state1.secrets.wifi_ssid === "Mein Netz" && state1.secrets.wifi_password === "supergeheim");

// Speichern, Neu, Laden
button(card("Projekte"), "Speichern").click();
await sleep(1200);
const state2 = JSON.parse(readFileSync(stateFile, "utf8"));
check("Projekt gespeichert", Object.keys(state2.projects).length === 1 && Object.values(state2.projects)[0].name === "kueche-licht");
check("Status zeigt „Gespeichert“", card("Projekte").textContent.includes("Gespeichert"));

button(card("Projekte"), "Duplizieren").click();
await sleep(1500);
check("Duplikat ist ungespeichert und umbenannt", card("Projekte").textContent.includes("Nicht gespeichert") && yamlText().length > 0
  && card("Gerät").querySelector("input[type=text]").value.includes("kopie"), card("Gerät").querySelector("input[type=text]").value);


// Neue Felder: Beschreibung, Platzhalter, Diagnose, Pin-Hinweis
button(root.querySelector(".out"), "ESPHome YAML").click();
await sleep(100);
const devC = card("Gerät");
const textInputs = [...devC.querySelectorAll("input[type=text]")];
const commentIn = textInputs.find((i) => i.placeholder === "Aquarium im Wohnzimmer");
check("Beschreibungsfeld vorhanden", !!commentIn);
setValue(commentIn, "Aquarium im Wohnzimmer");
const substBox = [...devC.querySelectorAll("label.check")].find((l) => l.textContent.includes("Platzhalter"));
substBox.querySelector("input").checked = true; fire(substBox.querySelector("input"), "change");
await settle();
check("Platzhalter und Kommentar im YAML", yamlText().includes("substitutions:") && yamlText().includes("comment: ${device_description}"), yamlText().slice(0, 300));
const netC = card("WLAN");
const bssid = [...netC.querySelectorAll("label.check")].find((l) => l.textContent.includes("BSSID"));
bssid.querySelector("input").checked = true; fire(bssid.querySelector("input"), "change");
const dbg = [...card("WLAN").querySelectorAll("label.check")].find((l) => l.textContent.includes("Freier Speicher"));
dbg.querySelector("input").checked = true; fire(dbg.querySelector("input"), "change");
await settle();
check("BSSID und Debug im YAML", yamlText().includes("bssid:") && yamlText().includes("debug:") && yamlText().includes("platform: debug"), yamlText().slice(-500));
check("Debug-Intervall-Feld erscheint", !!([...card("WLAN").querySelectorAll("input[type=text]")].find((i) => i.placeholder === "30s")));

// --- Board-Suche: alle Boards, Beken ---
{
  const dev = card("Gerät");
  const sel = dev.querySelectorAll("select")[0];
  const search = dev.querySelector("input[type=search]");
  const total = sel.querySelectorAll("option").length;
  check("Board-Liste enthält über 500 Boards", total > 500, String(total));
  const groups = [...sel.querySelectorAll("optgroup")].map((g) => g.label);
  check("Gruppen für Beken und Realtek", groups.includes("Beken BK7231N") && groups.some((g) => g.startsWith("Realtek")), groups.join(","));
  setValue(search, "cb2s");
  const hits = [...sel.querySelectorAll("option")].map((o) => o.value);
  check("Suche findet CB2S", hits.includes("cb2s") && hits.length < 10, hits.join(","));
  setValue(sel, "cb2s", "change");
  await sleep(1200);
  check("Beken-Block im YAML", yamlText().includes("bk72xx:") && yamlText().includes("board: cb2s"), yamlText().slice(0, 400));
  const pinTable = card("GPIO");
  check("Pin-Tabelle zeigt P-Pins", !!pinTable && pinTable.textContent.includes("P6") && pinTable.textContent.includes("P24"));
  const adder = card("Komponenten").querySelector("select");
  const opts = [...adder.querySelectorAll("option")].map((o) => o.value);
  check("Beken: kein I²C-Sensor, kein LED-Streifen", !opts.includes("bme280") && !opts.includes("light_strip") && opts.includes("light_pwm"), opts.join(","));
}

// --- YAML-Import ---
{
  const yamlIn = readFileSync(path.join(here, "samples/messy.yaml"), "utf8");
  const secIn = readFileSync(path.join(here, "samples/messy_secrets.yaml"), "utf8");
  button(card("Projekte"), "YAML importieren").click();
  await sleep(100);
  const imp = card("Bestehende YAML");
  check("Import-Karte öffnet sich", !!imp);
  const [ta1, ta2] = imp.querySelectorAll("textarea");
  setValue(ta1, yamlIn);
  setValue(ta2, secIn);
  button(imp, "Importieren").click();
  await sleep(2500);
  const rep = card("Import abgeschlossen");
  check("Import-Bericht erscheint", !!rep && /\d+ Komponenten/.test(rep.textContent), rep?.textContent.slice(0, 200));
  check("Gerätename aus Import", card("Gerät").querySelector("input[type=text]").value === "terrasse");
  check("Zusatz-YAML ist gefüllt", card("Gerät").querySelector("textarea").value.includes("globals:"));
  check("Zusatz-YAML im Ergebnis", yamlText().includes("script:") && yamlText().includes("on_boot:") && yamlText().includes("esp8266:"), yamlText().slice(0, 200));
  check("Kein Fehler nach Import", ![...root.querySelectorAll(".msg.err")].length, [...root.querySelectorAll(".msg.err")].map((m) => m.textContent).join("|"));
}

// --- Aus ESPHome laden ---
{
  button(card("Projekte"), "Aus ESPHome laden").click();
  await sleep(300);
  const imp = card("Bestehende YAML");
  check("Quellen-Liste erscheint", !!imp && !!imp.querySelector("select") && imp.textContent.includes("kueche.yaml"), imp?.textContent.slice(0, 200));
  button(imp, "Laden und importieren").click();
  await sleep(2500);
  check("Import aus ESPHome: Gerätename", card("Gerät").querySelector("input[type=text]").value === "kueche");
  check("Import aus ESPHome: kein Fehler", ![...root.querySelectorAll(".msg.err")].length);
}

// --- Katalog ---
{
  const det = () => card("Komponenten").querySelector("details");
  check("Katalog-Bereich vorhanden", !!det());
  setValue(det().querySelector("input[type=search]"), "bme680");
  await sleep(900);
  const selsAll = [...det().querySelectorAll("select")];
  const opts = [...selsAll[selsAll.length - 1].querySelectorAll("option")].map((o) => o.value);
  check("Suche findet bme680", opts.includes("bme680.sensor") && opts.length < 6, opts.join(","));
  const selects = [...det().querySelectorAll("select")];
  const entrySel = selects[selects.length - 1];
  entrySel.value = "bme680.sensor";
  button(det(), "Hinzufügen").click();
  await sleep(1500);
  check("Katalog-Baustein im YAML", yamlText().includes("platform: bme680"), yamlText().slice(-600));
  const myComp = () => [...card("Komponenten").querySelectorAll(".comp")].find((c) => c.querySelector("input.tname")?.value === "bme680");
  const c2 = myComp();
  check("Karte mit Messwerten", !!c2 && c2.textContent.includes("Temperatur") && c2.textContent.includes("Luftfeuchte"));
  check("I²C-Box erscheint", card("Komponenten").textContent.includes("I²C-Bus"));
  const iv = [...c2.querySelectorAll("input[type=text]")].find((i) => i.placeholder.startsWith("Standard:") && i.placeholder.includes("60s"));
  check("Aktualisierungs-Feld", !!iv);
  setValue(iv, "30s");
  await sleep(900);
  check("Intervall im YAML", yamlText().includes("update_interval: 30s"));
  const errs = [...root.querySelectorAll(".msg.err")].map((m) => m.textContent).filter((t) => !t.includes("doppelt belegt"));
  check("Kein Fehler nach Katalog (außer Pin-Überschneidung mit dem alten Projekt)", !errs.length, errs.join("|"));
  // Zusatz-YAML des Bausteins
  const c3 = myComp();
  setValue(c3.querySelector("textarea"), "device_class: temperature");
  await sleep(900);
  check("Baustein-Zusatz-YAML im YAML", yamlText().includes("device_class: temperature"));

  // Profi-Einstellungen
  const pd = () => [...myComp().querySelectorAll("details")].find((d) => d.textContent.includes("Profi-Einstellungen"));
  check("Profi-Einstellungen vorhanden", !!pd());
  const ents = () => [...pd().querySelectorAll(".ent")];
  const tempEnt = () => ents().find((e) => e.textContent.includes("Temperatur"));
  setValue([...tempEnt().querySelectorAll("input[type=text]")].find((i) => i.placeholder === "mdi:thermometer"), "mdi:home-thermometer");
  setValue([...tempEnt().querySelectorAll("input[type=text]")].find((i) => i.placeholder === "°C"), "°F");
  await sleep(900);
  check("Icon und Einheit im YAML", yamlText().includes("mdi:home-thermometer") && yamlText().includes("unit_of_measurement"), yamlText().slice(-900));
  const addSel = () => [...tempEnt().querySelectorAll(".filters select")].at(-1);
  setValue(addSel(), "offset", "change");
  await sleep(1200);
  const frow = () => tempEnt().querySelector(".frow");
  check("Filterzeile erscheint", !!frow());
  setValue(frow().querySelector("input"), "-1.5");
  await sleep(900);
  check("Filter im YAML", yamlText().includes("filters:") && yamlText().includes("offset: -1.5"), yamlText().slice(-700));
  setValue(frow().querySelector("input"), "abc");
  await sleep(900);
  check("Ungültiger Filterwert wird gemeldet", [...root.querySelectorAll(".msg.err")].some((m) => m.textContent.includes("Zahl")));
  frow().querySelector("button.danger").click();
  await sleep(1200);
  check("Filter entfernt", !tempEnt().querySelector(".frow"));
}

// --- Einfacher Modus und Start-Assistent ---
{
  el._setSimple(true);
  check("Einfach-Modus: Pin-Tabelle ausgeblendet", !card("GPIO"));
  check("Einfach-Modus: Zusatz-YAML ausgeblendet", !card("Gerät").querySelector("textarea"));
  check("Einfach-Modus: Import-Knopf ausgeblendet", !button(card("Projekte"), "YAML importieren"));
  check("Einfach-Modus: Weiter-Anleitung", !!card("Fertig") || root.textContent.includes("So geht’s weiter"));
  // neues Projekt -> Assistent
  button(card("Projekte"), "Neu").click();
  await sleep(1500);
  const wiz = card("Los geht");
  check("Assistent erscheint bei leerem Projekt", !!wiz);
  const chip = [...wiz.querySelectorAll(".chip")].find((c) => c.textContent.includes("ESP32 DevKit"));
  chip.click();
  await sleep(1200);
  const wiz2 = card("Los geht");
  const tpls = [...wiz2.querySelectorAll(".tpl")];
  check("17 Vorlagen", tpls.length === 17, String(tpls.length));
  const strip = tpls.find((t) => t.textContent.includes("LED-Streifen"));
  check("ESP32: LED-Streifen verfügbar", !strip.disabled);
  [...wiz2.querySelectorAll(".chip")].find((c) => c.textContent.includes("ESP-01")).click();
  await sleep(1200);
  const tpls8266 = [...card("Los geht").querySelectorAll(".tpl")];
  check("ESP-01: Wetterstation nicht möglich (kein I²C-Pin frei)", tpls8266.find((t) => t.textContent.includes("Wetterstation")).disabled === true);
  [...card("Los geht").querySelectorAll(".chip")].find((c) => c.textContent.includes("D1 Mini")).click();
  await sleep(1200);
  const rb = [...card("Los geht").querySelectorAll(".tpl")].find((t) => t.textContent.includes("Relais mit Taster"));
  check("D1 Mini: Relais mit Taster möglich", !rb.disabled);
  rb.click();
  await sleep(1500);
  check("Assistent verschwindet nach Vorlage", !card("Los geht"));
  check("Vorlage: Relais und Taster im YAML", yamlText().includes("platform: gpio") && yamlText().includes("binary_sensor:") && yamlText().includes("on_press"), yamlText().slice(-700));
  check("Vorlage: Gerätename gesetzt", yamlText().includes("name: schalter"), yamlText().slice(0, 200));
  check("Vorlage: Pins ohne Boot-Pins", !/GPIO(0|2|15)\b/.test(yamlText().split("binary_sensor:")[0].split("switch:")[1] || ""), yamlText());
  check("Vorlage erzeugt keinen Fehler", ![...root.querySelectorAll(".msg.err")].filter((m) => !m.textContent.includes("WLAN")).length,
    [...root.querySelectorAll(".msg.err")].map((m) => m.textContent).join("|"));
  const cc = card("Komponenten");
  check("Einfach-Modus: Zusatzeinstellungen eingeklappt", [...cc.querySelectorAll("details")].some((d) => d.textContent.includes("Weitere Einstellungen")));
  el._setSimple(false);
  check("Profi-Modus: Pin-Tabelle wieder da", !!card("GPIO"));

  // Alle Vorlagen auf mehreren Boards erzeugen und für die ESPHome-Prüfung ablegen
  if (process.env.TPL_DIR) {
    const { mkdirSync, writeFileSync } = await import("node:fs");
    mkdirSync(process.env.TPL_DIR, { recursive: true });
    el._setSimple(true);
    let n = 0;
    for (const board of ["d1_mini", "nodemcuv2", "esp32dev", "esp32-c3-devkitm-1", "cb2s", "rpipicow"]) {
      await el._newProject(board);
      const tplIds = el.p.components.length;
      for (const id of ["relay", "relay_btn", "light", "dimmer", "rgb", "strip", "dht", "bme", "ds", "door", "ir"]) {
        await el._newProject(board);
        el._wizardOff = false;
        const tpl = [...el.shadowRoot.querySelectorAll(".tpl")];
        el._renderAll();
        const btn = [...root.querySelectorAll(".tpl")][["relay", "relay_btn", "light", "dimmer", "rgb", "strip", "dht", "bme", "ds", "door", "ir"].indexOf(id)];
        if (!btn || btn.disabled) continue;
        btn.click();
        await sleep(900);
        const o = el.out;
        check(`Vorlage ${id} auf ${board}: keine Fehler`, o.errors.every((e) => e.includes("WLAN")), o.errors.join("|"));
        writeFileSync(`${process.env.TPL_DIR}/${board}__${id}.yaml`, o.yaml);
        writeFileSync(`${process.env.TPL_DIR}/${board}__${id}.secrets`, o.secrets);
        n++;
      }
    }
    check("Vorlagen-Dateien geschrieben", n > 30, String(n));
  }
}

// Projekt exportieren und wieder laden
{
  let captured = null;
  window.URL.createObjectURL = (blob) => { captured = blob; return "blob:test"; };
  window.URL.revokeObjectURL = () => {};
  window.HTMLAnchorElement.prototype.click = function () {};
  const exp = button(root, "Exportieren");
  check("Export-Schaltfläche da", !!exp);
  if (exp) {
    exp.click();
    const text = captured ? await captured.text() : "";
    const data = text ? JSON.parse(text) : null;
    check("Export enthält Projekt ohne Schlüssel", data?.format === "esphome-studio-project" && data.project.api.key === "" && data.project.ota.password === "" && Array.isArray(data.project.components), text.slice(0, 120));
    const name = data.project.name;
    el.p.name = "anderer-name";
    await el._importProjectFile({ text: async () => text });
    await settle();
    check("Import stellt Projekt wieder her", el.p.name === name && el.pid === null && el.dirty === true);
    check("Import erzeugt neue Schlüssel", el.p.api.key.length > 10 && el.p.ota.password.length > 5);
    await el._importProjectFile({ text: async () => "kein json" });
    check("Ungültige Datei ändert nichts", el.p.name === name);
  }
}

{
  const bad = [...root.querySelectorAll("*")].flatMap((n) => [...n.childNodes].filter((c) => c.nodeType === 3 && /^(null|undefined|NaN)$/.test(c.textContent.trim())));
  check("Kein verirrtes „null“ im Panel", bad.length === 0, String(bad.length));
}

console.log(`\nBackend-Aufrufe: ${calls}, Fehler: ${failures}`);
process.exit(failures ? 1 : 0);
