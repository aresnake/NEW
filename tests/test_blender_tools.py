import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]


class _ExecHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        payload = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _start_mock_bridge():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()
    server = HTTPServer((host, port), _ExecHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://{host}:{port}"


def _start_server(bridge_url):
    env = {**os.environ, "BLENDER_MCP_BRIDGE_URL": bridge_url, "BLENDER_MCP_BRIDGE_TIMEOUT": "1.0"}
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


def _read(proc, timeout=1.0):
    start = time.time()
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if line:
            return line
        time.sleep(0.01)
    return None


def _cleanup(proc, server):
    if proc.stdin:
        proc.stdin.close()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()
    if server:
        server.shutdown()
        server.server_close()


def test_blender_tools_success_with_mock_bridge():
    server, url = _start_mock_bridge()
    proc = _start_server(url)
    try:
        calls = [
            {"id": 1, "method": "tools/call", "params": {"name": "blender-add-cylinder", "arguments": {}}},
            {
                "id": 2,
                "method": "tools/call",
                "params": {"name": "blender-scale-object", "arguments": {"name": "Cube", "uniform": 2}},
            },
            {
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "blender-rotate-object",
                    "arguments": {"name": "Cube", "rotation": [0, 0, 90], "space": "world"},
                },
            },
            {"id": 4, "method": "tools/call", "params": {"name": "blender-add-sphere", "arguments": {}}},
            {"id": 5, "method": "tools/call", "params": {"name": "blender-add-plane", "arguments": {}}},
            {"id": 6, "method": "tools/call", "params": {"name": "blender-add-cone", "arguments": {}}},
            {"id": 7, "method": "tools/call", "params": {"name": "blender-add-torus", "arguments": {}}},
            {"id": 8, "method": "tools/call", "params": {"name": "blender-duplicate-object", "arguments": {"name": "Cube"}}},
            {"id": 9, "method": "tools/call", "params": {"name": "blender-list-objects", "arguments": {}}},
            {
                "id": 10,
                "method": "tools/call",
                "params": {"name": "blender-get-object-info", "arguments": {"name": "Cube"}},
            },
            {"id": 11, "method": "tools/call", "params": {"name": "blender-select-object", "arguments": {"name": "Cube"}}},
            {"id": 12, "method": "tools/call", "params": {"name": "blender-add-camera", "arguments": {}}},
            {"id": 13, "method": "tools/call", "params": {"name": "blender-add-light", "arguments": {}}},
            {
                "id": 14,
                "method": "tools/call",
                "params": {"name": "blender-assign-material", "arguments": {"object": "Cube", "material": "Mat"}},
            },
            {"id": 15, "method": "tools/call", "params": {"name": "blender-set-shading", "arguments": {"name": "Cube", "mode": "flat"}}},
            {"id": 16, "method": "tools/call", "params": {"name": "blender-delete-all", "arguments": {"confirm": "DELETE_ALL"}}},
            {"id": 17, "method": "tools/call", "params": {"name": "blender-reset-transform", "arguments": {"name": "Cube"}}},
            {"id": 18, "method": "tools/call", "params": {"name": "blender-get-mesh-stats", "arguments": {"name": "Cube"}}},
        ]
        for call in calls:
            _send(proc, {"jsonrpc": "2.0", **call})
            line = _read(proc, timeout=1.0)
            assert line is not None
            msg = json.loads(line)
            result = msg.get("result")
            assert isinstance(result, dict)
            assert result.get("isError") is False
    finally:
        _cleanup(proc, server)


def test_blender_tools_arg_errors():
    server, url = _start_mock_bridge()
    proc = _start_server(url)
    try:
        bad_calls = [
            {"id": 20, "name": "blender-scale-object", "arguments": {"name": "Cube", "uniform": "nope"}},
            {"id": 21, "name": "blender-rotate-object", "arguments": {"name": "Cube", "rotation": [0, 0]}},
            {"id": 22, "name": "blender-duplicate-object", "arguments": {"name": 123}},
            {"id": 23, "name": "blender-add-light", "arguments": {"type": "laser"}},
            {"id": 24, "name": "blender-select-object", "arguments": {}},
            {"id": 25, "name": "blender-assign-material", "arguments": {"object": 1, "material": "Mat"}},
            {"id": 26, "name": "blender-set-shading", "arguments": {"name": "Cube", "mode": "auto"}},
            {"id": 27, "name": "blender-delete-all", "arguments": {"confirm": "NOPE"}},
            {"id": 28, "name": "blender-reset-transform", "arguments": {"name": 5}},
            {"id": 29, "name": "blender-get-mesh-stats", "arguments": {"name": 5}},
        ]
        for call in bad_calls:
            _send(
                proc,
                {"jsonrpc": "2.0", "id": call["id"], "method": "tools/call", "params": {"name": call["name"], "arguments": call["arguments"]}},
            )
            line = _read(proc, timeout=1.0)
            assert line is not None
            msg = json.loads(line)
            result = msg.get("result")
            assert isinstance(result, dict)
            assert result.get("isError") is True
    finally:
        _cleanup(proc, server)


def test_blender_new_tools_with_mock_bridge():
    server, url = _start_mock_bridge()
    proc = _start_server(url)
    try:
        calls = [
            {
                "id": 1,
                "method": "tools/call",
                "params": {"name": "blender-join-objects", "arguments": {"objects": ["Cube", "Cylinder"], "name": "Joined"}},
            },
            {
                "id": 2,
                "method": "tools/call",
                "params": {"name": "blender-set-origin", "arguments": {"name": "Cube", "type": "geometry"}},
            },
            {
                "id": 3,
                "method": "tools/call",
                "params": {"name": "blender-apply-transforms", "arguments": {"name": "Cube", "scale": True}},
            },
            {
                "id": 4,
                "method": "tools/call",
                "params": {"name": "blender-create-material", "arguments": {"name": "MyMat"}},
            },
            {
                "id": 5,
                "method": "tools/call",
                "params": {"name": "blender-export", "arguments": {"path": "/tmp/test.fbx", "format": "fbx"}},
            },
            {
                "id": 6,
                "method": "tools/call",
                "params": {"name": "blender-rename-object", "arguments": {"old_name": "Cube", "new_name": "Box"}},
            },
        ]
        for call in calls:
            _send(proc, {"jsonrpc": "2.0", **call})
            line = _read(proc, timeout=1.0)
            assert line is not None
            msg = json.loads(line)
            result = msg.get("result")
            assert isinstance(result, dict)
            assert result.get("isError") is False
    finally:
        _cleanup(proc, server)
