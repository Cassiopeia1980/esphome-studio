# Mitmachen / Contributing

**Deutsch:** Fehler und Wünsche bitte als Issue melden (Vorlagen sind vorhanden). Pull Requests sind willkommen.
Bitte vorher die Tests laufen lassen:

```
pip install pytest-homeassistant-custom-component
pytest -q
npm install jsdom --prefix /tmp/jsdom-test
node tests/ui_smoke.mjs && node tests/ui_smoke_en.mjs
python tests/validate_with_esphome.py "$(which esphome)" && python tests/validate_with_esphome.py "$(which esphome)" --lang=en
```

**English:** Please report bugs and ideas as issues (templates included). Pull requests are welcome. Run the tests above first.

## Übersetzungen / Translations

- Deutscher Text ist der Quelltext und zugleich der Schlüssel. Englisch steht in `custom_components/esphome_studio/i18n_en.json` (Backend)
  und `i18n_ui_en.json` (Panel). `{0}`, `{1}` sind Platzhalter.
- `python tools/extract_i18n.py --missing` zeigt fehlende Übersetzungen. `node tests/ui_smoke_en.mjs` meldet deutsche Reste im englischen Panel.
- Neue Sprache: in `i18n.py` zu `LANGS` hinzufügen, ein Wörterbuch anlegen und im Panel die Auswahl ergänzen.

## Daten aus ESPHome / Data from ESPHome

`tools/gen_boards.py` und `tools/gen_catalog.py` lesen Boards und Komponenten aus einer installierten ESPHome-Version.
Der Workflow „Update ESPHome data“ macht das monatlich und öffnet einen Pull Request.
