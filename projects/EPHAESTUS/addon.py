"""
Hephaestus Blender Addon
Bridge between Blender and the Hephaestus MCP Server
"""

bl_info = {
    "name": "Hephaestus MCP",
    "author": "Hephaestus Team",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Hephaestus",
    "description": "Advanced MCP bridge for Blender + LLM workflows",
    "category": "Interface",
}

import bpy
import bmesh
import socket
import threading
import json
import traceback
import tempfile
import os
import math
import random
import time
from mathutils import Vector
import queue
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, BoolProperty, StringProperty


# Global server state
server_socket = None
server_thread = None
server_running = False
client_handlers = []
command_queue = queue.Queue()


def resolve_output_dir(raw_dir):
    """
    Pick a writable directory for outputs, favoring user-provided or env override.
    Falls back to Blender temp or system temp if the target is not writable.
    """
    candidate = raw_dir or os.environ.get("HEPHAESTUS_REPORT_DIR")
    if candidate:
        try:
            resolved = os.path.abspath(os.path.expanduser(candidate))
            os.makedirs(resolved, exist_ok=True)
            return resolved
        except PermissionError:
            # Use a temp path if the configured location cannot be created
            pass

    try:
        fallback = bpy.app.tempdir or tempfile.gettempdir()
    except Exception:
        fallback = tempfile.gettempdir()
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _get_principled(material):
    """Ensure material has a Principled BSDF node wired to output"""
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    principled = nodes.get("Principled BSDF")
    if principled is None:
        principled = nodes.new(type="ShaderNodeBsdfPrincipled")

    output = nodes.get("Material Output")
    if output is None:
        output = nodes.new(type="ShaderNodeOutputMaterial")

    # Ensure BSDF is linked to surface
    has_surface_link = any(
        link.to_node == output and link.to_socket.name == "Surface"
        for link in principled.outputs["BSDF"].links
    )
    if not has_surface_link:
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return principled


def process_command_queue():
    """Process queued commands on the main thread (called by bpy.app.timers)."""
    try:
        cmd_type, params, done = command_queue.get_nowait()
    except queue.Empty:
        return 0.1  # check again soon
    try:
        response = execute_blender_command(cmd_type, params)
    except Exception as e:
        response = {"status": "error", "message": str(e)}
    done["response"] = response
    done["event"].set()
    return 0.0  # run again immediately until queue is empty


def _ensure_world_nodes():
    """Return world node references for environment setup."""
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("HephaestusWorld")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    bg = nodes.get("Background") or nodes.new(type="ShaderNodeBackground")
    output = nodes.get("World Output") or nodes.new(type="ShaderNodeOutputWorld")

    # Ensure connection
    if not any(link.to_node == output for link in bg.outputs["Background"].links):
        links.new(bg.outputs["Background"], output.inputs["Surface"])

    env_tex = nodes.get("Hephaestus Environment") or nodes.new(type="ShaderNodeTexEnvironment")
    env_tex.name = "Hephaestus Environment"

    mapping = nodes.get("Hephaestus Mapping") or nodes.new(type="ShaderNodeMapping")
    mapping.name = "Hephaestus Mapping"
    tex_coord = nodes.get("Hephaestus Texture Coord") or nodes.new(type="ShaderNodeTexCoord")
    tex_coord.name = "Hephaestus Texture Coord"

    # Wire texture coords to mapping to env tex to background
    if not any(link.to_node == mapping for link in tex_coord.outputs["Generated"].links):
        links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    if not any(link.to_node == env_tex for link in mapping.outputs["Vector"].links):
        links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    if not any(link.to_node == bg for link in env_tex.outputs["Color"].links):
        links.new(env_tex.outputs["Color"], bg.inputs["Color"])

    return world, mapping, env_tex, bg


def _get_mesh_object(object_name):
    """Return mesh object, make it active/selected."""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != 'MESH':
        raise ValueError(f"Object '{object_name}' is not a mesh")
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def _ensure_mode(obj, mode):
    """Ensure object is active and in requested mode."""
    bpy.context.view_layer.objects.active = obj
    if obj.mode != mode:
        bpy.ops.object.mode_set(mode=mode)


def _set_select_mode(mode_str):
    """Set selection mode (VERT/EDGE/FACE)."""
    mode_str = mode_str.upper()
    if mode_str not in {"VERT", "EDGE", "FACE"}:
        raise ValueError("Selection mode must be VERT/EDGE/FACE")
    bpy.ops.mesh.select_mode(type=mode_str)


def _select_indices(bm, mode_str, indices):
    """Apply selection to verts/edges/faces based on indices."""
    if indices is None:
        return
    _set_select_mode(mode_str)
    bpy.ops.mesh.select_all(action='DESELECT')
    if mode_str == "VERT":
        bm.verts.ensure_lookup_table()
        for idx in indices:
            if 0 <= idx < len(bm.verts):
                bm.verts[idx].select = True
    elif mode_str == "EDGE":
        bm.edges.ensure_lookup_table()
        for idx in indices:
            if 0 <= idx < len(bm.edges):
                bm.edges[idx].select = True
    elif mode_str == "FACE":
        bm.faces.ensure_lookup_table()
        for idx in indices:
            if 0 <= idx < len(bm.faces):
                bm.faces[idx].select = True
    bmesh.update_edit_mesh(bm.id_data)


