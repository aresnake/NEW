import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

BRIDGE_URL = os.environ.get("NEW_MCP_BRIDGE_URL", "http://127.0.0.1:8765")
SERVER_VERSION = "0.1.0"


def _get_timeout(default: float) -> float:
    env_val = os.environ.get("NEW_MCP_BRIDGE_TIMEOUT")
    if env_val is None:
        return default
    try:
        return float(env_val)
    except ValueError:
        return default


class ToolError(Exception):
    def __init__(self, message: str, code: int = -32000, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


def _bridge_request(path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 0.5) -> Any:
    url = f"{BRIDGE_URL}{path}"
    use_timeout = _get_timeout(timeout)
    data: Optional[bytes] = None
    headers: Dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=use_timeout) as resp:
            body = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise ToolError(f"Bridge unreachable: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("Invalid response from bridge") from exc


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()

    def _register(
        self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        self._tools[name] = Tool(name=name, description=description, input_schema=input_schema, handler=handler)

    def _register_defaults(self) -> None:
        self._register(
            "health",
            "Health check",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_health,
        )
        self._register(
            "echo",
            "Echo text back",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            self._tool_echo,
        )
        self._register(
            "blender.ping",
            "Ping Blender bridge",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_blender_ping,
        )
        self._register(
            "blender.snapshot",
            "Get Blender scene snapshot",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_blender_snapshot,
        )
        self._register(
            "blender.exec",
            "Execute Python code in Blender (code <= 20000 chars)",
            {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
            self._tool_blender_exec,
        )

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            raise ToolError(f"Unknown tool: {name}", code=-32601)
        tool = self._tools[name]
        return tool.handler(arguments or {})

    def _tool_health(self, _: Dict[str, Any]) -> Dict[str, Any]:
        structured = {"ok": True, "version": SERVER_VERSION}
        return {"content": [{"type": "text", "text": "ok"}], "structured": structured}

    def _tool_echo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        structured = {"text": text}
        return {"content": [{"type": "text", "text": text}], "structured": structured}

    def _tool_blender_ping(self, _: Dict[str, Any]) -> Dict[str, Any]:
        data = _bridge_request("/ping")
        structured = {"ok": bool(data.get("ok")), "blender": data.get("blender")}
        text = f"blender: {structured['blender']}" if structured["ok"] else "bridge unavailable"
        return {"content": [{"type": "text", "text": text}], "structured": structured}

    def _tool_blender_snapshot(self, _: Dict[str, Any]) -> Dict[str, Any]:
        data = _bridge_request("/snapshot", timeout=2.0)
        text = f"scene: {data.get('scene')}"
        return {"content": [{"type": "text", "text": text}], "structured": data}

    def _tool_blender_exec(self, args: Dict[str, Any]) -> Dict[str, Any]:
        code = args.get("code", "")
        if not isinstance(code, str):
            raise ToolError("code must be a string")
        if len(code) > 20000:
            raise ToolError("code too long", data={"limit": 20000})
        payload = {"code": code}
        data = _bridge_request("/exec", payload=payload, timeout=10.0)
        ok = bool(data.get("ok"))
        text = "ok" if ok else f"error: {data.get('error')}"
        return {"content": [{"type": "text", "text": text}], "structured": data}
