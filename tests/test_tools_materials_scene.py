import sys
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_list_materials_and_slots(monkeypatch):
    responses = [
        {"ok": True, "result": ["MatA"]},
        {"ok": True, "result": [{"index": 0, "material": "MatA"}]},
    ]

    def fake_bridge(path, payload=None, timeout=0.5):
        return responses.pop(0)

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    mats = registry.call_tool("blender-list-materials", {}, log_action=False)
    assert mats["isError"] is False
    slots = registry.call_tool("blender-list-material-slots", {"name": "Cube"}, log_action=False)
    assert slots["isError"] is False
    assert "0" in slots["content"][0]["text"]


def test_assign_image_texture(monkeypatch, tmp_path):
    img_file = tmp_path / "tex.png"
    img_file.write_bytes(b"fake")

    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool(
        "blender-assign-image-texture",
        {"object": "Cube", "material": "Mat", "image_path": str(img_file), "target": "BASE_COLOR"},
        log_action=False,
    )
    assert result["isError"] is False


def test_parent_and_move_and_align(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append(path)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    parent = registry.call_tool("blender-parent", {"child": "Cube", "parent": "Root"}, log_action=False)
    move = registry.call_tool(
        "blender-move-to-collection", {"name": "Cube", "collection": "Coll"}, log_action=False
    )
    align = registry.call_tool(
        "blender-align-to-axis", {"name": "Cube", "axis": "Z", "mode": "LOCATION_ZERO"}, log_action=False
    )
    assert parent["isError"] is False
    assert move["isError"] is False
    assert align["isError"] is False
    assert calls


def test_missing_object_errors(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        return {"ok": False, "error": "Object not found"}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    result = registry.call_tool("blender-list-material-slots", {"name": "Missing"}, log_action=False)
    assert result["isError"] is True
    result2 = registry.call_tool("blender-parent", {"child": "Missing", "parent": "Other"}, log_action=False)
    assert result2["isError"] is True