def execute_blender_command(command_type, params):
    """
    Execute a command in Blender and return the result

    Args:
        command_type: Type of command to execute
        params: Command parameters

    Returns:
        Dict with status, result, and message
    """
    try:
        # Scene info
        if command_type == "get_scene_info":
            objects = []
            for obj in bpy.data.objects:
                objects.append({
                    "name": obj.name,
                    "type": obj.type,
                    "location": list(obj.location),
                    "rotation": list(obj.rotation_euler),
                    "scale": list(obj.scale),
                    "visible": not obj.hide_viewport,
                })

            collections = [c.name for c in bpy.data.collections]
            materials = [m.name for m in bpy.data.materials]
            active_obj = getattr(bpy.context, "active_object", None)

            result = {
                "objects": objects,
                "collections": collections,
                "materials": materials,
                "active_object": active_obj.name if active_obj else None,
            }
            return {"status": "success", "result": result, "message": "Scene info retrieved"}

        # Object info
        elif command_type == "get_object_info":
            obj_name = params.get("object_name")
            obj = bpy.data.objects.get(obj_name)

            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            result = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation_euler": list(obj.rotation_euler),
                "scale": list(obj.scale),
                "dimensions": list(obj.dimensions),
                "visible": not obj.hide_viewport,
                "parent": obj.parent.name if obj.parent else None,
                "children": [child.name for child in obj.children],
                "materials": [mat.name for mat in obj.data.materials] if hasattr(obj.data, 'materials') else [],
                "modifiers": [mod.name for mod in obj.modifiers],
            }
            return {"status": "success", "result": result, "message": f"Object info for '{obj_name}'"}

        # Viewport screenshot
        elif command_type == "get_viewport_screenshot":
            max_size = params.get("max_size", 800)
            shading = params.get("shading")  # e.g. "WIREFRAME", "SOLID"
            output_dir = resolve_output_dir(params.get("output_dir"))
            prefix = params.get("prefix", "hephaestus_viewport")

            # Save current render settings
            scene = bpy.context.scene
            original_file_format = scene.render.image_settings.file_format
            original_res_x = scene.render.resolution_x
            original_res_y = scene.render.resolution_y
            original_filepath = scene.render.filepath
            original_shading = None
            area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
            space = None
            if area:
                space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
                if space and hasattr(space, "shading"):
                    original_shading = space.shading.type

            # Calculate resolution maintaining aspect ratio
            if area:
                width = area.width
                height = area.height
                aspect = width / height

                if width > height:
                    res_x = min(width, max_size)
                    res_y = int(res_x / aspect)
                else:
                    res_y = min(height, max_size)
                    res_x = int(res_y * aspect)
            else:
                res_x = res_y = max_size

            # Setup for screenshot
            scene.render.image_settings.file_format = 'PNG'
            scene.render.resolution_x = res_x
            scene.render.resolution_y = res_y

            # Create temp file (unique name to avoid overwriting between views)
            base_dir = output_dir
            timestamp = int(time.time() * 1000)
            screenshot_path = os.path.join(base_dir, f"{prefix}_{timestamp}.png")
            scene.render.filepath = screenshot_path

            # Optional shading override
            if shading and space and hasattr(space, "shading"):
                try:
                    space.shading.type = shading
                except Exception:
                    pass

            # Render viewport
            bpy.ops.render.opengl(write_still=True)

            # Restore settings
            scene.render.image_settings.file_format = original_file_format
            scene.render.resolution_x = original_res_x
            scene.render.resolution_y = original_res_y
            scene.render.filepath = original_filepath
            if original_shading and space and hasattr(space, "shading"):
                try:
                    space.shading.type = original_shading
                except Exception:
                    pass

            result = {
                "path": screenshot_path,
                "width": res_x,
                "height": res_y,
            }
            return {"status": "success", "result": result, "message": "Screenshot captured"}

        # Capture view (optionally set camera + preset, then screenshot)
        elif command_type == "capture_view":
            max_size = params.get("max_size", 800)
            shading = params.get("shading")
            output_dir = resolve_output_dir(params.get("output_dir"))
            prefix = params.get("prefix", "view_capture")
            cam_name = params.get("camera_name")
            preset = params.get("preset")

            cam = None
            if cam_name:
                cam = bpy.data.objects.get(cam_name)
                if not cam or cam.type != 'CAMERA':
                    return {"status": "error", "message": f"Camera '{cam_name}' not found"}
                bpy.context.scene.camera = cam
            if preset and cam:
                # reuse preset logic
                pr = preset.lower()
                presets = {
                    "isometric": {"location": (8, -8, 8), "rotation": (math.radians(54.7356), 0, math.radians(45)), "orthographic": True, "scale": 15.0},
                    "top": {"location": (0, 0, 10), "rotation": (math.radians(90), 0, 0), "orthographic": True, "scale": 12.0},
                    "front": {"location": (0, -10, 0), "rotation": (math.radians(90), 0, math.radians(180))},
                    "product": {"location": (6, -6, 4), "rotation": (math.radians(60), 0, math.radians(45))},
                }
                if pr not in presets:
                    return {"status": "error", "message": f"Unknown camera preset '{preset}'"}
                cfg = presets[pr]
                cam.location = cfg["location"]
                cam.rotation_euler = cfg["rotation"]
                if cfg.get("orthographic"):
                    cam.data.type = 'ORTHO'
                    cam.data.ortho_scale = cfg.get("scale", 12.0)
                else:
                    cam.data.type = 'PERSP'

            # Reuse screenshot logic
            scene_ctx = bpy.context.scene
            original_file_format = scene_ctx.render.image_settings.file_format
            original_res_x = scene_ctx.render.resolution_x
            original_res_y = scene_ctx.render.resolution_y
            original_filepath = scene_ctx.render.filepath
            original_shading = None
            area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
            space = None
            if area:
                space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
                if space and hasattr(space, "shading"):
                    original_shading = space.shading.type

            if area:
                width = area.width
                height = area.height
                aspect = width / height
                if width > height:
                    res_x = min(width, max_size)
                    res_y = int(res_x / aspect)
                else:
                    res_y = min(height, max_size)
                    res_x = int(res_y * aspect)
            else:
                res_x = res_y = max_size

            scene_ctx.render.image_settings.file_format = 'PNG'
            scene_ctx.render.resolution_x = res_x
            scene_ctx.render.resolution_y = res_y

            unique_prefix = f"{prefix}_{int(bpy.app.timers.time() * 1000)}"
            filename = f"{unique_prefix}.png"
            filepath = os.path.join(output_dir, filename)
            scene_ctx.render.filepath = filepath

            if shading and space and hasattr(space, "shading"):
                space.shading.type = shading

            bpy.ops.render.opengl(write_still=True)

            scene_ctx.render.image_settings.file_format = original_file_format
            scene_ctx.render.resolution_x = original_res_x
            scene_ctx.render.resolution_y = original_res_y
            scene_ctx.render.filepath = original_filepath
            if space and hasattr(space, "shading") and original_shading:
                space.shading.type = original_shading

            return {"status": "success", "result": {"path": filepath, "width": res_x, "height": res_y}, "message": "View captured"}

        # Describe view: screenshot + info on objects
        elif command_type == "describe_view":
            from mathutils import Vector
            max_size = params.get("max_size", 800)
            shading = params.get("shading")
            output_dir = resolve_output_dir(params.get("output_dir"))
            prefix = params.get("prefix", "describe")
            cam_name = params.get("camera_name")
            preset = params.get("preset")
            object_names = params.get("object_names") or []

            # Select list
            if not object_names:
                sel = bpy.context.selected_objects
                object_names = [o.name for o in sel] if sel else []

            # Capture
            shot = execute_blender_command("capture_view", {
                "camera_name": cam_name,
                "preset": preset,
                "max_size": max_size,
                "shading": shading,
                "output_dir": output_dir,
                "prefix": prefix,
            })
            if shot.get("status") != "success":
                return shot

            infos = []
            for name in object_names:
                obj = bpy.data.objects.get(name)
                if not obj or not hasattr(obj.data, "vertices"):
                    continue
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = obj.evaluated_get(depsgraph)
                mesh = eval_obj.to_mesh()
                verts = [v.co.copy() for v in mesh.vertices]
                if not verts:
                    eval_obj.to_mesh_clear()
                    continue
                minv = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
                maxv = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
                local_size = maxv - minv
                local_center = (minv + maxv) / 2.0
                world_center = obj.matrix_world @ local_center
                eval_obj.to_mesh_clear()
                infos.append({
                    "name": name,
                    "bbox": {
                        "local_min": list(minv),
                        "local_max": list(maxv),
                        "local_size": list(local_size),
                        "local_center": list(local_center),
                        "world_center": list(world_center),
                    },
                    "location": list(obj.location),
                    "rotation_euler": list(obj.rotation_euler),
                    "scale": list(obj.scale),
                    "materials": [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else [],
                    "approx_volume_bbox": float(local_size.x * local_size.y * local_size.z),
                })

            return {
                "status": "success",
                "result": {"shot": shot.get("result"), "objects": infos},
                "message": "View described",
            }

        # Measure angle (ABC, angle at B)
        elif command_type == "measure_angle":
            from mathutils import Vector
            pa = params.get("point_a")
            pb = params.get("point_b")
            pc = params.get("point_c")
            if not (pa and pb and pc):
                return {"status": "error", "message": "Provide point_a, point_b, point_c"}
            va = Vector(pa) - Vector(pb)
            vc = Vector(pc) - Vector(pb)
            if va.length == 0 or vc.length == 0:
                return {"status": "error", "message": "Zero-length vector in angle measurement"}
            angle = va.angle(vc)  # radians
            return {"status": "success", "result": {"radians": float(angle), "degrees": float(angle * 180.0 / math.pi)}, "message": "Angle measured"}

        # Measure area (approx) and volume using evaluated mesh
        elif command_type == "measure_mesh":
            obj_name = params.get("object_name")
            mode = (params.get("mode") or "AREA").upper()  # AREA | VOLUME
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            if not hasattr(obj.data, "polygons"):
                return {"status": "error", "message": f"Object '{obj_name}' has no mesh data"}
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            area = sum(p.area for p in mesh.polygons)
            volume = mesh.calc_volume() if hasattr(mesh, "calc_volume") else None
            eval_obj.to_mesh_clear()
            if mode == "AREA":
                return {"status": "success", "result": {"area": float(area)}, "message": f"Area for '{obj_name}'"}
            elif mode == "VOLUME":
                return {"status": "success", "result": {"volume": float(volume) if volume is not None else None}, "message": f"Volume for '{obj_name}'"}
            else:
                return {"status": "error", "message": f"Unknown mode '{mode}' for measure_mesh"}

        # Set viewport shading (global 3D view)
        elif command_type == "set_viewport_shading":
            shading = params.get("shading")  # WIREFRAME, SOLID, MATERIAL, RENDERED
            area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
            if not area:
                return {"status": "error", "message": "VIEW_3D area not found"}
            space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
            if not space or not hasattr(space, "shading"):
                return {"status": "error", "message": "No shading on this area"}
            if shading:
                space.shading.type = shading
            return {"status": "success", "result": {"shading": shading}, "message": "Viewport shading set"}

        # Scatter on surface (simple random)
        elif command_type == "scatter_on_surface":
            import random
            from mathutils import Vector
            target = params.get("target_mesh")
            source = params.get("source_object")
            count = params.get("count")
            seed = params.get("seed", 0)
            jitter = params.get("jitter", 0.2)
            align_normal = params.get("align_normal", True)
            density = params.get("density")  # optional points per unit area
            max_points = params.get("max_points")

            tgt_obj = bpy.data.objects.get(target)
            src_obj = bpy.data.objects.get(source)
            if not tgt_obj or not src_obj:
                return {"status": "error", "message": "Target or source not found"}
            if tgt_obj.type != 'MESH':
                return {"status": "error", "message": "Target must be a mesh"}

            random.seed(seed)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = tgt_obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            verts = [v.co.copy() for v in mesh.vertices]
            if not verts:
                eval_obj.to_mesh_clear()
                return {"status": "error", "message": "No vertices on target"}

            # area estimation for density
            poly_area = sum(p.area for p in mesh.polygons) if mesh.polygons else 0.0
            if density and density > 0 and poly_area > 0:
                count_est = int(poly_area * density)
                if count_est <= 0:
                    count_est = 1
                if max_points:
                    count_est = min(count_est, int(max_points))
                count = count_est
            if count is None:
                count = 10
            count = int(count)

            created = []
            for i in range(count):
                dupli = src_obj.copy()
                dupli.data = src_obj.data.copy()
                bpy.context.collection.objects.link(dupli)
                v = random.choice(verts)
                offset = Vector((random.uniform(-jitter, jitter), random.uniform(-jitter, jitter), random.uniform(-jitter, jitter)))
                dupli.location = tgt_obj.matrix_world @ (v + offset)
                if align_normal and mesh.polygons:
                    poly = random.choice(mesh.polygons)
                    n = poly.normal
                    dupli.rotation_euler = n.to_track_quat('Z', 'Y').to_euler()
                created.append(dupli.name)
            eval_obj.to_mesh_clear()
            return {"status": "success", "result": {"objects": created, "area": poly_area}, "message": f"Scattered {len(created)} objects"}

        # Deformation / modifiers
        elif command_type == "add_simple_deform":
            obj_name = params.get("object_name")
            mode = params.get("mode", "BEND").upper()
            angle = params.get("angle", 0.5)
            factor = params.get("factor", 0.0)
            axis = params.get("axis", "Z").upper()
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="SimpleDeform", type='SIMPLE_DEFORM')
            mod.deform_method = mode
            mod.angle = angle
            mod.factor = factor
            mod.deform_axis = f"AXIS_{axis}"
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"SimpleDeform added to {obj_name}"}

        elif command_type == "add_solidify":
            obj_name = params.get("object_name")
            thickness = params.get("thickness", 0.05)
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            mod.thickness = thickness
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Solidify added to {obj_name}"}

        elif command_type == "add_decimate":
            obj_name = params.get("object_name")
            ratio = params.get("ratio", 0.5)
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
            mod.ratio = ratio
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Decimate added to {obj_name}"}

        elif command_type == "add_curve_deform":
            obj_name = params.get("object_name")
            curve_name = params.get("curve_name")
            obj = bpy.data.objects.get(obj_name)
            curve = bpy.data.objects.get(curve_name) if curve_name else None
            if not obj or not curve:
                return {"status": "error", "message": "Object or curve not found"}
            mod = obj.modifiers.new(name="CurveDeform", type='CURVE')
            mod.object = curve
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Curve deform added to {obj_name}"}

        elif command_type == "add_remesh":
            obj_name = params.get("object_name")
            voxel_size = params.get("voxel_size", 0.1)
            mode = (params.get("mode") or "VOXEL").upper()
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Remesh", type='REMESH')
            mod.mode = mode
            mod.voxel_size = voxel_size
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Remesh added to {obj_name}"}

        elif command_type == "apply_modifier":
            obj_name = params.get("object_name")
            mod_name = params.get("modifier_name")
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.get(mod_name)
            if not mod:
                return {"status": "error", "message": f"Modifier '{mod_name}' not found on {obj_name}"}
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            return {"status": "success", "message": f"Modifier '{mod_name}' applied on {obj_name}"}

        # Render preview (low samples)
        elif command_type == "render_preview":
            cam_name = params.get("camera_name")
            filepath = params.get("filepath")
            res_x = params.get("res_x", 800)
            res_y = params.get("res_y", 800)
            engine = params.get("engine", "BLENDER_EEVEE")
            samples = params.get("samples", 16)

            scene_ctx = bpy.context.scene
            cam = bpy.data.objects.get(cam_name) if cam_name else None
            if cam and cam.type == 'CAMERA':
                scene_ctx.camera = cam

            original_engine = scene_ctx.render.engine
            original_res_x = scene_ctx.render.resolution_x
            original_res_y = scene_ctx.render.resolution_y
            original_filepath = scene_ctx.render.filepath
            original_samples = getattr(scene_ctx, "eevee", None).taa_render_samples if hasattr(scene_ctx, "eevee") else None

            scene_ctx.render.engine = engine
            scene_ctx.render.resolution_x = res_x
            scene_ctx.render.resolution_y = res_y
            if hasattr(scene_ctx, "eevee") and engine == "BLENDER_EEVEE":
                scene_ctx.eevee.taa_render_samples = samples

            if filepath:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                scene_ctx.render.filepath = filepath
            else:
                scene_ctx.render.filepath = bpy.app.tempdir + "render_preview.png"

            bpy.ops.render.render(write_still=True)

            scene_ctx.render.engine = original_engine
            scene_ctx.render.resolution_x = original_res_x
            scene_ctx.render.resolution_y = original_res_y
            if hasattr(scene_ctx, "eevee") and original_samples is not None:
                scene_ctx.eevee.taa_render_samples = original_samples
            scene_ctx.render.filepath = original_filepath

            return {"status": "success", "result": {"path": scene_ctx.render.filepath}, "message": "Render preview done"}

        # Measure distance
        elif command_type == "measure_distance":
            from mathutils import Vector
            obj_a = params.get("object_a")
            obj_b = params.get("object_b")
            point_a = params.get("point_a")
            point_b = params.get("point_b")

            if obj_a and obj_b:
                oa = bpy.data.objects.get(obj_a)
                ob = bpy.data.objects.get(obj_b)
                if not oa or not ob:
                    return {"status": "error", "message": "Objects not found"}
                pa = oa.matrix_world.translation
                pb = ob.matrix_world.translation
            elif point_a and point_b:
                pa = Vector(point_a)
                pb = Vector(point_b)
            else:
                return {"status": "error", "message": "Provide object_a/object_b or point_a/point_b"}

            dist = (pa - pb).length
            return {"status": "success", "result": {"distance": float(dist)}, "message": f"Distance: {dist:.4f}"}

        # BBox info
        elif command_type == "bbox_info":
            from mathutils import Vector
            obj_name = params.get("object_name")
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            if not hasattr(obj.data, "vertices"):
                return {"status": "error", "message": f"Object '{obj_name}' has no geometry"}

            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            verts = [v.co.copy() for v in mesh.vertices]
            if not verts:
                eval_obj.to_mesh_clear()
                return {"status": "error", "message": f"No vertices on '{obj_name}'"}

            minv = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
            maxv = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
            local_size = maxv - minv
            local_center = (minv + maxv) / 2.0
            world_center = obj.matrix_world @ local_center

            eval_obj.to_mesh_clear()
            return {
                "status": "success",
                "result": {
                    "local_min": list(minv),
                    "local_max": list(maxv),
                    "local_size": list(local_size),
                    "local_center": list(local_center),
                    "world_center": list(world_center),
                },
                "message": f"BBox for '{obj_name}'"
            }

        # Execute arbitrary Python code
        elif command_type == "execute_code":
            code = params.get("code", "")
            if not code:
                return {"status": "error", "message": "No code provided"}

            # Execute in local namespace
            local_vars = {"bpy": bpy, "result": None}
            exec(code, {"__builtins__": __builtins__, "bpy": bpy}, local_vars)

            result = local_vars.get("result")
            return {"status": "success", "result": result, "message": "Code executed"}

        # Create collection
        elif command_type == "create_collection":
            name = params.get("name")
            parent_name = params.get("parent")
            color = params.get("color")

            # Create collection
            collection = bpy.data.collections.new(name)

            # Add to parent or scene
            if parent_name:
                parent = bpy.data.collections.get(parent_name)
                if parent:
                    parent.children.link(collection)
                else:
                    bpy.context.scene.collection.children.link(collection)
            else:
                bpy.context.scene.collection.children.link(collection)

            # Set color tag
            if color:
                collection.color_tag = color

            return {"status": "success", "result": {"name": name}, "message": f"Collection '{name}' created"}

        # Move to collection
        elif command_type == "move_to_collection":
            object_names = params.get("object_names", [])
            collection_name = params.get("collection_name")

            collection = bpy.data.collections.get(collection_name)
            if not collection:
                return {"status": "error", "message": f"Collection '{collection_name}' not found"}

            moved = []
            for obj_name in object_names:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    # Remove from all collections
                    for coll in obj.users_collection:
                        coll.objects.unlink(obj)
                    # Add to target collection
                    collection.objects.link(obj)
                    moved.append(obj_name)

            return {"status": "success", "result": {"moved": moved}, "message": f"Moved {len(moved)} objects"}

        # Get collection tree
        elif command_type == "get_collection_tree":
            def build_tree(collection):
                return {
                    "name": collection.name,
                    "objects": [obj.name for obj in collection.objects],
                    "children": [build_tree(child) for child in collection.children]
                }

            tree = build_tree(bpy.context.scene.collection)
            return {"status": "success", "result": tree, "message": "Collection tree retrieved"}

        # Batch select
        elif command_type == "batch_select":
            import re
            pattern = params.get("pattern")
            object_type = params.get("object_type")

            regex = re.compile(pattern)
            selected = []

            for obj in bpy.data.objects:
                if regex.search(obj.name):
                    if object_type is None or obj.type == object_type:
                        obj.select_set(True)
                        selected.append(obj.name)

            return {"status": "success", "result": {"selected": selected}, "message": f"Selected {len(selected)} objects"}

        # Create primitive
        elif command_type == "create_primitive":
            prim_type = params.get("type", "cube").lower()
            name = params.get("name")
            location = params.get("location", (0, 0, 0))
            scale = params.get("scale", (1, 1, 1))
            rotation = params.get("rotation", (0, 0, 0))

            # Create primitive based on type
            if prim_type == "cube":
                bpy.ops.mesh.primitive_cube_add(location=location)
            elif prim_type in ["sphere", "uv_sphere"]:
                bpy.ops.mesh.primitive_uv_sphere_add(location=location)
            elif prim_type == "ico_sphere":
                bpy.ops.mesh.primitive_ico_sphere_add(location=location)
            elif prim_type == "cylinder":
                bpy.ops.mesh.primitive_cylinder_add(location=location)
            elif prim_type == "cone":
                bpy.ops.mesh.primitive_cone_add(location=location)
            elif prim_type == "plane":
                bpy.ops.mesh.primitive_plane_add(location=location)
            elif prim_type == "torus":
                bpy.ops.mesh.primitive_torus_add(location=location)
            elif prim_type == "monkey":
                bpy.ops.mesh.primitive_monkey_add(location=location)
            else:
                return {"status": "error", "message": f"Unknown primitive type: {prim_type}"}

            obj = getattr(bpy.context, "active_object", None)
            if not obj and getattr(bpy.context, "selected_objects", None):
                # Fallback: last selected after operator
                if bpy.context.selected_objects:
                    obj = bpy.context.selected_objects[-1]
            if not obj and getattr(bpy.context, "view_layer", None):
                obj = getattr(bpy.context.view_layer.objects, "active", None)

            if not obj:
                return {"status": "error", "message": "Failed to get created object (no active object)"}

            if name:
                try:
                    obj.name = name
                except Exception:
                    # Ignore naming failures in restricted contexts
                    pass
            # Force transform application to match requested values
            obj.location = location
            obj.scale = scale
            obj.rotation_euler = rotation

            result = {"name": obj.name, "type": obj.type, "location": list(obj.location)}
            return {"status": "success", "result": result, "message": f"Created {prim_type}"}

        # Delete object
        elif command_type == "delete_object":
            obj_name = params.get("object_name")
            obj = bpy.data.objects.get(obj_name)

            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            bpy.data.objects.remove(obj, do_unlink=True)
            return {"status": "success", "message": f"Deleted '{obj_name}'"}

        # Transform object
        elif command_type == "transform_object":
            obj_name = params.get("object_name")
            obj = bpy.data.objects.get(obj_name)

            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            if "location" in params:
                obj.location = params["location"]
            if "rotation" in params:
                obj.rotation_euler = params["rotation"]
            if "scale" in params:
                obj.scale = params["scale"]

            result = {
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale)
            }
            return {"status": "success", "result": result, "message": f"Transformed '{obj_name}'"}

        # Duplicate object
        elif command_type == "duplicate_object":
            obj_name = params.get("object_name")
            obj = bpy.data.objects.get(obj_name)

            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            # Duplicate object
            new_obj = obj.copy()
            if obj.data:
                new_obj.data = obj.data.copy()

            # Link to scene
            bpy.context.collection.objects.link(new_obj)

            # Set name
            if "new_name" in params:
                new_obj.name = params["new_name"]

            # Apply location offset
            if "location_offset" in params:
                offset = params["location_offset"]
                new_obj.location = (
                    obj.location.x + offset[0],
                    obj.location.y + offset[1],
                    obj.location.z + offset[2]
                )

            result = {"name": new_obj.name, "location": list(new_obj.location)}
            return {"status": "success", "result": result, "message": f"Duplicated '{obj_name}'"}

        # Parent object
        elif command_type == "parent_object":
            child_name = params.get("child_name")
            parent_name = params.get("parent_name")
            keep_transform = params.get("keep_transform", True)

            child = bpy.data.objects.get(child_name)
            parent = bpy.data.objects.get(parent_name)

            if not child:
                return {"status": "error", "message": f"Child object '{child_name}' not found"}
            if not parent:
                return {"status": "error", "message": f"Parent object '{parent_name}' not found"}

            # Set parent
            child.parent = parent
            if keep_transform:
                child.matrix_parent_inverse = parent.matrix_world.inverted()

            return {"status": "success", "message": f"Parented '{child_name}' to '{parent_name}'"}

        # Array objects
        elif command_type == "array_objects":
            obj_name = params.get("object_name")
            count = params.get("count", 1)
            offset = params.get("offset", (2, 0, 0))

            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            created = []
            for i in range(count):
                # Duplicate
                new_obj = obj.copy()
                if obj.data:
                    new_obj.data = obj.data.copy()

                bpy.context.collection.objects.link(new_obj)
                new_obj.name = f"{obj_name}_array_{i+1}"

                # Apply offset
                new_obj.location = (
                    obj.location.x + offset[0] * (i + 1),
                    obj.location.y + offset[1] * (i + 1),
                    obj.location.z + offset[2] * (i + 1)
                )
                created.append(new_obj.name)

            result = {"created": created}
            return {"status": "success", "result": result, "message": f"Created {len(created)} array items"}

        # Select object
        elif command_type == "select_object":
            obj_name = params.get("object_name")
            deselect_others = params.get("deselect_others", True)

            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}

            if deselect_others:
                bpy.ops.object.select_all(action='DESELECT')

            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            return {"status": "success", "message": f"Selected '{obj_name}'"}

        # Rename object
        elif command_type == "rename_object":
            old_name = params.get("old_name")
            new_name = params.get("new_name")

            obj = bpy.data.objects.get(old_name)
            if not obj:
                return {"status": "error", "message": f"Object '{old_name}' not found"}

            obj.name = new_name
            return {"status": "success", "message": f"Renamed to '{new_name}'"}

        # Get selected objects
        elif command_type == "get_selected_objects":
            selected = [obj.name for obj in bpy.context.selected_objects]
            result = {"selected": selected, "count": len(selected)}
            return {"status": "success", "result": result, "message": f"Found {len(selected)} selected"}

        # Snap to grid
        elif command_type == "snap_to_grid":
            step = params.get("step", 1.0)
            names = params.get("object_names", [])
            if names:
                targets = [bpy.data.objects.get(n) for n in names if bpy.data.objects.get(n)]
            else:
                targets = list(getattr(bpy.context, "selected_objects", []))
            snapped = []
            for obj in targets:
                obj.location.x = round(obj.location.x / step) * step
                obj.location.y = round(obj.location.y / step) * step
                obj.location.z = round(obj.location.z / step) * step
                snapped.append(obj.name)
            return {"status": "success", "result": {"snapped": snapped}, "message": f"Snapped {len(snapped)} object(s)"}

        # Align objects
        elif command_type == "align_objects":
            target = params.get("target", "X")
            mode = params.get("mode", "center")
            reference = params.get("reference")
            names = params.get("object_names", [])
            axis_idx = {"X": 0, "Y": 1, "Z": 2}.get(target.upper(), 0)

            if names:
                objs = [bpy.data.objects.get(n) for n in names if bpy.data.objects.get(n)]
            else:
                objs = list(getattr(bpy.context, "selected_objects", []))

            if not objs:
                return {"status": "error", "message": "No objects to align"}

            coords = [obj.location[axis_idx] for obj in objs]
            if mode == "value" and reference is not None:
                ref = reference
            elif mode == "min":
                ref = min(coords)
            elif mode == "max":
                ref = max(coords)
            else:  # center or default
                ref = sum(coords) / len(coords)

            for obj in objs:
                loc = list(obj.location)
                loc[axis_idx] = ref
                obj.location = loc

            return {"status": "success", "result": {"aligned": [o.name for o in objs], "value": ref}, "message": f"Aligned {len(objs)} object(s) on {target}"}

        # Scatter along curve
        elif command_type == "scatter_along_curve":
            from mathutils import Vector
            source_name = params.get("source_object")
            curve_name = params.get("curve_name")
            count = params.get("count", 1)
            jitter = params.get("jitter")

            src = bpy.data.objects.get(source_name)
            curve = bpy.data.objects.get(curve_name)
            if not src:
                return {"status": "error", "message": f"Source object '{source_name}' not found"}
            if not curve or curve.type != 'CURVE':
                return {"status": "error", "message": f"Curve '{curve_name}' not found or is not a curve"}
            if count < 1:
                return {"status": "error", "message": "Count must be at least 1"}

            # Get evaluated points along the curve
            points = []
            depsgraph = bpy.context.evaluated_depsgraph_get()
            curve_eval = curve.evaluated_get(depsgraph)
            for spline in curve_eval.data.splines:
                for p in spline.points:
                    points.append(curve.matrix_world @ Vector(p.co.xyz))
                for p in getattr(spline, "bezier_points", []):
                    points.append(curve.matrix_world @ p.co)
            if len(points) < 2:
                return {"status": "error", "message": "Curve has insufficient points"}

            created = []
            for i in range(count):
                t = i / max(1, count - 1)
                idx = t * (len(points) - 1)
                i0 = int(math.floor(idx))
                i1 = min(i0 + 1, len(points) - 1)
                alpha = idx - i0
                pos = points[i0].lerp(points[i1], alpha)

                if jitter:
                    pos += Vector(jitter)

                new_obj = src.copy()
                if src.data:
                    new_obj.data = src.data.copy()
                new_obj.location = pos
                bpy.context.collection.objects.link(new_obj)
                created.append(new_obj.name)

            return {"status": "success", "result": {"created": created}, "message": f"Scattered {len(created)} objects along curve"}

        # Create road (with optional sidewalks)
        elif command_type == "create_road":
            width = params.get("width", 6.0)
            length = params.get("length", 20.0)
            add_sidewalk = params.get("add_sidewalk", True)
            sidewalk_width = params.get("sidewalk_width", 1.5)
            sidewalk_height = params.get("sidewalk_height", 0.15)

            def make_mesh(name, verts, faces):
                mesh = bpy.data.meshes.new(name)
                mesh.from_pydata(verts, [], faces)
                mesh.update()
                obj = bpy.data.objects.new(name, mesh)
                bpy.context.collection.objects.link(obj)
                return obj

            half_w = width / 2
            half_l = length / 2
            road = make_mesh("Road", [(-half_l, -half_w, 0), (half_l, -half_w, 0), (half_l, half_w, 0), (-half_l, half_w, 0)], [(0, 1, 2, 3)])

            sidewalks = []
            if add_sidewalk:
                sw = sidewalk_width
                sh = sidewalk_height
                # Left sidewalk
                verts = [
                    (-half_l, -half_w - sw, 0), (half_l, -half_w - sw, 0), (half_l, -half_w, 0), (-half_l, -half_w, 0),
                    (-half_l, -half_w - sw, sh), (half_l, -half_w - sw, sh), (half_l, -half_w, sh), (-half_l, -half_w, sh),
                ]
                faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
                sidewalks.append(make_mesh("Sidewalk_Left", verts, faces))
                # Right sidewalk
                verts = [
                    (-half_l, half_w, 0), (half_l, half_w, 0), (half_l, half_w + sw, 0), (-half_l, half_w + sw, 0),
                    (-half_l, half_w, sh), (half_l, half_w, sh), (half_l, half_w + sw, sh), (-half_l, half_w + sw, sh),
                ]
                sidewalks.append(make_mesh("Sidewalk_Right", verts, faces))

            created = [road.name] + [s.name for s in sidewalks]
            return {"status": "success", "result": {"created": created}, "message": "Road created"}

        # Repeat facade
        elif command_type == "repeat_facade":
            base_name = params.get("base_object")
            floors = params.get("floors", 5)
            bays = params.get("bays", 4)
            floor_height = params.get("floor_height", 3.0)
            bay_width = params.get("bay_width", 3.0)

            base = bpy.data.objects.get(base_name)
            if not base:
                return {"status": "error", "message": f"Base object '{base_name}' not found"}
            if floors < 1 or bays < 1:
                return {"status": "error", "message": "Floors and bays must be >= 1"}

            created = []
            for f in range(floors):
                for b in range(bays):
                    dup = base.copy()
                    if base.data:
                        dup.data = base.data.copy()
                    dup.location = (
                        base.location.x + b * bay_width,
                        base.location.y,
                        base.location.z + f * floor_height,
                    )
                    dup.name = f"{base.name}_f{f+1}_b{b+1}"
                    bpy.context.collection.objects.link(dup)
                    created.append(dup.name)

            return {"status": "success", "result": {"created": created}, "message": f"Created facade with {len(created)} elements"}

        # Macro city block
        elif command_type == "macro_city_block":
            style = params.get("style", "modern")
            buildings = params.get("buildings", 6)
            lamps_per_side = params.get("lamps_per_side", 6)

            # Ground
            bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
            ground = getattr(bpy.context, "active_object", None)
            if ground:
                ground.name = "Ground"

            # Road with sidewalks
            road_resp = execute_blender_command("create_road", {
                "width": 8.0,
                "length": 30.0,
                "add_sidewalk": True,
                "sidewalk_width": 1.5,
                "sidewalk_height": 0.15
            })

            created_buildings = []
            for i in range(buildings):
                bpy.ops.mesh.primitive_cube_add(location=(random.uniform(-10, 10), random.uniform(-6, 6), 0))
                obj = getattr(bpy.context, "active_object", None)
                if obj:
                    obj.scale = (1.5, 1.5, random.uniform(3, 10))
                    obj.location.z = obj.scale.z
                    obj.name = f"Building_{i+1}"
                    created_buildings.append(obj.name)

            # Simple lamps along X
            lamp_objs = []
            for side in (-1, 1):
                for i in range(lamps_per_side):
                    x = -12 + i * (24 / max(1, lamps_per_side - 1))
                    y = side * 6
                    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=4, location=(x, y, 2))
                    pole = getattr(bpy.context, "active_object", None)
                    if pole:
                        pole.name = f"LampPole_{side}_{i}"
                        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(x, y, 4.1))
                        head = getattr(bpy.context, "active_object", None)
                        if head:
                            head.name = f"LampHead_{side}_{i}"
                            lamp_objs.extend([pole.name, head.name])

            return {
                "status": "success",
                "result": {
                    "road": road_resp.get("result") if isinstance(road_resp, dict) else None,
                    "buildings": created_buildings,
                    "lamps": lamp_objs,
                },
                "message": "City block created"
            }

        # Camera tools
        elif command_type == "create_camera":
            name = params.get("name")
            location = params.get("location", (0, 0, 0))
            rotation = params.get("rotation")

            cam_data = bpy.data.cameras.new(name=name)
            cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
            bpy.context.collection.objects.link(cam_obj)
            cam_obj.location = location
            if rotation is not None:
                cam_obj.rotation_euler = rotation

            return {"status": "success", "result": {"name": cam_obj.name}, "message": f"Camera '{cam_obj.name}' created"}

        elif command_type == "set_active_camera":
            camera_name = params.get("camera_name")
            cam = bpy.data.objects.get(camera_name)
            if not cam or cam.type != 'CAMERA':
                return {"status": "error", "message": f"Camera '{camera_name}' not found"}
            bpy.context.scene.camera = cam
            return {"status": "success", "message": f"Active camera set to '{camera_name}'"}

        elif command_type == "point_camera_at":
            camera_name = params.get("camera_name")
            cam = bpy.data.objects.get(camera_name)
            if not cam or cam.type != 'CAMERA':
                return {"status": "error", "message": f"Camera '{camera_name}' not found"}

            target_obj_name = params.get("target_object")
            target_location = params.get("target_location")

            target_obj = None
            if target_obj_name:
                target_obj = bpy.data.objects.get(target_obj_name)
                if not target_obj:
                    return {"status": "error", "message": f"Target object '{target_obj_name}' not found"}
            elif target_location is not None:
                empty = bpy.data.objects.new(name="HephaestusTarget", object_data=None)
                bpy.context.collection.objects.link(empty)
                empty.location = target_location
                target_obj = empty
            else:
                return {"status": "error", "message": "No target specified for camera"}

            # Clear existing track constraints
            for c in cam.constraints:
                if c.type == 'TRACK_TO':
                    cam.constraints.remove(c)

            constraint = cam.constraints.new(type='TRACK_TO')
            constraint.target = target_obj
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

            return {"status": "success", "message": f"Camera '{camera_name}' pointed", "result": {"target": target_obj.name}}

        elif command_type == "set_camera_orthographic":
            camera_name = params.get("camera_name")
            scale = params.get("scale", 10.0)
            cam = bpy.data.objects.get(camera_name)
            if not cam or cam.type != 'CAMERA':
                return {"status": "error", "message": f"Camera '{camera_name}' not found"}
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = scale
            return {"status": "success", "message": f"Camera '{camera_name}' set to orthographic", "result": {"scale": scale}}

        elif command_type == "set_camera_preset":
            camera_name = params.get("camera_name")
            preset = (params.get("preset") or "").lower()
            cam = bpy.data.objects.get(camera_name)
            if not cam or cam.type != 'CAMERA':
                return {"status": "error", "message": f"Camera '{camera_name}' not found"}

            presets = {
                "isometric": {
                    "location": (8, -8, 8),
                    "rotation": (math.radians(54.7356), 0, math.radians(45)),
                    "orthographic": True,
                    "scale": 15.0,
                },
                "top": {
                    "location": (0, 0, 10),
                    "rotation": (math.radians(90), 0, 0),
                    "orthographic": True,
                    "scale": 12.0,
                },
                "front": {
                    "location": (0, -10, 0),
                    "rotation": (math.radians(90), 0, math.radians(180)),
                },
                "product": {
                    "location": (6, -6, 4),
                    "rotation": (math.radians(60), 0, math.radians(45)),
                },
            }
            if preset not in presets:
                return {"status": "error", "message": f"Unknown camera preset '{preset}'"}

            cfg = presets[preset]
            cam.location = cfg["location"]
            cam.rotation_euler = cfg["rotation"]
            if cfg.get("orthographic"):
                cam.data.type = 'ORTHO'
                cam.data.ortho_scale = cfg.get("scale", cam.data.ortho_scale)

            return {"status": "success", "message": f"Applied camera preset '{preset}'", "result": cfg}

        elif command_type == "create_camera_rig":
            rig_type = (params.get("rig_type") or "turntable").lower()
            target = params.get("target")
            if rig_type != "turntable":
                return {"status": "error", "message": f"Unsupported rig type '{rig_type}'"}

            rig_empty = bpy.data.objects.new("HephaestusCameraRig", None)
            bpy.context.collection.objects.link(rig_empty)

            cam_data = bpy.data.cameras.new(name="HephaestusRigCamera")
            cam_obj = bpy.data.objects.new(name="HephaestusRigCamera", object_data=cam_data)
            bpy.context.collection.objects.link(cam_obj)
            cam_obj.parent = rig_empty
            cam_obj.location = (0, -6, 2)

            if target:
                tgt = bpy.data.objects.get(target)
                if tgt:
                    constraint = cam_obj.constraints.new(type='TRACK_TO')
                    constraint.target = tgt
                    constraint.track_axis = 'TRACK_NEGATIVE_Z'
                    constraint.up_axis = 'UP_Y'

            return {"status": "success", "result": {"rig": rig_empty.name, "camera": cam_obj.name}, "message": "Camera rig created"}

        # Modifiers
        elif command_type == "add_modifier":
            object_name = params.get("object_name")
            modifier_type = (params.get("modifier_type") or "").upper()
            if modifier_type == "SUBDIVISION":
                modifier_type = "SUBSURF"
            mod_name = params.get("name") or modifier_type.title()
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}

            modifier = obj.modifiers.new(name=mod_name, type=modifier_type)
            if modifier.type == 'ARRAY':
                modifier.count = params.get("count", modifier.count)
                if "offset" in params:
                    modifier.relative_offset_displace = params["offset"]
            elif modifier.type == 'MIRROR':
                modifier.use_axis[0] = params.get("use_x", True)
                modifier.use_axis[1] = params.get("use_y", False)
                modifier.use_axis[2] = params.get("use_z", False)
            elif modifier.type == 'SUBSURF':
                modifier.levels = params.get("levels", modifier.levels)
                modifier.render_levels = params.get("render_levels", modifier.render_levels)
            elif modifier.type == 'BOOLEAN':
                modifier.operation = params.get("operation", modifier.operation)
                target_name = params.get("object")
                if target_name:
                    target_obj = bpy.data.objects.get(target_name)
                    if not target_obj:
                        return {"status": "error", "message": f"Boolean target '{target_name}' not found"}
                    modifier.object = target_obj
            elif modifier.type == 'SOLIDIFY':
                if "thickness" in params:
                    modifier.thickness = params["thickness"]
            elif modifier.type == 'BEVEL':
                if "width" in params:
                    modifier.width = params["width"]
                if "segments" in params:
                    modifier.segments = params["segments"]

            return {"status": "success", "result": {"name": modifier.name}, "message": f"Modifier '{modifier.name}' added"}

        elif command_type == "modify_modifier":
            object_name = params.get("object_name")
            modifier_name = params.get("modifier_name")
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return {"status": "error", "message": f"Modifier '{modifier_name}' not found on '{object_name}'"}

            for key, value in params.items():
                if key in {"object_name", "modifier_name"}:
                    continue
                if hasattr(mod, key):
                    setattr(mod, key, value)

            return {"status": "success", "message": f"Modifier '{modifier_name}' updated"}

        elif command_type == "apply_modifier":
            object_name = params.get("object_name")
            modifier_name = params.get("modifier_name")
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return {"status": "error", "message": f"Modifier '{modifier_name}' not found on '{object_name}'"}

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=modifier_name)

            return {"status": "success", "message": f"Modifier '{modifier_name}' applied"}

        elif command_type == "remove_modifier":
            object_name = params.get("object_name")
            modifier_name = params.get("modifier_name")
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return {"status": "error", "message": f"Modifier '{modifier_name}' not found on '{object_name}'"}
            obj.modifiers.remove(mod)
            return {"status": "success", "message": f"Modifier '{modifier_name}' removed"}

        elif command_type == "boolean_operation":
            object_a = params.get("object_a")
            object_b = params.get("object_b")
            operation = params.get("operation", "DIFFERENCE")

            obj_a = bpy.data.objects.get(object_a)
            obj_b = bpy.data.objects.get(object_b)
            if not obj_a or not obj_b:
                return {"status": "error", "message": "Boolean objects not found"}
            if obj_a.type != 'MESH' or obj_b.type != 'MESH':
                return {"status": "error", "message": "Boolean requires two mesh objects"}

            mod = obj_a.modifiers.new(name=f"Boolean_{obj_b.name}", type='BOOLEAN')
            mod.object = obj_b
            mod.operation = operation
            return {"status": "success", "message": f"Boolean {operation} added on '{object_a}' with '{object_b}'", "result": {"modifier": mod.name}}

        # Bevel helper
        elif command_type == "add_bevel":
            obj_name = params.get("object_name")
            width = params.get("width", 0.02)
            segments = params.get("segments", 2)
            limit_method = params.get("limit_method", "ANGLE")
            angle_limit = params.get("angle_limit", 0.785)
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Bevel", type='BEVEL')
            mod.width = width
            mod.segments = segments
            mod.limit_method = limit_method
            mod.angle_limit = angle_limit
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Bevel added to '{obj_name}'"}

        # Mirror helper
        elif command_type == "add_mirror":
            obj_name = params.get("object_name")
            axes = params.get("axes", (True, False, False))
            merge = params.get("merge", True)
            merge_threshold = params.get("merge_threshold", 0.001)
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Mirror", type='MIRROR')
            mod.use_axis = axes
            mod.use_mirror_merge = merge
            mod.merge_threshold = merge_threshold
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Mirror added to '{obj_name}'"}

        # Array helper
        elif command_type == "add_array":
            obj_name = params.get("object_name")
            count = params.get("count", 3)
            offset = params.get("offset", (1.0, 0.0, 0.0))
            relative = params.get("relative", True)
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Array", type='ARRAY')
            mod.count = count
            mod.use_relative_offset = relative
            mod.relative_offset_displace = offset
            mod.use_constant_offset = not relative
            mod.constant_offset_displace = offset
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Array added to '{obj_name}'"}

        # Subdivision helper
        elif command_type == "add_subsurf":
            obj_name = params.get("object_name")
            levels = params.get("levels", 2)
            render_levels = params.get("render_levels")
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                return {"status": "error", "message": f"Object '{obj_name}' not found"}
            mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
            mod.levels = levels
            if render_levels is not None:
                mod.render_levels = render_levels
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Subsurf added to '{obj_name}'"}

        # Boolean helper (modifier)
        elif command_type == "add_boolean":
            obj_name = params.get("object_name")
            target = params.get("target")
            operation = params.get("operation", "DIFFERENCE")
            obj = bpy.data.objects.get(obj_name)
            tgt = bpy.data.objects.get(target) if target else None
            if not obj or not tgt:
                return {"status": "error", "message": "Boolean objects not found"}
            mod = obj.modifiers.new(name=f"Boolean_{tgt.name}", type='BOOLEAN')
            mod.object = tgt
            mod.operation = operation
            return {"status": "success", "result": {"modifier": mod.name}, "message": f"Boolean {operation} added to '{obj_name}' with '{target}'"}

        # Lighting
        elif command_type == "create_light":
            light_type = params.get("type", "POINT").upper()
            name = params.get("name") or f"{light_type}_Light"
            location = params.get("location", (0, 0, 0))
            energy = params.get("energy", 100.0)
            color = params.get("color")

            light_data = bpy.data.lights.new(name=name, type=light_type)
            light_data.energy = energy
            if color:
                light_data.color = color[:3]
            light_obj = bpy.data.objects.new(name=name, object_data=light_data)
            bpy.context.collection.objects.link(light_obj)
            light_obj.location = location

            return {"status": "success", "result": {"name": light_obj.name}, "message": f"Light '{light_obj.name}' created"}

        elif command_type == "set_light_property":
            light_name = params.get("light_name")
            property_name = params.get("property_name")
            value = params.get("value")

            light_obj = bpy.data.objects.get(light_name)
            if not light_obj or light_obj.type != 'LIGHT':
                return {"status": "error", "message": f"Light '{light_name}' not found"}

            light = light_obj.data
            if property_name == "energy":
                light.energy = value
            elif property_name == "color":
                light.color = value[:3]
            elif property_name == "size":
                if light.type == 'AREA':
                    light.size = value
                else:
                    light.shadow_soft_size = value
            elif property_name == "angle":
                if light.type == 'SPOT':
                    light.spot_size = value
            else:
                return {"status": "error", "message": f"Unsupported light property '{property_name}'"}

            return {"status": "success", "message": f"Set '{property_name}' on '{light_name}'"}

        elif command_type == "apply_lighting_preset":
            preset_data = params.get("preset_data") or {}
            lights = preset_data.get("lights", [])
            created = []
            for light_cfg in lights:
                lt = light_cfg.get("type", "POINT").upper()
                name = light_cfg.get("name", f"{lt}_Light")
                location = light_cfg.get("location", (0, 0, 0))
                energy = light_cfg.get("energy", 100.0)
                color = light_cfg.get("color")
                size = light_cfg.get("size")
                angle = light_cfg.get("angle")

                light_data = bpy.data.lights.new(name=name, type=lt)
                light_data.energy = energy
                if color:
                    light_data.color = color[:3]
                if lt == 'AREA' and size:
                    light_data.size = size
                if lt == 'SPOT' and angle:
                    light_data.spot_size = angle

                light_obj = bpy.data.objects.new(name=name, object_data=light_data)
                bpy.context.collection.objects.link(light_obj)
                light_obj.location = location
                created.append(light_obj.name)

            return {"status": "success", "result": {"lights": created}, "message": f"Created {len(created)} lights from preset"}

        elif command_type == "set_world_hdri":
            hdri_path = params.get("hdri_path")
            rotation = params.get("rotation", 0.0)
            strength = params.get("strength", 1.0)

            world, mapping, env_tex, bg = _ensure_world_nodes()
            if not os.path.exists(hdri_path):
                return {"status": "error", "message": f"HDRI '{hdri_path}' not found"}

            env_tex.image = bpy.data.images.load(hdri_path, check_existing=True)
            mapping.inputs["Rotation"].default_value[2] = rotation
            bg.inputs["Strength"].default_value = strength

            return {"status": "success", "message": "HDRI applied", "result": {"hdri_path": hdri_path}}

        # Clear scene
        elif command_type == "clear_scene":
            names = [obj.name for obj in bpy.data.objects]
            for n in names:
                obj = bpy.data.objects.get(n)
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
            return {"status": "success", "result": {"deleted": names}, "message": f"Deleted {len(names)} objects"}

        # Delete multiple objects
        elif command_type == "delete_objects":
            names = params.get("object_names") or []
            if isinstance(names, str):
                names = [names]
            deleted, missing = [], []
            for n in names:
                obj = bpy.data.objects.get(n)
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    deleted.append(n)
                else:
                    missing.append(n)
            return {
                "status": "success",
                "result": {"deleted": deleted, "missing": missing},
                "message": f"Deleted {len(deleted)} objects"
            }

        # Create empty
        elif command_type == "create_empty":
            name = params.get("name", "Empty")
            location = params.get("location", (0, 0, 0))
            obj = bpy.data.objects.new(name, None)
            obj.location = location
            bpy.context.collection.objects.link(obj)
            return {"status": "success", "result": {"name": obj.name}, "message": f"Empty '{obj.name}' created"}

        # Set parent
        elif command_type == "set_parent":
            parent_name = params.get("parent_name")
            child_names = params.get("child_names") or []
            keep_transform = params.get("keep_transform", True)

            if isinstance(child_names, str):
                child_names = [child_names]

            parent_obj = bpy.data.objects.get(parent_name) if parent_name else None
            if not parent_obj:
                return {"status": "error", "message": f"Parent '{parent_name}' not found"}

            attached, missing = [], []
            for child in child_names:
                obj = bpy.data.objects.get(child)
                if not obj:
                    missing.append(child)
                    continue
                if keep_transform:
                    obj.parent = parent_obj
                    obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
                else:
                    obj.parent = parent_obj
                attached.append(child)

            msg = f"Parented {len(attached)} object(s) to '{parent_name}'"
            if missing:
                msg += f"; missing: {', '.join(missing)}"

            return {
                "status": "success",
                "result": {"parent": parent_name, "attached": attached, "missing": missing},
                "message": msg
            }

        # Apply transforms (location/rotation/scale)
        elif command_type == "apply_transforms":
            obj_names = params.get("object_names") or []
            if isinstance(obj_names, str):
                obj_names = [obj_names]
            apply_loc = params.get("location", True)
            apply_rot = params.get("rotation", True)
            apply_scale = params.get("scale", True)

            applied, missing, skipped = [], [], []
            from mathutils import Matrix
            for name in obj_names:
                obj = bpy.data.objects.get(name)
                if not obj:
                    missing.append(name)
                    continue
                if obj.type != 'MESH':
                    skipped.append(name)
                    continue
                mat = obj.matrix_world.copy()
                loc, rot, sca = mat.decompose()

                # Build matrix to bake based on flags
                bake = Matrix.Identity(4)
                if apply_loc:
                    bake.translation = loc
                if apply_rot:
                    bake @= rot.to_matrix().to_4x4()
                if apply_scale:
                    bake @= Matrix.Diagonal((sca.x, sca.y, sca.z, 1.0))

                obj.data.transform(bake)
                obj.matrix_world = obj.matrix_world @ bake.inverted()
                applied.append(name)

            msg = f"Applied transforms to {len(applied)} object(s)"
            if missing:
                msg += f"; missing: {', '.join(missing)}"
            if skipped:
                msg += f"; skipped non-mesh: {', '.join(skipped)}"
            return {
                "status": "success",
                "result": {"applied": applied, "missing": missing, "skipped": skipped},
                "message": msg
            }

        # Join objects
        elif command_type == "join_objects":
            names = params.get("object_names") or []
            if isinstance(names, str):
                names = [names]
            new_name = params.get("new_name", "Joined")

            import bmesh
            depsgraph = bpy.context.evaluated_depsgraph_get()
            bm = bmesh.new()

            for n in names:
                obj = bpy.data.objects.get(n)
                if not obj or obj.type != 'MESH':
                    continue
                eval_obj = obj.evaluated_get(depsgraph)
                temp_mesh = eval_obj.to_mesh()
                temp_mesh.transform(obj.matrix_world)
                bm.from_mesh(temp_mesh)
                eval_obj.to_mesh_clear()

            if len(bm.verts) == 0:
                bm.free()
                return {"status": "error", "message": "No mesh objects to join"}

            new_mesh = bpy.data.meshes.new(new_name)
            bm.to_mesh(new_mesh)
            bm.free()

            new_obj = bpy.data.objects.new(new_name, new_mesh)
            bpy.context.collection.objects.link(new_obj)

            return {
                "status": "success",
                "result": {"name": new_obj.name},
                "message": f"Joined into '{new_obj.name}'"
            }

        # Set origin
        elif command_type == "set_origin":
            from mathutils import Vector
            obj_name = params.get("object_name")
            mode = (params.get("mode") or "geometry").lower()
            target_param = params.get("target", (0, 0, 0))
            obj = bpy.data.objects.get(obj_name)
            if not obj or obj.type != 'MESH':
                return {"status": "error", "message": f"Object '{obj_name}' not found or not a mesh"}

            current_origin = obj.matrix_world.translation.copy()
            depsgraph = bpy.context.evaluated_depsgraph_get()

            def mesh_center(mode):
                eval_obj = obj.evaluated_get(depsgraph)
                mesh = eval_obj.to_mesh()
                center = Vector((0, 0, 0))
                verts = [v.co.copy() for v in mesh.vertices]
                if mode == "geometry":
                    if verts:
                        minv = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
                        maxv = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
                        center = (minv + maxv) / 2.0
                elif mode == "center_of_mass":
                    if hasattr(mesh, "calc_center_of_mass"):
                        center = mesh.calc_center_of_mass()
                    elif verts:
                        minv = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
                        maxv = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
                        center = (minv + maxv) / 2.0
                if verts:
                    pass
                eval_obj.to_mesh_clear()
                return obj.matrix_world @ center

            if mode == "geometry":
                target_world = mesh_center("geometry")
            elif mode == "center_of_mass":
                target_world = mesh_center("center_of_mass")
            elif mode == "cursor":
                target_world = Vector(target_param) if target_param else Vector((0, 0, 0))
            else:
                return {"status": "error", "message": f"Unsupported mode '{mode}'"}

            delta_world = target_world - current_origin
            delta_local = obj.matrix_world.inverted().to_3x3() @ delta_world

            # Move geometry opposite to delta_local
            if obj.type == 'MESH':
                for v in obj.data.vertices:
                    v.co -= delta_local
            obj.matrix_world.translation = target_world

            return {
                "status": "success",
                "result": {"target": list(target_world), "object": obj_name},
                "message": f"Origin set to {mode}"
            }

        # Instance collection
        elif command_type == "instance_collection":
            coll_name = params.get("collection_name")
            inst_name = params.get("name", f"Instance_{coll_name}")
            loc = params.get("location", (0, 0, 0))
            rot = params.get("rotation", (0, 0, 0))
            scale = params.get("scale", (1, 1, 1))

            coll = bpy.data.collections.get(coll_name)
            if not coll:
                return {"status": "error", "message": f"Collection '{coll_name}' not found"}

            inst = bpy.data.objects.new(inst_name, None)
            inst.instance_type = 'COLLECTION'
            inst.instance_collection = coll
            inst.location = loc
            inst.rotation_euler = rot
            inst.scale = scale
            bpy.context.collection.objects.link(inst)

            return {
                "status": "success",
                "result": {"name": inst.name},
                "message": f"Instanced collection '{coll_name}' as '{inst.name}'"
            }

        # Macro: mech rig (sprockets + optional chain + arm base)
        elif command_type == "mech_rig":
            style = params.get("style", "basic")
            include_chain = params.get("include_chain", True)

            # Clear small area first
            bbox_objs = [o for o in bpy.data.objects if o.location.length < 20]
            for o in bbox_objs:
                bpy.data.objects.remove(o, do_unlink=True)

            # Create sprockets
            def make_sprocket(name, loc, radius=0.8, teeth=10):
                bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=0.2, location=loc)
                base = bpy.context.active_object
                base.name = f"{name}_Base"
                teeth_names = []
                for i in range(teeth):
                    tname = f"{name}_Tooth_{i+1}"
                    bpy.ops.mesh.primitive_cube_add(size=0.2, location=loc)
                    tooth = bpy.context.active_object
                    tooth.name = tname
                    tooth.rotation_euler[2] = i * (6.283185 / teeth)
                    teeth_names.append(tooth.name)
                return [base.name] + teeth_names

            sprocket_left = make_sprocket("RigSprocketL", (-2, 0, 0))
            sprocket_right = make_sprocket("RigSprocketR", (2, 0, 0))

            chain_names = []
            if include_chain:
                curve = bpy.data.curves.new("RigChainCurve", type='CURVE')
                curve.dimensions = '3D'
                spline = curve.splines.new('POLY')
                spline.points.add(3)
                spline.points[0].co = (-2, 0, 0, 1)
                spline.points[1].co = (-2, 0, 0.8, 1)
                spline.points[2].co = (2, 0, 0.8, 1)
                spline.points[3].co = (2, 0, 0, 1)
                curve_obj = bpy.data.objects.new("RigChainPath", curve)
                bpy.context.collection.objects.link(curve_obj)

                bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.4, location=(0, 0, 0))
                link_obj = bpy.context.active_object
                link_obj.name = "RigChainLink"

                # simple scatter along the 4 points
                points = [
                    curve_obj.matrix_world @ p.co.to_3d()
                    for spl in curve_obj.data.splines
                    for p in spl.points
                ]
                for i, p in enumerate(points * 5):
                    new_obj = link_obj.copy()
                    new_obj.data = link_obj.data.copy()
                    new_obj.location = p
                    bpy.context.collection.objects.link(new_obj)
                    chain_names.append(new_obj.name)

            # Arm base
            bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=1.0, location=(0, -1.5, 0))
            arm_base = bpy.context.active_object
            arm_base.name = "RigArm_Base"
            bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0.8, -1.5, 0.8))
            arm_joint = bpy.context.active_object
            arm_joint.name = "RigArm_Joint"
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(1.6, -1.5, 1.3))
            arm_tip = bpy.context.active_object
            arm_tip.name = "RigArm_Tip"

            return {
                "status": "success",
                "result": {
                    "sprocket_left": sprocket_left,
                    "sprocket_right": sprocket_right,
                    "chain": chain_names,
                    "arm": [arm_base.name, arm_joint.name, arm_tip.name],
                },
                "message": "Mech rig created"
            }

        # Create curve path
        elif command_type == "create_curve_path":
            name = params.get("name", "Path")
            points = params.get("points", [])
            if len(points) < 2:
                return {"status": "error", "message": "At least two points required"}
            curve_data = bpy.data.curves.new(name=name, type='CURVE')
            curve_data.dimensions = '3D'
            spline = curve_data.splines.new(type='POLY')
            spline.points.add(len(points) - 1)
            for i, p in enumerate(points):
                spline.points[i].co = (p[0], p[1], p[2], 1.0)
            curve_obj = bpy.data.objects.new(name, curve_data)
            bpy.context.collection.objects.link(curve_obj)
            return {"status": "success", "result": {"name": curve_obj.name}, "message": f"Curve '{curve_obj.name}' created"}

        # Create material
        elif command_type == "create_material":
            name = params.get("name")
            if not name:
                return {"status": "error", "message": "Material name is required"}

            base_color = params.get("base_color", (0.8, 0.8, 0.8, 1.0))
            roughness = params.get("roughness", 0.5)
            metallic = params.get("metallic", 0.0)
            specular = params.get("specular")

            material = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
            principled = _get_principled(material)

            # Ensure color has alpha channel
            if len(base_color) == 3:
                base_color = (*base_color, 1.0)

            principled.inputs["Base Color"].default_value = base_color
            principled.inputs["Roughness"].default_value = roughness
            principled.inputs["Metallic"].default_value = metallic
            if specular is not None:
                principled.inputs["Specular"].default_value = specular

            result = {
                "name": material.name,
                "base_color": list(base_color),
                "roughness": roughness,
                "metallic": metallic,
                "specular": specular,
            }
            return {"status": "success", "result": result, "message": f"Material '{material.name}' created"}

        # Assign material
        elif command_type == "assign_material":
            object_name = params.get("object_name")
            material_name = params.get("material_name")
            slot = params.get("slot", 0)

            obj = bpy.data.objects.get(object_name)
            mat = bpy.data.materials.get(material_name)

            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            if not mat:
                return {"status": "error", "message": f"Material '{material_name}' not found"}
            if not hasattr(obj.data, "materials"):
                return {"status": "error", "message": f"Object '{object_name}' has no material slots"}

            # Ensure enough material slots
            while len(obj.data.materials) <= slot:
                obj.data.materials.append(None)
            obj.data.materials[slot] = mat
            obj.active_material_index = slot

            return {"status": "success", "message": f"Assigned '{material_name}' to '{object_name}' slot {slot}"}

        # Set material property
        elif command_type == "set_material_property":
            material_name = params.get("material_name")
            property_name = params.get("property_name")
            value = params.get("value")

            material = bpy.data.materials.get(material_name)
            if not material:
                return {"status": "error", "message": f"Material '{material_name}' not found"}

            principled = _get_principled(material)
            if property_name == "base_color":
                if len(value) == 3:
                    value = (*value, 1.0)
                principled.inputs["Base Color"].default_value = value
            elif property_name == "roughness":
                principled.inputs["Roughness"].default_value = value
            elif property_name == "metallic":
                principled.inputs["Metallic"].default_value = value
            elif property_name == "specular":
                principled.inputs["Specular"].default_value = value
            elif property_name == "emission_strength":
                principled.inputs["Emission Strength"].default_value = value
            elif property_name == "emission_color":
                if len(value) == 3:
                    value = (*value, 1.0)
                principled.inputs["Emission"].default_value = value
            else:
                return {"status": "error", "message": f"Unsupported material property '{property_name}'"}

            return {"status": "success", "message": f"Set '{property_name}' on '{material_name}'"}

        # Create material from preset data
        elif command_type == "create_material_preset":
            preset_name = params.get("preset_name")
            custom_name = params.get("custom_name")
            preset_data = params.get("preset_data") or {}

            if not preset_data:
                return {"status": "error", "message": f"Preset data missing for '{preset_name}'"}

            target_name = custom_name or preset_data.get("name") or preset_name
            base_color = preset_data.get("base_color", (0.8, 0.8, 0.8, 1.0))
            roughness = preset_data.get("roughness", 0.5)
            metallic = preset_data.get("metallic", 0.0)

            material = bpy.data.materials.get(target_name) or bpy.data.materials.new(name=target_name)
            principled = _get_principled(material)

            if len(base_color) == 3:
                base_color = (*base_color, 1.0)

            principled.inputs["Base Color"].default_value = base_color
            principled.inputs["Roughness"].default_value = roughness
            principled.inputs["Metallic"].default_value = metallic

            # Optional extra properties
            if "specular" in preset_data and "Specular" in principled.inputs:
                principled.inputs["Specular"].default_value = preset_data["specular"]
            if "emission_strength" in preset_data and "Emission Strength" in principled.inputs:
                principled.inputs["Emission Strength"].default_value = preset_data["emission_strength"]
            if "emission_color" in preset_data and "Emission" in principled.inputs:
                emission_color = preset_data["emission_color"]
                if len(emission_color) == 3:
                    emission_color = (*emission_color, 1.0)
                principled.inputs["Emission"].default_value = emission_color

            result = {
                "name": material.name,
                "preset": preset_name,
                "base_color": list(base_color),
                "roughness": roughness,
                "metallic": metallic,
            }
            return {"status": "success", "result": result, "message": f"Material '{material.name}' from preset '{preset_name}'"}

        # List materials
        elif command_type == "get_material_list":
            materials = [m.name for m in bpy.data.materials]
            result = {"materials": materials, "count": len(materials)}
            return {"status": "success", "result": result, "message": f"Found {len(materials)} materials"}


        # create_building_box - Create parametric building volume
        elif command_type == "create_building_box":
            width = params.get("width", 10.0)
            depth = params.get("depth", 10.0)
            height = params.get("height", 15.0)
            floors = params.get("floors", 5)
            name = params.get("name", "Building")

            # Create base cube
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, height/2))
            obj = bpy.context.active_object
            obj.name = name
            obj.scale = (width/2, depth/2, height/2)

            # Add custom properties for floors
            obj["floors"] = floors
            obj["floor_height"] = height / floors

            result = {
                "name": obj.name,
                "dimensions": [width, depth, height],
                "floors": floors,
                "floor_height": height / floors
            }
            return {"status": "success", "result": result, "message": f"Building box '{name}' created"}

        # create_window_grid - Create parametric window grid
        elif command_type == "create_window_grid":
            building_name = params.get("building_name")
            floors = params.get("floors", 5)
            windows_per_floor = params.get("windows_per_floor", 4)
            window_width = params.get("window_width", 1.5)
            window_height = params.get("window_height", 2.0)
            spacing = params.get("spacing", 0.5)
            inset = params.get("inset", 0.1)

            building = bpy.data.objects.get(building_name)
            if not building:
                return {"status": "error", "message": f"Building '{building_name}' not found"}

            # Get building dimensions
            dims = building.dimensions
            floor_height = dims[2] / floors

            windows_created = []

            # Create windows on one face (front)
            for floor in range(floors):
                for win in range(windows_per_floor):
                    # Create window primitive
                    bpy.ops.mesh.primitive_cube_add(size=1)
                    window = bpy.context.active_object
                    window.name = f"Window_F{floor}_W{win}"

                    # Scale to window size
                    window.scale = (window_width/2, 0.05, window_height/2)

                    # Position window
                    x_pos = -dims[0]/2 + spacing + win * (window_width + spacing)
                    y_pos = dims[1]/2 + inset
                    z_pos = floor * floor_height + floor_height/2

                    window.location = (x_pos, y_pos, z_pos)

                    # Parent to building
                    window.parent = building

                    windows_created.append(window.name)

            result = {
                "building": building_name,
                "windows_created": len(windows_created),
                "window_names": windows_created[:10]
            }
            return {"status": "success", "result": result, "message": f"Created {len(windows_created)} windows"}

        # array_along_path - Array objects along a curve
        elif command_type == "array_along_path":
            source_object = params.get("source_object")
            curve_name = params.get("curve_name")
            count = params.get("count", 10)
            align_to_curve = params.get("align_to_curve", True)
            spacing_factor = params.get("spacing_factor", 1.0)

            source = bpy.data.objects.get(source_object)
            curve = bpy.data.objects.get(curve_name)

            if not source:
                return {"status": "error", "message": f"Source object '{source_object}' not found"}
            if not curve or curve.type != 'CURVE':
                return {"status": "error", "message": f"Curve '{curve_name}' not found or not a curve"}

            # Get curve spline
            spline = curve.data.splines[0]
            curve_length = len(spline.points) if spline.type == 'POLY' else len(spline.bezier_points)

            created_objects = []

            for i in range(count):
                # Duplicate source
                new_obj = source.copy()
                if source.data:
                    new_obj.data = source.data.copy()
                bpy.context.collection.objects.link(new_obj)
                new_obj.name = f"{source.name}_Path_{i}"

                # Calculate position along curve (0 to 1)
                t = (i / max(count - 1, 1)) * spacing_factor

                # Simple linear interpolation along curve
                if spline.type == 'POLY':
                    idx = int(t * (curve_length - 1))
                    idx = min(idx, curve_length - 1)
                    point = spline.points[idx]
                    local_pos = Vector((point.co[0], point.co[1], point.co[2]))
                else:
                    idx = int(t * (curve_length - 1))
                    idx = min(idx, curve_length - 1)
                    point = spline.bezier_points[idx]
                    local_pos = point.co

                # Transform to world space
                world_pos = curve.matrix_world @ local_pos
                new_obj.location = world_pos

                created_objects.append(new_obj.name)

            result = {
                "source": source_object,
                "curve": curve_name,
                "objects_created": len(created_objects),
                "object_names": created_objects
            }
            return {"status": "success", "result": result, "message": f"Created {len(created_objects)} objects along path"}

        # randomize_transform - Add random variation to transforms
        elif command_type == "randomize_transform":
            import random as rand_module  # Local import to avoid UnboundLocalError

            object_names = params.get("object_names", [])
            location_range = params.get("location_range", [0.0, 0.0, 0.0])
            rotation_range = params.get("rotation_range", [0.0, 0.0, 0.0])
            scale_range = params.get("scale_range", [0.0, 0.0, 0.0])
            seed = params.get("seed", 0)

            if seed:
                rand_module.seed(seed)

            if not object_names:
                object_names = [obj.name for obj in bpy.context.selected_objects]

            randomized = []

            for obj_name in object_names:
                obj = bpy.data.objects.get(obj_name)
                if not obj:
                    continue

                # Randomize location
                if any(location_range):
                    obj.location.x += rand_module.uniform(-location_range[0], location_range[0])
                    obj.location.y += rand_module.uniform(-location_range[1], location_range[1])
                    obj.location.z += rand_module.uniform(-location_range[2], location_range[2])

                # Randomize rotation
                if any(rotation_range):
                    obj.rotation_euler.x += rand_module.uniform(-rotation_range[0], rotation_range[0])
                    obj.rotation_euler.y += rand_module.uniform(-rotation_range[1], rotation_range[1])
                    obj.rotation_euler.z += rand_module.uniform(-rotation_range[2], rotation_range[2])

                # Randomize scale
                if any(scale_range):
                    obj.scale.x *= 1.0 + rand_module.uniform(-scale_range[0], scale_range[0])
                    obj.scale.y *= 1.0 + rand_module.uniform(-scale_range[1], scale_range[1])
                    obj.scale.z *= 1.0 + rand_module.uniform(-scale_range[2], scale_range[2])

                randomized.append(obj_name)

            result = {
                "objects_randomized": len(randomized),
                "object_names": randomized
            }
            return {"status": "success", "result": result, "message": f"Randomized {len(randomized)} objects"}

        # create_stairs - Create parametric stairs
        elif command_type == "create_stairs":
            steps = params.get("steps", 10)
            step_width = params.get("step_width", 2.0)
            step_depth = params.get("step_depth", 0.3)
            step_height = params.get("step_height", 0.2)
            name = params.get("name", "Stairs")
            location = params.get("location", [0, 0, 0])

            created_steps = []

            for i in range(steps):
                # Create step
                bpy.ops.mesh.primitive_cube_add(size=1)
                step = bpy.context.active_object
                step.name = f"{name}_Step_{i}"

                # Scale step
                step.scale = (step_width/2, step_depth/2, step_height/2)

                # Position step
                step.location = (
                    location[0],
                    location[1] + i * step_depth,
                    location[2] + i * step_height + step_height/2
                )

                created_steps.append(step.name)

            # Create collection for stairs
            if name not in bpy.data.collections:
                stairs_col = bpy.data.collections.new(name)
                bpy.context.scene.collection.children.link(stairs_col)
            else:
                stairs_col = bpy.data.collections[name]

            # Move steps to collection
            for step_name in created_steps:
                step = bpy.data.objects.get(step_name)
                if step:
                    for col in step.users_collection:
                        col.objects.unlink(step)
                    stairs_col.objects.link(step)

            result = {
                "name": name,
                "steps_created": len(created_steps),
                "total_height": steps * step_height,
                "total_length": steps * step_depth
            }
            return {"status": "success", "result": result, "message": f"Stairs '{name}' with {steps} steps created"}

        # --- Edit Mode ---
        elif command_type == "edit_mode_enter":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "EDIT").upper()
            obj = _get_mesh_object(object_name)
            target_mode = "EDIT" if mode == "EDIT" else "OBJECT"
            bpy.ops.object.mode_set(mode=target_mode)
            return {"status": "success", "result": {"mode": target_mode}, "message": f"Mode set to {target_mode} for '{object_name}'"}

        elif command_type == "edit_mode_exit":
            object_name = params.get("object_name")
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            return {"status": "success", "result": {"mode": "OBJECT"}, "message": f"Exited edit mode for '{object_name}'"}

        elif command_type == "select_geometry":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "VERT").upper()
            indices = params.get("indices")
            pattern = (params.get("pattern") or "ALL").upper()
            expand = int(params.get("expand", 0))

            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            _set_select_mode(mode if mode in {"VERT", "EDGE", "FACE"} else "VERT")

            if indices is not None:
                _select_indices(bm, mode, indices)
            else:
                if pattern == "NONE":
                    bpy.ops.mesh.select_all(action='DESELECT')
                elif pattern == "ALL":
                    bpy.ops.mesh.select_all(action='SELECT')
                elif pattern == "INVERT":
                    bpy.ops.mesh.select_all(action='INVERT')
                elif pattern == "RANDOM":
                    bmesh.ops.select_random(bm, verts=bm.verts, edges=bm.edges, faces=bm.faces, seed=random.randint(0, 10_000))
                else:
                    bpy.ops.mesh.select_all(action='DESELECT')

            if pattern in {"LOOP", "RING"} and mode == "EDGE":
                # Start from current selection
                bpy.ops.mesh.loop_multi_select(ring=(pattern == "RING"))

            for _ in range(max(expand, 0)):
                bpy.ops.mesh.select_more()

            bmesh.update_edit_mesh(obj.data)
            result = {
                "selected_vertices": sum(1 for v in bm.verts if v.select),
                "selected_edges": sum(1 for e in bm.edges if e.select),
                "selected_faces": sum(1 for f in bm.faces if f.select),
            }
            return {"status": "success", "result": result, "message": "Selection updated"}

        elif command_type == "extrude":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "REGION").upper()
            offset = params.get("offset", (0.0, 0.0, 0.0))
            scale = float(params.get("scale", 1.0))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            _set_select_mode("FACE" if mode == "REGION" else (mode if mode in {"VERT", "EDGE", "FACE"} else "FACE"))

            if mode == "VERT":
                bpy.ops.mesh.extrude_vertices_move(TRANSFORM_OT_translate={"value": offset})
            elif mode == "EDGE":
                bpy.ops.mesh.extrude_edges_move(TRANSFORM_OT_translate={"value": offset})
            else:
                bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": offset})
            if abs(scale - 1.0) > 1e-6:
                bpy.ops.transform.resize(value=(scale, scale, scale))
            return {"status": "success", "result": {"offset": offset, "scale": scale}, "message": "Extrude completed"}

        elif command_type == "loop_cut":
            object_name = params.get("object_name")
            edge_index = int(params.get("edge_index", 0))
            cuts = int(params.get("cuts", 1))
            slide = float(params.get("slide", 0.0))
            even = bool(params.get("even", False))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bpy.ops.mesh.loopcut_slide(
                MESH_OT_loopcut={"number_cuts": cuts, "edge_index": edge_index},
                TRANSFORM_OT_edge_slide={"value": slide, "use_even": even},
            )
            return {"status": "success", "result": {"cuts": cuts}, "message": "Loop cut added"}

        elif command_type == "inset_faces":
            object_name = params.get("object_name")
            face_indices = params.get("face_indices")
            thickness = float(params.get("thickness", 0.01))
            depth = float(params.get("depth", 0.0))
            use_boundary = bool(params.get("use_boundary", True))
            use_even_offset = bool(params.get("use_even_offset", True))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            if face_indices is not None:
                _select_indices(bm, "FACE", face_indices)
            _set_select_mode("FACE")
            bpy.ops.mesh.inset(thickness=thickness, depth=depth, use_boundary=use_boundary, use_even_offset=use_even_offset)
            bmesh.update_edit_mesh(obj.data)
            return {"status": "success", "result": {"thickness": thickness, "depth": depth}, "message": "Inset completed"}

        elif command_type == "bevel_edges":
            object_name = params.get("object_name")
            edge_indices = params.get("edge_indices")
            width = float(params.get("width", 0.01))
            segments = int(params.get("segments", 1))
            profile = float(params.get("profile", 0.5))
            clamp = bool(params.get("clamp", True))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            if edge_indices is not None:
                _select_indices(bm, "EDGE", edge_indices)
            _set_select_mode("EDGE")
            bpy.ops.mesh.bevel(offset=width, offset_type='WIDTH', segments=segments, profile=profile, clamp_overlap=clamp)
            bmesh.update_edit_mesh(obj.data)
            return {"status": "success", "result": {"segments": segments}, "message": "Bevel applied"}

        elif command_type == "bridge_edge_loops":
            object_name = params.get("object_name")
            loop1 = params.get("loop1_indices") or []
            loop2 = params.get("loop2_indices") or []
            cuts = int(params.get("cuts", 0))
            twist = int(params.get("twist", 0))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            _select_indices(bm, "EDGE", list(loop1) + list(loop2))
            _set_select_mode("EDGE")
            bpy.ops.mesh.bridge_edge_loops(number_cuts=cuts, twist_offset=twist)
            bmesh.update_edit_mesh(obj.data)
            return {"status": "success", "result": {"cuts": cuts}, "message": "Edge loops bridged"}

        elif command_type == "merge_vertices":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "CENTER").upper()
            threshold = float(params.get("threshold", 0.0001))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            _set_select_mode("VERT")
            if mode in {"CENTER", "CURSOR", "FIRST", "LAST", "COLLAPSE"}:
                bpy.ops.mesh.merge(type=mode)
            if mode == "COLLAPSE" and threshold > 0:
                bpy.ops.mesh.merge_by_distance(distance=threshold)
            return {"status": "success", "result": {"mode": mode}, "message": "Vertices merged"}

        elif command_type == "dissolve":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "EDGE").upper()
            angle_limit = float(params.get("angle_limit", 0.0872665))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            if mode == "VERT":
                _set_select_mode("VERT")
                bpy.ops.mesh.dissolve_verts()
            elif mode == "EDGE":
                _set_select_mode("EDGE")
                bpy.ops.mesh.dissolve_edges()
            elif mode == "FACE":
                _set_select_mode("FACE")
                bpy.ops.mesh.dissolve_faces()
            elif mode == "LIMITED":
                bpy.ops.mesh.dissolve_limited(angle_limit=angle_limit)
            else:
                return {"status": "error", "message": f"Unsupported dissolve mode '{mode}'"}
            return {"status": "success", "result": {"mode": mode}, "message": "Dissolve completed"}

        elif command_type == "knife_cut":
            object_name = params.get("object_name")
            cut_points = params.get("cut_points") or []
            cut_through = bool(params.get("cut_through", False))
            if len(cut_points) < 2:
                return {"status": "error", "message": "cut_points requires at least 2 points"}
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')

            mesh = bpy.data.meshes.new("KnifeCutMesh")
            bm = bmesh.new()
            verts = [bm.verts.new(tuple(p)) for p in cut_points]
            bm.verts.ensure_lookup_table()
            for idx in range(len(verts) - 1):
                bm.edges.new((verts[idx], verts[idx + 1]))
            bm.to_mesh(mesh)
            bm.free()

            cutter = bpy.data.objects.new("KnifeCut", mesh)
            bpy.context.collection.objects.link(cutter)

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            cutter.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.knife_project(cut_through=cut_through)
            bpy.ops.object.mode_set(mode='OBJECT')

            bpy.data.objects.remove(cutter, do_unlink=True)
            return {"status": "success", "result": {"cut_points": len(cut_points)}, "message": "Knife cut applied"}

        # --- UV ---
        elif command_type == "uv_unwrap":
            object_name = params.get("object_name")
            method = (params.get("method") or "ANGLE_BASED").upper()
            angle_limit = float(params.get("angle_limit", 66.0))
            island_margin = float(params.get("island_margin", 0.02))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            _set_select_mode("FACE")
            if method in {"ANGLE_BASED", "CONFORMAL"}:
                bpy.ops.uv.unwrap(method=method, margin=island_margin)
            elif method == "SMART_UV":
                bpy.ops.uv.smart_project(angle_limit=angle_limit, island_margin=island_margin)
            elif method == "PROJECT_VIEW":
                bpy.ops.uv.project_from_view()
            else:
                return {"status": "error", "message": f"Unknown UV method '{method}'"}
            return {"status": "success", "result": {"method": method}, "message": "UV unwrap completed"}

        elif command_type == "uv_mark_seam":
            object_name = params.get("object_name")
            edge_indices = params.get("edge_indices") or []
            clear = bool(params.get("clear", False))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            for idx in edge_indices:
                if 0 <= idx < len(bm.edges):
                    bm.edges[idx].seam = not clear
            bmesh.update_edit_mesh(obj.data)
            return {"status": "success", "result": {"edges": len(edge_indices)}, "message": "Seams updated"}

        # --- Geometry Nodes ---
        elif command_type == "geonodes_create":
            object_name = params.get("object_name")
            tree_name = params.get("tree_name")
            if not tree_name:
                return {"status": "error", "message": "tree_name is required"}
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            tree = bpy.data.node_groups.get(tree_name) or bpy.data.node_groups.new(tree_name, 'GeometryNodeTree')
            modifier = obj.modifiers.get(tree_name) or obj.modifiers.new(name=tree_name, type='NODES')
            modifier.node_group = tree
            return {"status": "success", "result": {"tree": tree.name, "modifier": modifier.name}, "message": "GeoNodes created"}

        elif command_type == "geonodes_add_node":
            tree_name = params.get("tree_name")
            node_type = params.get("node_type")
            location = params.get("location", (0, 0))
            name = params.get("name")
            tree = bpy.data.node_groups.get(tree_name)
            if not tree:
                return {"status": "error", "message": f"Node tree '{tree_name}' not found"}
            node = tree.nodes.new(type=node_type)
            if name:
                node.name = name
            node.location = location
            return {"status": "success", "result": {"node_name": node.name}, "message": "Node added"}

        elif command_type == "geonodes_connect":
            tree_name = params.get("tree_name")
            from_node_name = params.get("from_node")
            from_socket = params.get("from_socket")
            to_node_name = params.get("to_node")
            to_socket = params.get("to_socket")
            tree = bpy.data.node_groups.get(tree_name)
            if not tree:
                return {"status": "error", "message": f"Node tree '{tree_name}' not found"}
            from_node = tree.nodes.get(from_node_name)
            to_node = tree.nodes.get(to_node_name)
            if not from_node or not to_node:
                return {"status": "error", "message": "Invalid node names for connection"}

            def _get_socket(socket_ref, sockets):
                if isinstance(socket_ref, int):
                    return sockets[socket_ref] if 0 <= socket_ref < len(sockets) else None
                return sockets.get(socket_ref) if hasattr(sockets, "get") else next((s for s in sockets if s.name == socket_ref), None)

            out_socket = _get_socket(from_socket, from_node.outputs)
            in_socket = _get_socket(to_socket, to_node.inputs)
            if not out_socket or not in_socket:
                return {"status": "error", "message": "Invalid sockets for connection"}
            tree.links.new(out_socket, in_socket)
            return {"status": "success", "result": {"from": from_node.name, "to": to_node.name}, "message": "Nodes connected"}

        elif command_type == "geonodes_set_input":
            tree_name = params.get("tree_name")
            node_name = params.get("node_name")
            input_name = params.get("input_name")
            value = params.get("value")
            tree = bpy.data.node_groups.get(tree_name)
            if not tree:
                return {"status": "error", "message": f"Node tree '{tree_name}' not found"}
            node = tree.nodes.get(node_name)
            if not node:
                return {"status": "error", "message": f"Node '{node_name}' not found"}
            sock = None
            if isinstance(input_name, int):
                if 0 <= input_name < len(node.inputs):
                    sock = node.inputs[input_name]
            else:
                sock = node.inputs.get(input_name)
            if not sock:
                return {"status": "error", "message": "Input socket not found"}
            try:
                sock.default_value = value
            except Exception:
                return {"status": "error", "message": "Failed to assign value to socket"}
            return {"status": "success", "result": {"input": sock.name}, "message": "Input set"}

        # --- Import / Export ---
        elif command_type == "import_model":
            filepath = params.get("filepath")
            fmt = (params.get("format") or "").upper()
            scale = float(params.get("scale", 1.0))
            if not filepath or fmt not in {"FBX", "OBJ", "GLTF", "STL"}:
                return {"status": "error", "message": "filepath and valid format (FBX/OBJ/GLTF/STL) required"}
            before = set(o.name for o in bpy.data.objects)
            if fmt == "FBX":
                bpy.ops.import_scene.fbx(filepath=filepath, global_scale=scale)
            elif fmt == "OBJ":
                bpy.ops.import_scene.obj(filepath=filepath)
            elif fmt == "GLTF":
                bpy.ops.import_scene.gltf(filepath=filepath)
            elif fmt == "STL":
                bpy.ops.import_mesh.stl(filepath=filepath, global_scale=scale)
            after = set(o.name for o in bpy.data.objects)
            imported = list(after - before)
            if fmt in {"OBJ", "GLTF"} and abs(scale - 1.0) > 1e-6:
                for name in imported:
                    obj = bpy.data.objects.get(name)
                    if obj:
                        obj.scale = (obj.scale[0] * scale, obj.scale[1] * scale, obj.scale[2] * scale)
            return {"status": "success", "result": {"imported": imported}, "message": f"Imported {len(imported)} object(s)"}

        elif command_type == "export_model":
            filepath = params.get("filepath")
            fmt = (params.get("format") or "").upper()
            object_names = params.get("object_names")
            apply_modifiers = bool(params.get("apply_modifiers", True))
            if not filepath or fmt not in {"FBX", "OBJ", "GLTF", "STL"}:
                return {"status": "error", "message": "filepath and valid format (FBX/OBJ/GLTF/STL) required"}
            bpy.ops.object.mode_set(mode='OBJECT')
            if object_names:
                bpy.ops.object.select_all(action='DESELECT')
                for name in object_names:
                    obj = bpy.data.objects.get(name)
                    if obj:
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = obj
            if fmt == "FBX":
                bpy.ops.export_scene.fbx(filepath=filepath, use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', use_mesh_modifiers=apply_modifiers)
            elif fmt == "OBJ":
                bpy.ops.export_scene.obj(filepath=filepath, use_selection=True, use_mesh_modifiers=apply_modifiers)
            elif fmt == "GLTF":
                bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, export_apply=apply_modifiers)
            elif fmt == "STL":
                bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True, global_scale=1.0, use_modifiers=apply_modifiers)
            return {"status": "success", "result": {"filepath": filepath}, "message": f"Exported selection to {filepath}"}

        # --- BMesh direct ---
        elif command_type == "bmesh_create_geometry":
            object_name = params.get("object_name")
            vertices = params.get("vertices") or []
            edges = params.get("edges") or []
            faces = params.get("faces") or []
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            bm = bmesh.new()
            vrefs = [bm.verts.new(tuple(v)) for v in vertices]
            bm.verts.ensure_lookup_table()
            for a, b in edges:
                try:
                    bm.edges.new((vrefs[a], vrefs[b]))
                except Exception:
                    pass
            for face in faces:
                try:
                    bm.faces.new([vrefs[i] for i in face])
                except Exception:
                    pass
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
            return {"status": "success", "result": {"verts": len(vertices)}, "message": "Geometry written"}

        elif command_type == "bmesh_get_geometry":
            object_name = params.get("object_name")
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = obj.data
            verts = [tuple(v.co) for v in mesh.vertices]
            edges = [tuple(e.vertices) for e in mesh.edges]
            faces = [list(p.vertices) for p in mesh.polygons]
            return {"status": "success", "result": {"verts": verts, "edges": edges, "faces": faces}, "message": "Geometry fetched"}

        # --- Advanced edit / topology ---
        elif command_type == "spin":
            object_name = params.get("object_name")
            angle = float(params.get("angle", 6.283185))
            steps = int(params.get("steps", 12))
            axis = (params.get("axis") or "Z").upper()
            center = params.get("center")
            dupli = bool(params.get("dupli", False))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            ax = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}.get(axis, (0, 0, 1))
            cen = tuple(center) if center else tuple(obj.location)
            bpy.ops.mesh.spin(steps=steps, dupli=dupli, angle=angle, center=cen, axis=ax)
            return {"status": "success", "result": {"steps": steps}, "message": "Spin completed"}

        elif command_type == "screw":
            object_name = params.get("object_name")
            screw_offset = float(params.get("screw_offset", 1.0))
            iterations = int(params.get("iterations", 2))
            steps = int(params.get("steps", 16))
            axis = (params.get("axis") or "Z").upper()
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            ax = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}.get(axis, (0, 0, 1))
            bpy.ops.mesh.screw(steps=steps, turns=iterations, screw_offset=screw_offset, axis=ax)
            return {"status": "success", "result": {"iterations": iterations}, "message": "Screw completed"}

        elif command_type == "fill_hole":
            object_name = params.get("object_name")
            mode = (params.get("mode") or "BEAUTY").upper()
            span = int(params.get("span", 1))
            offset = int(params.get("offset", 0))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            if mode == "GRID":
                bpy.ops.mesh.fill_grid(span=span, offset=offset)
            else:
                bpy.ops.mesh.fill()
            return {"status": "success", "result": {"mode": mode}, "message": "Fill completed"}

        elif command_type == "shrink_fatten":
            object_name = params.get("object_name")
            offset = float(params.get("offset", 0.0))
            use_even_offset = bool(params.get("use_even_offset", True))
            obj = _get_mesh_object(object_name)
            _ensure_mode(obj, 'EDIT')
            bpy.ops.transform.shrink_fatten(value=offset, use_even_offset=use_even_offset)
            return {"status": "success", "result": {"offset": offset}, "message": "Shrink/Fatten applied"}

        elif command_type == "set_edge_crease":
            object_name = params.get("object_name")
            edge_indices = params.get("edge_indices")
            value = float(params.get("value", 1.0))
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.edges.ensure_lookup_table()
            crease_layer = bm.edges.layers.crease.verify()
            indices = edge_indices if edge_indices is not None else range(len(bm.edges))
            count = 0
            for idx in indices:
                if 0 <= idx < len(bm.edges):
                    bm.edges[idx][crease_layer] = value
                    count += 1
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
            return {"status": "success", "result": {"edges_modified": count}, "message": "Edge crease set"}

        elif command_type == "set_bevel_weight":
            object_name = params.get("object_name")
            edge_indices = params.get("edge_indices")
            value = float(params.get("value", 1.0))
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.edges.ensure_lookup_table()
            bevel_layer = bm.edges.layers.bevel_weight.verify()
            indices = edge_indices if edge_indices is not None else range(len(bm.edges))
            count = 0
            for idx in indices:
                if 0 <= idx < len(bm.edges):
                    bm.edges[idx][bevel_layer] = value
                    count += 1
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
            return {"status": "success", "result": {"edges_modified": count}, "message": "Bevel weight set"}

        elif command_type == "mark_sharp":
            object_name = params.get("object_name")
            edge_indices = params.get("edge_indices")
            clear = bool(params.get("clear", False))
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.edges.ensure_lookup_table()
            indices = edge_indices if edge_indices is not None else range(len(bm.edges))
            count = 0
            for idx in indices:
                if 0 <= idx < len(bm.edges):
                    bm.edges[idx].smooth = clear is True
                    bm.edges[idx].use_edge_sharp = not clear
                    count += 1
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
            return {"status": "success", "result": {"edges_modified": count}, "message": "Sharp edges updated"}

        elif command_type == "set_shade_smooth":
            object_name = params.get("object_name")
            smooth = bool(params.get("smooth", True))
            use_auto_smooth = bool(params.get("use_auto_smooth", True))
            auto_angle = float(params.get("auto_smooth_angle", 0.523599))
            obj = _get_mesh_object(object_name)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            if smooth:
                bpy.ops.object.shade_smooth()
            else:
                bpy.ops.object.shade_flat()
            mesh = obj.data
            if hasattr(mesh, "use_auto_smooth"):
                mesh.use_auto_smooth = use_auto_smooth
                mesh.auto_smooth_angle = auto_angle
            return {"status": "success", "result": {"smooth": smooth}, "message": "Shading updated"}

        # --- Vertex groups ---
        elif command_type == "create_vertex_group":
            object_name = params.get("object_name")
            group_name = params.get("group_name")
            vertex_indices = params.get("vertex_indices")
            weight = float(params.get("weight", 1.0))
            obj = _get_mesh_object(object_name)
            vg = obj.vertex_groups.new(name=group_name)
            if vertex_indices:
                vg.add(vertex_indices, weight, 'REPLACE')
            return {"status": "success", "result": {"group": vg.name}, "message": "Vertex group created"}

        elif command_type == "assign_to_vertex_group":
            object_name = params.get("object_name")
            group_name = params.get("group_name")
            vertex_indices = params.get("vertex_indices") or []
            weight = float(params.get("weight", 1.0))
            mode = params.get("mode", "REPLACE")
            obj = _get_mesh_object(object_name)
            vg = obj.vertex_groups.get(group_name)
            if not vg:
                return {"status": "error", "message": f"Vertex group '{group_name}' not found"}
            vg.add(vertex_indices, weight, mode)
            return {"status": "success", "result": {"group": vg.name}, "message": "Vertices assigned"}

        elif command_type == "remove_from_vertex_group":
            object_name = params.get("object_name")
            group_name = params.get("group_name")
            vertex_indices = params.get("vertex_indices")
            obj = _get_mesh_object(object_name)
            vg = obj.vertex_groups.get(group_name)
            if not vg:
                return {"status": "error", "message": f"Vertex group '{group_name}' not found"}
            indices = vertex_indices if vertex_indices is not None else [v.index for v in obj.data.vertices]
            vg.remove(indices)
            return {"status": "success", "result": {"removed": len(indices)}, "message": "Vertices removed from group"}

        elif command_type == "get_vertex_groups":
            object_name = params.get("object_name")
            obj = _get_mesh_object(object_name)
            groups = []
            for idx, vg in enumerate(obj.vertex_groups):
                groups.append({"name": vg.name, "index": idx})
            return {"status": "success", "result": {"groups": groups}, "message": f"{len(groups)} vertex groups found"}

        # --- Modifiers ---
        elif command_type == "add_solidify":
            object_name = params.get("object_name")
            thickness = float(params.get("thickness", 0.01))
            offset = float(params.get("offset", -1.0))
            use_even = bool(params.get("use_even_thickness", True))
            use_quality = bool(params.get("use_quality_normals", True))
            use_rim = bool(params.get("use_rim", True))
            use_rim_only = bool(params.get("use_rim_only", False))
            material_offset = int(params.get("material_offset", 0))
            material_offset_rim = int(params.get("material_offset_rim", 0))
            obj = _get_mesh_object(object_name)
            mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            mod.thickness = thickness
            mod.offset = offset
            mod.use_even_offset = use_even
            mod.use_quality_normals = use_quality
            mod.use_rim = use_rim
            mod.use_rim_only = use_rim_only
            mod.material_offset = material_offset
            mod.material_offset_rim = material_offset_rim
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Solidify added"}

        elif command_type == "add_screw_modifier":
            object_name = params.get("object_name")
            angle = float(params.get("angle", 6.283185))
            screw_offset = float(params.get("screw_offset", 0.0))
            iterations = int(params.get("iterations", 1))
            steps = int(params.get("steps", 16))
            axis = (params.get("axis") or "Z").upper()
            use_merge_vertices = bool(params.get("use_merge_vertices", True))
            merge_threshold = float(params.get("merge_threshold", 0.0001))
            obj = _get_mesh_object(object_name)
            mod = obj.modifiers.new(name="Screw", type='SCREW')
            mod.angle = angle
            mod.screw_offset = screw_offset
            mod.steps = steps
            mod.render_steps = steps
            mod.iterations = iterations
            mod.axis = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}.get(axis, 'Z')
            mod.use_merge_vertices = use_merge_vertices
            mod.merge_threshold = merge_threshold
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Screw modifier added"}

        elif command_type == "add_shrinkwrap":
            object_name = params.get("object_name")
            target = params.get("target")
            wrap_method = params.get("wrap_method", "NEAREST_SURFACEPOINT")
            wrap_mode = params.get("wrap_mode", "ON_SURFACE")
            offset = float(params.get("offset", 0.0))
            obj = _get_mesh_object(object_name)
            tgt_obj = bpy.data.objects.get(target) if target else None
            if not tgt_obj:
                return {"status": "error", "message": f"Target '{target}' not found"}
            mod = obj.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
            mod.target = tgt_obj
            mod.wrap_method = wrap_method
            mod.wrap_mode = wrap_mode
            mod.offset = offset
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Shrinkwrap added"}

        elif command_type == "add_weighted_normal":
            object_name = params.get("object_name")
            weight = int(params.get("weight", 50))
            mode = params.get("mode", "FACE_AREA")
            keep_sharp = bool(params.get("keep_sharp", True))
            face_influence = bool(params.get("face_influence", False))
            obj = _get_mesh_object(object_name)
            mod = obj.modifiers.new(name="WeightedNormal", type='WEIGHTED_NORMAL')
            mod.weight = weight
            mod.mode = mode
            mod.keep_sharp = keep_sharp
            mod.use_face_influence = face_influence
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Weighted Normal added"}

        elif command_type == "add_lattice":
            object_name = params.get("object_name")
            lattice_object = params.get("lattice_object")
            resolution = tuple(params.get("resolution", (2, 2, 2)))
            interpolation = params.get("interpolation", "KEY_LINEAR")
            obj = _get_mesh_object(object_name)
            lat_obj = bpy.data.objects.get(lattice_object) if lattice_object else None
            if lat_obj is None:
                lat_data = bpy.data.lattices.new(name=f"{object_name}_LatticeData")
                lat_data.points_u, lat_data.points_v, lat_data.points_w = resolution
                lat_obj = bpy.data.objects.new(f"{object_name}_Lattice", lat_data)
                bpy.context.collection.objects.link(lat_obj)
                lat_obj.location = obj.location
            mod = obj.modifiers.new(name="Lattice", type='LATTICE')
            mod.object = lat_obj
            mod.interpolation_type_u = interpolation
            mod.interpolation_type_v = interpolation
            mod.interpolation_type_w = interpolation
            return {"status": "success", "result": {"modifier": mod.name, "lattice": lat_obj.name}, "message": "Lattice added"}

        elif command_type == "add_wireframe":
            object_name = params.get("object_name")
            thickness = float(params.get("thickness", 0.02))
            use_even_offset = bool(params.get("use_even_offset", True))
            use_boundary = bool(params.get("use_boundary", True))
            use_replace = bool(params.get("use_replace", True))
            material_offset = int(params.get("material_offset", 0))
            obj = _get_mesh_object(object_name)
            mod = obj.modifiers.new(name="Wireframe", type='WIREFRAME')
            mod.thickness = thickness
            mod.use_even_offset = use_even_offset
            mod.use_boundary = use_boundary
            mod.use_replace = use_replace
            mod.material_offset = material_offset
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Wireframe added"}

        elif command_type == "add_skin":
            object_name = params.get("object_name")
            branch_smoothing = float(params.get("branch_smoothing", 0.0))
            use_smooth_shade = bool(params.get("use_smooth_shade", False))
            obj = _get_mesh_object(object_name)
            mod = obj.modifiers.new(name="Skin", type='SKIN')
            mod.branch_smoothing = branch_smoothing
            mod.use_smooth_shade = use_smooth_shade
            return {"status": "success", "result": {"modifier": mod.name}, "message": "Skin added"}

        # --- Curves / conversion ---
        elif command_type == "convert_object":
            object_name = params.get("object_name")
            target_type = params.get("target_type", "MESH")
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target=target_type)
            return {"status": "success", "result": {"target_type": target_type}, "message": f"Converted to {target_type}"}

        elif command_type == "set_curve_bevel":
            curve_name = params.get("curve_name")
            depth = float(params.get("depth", 0.0))
            resolution = int(params.get("resolution", 4))
            bevel_object = params.get("bevel_object")
            fill_mode = params.get("fill_mode", "FULL")
            curve_obj = bpy.data.objects.get(curve_name)
            if not curve_obj or curve_obj.type != 'CURVE':
                return {"status": "error", "message": f"Curve '{curve_name}' not found"}
            curve_obj.data.bevel_depth = depth
            curve_obj.data.bevel_resolution = resolution
            curve_obj.data.fill_mode = fill_mode
            if bevel_object:
                curve_obj.data.bevel_object = bpy.data.objects.get(bevel_object)
            return {"status": "success", "result": {"curve": curve_name}, "message": "Curve bevel updated"}

        # --- Macro ---
        elif command_type == "circular_array":
            object_name = params.get("object_name")
            count = int(params.get("count", 1))
            axis = (params.get("axis") or "Z").upper()
            center = params.get("center", (0.0, 0.0, 0.0))
            angle = float(params.get("angle", 6.283185))
            use_instances = bool(params.get("use_instances", True))
            obj = bpy.data.objects.get(object_name)
            if not obj:
                return {"status": "error", "message": f"Object '{object_name}' not found"}
            bpy.ops.object.mode_set(mode='OBJECT')
            created = []
            for i in range(count):
                dup = obj.copy()
                if not use_instances and obj.data:
                    dup.data = obj.data.copy()
                bpy.context.collection.objects.link(dup)
                frac = angle * (i / max(count, 1))
                if axis == "X":
                    rot = (frac, 0, 0)
                elif axis == "Y":
                    rot = (0, frac, 0)
                else:
                    rot = (0, 0, frac)
                dup.rotation_euler = rot
                dup.location = center
                created.append(dup.name)
            return {"status": "success", "result": {"created": created}, "message": f"Circular array created ({len(created)} objects)"}

        else:
            return {"status": "error", "message": f"Unknown command type: {command_type}"}

    except Exception as e:
        error_msg = f"Error executing command: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


