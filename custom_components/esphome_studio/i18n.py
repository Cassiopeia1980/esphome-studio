"""Zweisprachigkeit (Deutsch = Quelltext, Englisch = Übersetzung).

Alle Texte im Programm sind deutsch geschrieben. Für Englisch gibt es ``i18n_en.json``
(Schlüssel = deutscher Text, f-Strings als Vorlage mit {0}, {1} …). Meldungen mit
eingesetzten Namen werden über Muster erkannt und übersetzt.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

LANGS = ("de", "en")
DEFAULT_LANG = "de"
LANG: ContextVar[str] = ContextVar("esphome_studio_lang", default=DEFAULT_LANG)

_EN: dict[str, str] = json.loads((Path(__file__).parent / "i18n_en.json").read_text(encoding="utf-8"))
_UI_EN: dict[str, str] = json.loads((Path(__file__).parent / "i18n_ui_en.json").read_text(encoding="utf-8"))
_PH = re.compile(r"\{(\d+)\}")


def _compile() -> tuple[list[tuple[re.Pattern[str], str]], list[tuple[re.Pattern[str], str]]]:
    full: list[tuple[int, re.Pattern[str], str]] = []
    prefix: list[tuple[int, re.Pattern[str], str]] = []
    for de, en in _EN.items():
        if not _PH.search(de) and not de.endswith((" ", ": ")):
            continue
        # {{ und }} sind maskierte Klammern (aus f-Strings)
        raw = de.replace("{{", "\x00").replace("}}", "\x01")
        parts = _PH.split(raw)
        rx = ""
        for i, part in enumerate(parts):
            part = part.replace("\x00", "{").replace("\x01", "}")
            rx += re.escape(part) if i % 2 == 0 else "(.*?)"
        weight = sum(len(p) for p in parts[::2])
        pat_full = re.compile("^" + rx + "$", re.S)
        full.append((weight, pat_full, en))
        prefix.append((weight, re.compile("^" + rx + "(.*)$", re.S), en))
    full.sort(key=lambda t: -t[0])
    prefix.sort(key=lambda t: -t[0])
    return [(p, e) for _, p, e in full], [(p, e) for _, p, e in prefix]


_FULL, _PREFIX = _compile()


def _quotes(s: str) -> str:
    return s.replace("„", '"').replace("“", '"')


def _fmt(en: str, groups: tuple[str, ...]) -> str:
    try:
        return _PH.sub(lambda m: tr(groups[int(m.group(1))], "en") if int(m.group(1)) < len(groups) else m.group(0),
                       en.replace("{{", "{").replace("}}", "}"))
    except Exception:  # noqa: BLE001
        return en


def tr(text: str, lang: str | None = None) -> str:
    """Übersetzt einen deutschen Text. Unbekanntes bleibt unverändert."""
    lang = lang or LANG.get()
    if lang != "en" or not isinstance(text, str) or not text:
        return text
    hit = _EN.get(text)
    if hit is not None:
        return hit
    for pat, en in _FULL:
        m = pat.match(text)
        if m:
            return _fmt(en, m.groups())
    # zusammengesetzte Meldungen „A – B“
    if " – " in text:
        return " – ".join(tr(p, "en") for p in text.split(" – "))
    for pat, en in _PREFIX:
        m = pat.match(text)
        if m and m.groups()[-1] != text:
            g = m.groups()
            return _fmt(en, g[:-1]) + tr(g[-1], "en")
    return _quotes(text) if "„" in text else text


def T(de: str, *args: Any) -> str:
    """Text in der aktuellen Sprache; {0}, {1} … werden mit ``args`` gefüllt."""
    out = tr(de) if LANG.get() == "en" else de
    return _PH.sub(lambda m: str(args[int(m.group(1))]), out) if args else out


@contextmanager
def use_lang(lang: str):
    tok = LANG.set(lang if lang in LANGS else DEFAULT_LANG)
    try:
        yield
    finally:
        LANG.reset(tok)


def tr_struct(obj: Any, lang: str) -> Any:
    """Übersetzt alle Texte einer Datenstruktur, die genau im Wörterbuch stehen (Beschriftungen u. ä.)."""
    if lang != "en":
        return obj
    if isinstance(obj, str):
        return _EN.get(obj, obj)
    if isinstance(obj, list):
        return [tr_struct(x, lang) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in _KEEP else tr_struct(v, lang)) for k, v in obj.items()}
    return obj


# Felder, die nie übersetzt werden dürfen (Schlüssel, Kennungen, Werte, die ins YAML gehen)
_KEEP = {"key", "type", "id", "kind", "platform", "choices", "default", "domain", "cat", "cls", "provides", "value"}


def ui_dictionary(lang: str) -> dict[str, str]:
    """Wörterbuch für die Oberfläche (Panel). Deutsch braucht keines."""
    if lang != "en":
        return {}
    return {**_EN, **_UI_EN}
