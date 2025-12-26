import json
import os
import re
import sys
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

from .tools_packs import register_all

BRIDGE_URL = os.environ.get("BLENDER_MCP_BRIDGE_URL") or os.environ.get("NEW_MCP_BRIDGE_URL", "http://127.0.0.1:8765")
SERVER_VERSION = "0.1.0"
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
DEBUG_EXEC_ENABLED = os.environ.get("BLENDER_MCP_DEBUG_EXEC") == "1" or os.environ.get("NEW_MCP_DEBUG_EXEC") == "1"
ROOT_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT_DIR / "runs"
RUNS_FILE = RUNS_DIR / "actions.jsonl"
REQUESTS_FILE = RUNS_DIR / "requests.jsonl"
TOOL_REQUEST_DIR = Path(os.environ.get("TOOL_REQUEST_DATA_DIR") or (ROOT_DIR / "data"))
TOOL_REQUEST_FILE = TOOL_REQUEST_DIR / "tool_requests.jsonl"
TOOL_REQUEST_UPDATES_FILE = TOOL_REQUEST_DIR / "tool_requests_updates.jsonl"


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


class ToolRequestStore:
    _ENUMS = {
        "source": {"claude", "codex", "manual"},
        "type": {"bug_fix", "new_tool", "enhancement", "deprecation"},
        "priority": {"critical", "high", "medium", "low"},
        "domain": {
            "mesh",
            "object",
            "selection",
            "material",
            "modifier",
            "scene",
            "render",
            "nodes",
            "uv",
            "anim",
            "io",
            "system",
        },
        "status": {"pending", "triaged", "accepted", "implemented", "released", "rejected", "needs_info"},
    }
    _ESTIMATED_EFFORT = {"trivial", "small", "medium", "large"}

    def __init__(self) -> None:
        self.requests: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _normalize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(entry)
        created_at = normalized.get("created_at")
        try:
            normalized["revision"] = int(normalized.get("revision", 1))
        except Exception:
            normalized["revision"] = 1
        normalized.setdefault("updated_at", created_at)
        for list_field in ("depends_on", "blocks"):
            val = normalized.get(list_field)
            if not isinstance(val, list):
                normalized[list_field] = []
        return normalized

    def _merge_value(self, current: Any, new_value: Any, *, mode: str, list_mode: str) -> Any:
        if mode == "replace" or new_value is None:
            return new_value
        if isinstance(current, dict) and isinstance(new_value, dict):
            merged = dict(current)
            for key, val in new_value.items():
                merged[key] = self._merge_value(current.get(key), val, mode=mode, list_mode=list_mode)
            return merged
        if isinstance(current, list) and isinstance(new_value, list):
            if list_mode == "replace":
                return new_value
            merged_list = list(current)
            for item in new_value:
                if item not in merged_list:
                    merged_list.append(item)
            return merged_list
        return new_value

    def _merge_payload(self, base: Dict[str, Any], changes: Dict[str, Any], *, mode: str, list_mode: str) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in changes.items():
            merged[key] = self._merge_value(base.get(key), value, mode=mode, list_mode=list_mode)
        return merged

    def _validate_examples(self, examples: Any) -> Optional[List[Any]]:
        if examples is None:
            return None
        if not isinstance(examples, list):
            raise ToolError("examples must be an array", code=-32602)
        for ex in examples:
            if not isinstance(ex, (str, dict)):
                raise ToolError("examples must contain strings or objects", code=-32602)
        return examples

    def _load_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not path.exists():
            return items
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    warnings.warn(f"tool-request: skipping corrupted line in {path.name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"tool-request: failed reading {path}: {exc}")
        return items

    def _load(self) -> None:
        TOOL_REQUEST_DIR.mkdir(parents=True, exist_ok=True)
        base_items = self._load_jsonl(TOOL_REQUEST_FILE)
        updates = self._load_jsonl(TOOL_REQUEST_UPDATES_FILE)
        for item in base_items:
            if isinstance(item, dict) and "id" in item:
                self.requests[item["id"]] = self._normalize_entry(item)
        for upd in updates:
            self._apply_update_record(upd)

    def _apply_update_record(self, record: Dict[str, Any]) -> None:
        if not isinstance(record, dict):
            return
        req_id = record.get("id")
        changes = record.get("changes") or {}
        if record.get("delete") is True and isinstance(req_id, str):
            self.requests.pop(req_id, None)
            return
        if not isinstance(req_id, str) or req_id not in self.requests or not isinstance(changes, dict):
            return
        mode = record.get("mode") or "replace"
        list_mode = record.get("list_mode") or ("replace" if mode == "replace" else "append")
        current = self.requests[req_id].copy()
        merged = self._merge_payload(current, changes, mode=mode, list_mode=list_mode)
        merged["updated_at"] = record.get("ts") or datetime.now(timezone.utc).isoformat()
        merged["revision"] = int(current.get("revision") or 1) + 1
        if record.get("updated_by") is not None:
            merged["updated_by"] = record.get("updated_by")
        self.requests[req_id] = self._normalize_entry(merged)

    def _write_jsonl(self, path: Path, entry: Dict[str, Any]) -> None:
        TOOL_REQUEST_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _validate_new(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key in ("need", "why", "session"):
            if not isinstance(payload.get(key), str):
                raise ToolError(f"{key} must be a string", code=-32602)
            out[key] = payload[key]
        def _enum_field(name: str, default: str, soft: bool = False) -> None:
            raw_val = payload.get(name, default)
            if raw_val is None:
                return
            if not isinstance(raw_val, str):
                raise ToolError(f"{name} must be a string", code=-32602)
            val = raw_val.lower()
            allowed = self._ENUMS[name]
            if not soft and val not in allowed:
                raise ToolError(f"{name} must be one of {', '.join(sorted(allowed))}", code=-32602)
            out[name] = val

        _enum_field("source", "manual")
        _enum_field("type", "enhancement")
        _enum_field("priority", "medium")
        _enum_field("domain", "system", soft=True)
        _enum_field("status", "pending")
        examples = self._validate_examples(payload.get("examples"))
        if examples is not None:
            out["examples"] = examples
        for optional_str in (
            "related_tool",
            "resolution_note",
            "owner",
            "proposed_tool_name",
            "assigned_to",
            "implementation_hint",
            "updated_by",
        ):
            val = payload.get(optional_str)
            if val is not None and not isinstance(val, str):
                raise ToolError(f"{optional_str} must be a string", code=-32602)
            if val is not None:
                out[optional_str] = val
        tags = payload.get("tags")
        if tags is not None:
            if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
                raise ToolError("tags must be an array of strings", code=-32602)
            out["tags"] = tags
        for list_field in ("depends_on", "blocks", "acceptance_criteria"):
            val = payload.get(list_field)
            if val is None:
                continue
            if not isinstance(val, list) or any(not isinstance(v, str) for v in val):
                raise ToolError(f"{list_field} must be an array of strings", code=-32602)
            out[list_field] = val
        failing_call = payload.get("failing_call")
        if failing_call is not None:
            if not isinstance(failing_call, dict) or not isinstance(failing_call.get("name"), str):
                raise ToolError("failing_call must be an object with name", code=-32602)
            out["failing_call"] = failing_call
        for obj_field in ("blender", "context", "repro", "error", "api_probe", "proposed_params_schema", "return_schema"):
            val = payload.get(obj_field)
            if val is not None and not isinstance(val, dict):
                raise ToolError(f"{obj_field} must be an object", code=-32602)
            if val is not None:
                out[obj_field] = val
        effort = payload.get("estimated_effort")
        if effort is not None:
            if not isinstance(effort, str) or effort.lower() not in self._ESTIMATED_EFFORT:
                raise ToolError("estimated_effort must be one of trivial, small, medium, large", code=-32602)
            out["estimated_effort"] = effort.lower()
        return out

    def _validate_update(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(changes, dict):
            raise ToolError("changes must be an object", code=-32602)
        clean: Dict[str, Any] = {}

        def _enum_field(name: str, allowed: set[str], soft: bool = False) -> None:
            if name not in changes:
                return
            val = changes[name]
            if val is None:
                clean[name] = None
                return
            if not isinstance(val, str):
                raise ToolError(f"{name} must be a string", code=-32602)
            val_norm = val.lower()
            if not soft and val_norm not in allowed:
                raise ToolError(f"{name} must be one of {', '.join(sorted(allowed))}", code=-32602)
            clean[name] = val_norm

        _enum_field("status", self._ENUMS["status"])
        _enum_field("priority", self._ENUMS["priority"])
        _enum_field("type", self._ENUMS["type"])
        _enum_field("source", self._ENUMS["source"])
        _enum_field("domain", self._ENUMS["domain"], soft=True)
        for text_field in (
            "need",
            "why",
            "owner",
            "resolution_note",
            "proposed_tool_name",
            "related_tool",
            "assigned_to",
            "implementation_hint",
            "updated_by",
        ):
            if text_field in changes:
                val = changes[text_field]
                if val is not None and not isinstance(val, str):
                    raise ToolError(f"{text_field} must be a string", code=-32602)
                clean[text_field] = val
        if "tags" in changes:
            tags = changes["tags"]
            if tags is not None and (not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)):
                raise ToolError("tags must be array of strings", code=-32602)
            clean["tags"] = tags
        for list_field in ("depends_on", "blocks", "acceptance_criteria"):
            if list_field in changes:
                val = changes[list_field]
                if val is not None and (not isinstance(val, list) or any(not isinstance(v, str) for v in val)):
                    raise ToolError(f"{list_field} must be an array of strings", code=-32602)
                clean[list_field] = val
        if "examples" in changes:
            clean["examples"] = self._validate_examples(changes.get("examples"))
        for obj_field in ("blender", "context", "repro", "error", "api_probe", "proposed_params_schema", "return_schema"):
            if obj_field in changes:
                val = changes[obj_field]
                if val is not None and not isinstance(val, dict):
                    raise ToolError(f"{obj_field} must be an object", code=-32602)
                clean[obj_field] = val
        if "failing_call" in changes:
            val = changes["failing_call"]
            if val is not None and (not isinstance(val, dict) or not isinstance(val.get("name"), str)):
                raise ToolError("failing_call must be an object with name", code=-32602)
            clean["failing_call"] = val
        if "estimated_effort" in changes:
            val = changes["estimated_effort"]
            if val is not None:
                if not isinstance(val, str) or val.lower() not in self._ESTIMATED_EFFORT:
                    raise ToolError("estimated_effort must be one of trivial, small, medium, large", code=-32602)
                clean["estimated_effort"] = val.lower()
            else:
                clean["estimated_effort"] = None
        return clean

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        clean = self._validate_new(payload)
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "schema_version": 2,
            "id": str(uuid.uuid4()),
            "created_at": now,
            "updated_at": now,
            "revision": 1,
            **clean,
        }
        entry.setdefault("depends_on", [])
        entry.setdefault("blocks", [])
        self._write_jsonl(TOOL_REQUEST_FILE, entry)
        self.requests[entry["id"]] = self._normalize_entry(entry)
        return entry

    def list(
        self, filters: Dict[str, Any], limit: int = 50, cursor: Optional[str] = None, next_page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        items = list(self.requests.values())
        filters = filters or {}
        status_filter = filters.get("status")
        if isinstance(status_filter, list):
            items = [it for it in items if it.get("status") in status_filter]
        elif isinstance(status_filter, str):
            items = [it for it in items if it.get("status") == status_filter]
        priority_filter = filters.get("priority")
        if isinstance(priority_filter, list):
            items = [it for it in items if it.get("priority") in priority_filter]
        elif isinstance(priority_filter, str):
            items = [it for it in items if it.get("priority") == priority_filter]
        for key in ("domain", "type", "session"):
            val = filters.get(key)
            if isinstance(val, str) and val:
                items = [it for it in items if str(it.get(key) or "").lower() == val.lower()]
        if filters.get("has_api_probe") is True:
            items = [it for it in items if isinstance(it.get("api_probe"), dict)]
        elif filters.get("has_api_probe") is False:
            items = [it for it in items if not isinstance(it.get("api_probe"), dict)]
        if filters.get("has_params_schema") is True:
            items = [it for it in items if isinstance(it.get("proposed_params_schema"), dict)]
        elif filters.get("has_params_schema") is False:
            items = [it for it in items if not isinstance(it.get("proposed_params_schema"), dict)]
        text = filters.get("q") or filters.get("text")
        if text:
            low = text.lower()
            items = [
                it
                for it in items
                if low
                in (
                    (it.get("need", "") or "") + (it.get("why", "") or "") + " ".join(it.get("tags") or [])
                ).lower()
            ]
        items.sort(key=lambda i: (i.get("created_at", ""), i.get("id", "")))
        start = 0
        token = next_page_token or cursor
        if token:
            try:
                start = int(token)
            except Exception:
                start = 0
        sliced = items[start : start + limit]
        next_cursor = None
        if start + limit < len(items):
            next_cursor = str(start + limit)
        summaries = [
            {
                "id": it.get("id"),
                "created_at": it.get("created_at"),
                "updated_at": it.get("updated_at"),
                "need": it.get("need"),
                "type": it.get("type"),
                "priority": it.get("priority"),
                "domain": it.get("domain"),
                "status": it.get("status"),
                "session": it.get("session"),
                "revision": it.get("revision"),
            }
            for it in sliced
        ]
        return {"items": summaries, "cursor": next_cursor, "next_page_token": next_cursor}

    def get(self, req_id: str) -> Optional[Dict[str, Any]]:
        return self.requests.get(req_id)

    def update(self, req_id: str, changes: Dict[str, Any], *, mode: str = "merge", list_mode: str = "append") -> Dict[str, Any]:
        if req_id not in self.requests:
            raise ToolError("request not found", code=-32602)
        if mode not in {"merge", "replace"}:
            raise ToolError("mode must be merge or replace", code=-32602)
        if list_mode not in {"append", "replace"}:
            raise ToolError("list_mode must be append or replace", code=-32602)
        clean = self._validate_update(changes)
        if not clean:
            raise ToolError("no changes provided", code=-32602)
        current = self.requests[req_id].copy()
        merged = self._merge_payload(current, clean, mode=mode, list_mode=list_mode)
        merged["revision"] = int(current.get("revision") or 1) + 1
        merged["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.requests[req_id] = self._normalize_entry(merged)
        record: Dict[str, Any] = {
            "id": req_id,
            "ts": merged["updated_at"],
            "changes": clean,
            "mode": mode,
            "list_mode": list_mode,
        }
        if "updated_by" in clean:
            record["updated_by"] = clean["updated_by"]
        self._write_jsonl(TOOL_REQUEST_UPDATES_FILE, record)
        return self.requests[req_id]

    def delete(self, req_id: str) -> Dict[str, Any]:
        if req_id not in self.requests:
            raise ToolError("request not found", code=-32602)
        self.requests.pop(req_id, None)
        record = {"id": req_id, "ts": datetime.now(timezone.utc).isoformat(), "delete": True}
        self._write_jsonl(TOOL_REQUEST_UPDATES_FILE, record)
        return {"ok": True, "deleted_id": req_id}

    def purge(self, *, statuses: Optional[List[str]] = None, older_than_days: Optional[int] = None) -> List[str]:
        now = datetime.now(timezone.utc)
        deleted: List[str] = []
        for req_id, item in list(self.requests.items()):
            status_ok = True
            if statuses:
                status_ok = item.get("status") in statuses
            age_ok = True
            if older_than_days is not None:
                created_at = item.get("created_at")
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    age_ok = (now - created_dt).days >= older_than_days
                except Exception:
                    age_ok = False
            if status_ok and age_ok:
                self.delete(req_id)
                deleted.append(req_id)
        return deleted

    def bulk_update(
        self, req_ids: List[str], changes: Dict[str, Any], *, mode: str = "merge", list_mode: str = "append"
    ) -> List[Dict[str, Any]]:
        if not isinstance(req_ids, list) or any(not isinstance(rid, str) for rid in req_ids):
            raise ToolError("ids must be an array of strings", code=-32602)
        if not isinstance(changes, dict):
            raise ToolError("patch must be an object", code=-32602)
        updated = []
        for rid in req_ids:
            updated.append(self.update(rid, changes, mode=mode, list_mode=list_mode))
        return updated

    def bulk_delete(self, req_ids: List[str]) -> List[str]:
        if not isinstance(req_ids, list) or any(not isinstance(rid, str) for rid in req_ids):
            raise ToolError("ids must be an array of strings", code=-32602)
        deleted: List[str] = []
        for rid in req_ids:
            self.delete(rid)
            deleted.append(rid)
        return deleted


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
        self._tool_request_store = ToolRequestStore()

    def _register(
        self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        if not NAME_PATTERN.match(name):
            raise ValueError(f"Invalid tool name: {name}")
        self._tools[name] = Tool(name=name, description=description, input_schema=input_schema, handler=handler)

    def _register_defaults(self) -> None:
        register_all(self, _bridge_request, _make_tool_result, ToolError)

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
        def _coerce_location(val: Any) -> List[float]:
            if val is None:
                return [0.0, 0.0, 0.0]
            if isinstance(val, (list, tuple)) and len(val) == 3:
                seq = val
            elif isinstance(val, dict) and {"x", "y", "z"} <= set(val.keys()):
                seq = [val.get("x"), val.get("y"), val.get("z")]
            elif isinstance(val, str):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if len(parts) != 3:
                    raise ToolError("location string must be 'x,y,z'", code=-32602)
                seq = parts
            else:
                raise ToolError("location must be an array of 3 numbers", code=-32602)
            out: List[float] = []
            for item in seq:
                try:
                    out.append(float(item))
                except Exception:
                    raise ToolError("location must be an array of 3 numbers", code=-32602)
            if len(out) != 3:
                raise ToolError("location must be an array of 3 numbers", code=-32602)
            return out
        location = _coerce_location(args.get("location"))
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
        radius_arg = args.get("radius")
        diameter = args.get("diameter")
        radius = radius_arg if radius_arg is not None else None
        if radius is None and diameter is not None:
            try:
                diameter_f = float(diameter)
            except Exception:
                raise ToolError("diameter must be a number", code=-32602)
            if diameter_f <= 0:
                raise ToolError("diameter must be > 0", code=-32602)
            radius = diameter_f / 2.0
        if radius is None:
            radius = 1.0
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        name = args.get("name") or "Sphere"
        if sphere_type not in ("uv", "ico"):
            raise ToolError("type must be 'uv' or 'ico'", code=-32602)
        try:
            radius_f = float(radius)
        except Exception:
            raise ToolError("radius must be a number", code=-32602)
        if radius_f <= 0:
            raise ToolError("radius must be > 0", code=-32602)
        if sphere_type == "uv":
            try:
                seg_i = int(segments)
                ring_i = int(rings)
            except Exception:
                raise ToolError("segments and rings must be integers", code=-32602)
            code = f"""
import bpy
bpy.ops.mesh.primitive_uv_sphere_add(radius={radius_f}, segments={seg_i}, ring_count={ring_i}, location=({location[0]}, {location[1]}, {location[2]}))
obj = bpy.context.active_object
if obj is not None:
    obj.name = {json.dumps(name)}
"""
        else:
            try:
                sub_i = int(subdivisions)
            except Exception:
                raise ToolError("subdivisions must be an integer", code=-32602)
            code = f"""
import bpy
bpy.ops.mesh.primitive_ico_sphere_add(radius={radius_f}, subdivisions={sub_i}, location=({location[0]}, {location[1]}, {location[2]}))
obj = bpy.context.active_object
if obj is not None:
    obj.name = {json.dumps(name)}
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
import bpy
bpy.ops.mesh.primitive_torus_add(major_radius={maj_r}, minor_radius={min_r}, major_segments={maj_seg}, minor_segments={min_seg}, location=({location[0]}, {location[1]}, {location[2]}))
obj = bpy.context.active_object
if obj is not None:
    obj.name = {json.dumps(name)}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to add torus", is_error=True)
        return _make_tool_result("Added torus", is_error=False)

    def _tool_create_empty(self, args: Dict[str, Any]) -> Dict[str, Any]:
        empty_type = (args.get("type") or "PLAIN_AXES").upper()
        name = args.get("name") or "Empty"
        size = args.get("size", 1.0)
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        rotation = self._validate_vector(args.get("rotation"), name="rotation") or [0.0, 0.0, 0.0]
        valid_types = {"PLAIN_AXES", "ARROWS", "SINGLE_ARROW", "CIRCLE", "CUBE", "SPHERE"}
        if empty_type not in valid_types:
            raise ToolError("type must be one of PLAIN_AXES, ARROWS, SINGLE_ARROW, CIRCLE, CUBE, SPHERE", code=-32602)
        try:
            size_f = float(size)
        except Exception:
            raise ToolError("size must be a number", code=-32602)
        if size_f <= 0:
            raise ToolError("size must be > 0", code=-32602)
        code = f"""
import bpy, math
etype = {json.dumps(empty_type)}
name = {json.dumps(name)}
loc = ({location[0]}, {location[1]}, {location[2]})
rot = ({rotation[0]}, {rotation[1]}, {rotation[2]})
obj = bpy.data.objects.new(name, None)
obj.empty_display_type = etype
obj.empty_display_size = {size_f}
obj.location = loc
obj.rotation_euler = tuple(math.radians(v) for v in rot)
bpy.context.scene.collection.objects.link(obj)
result = {{
    "name": obj.name,
    "type": etype,
    "location": [obj.location.x, obj.location.y, obj.location.z],
    "rotation": [math.degrees(v) for v in obj.rotation_euler],
    "size": obj.empty_display_size,
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to create empty", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            text = f"Created empty {info.get('name')} ({info.get('type')})"
        else:
            text = f"Created empty {name} ({empty_type})"
        return _make_tool_result(text, is_error=False)

    def _tool_create_curve(self, args: Dict[str, Any]) -> Dict[str, Any]:
        curve_type = (args.get("type") or "BEZIER").upper()
        name = args.get("name") or "Curve"
        location = self._validate_vector(args.get("location"), name="location") or [0.0, 0.0, 0.0]
        radius = args.get("radius", args.get("size", 1.0))
        resolution = args.get("resolution", 12)
        valid = {"BEZIER", "NURBS", "PATH", "CIRCLE"}
        if curve_type not in valid:
            raise ToolError("type must be BEZIER, NURBS, PATH, or CIRCLE", code=-32602)
        try:
            radius_f = float(radius)
        except Exception:
            raise ToolError("radius must be a number", code=-32602)
        if radius_f <= 0:
            raise ToolError("radius must be > 0", code=-32602)
        try:
            res_i = int(resolution)
        except Exception:
            raise ToolError("resolution must be an integer", code=-32602)
        code = f"""
import bpy, math
curve_type = {json.dumps(curve_type)}
name = {json.dumps(name)}
radius = {radius_f}
res_u = {res_i}
loc = ({location[0]}, {location[1]}, {location[2]})
curve_data = bpy.data.curves.new(name=name + "_Curve", type='CURVE')
curve_data.dimensions = '3D'
curve_data.resolution_u = res_u
if curve_type == "BEZIER":
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(1)
    pts = [(0.0, 0.0, 0.0), (radius, 0.0, 0.0)]
    for pt, co in zip(spline.bezier_points, pts):
        pt.co = co
        pt.handle_left_type = 'AUTO'
        pt.handle_right_type = 'AUTO'
elif curve_type in {{"NURBS", "PATH"}}:
    spline = curve_data.splines.new('NURBS')
    spline.points.add(3)
    pts = [(0.0, 0.0, 0.0), (radius, 0.0, 0.0), (radius, radius, 0.0), (0.0, radius, 0.0)]
    for pt, co in zip(spline.points, pts):
        pt.co = (co[0], co[1], co[2], 1.0)
    spline.use_endpoint_u = True
elif curve_type == "CIRCLE":
    spline = curve_data.splines.new('NURBS')
    spline.points.add(7)
    pts = [
        (1.0, 0.0, 0.0), (0.7071, 0.7071, 0.0), (0.0, 1.0, 0.0), (-0.7071, 0.7071, 0.0),
        (-1.0, 0.0, 0.0), (-0.7071, -0.7071, 0.0), (0.0, -1.0, 0.0), (0.7071, -0.7071, 0.0)
    ]
    for pt, co in zip(spline.points, pts):
        pt.co = (co[0] * radius, co[1] * radius, co[2], 1.0)
    spline.use_cyclic_u = True
obj = bpy.data.objects.new(name, curve_data)
bpy.context.scene.collection.objects.link(obj)
obj.location = loc
result = {{
    "name": obj.name,
    "type": curve_type,
    "location": [obj.location.x, obj.location.y, obj.location.z],
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to create curve", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            text = f"Created curve {info.get('name')} ({info.get('type')})"
        else:
            text = f"Created curve {name} ({curve_type})"
        return _make_tool_result(text, is_error=False)

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
        payload = dict(args)
        # legacy upgrade path
        if {"need", "why", "session"} <= payload.keys() and "type" not in payload:
            payload.setdefault("type", "enhancement")
            payload.setdefault("priority", "medium")
            payload.setdefault("domain", "system")
            payload.setdefault("source", "manual")
            payload.setdefault("schema_version", 2)
        try:
            entry = self._tool_request_store.create(payload)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        _append_request({"type": "tool-request", "id": entry["id"], "payload": payload})
        return _make_tool_result(json.dumps({"ok": True, "id": entry["id"], "status": entry.get("status"), "stored_path": str(TOOL_REQUEST_FILE)}), is_error=False)

    def _tool_tool_request_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        filters = args.get("filters") or {}
        if not isinstance(filters, dict):
            return _make_tool_result("filters must be an object", is_error=True)
        limit = args.get("limit", 50)
        cursor = args.get("cursor")
        next_page_token = args.get("next_page_token")
        try:
            limit_i = int(limit)
        except Exception:
            return _make_tool_result("limit must be an integer", is_error=True)
        res = self._tool_request_store.list(filters, limit=limit_i, cursor=cursor, next_page_token=next_page_token)
        return _make_tool_result(json.dumps(res), is_error=False)

    def _tool_tool_request_get(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req_id = args.get("id")
        if not isinstance(req_id, str):
            return _make_tool_result("id must be a string", is_error=True)
        item = self._tool_request_store.get(req_id)
        if not item:
            return _make_tool_result("not found", is_error=True)
        return _make_tool_result(json.dumps(item), is_error=False)

    def _tool_tool_request_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req_id = args.get("id")
        if not isinstance(req_id, str):
            return _make_tool_result("id must be a string", is_error=True)
        tests_passed = args.get("tests_passed")
        mode = args.get("mode", "merge")
        list_mode = args.get("list_mode", "append")
        changes = {k: v for k, v in args.items() if k not in {"id", "tests_passed", "mode", "list_mode"}}
        if "status" in changes and changes["status"] == "implemented":
            if tests_passed is not True:
                return _make_tool_result("tests_passed must be true to mark implemented", is_error=True)
            related = self._tool_request_store.requests.get(req_id, {}).get("related_tool")
            if related and related not in self._tools:
                return _make_tool_result("related_tool not found in registry", is_error=True)
        try:
            updated = self._tool_request_store.update(req_id, changes, mode=mode, list_mode=list_mode)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        return _make_tool_result(json.dumps({"ok": True, "id": req_id, "status": updated.get("status")}), is_error=False)

    def _tool_tool_request_delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        req_id = args.get("id")
        if not isinstance(req_id, str):
            return _make_tool_result("id must be a string", is_error=True)
        try:
            res = self._tool_request_store.delete(req_id)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        return _make_tool_result(json.dumps(res), is_error=False)

    def _tool_tool_request_bulk_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        ids = args.get("ids")
        patch = args.get("patch")
        mode = args.get("mode", "merge")
        list_mode = args.get("list_mode", "append")
        tests_passed = args.get("tests_passed")
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            return _make_tool_result("ids must be an array of strings", is_error=True)
        if not isinstance(patch, dict):
            return _make_tool_result("patch must be an object", is_error=True)
        if patch.get("status") == "implemented":
            if tests_passed is not True:
                return _make_tool_result("tests_passed must be true to mark implemented", is_error=True)
            for rid in ids:
                related = self._tool_request_store.requests.get(rid, {}).get("related_tool")
                if related and related not in self._tools:
                    return _make_tool_result("related_tool not found in registry", is_error=True)
        try:
            updated = self._tool_request_store.bulk_update(ids, patch, mode=mode, list_mode=list_mode)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        return _make_tool_result(json.dumps({"ok": True, "updated_ids": [u.get("id") for u in updated]}), is_error=False)

    def _tool_tool_request_bulk_delete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        ids = args.get("ids")
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            return _make_tool_result("ids must be an array of strings", is_error=True)
        try:
            deleted = self._tool_request_store.bulk_delete(ids)
        except ToolError as exc:
            return _make_tool_result(str(exc), is_error=True)
        return _make_tool_result(json.dumps({"ok": True, "deleted_ids": deleted}), is_error=False)

    def _tool_tool_request_purge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        statuses = args.get("status") or []
        older_than_days = args.get("older_than_days")
        if statuses and (not isinstance(statuses, list) or any(not isinstance(s, str) for s in statuses)):
            return _make_tool_result("status must be an array of strings", is_error=True)
        if older_than_days is not None:
            try:
                older_than_days = int(older_than_days)
            except Exception:
                return _make_tool_result("older_than_days must be an integer", is_error=True)
        deleted = self._tool_request_store.purge(statuses=statuses, older_than_days=older_than_days)
        return _make_tool_result(json.dumps({"ok": True, "deleted_ids": deleted}), is_error=False)

    def _tool_tool_request_lint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tests_passed = args.get("tests_passed", False)
        if not isinstance(tests_passed, bool):
            return _make_tool_result("tests_passed must be a boolean", is_error=True)
        requests = list(self._tool_request_store.requests.values())
        tool_names = set(self._tools.keys())
        seen_keys: Dict[str, str] = {}
        duplicates = []
        for item in requests:
            domain = str(item.get("domain", "")).lower()
            typ = str(item.get("type", "")).lower()
            need = str(item.get("need", "")).strip().lower()
            norm_key = f"{domain}::{typ}::{need}"
            if norm_key in seen_keys:
                duplicates.append({"key": norm_key, "ids": [seen_keys[norm_key], item.get("id")]})
            else:
                seen_keys[norm_key] = item.get("id")
        issues = []
        for item in requests:
            if item.get("status") == "implemented":
                related = item.get("related_tool")
                if not related or related not in tool_names:
                    issues.append({"id": item.get("id"), "reason": "missing_tool"})
                elif not tests_passed:
                    issues.append({"id": item.get("id"), "reason": "tests_not_confirmed"})
        payload = {"ok": True, "duplicates": duplicates, "issues": issues, "count": len(requests)}
        return _make_tool_result(json.dumps(payload), is_error=False)

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

    def _tool_convert_object(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        target = (args.get("target") or "").upper()
        valid_targets = {"MESH", "CURVE"}
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if target not in valid_targets:
            raise ToolError("target must be MESH or CURVE", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
target = {json.dumps(target)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
if target == "MESH" and obj.type not in {{"CURVE", "MESH", "FONT", "SURFACE", "TEXT"}}:
    raise ValueError("Object cannot be converted to mesh")
if target == "CURVE" and obj.type not in {{"MESH", "CURVE"}}:
    raise ValueError("Object cannot be converted to curve")
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.convert(target=target)
new_obj = bpy.context.view_layer.objects.active or obj
result = {{
    "name": new_obj.name,
    "type": new_obj.type,
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to convert object", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            text = f"Converted {name} to {info.get('type')} as {info.get('name')}"
        else:
            text = f"Converted {name} to {target}"
        return _make_tool_result(text, is_error=False)

    def _tool_set_3d_cursor(self, args: Dict[str, Any]) -> Dict[str, Any]:
        location = self._validate_vector(args.get("location"), name="location")
        rotation = self._validate_vector(args.get("rotation"), name="rotation")
        if location is None:
            raise ToolError("location must be an array of 3 numbers", code=-32602)
        if rotation is None:
            rotation = [0.0, 0.0, 0.0]
        code = f"""
import bpy, math
loc = ({location[0]}, {location[1]}, {location[2]})
rot = ({rotation[0]}, {rotation[1]}, {rotation[2]})
cursor = bpy.context.scene.cursor
cursor.location = loc
cursor.rotation_euler = tuple(math.radians(v) for v in rot)
result = {{
    "location": [cursor.location.x, cursor.location.y, cursor.location.z],
    "rotation": [math.degrees(v) for v in cursor.rotation_euler],
}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=3.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to set cursor", is_error=True)
        info = data.get("result")
        if isinstance(info, dict):
            text = f"Cursor -> loc {info.get('location')} rot {info.get('rotation')}"
        else:
            text = "Cursor updated"
        return _make_tool_result(text, is_error=False)

    def _tool_snap(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        target = (args.get("target") or "").upper()
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        valid_targets = {"GRID", "CURSOR", "ACTIVE", "INCREMENT"}
        if target not in valid_targets:
            raise ToolError("target must be GRID, CURSOR, ACTIVE, or INCREMENT", code=-32602)
        code = f"""
import bpy, math
name = {json.dumps(name)}
target = {json.dumps(target)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
before = {{
    "location": [obj.location.x, obj.location.y, obj.location.z],
    "rotation": [math.degrees(v) for v in obj.rotation_euler],
    "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
}}
new_loc = before["location"]
if target in {{"GRID", "INCREMENT"}}:
    new_loc = [round(obj.location.x), round(obj.location.y), round(obj.location.z)]
elif target == "CURSOR":
    cur = bpy.context.scene.cursor.location
    new_loc = [cur.x, cur.y, cur.z]
elif target == "ACTIVE":
    active = bpy.context.view_layer.objects.active
    if active is None:
        raise ValueError("Active object required for ACTIVE snap")
    new_loc = [active.location.x, active.location.y, active.location.z]
obj.location = tuple(new_loc)
after = {{
    "location": [obj.location.x, obj.location.y, obj.location.z],
    "rotation": [math.degrees(v) for v in obj.rotation_euler],
    "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
}}
result = {{"before": before, "after": after, "target": target}}
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to snap", is_error=True)
        return _make_tool_result("Snapped object", is_error=False)

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

    def _tool_mark_sharp_edges(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        mode = (args.get("mode") or "").lower()
        selection = (args.get("selection") or "").lower()
        angle_deg = args.get("angle_degrees", 30.0)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        if mode not in ("mark", "clear"):
            raise ToolError("mode must be 'mark' or 'clear'", code=-32602)
        if selection not in ("selected", "by_angle"):
            raise ToolError("selection must be 'selected' or 'by_angle'", code=-32602)
        if selection == "by_angle":
            try:
                angle_f = float(angle_deg)
            except Exception:
                raise ToolError("angle_degrees must be a number", code=-32602)
            if angle_f <= 0 or angle_f > 180:
                raise ToolError("angle_degrees must be between 0 and 180", code=-32602)
        else:
            angle_f = 30.0
        clear_flag = mode == "clear"
        code = f"""
import bpy, bmesh, math
name = {json.dumps(name)}
clear_flag = {clear_flag}
selection_mode = {json.dumps(selection)}
angle_rad = math.radians({angle_f})
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
    bpy.ops.mesh.select_mode(type='EDGE')
    if selection_mode == "by_angle":
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.edges_select_sharp(sharpness=angle_rad)
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    selected_edges = [e for e in bm.edges if e.select]
    if not selected_edges:
        raise RuntimeError("No edges selected")
    bpy.ops.mesh.mark_sharp(clear=clear_flag)
    bpy.ops.object.mode_set(mode='OBJECT')
    sharp_count = sum(1 for e in obj.data.edges if getattr(e, "use_edge_sharp", False))
    result = {{"affected": len(selected_edges), "sharp_edges": sharp_count}}
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=8.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to mark sharp edges", is_error=True)
        info = data.get("result") or {}
        if isinstance(info, dict):
            text = f"{'Cleared' if clear_flag else 'Marked'} sharp on {info.get('affected', 0)} edges"
        else:
            text = "Updated sharp edges"
        return _make_tool_result(text, is_error=False)

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
            "screw": "SCREW",
            "edge_split": "EDGE_SPLIT",
            "shrinkwrap": "SHRINKWRAP",
            "lattice": "LATTICE",
            "skin": "SKIN",
        }
        if mod_type not in type_map:
            raise ToolError(
                "type must be one of mirror,array,solidify,bevel,subdivision,boolean,decimate,weld,triangulate,"
                "screw,edge_split,shrinkwrap,lattice,skin",
                code=-32602,
            )
        clean_settings: Dict[str, Any] = {}
        if mod_type == "mirror":
            for axis_key in ("use_axis_x", "use_axis_y", "use_axis_z"):
                val = settings.get(axis_key)
                if val is not None:
                    if not isinstance(val, bool):
                        raise ToolError(f"{axis_key} must be a boolean", code=-32602)
                    clean_settings[axis_key] = val
            for opt_key, prop in (("clipping", "use_clip"), ("merge", "use_mirror_merge")):
                val = settings.get(opt_key)
                if val is not None:
                    if not isinstance(val, bool):
                        raise ToolError(f"{opt_key} must be a boolean", code=-32602)
                    clean_settings[prop] = val
            merge_threshold = settings.get("merge_threshold")
            if merge_threshold is not None:
                try:
                    clean_settings["merge_threshold"] = float(merge_threshold)
                except Exception:
                    raise ToolError("merge_threshold must be a number", code=-32602)
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
            offset_obj = settings.get("offset_object")
            if offset_obj is not None:
                if not isinstance(offset_obj, str):
                    raise ToolError("offset_object must be a string", code=-32602)
                clean_settings["offset_object"] = offset_obj
            obj_offset = settings.get("object_offset")
            if obj_offset is not None:
                if not isinstance(obj_offset, list) or len(obj_offset) != 3:
                    raise ToolError("object_offset must be an array of 3 numbers", code=-32602)
                try:
                    clean_settings["object_offset"] = [float(v) for v in obj_offset]
                except Exception:
                    raise ToolError("object_offset must be an array of 3 numbers", code=-32602)
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
        if mod_type == "screw":
            angle = settings.get("angle_degrees", settings.get("angle", 360.0))
            steps = settings.get("steps")
            axis = (settings.get("axis") or "Z").upper()
            try:
                clean_settings["angle"] = float(angle)
            except Exception:
                raise ToolError("angle_degrees must be a number", code=-32602)
            if steps is not None:
                try:
                    clean_settings["steps"] = int(steps)
                except Exception:
                    raise ToolError("steps must be an integer", code=-32602)
            if axis not in ("X", "Y", "Z"):
                raise ToolError("axis must be X, Y, or Z", code=-32602)
            clean_settings["axis"] = axis
        if mod_type == "edge_split":
            split_angle = settings.get("split_angle", 30.0)
            try:
                clean_settings["split_angle"] = float(split_angle)
            except Exception:
                raise ToolError("split_angle must be a number", code=-32602)
            for key in ("use_edge_angle", "use_edge_sharp"):
                val = settings.get(key)
                if val is not None:
                    if not isinstance(val, bool):
                        raise ToolError(f"{key} must be a boolean", code=-32602)
                    clean_settings[key] = val
        if mod_type == "shrinkwrap":
            target_obj = settings.get("target")
            if target_obj is not None and not isinstance(target_obj, str):
                raise ToolError("target must be a string", code=-32602)
            if target_obj is not None:
                clean_settings["target"] = target_obj
            offset = settings.get("offset")
            if offset is not None:
                try:
                    clean_settings["offset"] = float(offset)
                except Exception:
                    raise ToolError("offset must be a number", code=-32602)
            wrap_method = settings.get("wrap_method")
            if wrap_method is not None:
                if not isinstance(wrap_method, str):
                    raise ToolError("wrap_method must be a string", code=-32602)
                valid_wrap = {"NEAREST_SURFACEPOINT", "PROJECT", "NEAREST_VERTEX", "TARGET_PROJECT"}
                wm_upper = wrap_method.upper()
                if wm_upper not in valid_wrap:
                    raise ToolError("wrap_method is invalid", code=-32602)
                clean_settings["wrap_method"] = wm_upper
        if mod_type == "lattice":
            lattice = settings.get("lattice")
            if lattice is None or not isinstance(lattice, str):
                raise ToolError("lattice must be a string", code=-32602)
            clean_settings["lattice"] = lattice
        mod_bpy_type = type_map[mod_type]
        code = f"""
import bpy, math
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
    if "offset_object" in settings:
        off_obj = bpy.data.objects.get(settings["offset_object"])
        if off_obj is None:
            raise ValueError("Offset object not found")
        mod.use_object_offset = True
        mod.offset_object = off_obj
    if "object_offset" in settings:
        mod.use_constant_offset = True
        mod.constant_offset_displace = tuple(settings["object_offset"])
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
elif {json.dumps(mod_type)} == "screw":
    if "angle" in settings:
        mod.angle = math.radians(settings["angle"])
    if "steps" in settings:
        mod.steps = settings["steps"]
    if "axis" in settings:
        mod.axis = settings["axis"]
elif {json.dumps(mod_type)} == "edge_split":
    if "split_angle" in settings:
        mod.split_angle = math.radians(settings["split_angle"])
    if "use_edge_angle" in settings:
        mod.use_edge_angle = settings["use_edge_angle"]
    if "use_edge_sharp" in settings:
        mod.use_edge_sharp = settings["use_edge_sharp"]
elif {json.dumps(mod_type)} == "shrinkwrap":
    if "target" in settings:
        tgt = bpy.data.objects.get(settings["target"])
        if tgt is None:
            raise ValueError("Shrinkwrap target not found")
        mod.target = tgt
    if "offset" in settings:
        mod.offset = settings["offset"]
    if "wrap_method" in settings:
        mod.wrap_method = settings["wrap_method"]
elif {json.dumps(mod_type)} == "lattice":
    if "lattice" in settings:
        lat = bpy.data.objects.get(settings["lattice"])
        if lat is None:
            raise ValueError("Lattice object not found")
        mod.object = lat
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

    def _tool_list_modifiers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        code = f"""
import bpy
name = {json.dumps(name)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise ValueError("Object not found")
mods = []
for mod in obj.modifiers:
    info = {{"name": mod.name, "type": mod.type}}
    for field in (
        "levels", "render_levels", "width", "segments", "thickness", "ratio",
        "merge_threshold", "use_clip", "use_mirror_merge", "use_relative_offset",
        "relative_offset_displace", "use_constant_offset", "constant_offset_displace",
        "use_object_offset", "offset_object", "split_angle", "use_edge_angle", "use_edge_sharp",
        "wrap_method", "offset", "axis", "angle", "steps"
    ):
        try:
            val = getattr(mod, field, None)
        except Exception:
            continue
        if hasattr(val, "name"):
            val = val.name
        elif hasattr(val, "to_tuple"):
            try:
                val = list(val)
            except Exception:
                pass
        info[field] = val
    mods.append(info)
result = mods
"""
        data = _bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return _make_tool_result(data.get("error") or "Failed to list modifiers", is_error=True)
        mods = data.get("result") or []
        if isinstance(mods, list):
            names = [f"{m.get('name')}({m.get('type')})" for m in mods if isinstance(m, dict)]
            text = ", ".join(names) if names else "no modifiers"
        else:
            text = "listed modifiers"
        return _make_tool_result(text, is_error=False)

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