def handle_client(client_socket, address):
    """Handle a client connection"""
    print(f"Hephaestus: Client connected from {address}")

    try:
        buffer = ""
        while server_running:
            data = client_socket.recv(4096)
            if not data:
                break

            buffer += data.decode('utf-8')

            # Process complete messages (newline-delimited)
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    try:
                        # Parse command
                        command = json.loads(line)
                        command_type = command.get("type")
                        params = command.get("params", {})

                        # Dispatch command to main thread via queue
                        done = {"event": threading.Event(), "response": None}
                        command_queue.put((command_type, params, done))
                        if not done["event"].wait(timeout=10):
                            response = {"status": "error", "message": f"Command '{command_type}' timed out"}
                        else:
                            response = done["response"]

                        # Send response
                        response_json = json.dumps(response) + "\n"
                        client_socket.sendall(response_json.encode('utf-8'))

                    except json.JSONDecodeError as e:
                        error_response = {
                            "status": "error",
                            "message": f"Invalid JSON: {str(e)}"
                        }
                        client_socket.sendall((json.dumps(error_response) + "\n").encode('utf-8'))

    except Exception as e:
        print(f"Hephaestus: Client error: {e}")
    finally:
        client_socket.close()
        print(f"Hephaestus: Client disconnected from {address}")


