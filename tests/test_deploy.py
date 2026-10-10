"""Tests für „In ESPHome speichern“ (Ordner, secrets-Zusammenführung, Dashboard)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.esphome_studio import deploy as dp  # noqa: E402
from custom_components.esphome_studio.generator import default_project, new_component  # noqa: E402

from test_integration import _enable_custom_integrations, call, setup  # noqa: E402,F401  (Fixtures)

BLOCK = '# Kommentar\nwifi_ssid: "Heim"\nwifi_password: "pw"\nkueche_api_key: "abc="\n'


def test_merge_never_overwrites():
    text, added, conflicts = dp.merge_secrets('wifi_ssid: "Alt"\nandere: 1\n', BLOCK)
    assert added == ["wifi_password", "kueche_api_key"] and conflicts == ["wifi_ssid"]
    assert 'wifi_ssid: "Alt"' in text and "andere: 1" in text and 'kueche_api_key: "abc="' in text
    t2, a2, c2 = dp.merge_secrets(text, BLOCK)
    assert t2 == text and a2 == [] and c2 == ["wifi_ssid"]


def test_merge_empty_and_broken():
    text, added, _ = dp.merge_secrets("", BLOCK)
    assert added == ["wifi_ssid", "wifi_password", "kueche_api_key"] and text.endswith("\n")
    with pytest.raises(dp.DeployError):
        dp.merge_secrets("a: [unclosed", BLOCK)


def test_write_to_folder_backup_and_name_check(tmp_path):
    r = dp.write_to_folder(str(tmp_path), "kueche", "esphome:\n", BLOCK)
    assert (tmp_path / "kueche.yaml").read_text() == "esphome:\n" and not r["backup"]
    r = dp.write_to_folder(str(tmp_path), "kueche", "neu\n", "")
    assert r["backup"] and (tmp_path / "kueche.yaml.bak").read_text() == "esphome:\n"
    for bad in ("../x", "A b", "", "a/b"):
        with pytest.raises(dp.DeployError):
            dp.write_to_folder(str(tmp_path), bad, "x", "")
    with pytest.raises(dp.DeployError):
        dp.write_to_folder(str(tmp_path / "gibtsnicht"), "x", "x", "")


async def test_ws_deploy(setup, hass, tmp_path):  # noqa: F811
    _entry, ws = setup
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    r = await call(ws, "deploy_settings", target_dir=str(tmp_path))
    assert r["success"] and r["result"]["dir_exists"]
    p = default_project()
    p["name"] = "kueche"
    p["components"] = [new_component("switch", "Relais", {"pin": "GPIO5"})]
    r = await call(ws, "deploy", project=p)
    assert r["success"], r
    assert (tmp_path / "kueche.yaml").exists() and "kueche_api_key" in (tmp_path / "secrets.yaml").read_text()
    # unzulässiger Ordner wird abgelehnt
    await call(ws, "deploy_settings", target_dir="/etc")
    r = await call(ws, "deploy", project=p)
    assert not r["success"] and r["error"]["code"] == "deploy_failed"


async def test_dashboard_protocol_with_fake_device_builder(aiohttp_server, socket_enabled):
    """Prüft den Ablauf gegen einen nachgebauten ESPHome Device Builder (WebSocket /ws)."""
    import aiohttp  # noqa: PLC0415
    from aiohttp import web  # noqa: PLC0415

    seen: list[tuple[str, dict]] = []
    secrets = ["wifi_ssid"]

    async def ws_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_json({"server_version": "1.0", "requires_auth": False})
        async for m in ws:
            msg = m.json()
            seen.append((msg["command"], msg["args"]))
            res: object = {"created": True}
            if msg["command"] == "config/get_secrets":
                res = list(secrets)
            await ws.send_json({"message_id": msg["message_id"], "result": res})
        return ws

    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as s:
        r = await dp.write_to_dashboard(s, f"http://127.0.0.1:{server.port}", "kueche", "esphome:\n", BLOCK)
    assert r["secrets_added"] == ["wifi_password", "kueche_api_key"] and r["secrets_conflicts"] == ["wifi_ssid"]
    cmds = [c for c, _ in seen]
    assert cmds[:2] == ["config/get_secrets", "devices/create"] and cmds.count("config/set_secret") == 2
    assert dict(seen)["devices/create"]["overwrite"] is True
    async with aiohttp.ClientSession() as s:
        with pytest.raises(dp.DeployError):
            await dp.write_to_dashboard(s, "http://127.0.0.1:9", "kueche", "x", "")
        with pytest.raises(dp.DeployError):
            await dp.write_to_dashboard(s, "ftp://x", "kueche", "x", "")
