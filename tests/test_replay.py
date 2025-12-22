import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]
RUNS_FILE = ROOT / "runs" / "actions.jsonl"


def _start_server(extra_env=None):
    env = {**os.environ, **(extra_env or {})}
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT,
        env=env,
    )
    return proc


def _send(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _read_line(proc, timeout=1.0):
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if line:
            return line
        time.sleep(0.01)
    return None


def _cleanup_proc(proc):
    if proc.stdin:
        proc.stdin.close()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_replay_logging_and_list(tmp_path):
    if RUNS_FILE.exists():
        RUNS_FILE.unlink()
    proc = _start_server()
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "health", "arguments": {}}})
        _read_line(proc, timeout=1.0)
        assert RUNS_FILE.exists(), "runs file should be created"
        lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 1

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "replay-list", "arguments": {"limit": 10}},
            },
        )
        line = _read_line(proc, timeout=1.0)
        assert line is not None
        msg = json.loads(line)
        result = msg.get("result")
        assert isinstance(result, dict)
        assert result.get("isError") is False
        assert isinstance(result.get("content"), list)
    finally:
        _cleanup_proc(proc)


def test_replay_run_with_bridge_down(tmp_path):
    if RUNS_FILE.exists():
        RUNS_FILE.unlink()
    proc = _start_server({"BLENDER_MCP_BRIDGE_URL": "http://127.0.0.1:65500"})
    try:
        _send(
            proc,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "blender-ping", "arguments": {}}},
        )
        _read_line(proc, timeout=1.0)
        lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
        assert lines
        last_action = json.loads(lines[-1])
        action_id = last_action["id"]

        _send(
            proc,
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "replay-run", "arguments": {"id": action_id}}},
        )
        line = _read_line(proc, timeout=1.0)
        assert line is not None
        msg = json.loads(line)
        result = msg.get("result")
        assert isinstance(result, dict)
        assert result.get("isError") is True
    finally:
        _cleanup_proc(proc)
