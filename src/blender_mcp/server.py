import sys
import traceback
import warnings
from typing import Any, Dict, Optional

from .protocol import PROTOCOL_VERSION, make_error, make_result, parse_message, serialize_message
from .tools import ToolError, ToolRegistry

SERVER_INFO = {"name": "blender-mcp", "version": "0.1.0"}


class StdioServer:
    def __init__(self, tools: Optional[ToolRegistry] = None, stdin=None, stdout=None, stderr=None) -> None:
        self.tools = tools or ToolRegistry()
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._redirect_warnings()

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

    def _redirect_warnings(self) -> None:
        def _showwarning(message, category, filename, lineno, file=None, line=None) -> None:
            target = file or self._stderr
            try:
                text = warnings.formatwarning(message, category, filename, lineno, line)
                target.write(text)
                target.flush()
            except Exception:
                pass

        warnings.showwarning = _showwarning

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
                serialized = serialize_message(response)
            except Exception as exc:
                self._log_error(f"Failed to serialize response: {exc}")
                self._log_exception()
                continue
            try:
                self._stdout.write(serialized)
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
                result = self.tools.call_tool(name, arguments)
                if not isinstance(result, dict):
                    raise ToolError("Tool result must be an object")
                return make_result(request_id, result)

            return make_error(request_id, -32601, "Method not found")
        except ToolError as exc:
            message = str(exc)
            result = {"content": [{"type": "text", "text": message}], "isError": True}
            return make_result(request_id, result)
        except Exception:
            self._log_exception()
            return make_error(request_id, -32000, "Internal error")
