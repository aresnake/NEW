import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]
REQUESTS_FILE = ROOT / "runs" / "requests.jsonl"


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


def _cleanup(proc):
    if proc.stdin:
        proc.stdin.close()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_model_tools_logging():
    if REQUESTS_FILE.exists():
        REQUESTS_FILE.unlink()
    proc = _start_server()
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "model-start", "arguments": {"goal": "test goal"}},
            },
        )
        _read_line(proc, timeout=1.0)
        assert REQUESTS_FILE.exists(), "requests file should be created"

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "model-step",
                    "arguments": {"session": "sess1", "intent": "move", "proposed_tool": "blender-add-cube"},
                },
            },
        )
        _read_line(proc, timeout=1.0)

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "tool-request", "arguments": {"session": "sess1", "need": "x", "why": "y"}},
            },
        )
        _read_line(proc, timeout=1.0)

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "model-end", "arguments": {"session": "sess1", "summary": "done"}},
            },
        )
        _read_line(proc, timeout=1.0)

        lines = REQUESTS_FILE.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 4
    finally:
        _cleanup(proc)
