import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_extrude_allows_negative(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-mesh-extrude", {"name": "Cube", "distance": -0.2}, log_action=False)
    assert res["isError"] is False
    code = payloads[0]["code"]
    assert "-0.2" in code


def test_inset_switches_mode(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-mesh-inset", {"name": "Cube", "thickness": 0.1}, log_action=False)
    assert res["isError"] is False
    code = payloads[0]["code"]
    assert "mode_set(mode='EDIT')" in code
    assert "mesh.inset" in code


def test_torus_operator(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool("blender-add-torus", {}, log_action=False)
    assert res["isError"] is False
    assert "primitive_torus_add" in payloads[0]["code"]


def test_mesh_spin_center(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-mesh-spin", {"name": "Cube", "axis": "Z", "angle_degrees": 90, "center": [1, 2, 3]}, log_action=False
    )
    assert res["isError"] is False
    code = payloads[0]["code"]
    assert "cent=" in code and "1.0" in code and "3.0" in code