def server_loop(port):
    """Main server loop"""
    global server_socket, server_running

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind(('localhost', port))
        server_socket.listen(5)
        server_socket.settimeout(1.0)  # Allow periodic checks
        print(f"Hephaestus: Server listening on port {port}")

        while server_running:
            try:
                client_socket, address = server_socket.accept()
                # Handle each client in main thread (Blender API not thread-safe)
                handle_client(client_socket, address)
            except socket.timeout:
                continue
            except Exception as e:
                if server_running:
                    print(f"Hephaestus: Server error: {e}")

    finally:
        if server_socket:
            server_socket.close()
        print("Hephaestus: Server stopped")


# Operators
class HEPHAESTUS_OT_start_server(Operator):
    """Start the Hephaestus MCP server"""
    bl_idname = "hephaestus.start_server"
    bl_label = "Start Hephaestus Server"

    def execute(self, context):
        global server_thread, server_running

        if server_running:
            self.report({'WARNING'}, "Server already running")
            return {'CANCELLED'}

        props = context.scene.hephaestus_props
        port = props.port

        server_running = True
        server_thread = threading.Thread(target=server_loop, args=(port,), daemon=True)
        server_thread.start()

        self.report({'INFO'}, f"Hephaestus server started on port {port}")
        return {'FINISHED'}


