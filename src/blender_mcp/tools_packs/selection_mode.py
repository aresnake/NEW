import json
from typing import Any, Dict


def register(registry, bridge_request: Any, make_tool_result: Any, ToolError: Any) -> None:  # noqa: ANN001, N803
    reg = registry._register  # noqa: SLF001

    mode_values = {"OBJECT", "EDIT", "SCULPT", "VERTEX_PAINT", "WEIGHT_PAINT", "TEXTURE_PAINT"}
    select_mode_values = {"VERT", "EDGE", "FACE"}
    box_circle_modes = {"SET", "ADD", "SUB"}
    trait_ops_map = {
        "NON_MANIFOLD": ("EDGE", "bpy.ops.mesh.select_non_manifold()"),
        "BOUNDARY": (
            "EDGE",
            "bpy.ops.mesh.select_non_manifold(use_boundary=True, use_wire=False, use_multi_face=False, use_non_contiguous=False, use_verts=False)",
        ),
        "LOOSE": ("VERT", "bpy.ops.mesh.select_loose()"),
        "INTERIOR_FACES": ("FACE", "bpy.ops.mesh.select_interior_faces()"),
    }

    def _indent(code: str) -> str:
        return "\n    ".join(code.strip().splitlines())

    def _build_edit_code(op: str, selection_type: str | None = None) -> str:
        selection_stmt = ""
        if selection_type:
            selection_stmt = f"    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type={json.dumps(selection_type)})\n"
        op_body = _indent(op)
        return f"""
import bpy, bmesh
obj = bpy.context.view_layer.objects.active
if obj is None or obj.type != 'MESH':
    mesh_obj = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    if mesh_obj is None:
        mesh = bpy.data.meshes.new("AutoMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.to_mesh(mesh)
        bm.free()
        mesh_obj = bpy.data.objects.new("AutoMesh", mesh)
        bpy.context.scene.collection.objects.link(mesh_obj)
    bpy.context.view_layer.objects.active = mesh_obj
    obj = mesh_obj
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT', 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
{selection_stmt}    {op_body}
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""

    def _set_mode(args: Dict[str, Any]) -> Dict[str, Any]:
        mode = (args.get("mode") or "").upper()
        if mode not in mode_values:
            raise ToolError("mode must be OBJECT, EDIT, SCULPT, VERTEX_PAINT, WEIGHT_PAINT, or TEXTURE_PAINT", code=-32602)
        code = f"""
import bpy, bmesh
mode = {json.dumps(mode)}
obj = bpy.context.view_layer.objects.active
if obj is None or (mode != 'OBJECT' and obj.type != 'MESH'):
    mesh_obj = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
    if mesh_obj is None:
        mesh = bpy.data.meshes.new("AutoMesh")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.to_mesh(mesh)
        bm.free()
        mesh_obj = bpy.data.objects.new("AutoMesh", mesh)
        bpy.context.scene.collection.objects.link(mesh_obj)
    bpy.context.view_layer.objects.active = mesh_obj
    obj = mesh_obj
try:
    bpy.ops.object.mode_set(mode=mode)
