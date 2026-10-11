"""Englisch: Vollständigkeit der Übersetzungen und keine deutschen Reste in der Ausgabe."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import extract_i18n as ex  # noqa: E402
import validate_with_esphome as v  # noqa: E402
from custom_components.esphome_studio import generator as gen, importer as imp  # noqa: E402
from custom_components.esphome_studio.boards import board_detail, boards_meta  # noqa: E402
from custom_components.esphome_studio.components import components_meta  # noqa: E402
from custom_components.esphome_studio.entity import entity_meta  # noqa: E402
from custom_components.esphome_studio.i18n import _EN, tr, tr_struct  # noqa: E402

GERMAN = re.compile(r"[äöüÄÖÜß]|\b(und|nicht|bitte|oder|für|muss|einen|eine|keine|werden|wurde|gibt|noch|dann|statt)\b")
# Schlüssel, die keine Texte sind (Muster, Einheiten, Namen) und deshalb keine Übersetzung brauchen
NO_TEXT = re.compile(r"^(\^.*\$|\[.*\]\+?|!lambda|0x.*|[A-Za-z0-9_/%³µ.\-]{1,10}|\{0\} · \{1\}|[A-Z][A-Za-z ]+ ?[A-Za-z0-9/()\- ]*)$")


def _left(text: str) -> bool:
    return bool(GERMAN.search(text))


def test_every_german_source_text_has_an_english_translation():
    missing = []
    for p in sorted(ex.ROOT.glob("*.py")):
        if p.name in ex.SKIP_FILES:
            continue
        for key, line in ex.keys(p):
            if key not in _EN and _left(key) and not key.startswith("^"):
                missing.append(f"{p.name}:{line} {key[:70]}")
    assert not missing, "\n".join(missing)


def test_board_data_texts_are_translated():
    data = json.loads((ex.ROOT / "boards_data.json").read_text(encoding="utf-8"))
    found: set[str] = set()

    def walk(o):
        if isinstance(o, str):
            if _left(o):
                found.add(o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)

    walk(data)
    assert not [t for t in found if t not in _EN], [t for t in found if t not in _EN]


def test_samples_in_english_have_no_german_leftovers():
    bad = []
    for key, proj in v.SAMPLES.items():
        r = gen.generate(proj, {"wifi_ssid": "x", "wifi_password": "y"}, "en")
        for where in ("errors", "warnings"):
            bad += [(key, where, m) for m in r[where] if _left(m)]
        bad += [(key, "yaml", ln) for ln in r["yaml"].splitlines() if ln.lstrip().startswith("#") and _left(ln)]
        bad += [(key, "secrets", ln) for ln in r["secrets"].splitlines() if _left(ln)]
    assert not bad, bad[:10]


def test_meta_in_english_has_no_german_leftovers():
    meta = tr_struct({"boards": boards_meta(), "types": components_meta(), "entity": entity_meta()}, "en")
    texts: list[str] = []

    def walk(o, path=""):
        if isinstance(o, str):
            texts.append(f"{path}: {o}")
        elif isinstance(o, list):
            for x in o:
                walk(x, path)
        elif isinstance(o, dict):
            for k, x in o.items():
                if k not in ("key", "type", "id", "choices", "default", "value"):
                    walk(x, f"{path}/{k}")

    walk(meta)
    bad = [t for t in texts if _left(t.split(": ", 1)[1])]
    assert not bad, bad[:15]
    pins = [p.get("note", "") for p in board_detail("d1_mini")["pins"]]
    assert not [n for n in tr_struct(pins, "en") if _left(n)]


def test_importer_messages_in_english():
    res = imp.import_yaml("esphome:\n  name: t\nesp8266:\n  board: d1_mini\nsensor:\n  - platform: wifi_signal\n"
                          "    name: X\n    filters:\n      - multiply: 2\n", "", "en")
    assert res["ok"] and not [m for m in res["unmapped"] + res["notes"] if _left(m)], res
    res = imp.import_yaml("kaputt: [", "", "en")
    assert not res["ok"] and not [e for e in res["errors"] if _left(e)], res["errors"]


def test_english_names_roundtrip_through_importer():
    p = gen.default_project()
    p["name"] = "t"
    p["diag"] = {"wifi_signal": True, "uptime": True, "restart": True, "uptime_text": True, "ip": True, "status": True}
    for lang in ("de", "en"):
        r = gen.generate(p, {"wifi_ssid": "x", "wifi_password": "y"}, lang)
        res = imp.import_yaml(r["yaml"], r["secrets"], lang)
        assert res["ok"] and res["project"]["diag"]["wifi_signal"] and res["project"]["diag"]["uptime_text"], (lang, res)
        assert not res["unmapped"], (lang, res["unmapped"])
    assert "WiFi signal" in gen.generate(p, {}, "en")["yaml"] and "WLAN-Signal" in gen.generate(p, {}, "de")["yaml"]
