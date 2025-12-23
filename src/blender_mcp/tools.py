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
REQUESTS_FILE = RUNS_DIR / "requests.jsonl"


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


def _append_request(entry: Dict[str, Any]) -> None:
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        with REQUESTS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        try:
            sys.stderr.write(f"[model] failed to log request: {exc}\n")
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
            "blender-add-cylinder",
            "Add a low-poly cylinder",
            {
                "type": "object",
                "properties": {
                    "vertices": {"type": "integer"},
                    "radius": {"type": "number"},
                    "depth": {"type": "number"},
                    "location": {"type": "array"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_cylinder,
        )
        self._register(
            "blender-add-sphere",
            "Add a UV or ico sphere",
            {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "segments": {"type": "integer"},
                    "rings": {"type": "integer"},
                    "subdivisions": {"type": "integer"},
                    "radius": {"type": "number"},
                    "location": {"type": "array"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_sphere,
        )
        self._register(
            "blender-add-plane",
            "Add a plane",
            {
                "type": "object",
                "properties": {"size": {"type": "number"}, "location": {"type": "array"}, "name": {"type": "string"}},
                "additionalProperties": False,
            },
            self._tool_add_plane,
        )
        self._register(
            "blender-add-cone",
            "Add a cone",
            {
                "type": "object",
                "properties": {
                    "vertices": {"type": "integer"},
                    "radius1": {"type": "number"},
                    "radius2": {"type": "number"},
                    "depth": {"type": "number"},
                    "location": {"type": "array"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_cone,
        )
        self._register(
            "blender-add-torus",
            "Add a torus",
            {
                "type": "object",
                "properties": {
                    "major_radius": {"type": "number"},
                    "minor_radius": {"type": "number"},
                    "major_segments": {"type": "integer"},
                    "minor_segments": {"type": "integer"},
                    "location": {"type": "array"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_torus,
        )
        self._register(
            "blender-scale-object",
            "Scale an object uniformly or per-axis",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "scale": {"type": "array"},
                    "uniform": {"type": "number"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_scale_object,
        )
        self._register(
            "blender-rotate-object",
            "Rotate an object in degrees",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "rotation": {"type": "array"},
                    "space": {"type": "string"},
                },
                "required": ["name", "rotation"],
                "additionalProperties": False,
            },
            self._tool_rotate_object,
        )
        self._register(
            "blender-duplicate-object",
            "Duplicate an object",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "new_name": {"type": "string"},
                    "offset": {"type": "array"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_duplicate_object,
        )
        self._register(
            "blender-list-objects",
            "List objects in the scene",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_list_objects,
        )
        self._register(
            "blender-get-object-info",
            "Get location/rotation/scale and materials for an object",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_get_object_info,
        )
        self._register(
            "blender-select-object",
            "Select one or multiple objects",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "names": {"type": "array"}},
                "required": [],
                "additionalProperties": False,
            },
            self._tool_select_object,
        )
        self._register(
            "blender-add-camera",
            "Add a camera",
            {
                "type": "object",
                "properties": {
                    "location": {"type": "array"},
                    "rotation": {"type": "array"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_camera,
        )
        self._register(
            "blender-add-light",
            "Add a light (point, sun, spot, area)",
            {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "location": {"type": "array"},
                    "rotation": {"type": "array"},
                    "power": {"type": "number"},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            self._tool_add_light,
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
        self._register(
            "model-start",
            "Start an observation session",
            {
                "type": "object",
                "properties": {"goal": {"type": "string"}, "constraints": {"type": "string"}},
                "required": ["goal"],
                "additionalProperties": False,
            },
            self._tool_model_start,
        )
        self._register(
            "model-step",
            "Record an observation step",
            {
                "type": "object",
                "properties": {
                    "session": {"type": "string"},
                    "intent": {"type": "string"},
                    "proposed_tool": {"type": "string"},
                    "proposed_args": {"type": "object"},
                    "notes": {"type": "string"},
                },
                "required": ["session", "intent"],
                "additionalProperties": False,
            },
            self._tool_model_step,
        )
        self._register(
            "model-end",
            "End an observation session",
            {
                "type": "object",
                "properties": {"session": {"type": "string"}, "summary": {"type": "string"}},
                "required": ["session", "summary"],
                "additionalProperties": False,
            },
            self._tool_model_end,
        )
        self._register(
            "tool-request",
            "Request a new tool capability",
            {
                "type": "object",
                "properties": {
                    "session": {"type": "string"},
                    "need": {"type": "string"},
                    "why": {"type": "string"},
                    "examples": {"type": "array"},
                },
                "required": ["session", "need", "why"],
                "additionalProperties": False,
            },
            self._tool_tool_request,
        )
        self._register(
            "blender-join-objects",
            "Join multiple objects into one",
            {
                "type": "object",
                "properties": {
                    "objects": {"type": "array"},
                    "name": {"type": "string"},
                },
                "required": ["objects", "name"],
                "additionalProperties": False,
            },
            self._tool_join_objects,
        )
        self._register(
            "blender-set-origin",
            "Set object origin to geometry, cursor, mass center, or bottom center",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["name", "type"],
                "additionalProperties": False,
            },
            self._tool_set_origin,
        )
        self._register(
            "blender-apply-transforms",
            "Apply location, rotation, and/or scale to object",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "location": {"type": "boolean"},
                    "rotation": {"type": "boolean"},
                    "scale": {"type": "boolean"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_apply_transforms,
        )
        self._register(
            "blender-create-material",
            "Create a new material with optional base color",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "base_color": {"type": "array"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_create_material,
        )
        self._register(
            "blender-export",
            "Export scene to FBX or glTF format",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "format": {"type": "string"},
                    "selected_only": {"type": "boolean"},
                },
                "required": ["path", "format"],
                "additionalProperties": False,
            },
            self._tool_export,
        )
        self._register(
            "blender-rename-object",
            "Rename an object",
            {
                "type": "object",
                "properties": {
                    "old_name": {"type": "string"},
                    "new_name": {"type": "string"},
                },
                "required": ["old_name", "new_name"],
                "additionalProperties": False,
            },
            self._tool_rename_object,
        )
        self._register(
            "blender-assign-material",
            "Assign an existing material to an object",
            {
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "material": {"type": "string"},
                    "slot": {"type": "integer"},
                    "create_slot": {"type": "boolean"},
                },
                "required": ["object", "material"],
                "additionalProperties": False,
            },
            self._tool_assign_material,
        )
        self._register(
            "blender-set-shading",
            "Set object shading to flat or smooth",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "mode": {"type": "string"}},
                "required": ["name", "mode"],
                "additionalProperties": False,
            },
            self._tool_set_shading,
        )
        self._register(
            "blender-add-modifier",
            "Add a modifier to an object with optional settings",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "settings": {"type": "object"}},
                "required": ["name", "type"],
                "additionalProperties": False,
            },
            self._tool_add_modifier,
        )
        self._register(
            "blender-apply-modifier",
            "Apply a modifier on an object",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "modifier": {"type": "string"}},
                "required": ["name", "modifier"],
                "additionalProperties": False,
            },
            self._tool_apply_modifier,
        )
        self._register(
            "blender-boolean",
            "Perform a boolean operation using a cutter object",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "cutter": {"type": "string"},
                    "operation": {"type": "string"},
                    "apply": {"type": "boolean"},
                },
                "required": ["name", "cutter", "operation"],
                "additionalProperties": False,
            },
            self._tool_boolean,
        )
        self._register(
            "blender-delete-all",
            "Delete all objects (safety confirm required)",
            {
                "type": "object",
                "properties": {"confirm": {"type": "string"}},
                "required": ["confirm"],
                "additionalProperties": False,
            },
            self._tool_delete_all,
        )
        self._register(
            "blender-reset-transform",
            "Reset location/rotation/scale of an object",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_reset_transform,
        )
        self._register(
            "blender-get-mesh-stats",
            "Get mesh vertex/edge/face/triangle counts",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_get_mesh_stats,
        )
        self._register(
            "blender-extrude",
            "Extrude all faces of a mesh",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "mode": {"type": "string"}, "distance": {"type": "number"}},
                "required": ["name", "mode", "distance"],
                "additionalProperties": False,
            },
            self._tool_extrude,
        )
        self._register(
            "blender-inset",
            "Inset all faces of a mesh",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "thickness": {"type": "number"}},
                "required": ["name", "thickness"],
                "additionalProperties": False,
            },
            self._tool_inset,
        )
        self._register(
            "blender-loop-cut",
            "Add loop cuts to a mesh",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "cuts": {"type": "integer"}, "position": {"type": "number"}},
                "required": ["name", "cuts"],
                "additionalProperties": False,
            },
            self._tool_loop_cut,
        )
        self._register(
            "blender-bevel-edges",
            "Bevel mesh edges",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "width": {"type": "number"}, "segments": {"type": "integer"}},
                "required": ["name", "width", "segments"],
                "additionalProperties": False,
            },
            self._tool_bevel_edges,
        )
        self._register(
            "blender-merge-by-distance",
            "Merge mesh vertices by distance",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "distance": {"type": "number"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_merge_by_distance,
        )
        self._register(
            "blender-recalc-normals",
            "Recalculate mesh normals (outside or inside)",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "inside": {"type": "boolean"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_recalc_normals,
        )
        self._register(
            "blender-triangulate",
            "Triangulate mesh faces",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "method": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_triangulate,
        )
        self._register(
            "blender-uv-unwrap",
            "Mark seams (optional) and unwrap UVs for a mesh",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "method": {"type": "string"},
                    "margin": {"type": "number"},
                    "mark_seams": {"type": "boolean"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_uv_unwrap,
        )
        self._register(
            "blender-list-materials",
            "List all materials in the scene",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self._tool_list_materials,
        )
        self._register(
            "blender-list-material-slots",
            "List material slots for an object",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            self._tool_list_material_slots,
        )
        self._register(
            "blender-assign-image-texture",
            "Assign an image texture to a material slot",
            {
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "material": {"type": "string"},
                    "image_path": {"type": "string"},
                    "target": {"type": "string"},
                    "create_material": {"type": "boolean"},
                    "create_slot": {"type": "boolean"},
                },
                "required": ["object", "material", "image_path"],
                "additionalProperties": False,
            },
            self._tool_assign_image_texture,
        )
        self._register(
            "blender-parent",
            "Parent one object to another",
            {
                "type": "object",
                "properties": {
                    "child": {"type": "string"},
                    "parent": {"type": "string"},
                    "keep_transform": {"type": "boolean"},
                },
                "required": ["child", "parent"],
                "additionalProperties": False,
            },
            self._tool_parent,
        )
        self._register(
            "blender-move-to-collection",
            "Move an object to a collection (links without unlinking others)",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "collection": {"type": "string"}, "create": {"type": "boolean"}},
                "required": ["name", "collection"],
                "additionalProperties": False,
            },
            self._tool_move_to_collection,
        )
        self._register(
            "blender-align-to-axis",
            "Align object rotation or location to axis",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "axis": {"type": "string"},
                    "mode": {"type": "string"},
                },
                "required": ["name", "axis"],
                "additionalProperties": False,
            },
            self._tool_align_to_axis,
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
        if log_action and name not in ("replay-list", "replay-run", "model-start", "model-step", "model-end", "tool-request"):
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

    def _validate_vector(self, value: Any, *, name: str) -> Optional[List[float]]:
        if value is None:
            return None
        if not isinstance(value, list) or len(value) != 3:
            raise ToolError(f"{name} must be an array of 3 numbers", code=-32602)
        out: List[float] = []
        for v in value:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                raise ToolError(f"{name} must be an array of 3 numbers", code=-32602)
        return out

    def _tool_add_cylinder(self, args: Dict[str, Any]) -> Dict[str, Any]:
        vertices = args.get("vertices", 16)
        radius = args.get("radius", 1.0)
        depth = args.get("depth", 2.0)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name")
        try:
            vertices_i = int(vertices)
        except Exception:
            raise ToolError("vertices must be an integer", code=-32602)
        try:
            radius_f = float(radius)
            depth_f = float(depth)
        except Exception:
            raise ToolError("radius and depth must be numbers", code=-32602)
        if name is not None and not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
