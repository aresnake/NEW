import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_CMD = [sys.executable, "-u", str(ROOT / "scripts" / "mcp_stdio_server.py")]


def _start_server():
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT,
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
