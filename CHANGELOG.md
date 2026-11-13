# Changelog

## 0.17.6
- `cleanup` schaltet jetzt beide Uptime-Sensoren des Studios an (Laufzeit als Zahl und Betriebszeit als Text) und übernimmt Name, Symbol und Kategorie eines entfernten Zahl-Sensors, damit die Entität in Home Assistant dieselbe bleibt
- Neu: `patch.restore_uptime_names: true` holt den Namen des früheren sichtbaren Uptime-Sensors aus der ersten Sicherung (Substitutionen aufgelöst); für Geräte, die schon bereinigt wurden

## 0.17.5
- Fix: `cleanup` behält einen internen Uptime-Sensor, wenn andere Teile ihn per `id(...)` nutzen (z. B. Start-Sperre im Schalter-Lambda); vorher blockierte die ID-Prüfung das Gerät

## 0.17.4
- Neu: `patch.cleanup: true` bei `esphome_studio/project_patch` räumt die Diagnose auf: Web-Server aus, Debug-Sensoren bis auf den Reset-Grund aus, Betriebszeit nur als Text (Zahl-Laufzeit aus). Auch im Zusatz-YAML werden `web_server`, `uptime`-Sensoren, Debug-Sensoren und alte Lambda-Betriebszeiten entfernt; Name, Symbol und Kategorie der bisherigen Text-Betriebszeit bleiben erhalten, damit die Entität in Home Assistant dieselbe bleibt
- Neu: `esphome_studio/bulk_patch` wendet dieselbe Änderung auf viele Geräte an und meldet je Gerät nur Fehler und Hinweise
- `project_patch` speichert und deployt nichts mehr, wenn das erzeugte YAML Fehler oder fehlende IDs hat

## 0.17.3
- Fix: die ID-Prüfung kennt jetzt aus dem Namen abgeleitete IDs (ESPHome erzeugt `display_brightness` aus „Display Brightness“) und ignoriert Typangaben bei `variables:` von API-Diensten; vorher meldete sie fälschlich fehlende IDs

## 0.17.2
- Fix: beim Import behält ein abgebildeter Baustein seine `id`, wenn das Zusatz-YAML (Lambda, Skript, Automation) darauf verweist; vorher fehlte die ID im erzeugten YAML und ESPHome meldete einen Fehler
- Neu: Prüfung auf Verweise auf nicht vorhandene IDs; `source_import`/`project_patch` schreiben solches YAML nicht mehr, neuer Befehl `esphome_studio/check_all` prüft alle gespeicherten Projekte

## 0.17.1
- Import: eine Taster-Aktion (z. B. `light.toggle`), deren Ziel das Studio nicht abbilden kann, geht nicht mehr verloren; der Taster bleibt unverändert im Zusatz-YAML
- Import: `one_wire:` in der alten Schreibweise (ein Eintrag statt Liste) und ein DS18B20 ohne `one_wire_id` werden erkannt, statt den Bus zu verwerfen
- Vergleich beim Umbau ignoriert Standardwerte (`resolution: 12`, `update_interval: 60s`) und die Schreibweise von `one_wire`

## 0.17.0
- Neu: **einmalige Umstellung auf OTA-Verschlüsselung** (ESPHome ab 2026.10, `allow_plaintext_upload`). Ein Gerät, das noch mit OTA-Passwort läuft, nimmt das nächste Update noch mit dem alten Passwort an und ist danach verschlüsselt, ohne USB-Flash. Option „Einmalige Umstellung von OTA-Passwort“ im Bereich „WLAN, Secrets & Sicherheit“; nach dem erfolgreichen Update ausschalten und neu speichern. Der Import erkennt diesen Zustand
- Neue Websocket-Befehle zum Umbauen vieler bestehender Geräte (für Automatisierungen und Assistenten):
  - `esphome_studio/source_import`: holt ein Gerät aus dem Device Builder, speichert es als Projekt und kann es auf Wunsch gleich auf den aktuellen Stand heben (`upgrade`: API und OTA verschlüsseln, mit einmaliger Umstellung), einzelne Einstellungen ändern (`patch`) und deployen (`deploy`). Liefert einen Vergleich zwischen alter und neu erzeugter YAML (ohne umbenannte interne IDs und Reihenfolge), damit Unterschiede auffallen
  - `esphome_studio/project_patch`: ändert einzelne Einstellungen eines gespeicherten Projekts, Bausteine über ihren Namen
  - `esphome_studio/backup_get` / `esphome_studio/backup_restore`: Vor jedem Deploy in den Device Builder wird die bisherige YAML gesichert (die allererste Fassung bleibt dauerhaft erhalten) und lässt sich zurückschreiben
