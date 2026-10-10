"""YAML einlesen, ohne ESPHome-Spezialfälle zu verlieren (``!secret``, ``!lambda``, ``!include`` …).

Getaggte Werte werden als :class:`Tag` gelesen und vom Generator genauso wieder ausgegeben.
"""

from __future__ import annotations

from typing import Any

import yaml


class Tag:
    """Wert mit YAML-Tag, z. B. ``!secret wifi_ssid`` oder ``!lambda |- return 1;``."""

    def __init__(self, tag: str, value: Any) -> None:
        self.tag = tag
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"Tag({self.tag!r}, {self.value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tag) and (self.tag, self.value) == (other.tag, other.value)

    def __hash__(self) -> int:
        return hash((self.tag, repr(self.value)))


class _Loader(yaml.SafeLoader):
    pass


def _construct_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> Tag:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return Tag("!" + suffix, value)


_Loader.add_multi_constructor("!", _construct_tag)


def load_text(text: str) -> Any:
    """Liest YAML-Text. Wirft ``ValueError`` mit lesbarer Meldung bei Syntaxfehlern."""
    try:
        return yaml.load(text, Loader=_Loader)  # noqa: S506 - eigener SafeLoader
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (Zeile {mark.line + 1}, Spalte {mark.column + 1})" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise ValueError(f"{problem}{where}") from exc