class HEPHAESTUS_OT_stop_server(Operator):
    """Stop the Hephaestus MCP server"""
    bl_idname = "hephaestus.stop_server"
    bl_label = "Stop Hephaestus Server"

    def execute(self, context):
        global server_running, server_socket

        if not server_running:
            self.report({'WARNING'}, "Server not running")
            return {'CANCELLED'}

        server_running = False

        # Close socket to unblock accept()
        if server_socket:
            try:
                server_socket.close()
            except:
                pass

        self.report({'INFO'}, "Hephaestus server stopped")
        return {'FINISHED'}


# Properties
class HephaestusProperties(PropertyGroup):
    port: IntProperty(
        name="Port",
        description="Server port",
        default=9876,
        min=1024,
        max=65535
    )


# UI Panel
class HEPHAESTUS_PT_main_panel(Panel):
    """Hephaestus MCP main panel"""
    bl_label = "Hephaestus MCP"
    bl_idname = "HEPHAESTUS_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Hephaestus'

    def draw(self, context):
        layout = self.layout
        props = context.scene.hephaestus_props

        # Status
        box = layout.box()
        if server_running:
            box.label(text="Status: Connected", icon='LINKED')
        else:
            box.label(text="Status: Disconnected", icon='UNLINKED')

        # Port setting
        layout.prop(props, "port")

        # Control buttons
        row = layout.row()
        row.scale_y = 1.5
        if server_running:
            row.operator("hephaestus.stop_server", icon='PAUSE')
        else:
            row.operator("hephaestus.start_server", icon='PLAY')

        # Info
        box = layout.box()
        box.label(text="Hephaestus v0.1.0", icon='INFO')
        box.label(text="Advanced Blender MCP")


# Registration
classes = (
    HephaestusProperties,
    HEPHAESTUS_OT_start_server,
    HEPHAESTUS_OT_stop_server,
    HEPHAESTUS_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hephaestus_props = bpy.props.PointerProperty(type=HephaestusProperties)
    print("Hephaestus MCP addon registered")
    # Ensure command queue processor is running (idempotent)
    try:
        bpy.app.timers.register(process_command_queue, persistent=True)
    except Exception:
        pass


def unregister():
    global server_running
    server_running = False

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.hephaestus_props
    print("Hephaestus MCP addon unregistered")


if __name__ == "__main__":
    register()
