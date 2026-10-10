# ESPHome Studio

Ein Konfigurator für ESPHome direkt in Home Assistant, ähnlich wie die GPIO-Konfiguration bei Tasmota:
Board wählen, jedem Pin eine Funktion geben, WLAN und Secrets eintragen, fertig ist die ESPHome-YAML.
Das Panel erscheint in der Seitenleiste von Home Assistant (nur für Administratoren).

## Was es kann

- **Anfängerhilfe:** Standardmäßig läuft das Panel im **Einfachen Modus** (Schalter oben rechts). Bei einem leeren
  Projekt führt ein Start-Assistent in drei Schritten durch: Board wählen, eine von 11 Vorlagen nehmen (Steckdose,
  Relais mit Taster, Licht, Dimmer, RGB, LED-Streifen, DHT22, BME280, DS18B20, Türkontakt, IR-Sender) und das WLAN
  eintragen. Die Pins sucht das Studio selbst aus (ohne Boot-, UART-, USB-, Flash-Pins). Vorlagen, die auf dem
  Board nicht gehen, sind ausgegraut. Im Einfachen Modus sind Pin-Tabelle, YAML-Import, Zusatz-YAML und
  Profi-Einstellungen ausgeblendet oder eingeklappt, und eine Anleitung erklärt den Weg bis zum Flashen.
  Der Profi-Modus zeigt alles wie bisher.

- **Alle Boards von ESPHome (über 500):** ESP8266 (45), ESP32 inkl. S2, S3, C2, C3, C5, C6, C61, H2, P4 (298),
  Raspberry Pi Pico / RP2040 / RP2350 (150) und **Beken BK72xx** (z. B. CB2S, WB2S, CBU, Tuya-Module),
  Realtek RTL87xx und Lightning LN882x. Die Board- und Pin-Daten liest `tools/gen_boards.py` direkt aus ESPHome
  (2026.9.1) aus. Die Board-Auswahl hat eine Suche und ist nach Chip gruppiert.
- **YAML-Import:** Eine bestehende ESPHome-YAML (optional mit secrets.yaml) einfügen. Das Studio übernimmt, was es selbst
  erzeugen kann, und behält alles andere (Skripte, Lambdas, Display, eigene Sensoren, `globals`, `interval` …)
  unverändert im Feld „Zusatz-YAML“. Es geht nichts verloren, nur Kommentare entfallen.
- **GPIO-Zuordnung wie bei Tasmota:** Eine Tabelle mit allen Pins, pro Pin ein Dropdown mit den Funktionen,
  die an diesem Pin möglich sind. Boot-Pins, UART-, USB-, PSRAM- und Flash-Pins sind markiert,
  ungeeignete Pins (z. B. Ausgang auf einem Nur-Eingang-Pin) sind gesperrt.
- **Komponenten:** Relais/Schalter (auch als Impuls), Status-LED, Licht an/aus, Licht dimmbar, RGB/RGBW/RGBWW,
  adressierbarer LED-Streifen (WS2812, SK6812, SM16703 … nur ESP32), Taster/Schalter/Kontakt
  (mit Entprellen und direktem Umschalten eines Relais oder Lichts), IR-Sender und -Empfänger,
  DHT11/22, DS18B20, Analog-Eingang, HC-SR04, BME280, BMP280, SHT3x, AHT10/20, BH1750.
