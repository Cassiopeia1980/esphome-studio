"""Sammelt alle deutschen Texte (Quelltexte = Schlüssel) aus den Python-Dateien.

Aufruf:  python3 tools/extract_i18n.py [--missing]
Schreibt nichts, gibt die Schlüssel aus; --missing zeigt nur die, die in i18n_en.json fehlen.
f-Strings werden zu Vorlagen mit {0}, {1} … (Reihenfolge der Platzhalter).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "esphome_studio"
DE = re.compile(r"[äöüÄÖÜß]|\b(der|die|das|und|nicht|bitte|Pin|Gerät|oder|für|ist|wird|mit|muss|einen|eine|kein|keine|"
                r"Zugangsdaten|Schlüssel|werden|wurde|bei|von|dem|den|im|zum|zur|auf|nur|sind|noch|dann|statt|wie|sonst)\b")
# Dateien, in denen (fast) jeder Text eine Beschriftung ist
DATA_FILES = {"components.py", "entity.py", "boards.py", "catalog.py", "const.py"}
SKIP_FILES = {"i18n.py"}


def template(node: ast.JoinedStr) -> str:
    out, i = [], 0
    for v in node.values:
        if isinstance(v, ast.Constant):
            out.append(str(v.value).replace("{", "{{").replace("}", "}}"))
        else:
            out.append("{%d}" % i)
            i += 1
    return "".join(out)


def keys(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            docstrings.add(id(n.body[0].value))
    found: list[tuple[str, int]] = []
    inside_f = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            for v in n.values:
                inside_f.add(id(v))
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            t = template(n)
            if DE.search(t) or path.name in DATA_FILES:
                found.append((t, n.lineno))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings \
                and id(n) not in inside_f:
            s = n.value
            if len(s) < 2 or not re.search(r"[A-Za-zäöüÄÖÜ]", s):
                continue
            if path.name in DATA_FILES:
                if re.fullmatch(r"[a-z0-9_.:/\-]+", s) or s.isupper() or "\n" in s and len(s) > 400:
                    continue
                found.append((s, n.lineno))
            elif DE.search(s):
                found.append((s, n.lineno))
    return found


def main() -> None:
    allk: dict[str, list[str]] = {}
    for p in sorted(ROOT.glob("*.py")):
        if p.name in SKIP_FILES:
            continue
        for k, line in keys(p):
            allk.setdefault(k, []).append(f"{p.name}:{line}")
    en_file = ROOT / "i18n_en.json"
    have = json.loads(en_file.read_text(encoding="utf-8")) if en_file.exists() else {}
    if "--missing" in sys.argv:
        allk = {k: v for k, v in allk.items() if k not in have}
    json.dump({k: v[0] for k, v in allk.items()}, sys.stdout, ensure_ascii=False, indent=0)
    print(f"\n# {len(allk)} Schlüssel", file=sys.stderr)


if __name__ == "__main__":
    main()
