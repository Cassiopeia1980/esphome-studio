"""Simuliert die Websocket-Befehle für den JS-Test: liest eine JSON-Nachricht von stdin,
antwortet auf stdout. Der Zustand liegt in der Datei, die als Argument übergeben wird."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from helpers import load_core  # noqa: E402

boards, components, gen = load_core()
state_file = Path(sys.argv[1])
state = json.loads(state_file.read_text()) if state_file.exists() else {"projects": {}, "secrets": {}}
msg = json.loads(sys.stdin.read())
t = msg["type"].split("/")[1]
lang = msg.get("lang") or "de"
import importlib  # noqa: E402
i18n = importlib.import_module("esphome_studio.i18n")

if t == "meta":
    res = i18n.tr_struct({"version": "test", "boards": boards.boards_meta(), "types": components.components_meta(),
           "group_order": components.GROUP_ORDER,
           "entity": importlib.import_module("esphome_studio.entity").entity_meta()}, lang)
elif t == "catalog":
    res = importlib.import_module("esphome_studio.catalog").catalog()
    res = res if lang != "en" else i18n.tr_struct(res, lang)
elif t == "board":
    res = {"board": i18n.tr_struct(boards.board_detail(msg["key"]), lang)}
elif t == "import":
    res = importlib.import_module("esphome_studio.importer").import_yaml(msg["yaml"], msg.get("secrets", ""), lang)
elif t == "list":
    res = {"projects": [{"id": k, "name": v["name"], "friendly_name": v.get("friendly_name", ""), "board": v["board"]}
                        for k, v in state["projects"].items()], "secrets": state["secrets"]}
elif t == "get":
    res = {"project": {**state["projects"][msg["project_id"]], "id": msg["project_id"]}}
elif t == "save":
    p = dict(msg["project"]); pid = p.pop("id", None) or gen.new_uid()
    state["projects"][pid] = p
    res = {"project": {**p, "id": pid}}
elif t == "delete":
    state["projects"].pop(msg["project_id"], None); res = {}
elif t == "new":
    with i18n.use_lang(lang):
        res = {"project": gen.default_project(msg.get("board") or "d1_mini")}
elif t == "generate":
    res = gen.generate(msg["project"], state["secrets"], lang=lang)
elif t == "set_secrets":
    state["secrets"].update(msg["secrets"]); res = {"secrets": state["secrets"]}
elif t == "random":
    res = {"value": {"api": gen.new_api_key, "ota": gen.new_password, "ap": gen.new_ap_password}[msg["kind"]]()}
elif t == "source_list":
    res = {"source": "folder", "where": "/config/esphome", "items": [
        {"configuration": "kueche.yaml", "name": "kueche", "friendly_name": "", "platform": ""}]}
elif t == "source_get":
    res = {"source": "folder", "yaml": "esphome:\n  name: kueche\nesp32:\n  board: esp32dev\nwifi:\n  ssid: !secret wifi_ssid\n",
           "secrets": "wifi_ssid: \"Heim\"\n"}
elif t == "i18n":
    res = {"dict": i18n.ui_dictionary(lang)}
else:
    raise SystemExit(f"unbekannt: {t}")
state_file.write_text(json.dumps(state))
print(json.dumps(res))