- **Katalog mit allen ESPHome-Bausteinen:** Unter „Komponenten“ gibt es „Weitere Bausteine (Katalog)“ mit Suche und
  Filter. Der Katalog wird aus dem ESPHome-Schema erzeugt (`tools/gen_catalog.py`) und enthält 670 Sensoren,
  Binär-/Text-Sensoren, Schalter, Ausgänge, Lichter, Lüfter, Rollläden, Klima, Zahlen, Auswahlen, Schlösser, Ventile und
  Hubs (z. B. ADS1115, LD2410, Modbus). Pins, Pflichtfelder, Auswahllisten, Messwerte, I²C/SPI/UART und Verweise
  (z. B. Sensor → Hub, Lüfter → Ausgang) erzeugt das Panel automatisch aus den Katalogdaten. Pro Baustein gibt es
  ein Feld für weiteres YAML (z. B. `filters`, `device_class`).
  **Geprüft:** Jeder Baustein wurde mit `tools/verify_catalog.py` und dem echten `esphome config` auf ESP32, ESP8266,
  Pico und den LibreTiny-Chips ausprobiert. 427 Bausteine liefen durch und stehen standardmäßig in der Liste (nur
  auf den Plattformen, auf denen sie liefen). Die übrigen (z. B. Bluetooth, Modbus-Controller, Displays) sind
  über „Auch ungeprüfte Bausteine zeigen“ wählbar und mit „?“ markiert. Sie können zusätzliche Voraussetzungen
  haben, die das Studio noch nicht kennt.
- **Webserver:** Version 1, 2 oder 3, Port, Zugangsschutz (basic/digest, Zugangsdaten als Secrets), Firmware-Upload
  über die Webseite, Komprimierung, interne Entitäten, Dateien lokal laden, eigenes Stylesheet/Skript und erlaubte
  Herkunftsadressen. Version 1 ist veraltet (ESPHome entfernt sie mit 2027.1) und löst eine Warnung aus.
- **WLAN und Secrets:** SSID/Passwort einmal eintragen. Im YAML steht nur `!secret …`, die passenden Zeilen
  für die `secrets.yaml` gibt es in einem eigenen Reiter. Pro Gerät werden API-Schlüssel, OTA- und
  Hotspot-Passwort erzeugt, ihre Schlüsselnamen enthalten den Gerätenamen und kollidieren daher nicht.
  Wer lieber alles in einer Datei will, schaltet die Auslagerung ab.
- **Weitere Einstellungen:** Fallback-Hotspot mit Captive Portal, feste IP (mit Prüfung, ob Gateway und IP im
  selben Netz liegen), API-Verschlüsselung, OTA-Absicherung (verschlüsselt mit dem API-Schlüssel, per Passwort
  oder keine), Webserver, Uhrzeit von Home Assistant, Mindest-Verschlüsselung des WLANs (WPA/WPA2/WPA3),
  Beschreibung (`comment`) und Platzhalter (`substitutions` mit `devicename` und `device_description`),
  beim ESP8266 Flash-Modus und `early_pin_init`.
- **Diagnose-Entitäten:** Status, WLAN-Signal, Laufzeit (Sekunden oder als Text wie „2T 4Std 12Min“),
  IP-Adresse, SSID, BSSID, MAC-Adresse, Neustart-Knopf und zur Fehlersuche die Debug-Sensoren
  (freier Heap, größter Block, Loop-Zeit, Neustart-Grund).
- **Licht-Extras:** Effekte (Pulsieren, Zufällig, Blitzen) und „Name = Gerätename“ (`name: None`).
- **DS18B20:** Auflösung, Mindestpause (`throttle`) und Änderungsschwelle (`delta`) als kombinierter Filter.
- **Prüfung:** Doppelt belegte Pins, doppelte Namen, ungültige Gerätenamen, fehlende Pull-ups,
  ADC-Pins und mehr werden live gemeldet. Bei Fehlern sperrt das Panel Kopieren und Herunterladen.
- **Projekte:** Speichern, Laden, Duplizieren (mit neuen Schlüsseln), alles in Home Assistant.

## Installation (ZIP, von Hand)

1. ZIP entpacken.
2. Den Ordner `custom_components/esphome_studio` nach `/config/custom_components/` kopieren
   (z. B. mit dem Samba- oder dem Studio-Code-Server-Add-on).
3. Home Assistant neu starten.
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **ESPHome Studio**.
5. In der Seitenleiste erscheint **ESPHome Studio**. Beim ersten Öffnen einmal `Strg+F5` drücken.

### Installation über HACS (Repository ist vorbereitet)