import bmesh
mesh = bpy.data.meshes.new("Cylinder")
bm = bmesh.new()
bmesh.ops.create_circle(bm, segments={vertices_i}, radius={radius_f}, cap_ends=True)
bmesh.ops.extrude_edge_only(bm, edges=bm.edges)
bmesh.ops.translate(bm, verts=[v for v in bm.verts if v.co.z > 0], vec=(0,0,{depth_f}))
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name or "Cylinder")}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add cylinder", is_error=True)
        return _make_tool_result("Added cylinder", is_error=False)

    def _tool_scale_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        scale = args.get("scale")
        uniform = args.get("uniform")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        vec = None
        if uniform is not None:
            try:
                val = float(uniform)
            except (TypeError, ValueError):
                raise ToolError("uniform must be a number", code=-32602)
            vec = [val, val, val]
        elif scale is not None:
            vec = self._validate_vector(scale, name="scale")
        if vec is None:
            raise ToolError("provide uniform or scale", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
obj.scale = ({vec[0]}, {vec[1]}, {vec[2]})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to scale object", is_error=True)
        return _make_tool_result(f"Scaled {name} to {tuple(vec)}", is_error=False)

    def _tool_rotate_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        rotation = args.get("rotation")
        space = args.get("space", "world")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        rot_vec = self._validate_vector(rotation, name="rotation")
        if space not in ("world", "local"):
            raise ToolError("space must be 'world' or 'local'", code=-32602)
        code = f"""
import bpy, math
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
rx, ry, rz = ({rot_vec[0]}, {rot_vec[1]}, {rot_vec[2]})
rad = (math.radians(rx), math.radians(ry), math.radians(rz))
if {json.dumps(space)} == "world":
    obj.rotation_euler = rad
else:
    obj.rotation_euler = rad
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to rotate object", is_error=True)
        return _make_tool_result(f"Rotated {name} to {tuple(rot_vec)} deg ({space})", is_error=False)

    def _tool_add_sphere(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sphere_type = args.get("type", "uv")
        segments = args.get("segments", 32)
        rings = args.get("rings", 16)
        subdivisions = args.get("subdivisions", 2)
        radius = args.get("radius", 1.0)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Sphere"
        if sphere_type not in ("uv", "ico"):
            raise ToolError("type must be 'uv' or 'ico'", code=-32602)
        try:
            radius_f = float(radius)
        except Exception:
            raise ToolError("radius must be a number", code=-32602)
        if sphere_type == "uv":
            try:
                seg_i = int(segments)
                ring_i = int(rings)
            except Exception:
                raise ToolError("segments and rings must be integers", code=-32602)
            code = f"""
import bpy, bmesh
mesh = bpy.data.meshes.new("UVSphere")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments={seg_i}, v_segments={ring_i}, diameter={radius_f*2})
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name)}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        else:
            try:
                sub_i = int(subdivisions)
            except Exception:
                raise ToolError("subdivisions must be an integer", code=-32602)
            code = f"""
import bpy, bmesh
mesh = bpy.data.meshes.new("IcoSphere")
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions={sub_i}, radius={radius_f})
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name)}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add sphere", is_error=True)
        return _make_tool_result(f"Added {sphere_type} sphere", is_error=False)

    def _tool_add_plane(self, args: Dict[str, Any]) -> Dict[str, Any]:
        size = args.get("size", 2.0)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Plane"
        try:
            size_f = float(size)
        except Exception:
            raise ToolError("size must be a number", code=-32602)
        code = f"""
