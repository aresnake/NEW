import json
from typing import Any, Dict, List


def register(registry, bridge_request: Any, make_tool_result: Any, ToolError: Any) -> None:  # noqa: ANN001, N803
    reg = registry._register  # noqa: SLF001

    def _indent(code: str) -> str:
        return "\n    ".join(code.strip().splitlines())

    def _build_edit_code(op: str) -> str:
        op_body = _indent(op)
        return f"""
import bpy, bmesh, math
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
    {op_body}
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""

    def _run(code: str, *, timeout: float = 5.0, error_msg: str = "Operation failed") -> Dict[str, Any]:
        data = bridge_request("/exec", payload={"code": code}, timeout=timeout)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or error_msg, is_error=True)
        return make_tool_result("ok", is_error=False)

    def _select_edges_sharp(args: Dict[str, Any]) -> Dict[str, Any]:
        angle = args.get("angle_degrees", 30.0)
        include_boundary = args.get("include_boundary", True)
        include_seams = args.get("include_seams", True)
        try:
            angle_f = float(angle)
        except Exception:
            raise ToolError("angle_degrees must be a number", code=-32602)
        if angle_f < 0:
            raise ToolError("angle_degrees must be >= 0", code=-32602)
        if not isinstance(include_boundary, bool):
            raise ToolError("include_boundary must be a boolean", code=-32602)
        if not isinstance(include_seams, bool):
            raise ToolError("include_seams must be a boolean", code=-32602)
        code = _build_edit_code(
            f"""
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.edges.ensure_lookup_table()
threshold = math.radians({angle_f})
for e in bm.edges:
    e.select_set(False)
for e in bm.edges:
    if {include_seams} and e.seam:
        e.select_set(True)
        continue
    lf = len(e.link_faces)
    if lf == 2:
        ang = e.calc_face_angle() or 0.0
        if ang >= threshold:
            e.select_set(True)
    elif lf == 1 and {include_boundary}:
        e.select_set(True)
bmesh.update_edit_mesh(mesh, False, False)
"""
        )
        return _run(code, error_msg="Failed to select sharp edges")

    def _select_faces_by_normal(args: Dict[str, Any]) -> Dict[str, Any]:
        axis = (args.get("axis") or "Z").upper()
        sign = (args.get("sign") or "POS").upper()
        min_dot = args.get("min_dot", 0.5)
        max_dot = args.get("max_dot")
        axis_map = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
        if axis not in axis_map:
            raise ToolError("axis must be X, Y, or Z", code=-32602)
        if sign not in {"POS", "NEG", "BOTH"}:
            raise ToolError("sign must be POS, NEG, or BOTH", code=-32602)
        try:
            min_dot_f = float(min_dot)
        except Exception:
            raise ToolError("min_dot must be a number", code=-32602)
        max_dot_expr = "None"
        if max_dot is not None:
            try:
                max_dot_f = float(max_dot)
            except Exception:
                raise ToolError("max_dot must be a number", code=-32602)
            max_dot_expr = str(max_dot_f)
        axis_vec = axis_map[axis]
        code = _build_edit_code(
            f"""
axis = {axis_vec}
sign = {json.dumps(sign)}
min_dot = {min_dot_f}
max_dot = {max_dot_expr}
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.faces.ensure_lookup_table()
for f in bm.faces:
    f.select_set(False)
for f in bm.faces:
    dot = f.normal.dot(axis)
    if sign == "POS":
        ok = dot >= min_dot
    elif sign == "NEG":
        ok = dot <= -min_dot
    else:
        ok = abs(dot) >= min_dot
    if max_dot is not None:
        ok = ok and abs(dot) <= max_dot
    if ok:
        f.select_set(True)
bmesh.update_edit_mesh(mesh, False, False)
"""
        )
        return _run(code, error_msg="Failed to select faces by normal")

    def _select_elements_by_index(args: Dict[str, Any]) -> Dict[str, Any]:
        elem_type = (args.get("element_type") or "").upper()
        indices = args.get("indices")
        invert = args.get("invert", False)
        if elem_type not in {"VERT", "EDGE", "FACE"}:
            raise ToolError("element_type must be VERT, EDGE, or FACE", code=-32602)
        if not isinstance(indices, list) or not indices:
            raise ToolError("indices must be a non-empty array of integers", code=-32602)
        if any(not isinstance(i, int) for i in indices):
            raise ToolError("indices must be integers", code=-32602)
        if not isinstance(invert, bool):
            raise ToolError("invert must be a boolean", code=-32602)
        code = _build_edit_code(
            f"""
