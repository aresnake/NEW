import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import blender_mcp.tools as tools


def test_add_sphere_uses_radius_from_diameter(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-add-sphere", {"diameter": 2.0}, log_action=False)
    assert result["isError"] is False
    code = payloads[0]["code"]
    assert "primitive_uv_sphere_add" in code
    assert "radius=1.0" in code


def test_add_cylinder_location_coercion(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    registry.call_tool("blender-add-cylinder", {"location": [1, 2, 3]}, log_action=False)
    registry.call_tool("blender-add-cylinder", {"location": "4,5,6"}, log_action=False)
    codes = [p["code"] for p in payloads]
    assert any("(1.0, 2.0, 3.0)" in code for code in codes)
    assert any("(4.0, 5.0, 6.0)" in code for code in codes)


def test_get_object_info_imports_math(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True, "result": {"name": "Cube"}}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    registry.call_tool("blender-get-object-info", {"name": "Cube"}, log_action=False)
    code = payloads[0]["code"]
    assert "math" in code.splitlines()[1]


def test_blender_exec_gated(monkeypatch):
    monkeypatch.delenv("BLENDER_MCP_UNSAFE", raising=False)
    monkeypatch.delenv("BLENDER_MCP_DEBUG_EXEC", raising=False)
    importlib.reload(tools)
    registry = tools.ToolRegistry()
    names = {tool["name"] for tool in registry.list_tools()}
    assert "blender-exec" not in names

    monkeypatch.setenv("BLENDER_MCP_UNSAFE", "1")
    monkeypatch.setenv("BLENDER_MCP_DEBUG_EXEC", "1")
    importlib.reload(tools)

    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry2 = tools.ToolRegistry()
    names2 = {tool["name"] for tool in registry2.list_tools()}
    assert "blender-exec" in names2
    res = registry2.call_tool("blender-exec", {"code": "print('hi')"}, log_action=False)
    assert res["isError"] is False
    assert payloads and "print('hi')" in payloads[0]["code"]

    monkeypatch.delenv("BLENDER_MCP_UNSAFE", raising=False)
    monkeypatch.delenv("BLENDER_MCP_DEBUG_EXEC", raising=False)
    importlib.reload(tools)
