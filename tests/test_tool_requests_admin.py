import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp import tools
import pytest


def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOL_REQUEST_DATA_DIR", str(tmp_path))
    importlib.reload(tools)


def test_tool_requests_info(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    reg = tools.ToolRegistry()
    res = reg.call_tool("tool-requests-info", {}, log_action=False)
    assert res["isError"] is False
    payload = json.loads(res["content"][0]["text"])
    assert payload["ok"] is True
    assert "data_dir" in payload
    assert payload["counts"]["loaded_requests"] >= 0


def test_tool_requests_tail_empty(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    reg = tools.ToolRegistry()
    res = reg.call_tool("tool-requests-tail", {"n": 10, "which": "both"}, log_action=False)
    assert res["isError"] is False
    payload = json.loads(res["content"][0]["text"])
    assert payload["ok"] is True
    assert "base" in payload and "updates" in payload


def test_tool_requests_clear_requires_confirm(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    reg = tools.ToolRegistry()
    res = reg.call_tool("tool-requests-clear", {"confirm": False}, log_action=False)
    assert res["isError"] is True


def test_tool_requests_clear_deletes_files(monkeypatch, tmp_path):
    # create store with a file
    tmp_path.joinpath("tool_requests.jsonl").write_text('{"id":"x","need":"n","why":"w","session":"s"}\n', encoding="utf-8")
    tmp_path.joinpath("tool_request_updates.jsonl").write_text('{"id":"x","changes":{"status":"triaged"}}\n', encoding="utf-8")

    _setup_env(monkeypatch, tmp_path)
    reg = tools.ToolRegistry()

    res = reg.call_tool("tool-requests-clear", {"confirm": True}, log_action=False)
    assert res["isError"] is False
    payload = json.loads(res["content"][0]["text"])
    assert payload["ok"] is True
    assert not tmp_path.joinpath("tool_requests.jsonl").exists()
    assert not tmp_path.joinpath("tool_request_updates.jsonl").exists()