import bpy, bmesh
mesh = bpy.data.meshes.new("Plane")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size={size_f})
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name)}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add plane", is_error=True)
        return _make_tool_result("Added plane", is_error=False)

    def _tool_add_cone(self, args: Dict[str, Any]) -> Dict[str, Any]:
        vertices = args.get("vertices", 32)
        radius1 = args.get("radius1", 1.0)
        radius2 = args.get("radius2", 0.0)
        depth = args.get("depth", 2.0)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Cone"
        try:
            vertices_i = int(vertices)
        except Exception:
            raise ToolError("vertices must be an integer", code=-32602)
        try:
            r1 = float(radius1)
            r2 = float(radius2)
            d = float(depth)
        except Exception:
            raise ToolError("radius1, radius2, depth must be numbers", code=-32602)
        code = f"""
import bpy, bmesh
mesh = bpy.data.meshes.new("Cone")
bm = bmesh.new()
bmesh.ops.create_cone(bm, segments={vertices_i}, radius1={r1}, radius2={r2}, depth={d})
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name)}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add cone", is_error=True)
        return _make_tool_result("Added cone", is_error=False)

    def _tool_add_torus(self, args: Dict[str, Any]) -> Dict[str, Any]:
        major_radius = args.get("major_radius", 1.0)
        minor_radius = args.get("minor_radius", 0.25)
        major_segments = args.get("major_segments", 24)
        minor_segments = args.get("minor_segments", 16)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Torus"
        try:
            maj_r = float(major_radius)
            min_r = float(minor_radius)
        except Exception:
            raise ToolError("major_radius and minor_radius must be numbers", code=-32602)
        try:
            maj_seg = int(major_segments)
            min_seg = int(minor_segments)
        except Exception:
            raise ToolError("major_segments and minor_segments must be integers", code=-32602)
        code = f"""
import bpy, bmesh
mesh = bpy.data.meshes.new("Torus")
bm = bmesh.new()
bmesh.ops.create_torus(bm, segments_major={maj_seg}, segments_minor={min_seg}, major_radius={maj_r}, minor_radius={min_r})
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new({json.dumps(name)}, mesh)
scene = bpy.context.scene
scene.collection.objects.link(obj)
obj.location = ({location[0]}, {location[1]}, {location[2]})
bpy.context.view_layer.objects.active = obj
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add torus", is_error=True)
        return _make_tool_result("Added torus", is_error=False)

    def _tool_duplicate_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        new_name = args.get("new_name")
        offset = self._validate_vector(args.get("offset"), name="offset") or [0.0, 0.0, 0.0]
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if new_name is not None and not isinstance(new_name, str):
            raise ToolError("new_name must be a string", code=-32602)
        target_name = new_name or f"{name}_copy"
        code = f"""
import bpy
name = {json.dumps(name)}
new_name = {json.dumps(target_name)}
offset = ({offset[0]}, {offset[1]}, {offset[2]})
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
dup = obj.copy()
dup.data = obj.data.copy()
dup.name = new_name
dup.location = (obj.location.x + offset[0], obj.location.y + offset[1], obj.location.z + offset[2])
obj.users_collection[0].objects.link(dup)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to duplicate object", is_error=True)
        return _make_tool_result(f"Duplicated {name} -> {target_name}", is_error=False)

    def _tool_list_objects(self, _: Dict[str, Any]) -> Dict[str, Any]:
        code = """
import bpy
result = []
for obj in bpy.data.objects:
    result.append({"name": obj.name, "type": obj.type})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to list objects", is_error=True)
        items = data.get("result") or []
        if isinstance(items, list):
            names = [f"{item.get('name')} ({item.get('type')})" for item in items if isinstance(item, dict)]
            text = ", ".join(names) if names else "no objects"
        else:
            text = "listed objects"
        return _make_tool_result(text, is_error=False)

    def _tool_get_object_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
