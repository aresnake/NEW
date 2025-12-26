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


def test_update_merge_api_probe(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "tool-request", {"session": "s1", "need": "need1", "why": "w1", "api_probe": {"params": {"a": 1}}}, log_action=False
    )
    req_id = json.loads(res["content"][0]["text"])["id"]
    registry.call_tool("tool-request-update", {"id": req_id, "api_probe": {"params": {"b": 2}}}, log_action=False)
    got = registry.call_tool("tool-request-get", {"id": req_id}, log_action=False)
    payload = json.loads(got["content"][0]["text"])
    assert payload["api_probe"]["params"]["a"] == 1
    assert payload["api_probe"]["params"]["b"] == 2


def test_update_replace_api_probe(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res = registry.call_tool(
        "tool-request", {"session": "s1", "need": "need1", "why": "w1", "api_probe": {"params": {"a": 1}}}, log_action=False
    )
    req_id = json.loads(res["content"][0]["text"])["id"]
    registry.call_tool(
        "tool-request-update", {"id": req_id, "api_probe": {"params": {"b": 2}}, "mode": "replace"}, log_action=False
    )
    got = registry.call_tool("tool-request-get", {"id": req_id}, log_action=False)
    payload = json.loads(got["content"][0]["text"])
    assert payload["api_probe"]["params"] == {"b": 2}


def test_tool_request_delete(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res1 = registry.call_tool("tool-request", {"session": "s1", "need": "need1", "why": "w1"}, log_action=False)
    res2 = registry.call_tool("tool-request", {"session": "s2", "need": "need2", "why": "w2"}, log_action=False)
    id1 = json.loads(res1["content"][0]["text"])["id"]
    registry.call_tool("tool-request-delete", {"id": id1}, log_action=False)
    list_res = registry.call_tool("tool-request-list", {"filters": {}}, log_action=False)
    payload = json.loads(list_res["content"][0]["text"])
    ids = [it["id"] for it in payload["items"]]
    assert id1 not in ids
    assert json.loads(res2["content"][0]["text"])["id"] in ids


def test_tool_request_list_filters_api_probe_and_status(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    res1 = registry.call_tool(
        "tool-request", {"session": "s1", "need": "need1", "why": "w1", "api_probe": {"params": {"a": 1}}}, log_action=False
    )
    res2 = registry.call_tool("tool-request", {"session": "s2", "need": "need2", "why": "w2"}, log_action=False)
    req2_id = json.loads(res2["content"][0]["text"])["id"]
    registry.call_tool("tool-request-update", {"id": req2_id, "status": "triaged"}, log_action=False)
    has_probe = registry.call_tool("tool-request-list", {"filters": {"has_api_probe": True}}, log_action=False)
    payload_probe = json.loads(has_probe["content"][0]["text"])
    assert [it["id"] for it in payload_probe["items"]] == [json.loads(res1["content"][0]["text"])["id"]]
    status_res = registry.call_tool("tool-request-list", {"filters": {"status": ["triaged"]}}, log_action=False)
    payload_status = json.loads(status_res["content"][0]["text"])
    assert [it["id"] for it in payload_status["items"]] == [req2_id]


def test_bulk_update(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    registry = tools.ToolRegistry()
    ids = []
    for sess in ("s1", "s2", "s3"):
        res = registry.call_tool("tool-request", {"session": sess, "need": sess, "why": "w"}, log_action=False)
        ids.append(json.loads(res["content"][0]["text"])["id"])
    upd = registry.call_tool("tool-request-bulk-update", {"ids": ids, "patch": {"status": "triaged"}}, log_action=False)
    assert upd["isError"] is False
    for rid in ids:
        got = registry.call_tool("tool-request-get", {"id": rid}, log_action=False)
        payload = json.loads(got["content"][0]["text"])
        assert payload["status"] == "triaged"
