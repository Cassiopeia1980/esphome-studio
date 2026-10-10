"""Webserver: Versionen, Optionen, Zugangsschutz, Import."""
from custom_components.esphome_studio.generator import default_project, generate
from custom_components.esphome_studio.importer import import_yaml


def _gen(web):
    p = default_project()
    p["web_server"] = True
    if web is not None:
        p["web"] = web
    return generate(p)


def test_default_alt():
    r = _gen(None)
    assert "web_server:\n  port: 80\n  ota: false" in r["yaml"]


def test_version3_und_optionen():
    r = _gen({"version": "3", "port": 8080, "local": True, "compression": "br", "log": False})
    y = r["yaml"]
    assert "version: 3" in y and "port: 8080" in y and "local: true" in y and "compression: br" in y and "log: false" in y
    assert not r["errors"]


def test_version1_warnt():
    r = _gen({"version": "1"})
    assert any("veraltet" in w for w in r["warnings"])


def test_auth_und_ota():
    r = _gen({"auth": True, "auth_user": "admin", "auth_password": "geheim", "ota_web": True, "auth_type": "digest"})
    y = r["yaml"]
    assert "!secret" in y and "platform: web_server" in y and "type: digest" in y
    assert "geheim" in r["secrets"]
    assert not r["errors"]
    r2 = _gen({"auth": True, "auth_user": "", "auth_password": ""})
    assert r2["errors"]


def test_import_roundtrip():
    r = _gen({"version": "3", "port": 8080, "local": True})
    imp = import_yaml(r["yaml"], r["secrets"])
    assert imp["project"]["web"]["version"] == "3" and imp["project"]["web"]["port"] == 8080
    assert generate(imp["project"])["yaml"] == r["yaml"]
