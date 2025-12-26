import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import blender_mcp.tools as tools


def test_create_empty_and_curve(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res1 = registry.call_tool(
        "blender-create-empty",
        {"type": "plain_axes", "name": "EmptyA", "size": 2.0, "location": [1, 2, 3]},
        log_action=False,
    )
    res2 = registry.call_tool(
        "blender-create-curve",
        {"type": "bezier", "name": "BezierA", "radius": 1.5, "resolution": 8},
        log_action=False,
    )
    assert res1["isError"] is False
    assert res2["isError"] is False
    codes = [p["code"] for p in payloads]
    assert any("empty_display_type" in code for code in codes)
    assert any("curves.new" in code for code in codes)


def test_create_empty_invalid_type(monkeypatch):
    monkeypatch.setattr(tools, "_bridge_request", lambda *_, **__: {"ok": True})
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-create-empty", {"type": "invalid"}, log_action=False)
    assert res["isError"] is True


def test_convert_cursor_snap(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append((path, payload))
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    ok = registry.call_tool("blender-convert-object", {"name": "Curve", "target": "mesh"}, log_action=False)
    snap = registry.call_tool("blender-snap", {"name": "Cube", "target": "grid"}, log_action=False)
    cursor = registry.call_tool("blender-set-3d-cursor", {"location": [0, 0, 0]}, log_action=False)
    assert ok["isError"] is False
    assert snap["isError"] is False
    assert cursor["isError"] is False
    code_strings = [payload["code"] for _, payload in calls]
    assert any("convert(" in code for code in code_strings)
    assert any("cursor" in code for code in code_strings)


def test_snap_invalid_target(monkeypatch):
    monkeypatch.setattr(tools, "_bridge_request", lambda *_, **__: {"ok": True})
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-snap", {"name": "Cube", "target": "bad"}, log_action=False)
    assert res["isError"] is True


def test_list_modifiers(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {
            "ok": True,
            "result": [
                {"name": "Array", "type": "ARRAY", "count": 2},
                {"name": "Mirror", "type": "MIRROR"},
            ],
        }

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-list-modifiers", {"name": "Cube"}, log_action=False)
    assert res["isError"] is False
    assert "Array" in res["content"][0]["text"]


def test_add_modifier_extended(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-add-modifier",
        {"name": "Cube", "type": "screw", "settings": {"angle_degrees": 90, "steps": 5, "axis": "z"}},
        log_action=False,
    )
    assert res["isError"] is False
    code = payloads[-1]["code"]
    assert "SCREW" in code


def test_add_modifier_invalid_object_offset(monkeypatch):
    monkeypatch.setattr(tools, "_bridge_request", lambda *_, **__: {"ok": True})
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-add-modifier",
        {"name": "Cube", "type": "array", "settings": {"object_offset": "bad"}},
        log_action=False,
    )
    assert res["isError"] is True


def test_mark_sharp_requires_angle(monkeypatch):
    monkeypatch.setattr(tools, "_bridge_request", lambda *_, **__: {"ok": True})
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-mark-sharp-edges",
        {"name": "Cube", "mode": "mark", "selection": "by_angle", "angle_degrees": "nope"},
        log_action=False,
    )
    assert res["isError"] is True


def test_tool_request_lint_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOL_REQUEST_DATA_DIR", str(tmp_path))
    importlib.reload(tools)
    registry = tools.ToolRegistry()
    registry.call_tool("tool-request", {"session": "s1", "need": "Need A", "why": "x", "domain": "mesh"}, log_action=False)
    registry.call_tool(
        "tool-request",
        {"session": "s2", "need": "need a", "why": "x", "domain": "mesh", "type": "enhancement"},
        log_action=False,
    )
    res = registry.call_tool("tool-request-lint", {"tests_passed": False}, log_action=False)
    payload = json.loads(res["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["duplicates"]
