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


def _log(msg: str) -> None:
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass


BRIDGE_STATE = {
    "queue": queue.Queue(),
    "jobs": {},
    "stats": {"ticks": 0, "queued": 0, "executed": 0},
    "timer_registered": False,
    "server_thread": None,
    "httpd": None,
    "host": "127.0.0.1",
    "port": 8765,
    "exec_timeout": float(os.environ.get("NEW_MCP_EXEC_TIMEOUT", "10.0") or 10.0),
}


def drain_queue():
    state = BRIDGE_STATE
    state["stats"]["ticks"] += 1
    processed = 0
    max_per_tick = 10
    while processed < max_per_tick:
        try:
            job = state["queue"].get_nowait()
        except queue.Empty:
            break
        _run_job(job)
        state["stats"]["executed"] += 1
        processed += 1
    return 0.05


def _register_timer():
    state = BRIDGE_STATE
    if state["timer_registered"]:
        return
    bpy.app.timers.register(drain_queue, first_interval=0.05, persistent=True)
    state["timer_registered"] = True
    _log("[bridge] Timer registered")


def _run_job(job: dict) -> None:
    code = job.get("code", "")
    try:
        compiled = compile(code, "<mcp_exec>", "exec")
        exec_ns = {"__builtins__": __builtins__, "bpy": bpy}
        exec(compiled, exec_ns, exec_ns)
        job["ok"] = True
        job["error"] = None
        job["traceback"] = None
        job["result"] = exec_ns.get("result")
    except Exception as exc:  # noqa: BLE001
        job["ok"] = False
        job["error"] = str(exc)
        job["traceback"] = traceback.format_exc()
    finally:
        job["done_event"].set()


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "blender_bridge/0.2"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        _log("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))

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
            state = BRIDGE_STATE
            payload = {
                "ticks": state["stats"]["ticks"],
                "queued": state["stats"]["queued"],
                "executed": state["stats"]["executed"],
                "queue_size": state["queue"].qsize(),
                "timer_registered": state["timer_registered"],
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
        code = payload.get("code")
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
            "error": None,
            "traceback": None,
        }
        state = BRIDGE_STATE
        state["jobs"][job_id] = job
        state["queue"].put(job)
        state["stats"]["queued"] += 1
        _log(f"[bridge] queued job {job_id}")

        done = job["done_event"].wait(timeout=state["exec_timeout"])
        if not done or job["ok"] is None:
            self._send_json({"ok": False, "error": "Timed out waiting for execution", "id": job_id})
            return
        if job["ok"]:
            payload = {"ok": True, "id": job_id}
            if "result" in job:
                payload["result"] = job.get("result")
            self._send_json(payload)
        else:
            self._send_json({"ok": False, "id": job_id, "error": job["error"], "traceback": job["traceback"]})


def start_server():
    state = BRIDGE_STATE
    if state["httpd"] is not None:
        return state["httpd"]
    server = ThreadingHTTPServer((state["host"], state["port"]), BridgeHandler)
    state["httpd"] = server
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    state["server_thread"] = thread
    thread.start()
    _log(f"[bridge] HTTP server started on {state['host']}:{state['port']}")
    _register_timer()
    return server


def stop_server():
    state = BRIDGE_STATE
    if state["httpd"] is None:
        return
    state["httpd"].shutdown()
    state["httpd"].server_close()
    state["httpd"] = None
    state["server_thread"] = None
    _log("[bridge] HTTP server stopped")


if __name__ == "__main__":
    start_server()
