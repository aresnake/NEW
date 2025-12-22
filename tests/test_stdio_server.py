import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]


def _start_server():
    return _start_server_with_env({})


def _start_server_with_env(extra_env):
    env = {**os.environ, **extra_env}
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT,
        env=env,
    )
    out_queue: "queue.Queue[str]" = queue.Queue()

    def _reader():
        for line in proc.stdout:
            out_queue.put(line)

    threading.Thread(target=_reader, daemon=True).start()
    return proc, out_queue


def _send(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _read(out_queue, timeout=1.0):
    try:
        return out_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def _drain(out_queue, timeout=0.2):
    lines = []
    while True:
        try:
            line = out_queue.get(timeout=timeout if not lines else 0.05)
        except queue.Empty:
            break
        else:
            lines.append(line)
    return lines


def test_stdio_protocol_roundtrip():
    proc, out_queue = _start_server()
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}, "capabilities": {}},
            },
        )
        init_line = _read(out_queue, timeout=1.0)
        assert init_line is not None, "initialize response missing"
        init_resp = json.loads(init_line)
        assert init_resp.get("id") == 1
        assert init_resp.get("result", {}).get("protocolVersion") == "2024-11-05"

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        assert _read(out_queue, timeout=0.3) is None, "notification should not produce output"

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        list_line = _read(out_queue, timeout=1.0)
        assert list_line is not None, "tools/list response missing"
        list_resp = json.loads(list_line)
        names = {tool["name"] for tool in list_resp.get("result", [])}
        assert "health" in names
        assert "echo" in names

        time.sleep(0.1)
        assert _read(out_queue, timeout=0.2) is None, "unexpected extra output on stdout"
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_tools_call_bridge_errors_without_stdout_noise():
    proc, out_queue = _start_server_with_env(
        {"NEW_MCP_BRIDGE_URL": "http://127.0.0.1:65500", "NEW_MCP_BRIDGE_TIMEOUT": "0.2"}
    )
    try:
        _send(
            proc,
            {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "blender.ping", "arguments": {}}},
        )
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "blender.snapshot", "arguments": {}},
            },
        )
        lines = [_read(out_queue, timeout=1.0), _read(out_queue, timeout=1.0)]
        lines = [line for line in lines if line is not None]
        assert len(lines) == 2, "expected two responses for tools/call"
        for line, expected_id in zip(lines, (10, 11)):
            msg = json.loads(line)
            assert msg.get("id") == expected_id
            assert "error" in msg
            assert msg["error"]["code"] == -32000

        # Send notification and ensure no output follows
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        time.sleep(0.1)
        assert _drain(out_queue) == [], "no extra stdout expected"
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
