import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools


def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOL_REQUEST_DATA_DIR", str(tmp_path))
    importlib.reload(tools)


def test_create_v2_minimal(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    args = {
        "session": "s1",
        "need": "do something",
        "why": "missing op",
        "type": "bug_fix",
        "priority": "high",
        "domain": "mesh",
        "source": "manual",
    }
    res = registry.call_tool("tool-request", args, log_action=False)
    assert res["isError"] is False
    payload = json.loads(res["content"][0]["text"])
    assert payload["ok"] is True
    assert (tmp_path / "tool_requests.jsonl").exists()


def test_create_legacy_payload_upgraded(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res = registry.call_tool("tool-request", {"session": "legacy", "need": "x", "why": "y"}, log_action=False)
    assert res["isError"] is False
    line = (tmp_path / "tool_requests.jsonl").read_text(encoding="utf-8").splitlines()[0]
    saved = json.loads(line)
    assert saved["schema_version"] == 2
    assert saved["type"] == "enhancement"
    assert saved["priority"] == "medium"
    assert saved["domain"] == "system"


def test_list_filters(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    registry.call_tool(
        "tool-request",
        {"session": "s1", "need": "need1", "why": "w1", "type": "bug_fix", "priority": "low", "domain": "mesh"},
        log_action=False,
    )
    registry.call_tool(
        "tool-request",
        {"session": "s2", "need": "need2", "why": "w2", "type": "enhancement", "priority": "high", "domain": "object"},
        log_action=False,
    )
    res = registry.call_tool("tool-request-list", {"filters": {"domain": "mesh"}}, log_action=False)
    payload = json.loads(res["content"][0]["text"])
    assert len(payload["items"]) == 1
    assert payload["items"][0]["domain"] == "mesh"


def test_get_by_id(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res = registry.call_tool("tool-request", {"session": "s1", "need": "need1", "why": "w1"}, log_action=False)
    req_id = json.loads(res["content"][0]["text"])["id"]
    got = registry.call_tool("tool-request-get", {"id": req_id}, log_action=False)
    payload = json.loads(got["content"][0]["text"])
    assert payload["id"] == req_id
    assert payload["need"] == "need1"


def test_update_status(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res = registry.call_tool("tool-request", {"session": "s1", "need": "need1", "why": "w1"}, log_action=False)
    req_id = json.loads(res["content"][0]["text"])["id"]
    upd = registry.call_tool("tool-request-update", {"id": req_id, "status": "triaged"}, log_action=False)
    assert upd["isError"] is False
    got = registry.call_tool("tool-request-get", {"id": req_id}, log_action=False)
    payload = json.loads(got["content"][0]["text"])
    assert payload["status"] == "triaged"
