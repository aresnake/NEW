import sys
import traceback
from typing import Any, Dict, Optional

from .protocol import PROTOCOL_VERSION, make_error, make_result, parse_message, serialize_message
from .tools import ToolError, ToolRegistry

SERVER_INFO = {"name": "new-mcp-blender", "version": "0.1.0"}


class StdioServer:
    def __init__(self, tools: Optional[ToolRegistry] = None, stdin=None, stdout=None, stderr=None) -> None:
        self.tools = tools or ToolRegistry()
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def _log_error(self, message: str) -> None:
        try:
            self._stderr.write(message + "\n")
            self._stderr.flush()
        except Exception:
            pass

    def _log_exception(self) -> None:
        try:
            traceback.print_exc(file=self._stderr)
            self._stderr.flush()
        except Exception:
            pass

    def run(self) -> None:
        while True:
            line = self._stdin.readline()
            if line == "":
                break  # EOF
            if not line.strip():
                continue
            response = self._handle_line(line)
            if response is None:
                continue
            try:
                self._stdout.write(serialize_message(response))
                self._stdout.flush()
            except Exception as exc:
                self._log_error(f"Failed to write response: {exc}")
                self._log_exception()
                break

    def _handle_line(self, line: str) -> Optional[Dict[str, Any]]:
        try:
            message = parse_message(line)
        except Exception as exc:
            return make_error(None, -32700, str(exc))

        method = message.get("method")
        request_id = message.get("id")
        raw_params = message.get("params")
        if raw_params is None:
            params_obj: Dict[str, Any] = {}
        elif isinstance(raw_params, dict):
            params_obj = raw_params
        else:
            return make_error(request_id, -32602, "Invalid params")

        # Notifications have no id and produce no response
        if request_id is None:
            if method == "notifications/initialized":
                return None
            return None

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": SERVER_INFO,
                    "capabilities": {"tools": {}},
                }
                return make_result(request_id, result)

            if method == "tools/list":
                tools = self.tools.list_tools()
                return make_result(request_id, {"tools": tools})

            if method == "tools/call":
                params = params_obj
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if not isinstance(params, dict):
                    return make_error(request_id, -32602, "Invalid params")
                if not isinstance(arguments, dict):
                    raise ToolError("Invalid arguments", code=-32602)
                if not isinstance(name, str):
                    raise ToolError("Invalid tool name", code=-32602)
                result = self.tools.call_tool(name, arguments)
                return make_result(request_id, result)

            return make_error(request_id, -32601, "Method not found")
        except ToolError as exc:
            return make_error(request_id, exc.code, str(exc), data=exc.data or None)
        except Exception:
            self._log_exception()
            return make_error(request_id, -32000, "Internal error")
