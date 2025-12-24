import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def test_selection_tools_listed():
    registry = tools.ToolRegistry()
    names = {tool["name"] for tool in registry.list_tools()}
    expected = {
        "blender-set-mode",
        "blender-set-selection-mode",
        "blender-select-all",
        "blender-select-none",
        "blender-select-invert",
        "blender-select-linked",
        "blender-select-more",
        "blender-select-less",
        "blender-select-loop",
        "blender-select-ring",
        "blender-select-trait",
        "blender-select-box",
        "blender-select-circle",
    }
    assert expected.issubset(names)


def test_set_mode_roundtrip(monkeypatch):
    calls = []

    def fake_bridge(path, payload=None, timeout=0.5):
        calls.append((path, payload, timeout))
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    for mode in ("OBJECT", "EDIT", "OBJECT"):
        result = registry.call_tool("blender-set-mode", {"mode": mode}, log_action=False)
        assert result["isError"] is False
    assert len(calls) == 3
    assert all(call[0] == "/exec" for call in calls)
    assert "mode_set" in calls[1][1]["code"]


def test_set_selection_mode(monkeypatch):
    codes = []

    def fake_bridge(path, payload=None, timeout=0.5):
        codes.append(payload["code"])
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    for mode in ("VERT", "EDGE", "FACE"):
        result = registry.call_tool("blender-set-selection-mode", {"mode": mode}, log_action=False)
        assert result["isError"] is False
    assert any("select_mode" in code for code in codes)
    assert "FACE" in codes[-1]


def test_select_all_none_invert(monkeypatch):
    codes = []

    def fake_bridge(path, payload=None, timeout=0.5):
        codes.append(payload["code"])
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    for name in ("blender-select-all", "blender-select-none", "blender-select-invert"):
        result = registry.call_tool(name, {}, log_action=False)
        assert result["isError"] is False
    assert any("SELECT" in code for code in codes)
    assert any("DESELECT" in code for code in codes)
    assert any("INVERT" in code for code in codes)


def test_select_trait_validation_and_mapping(monkeypatch):
    codes = []

    def fake_bridge(path, payload=None, timeout=0.5):
        codes.append(payload["code"])
        return {"ok": True}

    monkeypatch.setattr(tools, "_bridge_request", fake_bridge)
    registry = tools.ToolRegistry()
    ok = registry.call_tool("blender-select-trait", {"trait": "NON_MANIFOLD"}, log_action=False)
    assert ok["isError"] is False
    assert "select_non_manifold" in codes[-1]

    bad = registry.call_tool("blender-select-trait", {"trait": "BAD"}, log_action=False)
    assert bad["isError"] is True
    assert len(codes) == 1
