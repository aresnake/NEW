import json
from typing import Any, Dict


SNAPSHOT_CODE = """
try:
    import bpy
except Exception as exc:
    result = {"ok": False, "error": f"bpy unavailable: {exc}"}
else:
    collections = [col.name for col in bpy.data.collections]
    active_obj = None
    try:
        ctx_active = getattr(bpy.context, "active_object", None)
        if ctx_active is not None:
            active_obj = ctx_active.name
    except Exception:
        active_obj = None
    selected_objects = []
    try:
        selected_objects = [obj.name for obj in getattr(bpy.context, "selected_objects", [])]
    except Exception:
        selected_objects = []
    objects = []
    counts = {
        "objects": 0,
        "meshes": 0,
        "lights": 0,
        "cameras": 0,
        "empties": 0,
        "collections": len(collections),
        "materials": len(getattr(bpy.data, "materials", [])),
    }
    for obj in bpy.data.objects:
        counts["objects"] += 1
        obj_type = getattr(obj, "type", "") or ""
        obj_type_lower = obj_type.lower()
        if obj_type_lower == "mesh":
            counts["meshes"] += 1
        elif obj_type_lower == "light":
            counts["lights"] += 1
        elif obj_type_lower == "camera":
            counts["cameras"] += 1
        elif obj_type_lower == "empty":
            counts["empties"] += 1
        try:
            col_names = [c.name for c in obj.users_collection]
        except Exception:
            col_names = []
        try:
            mat_slots = len(obj.material_slots)
        except Exception:
            mat_slots = 0
        def _to_list(vec, fallback):
            try:
                return list(vec)
            except Exception:
                return fallback
        objects.append(
            {
                "name": getattr(obj, "name", ""),
                "type": obj_type,
                "location": _to_list(getattr(obj, "location", None), [0.0, 0.0, 0.0]),
                "rotation_euler": _to_list(getattr(obj, "rotation_euler", None), [0.0, 0.0, 0.0]),
                "scale": _to_list(getattr(obj, "scale", None), [1.0, 1.0, 1.0]),
                "dimensions": _to_list(getattr(obj, "dimensions", None), [0.0, 0.0, 0.0]),
                "collection_names": col_names,
                "material_slots_count": mat_slots,
            }
        )
    result = {
        "ok": True,
        "snapshot": {
            "collections": collections,
            "active_object": active_obj,
            "selected_objects": selected_objects,
            "objects": objects,
            "counts": counts,
        },
    }
"""


def register(registry, bridge_request: Any, _: Any, ToolError: Any) -> None:  # noqa: ANN001, N803
    reg = registry._register  # noqa: SLF001

    def _tool_blender_scene_snapshot(_: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = bridge_request("/exec", payload={"code": SNAPSHOT_CODE}, timeout=5.0)
        except ToolError as exc:  # noqa: BLE001
            return {"ok": False, "content": [{"type": "text", "text": str(exc)}], "isError": True}
        if not data.get("ok"):
            return {
                "ok": False,
                "content": [{"type": "text", "text": data.get("error") or "Failed to snapshot scene"}],
                "isError": True,
            }
        snapshot = data.get("result") or {}
        if isinstance(snapshot, dict) and "snapshot" in snapshot:
            snapshot = snapshot.get("snapshot") or {}
        return {"ok": True, "content": [{"type": "text", "text": json.dumps(snapshot)}], "isError": False}

    reg(
        "blender-scene-snapshot",
        "Capture a summary of the current Blender scene.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _tool_blender_scene_snapshot,
    )
