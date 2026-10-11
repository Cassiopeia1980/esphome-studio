# ESPHome Studio

🇩🇪 [Deutsch](README.md) · 🇬🇧 English

A configurator for ESPHome right inside Home Assistant, similar to the GPIO configuration in Tasmota:
pick a board, give every pin a function, enter Wi-Fi and secrets, and you get the ESPHome YAML.
The panel appears in the Home Assistant sidebar (administrators only). The panel language can be switched between
**German and English** at the top right; by default it follows the Home Assistant language.

## Features

- **Beginner friendly:** The panel starts in **Simple mode** (toggle at the top right). For an empty project a
  three-step wizard guides you: choose a board, pick one of 11 templates (socket, relay with button, light, dimmer,
  RGB, LED strip, DHT22, BME280, DS18B20, door contact, IR transmitter) and enter your Wi-Fi. The Studio picks the pins
  itself (no boot, UART, USB or flash pins). Templates that do not work on the board are greyed out. Pro mode shows
  everything.
- **All ESPHome boards (500+):** ESP8266, ESP32 (S2, S3, C2, C3, C5, C6, C61, H2, P4), Raspberry Pi Pico / RP2040 /
  RP2350 and LibreTiny (Beken BK72xx such as CB2S/WB2S, Realtek, Lightning). Board and pin data is read directly
  from ESPHome by `tools/gen_boards.py`.
- **YAML import:** Paste an existing ESPHome YAML (optionally with secrets.yaml). The Studio takes over what it can
  generate and keeps everything else (scripts, lambdas, displays, `globals`, `interval` …) unchanged in “Extra YAML”.
- **Tasmota-style GPIO table:** one dropdown per pin with the functions possible on that pin. Boot, UART, USB, PSRAM
  and flash pins are marked; unsuitable pins are disabled.
- **Components:** relay/switch, status LED, lights (on/off, dimmable, RGB/RGBW/RGBWW, addressable strips), buttons and
  contacts, IR transmitter/receiver, DHT, DS18B20, ADC, HC-SR04, BME280, BMP280, SHT3x, AHT10/20, BH1750.
- **Catalog with all ESPHome components (844):** search and filter; pins, required fields, choices, measurements,
  I²C/SPI/UART and references are generated from the ESPHome schema. 699 components were verified against the real
  `esphome config`; the rest are available via “Also show unverified components” and marked with “?”.
- **Web server, Wi-Fi & secrets:** web server (v1–v3, auth, OTA upload), Wi-Fi/secrets stored once, per-device keys
  in a separate `secrets.yaml` tab, fallback hotspot, static IP, API encryption, OTA protection, diagnostic entities
  (status, Wi-Fi signal, uptime, IP, SSID, BSSID, MAC, restart button, debug sensors).
- **Save to ESPHome:** write the YAML directly into your ESPHome folder or into the ESPHome Device Builder (with
  login). Existing files are backed up as `.bak`; secrets are only added, never overwritten.
- **Checks:** duplicate pins, duplicate names, invalid device names, missing pull-ups, ADC pins and more are reported
  live; copying and downloading are blocked while there are errors.

## Installation

**HACS:** add `https://github.com/Cassiopeia1980/esphome-studio` as a custom repository (category *Integration*),
download it, restart Home Assistant, then add the integration under *Settings → Devices & services*.

**Manually:** copy `custom_components/esphome_studio` into your `config/custom_components` folder and restart.

## Usage

1. Open **ESPHome Studio** in the sidebar and choose your language at the top right.
2. Pick a board and a template (or add components / assign pins yourself).
3. Enter your Wi-Fi name and password once.
4. Use **Copy** or **Save to ESPHome**, paste the lines from the `secrets.yaml` tab into your secrets.yaml, and install.

Note: OTA encryption (`ota: encryption`) needs ESPHome 2026.9 or newer. With an older version choose “Password”.

## Translations

German is the source language. `i18n_en.json` (backend) and `i18n_ui_en.json` (panel) are plain dictionaries
(German text → English; `{0}` marks placeholders). `python tools/extract_i18n.py --missing` lists untranslated texts.
To add a language, extend `LANGS` in `i18n.py` and provide a dictionary.

## Tests

`pytest -q` (backend), `node tests/ui_smoke.mjs` and `node tests/ui_smoke_en.mjs` (panel in jsdom, German and English),
`python tests/validate_with_esphome.py <esphome> [--lang=en]` (validates generated YAML with `esphome config`).
