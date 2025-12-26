import json
import importlib

from blender_mcp import tools


def test_scene_snapshot_listed():
    reg = tools.ToolRegistry()
    names = {t["name"] for t in reg.list_tools()}
    assert "blender-scene-snapshot" in names


def test_scene_snapshot_calls_bridge(monkeypatch):
    called = {}

    def fake_bridge(path, payload=None, timeout=None):
        called["path"] = path
        called["payload"] = payload
        called["timeout"] = timeout
        return {"ok": True, "result": {"collections": [], "active_object": None, "selected_objects": [], "objects": [], "counts": {}}}

    importlib.reload(tools)
    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    reg = tools.ToolRegistry()
    res = reg.call_tool("blender-scene-snapshot", {}, log_action=False)
    assert called["path"] == "/exec"
    code = called["payload"]["code"]
    assert "bpy.data.objects" in code
    assert "bpy.data.collections" in code
    assert res["ok"] is True
    payload = json.loads(res["content"][0]["text"])
    assert payload["objects"] == []


def test_scene_snapshot_bridge_error(monkeypatch):
    def fake_bridge(*_, **__):
        return {"ok": False, "error": "boom"}

    importlib.reload(tools)
    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    reg = tools.ToolRegistry()
    res = reg.call_tool("blender-scene-snapshot", {}, log_action=False)
    assert res["ok"] is False
    assert res["isError"] is True
    assert "boom" in res["content"][0]["text"]