- Deploy: Heißt die Datei im Device Builder anders als das Gerät (z. B. `kellerlicht.yaml` für das Gerät `keller`), schreibt das Studio in dieselbe Datei, statt eine zweite anzulegen

## 0.16.0
- Neu für ESP8266-Geräte: Option „Zustände bei Stromausfall behalten“ im Bereich „Gerät“ (`esp8266: restore_from_flash`). Ohne sie behält ein ESP8266 gespeicherte Werte (Lichter, Schalter, `restore_value`) nur bei einem Neustart, nicht bei einem Stromausfall. Standard „Automatisch“: das Studio schaltet die Option ein, sobald im fertigen YAML etwas seinen Zustand wiederherstellen soll (Lichter mit `restore_*`, Schalter ohne `restore_mode`, `restore_value: true`, auch im Zusatz-YAML). Der Flash wird nur beschrieben, wenn sich ein Wert ändert
- Der Import übernimmt ein vorhandenes `restore_from_flash` (an/aus) in diese Option, statt es ins Zusatz-YAML zu legen
- Geräte, die nichts wiederherstellen, bekommen die Zeile nicht

## 0.15.1
- Neue Projekte schreiben bei Lichtern jetzt `restore_state` (ESPHome ab 2026.10). Bestehende, gespeicherte Projekte behalten ihre Schreibweise; der Haken „Neue Schreibweise für „Zustand nach Neustart““ im Bereich „Gerät“ schaltet um. Mit ESPHome 2026.9 oder älter den Haken entfernen
- Der Import überführt `restore_mode` aus alten YAMLs beim Neuerzeugen in die neue Schreibweise (Haken entfernen, wenn das nicht gewünscht ist)

## 0.15.0
- ESPHome 2026.10 ersetzt bei Lichtern `restore_mode` durch `restore_state` (das alte `restore_mode` läuft dort noch). Das Studio kann jetzt beides: die Option „Neue Schreibweise für „Zustand nach Neustart“ bei Lichtern“ im Bereich „Gerät“ schreibt `restore_state` (+ `initial_state`) mit identischem Verhalten für alle 8 Modi. **Standard bleibt aus**, weil ESPHome 2026.9 `restore_state` nicht kennt und das Kompilieren abbricht
- Der Import liest beide Schreibweisen und schaltet die Option ein, wenn die YAML schon `restore_state` benutzt. Einzelne Felder (z. B. `brightness`) bleiben im Zusatz-YAML
- Alle Studio-Beispiele und die drei Beispielgeräte sind gegen ESPHome 2026.10.0 geprüft

## 0.14.0
- Neue Option „Ein Hotspot-Passwort für alle Geräte“ (Standard bei neuen Projekten): das Passwort des Fallback-Hotspots liegt wie das WLAN-Passwort einmal im Speicher von Home Assistant und steht im secrets.yaml-Block als `ap_password`. Bestehende Projekte behalten ihr Passwort pro Gerät
- Der Import erkennt `!secret ap_password` als gemeinsames Hotspot-Passwort und übernimmt den Wert in den Speicher

## 0.13.0
- Der Baustein „Taster / Reed-Kontakt / Türkontakt“ kann jetzt ein Licht/Relais dem Kontakt **folgen** lassen (aus/an bei geschlossenem Kontakt) und beim Start den Zustand angleichen (`on_boot`); der Import erkennt dieses Muster samt `delayed_on` + `delayed_off`
- Import-Option „Namen der Diagnose-Entitäten und Lichteffekte auf den Studio-Standard vereinheitlichen“ (Standard: an), damit alle Geräte gleiche Namen bekommen; ohne Haken bleiben eigene Namen

## 0.12.1
- Fix zu 0.12.0: `restore_mode` bei Lichtern wurde beim Import verworfen, obwohl `RESTORE_DEFAULT_OFF` nicht der ESPHome-Standard ist (der ist `ALWAYS_OFF`). Dadurch hätte das Licht nach einem Neustart seinen letzten Zustand nicht behalten
- Lichter haben jetzt die Einstellung „Zustand nach Neustart“; der Import übernimmt den Wert

