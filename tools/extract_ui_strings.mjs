// Zieht deutsche Texte aus dem Panel-JS (für die englische Übersetzung). Aufruf: node tools/extract_ui_strings.mjs
import fs from "node:fs";
const f = "custom_components/esphome_studio/frontend/esphome-studio-panel.js";
const s = fs.readFileSync(f, "utf8");
const out = new Set();
const re = /"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`|'((?:[^'\\\n]|\\.)*)'/g;
for (const r of s.matchAll(re)) {
  let t = r[1] ?? r[2] ?? r[3];
  if (r[2] !== undefined) { let i = 0; t = t.replace(/\$\{[^}]*\}/g, () => `{${i++}}`); }
  t = t.replace(/\\n/g, "\n").replace(/\\(["'`\\])/g, "$1");
  if (/[A-Za-zÄÖÜäöüß]{3}/.test(t) && /[ äöüÄÖÜß]|^[A-Z][a-zäöüß]+$/.test(t) && !/[;{}]\s*$|^\s*[.#:\w-]+\s*\{/.test(t)) out.add(t);
}
console.log(JSON.stringify([...out], null, 0).replace(/","/g, '",\n"'));
