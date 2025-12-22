import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

BRIDGE_URL = os.environ.get("BLENDER_MCP_BRIDGE_URL") or os.environ.get("NEW_MCP_BRIDGE_URL", "http://127.0.0.1:8765")
SERVER_VERSION = "0.1.0"
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
DEBUG_EXEC_ENABLED = os.environ.get("BLENDER_MCP_DEBUG_EXEC") == "1" or os.environ.get("NEW_MCP_DEBUG_EXEC") == "1"
ROOT_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT_DIR / "runs"
RUNS_FILE = RUNS_DIR / "actions.jsonl"


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


def _append_action(tool: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        summary = ""
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                text_val = first.get("text")
                if isinstance(text_val, str):
                    summary = text_val[:200]
        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "arguments": arguments or {},
            "isError": bool(result.get("isError")),
            "summary": summary,
        }
        with RUNS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        try:
            sys.stderr.write(f"[replay] failed to log action: {exc}\n")
            sys.stderr.flush()
        except Exception:
            pass


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
        self._register(
            "intent-resolve",
            "Resolve natural text to a tool call",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            self._tool_intent_resolve,
        )
        self._register(
            "intent-run",
            "Resolve natural text and run the resolved tool",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            self._tool_intent_run,
        )
        self._register(
            "replay-list",
            "List recent tool executions",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
                "additionalProperties": False,
            },
            self._tool_replay_list,
        )
        self._register(
            "replay-run",
            "Re-run a previous tool execution by id",
            {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            },
            self._tool_replay_run,
        )

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any], *, log_action: bool = True) -> Dict[str, Any]:
        if not isinstance(name, str):
            raise ToolError("Invalid tool name", code=-32602)
        if name not in self._tools:
            raise ToolError(f"Unknown tool: {name}", code=-32601)
        tool = self._tools[name]
        result: Dict[str, Any]
        try:
            result = tool.handler(arguments or {})
        except ToolError as exc:
            result = _make_tool_result(str(exc), is_error=True)
        if log_action and name not in ("replay-list", "replay-run"):
            _append_action(name, arguments or {}, result)
        return result

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
        if not DEBUG_EXEC_ENABLED:
            return _make_tool_result("debug exec disabled", is_error=True)
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

    def _read_actions(self) -> List[Dict[str, Any]]:
        if not RUNS_FILE.exists():
            return []
        try:
            lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
            actions: List[Dict[str, Any]] = []
            for line in lines:
                try:
                    actions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return actions
        except Exception as exc:  # noqa: BLE001
            try:
                sys.stderr.write(f"[replay] failed to read actions: {exc}\n")
                sys.stderr.flush()
            except Exception:
                pass
            return []

    def _tool_replay_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        limit = args.get("limit", 50)
        try:
            limit_val = int(limit)
        except Exception:
            limit_val = 50
        if limit_val <= 0:
            limit_val = 50
        actions = self._read_actions()
        slice_actions = actions[-limit_val:] if actions else []
        lines = []
        for action in reversed(slice_actions):
            lines.append(
                f"{action.get('id','?')} | {action.get('ts','?')} | {action.get('tool','?')} | "
                f"{'err' if action.get('isError') else 'ok'} | {action.get('summary','')}"
            )
        text = "\n".join(lines) if lines else "no actions"
        return _make_tool_result(text, is_error=False)

    def _tool_replay_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        action_id = args.get("id")
        if not isinstance(action_id, str):
            return _make_tool_result("id must be a string", is_error=True)
        actions = self._read_actions()
        target = None
        for action in actions:
            if action.get("id") == action_id:
                target = action
                break
        if target is None:
            return _make_tool_result("action id not found", is_error=True)
        tool = target.get("tool")
        arguments = target.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _make_tool_result("invalid stored arguments", is_error=True)
        if tool not in self._tools:
            return _make_tool_result("stored tool unavailable", is_error=True)
        return self.call_tool(tool, arguments)

    def _resolve_intent(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            raise ToolError("text must be a string", code=-32602)
        normalized = text.strip().lower()
        if not normalized:
            raise ToolError("text is empty", code=-32602)

        def result(tool: str, arguments: Dict[str, Any], confidence: float, notes: str) -> Dict[str, Any]:
            return {"tool": tool, "arguments": arguments, "confidence": confidence, "notes": notes}

        # exec path, gated by env and prefix
        if normalized.startswith("exec:"):
            if not DEBUG_EXEC_ENABLED:
                raise ToolError("debug exec disabled", code=-32602)
            code = text[text.lower().find("exec:") + len("exec:") :].strip()
            if not code:
                raise ToolError("exec code missing", code=-32602)
            return result("blender-exec", {"code": code}, 0.9, "explicit exec request")

        cube_patterns = ("add cube", "ajoute un cube", "create cube")
        if any(pat in normalized for pat in cube_patterns):
            return result("blender-add-cube", {}, 0.9, "cube creation intent")

        if normalized.startswith("move cube") or normalized.startswith("deplace cube") or normalized.startswith("déplace cube"):
            parts = normalized.split()
            try:
                numbers = [float(val) for val in parts[-3:]]
            except Exception:
                raise ToolError("move requires x y z numbers", code=-32602)
            if len(numbers) != 3:
                raise ToolError("move requires x y z numbers", code=-32602)
            x, y, z = numbers
            return result("blender-move-object", {"name": "Cube", "x": x, "y": y, "z": z}, 0.8, "move cube intent")

        delete_patterns = ("delete cube", "supprime cube", "remove cube")
        if any(pat in normalized for pat in delete_patterns):
            return result("blender-delete-object", {"name": "Cube"}, 0.8, "delete cube intent")

        if "blockout" in normalized or "macro blockout" in normalized:
            return result("macro-blockout", {}, 0.8, "blockout intent")

        raise ToolError("intent not recognized", code=-32602)

    def _tool_intent_resolve(self, args: Dict[str, Any]) -> Dict[str, Any]:
        intent_text = args.get("text")
        resolved = self._resolve_intent(intent_text)
        return _make_tool_result(json.dumps(resolved), is_error=False)

    def _tool_intent_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        intent_text = args.get("text")
        try:
            resolved = self._resolve_intent(intent_text)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        tool = resolved.get("tool")
        arguments = resolved.get("arguments") or {}
        if tool not in self._tools or tool in ("intent-run", "intent-resolve"):
            return _make_tool_result("resolved tool not available", is_error=True)
        try:
            return self.call_tool(tool, arguments)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