elem_type = {json.dumps(elem_type)}
indices = {json.dumps(indices)}
invert = {invert}
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
def _invert(selection_iter):
    for elem in selection_iter:
        elem.select_set(not elem.select)
if elem_type == "VERT":
    if max(indices) >= len(bm.verts) or min(indices) < 0:
        raise RuntimeError("index out of range")
    for v in bm.verts:
        v.select_set(False)
    for idx in indices:
        bm.verts[idx].select_set(True)
    if invert:
        _invert(bm.verts)
elif elem_type == "EDGE":
    if max(indices) >= len(bm.edges) or min(indices) < 0:
        raise RuntimeError("index out of range")
    for e in bm.edges:
        e.select_set(False)
    for idx in indices:
        bm.edges[idx].select_set(True)
    if invert:
        _invert(bm.edges)
elif elem_type == "FACE":
    if max(indices) >= len(bm.faces) or min(indices) < 0:
        raise RuntimeError("index out of range")
    for f in bm.faces:
        f.select_set(False)
    for idx in indices:
        bm.faces[idx].select_set(True)
    if invert:
        _invert(bm.faces)
bmesh.update_edit_mesh(mesh, False, False)
"""
        )
        return _run(code, error_msg="Failed to select by index")

    def _select_faces_by_criteria(args: Dict[str, Any]) -> Dict[str, Any]:
        criteria = (args.get("criteria") or "NORMAL").upper()
        if criteria not in {"NORMAL", "AREA_GT", "AREA_LT"}:
            raise ToolError("criteria must be NORMAL, AREA_GT, or AREA_LT", code=-32602)
        if criteria == "NORMAL":
            axis = (args.get("axis") or "Z").upper()
            sign = (args.get("sign") or "POS").upper()
            min_dot = args.get("min_dot", 0.5)
            max_dot = args.get("max_dot")
            # reuse normal selection logic
            return _select_faces_by_normal({"axis": axis, "sign": sign, "min_dot": min_dot, "max_dot": max_dot})
        threshold = args.get("threshold")
        try:
            threshold_f = float(threshold)
        except Exception:
            raise ToolError("threshold must be a number", code=-32602)
        op = f"""
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.faces.ensure_lookup_table()
for f in bm.faces:
    f.select_set(False)
for f in bm.faces:
    if {"f.calc_area() >= threshold_f" if criteria == "AREA_GT" else "f.calc_area() <= threshold_f"}:
        f.select_set(True)
bmesh.update_edit_mesh(mesh, False, False)
"""
        code = _build_edit_code(op)
        return _run(code, error_msg="Failed to select faces by criteria")

    reg(
        "blender-select-edges-sharp",
        "Select edges above an angle threshold",
        {
            "type": "object",
            "properties": {
                "angle_degrees": {"type": "number"},
                "include_boundary": {"type": "boolean"},
                "include_seams": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        _select_edges_sharp,
    )
    reg(
        "blender-select-faces-by-normal",
        "Select faces by normal direction",
        {
            "type": "object",
            "properties": {
                "axis": {"type": "string"},
                "sign": {"type": "string"},
                "min_dot": {"type": "number"},
                "max_dot": {"type": "number"},
            },
            "additionalProperties": False,
        },
        _select_faces_by_normal,
    )
    reg(
        "blender-select-elements-by-index",
        "Select verts/edges/faces by indices",
        {
            "type": "object",
            "properties": {
                "element_type": {"type": "string"},
                "indices": {"type": "array"},
                "invert": {"type": "boolean"},
            },
            "required": ["element_type", "indices"],
            "additionalProperties": False,
        },
        _select_elements_by_index,
    )
    reg(
        "blender-select-faces-by-criteria",
        "Select faces by criteria (normal or area)",
        {
            "type": "object",
            "properties": {
                "criteria": {"type": "string"},
                "axis": {"type": "string"},
                "sign": {"type": "string"},
                "min_dot": {"type": "number"},
                "max_dot": {"type": "number"},
                "threshold": {"type": "number"},
            },
            "additionalProperties": False,
        },
        _select_faces_by_criteria,
    )
