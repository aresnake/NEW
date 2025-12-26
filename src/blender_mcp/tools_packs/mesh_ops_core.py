import json
from typing import Any, Dict


def register(registry, bridge_request: Any, make_tool_result: Any, ToolError: Any) -> None:  # noqa: ANN001, N803
    reg = registry._register  # noqa: SLF001

    def _indent(code: str) -> str:
        return "\n    ".join(code.strip().splitlines())

    def _build_edit_code(op: str) -> str:
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
    {op_body}
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""

    def _run(code: str, *, timeout: float = 5.0, error_msg: str = "Operation failed"):
        data = bridge_request("/exec", payload={"code": code}, timeout=timeout)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or error_msg, is_error=True)
        return make_tool_result("ok", is_error=False)

    def _mesh_fill(args: Dict[str, Any]) -> Dict[str, Any]:
        use_beauty = args.get("use_beauty", True)
        if not isinstance(use_beauty, bool):
            raise ToolError("use_beauty must be a boolean", code=-32602)
        code = _build_edit_code(f"bpy.ops.mesh.fill(use_beauty={use_beauty})")
        return _run(code, error_msg="Failed to fill selection")

    def _mesh_grid_fill(args: Dict[str, Any]) -> Dict[str, Any]:
        parts = []
        span = args.get("span")
        offset = args.get("offset")
        if span is not None:
            try:
                span_i = int(span)
            except Exception:
                raise ToolError("span must be an integer", code=-32602)
            parts.append(f"span={span_i}")
        if offset is not None:
            try:
                offset_i = int(offset)
            except Exception:
                raise ToolError("offset must be an integer", code=-32602)
            parts.append(f"offset={offset_i}")
        arg_str = ", ".join(parts)
        call = f"bpy.ops.mesh.fill_grid({arg_str})" if arg_str else "bpy.ops.mesh.fill_grid()"
        code = _build_edit_code(call)
        return _run(code, error_msg="Failed to grid fill")

    def _mesh_split(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.split()")
        return _run(code, error_msg="Failed to split selection")

    def _mesh_separate_selected(args: Dict[str, Any]) -> Dict[str, Any]:
        sep_type = (args.get("type") or "SELECTED").upper()
        valid_types = {"SELECTED", "MATERIAL", "LOOSE", "BY_MATERIAL"}
        if sep_type not in valid_types:
            raise ToolError("type must be SELECTED, MATERIAL, LOOSE, or BY_MATERIAL", code=-32602)
        code = _build_edit_code(
            f"""
mesh = bpy.context.active_object.data
bm = bmesh.from_edit_mesh(mesh)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
has_sel = any(v.select for v in bm.verts) or any(e.select for e in bm.edges) or any(f.select for f in bm.faces)
if not has_sel:
    raise RuntimeError("Nothing selected")
bpy.ops.mesh.separate(type={json.dumps(sep_type)})
"""
        )
        return _run(code, error_msg="Failed to separate selection")

    def _mesh_make_edge_face(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.edge_face_add()")
        return _run(code, error_msg="Failed to create edge/face")

    def _mesh_triangulate(args: Dict[str, Any]) -> Dict[str, Any]:
        quad_method = (args.get("quad_method") or "BEAUTY").upper()
        ngon_method = (args.get("ngon_method") or "BEAUTY").upper()
        valid_quad = {"BEAUTY", "FIXED", "FIXED_ALTERNATE", "SHORTEST_DIAGONAL"}
        valid_ngon = {"BEAUTY", "CLIP"}
        if quad_method not in valid_quad:
            raise ToolError("quad_method must be BEAUTY, FIXED, FIXED_ALTERNATE, or SHORTEST_DIAGONAL", code=-32602)
        if ngon_method not in valid_ngon:
            raise ToolError("ngon_method must be BEAUTY or CLIP", code=-32602)
        call = f"bpy.ops.mesh.quads_convert_to_tris(quad_method={json.dumps(quad_method)}, ngon_method={json.dumps(ngon_method)})"
        code = _build_edit_code(call)
        return _run(code, error_msg="Failed to triangulate faces")

    def _mesh_tris_to_quads(args: Dict[str, Any]) -> Dict[str, Any]:
        face_threshold = args.get("face_threshold", 0.6981)
        shape_threshold = args.get("shape_threshold", 0.6981)
        uvs = args.get("uvs", False)
        try:
            face_f = float(face_threshold)
            shape_f = float(shape_threshold)
        except Exception:
            raise ToolError("face_threshold and shape_threshold must be numbers", code=-32602)
        if not isinstance(uvs, bool):
            raise ToolError("uvs must be a boolean", code=-32602)
        call = (
            "bpy.ops.mesh.tris_convert_to_quads("
            f"face_threshold={face_f}, shape_threshold={shape_f}, uvs={uvs})"
        )
        code = _build_edit_code(call)
        return _run(code, error_msg="Failed to convert tris to quads")

    def _mesh_poke(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.poke()")
        return _run(code, error_msg="Failed to poke faces")

    def _mesh_rip(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.rip()")
        return _run(code, error_msg="Failed to rip mesh")

    def _mesh_rip_fill(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.rip_fill()")
        return _run(code, error_msg="Failed to rip fill mesh")

    def _mesh_bridge_edge_loops(_: Dict[str, Any]) -> Dict[str, Any]:
        code = _build_edit_code("bpy.ops.mesh.bridge_edge_loops()")
        return _run(code, error_msg="Failed to bridge edge loops")

    reg(
        "blender-mesh-fill",
        "Fill selected boundaries/edges/faces",
        {
            "type": "object",
            "properties": {"use_beauty": {"type": "boolean"}},
            "additionalProperties": False,
        },
        _mesh_fill,
    )
    reg(
        "blender-mesh-grid-fill",
        "Grid fill selected boundary",
        {
            "type": "object",
            "properties": {"span": {"type": "integer"}, "offset": {"type": "integer"}},
            "additionalProperties": False,
        },
        _mesh_grid_fill,
    )
    reg(
        "blender-mesh-split",
        "Split selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_split,
    )
    reg(
        "blender-mesh-separate-selected",
        "Separate selected elements into a new object",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_separate_selected,
    )
    reg(
        "blender-mesh-make-edge-face",
        "Create edge/face from selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_make_edge_face,
    )
    reg(
        "blender-mesh-triangulate-faces",
        "Triangulate selected faces",
        {
            "type": "object",
            "properties": {
                "quad_method": {"type": "string"},
                "ngon_method": {"type": "string"},
            },
            "additionalProperties": False,
        },
        _mesh_triangulate,
    )
    reg(
        "blender-mesh-quads-to-tris",
        "Convert quads/ngons to triangles",
        {
            "type": "object",
            "properties": {
                "quad_method": {"type": "string"},
                "ngon_method": {"type": "string"},
            },
            "additionalProperties": False,
        },
        _mesh_triangulate,
    )
    reg(
        "blender-mesh-tris-to-quads",
        "Convert triangles to quads",
        {
            "type": "object",
            "properties": {
                "face_threshold": {"type": "number"},
                "shape_threshold": {"type": "number"},
                "uvs": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        _mesh_tris_to_quads,
    )
    reg(
        "blender-mesh-poke-faces",
        "Poke selected faces",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_poke,
    )
    reg(
        "blender-mesh-rip",
        "Rip selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_rip,
    )
    reg(
        "blender-mesh-rip-fill",
        "Rip fill selection",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_rip_fill,
    )
    reg(
        "blender-mesh-bridge-edge-loops",
        "Bridge selected edge loops",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _mesh_bridge_edge_loops,
    )
    reg(
        "blender-mark-sharp-edges",
        "Mark or clear sharp edges",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "mode": {"type": "string"},
                "selection": {"type": "string"},
                "angle_degrees": {"type": "number"},
            },
            "required": ["name", "mode", "selection"],
            "additionalProperties": False,
        },
        registry._tool_mark_sharp_edges,  # noqa: SLF001
    )
