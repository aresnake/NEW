import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_mesh_cleanup_happy_path(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append((path, payload))
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    registry.call_tool("blender-add-cube", {}, log_action=False)
    for name in ("blender-merge-by-distance", "blender-recalc-normals", "blender-triangulate"):
        result = registry.call_tool(name, {"name": "Cube"}, log_action=False)
        assert result["isError"] is False
        assert isinstance(result.get("content"), list)
        assert result["content"] and "text" in result["content"][0]
    assert len(calls) == 4


def test_mesh_cleanup_missing_object(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": False, "error": "Object not found"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-merge-by-distance", {"name": "Missing"}, log_action=False)
    assert result["isError"] is True
    assert isinstance(result.get("content"), list)
    assert result["content"]


def test_mesh_cleanup_non_mesh(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": False, "error": "Object is not a mesh"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-triangulate", {"name": "Camera"}, log_action=False)
    assert result["isError"] is True
    assert isinstance(result.get("content"), list)
    assert result["content"]
