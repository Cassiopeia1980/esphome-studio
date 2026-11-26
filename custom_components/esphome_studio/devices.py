"""Startseite: Studio-Projekte mit den ESPHome-Geräten aus Home Assistant abgleichen (reine Funktionen)."""

from __future__ import annotations

import re
from typing import Any

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?(b\d+)?")


def norm(name: str) -> str:
    """Namen vergleichbar machen: klein, ohne Leer-, Binde-, Unterstriche und Sonderzeichen."""
    return re.sub(r"[\W_]", "", str(name or "").lower())


def parse_version(sw: str) -> tuple[int, int, int] | None:
    """'2026.11.0 (Nov 23 2026, 12:00:00)' -> (2026, 11, 0); ``None``, wenn keine Version erkennbar ist."""
    m = _VERSION_RE.search(sw or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def newest_version(ha_devices: dict[str, dict[str, Any]]) -> str:
    best: tuple[int, int, int] | None = None
    for dev in ha_devices.values():
        v = parse_version(dev.get("sw_version", ""))
        if v and (best is None or v > best):
            best = v
    return ".".join(str(x) for x in best) if best else ""


def _ip(p: dict[str, Any]) -> str:
    wifi = p.get("wifi") if isinstance(p.get("wifi"), dict) else {}
    st = wifi.get("static_ip") if isinstance(wifi.get("static_ip"), dict) else {}
    return str(st.get("ip") or "") if st.get("enabled") else ""


def device_rows(projects: dict[str, dict[str, Any]], ha_devices: dict[str, dict[str, Any]],
                migrate_open: dict[str, bool] | None = None) -> dict[str, Any]:
    """Je Projekt eine Zeile mit Firmware-Stand und Online-Status. ``ha_devices`` ist nach Gerätenamen (klein) geschlüsselt."""
    latest = newest_version(ha_devices)
    latest_t = parse_version(latest)
    rows = []
    for pid, p in projects.items():
        name = str(p.get("name", ""))
        dev = ha_devices.get(norm(name)) or ha_devices.get(norm(p.get("friendly_name", ""))) or {}
        sw = str(dev.get("sw_version", ""))
        v = parse_version(sw)
        ota = p.get("ota") or {}
        rows.append({
            "id": pid,
            "name": name,
            "file": str(p.get("file_name") or name),
            "friendly_name": p.get("friendly_name", ""),
            "board": p.get("board", ""),
            "updated": p.get("updated", ""),
            "components": len(p.get("components") or []),
            "ip": _ip(p),
            "in_ha": bool(dev),
            "online": dev.get("online"),
            "version": ".".join(str(x) for x in v) if v else "",
            "firmware": sw,
            "outdated": bool(v and latest_t and v < latest_t),
            "migrate_open": bool(ota.get("migrate")) if isinstance(ota, dict) else False,
        })
    rows.sort(key=lambda r: r["name"].lower())
    return {"devices": rows, "latest": latest}


def keep_api_key(new: dict, *olds: dict | None) -> bool:
    """Fehlt im neu eingelesenen Projekt der API-Schlüssel (Builder liefert keine secrets.yaml), den alten übernehmen.

    Nimmt den ersten brauchbaren Schlüssel (mindestens 40 Zeichen) aus ``olds``. Gibt True zurück, wenn einer
    übernommen wurde.
    """
    api = new.get("api")
    if not isinstance(api, dict) or not api.get("encryption", True):
        return False
    if len(str(api.get("key") or "")) >= 40:
        return False
    for old in olds:
        key = str(((old or {}).get("api") or {}).get("key") or "")
        if len(key) >= 40:
            api["key"] = key
            return True
    return False
