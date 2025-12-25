import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_selection_core_listed():
    registry = tools.ToolRegistry()
    names = {t["name"] for t in registry.list_tools()}
    expected = {
        "blender-select-edges-sharp",
        "blender-select-faces-by-normal",
        "blender-select-elements-by-index",
        "blender-select-faces-by-criteria",
    }
    assert expected.issubset(names)


def test_edges_sharp_calls_bridge(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-select-edges-sharp",
        {"angle_degrees": 45, "include_boundary": False, "include_seams": True},
        log_action=False,
    )
    assert res["isError"] is False
    code = payloads[0]["code"]
    assert "math.radians(45.0)" in code


def test_faces_by_normal(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-select-faces-by-normal", {"axis": "Z", "sign": "POS", "min_dot": 0.7}, log_action=False
    )
    assert res["isError"] is False
    assert "min_dot = 0.7" in payloads[0]["code"]


def test_select_by_index_validation(monkeypatch):
    def fake_bridge(path, payload=None, timeout=0.5):
        raise AssertionError("bridge should not be called on invalid input")

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    bad = registry.call_tool("blender-select-elements-by-index", {"element_type": "FACE", "indices": []}, log_action=False)
    assert bad["isError"] is True


def test_faces_by_criteria_area(monkeypatch):
    payloads = []

    def fake_bridge(path, payload=None, timeout=0.5):
        payloads.append(payload)
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "blender-select-faces-by-criteria", {"criteria": "AREA_GT", "threshold": 0.1}, log_action=False
    )
    assert res["isError"] is False
    assert "calc_area" in payloads[0]["code"]
