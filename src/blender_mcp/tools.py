import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

BRIDGE_URL = os.environ.get("BLENDER_MCP_BRIDGE_URL") or os.environ.get("NEW_MCP_BRIDGE_URL", "http://127.0.0.1:8765")
SERVER_VERSION = "0.1.0"
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_timeout(default: float) -> float:
    env_val = os.environ.get("BLENDER_MCP_BRIDGE_TIMEOUT") or os.environ.get("NEW_MCP_BRIDGE_TIMEOUT")
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
        raise ToolError("Blender bridge unreachable", data={"reason": str(exc)})
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("Invalid response from Blender bridge") from exc


def _make_tool_result(text: str, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()

    def _register(
        self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        if not NAME_PATTERN.match(name):
            raise ValueError(f"Invalid tool name: {name}")
        self._tools[name] = Tool(name=name, description=description, input_schema=input_schema, handler=handler)

    def _register_defaults(self) -> None:
        self._register(
            "health",
            "Health check",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_health,
        )
        self._register(
            "blender-ping",
            "Ping Blender bridge",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_blender_ping,
        )
        self._register(
            "blender-snapshot",
            "Get Blender scene snapshot",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_blender_snapshot,
        )
        self._register(
            "blender-exec",
            "Execute Python code in Blender (code <= 20000 chars)",
            {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
            self._tool_blender_exec,
        )
        self._register(
            "blender-add-cube",
            "Add a cube at the origin",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_add_cube,
        )
        self._register(
            "blender-move-object",
            "Move an object to (x,y,z)",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                },
                "required": ["name", "x", "y", "z"],
                "additionalProperties": False,
            },
            self._tool_move_object,
        )
        self._register(
            "blender-delete-object",
            "Delete an object by name",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_delete_object,
        )
        self._register(
            "macro-blockout",
            "Create a blockout cube scaled to (2,1,1) at origin",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_macro_blockout,
        )

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(name, str):
            raise ToolError("Invalid tool name", code=-32602)
        if name not in self._tools:
            raise ToolError(f"Unknown tool: {name}", code=-32601)
        tool = self._tools[name]
        return tool.handler(arguments or {})

    def _tool_health(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return _make_tool_result(f"ok (server {SERVER_VERSION})")

    def _tool_blender_ping(self, _: Dict[str, Any]) -> Dict[str, Any]:
        data = _bridge_request("/ping")
        ok = bool(data.get("ok", True))
        blender_info = data.get("blender") or "unknown"
        if not ok:
            raise ToolError("Blender bridge reported not ok")
        return _make_tool_result(f"blender: {blender_info}")

    def _tool_blender_snapshot(self, _: Dict[str, Any]) -> Dict[str, Any]:
        data = _bridge_request("/snapshot", timeout=2.0)
        scene = data.get("scene") or data.get("file") or "unknown"
        objects = data.get("objects") or []
        count = len(objects) if isinstance(objects, list) else 0
        return _make_tool_result(f"scene: {scene}, objects: {count}")

    def _tool_blender_exec(self, args: Dict[str, Any]) -> Dict[str, Any]:
        code = args.get("code", "")
        if not isinstance(code, str):
            raise ToolError("code must be a string", code=-32602)
        if len(code) > 20000:
            raise ToolError("code too long", data={"limit": 20000})
        payload = {"code": code}
        data = _bridge_request("/exec", payload=payload, timeout=10.0)
        ok = bool(data.get("ok"))
        if not ok:
            return _make_tool_result(data.get("error") or "Execution failed", is_error=True)
        return _make_tool_result("execution ok")

    def _tool_add_cube(self, _: Dict[str, Any]) -> Dict[str, Any]:
        code = """
import bpy, bmesh
mesh = bpy.data.meshes.new("Cube")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Cube", mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add cube", is_error=True)
        return _make_tool_result("Added cube at origin")

    def _tool_move_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        x, y, z = args.get("x"), args.get("y"), args.get("z")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            xf, yf, zf = float(x), float(y), float(z)
        except (TypeError, ValueError):
            raise ToolError("x, y, z must be numbers", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
obj.location = ({xf}, {yf}, {zf})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to move object", is_error=True)
        return _make_tool_result(f"Moved {name} to ({xf}, {yf}, {zf})")

    def _tool_delete_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
bpy.data.objects.remove(obj, do_unlink=True)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to delete object", is_error=True)
        return _make_tool_result(f"Deleted object {name}")

    def _tool_macro_blockout(self, _: Dict[str, Any]) -> Dict[str, Any]:
        code = """
import bpy, bmesh
name = "BlockoutCube"
existing = bpy.data.objects.get(name)
if existing:
    bpy.data.objects.remove(existing, do_unlink=True)
mesh = bpy.data.meshes.new(name)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new(name, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.scale = (2.0, 1.0, 1.0)
obj.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to create blockout", is_error=True)
        return _make_tool_result("Blockout cube created, scaled to (2,1,1) at origin")
