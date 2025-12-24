import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_mesh_ops_listed():
    registry = tools.ToolRegistry()
    names = {tool["name"] for tool in registry.list_tools()}
    expected = {
        "blender-mesh-fill",
        "blender-mesh-split",
        "blender-mesh-separate-selected",
        "blender-mesh-triangulate-faces",
        "blender-mesh-tris-to-quads",
    }
    assert expected.issubset(names)


def test_mesh_ops_calls(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append((path, payload))
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    call_map = [
        ("blender-mesh-fill", {"use_beauty": False}),
        ("blender-mesh-grid-fill", {"span": 2, "offset": 1}),
        ("blender-mesh-split", {}),
        ("blender-mesh-separate-selected", {}),
        ("blender-mesh-make-edge-face", {}),
        ("blender-mesh-triangulate-faces", {"quad_method": "BEAUTY", "ngon_method": "CLIP"}),
        ("blender-mesh-quads-to-tris", {"quad_method": "FIXED", "ngon_method": "BEAUTY"}),
        ("blender-mesh-tris-to-quads", {"face_threshold": 0.5, "shape_threshold": 0.5, "uvs": True}),
        ("blender-mesh-poke-faces", {}),
        ("blender-mesh-rip", {}),
        ("blender-mesh-rip-fill", {}),
        ("blender-mesh-bridge-edge-loops", {}),
    ]
    for name, args in call_map:
        result = registry.call_tool(name, args, log_action=False)
        assert result["isError"] is False
    assert calls
    assert all(call[0] == "/exec" for call in calls)


def test_triangulate_enum_validation(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        raise AssertionError("bridge should not be called on invalid enum")

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    bad = registry.call_tool("blender-mesh-triangulate-faces", {"quad_method": "BAD"}, log_action=False)
    assert bad["isError"] is True


def test_tris_to_quads_uses_python_bool(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-mesh-tris-to-quads", {"uvs": True}, log_action=False)
    assert result["isError"] is False
    code = payloads[0]["code"]
    assert "false" not in code
    assert "uvs=True" in code


def test_separate_selected_type_and_empty(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": False, "error": "Nothing selected"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-mesh-separate-selected", {"type": "BY_MATERIAL"}, log_action=False)
    assert result["isError"] is True
    code = payloads[0]["code"]
    assert "BY_MATERIAL" in code