1. Auf GitHub ein neues Repository `esphome-studio` anlegen und den Inhalt dieses Ordners hochladen.
2. Vorher einmal `sh tools/set_github_user.sh DEIN-GITHUB-NAME` ausführen (ersetzt `Cassiopeia1980`, setzt `codeowners`).
3. Release erstellen: Tag `v0.6.0` pushen. Der Workflow `release.yml` hängt `esphome_studio.zip` an.
4. In HACS: ⋮ → Benutzerdefinierte Repositories → URL einfügen, Typ **Integration**.
5. Die Workflows `Validate` (hassfest, HACS-Prüfung, Tests) laufen bei jedem Push automatisch.

## Benutzung

1. **Gerät:** Name (Hostname), Anzeigename und Board wählen.
2. **WLAN, Secrets & Sicherheit:** SSID und Passwort eintragen.
3. **GPIO-Zuordnung:** Pro Pin die Funktion wählen. Mehrpolige Bauteile (RGB-Licht, HC-SR04,
   I²C-Sensoren) fügst du unter *Komponenten* hinzu. Dort stellst du auch Namen und Optionen ein.
4. **Ergebnis** rechts: YAML kopieren oder herunterladen, in ESPHome ein neues Gerät anlegen und den
   Inhalt ersetzen. Die Zeilen aus dem Reiter *secrets.yaml* in die `secrets.yaml` von ESPHome einfügen.
5. Erstes Flashen per USB, danach per WLAN. In Home Assistant wird das Gerät dann automatisch gefunden.

## Grenzen und Hinweise

- Katalog-Bausteine werden beim YAML-Import **nicht** zurückgelesen. Sie bleiben dann im Zusatz-YAML erhalten
  (nichts geht verloren), erscheinen aber nicht als Karte. Dasselbe gilt für Webserver mit Zugangsschutz oder
  Firmware-Upload.
- Katalog-Bausteine ohne Prüfung („?“): Das Studio erzeugt die YAML nach dem ESPHome-Schema, hat sie aber nicht
  mit `esphome config` getestet. Immer die Meldungen von ESPHome beim Kompilieren beachten.
- Das YAML wird nur ausgegeben, nicht direkt in den ESPHome-Ordner geschrieben.
- Beim YAML-Import werden Kommentare nicht übernommen. `packages:`/`!include` werden nicht aufgelöst, sondern
  unverändert weitergereicht. Mehrere DS18B20 an einem gemeinsamen 1-Wire-Bus bleiben im Zusatz-YAML.
- Beken, Realtek und Lightning (LibreTiny): ESPHome bietet dort kein I²C. Der adressierbare LED-Streifen und der
  IR-Sender brauchen RMT (nur ESP32, nicht C2/C61). Der ESP32-H2 und -P4 haben kein eigenes WLAN, normale
  Pico-Boards ohne „W“ auch nicht; dafür erzeugt das Studio eine Fehlermeldung.
- Beim CB2S unterscheiden sich Chips (BK7231N oder T). Das ESPHome-Board `cb2s` ist ein BK7231N; bei einem BK7231T
  das Board `wb2s` oder `generic-bk7231t-qfn32-tuya` nehmen. Das erste Flashen geht dort per UART mit einem
  USB-Seriell-Adapter.
- WLAN-Name und -Passwort liegen im Speicher von Home Assistant (`.storage/esphome_studio`), unverschlüsselt
  wie bei anderen Integrationen. Die Schlüssel der Projekte ebenfalls.
- Die Pin-Hinweise gelten für die Standard-Boards. Eigene oder abweichende Boards (z. B. mit
  PSRAM-Modul) können andere Einschränkungen haben.
- Für den IR-Sender erzeugt das Panel nur die Hardware-Komponente; Codes sendest du über eigene
  ESPHome-Aktionen oder Home-Assistant-Dienste.
- Ziel ist ESPHome **2026.9**. Ältere Versionen kennen z. B. die OTA-Verschlüsselung und
  `channel_colors` beim LED-Streifen nicht.

## Tests

