import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_uv_unwrap_happy_path(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append((path, payload))
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-uv-unwrap", {"name": "Cube"}, log_action=False)
    assert result["isError"] is False
    assert "Cube" in result["content"][0]["text"]
    assert calls and calls[0][0] == "/exec"


def test_uv_unwrap_missing_object(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": False, "error": "Object not found"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-uv-unwrap", {"name": "Missing"}, log_action=False)
    assert result["isError"] is True
    assert "Object not found" in result["content"][0]["text"]


def test_uv_unwrap_non_mesh(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": False, "error": "Object is not a mesh"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-uv-unwrap", {"name": "Light"}, log_action=False)
    assert result["isError"] is True
    assert "not a mesh" in result["content"][0]["text"]