## 0.12.0
- Import erkennt Diagnose-Blöcke mit eigenen Namen, Symbolen und Formaten (Uptime/WLAN-Info/Debug/Status/Neustart/WLAN-Signal, auch ohne `entity_category`) und behält sie bei, statt sie ins Zusatz-YAML zu schieben
- Lichter mit eigenen Effekt-Namen werden übernommen; die Begründung bei nicht abbildbaren Lichteffekten ist jetzt richtig

## 0.11.1
- „In ESPHome speichern“ über den Device Builder sichert die vorherige Version: nach dem Speichern gibt es den Knopf „Vorherige Version herunterladen“ (der Device Builder legt selbst keine .bak an)
- Hinweis zu den Schlüsseln im Import-Bericht erscheint nur noch, wenn wirklich eine API-Verschlüsselung vorhanden ist

## 0.11.0
- Neu: optionaler **Secrets-Speicher** (auf eigene Gefahr): die ganze secrets.yaml einmal ablegen, beim Import werden benutzte `!secret`-Werte automatisch ergänzt (gemeinsame API-Schlüssel und Passwörter bleiben dadurch erhalten); eingefügte Zeilen haben Vorrang
- Werte werden nie an das Panel zurückgegeben, nur die Namen; neuer Websocket-Befehl `secret_store`

## 0.10.1
- „Aus ESPHome laden“ importiert nicht mehr sofort: erst „Laden“, dann Secret-Prüfung (bekannt/fehlt, fehlende Werte einfügen), dann „Importieren“; der Bericht nennt leer gebliebene Secrets

## 0.10.0
- Neu: **„Aus ESPHome laden“** – bestehende Geräte-YAMLs direkt aus dem ESPHome Device Builder (oder dem ESPHome-Ordner) wählen und ins Studio importieren, um sie auf den aktuellen Stand zu bringen; kein Kopieren mehr nötig
- Neue Websocket-Befehle `source_list` und `source_get`; im Ordner-Modus werden nur die von der YAML benutzten Secrets übernommen

## 0.9.1
- Katalog-Generator ist jetzt deterministisch (gleiche ESPHome-Version ergibt immer dieselbe catalog.json), der monatliche Update-Pull-Request erscheint nur noch bei echten Änderungen

## 0.9.0
- 17 Vorlagen (neu: Zwei Relais, Bewegungsmelder, SHT3x, BH1750, HC-SR04, Spannung messen)
- Projekt exportieren/laden als Datei (ohne Schlüssel und Passwörter)
- Fix: verirrter Text „null“ im Ergebnis-Bereich; fehlende englische Texte ergänzt
- CI: Panel-Tests (de/en) und `esphome config` (de/en); monatlicher Daten-Update-Workflow; Issue-Vorlagen; Screenshots

## 0.8.0
- Zweisprachig: Deutsch und English, Sprachauswahl im Panel (Standard: Sprache von Home Assistant)
- Oberfläche, Katalog, Boards, Meldungen, Import und die erzeugten YAML-Namen/-Kommentare werden übersetzt
- Neuer Websocket-Befehl `i18n`, alle Befehle nehmen `lang` entgegen

## 0.7.2
- Warnung, wenn der Device Builder älter als ESPHome 2026.9 ist und OTA-Verschlüsselung gewählt ist; Hinweis bei der OTA-Absicherung

## 0.7.1
- Anmeldung (Benutzer/Passwort) am ESPHome Device Builder möglich

## 0.7.0
- „In ESPHome speichern“ (Ordner oder ESPHome Device Builder), secrets nur ergänzt
- Import erkennt Katalog-Bausteine
- 699 von 844 Katalog-Komponenten verifiziert (BLE-Sensoren legen den Tracker automatisch an)

## 0.6.2
- Fix: Text „nullnull“ unter dem Projekt-Block (append(null))

## 0.6.1
- Integrations-Icon (brand/icon.png)

## 0.6.0
- Profi-Einstellungen je Entität (Icon, Einheit, Geräteklasse, Filter …)
- Katalog mit ca. 884 Komponenten (661 mit `esphome config` verifiziert)
- Hubs/Referenzen automatisch, Port-Expander als Pin-Quelle
- IDs, die ESPHome-Integrationen heißen, bekommen `_id`

## 0.5.0
- Einsteigerhilfe: Start-Assistent mit 11 Vorlagen, einfacher Modus, „Wie geht es weiter?“

## 0.4.0
- web_server v1/2/3, Komponentenkatalog

## 0.1.0 – 0.3.0
- Grundfunktionen: Board-/GPIO-Auswahl, Secrets, WLAN, Sensoren, YAML-Erzeugung
