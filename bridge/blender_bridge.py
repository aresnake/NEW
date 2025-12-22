import contextlib
import io
import json
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy

HOST = "127.0.0.1"
PORT = 8765

_job_queue: "queue.Queue[tuple[str, queue.Queue]]" = queue.Queue()
_server = None


def _process_jobs():
    try:
        code, result_queue = _job_queue.get_nowait()
    except queue.Empty:
        return 0.1

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        local_ns = {}
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exec(code, {"bpy": bpy}, local_ns)
        result = local_ns.get("result")
        result_queue.put({"ok": True, "result": result, "stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue()})
    except Exception as exc:  # noqa: BLE001
        result_queue.put(
            {"ok": False, "error": str(exc), "stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue()}
        )
    return 0.0


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

        result_queue: "queue.Queue[dict]" = queue.Queue()
        _job_queue.put((code, result_queue))
        try:
            result = result_queue.get(timeout=10.0)
        except queue.Empty:
            self._send_json({"ok": False, "error": "Timed out waiting for execution"})
            return
        self._send_json(result)


def start_server():
    global _server
    if _server is not None:
        return _server
    _server = ThreadingHTTPServer((HOST, PORT), _Handler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True)
    thread.start()
    bpy.app.timers.register(_process_jobs, persistent=True)
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
    print(f"Blender bridge server running on http://{HOST}:{PORT}")
