import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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
        list_result = list_resp.get("result")
        assert isinstance(list_result, dict), "tools/list result should be an object"
        tools = list_result.get("tools")
        assert isinstance(tools, list), "tools should be a list"
        names = {tool["name"] for tool in tools}
        assert "health" in names
        assert "blender-ping" in names
        assert "blender-snapshot" in names
        assert "blender-add-cube" in names
        assert "blender-add-sphere" in names
        assert "blender-add-plane" in names
        assert "blender-add-cone" in names
        assert "blender-add-torus" in names
        assert "blender-move-object" in names
        assert "blender-delete-object" in names
        assert "macro-blockout" in names
        assert "blender-add-cylinder" in names
        assert "blender-scale-object" in names
        assert "blender-rotate-object" in names
        assert "blender-duplicate-object" in names
        assert "blender-list-objects" in names
        assert "blender-get-object-info" in names
        assert "blender-select-object" in names
        assert "blender-add-camera" in names
        assert "blender-add-light" in names
        assert "intent-resolve" in names
        assert "intent-run" in names
        assert "replay-list" in names
        assert "replay-run" in names
        assert "model-start" in names
        assert "model-step" in names
        assert "model-end" in names
        assert "tool-request" in names
        for tool in tools:
            assert NAME_PATTERN.match(tool["name"]), f"tool name fails regex: {tool['name']}"

        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}})
        health_line = _read(out_queue, timeout=1.0)
        assert health_line is not None, "tools/call response missing"
        health_resp = json.loads(health_line)
        health_result = health_resp.get("result")
        assert isinstance(health_result, dict)
        assert isinstance(health_result.get("content"), list)
        assert health_result.get("isError") is False
        assert health_result["content"][0]["type"] == "text"

        time.sleep(0.1)
        assert _read(out_queue, timeout=0.2) is None, "unexpected extra output on stdout"
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_intent_resolve_parses_move():
    proc, out_queue = _start_server()
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {"name": "intent-resolve", "arguments": {"text": "move cube 1 2 3"}},
            },
        )
        line = _read(out_queue, timeout=1.0)
        assert line is not None
        msg = json.loads(line)
        result = msg.get("result")
        assert isinstance(result, dict)
        content = result.get("content")
        assert isinstance(content, list)
        resolved = json.loads(content[0]["text"])
        assert resolved["tool"] == "blender-move-object"
        assert resolved["arguments"]["x"] == 1
        assert resolved["arguments"]["y"] == 2
        assert resolved["arguments"]["z"] == 3
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_tools_call_bridge_errors_without_stdout_noise():
    proc, out_queue = _start_server_with_env(
        {"BLENDER_MCP_BRIDGE_URL": "http://127.0.0.1:65500", "BLENDER_MCP_BRIDGE_TIMEOUT": "0.2"}
    )
    try:
        _send(
            proc,
            {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "blender-ping", "arguments": {}}},
        )
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "blender-snapshot", "arguments": {}},
            },
        )
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {"name": "blender-exec", "arguments": {"code": "print('x')"}},
            },
        )
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {"name": "intent-run", "arguments": {"text": "add cube"}},
            },
        )
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tools/call",
                "params": {"name": "blender-add-cylinder", "arguments": {}},
            },
        )
        lines = [_read(out_queue, timeout=1.0), _read(out_queue, timeout=1.0)]
        lines.append(_read(out_queue, timeout=1.0))
        lines.append(_read(out_queue, timeout=1.0))
        lines.append(_read(out_queue, timeout=1.0))
        lines = [line for line in lines if line is not None]
        assert len(lines) == 5, "expected five responses for tools/call"
        for line, expected_id in zip(lines, (10, 11, 12, 13, 14)):
            msg = json.loads(line)
            assert msg.get("id") == expected_id
            result = msg.get("result")
            assert isinstance(result, dict)
            assert result.get("isError") is True
            assert isinstance(result.get("content"), list)

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