import math
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
result = {{
    "name": obj.name,
    "type": obj.type,
    "location": [obj.location.x, obj.location.y, obj.location.z],
    "rotation": [math.degrees(v) for v in obj.rotation_euler],
    "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
    "materials": [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else [],
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to get object info", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            mat_list = info.get("materials") or []
            mats = ", ".join(mat_list) if isinstance(mat_list, list) else ""
            text = (
                f"{info.get('name')} loc={info.get('location')} rot(deg)={info.get('rotation')} "
                f"scale={info.get('scale')} materials={mats}"
            )
        else:
            text = f"Fetched info for {name}"
        return _make_tool_result(text, is_error=False)

    def _tool_select_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        names = args.get("names")
        selected: List[str] = []
        if name is not None:
            if not isinstance(name, str):
                raise ToolError("name must be a string", code=-32602)
            selected.append(name)
        if names is not None:
            if not isinstance(names, list):
                raise ToolError("names must be a list", code=-32602)
            for item in names:
                if not isinstance(item, str):
                    raise ToolError("names entries must be strings", code=-32602)
            selected.extend(names)
        if not selected:
            raise ToolError("provide name or names", code=-32602)
        code = f"""
import bpy
names = {json.dumps(selected)}
bpy.ops.object.select_all(action='DESELECT')
found = []
missing = []
for nm in names:
    obj = bpy.data.objects.get(nm)
    if obj is None:
        missing.append(nm)
        continue
    obj.select_set(True)
    found.append(nm)
if missing:
    raise ValueError(f"Objects not found: {{', '.join(missing)}}")
if found:
    bpy.context.view_layer.objects.active = bpy.data.objects.get(found[0])
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to select objects", is_error=True)
        return _make_tool_result(f"Selected: {', '.join(selected)}", is_error=False)

    def _tool_add_camera(self, args: Dict[str, Any]) -> Dict[str, Any]:
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 10.0]
        rotation = self._validate_vector(args.get("rotation"), name="rotation") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Camera"
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy, math
cam_data = bpy.data.cameras.new({json.dumps(name)})
cam_obj = bpy.data.objects.new({json.dumps(name)}, cam_data)
scene = bpy.context.scene
scene.collection.objects.link(cam_obj)
cam_obj.location = ({location[0]}, {location[1]}, {location[2]})
cam_obj.rotation_euler = (math.radians({rotation[0]}), math.radians({rotation[1]}), math.radians({rotation[2]}))
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add camera", is_error=True)
        return _make_tool_result(f"Added camera {name}", is_error=False)

    def _tool_add_light(self, args: Dict[str, Any]) -> Dict[str, Any]:
        light_type = args.get("type", "POINT").upper()
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 2.0]
        rotation = self._validate_vector(args.get("rotation"), name="rotation") or [0.0, 0.0, 0.0]
        power = args.get("power", 1000.0)
        name = args.get("name") or "Light"
        valid_types = {"POINT", "SUN", "SPOT", "AREA"}
        if light_type not in valid_types:
            raise ToolError("type must be one of point, sun, spot, area", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            power_val = float(power)
        except Exception:
            raise ToolError("power must be a number", code=-32602)
        code = f"""
import bpy, math
light_data = bpy.data.lights.new(name={json.dumps(name)}, type={json.dumps(light_type)})
light_data.energy = {power_val}
light_obj = bpy.data.objects.new(name={json.dumps(name)}, object_data=light_data)
scene = bpy.context.scene
scene.collection.objects.link(light_obj)
light_obj.location = ({location[0]}, {location[1]}, {location[2]})
light_obj.rotation_euler = (math.radians({rotation[0]}), math.radians({rotation[1]}), math.radians({rotation[2]}))
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add light", is_error=True)
        return _make_tool_result(f"Added light {name} ({light_type.lower()})", is_error=False)

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

    def _tool_model_start(self, args: Dict[str, Any]) -> Dict[str, Any]:
        goal = args.get("goal")
        constraints = args.get("constraints")
        if not isinstance(goal, str):
            return _make_tool_result("goal must be a string", is_error=True)
        if constraints is not None and not isinstance(constraints, str):
            return _make_tool_result("constraints must be a string", is_error=True)
        session_id = str(uuid.uuid4())
        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "model-start",
            "session": session_id,
            "payload": {"goal": goal, "constraints": constraints},
        }
        _append_request(entry)
        return _make_tool_result(f"session: {session_id}", is_error=False)

    def _tool_model_step(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session = args.get("session")
        intent = args.get("intent")
        proposed_tool = args.get("proposed_tool")
        proposed_args = args.get("proposed_args")
        notes = args.get("notes")
        if not isinstance(session, str):
            return _make_tool_result("session must be a string", is_error=True)
        if not isinstance(intent, str):
            return _make_tool_result("intent must be a string", is_error=True)
        if proposed_tool is not None and not isinstance(proposed_tool, str):
            return _make_tool_result("proposed_tool must be a string", is_error=True)
        if proposed_args is not None and not isinstance(proposed_args, dict):
            return _make_tool_result("proposed_args must be an object", is_error=True)
        if notes is not None and not isinstance(notes, str):
            return _make_tool_result("notes must be a string", is_error=True)
        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "model-step",
            "session": session,
            "payload": {
                "intent": intent,
                "proposed_tool": proposed_tool,
                "proposed_args": proposed_args,
                "notes": notes,
            },
        }
        _append_request(entry)
        return _make_tool_result("model step recorded", is_error=False)

    def _tool_model_end(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session = args.get("session")
        summary = args.get("summary")
        if not isinstance(session, str):
            return _make_tool_result("session must be a string", is_error=True)
        if not isinstance(summary, str):
            return _make_tool_result("summary must be a string", is_error=True)
        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "model-end",
            "session": session,
            "payload": {"summary": summary},
        }
        _append_request(entry)
        return _make_tool_result("model session ended", is_error=False)

    def _tool_tool_request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session = args.get("session")
        need = args.get("need")
        why = args.get("why")
        examples = args.get("examples")
        if not isinstance(session, str):
            return _make_tool_result("session must be a string", is_error=True)
        if not isinstance(need, str):
            return _make_tool_result("need must be a string", is_error=True)
        if not isinstance(why, str):
            return _make_tool_result("why must be a string", is_error=True)
        if examples is not None and not isinstance(examples, list):
            return _make_tool_result("examples must be a list", is_error=True)
        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "tool-request",
            "session": session,
            "payload": {"need": need, "why": why, "examples": examples},
        }
        _append_request(entry)
        return _make_tool_result("tool request recorded", is_error=False)

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

    def _tool_join_objects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        objects = args.get("objects")
        name = args.get("name")
        if not isinstance(objects, list) or not objects:
            raise ToolError("objects must be a non-empty list", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        for obj in objects:
            if not isinstance(obj, str):
                raise ToolError("all objects must be strings", code=-32602)
        code = f"""
import bpy
objects = {json.dumps(objects)}
name = {json.dumps(name)}
bpy.ops.object.select_all(action='DESELECT')
for obj_name in objects:
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError(f"Object {{obj_name}} not found")
    obj.select_set(True)
if not bpy.context.selected_objects:
    raise ValueError("No objects selected")
bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
bpy.ops.object.join()
bpy.context.active_object.name = name
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to join objects", is_error=True)
        return _make_tool_result(f"Joined {len(objects)} objects into {name}", is_error=False)

    def _tool_set_origin(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        origin_type = args.get("type")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(origin_type, str):
            raise ToolError("type must be a string", code=-32602)
        valid_types = {
            "geometry": "ORIGIN_GEOMETRY",
            "cursor": "ORIGIN_CURSOR",
            "mass_center": "ORIGIN_CENTER_OF_MASS",
            "bottom_center": "BOTTOM_CENTER",
        }
        if origin_type not in valid_types:
            raise ToolError(f"type must be one of {list(valid_types.keys())}", code=-32602)
        if origin_type == "bottom_center":
            code = f"""
import bpy, mathutils
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
coords = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
if not coords:
    raise ValueError("Object has no bounding box")
xs = [c.x for c in coords]; ys = [c.y for c in coords]; zs = [c.z for c in coords]
target = mathutils.Vector((sum(xs)/len(xs), sum(ys)/len(ys), min(zs)))
cur = obj.matrix_world.to_translation()
delta = target - cur
if hasattr(obj.data, "transform"):
    obj.data.transform(mathutils.Matrix.Translation(-obj.matrix_world.inverted() @ delta))
    obj.location = obj.location + delta
else:
    raise ValueError("Object has no geometry to transform")
"""
        else:
            blender_type = valid_types[origin_type]
            code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.origin_set(type={json.dumps(blender_type)})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to set origin", is_error=True)
        return _make_tool_result(f"Set origin of {name} to {origin_type}", is_error=False)

    def _tool_apply_transforms(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        location = args.get("location", False)
        rotation = args.get("rotation", False)
        scale = args.get("scale", False)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(location, bool):
            raise ToolError("location must be a boolean", code=-32602)
        if not isinstance(rotation, bool):
            raise ToolError("rotation must be a boolean", code=-32602)
        if not isinstance(scale, bool):
            raise ToolError("scale must be a boolean", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError(f"Object {{name}} not found")
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(location={location}, rotation={rotation}, scale={scale})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to apply transforms", is_error=True)
        parts = []
        if location:
            parts.append("location")
        if rotation:
            parts.append("rotation")
        if scale:
            parts.append("scale")
        applied = ", ".join(parts) if parts else "none"
        return _make_tool_result(f"Applied transforms ({applied}) to {name}", is_error=False)

    def _tool_assign_material(self, args: Dict[str, Any]) -> Dict[str, Any]:
        obj_name = args.get("object")
        mat_name = args.get("material")
        slot = args.get("slot", 0)
        create_slot = args.get("create_slot", True)
        if not isinstance(obj_name, str):
            raise ToolError("object must be a string", code=-32602)
        if not isinstance(mat_name, str):
            raise ToolError("material must be a string", code=-32602)
        try:
            slot_index = int(slot)
        except Exception:
            raise ToolError("slot must be an integer", code=-32602)
        if slot_index < 0:
            raise ToolError("slot must be >= 0", code=-32602)
        if not isinstance(create_slot, bool):
            raise ToolError("create_slot must be a boolean", code=-32602)
        code = f"""
import bpy
obj = bpy.data.objects.get({json.dumps(obj_name)})
if obj is None:
    raise ValueError("Object not found")
mat = bpy.data.materials.get({json.dumps(mat_name)})
if mat is None:
    raise ValueError("Material not found")
slot_index = {slot_index}
create_slot = {create_slot}
slots = obj.data.materials
if slot_index >= len(slots):
    if not create_slot:
        raise ValueError("Material slot does not exist")
    while len(slots) <= slot_index:
        slots.append(None)
slots[slot_index] = mat
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to assign material", is_error=True)
        return _make_tool_result(f"Assigned {mat_name} to {obj_name} (slot {slot_index})", is_error=False)

    def _tool_assign_image_texture(self, args: Dict[str, Any]) -> Dict[str, Any]:
        obj_name = args.get("object")
        mat_name = args.get("material")
        image_path = args.get("image_path")
        target = (args.get("target") or "BASE_COLOR").upper()
        create_material = args.get("create_material", False)
        create_slot = args.get("create_slot", True)
        if not isinstance(obj_name, str):
            raise ToolError("object must be a string", code=-32602)
        if not isinstance(mat_name, str):
            raise ToolError("material must be a string", code=-32602)
        if not isinstance(image_path, str):
            raise ToolError("image_path must be a string", code=-32602)
        valid_targets = {"BASE_COLOR", "ROUGHNESS", "NORMAL"}
        if target not in valid_targets:
            raise ToolError("target must be BASE_COLOR, ROUGHNESS, or NORMAL", code=-32602)
        if not isinstance(create_material, bool):
            raise ToolError("create_material must be a boolean", code=-32602)
        if not isinstance(create_slot, bool):
            raise ToolError("create_slot must be a boolean", code=-32602)
        code = f"""
import bpy
import os
obj_name = {json.dumps(obj_name)}
mat_name = {json.dumps(mat_name)}
image_path = {json.dumps(image_path)}
target = {json.dumps(target)}
create_material = {create_material}
create_slot = {create_slot}
obj = bpy.data.objects.get(obj_name)
if obj is None:
    raise ValueError("Object not found")
mat = bpy.data.materials.get(mat_name)
if mat is None:
    if not create_material:
        raise ValueError("Material not found")
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
if not hasattr(obj.data, "materials"):
    raise ValueError("Object has no material slots")
slots = obj.data.materials
if mat.name not in [m.name for m in slots if m]:
    if not slots:
        slots.append(mat)
    else:
        if create_slot:
            slots.append(None)
        slots[0] = mat if not slots[0] else slots[0]
        if mat not in slots:
            for i, existing in enumerate(slots):
                if existing is None:
                    slots[i] = mat
                    break
            else:
                slots.append(mat)
img = bpy.data.images.load(image_path, check_existing=True)
if mat.node_tree is None:
    mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf is None:
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
if output is None:
    output = nodes.new(type='ShaderNodeOutputMaterial')
tex_node = nodes.new(type='ShaderNodeTexImage')
tex_node.image = img
tex_node.location = (-400, 0)
bsdf.location = (-100, 0)
output.location = (200, 0)
if target == "BASE_COLOR":
    if hasattr(tex_node, "image") and hasattr(tex_node.image, "colorspace_settings"):
        tex_node.image.colorspace_settings.name = "sRGB"
    links.new(tex_node.outputs.get("Color"), bsdf.inputs.get("Base Color"))
elif target == "ROUGHNESS":
    if hasattr(tex_node, "image") and hasattr(tex_node.image, "colorspace_settings"):
        tex_node.image.colorspace_settings.name = "Non-Color"
    links.new(tex_node.outputs.get("Color"), bsdf.inputs.get("Roughness"))
elif target == "NORMAL":
    if hasattr(tex_node, "image") and hasattr(tex_node.image, "colorspace_settings"):
        tex_node.image.colorspace_settings.name = "Non-Color"
    normal_node = nodes.new(type='ShaderNodeNormalMap')
    normal_node.location = (-150, -200)
    links.new(tex_node.outputs.get("Color"), normal_node.inputs.get("Color"))
    links.new(normal_node.outputs.get("Normal"), bsdf.inputs.get("Normal"))
if not any(link.to_node == output for link in links):
    links.new(bsdf.outputs.get("BSDF"), output.inputs.get("Surface"))
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=10.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to assign image texture", is_error=True)
        return _make_tool_result(f"Assigned {target} texture to {mat_name} on {obj_name}", is_error=False)

    def _tool_set_shading(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        mode = args.get("mode")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if mode not in ("flat", "smooth"):
            raise ToolError("mode must be 'flat' or 'smooth'", code=-32602)
        use_smooth = mode == "smooth"
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if not hasattr(obj.data, "polygons"):
    raise ValueError("Object has no polygons")
for poly in obj.data.polygons:
    poly.use_smooth = {use_smooth}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to set shading", is_error=True)
        return _make_tool_result(f"Set shading of {name} to {mode}", is_error=False)

    def _tool_delete_all(self, args: Dict[str, Any]) -> Dict[str, Any]:
        confirm = args.get("confirm")
        if confirm != "DELETE_ALL":
            raise ToolError("confirm must equal 'DELETE_ALL'", code=-32602)
        code = """
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to delete all", is_error=True)
        return _make_tool_result("Deleted all objects", is_error=False)

    def _tool_reset_transform(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to reset transform", is_error=True)
        return _make_tool_result(f"Reset transforms for {name}", is_error=False)

    def _tool_get_mesh_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
mesh = obj.data
mesh.calc_loop_triangles()
result = {{
    "verts": len(mesh.vertices),
    "edges": len(mesh.edges),
    "faces": len(mesh.polygons),
    "triangles": len(mesh.loop_triangles),
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to get mesh stats", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            text = f"{name}: verts={info.get('verts')} edges={info.get('edges')} faces={info.get('faces')} tris={info.get('triangles')}"
        else:
            text = f"Mesh stats for {name}"
        return _make_tool_result(text, is_error=False)

    def _tool_extrude(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        mode = args.get("mode")
        distance = args.get("distance")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if mode not in ("faces",):
            raise ToolError("mode must be 'faces'", code=-32602)
        try:
            dist = float(distance)
        except Exception:
            raise ToolError("distance must be a number", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
bm.normal_update()
faces = bm.faces[:]
if not faces:
    raise ValueError("Mesh has no faces")
geom = bmesh.ops.extrude_face_region(bm, geom=faces)
verts = [ele for ele in geom["geom"] if isinstance(ele, bmesh.types.BMVert)]
if not verts:
    raise ValueError("Extrude failed")
for v in verts:
    v.co += v.normal.normalized() * {dist}
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to extrude", is_error=True)
        return _make_tool_result(f"Extruded faces on {name}", is_error=False)

    def _tool_inset(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        thickness = args.get("thickness")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            thickness_val = float(thickness)
        except Exception:
            raise ToolError("thickness must be a number", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
faces = bm.faces[:]
if not faces:
    raise ValueError("Mesh has no faces")
bmesh.ops.inset_region(bm, faces=faces, thickness={thickness_val}, depth=0.0, use_even_offset=True)
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to inset", is_error=True)
        return _make_tool_result(f"Inset faces on {name}", is_error=False)

    def _tool_loop_cut(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        cuts = args.get("cuts")
        position = args.get("position", 0.5)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            cuts_i = int(cuts)
        except Exception:
            raise ToolError("cuts must be an integer", code=-32602)
        if cuts_i < 1 or cuts_i > 20:
            raise ToolError("cuts must be between 1 and 20", code=-32602)
        try:
            pos_f = float(position)
        except Exception:
            raise ToolError("position must be a number", code=-32602)
        if pos_f < 0.0 or pos_f > 1.0:
            raise ToolError("position must be between 0 and 1", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
edges = bm.edges[:]
if not edges:
    raise ValueError("Mesh has no edges")
perc = [{pos_f} for _ in edges]
bmesh.ops.subdivide_edges(bm, edges=edges, cuts={cuts_i}, edge_perc=perc, use_grid_fill=False)
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add loop cuts", is_error=True)
        return _make_tool_result(f"Added {cuts_i} loop cuts on {name}", is_error=False)

    def _tool_bevel_edges(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        width = args.get("width")
        segments = args.get("segments")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            width_f = float(width)
        except Exception:
            raise ToolError("width must be a number", code=-32602)
        if width_f <= 0:
            raise ToolError("width must be > 0", code=-32602)
        try:
            segments_i = int(segments)
        except Exception:
            raise ToolError("segments must be an integer", code=-32602)
        if segments_i < 1 or segments_i > 12:
            raise ToolError("segments must be between 1 and 12", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
edges = bm.edges[:]
if not edges:
    raise ValueError("Mesh has no edges")
bmesh.ops.bevel(bm, geom=edges, offset={width_f}, offset_type='OFFSET', segments={segments_i}, profile=0.5, clamp_overlap=True)
bm.to_mesh(mesh)
bm.free()
mesh.update()
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to bevel edges", is_error=True)
        return _make_tool_result(f"Beveled edges on {name}", is_error=False)

    def _tool_merge_by_distance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        distance = args.get("distance", 0.0001)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        try:
            distance_f = float(distance)
        except Exception:
            raise ToolError("distance must be a number", code=-32602)
        if distance_f < 0:
            raise ToolError("distance must be >= 0", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
distance = {distance_f}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.merge_by_distance(distance=distance)
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to merge by distance", is_error=True)
        return _make_tool_result(f"Merged {name} by distance {distance_f}", is_error=False)

    def _tool_recalc_normals(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        inside = args.get("inside", False)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(inside, bool):
            raise ToolError("inside must be a boolean", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
inside = {inside}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=inside)
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to recalc normals", is_error=True)
        side = "inside" if inside else "outside"
        return _make_tool_result(f"Recalculated {name} normals ({side})", is_error=False)

    def _tool_triangulate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        method = (args.get("method") or "BEAUTY").upper()
        valid_methods = {"BEAUTY", "FIXED", "FIXED_ALTERNATE", "SHORTEST_DIAGONAL"}
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if method not in valid_methods:
            raise ToolError("method must be BEAUTY, FIXED, FIXED_ALTERNATE, or SHORTEST_DIAGONAL", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
method = {json.dumps(method)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris(quad_method=method, ngon_method='BEAUTY')
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to triangulate", is_error=True)
        return _make_tool_result(f"Triangulated {name} with {method}", is_error=False)

    def _tool_uv_unwrap(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        method = (args.get("method") or "ANGLE_BASED").upper()
        margin = args.get("margin", 0.02)
        mark_seams = args.get("mark_seams", True)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if method not in ("ANGLE_BASED", "CONFORMAL"):
            raise ToolError("method must be ANGLE_BASED or CONFORMAL", code=-32602)
        try:
            margin_f = float(margin)
        except Exception:
            raise ToolError("margin must be a number", code=-32602)
        if margin_f < 0.0 or margin_f > 1.0:
            raise ToolError("margin must be between 0 and 1", code=-32602)
        if not isinstance(mark_seams, bool):
            raise ToolError("mark_seams must be a boolean", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
method = {json.dumps(method)}
margin = {margin_f}
mark_seams = {mark_seams}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if obj.type != 'MESH':
    raise ValueError("Object is not a mesh")
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if mark_seams:
        bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.uv.unwrap(method=method, margin=margin)
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to unwrap UVs", is_error=True)
        return _make_tool_result(f"Unwrapped {name} with {method} (margin={margin_f})", is_error=False)

    def _tool_add_modifier(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        mod_type = args.get("type")
        settings = args.get("settings") or {}
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(mod_type, str):
            raise ToolError("type must be a string", code=-32602)
        if settings is not None and not isinstance(settings, dict):
            raise ToolError("settings must be an object", code=-32602)
        type_map = {
            "mirror": "MIRROR",
            "array": "ARRAY",
            "solidify": "SOLIDIFY",
            "bevel": "BEVEL",
            "subdivision": "SUBSURF",
            "boolean": "BOOLEAN",
            "decimate": "DECIMATE",
            "weld": "WELD",
            "triangulate": "TRIANGULATE",
        }
        if mod_type not in type_map:
            raise ToolError("type must be one of mirror,array,solidify,bevel,subdivision,boolean,decimate,weld,triangulate", code=-32602)
        clean_settings: Dict[str, Any] = {}
        if mod_type == "mirror":
            for axis_key in ("use_axis_x", "use_axis_y", "use_axis_z"):
                val = settings.get(axis_key)
                if val is not None:
                    if not isinstance(val, bool):
                        raise ToolError(f"{axis_key} must be a boolean", code=-32602)
                    clean_settings[axis_key] = val
        if mod_type == "array":
            count = settings.get("count")
            if count is not None:
                try:
                    count_i = int(count)
                except Exception:
                    raise ToolError("count must be an integer", code=-32602)
                clean_settings["count"] = count_i
            rel = settings.get("relative_offset")
            if rel is not None:
                if not isinstance(rel, list) or len(rel) != 3:
                    raise ToolError("relative_offset must be an array of 3 numbers", code=-32602)
                try:
                    rel_vals = [float(v) for v in rel]
                except Exception:
                    raise ToolError("relative_offset must be an array of 3 numbers", code=-32602)
                clean_settings["relative_offset"] = rel_vals
        if mod_type == "solidify":
            thickness = settings.get("thickness")
            if thickness is not None:
                try:
                    clean_settings["thickness"] = float(thickness)
                except Exception:
                    raise ToolError("thickness must be a number", code=-32602)
        if mod_type == "bevel":
            width = settings.get("width")
            segments = settings.get("segments")
            if width is not None:
                try:
                    clean_settings["width"] = float(width)
                except Exception:
                    raise ToolError("width must be a number", code=-32602)
            if segments is not None:
                try:
                    segments_i = int(segments)
                except Exception:
                    raise ToolError("segments must be an integer", code=-32602)
                clean_settings["segments"] = segments_i
        if mod_type == "subdivision":
            levels = settings.get("levels")
            if levels is not None:
                try:
                    clean_settings["levels"] = int(levels)
                except Exception:
                    raise ToolError("levels must be an integer", code=-32602)
        if mod_type == "boolean":
            cutter = settings.get("cutter")
            operation = settings.get("operation", "union")
            if cutter is not None and not isinstance(cutter, str):
                raise ToolError("cutter must be a string", code=-32602)
            if operation not in ("union", "difference", "intersect"):
                raise ToolError("operation must be union, difference, or intersect", code=-32602)
            clean_settings["cutter"] = cutter
            clean_settings["operation"] = operation
        if mod_type == "decimate":
            ratio = settings.get("ratio")
            if ratio is not None:
                try:
                    r = float(ratio)
                except Exception:
                    raise ToolError("ratio must be a number", code=-32602)
                clean_settings["ratio"] = r
        if mod_type == "weld":
            merge_threshold = settings.get("merge_threshold")
            if merge_threshold is not None:
                try:
                    clean_settings["merge_threshold"] = float(merge_threshold)
                except Exception:
                    raise ToolError("merge_threshold must be a number", code=-32602)
        if mod_type == "triangulate":
            quad_method = settings.get("quad_method")
            ngon_method = settings.get("ngon_method")
            quad_valid = {"BEAUTY", "FIXED", "FIXED_ALTERNATE", "SHORTEST_DIAGONAL"}
            ngon_valid = {"BEAUTY", "FIXED", "FIXED_ALTERNATE", "SHORTEST_DIAGONAL"}
            if quad_method is not None:
                if not isinstance(quad_method, str) or quad_method.upper() not in quad_valid:
                    raise ToolError("quad_method must be a valid triangulate method", code=-32602)
                clean_settings["quad_method"] = quad_method.upper()
            if ngon_method is not None:
                if not isinstance(ngon_method, str) or ngon_method.upper() not in ngon_valid:
                    raise ToolError("ngon_method must be a valid triangulate method", code=-32602)
                clean_settings["ngon_method"] = ngon_method.upper()
        mod_bpy_type = type_map[mod_type]
        code = f"""
import bpy
obj = bpy.data.objects.get({json.dumps(name)})
if obj is None:
    raise ValueError("Object not found")
mod = obj.modifiers.new(name={json.dumps(mod_type + "_mod")}, type={json.dumps(mod_bpy_type)})
settings = {json.dumps(clean_settings)}
if {json.dumps(mod_type)} == "mirror":
    for key, val in settings.items():
        setattr(mod, key, val)
elif {json.dumps(mod_type)} == "array":
    if "count" in settings:
        mod.count = settings["count"]
    if "relative_offset" in settings:
        mod.use_relative_offset = True
        mod.relative_offset_displace = tuple(settings["relative_offset"])
elif {json.dumps(mod_type)} == "solidify":
    if "thickness" in settings:
        mod.thickness = settings["thickness"]
elif {json.dumps(mod_type)} == "bevel":
    if "width" in settings:
        mod.width = settings["width"]
    if "segments" in settings:
        mod.segments = settings["segments"]
elif {json.dumps(mod_type)} == "subdivision":
    if "levels" in settings:
        mod.levels = settings["levels"]
elif {json.dumps(mod_type)} == "boolean":
    if "cutter" in settings and settings["cutter"]:
        cutter_obj = bpy.data.objects.get(settings["cutter"])
        if cutter_obj is None:
            raise ValueError("Cutter object not found")
        mod.object = cutter_obj
    op_map = {{"union": "UNION", "difference": "DIFFERENCE", "intersect": "INTERSECT"}}
    mod.operation = op_map.get(settings.get("operation", "union"), "UNION")
elif {json.dumps(mod_type)} == "decimate":
    if "ratio" in settings:
        mod.ratio = settings["ratio"]
elif {json.dumps(mod_type)} == "weld":
    if "merge_threshold" in settings:
        mod.merge_threshold = settings["merge_threshold"]
elif {json.dumps(mod_type)} == "triangulate":
    if "quad_method" in settings:
        mod.quad_method = settings["quad_method"]
    if "ngon_method" in settings:
        mod.ngon_method = settings["ngon_method"]
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add modifier", is_error=True)
        return _make_tool_result(f"Added {mod_type} modifier to {name}", is_error=False)

    def _tool_apply_modifier(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        modifier = args.get("modifier")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(modifier, str):
            raise ToolError("modifier must be a string", code=-32602)
        code = f"""
import bpy
obj = bpy.data.objects.get({json.dumps(name)})
if obj is None:
    raise ValueError("Object not found")
mod = obj.modifiers.get({json.dumps(modifier)})
if mod is None:
    raise ValueError("Modifier not found")
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier=mod.name)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to apply modifier", is_error=True)
        return _make_tool_result(f"Applied modifier {modifier} on {name}", is_error=False)

    def _tool_boolean(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        cutter = args.get("cutter")
        operation = args.get("operation")
        apply = args.get("apply", True)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(cutter, str):
            raise ToolError("cutter must be a string", code=-32602)
        if operation not in ("union", "difference", "intersect"):
            raise ToolError("operation must be union, difference, or intersect", code=-32602)
        if not isinstance(apply, bool):
            raise ToolError("apply must be a boolean", code=-32602)
        code = f"""
import bpy
obj = bpy.data.objects.get({json.dumps(name)})
if obj is None:
    raise ValueError("Object not found")
cutter_obj = bpy.data.objects.get({json.dumps(cutter)})
if cutter_obj is None:
    raise ValueError("Cutter object not found")
mod = obj.modifiers.new(name="Boolean_auto", type="BOOLEAN")
op_map = {{"union": "UNION", "difference": "DIFFERENCE", "intersect": "INTERSECT"}}
mod.operation = op_map[{json.dumps(operation)}]
mod.object = cutter_obj
"""
        if apply:
            code += """
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier=mod.name)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to perform boolean", is_error=True)
        return _make_tool_result(f"Boolean {operation} on {name} with {cutter}", is_error=False)

    def _validate_rgba(self, value: Any, *, name: str) -> Optional[List[float]]:
        if value is None:
            return None
        if not isinstance(value, list) or len(value) != 4:
            raise ToolError(f"{name} must be an array of 4 numbers (RGBA)", code=-32602)
        out: List[float] = []
        for v in value:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                raise ToolError(f"{name} must be an array of 4 numbers (RGBA)", code=-32602)
        return out

    def _tool_parent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        child = args.get("child")
        parent = args.get("parent")
        keep_transform = args.get("keep_transform", True)
        if not isinstance(child, str):
            raise ToolError("child must be a string", code=-32602)
        if not isinstance(parent, str):
            raise ToolError("parent must be a string", code=-32602)
        if not isinstance(keep_transform, bool):
            raise ToolError("keep_transform must be a boolean", code=-32602)
        code = f"""
import bpy
child_name = {json.dumps(child)}
parent_name = {json.dumps(parent)}
keep_transform = {keep_transform}
child_obj = bpy.data.objects.get(child_name)
if child_obj is None:
    raise ValueError("Child not found")
parent_obj = bpy.data.objects.get(parent_name)
if parent_obj is None:
    raise ValueError("Parent not found")
current_matrix = child_obj.matrix_world.copy()
child_obj.parent = parent_obj
if keep_transform:
    child_obj.matrix_world = current_matrix
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to parent object", is_error=True)
        return _make_tool_result(f"Parented {child} to {parent}", is_error=False)

    def _tool_move_to_collection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        collection = args.get("collection")
        create = args.get("create", True)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if not isinstance(collection, str):
            raise ToolError("collection must be a string", code=-32602)
        if not isinstance(create, bool):
            raise ToolError("create must be a boolean", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
collection_name = {json.dumps(collection)}
create = {create}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
col = bpy.data.collections.get(collection_name)
if col is None:
    if not create:
        raise ValueError("Collection not found")
    col = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(col)
if obj.name not in col.objects:
    col.objects.link(obj)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to move to collection", is_error=True)
        return _make_tool_result(f"Moved {name} to collection {collection}", is_error=False)

    def _tool_align_to_axis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        axis = (args.get("axis") or "").upper()
        mode = (args.get("mode") or "ROTATION_ZERO").upper()
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if axis not in ("X", "Y", "Z"):
            raise ToolError("axis must be X, Y, or Z", code=-32602)
        if mode not in ("ROTATION_ZERO", "LOCATION_ZERO"):
            raise ToolError("mode must be ROTATION_ZERO or LOCATION_ZERO", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
axis = {json.dumps(axis)}
mode = {json.dumps(mode)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if mode == "ROTATION_ZERO":
    obj.rotation_euler = (0.0, 0.0, 0.0)
else:
    loc = list(obj.location)
    if axis == "X":
        loc[0] = 0.0
    elif axis == "Y":
        loc[1] = 0.0
    elif axis == "Z":
        loc[2] = 0.0
    obj.location = tuple(loc)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to align object", is_error=True)
        return _make_tool_result(f"Aligned {name} ({mode} {axis})", is_error=False)


    def _tool_create_material(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        base_color = self._validate_rgba(args.get("base_color"), name="base_color")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if base_color is None:
            base_color = [0.8, 0.8, 0.8, 1.0]
        code = f"""
import bpy
name = {json.dumps(name)}
mat = bpy.data.materials.new(name=name)
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()
bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Base Color'].default_value = ({base_color[0]}, {base_color[1]}, {base_color[2]}, {base_color[3]})
output = nodes.new(type='ShaderNodeOutputMaterial')
output.location = (300, 0)
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to create material", is_error=True)
        return _make_tool_result(f"Created material {name}", is_error=False)

    def _tool_list_materials(self, _: Dict[str, Any]) -> Dict[str, Any]:
        code = """
import bpy
result = [mat.name for mat in bpy.data.materials]
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to list materials", is_error=True)
        mats = data.get("result") or []
        if isinstance(mats, list) and mats:
            text = ", ".join(mats)
        else:
            text = "no materials"
        return _make_tool_result(text, is_error=False)

    def _tool_list_material_slots(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if not hasattr(obj.data, "materials"):
    raise ValueError("Object has no material slots")
slots = []
for idx, mat in enumerate(obj.data.materials):
    slots.append({{"index": idx, "material": mat.name if mat else None}})
result = slots
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to list material slots", is_error=True)
        slots = data.get("result") or []
        if isinstance(slots, list) and slots:
            parts = [f"{item.get('index')}: {item.get('material')}" for item in slots if isinstance(item, dict)]
            text = ", ".join(parts) if parts else "no slots"
        else:
            text = "no slots"
        return _make_tool_result(text, is_error=False)

    def _tool_export(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        fmt = args.get("format")
        selected_only = args.get("selected_only", False)
        if not isinstance(path, str):
            raise ToolError("path must be a string", code=-32602)
        if not isinstance(fmt, str):
            raise ToolError("format must be a string", code=-32602)
        if not isinstance(selected_only, bool):
            raise ToolError("selected_only must be a boolean", code=-32602)
        if fmt not in ("fbx", "gltf"):
            raise ToolError("format must be 'fbx' or 'gltf'", code=-32602)
        if fmt == "fbx":
            code = f"""
import bpy
path = {json.dumps(path)}
bpy.ops.export_scene.fbx(filepath=path, use_selection={selected_only})
"""
        else:
            code = f"""
import bpy
path = {json.dumps(path)}
bpy.ops.export_scene.gltf(filepath=path, use_selection={selected_only})
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=10.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to export", is_error=True)
        return _make_tool_result(f"Exported to {path} as {fmt}", is_error=False)

    def _tool_rename_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        old_name = args.get("old_name")
        new_name = args.get("new_name")
        if not isinstance(old_name, str):
            raise ToolError("old_name must be a string", code=-32602)
        if not isinstance(new_name, str):
            raise ToolError("new_name must be a string", code=-32602)
        code = f"""
import bpy
old_name = {json.dumps(old_name)}
new_name = {json.dumps(new_name)}
obj = bpy.data.objects.get(old_name)
if obj is None:
    raise ValueError(f"Object {{old_name}} not found")
obj.name = new_name
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to rename object", is_error=True)
        return _make_tool_result(f"Renamed {old_name} to {new_name}", is_error=False)
