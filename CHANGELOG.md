# Changelog

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