```
pip install esphome pytest pytest-homeassistant-custom-component
pytest                                  # Generator + Integration (echtes Home Assistant)
python tools/verify_catalog.py esphome [--failed] # prüft den Katalog (dauert ca. 30 Minuten) und trägt die Ergebnisse ein
python tests/validate_with_esphome.py   # erzeugt 22 Beispielgeräte (u. a. Beken, Realtek, Pico W) und prüft sie mit `esphome config`
python tests/matrix.py esphome d1_mini,cb2s,rpipicow   # jede Komponente auf den gewählten Boards mit `esphome config` prüfen
node tests/ui_smoke.mjs                 # Oberfläche in jsdom (mit TPL_DIR=/pfad werden alle Vorlagen auf 6 Boards als YAML abgelegt) (benötigt `npm i jsdom` unter /tmp/jsdom-test)
```

Geprüft mit ESPHome 2026.9.1 und Home Assistant 2026.2.3. Nicht geprüft: die Darstellung im echten
Browser, das Flashen auf echter Hardware und neuere Home-Assistant-Versionen als 2026.2.3.

Lizenz: MIT


## Neu in 0.6.0

- **Profi-Einstellungen je Entität**: Icon, Einheit, Geräteklasse, Zustandsklasse, Nachkommastellen, Entitätskategorie, intern / standardmäßig deaktiviert und **Filter** (Sensoren: 19 Filter, dazu Binär- und Textsensoren). Alles wird vom Generator geprüft und gegen echtes `esphome config` getestet.
- **Katalog erweitert**: ca. 884 Komponenten, davon ca. 844 unterstützt und 699 mit `esphome config` verifiziert. Nicht verifizierte sind mit „?“ markiert.
- **Hubs und Referenzen** (z. B. UART-/I²C-Geräte, Sensoren die einen Hub brauchen) werden automatisch mit angelegt.
- **Port-Expander** (MCP23xxx, PCF8574, PCA9554, SN74HC165/595 u. a.) als Pin-Quelle. Pull-ups gibt es nur bei MCP23xxx, PCA6416A und PI4IOE5V6408; sonst warnt der Generator.
- IDs, die ESPHome-Integrationen heißen (z. B. `display`), werden automatisch zu `display_id`.

## Neu in 0.7.0

- **„In ESPHome speichern“:** Der Knopf unter dem YAML schreibt die Datei direkt in deinen ESPHome-Ordner oder über den ESPHome Device Builder (Adresse z. B. `http://homeassistant.local:6052`, im Add-on den Port freigeben). Dazu unter „Ziel für In ESPHome speichern“ den Ordner oder die Adresse eintragen.
  - Alte Dateien werden als `.bak` gesichert.
  - In die `secrets.yaml` werden nur **fehlende** Einträge ergänzt. Vorhandene Werte werden nie überschrieben.
  - Wichtig: Das ESPHome-Add-on von Home Assistant OS liegt in einem Ordner, den Home Assistant selbst nicht beschreiben kann. Dort die Device-Builder-Adresse benutzen. Der Ordner passt für ESPHome in Docker oder auf einem anderen Rechner mit gemeinsamem Ordner.
  - Der Device Builder darf keine Anmeldung verlangen.
- **Import erkennt Katalog-Bausteine:** Beim Import werden einfache Katalog-Komponenten (z. B. Sensoren an I²C, Template-Schalter) wieder als bearbeitbare Bausteine übernommen. Alles mit Lambdas, Filtern, UART/SPI, Verweisen oder anderen Besonderheiten bleibt unverändert als Zusatz-YAML erhalten (nichts geht verloren).
- **Mehr geprüfte Komponenten:** Über 40 Bluetooth-Sensoren (Xiaomi, ThermoPro, Ruuvi …) legen jetzt den benötigten BLE-Tracker automatisch mit an.
- **Backup:** Projekte liegen im internen Speicher von Home Assistant (`.storage/esphome_studio`) und sind damit in deinen Home-Assistant-Backups enthalten.
- **Icon:** Eigene Integrations-Icons zeigt Home Assistant ab 2026.3. Ältere Versionen laufen weiter, nur ohne Icon.