except Exception as exc:  # noqa: BLE001
    raise RuntimeError(f"Failed to set mode {{mode}}: {{exc}}")
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or f"Failed to set mode {mode}", is_error=True)
        return make_tool_result(f"Set mode to {mode}", is_error=False)

    def _set_selection_mode(args: Dict[str, Any]) -> Dict[str, Any]:
        mode = (args.get("mode") or "").upper()
        if mode not in select_mode_values:
            raise ToolError("mode must be VERT, EDGE, or FACE", code=-32602)
        code = _build_edit_code(f"bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type={json.dumps(mode)})", selection_type=mode)
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to set selection mode", is_error=True)
        return make_tool_result(f"Selection mode set to {mode}", is_error=False)

    def _select_all(args: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.select_all(action='SELECT')", selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select all", is_error=True)
        return make_tool_result("Selected all", is_error=False)

    def _select_none(args: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.select_all(action='DESELECT')", selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to deselect", is_error=True)
        return make_tool_result("Deselected all", is_error=False)

    def _select_invert(args: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.select_all(action='INVERT')", selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to invert selection", is_error=True)
        return make_tool_result("Inverted selection", is_error=False)

    def _select_linked(args: Dict[str, Any]) -> Dict[str, Any]:
        op = """
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
if not bm.verts:
    raise RuntimeError("Mesh has no geometry")
bm.verts.ensure_lookup_table()
for v in bm.verts:
    v.select_set(False)
seed = bm.verts[0]
seed.select_set(True)
bmesh.update_edit_mesh(mesh, False, False)
bpy.ops.mesh.select_linked()
"""
        code = _build_edit_code(op, selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select linked", is_error=True)
        return make_tool_result("Selected linked", is_error=False)

    def _select_more(args: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.select_more()", selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select more", is_error=True)
        return make_tool_result("Expanded selection", is_error=False)

    def _select_less(args: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.select_less()", selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select less", is_error=True)
        return make_tool_result("Contracted selection", is_error=False)

    def _select_loop(args: Dict[str, Any]) -> Dict[str, Any]:
        op = """
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.edges.ensure_lookup_table()
if not bm.edges:
    raise RuntimeError("Mesh has no edges")
for e in bm.edges:
    e.select_set(False)
target = bm.edges[0]
target.select_set(True)
bm.select_history.clear()
bm.select_history.add(target)
bmesh.update_edit_mesh(mesh, False, False)
bpy.ops.mesh.loop_multi_select(ring=False)
"""
        code = _build_edit_code(op, selection_type="EDGE")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select loop", is_error=True)
        return make_tool_result("Selected edge loop", is_error=False)

    def _select_ring(args: Dict[str, Any]) -> Dict[str, Any]:
        op = """
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.edges.ensure_lookup_table()
if not bm.edges:
    raise RuntimeError("Mesh has no edges")
for e in bm.edges:
    e.select_set(False)
target = bm.edges[0]
target.select_set(True)
bm.select_history.clear()
bm.select_history.add(target)
bmesh.update_edit_mesh(mesh, False, False)
bpy.ops.mesh.loop_multi_select(ring=True)
"""
        code = _build_edit_code(op, selection_type="EDGE")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to select ring", is_error=True)
        return make_tool_result("Selected edge ring", is_error=False)

    def _select_trait(args: Dict[str, Any]) -> Dict[str, Any]:
        trait = (args.get("trait") or "").upper()
        if trait not in trait_ops_map:
            raise ToolError("trait must be NON_MANIFOLD, BOUNDARY, LOOSE, or INTERIOR_FACES", code=-32602)
        selection_type, op = trait_ops_map[trait]
        code = _build_edit_code(op, selection_type=selection_type)
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or f"Failed to select {trait.lower()}", is_error=True)
        return make_tool_result(f"Selected {trait.lower().replace('_', ' ')}", is_error=False)

    def _select_box(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            xmin = int(args.get("xmin"))
            ymin = int(args.get("ymin"))
            xmax = int(args.get("xmax"))
            ymax = int(args.get("ymax"))
        except Exception:
            raise ToolError("xmin, ymin, xmax, ymax must be integers", code=-32602)
        mode = (args.get("mode") or "SET").upper()
        if mode not in box_circle_modes:
            raise ToolError("mode must be SET, ADD, or SUB", code=-32602)
        op = f"bpy.ops.mesh.select_box(xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}, mode={json.dumps(mode)})"
        code = _build_edit_code(op, selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to box select", is_error=True)
        return make_tool_result("Box selected", is_error=False)

    def _select_circle(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            x = int(args.get("x"))
            y = int(args.get("y"))
            radius = int(args.get("radius"))
        except Exception:
            raise ToolError("x, y, radius must be integers", code=-32602)
        mode = (args.get("mode") or "SET").upper()
        if mode not in box_circle_modes:
            raise ToolError("mode must be SET, ADD, or SUB", code=-32602)
        op = f"bpy.ops.mesh.select_circle(x={x}, y={y}, radius={radius}, mode={json.dumps(mode)})"
        code = _build_edit_code(op, selection_type="VERT")
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to circle select", is_error=True)
        return make_tool_result("Circle selected", is_error=False)

    reg(
        "blender-set-mode",
        "Set Blender interaction mode",
        {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": sorted(mode_values)}},
            "required": ["mode"],
            "additionalProperties": False,
        },
        _set_mode,
    )
    reg(
        "blender-set-selection-mode",
        "Set mesh selection mode",
        {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": sorted(select_mode_values)}},
            "required": ["mode"],
            "additionalProperties": False,
        },
        _set_selection_mode,
    )
    reg(
        "blender-select-all",
        "Select all mesh elements",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_all,
    )
    reg(
        "blender-select-none",
        "Deselect all mesh elements",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_none,
    )
    reg(
        "blender-select-invert",
        "Invert selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_invert,
    )
    reg(
        "blender-select-linked",
        "Select linked geometry from active element",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_linked,
    )
    reg(
        "blender-select-more",
        "Expand selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_more,
    )
    reg(
        "blender-select-less",
        "Shrink selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_less,
    )
    reg(
        "blender-select-loop",
        "Select an edge loop",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_loop,
    )
    reg(
        "blender-select-ring",
        "Select an edge ring",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _select_ring,
    )
    reg(
        "blender-select-trait",
        "Select geometry by trait",
        {
            "type": "object",
            "properties": {"trait": {"type": "string", "enum": sorted(trait_ops_map.keys())}},
            "required": ["trait"],
            "additionalProperties": False,
        },
        _select_trait,
    )
    reg(
        "blender-select-box",
        "Box select in edit mode",
        {
            "type": "object",
            "properties": {
                "xmin": {"type": "integer"},
                "ymin": {"type": "integer"},
                "xmax": {"type": "integer"},
                "ymax": {"type": "integer"},
                "mode": {"type": "string", "enum": sorted(box_circle_modes)},
            },
            "required": ["xmin", "ymin", "xmax", "ymax"],
            "additionalProperties": False,
        },
        _select_box,
    )
    reg(
        "blender-select-circle",
        "Circle select in edit mode",
        {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "radius": {"type": "integer"},
                "mode": {"type": "string", "enum": sorted(box_circle_modes)},
            },
            "required": ["x", "y", "radius"],
            "additionalProperties": False,
        },
        _select_circle,
    )
