
import json
from typing import Any, Dict


def register(registry, bridge_request, make_tool_result, ToolError) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001
    validate_vector = registry._validate_vector  # noqa: SLF001

    reg(
        "blender-extrude",
        "Extrude all faces of a mesh",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "mode": {"type": "string"}, "distance": {"type": "number"}},
            "required": ["name", "mode", "distance"],
            "additionalProperties": False,
        },
        registry._tool_extrude,  # noqa: SLF001
    )
    reg(
        "blender-inset",
        "Inset all faces of a mesh",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "thickness": {"type": "number"}},
            "required": ["name", "thickness"],
            "additionalProperties": False,
        },
        registry._tool_inset,  # noqa: SLF001
    )
    reg(
        "blender-loop-cut",
        "Add loop cuts to a mesh",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "cuts": {"type": "integer"}, "position": {"type": "number"}},
            "required": ["name", "cuts"],
            "additionalProperties": False,
        },
        registry._tool_loop_cut,  # noqa: SLF001
    )
    reg(
        "blender-bevel-edges",
        "Bevel mesh edges",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "width": {"type": "number"}, "segments": {"type": "integer"}},
            "required": ["name", "width", "segments"],
            "additionalProperties": False,
        },
        registry._tool_bevel_edges,  # noqa: SLF001
    )
    reg(
        "blender-merge-by-distance",
        "Merge mesh vertices by distance",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "distance": {"type": "number"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_merge_by_distance,  # noqa: SLF001
    )
    reg(
        "blender-recalc-normals",
        "Recalculate mesh normals (outside or inside)",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "inside": {"type": "boolean"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_recalc_normals,  # noqa: SLF001
    )
    reg(
        "blender-triangulate",
        "Triangulate mesh faces",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "method": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_triangulate,  # noqa: SLF001
    )
    def _mesh_extrude(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        distance = args.get("distance", 0.1)
        axis = args.get("axis", "NORMAL")
        selection_mode = args.get("selection_mode", "FACES")
        try:
            dist_f = float(distance)
        except Exception:
            raise ToolError("distance must be a number", code=-32602)
        axis_vals = {"X", "Y", "Z", "NORMAL"}
        if axis not in axis_vals:
            raise ToolError("axis must be one of X,Y,Z,NORMAL", code=-32602)
        sel_vals = {"FACES", "EDGES", "VERTS"}
        if selection_mode not in sel_vals:
            raise ToolError("selection_mode must be FACES, EDGES, or VERTS", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
distance = {dist_f}
axis = {json.dumps(axis)}
sel_mode = {json.dumps(selection_mode)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
bm.normal_update()
geom = None
verts = []
if sel_mode == "FACES":
    faces = bm.faces[:]
    if not faces:
        raise RuntimeError("Mesh has no faces")
    geom = bmesh.ops.extrude_face_region(bm, geom=faces)
elif sel_mode == "EDGES":
    edges = bm.edges[:]
    if not edges:
        raise RuntimeError("Mesh has no edges")
    geom = bmesh.ops.extrude_edge_only(bm, edges=edges)
elif sel_mode == "VERTS":
    verts = bm.verts[:]
    if not verts:
        raise RuntimeError("Mesh has no verts")
    geom = bmesh.ops.extrude_vert_indiv(bm, verts=verts)
if geom is not None:
    verts = [ele for ele in geom.get("geom", []) if isinstance(ele, bmesh.types.BMVert)]
if axis == "X":
    vec = (distance, 0.0, 0.0)
elif axis == "Y":
    vec = (0.0, distance, 0.0)
elif axis == "Z":
    vec = (0.0, 0.0, distance)
else:
    vec = (0.0, 0.0, distance)
bmesh.ops.translate(bm, verts=verts, vec=vec)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to extrude mesh", is_error=True)
        return make_tool_result(f"Extruded mesh on {name}", is_error=False)

    def _mesh_inset(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        thickness = args.get("thickness", 0.02)
        depth = args.get("depth", 0.0)
        selection_mode = args.get("selection_mode", "FACES")
        try:
            thick_f = float(thickness)
        except Exception:
            raise ToolError("thickness must be a number", code=-32602)
        if thick_f <= 0:
            raise ToolError("thickness must be > 0", code=-32602)
        try:
            depth_f = float(depth)
        except Exception:
            raise ToolError("depth must be a number", code=-32602)
        if depth_f < 0:
            raise ToolError("depth must be >= 0", code=-32602)
        sel_vals = {"FACES", "EDGES", "VERTS"}
        if selection_mode not in sel_vals:
            raise ToolError("selection_mode must be FACES, EDGES, or VERTS", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
thickness = {thick_f}
depth = {depth_f}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
initial_mode = obj.mode
restore_mode = initial_mode if initial_mode in {{'EDIT', 'OBJECT', 'SCULPT', 'VERTEX_PAINT', 'WEIGHT_PAINT', 'TEXTURE_PAINT'}} else 'OBJECT'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.inset(thickness=thickness, depth=depth)
finally:
    bpy.ops.object.mode_set(mode=restore_mode)
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to inset mesh", is_error=True)
        return make_tool_result(f"Inset mesh on {name}", is_error=False)

    def _mesh_bevel(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        offset = args.get("offset", 0.02)
        segments = args.get("segments", 1)
        affect = args.get("affect", "EDGES")
        try:
            offset_f = float(offset)
        except Exception:
            raise ToolError("offset must be a number", code=-32602)
        if offset_f <= 0:
            raise ToolError("offset must be > 0", code=-32602)
        try:
            segments_i = int(segments)
        except Exception:
            raise ToolError("segments must be an integer", code=-32602)
        if segments_i < 1:
            raise ToolError("segments must be >= 1", code=-32602)
        affect_vals = {"EDGES", "VERTS"}
        if affect not in affect_vals:
            raise ToolError("affect must be EDGES or VERTS", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
offset = {offset_f}
segments = {segments_i}
affect = {json.dumps(affect)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
geom = bm.edges[:] if affect == "EDGES" else bm.verts[:]
if not geom:
    raise RuntimeError("Mesh has no geometry to bevel")
bmesh.ops.bevel(bm, geom=geom, offset=offset, offset_type='OFFSET', segments=segments, profile=0.5, clamp_overlap=True)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to bevel mesh", is_error=True)
        return make_tool_result(f"Beveled mesh on {name}", is_error=False)

    def _mesh_subdivide(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        cuts = args.get("cuts", 1)
        try:
            cuts_i = int(cuts)
        except Exception:
            raise ToolError("cuts must be an integer", code=-32602)
        if cuts_i < 1:
            raise ToolError("cuts must be >= 1", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
cuts = {cuts_i}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
edges = bm.edges[:]
if not edges:
    raise RuntimeError("Mesh has no edges")
bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=False)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to subdivide mesh", is_error=True)
        return make_tool_result(f"Subdivided mesh on {name}", is_error=False)

    def _mesh_merge_by_distance(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        distance = args.get("distance", 0.0001)
        try:
            dist_f = float(distance)
        except Exception:
            raise ToolError("distance must be a number", code=-32602)
        if dist_f <= 0:
            raise ToolError("distance must be > 0", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
dist = {dist_f}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
verts = bm.verts[:]
if not verts:
    raise RuntimeError("Mesh has no verts")
bmesh.ops.remove_doubles(bm, verts=verts, dist=dist)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to merge by distance", is_error=True)
        return make_tool_result(f"Merged verts on {name}", is_error=False)
    def _mesh_bisect(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        plane_point = validate_vector(args.get("plane_point"), name="plane_point")
        plane_normal = validate_vector(args.get("plane_normal"), name="plane_normal")
        if plane_point is None:
            raise ToolError("plane_point is required", code=-32602)
        if plane_normal is None:
            raise ToolError("plane_normal is required", code=-32602)
        if all(abs(v) < 1e-8 for v in plane_normal):
            raise ToolError("plane_normal must be non-zero", code=-32602)
        clear_inner = args.get("clear_inner", False)
        clear_outer = args.get("clear_outer", False)
        use_fill = args.get("use_fill", False)
        if not isinstance(clear_inner, bool):
            raise ToolError("clear_inner must be a boolean", code=-32602)
        if not isinstance(clear_outer, bool):
            raise ToolError("clear_outer must be a boolean", code=-32602)
        if not isinstance(use_fill, bool):
            raise ToolError("use_fill must be a boolean", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
plane_point = {json.dumps(plane_point)}
plane_normal = {json.dumps(plane_normal)}
clear_inner = {json.dumps(clear_inner)}
clear_outer = {json.dumps(clear_outer)}
use_fill = {json.dumps(use_fill)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
bmesh.ops.bisect_plane(
    bm,
    geom=geom,
    plane_co=tuple(plane_point),
    plane_no=tuple(plane_normal),
    clear_inner=clear_inner,
    clear_outer=clear_outer,
    use_snap_center=False,
    snap_center=tuple(plane_point),
    use_fill=use_fill,
)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to knife plane", is_error=True)
        return make_tool_result(f"Knife plane on {name}", is_error=False)

    def _mesh_fill_holes(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        sides = args.get("sides", 0)
        try:
            sides_i = int(sides)
        except Exception:
            raise ToolError("sides must be an integer", code=-32602)
        if sides_i < 0:
            raise ToolError("sides must be >= 0", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
sides = {sides_i}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
boundary_edges = [e for e in bm.edges if e.is_boundary]
if not boundary_edges:
    raise RuntimeError("Mesh has no boundary edges")
bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=sides)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to fill holes", is_error=True)
        return make_tool_result(f"Filled holes on {name}", is_error=False)

    def _mesh_bridge_loops(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        cuts = args.get("cuts", 0)
        twist = args.get("twist", 0)
        try:
            cuts_i = int(cuts)
        except Exception:
            raise ToolError("cuts must be an integer", code=-32602)
        if cuts_i < 0:
            raise ToolError("cuts must be >= 0", code=-32602)
        try:
            twist_i = int(twist)
        except Exception:
            raise ToolError("twist must be an integer", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
cuts = {cuts_i}
twist = {twist_i}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
boundary_edges = [e for e in bm.edges if e.is_boundary]
if len(boundary_edges) < 2:
    raise RuntimeError("Not enough boundary loops to bridge")
visited = set()
loops = []
for e in boundary_edges:
    if e in visited:
        continue
    stack = [e]
    loop_edges = []
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        loop_edges.append(cur)
        for v in cur.verts:
            for ne in v.link_edges:
                if ne.is_boundary and ne not in visited:
                    stack.append(ne)
    if loop_edges:
        loops.append(loop_edges)
if len(loops) < 2:
    raise RuntimeError("Not enough boundary loops to bridge")
loops = sorted(loops, key=lambda l: len(l), reverse=True)[:2]
bridge_edges = loops[0] + loops[1]
res = bmesh.ops.bridge_loops(bm, edges=bridge_edges, cuts=cuts, twist=twist)
if not res.get("faces"):
    raise RuntimeError("Bridge failed")
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to bridge loops", is_error=True)
        return make_tool_result(f"Bridged boundary loops on {name}", is_error=False)

    def _mesh_delete(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        domain = args.get("domain")
        mode = args.get("mode", "ALL")
        valid_domain = {"VERTS", "EDGES", "FACES"}
        if domain not in valid_domain:
            raise ToolError("domain must be VERTS, EDGES, or FACES", code=-32602)
        valid_mode = {"SELECTED", "ALL"}
        if mode not in valid_mode:
            raise ToolError("mode must be SELECTED or ALL", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
domain = {json.dumps(domain)}
mode = {json.dumps(mode)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
if domain == "VERTS":
    geom = [v for v in bm.verts if (v.select or mode == "ALL")]
    if not geom:
        raise RuntimeError("No verts selected for delete")
    bmesh.ops.delete(bm, geom=geom, context='VERTS')
elif domain == "EDGES":
    geom = [e for e in bm.edges if (e.select or mode == "ALL")]
    if not geom:
        raise RuntimeError("No edges selected for delete")
    bmesh.ops.delete(bm, geom=geom, context='EDGES')
elif domain == "FACES":
    geom = [f for f in bm.faces if (f.select or mode == "ALL")]
    if not geom:
        raise RuntimeError("No faces selected for delete")
    bmesh.ops.delete(bm, geom=geom, context='FACES')
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to delete mesh elements", is_error=True)
        return make_tool_result(f"Deleted mesh elements on {name}", is_error=False)

    def _mesh_dissolve(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        angle_limit = args.get("angle_limit", 0.087266)
        delimit_raw = args.get("delimit") or []
        try:
            angle_f = float(angle_limit)
        except Exception:
            raise ToolError("angle_limit must be a number", code=-32602)
        if angle_f <= 0:
            raise ToolError("angle_limit must be > 0", code=-32602)
        valid_delimit = {"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"}
        if not isinstance(delimit_raw, list) or any(not isinstance(d, str) for d in delimit_raw):
            raise ToolError("delimit must be an array of strings", code=-32602)
        delimit_set = []
        for d in delimit_raw:
            d_up = d.upper()
            if d_up not in valid_delimit:
                raise ToolError("delimit entries must be NORMAL,MATERIAL,SEAM,SHARP,UV", code=-32602)
            delimit_set.append(d_up)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
angle_limit = {angle_f}
delimit = {json.dumps(delimit_set)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.dissolve_limit(bm, angle_limit=angle_limit, verts=bm.verts, edges=bm.edges, delimit=set(delimit))
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to dissolve limited", is_error=True)
        return make_tool_result(f"Dissolved limited on {name}", is_error=False)
    def _mesh_loop_cut(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        cuts = args.get("cuts", 1)
        axis = args.get("axis", "Z")
        factor = args.get("factor", 0.5)
        try:
            cuts_i = int(cuts)
        except Exception:
            raise ToolError("cuts must be an integer", code=-32602)
        if cuts_i < 1:
            raise ToolError("cuts must be >= 1", code=-32602)
        axis_vals = {"X", "Y", "Z"}
        if axis not in axis_vals:
            raise ToolError("axis must be X, Y, or Z", code=-32602)
        try:
            factor_f = float(factor)
        except Exception:
            raise ToolError("factor must be a number", code=-32602)
        if factor_f < 0.0 or factor_f > 1.0:
            raise ToolError("factor must be between 0 and 1", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
cuts = {cuts_i}
axis = {json.dumps(axis)}
factor = {factor_f}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis]
def edge_axis_length(e):
    v1, v2 = e.verts
    return abs(v2.co[axis_index] - v1.co[axis_index])
edges = sorted(bm.edges, key=edge_axis_length, reverse=True)
if not edges:
    raise RuntimeError("Mesh has no edges")
target_edge = edges[0:1]
res = bmesh.ops.subdivide_edges(bm, edges=target_edge, cuts=cuts, use_grid_fill=False)
new_verts = [v for v in res.get("geom_split", []) if isinstance(v, bmesh.types.BMVert)]
for v in new_verts:
    linked_edges = list(v.link_edges)
    if len(linked_edges) == 2:
        v1 = linked_edges[0].other_vert(v)
        v2 = linked_edges[1].other_vert(v)
        v.co = v1.co.lerp(v2.co, factor)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to loop cut", is_error=True)
        return make_tool_result(f"Loop cut mesh {name}", is_error=False)

    def _mesh_spin(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        axis = args.get("axis")
        angle_degrees = args.get("angle_degrees", 360)
        steps = args.get("steps", 12)
        if axis not in {"X", "Y", "Z"}:
            raise ToolError("axis must be X, Y, or Z", code=-32602)
        try:
            angle_f = float(angle_degrees)
        except Exception:
            raise ToolError("angle_degrees must be a number", code=-32602)
        if angle_f == 0:
            raise ToolError("angle_degrees must be non-zero", code=-32602)
        try:
            steps_i = int(steps)
        except Exception:
            raise ToolError("steps must be an integer", code=-32602)
        if steps_i < 1:
            raise ToolError("steps must be >= 1", code=-32602)
        center = registry._validate_vector(args.get("center"), name="center") or [0.0, 0.0, 0.0]  # noqa: SLF001
        axis_vec = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}[axis]
        code = f"""
import bpy, bmesh, math
name = {json.dumps(name)}
axis_vec = {json.dumps(axis_vec)}
angle = math.radians({angle_f})
steps = {steps_i}
cent = ({center[0]}, {center[1]}, {center[2]})
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
bmesh.ops.spin(
    bm,
    geom=geom,
    cent=cent,
    axis=axis_vec,
    angle=angle,
    steps=steps,
)
bm.to_mesh(mesh)
bm.free()
mesh.update()
bpy.context.view_layer.objects.active = obj
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to spin mesh", is_error=True)
        return make_tool_result(f"Spun mesh {name}", is_error=False)

    def _separate_loose(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        if name is None:
            raise ToolError("name is required", code=-32602)
        if not isinstance(name, str):
            raise ToolError("name must be a string", code=-32602)
        keep_original = args.get("keep_original", False)
        if not isinstance(keep_original, bool):
            raise ToolError("keep_original must be a boolean", code=-32602)
        code = f"""
import bpy, bmesh
name = {json.dumps(name)}
keep_original = {json.dumps(keep_original)}
obj = bpy.data.objects.get(name)
if obj is None:
    raise RuntimeError(f"Object not found: {{name}}")
if obj.type != 'MESH':
    raise RuntimeError("Object is not a mesh")
mesh = obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
islands = []
visited = set()
for v in bm.verts:
    if v in visited:
        continue
    stack = [v]
    island = []
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        island.append(cur)
        for e in cur.link_edges:
            other = e.other_vert(cur)
            if other not in visited:
                stack.append(other)
    if island:
        islands.append(island)
collection = bpy.context.scene.collection
created = []
for idx, island in enumerate(islands):
    new_bm = bmesh.new()
    vmap = {{}}
    for v in island:
        nv = new_bm.verts.new(v.co)
        vmap[v] = nv
    for e in bm.edges:
        if e.verts[0] in vmap and e.verts[1] in vmap:
            try:
                new_bm.edges.new((vmap[e.verts[0]], vmap[e.verts[1]]))
            except ValueError:
                pass
    for f in bm.faces:
        if all(v in vmap for v in f.verts):
            try:
                new_bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
    new_mesh = bpy.data.meshes.new(f"{{name}}_part{{idx+1}}")
    new_bm.to_mesh(new_mesh)
    new_bm.free()
    new_obj = bpy.data.objects.new(f"{{name}}_part{{idx+1}}", new_mesh)
    collection.objects.link(new_obj)
    created.append(new_obj.name)
if not keep_original:
    collection.objects.unlink(obj)
    if obj.data.users == 1:
        bpy.data.meshes.remove(obj.data)
    bpy.data.objects.remove(obj)
bpy.context.view_layer.objects.active = bpy.data.objects.get(created[0]) if created else None
result = created
"""
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to separate loose parts", is_error=True)
        return make_tool_result("Separated by loose parts", is_error=False)

    def _join_objects(args: Dict[str, Any]) -> Dict[str, Any]:
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
        data = bridge_request("/exec", payload={"code": code}, timeout=5.0)
        if not data.get("ok"):
            return make_tool_result(data.get("error") or "Failed to join objects", is_error=True)
        return make_tool_result(f"Joined {len(objects)} objects into {name}", is_error=False)

    reg(
        "blender-mesh-extrude",
        "Extrude mesh elements",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "distance": {"type": "number"},
                "axis": {"type": "string"},
                "selection_mode": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_extrude,
    )
    reg(
        "blender-mesh-inset",
        "Inset mesh faces",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "thickness": {"type": "number"},
                "depth": {"type": "number"},
                "selection_mode": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_inset,
    )
    reg(
        "blender-mesh-bevel",
        "Bevel mesh edges or vertices",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "offset": {"type": "number"},
                "segments": {"type": "integer"},
                "affect": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_bevel,
    )
    reg(
        "blender-mesh-subdivide",
        "Subdivide mesh edges",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "cuts": {"type": "integer"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_subdivide,
    )
    reg(
        "blender-mesh-merge-by-distance",
        "Merge vertices by distance",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "distance": {"type": "number"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_merge_by_distance,
    )
    reg(
        "blender-mesh-bisect",
        "Bisect a mesh with a plane",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "plane_point": {"type": "array"},
                "plane_normal": {"type": "array"},
                "clear_inner": {"type": "boolean"},
                "clear_outer": {"type": "boolean"},
                "use_fill": {"type": "boolean"},
            },
            "required": ["name", "plane_point", "plane_normal"],
            "additionalProperties": False,
        },
        _mesh_bisect,
    )
    reg(
        "blender-mesh-fill-holes",
        "Fill holes in a mesh",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "sides": {"type": "integer"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_fill_holes,
    )
    reg(
        "blender-mesh-bridge-boundary-loops",
        "Bridge two boundary edge loops",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "cuts": {"type": "integer"}, "twist": {"type": "integer"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_bridge_loops,
    )
    reg(
        "blender-mesh-delete",
        "Delete mesh elements",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "domain": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["name", "domain"],
            "additionalProperties": False,
        },
        _mesh_delete,
    )
    reg(
        "blender-mesh-dissolve-limited",
        "Dissolve limited by angle",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "angle_limit": {"type": "number"}, "delimit": {"type": "array"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_dissolve,
    )
    reg(
        "blender-mesh-loop-cut",
        "Loop cut along an axis",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "cuts": {"type": "integer"}, "axis": {"type": "string"}, "factor": {"type": "number"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _mesh_loop_cut,
    )
    reg(
        "blender-mesh-knife-plane",
        "Knife cut mesh with a plane",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "plane_point": {"type": "array"},
                "plane_normal": {"type": "array"},
                "clear_inner": {"type": "boolean"},
                "clear_outer": {"type": "boolean"},
                "use_fill": {"type": "boolean"},
            },
            "required": ["name", "plane_point", "plane_normal"],
            "additionalProperties": False,
        },
        _mesh_bisect,
    )
    reg(
        "blender-mesh-spin",
        "Spin mesh elements around an axis",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "axis": {"type": "string"},
                "angle_degrees": {"type": "number"},
                "steps": {"type": "integer"},
                "center": {"type": "array"},
            },
            "required": ["name", "axis"],
            "additionalProperties": False,
        },
        _mesh_spin,
    )
    reg(
        "blender-separate-by-loose-parts",
        "Separate mesh into loose parts",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "keep_original": {"type": "boolean"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _separate_loose,
    )
    reg(
        "blender-join-objects",
        "Join multiple mesh objects into one",
        {
            "type": "object",
            "properties": {"objects": {"type": "array"}, "name": {"type": "string"}},
            "required": ["objects", "name"],
            "additionalProperties": False,
        },
        _join_objects,
    )
