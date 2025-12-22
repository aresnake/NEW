import json
import os
import queue
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy

HOST = "127.0.0.1"
PORT = 8765
EXEC_TIMEOUT = float(os.environ.get("NEW_MCP_EXEC_TIMEOUT", "10.0") or 10.0)
_job_queue: "queue.Queue[dict]" = queue.Queue()
_job_results: dict = {}
_server = None
_timer_registered = False
_debug_stats = {"ticks": 0, "queued": 0, "executed": 0}
_jobs_lock = threading.Lock()


def _register_timer():
    global _timer_registered
    if _timer_registered:
        return
    bpy.app.timers.register(_drain_queue, first_interval=0.05, persistent=True)
    _timer_registered = True
    sys.stderr.write("[bridge] timer registered\n")
    sys.stderr.flush()


def _drain_queue():
    _debug_stats["ticks"] += 1
    processed = 0
    max_per_tick = 10
    while processed < max_per_tick:
        try:
            job = _job_queue.get_nowait()
        except queue.Empty:
            break
        _run_job(job)
        processed += 1
        _debug_stats["executed"] += 1
    return 0.05


def _run_job(job: dict) -> None:
    code = job.get("code", "")
    try:
        compiled = compile(code, "<mcp_exec>", "exec")
        exec_globals = {"bpy": bpy}
        exec_locals: dict = {}
        exec(compiled, exec_globals, exec_locals)
        job["ok"] = True
        job["error"] = None
        job["traceback"] = None
    except Exception as exc:  # noqa: BLE001
        job["ok"] = False
        job["error"] = str(exc)
        job["traceback"] = traceback.format_exc()
    finally:
        with _jobs_lock:
            _job_results[job["id"]] = job
        job["done_event"].set()


class _Handler(BaseHTTPRequestHandler):
    server_version = "blender_bridge/0.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        try:
            msg = "%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args)
            sys.stderr.write(msg)
        except Exception:
            pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/ping":
            self._send_json({"ok": True, "blender": bpy.app.version_string})
            return
        if self.path == "/snapshot":
            snapshot = {
                "blender_version": bpy.app.version_string,
                "file": bpy.data.filepath,
                "scene": bpy.context.scene.name if bpy.context.scene else None,
                "objects": [
                    {
                        "name": obj.name,
                        "type": obj.type,
                        "location": [obj.location.x, obj.location.y, obj.location.z],
                        "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                        "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
                    }
                    for obj in bpy.data.objects
                ],
            }
            self._send_json(snapshot)
            return
        if self.path == "/debug":
            payload = {
                "ticks": _debug_stats["ticks"],
                "queued": _debug_stats["queued"],
                "executed": _debug_stats["executed"],
                "queue_size": _job_queue.qsize(),
            }
            self._send_json(payload)
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self):  # noqa: N802
        if self.path != "/exec":
            self._send_json({"ok": False, "error": "Not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
            return
        code = payload.get("code") or ""
        if not isinstance(code, str):
            self._send_json({"ok": False, "error": "code must be a string"}, status=400)
            return
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "code": code,
            "created_at": time.time(),
            "done_event": threading.Event(),
            "ok": None,
            "output": "",
            "error": None,
            "traceback": None,
        }
        _job_queue.put(job)
        _debug_stats["queued"] += 1
        sys.stderr.write(f"[bridge] queued job {job_id}\n")
        sys.stderr.flush()
        done = job["done_event"].wait(timeout=EXEC_TIMEOUT)
        if not done or job["ok"] is None:
            self._send_json({"ok": False, "error": "Timed out waiting for execution", "id": job_id})
            return
        resp = {
            "ok": bool(job["ok"]),
            "error": job["error"],
            "traceback": job["traceback"],
            "id": job_id,
        }
        self._send_json(resp)


def start_server():
    global _server
    if _server is not None:
        return _server
    _server = ThreadingHTTPServer((HOST, PORT), _Handler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True)
    thread.start()
    _register_timer()
    return _server


def stop_server():
    global _server
    if _server is None:
        return
    _server.shutdown()
    _server.server_close()
    _server = None


if __name__ == "__main__":
    start_server()
    sys.stderr.write(f"[bridge] running on http://{HOST}:{PORT}\n")
    sys.stderr.flush()
