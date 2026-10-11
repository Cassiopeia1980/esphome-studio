"""YAML und Secrets direkt in den ESPHome-Ordner bzw. das ESPHome-Dashboard schreiben."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .yamlutil import load_text

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
DEFAULT_DIR = "/config/esphome"


class DeployError(Exception):
    """Fehler mit lesbarer deutscher Meldung."""


def parse_secret_block(block: str) -> dict[str, str]:
    """Liest den vom Generator erzeugten Secrets-Block (Schlüssel: Wert)."""
    try:
        data = load_text(block or "")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def merge_secrets(existing: str, block: str) -> tuple[str, list[str], list[str]]:
    """Ergänzt fehlende Schlüssel. Vorhandene Schlüssel werden nie überschrieben.

    Rückgabe: (neuer Text, hinzugefügte Schlüssel, Schlüssel mit abweichendem Wert).
    """
    new = parse_secret_block(block)
    try:
        cur = load_text(existing) if existing.strip() else {}
    except ValueError as exc:
        raise DeployError(f"Die vorhandene secrets.yaml lässt sich nicht lesen: {exc}") from exc
    if not isinstance(cur, dict):
        raise DeployError("Die vorhandene secrets.yaml hat ein unerwartetes Format.")
    added: list[str] = []
    conflicts: list[str] = []
    lines: list[str] = []
    for k, v in new.items():
        if k in cur:
            if str(cur[k]) != v:
                conflicts.append(k)
            continue
        added.append(k)
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    if not lines:
        return existing, added, conflicts
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += "# von ESPHome Studio ergänzt\n" + "\n".join(lines) + "\n"
    return text, added, conflicts


def need_auth_flag(exc: Exception) -> bool:
    t = str(exc).lower()
    return "authenticat" in t or "unauthor" in t or "auth" in t and "required" in t


def version_tuple(v: str) -> tuple[int, int]:
    m = re.match(r"^(\d+)\.(\d+)", v or "")
    return (int(m.group(1)), int(m.group(2))) if m else (9999, 0)


def check_name(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise DeployError("Der Gerätename ist ungültig (nur Kleinbuchstaben, Ziffern, - und _).")
    return name


def write_to_folder(folder: str, name: str, yaml_text: str, secrets_block: str) -> dict[str, Any]:
    """Blockierend (im Executor aufrufen)."""
    check_name(name)
    d = Path(folder)
    if not d.is_dir():
        raise DeployError(f"Der Ordner „{folder}“ existiert nicht. Unter „Ziel“ einen vorhandenen Ordner eintragen.")
    target = d / f"{name}.yaml"
    backup = False
    if target.exists():
        target.replace(d / f"{name}.yaml.bak")
        backup = True
    target.write_text(yaml_text, encoding="utf-8")
    result: dict[str, Any] = {"where": str(target), "backup": backup, "secrets_added": [], "secrets_conflicts": []}
    if secrets_block.strip():
        sp = d / "secrets.yaml"
        existing = sp.read_text(encoding="utf-8") if sp.exists() else ""
        text, added, conflicts = merge_secrets(existing, secrets_block)
        if added:
            if sp.exists():
                sp.replace(d / "secrets.yaml.bak")
            sp.write_text(text, encoding="utf-8")
        result["secrets_added"], result["secrets_conflicts"] = added, conflicts
    return result


async def write_to_dashboard(session: Any, base_url: str, name: str, yaml_text: str, secrets_block: str,
                             username: str = "", password: str = "") -> dict[str, Any]:
    """Über die WebSocket-Schnittstelle des ESPHome Device Builders (ESPHome ab 2026.x, ohne Anmeldung).

    Vorhandene Secret-Schlüssel werden nie überschrieben (der Device Builder verrät keine Werte).
    """
    import asyncio  # noqa: PLC0415

    check_name(name)
    base = base_url.strip().rstrip("/")
    if not re.match(r"^https?://[^\s/]+(:\d+)?$", base):
        raise DeployError("Die Dashboard-Adresse ist ungültig (Beispiel: http://homeassistant.local:6052, ohne Pfad).")

    try:
        async with session.ws_connect(f"{base}/ws", timeout=15) as ws:
            counter = 0
            need_auth = [False]
            version = [""]

            async def cmd(command: str, **args: Any) -> Any:
                nonlocal counter
                counter += 1
                mid = str(counter)
                await ws.send_json({"command": command, "message_id": mid, "args": args})
                while True:
                    m = await asyncio.wait_for(ws.receive_json(), 20)
                    if m.get("message_id") != mid:
                        if m.get("requires_auth"):
                            need_auth[0] = True
                        if m.get("esphome_version"):
                            version[0] = str(m["esphome_version"])
                        continue
                    if "result" in m:
                        return m["result"]
                    raise DeployError(f"Das ESPHome-Dashboard meldet: {m.get('details') or m.get('message') or m.get('error') or m}")

            if username:
                try:
                    await cmd("auth/login", username=username, password=password)
                except DeployError as exc:
                    raise DeployError("Anmeldung am ESPHome-Dashboard fehlgeschlagen. Benutzername und Passwort prüfen "
                                      f"({exc}).") from exc
            existing = await cmd("config/get_secrets")
            result: dict[str, Any] = {"where": f"{base} → {name}.yaml", "backup": False,
                                      "secrets_added": [], "secrets_conflicts": []}
            await cmd("devices/create", name=name, file_content=yaml_text, overwrite=True)
            for k, v in parse_secret_block(secrets_block).items():
                if k in (existing or []):
                    result["secrets_conflicts"].append(k)  # vorhanden, Wert unbekannt -> nicht angefasst
                else:
                    await cmd("config/set_secret", key=k, value=v)
                    result["secrets_added"].append(k)
            result["esphome_version"] = version[0]
            return result
    except DeployError as exc:
        if need_auth_flag(exc) and not username:
            raise DeployError("Das ESPHome-Dashboard verlangt eine Anmeldung. Benutzername und Passwort unter "
                              "„Ziel“ eintragen.") from exc
        raise
    except Exception as exc:  # noqa: BLE001 - Netzwerkfehler lesbar machen
        raise DeployError(f"Das ESPHome-Dashboard ist nicht erreichbar oder antwortet anders als erwartet "
                          f"({type(exc).__name__}). Adresse prüfen.") from exc
