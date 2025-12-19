"""
Advanced modeling tools and macros for Hephaestus v1.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import error_response, success_response, validate_vector3


def _send(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = ensure_connected()
    response = conn.send_command(name, payload)
    if response.get("status") == "success":
        return success_response(response.get("message", f"{name} ok"), data=response.get("result"))
    return error_response(response.get("message", f"Failed to run {name}"))


# Edit mode operations
def spin(object_name: str, angle: float = 6.283185, steps: int = 12, axis: str = "Z", center: Tuple[float, float, float] | None = None, dupli: bool = False) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "angle": float(angle),
        "steps": int(steps),
        "axis": axis,
        "center": validate_vector3(center, "center") if center is not None else None,
        "dupli": bool(dupli),
    }
    return _send("spin", payload)


def screw(object_name: str, screw_offset: float = 1.0, iterations: int = 2, steps: int = 16, axis: str = "Z") -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "screw_offset": float(screw_offset),
        "iterations": int(iterations),
        "steps": int(steps),
        "axis": axis,
    }
    return _send("screw", payload)


def fill_hole(object_name: str, mode: str = "BEAUTY", span: int = 1, offset: int = 0) -> Dict[str, Any]:
    payload = {"object_name": object_name, "mode": mode, "span": int(span), "offset": int(offset)}
    return _send("fill_hole", payload)


def shrink_fatten(object_name: str, offset: float, use_even_offset: bool = True) -> Dict[str, Any]:
    payload = {"object_name": object_name, "offset": float(offset), "use_even_offset": bool(use_even_offset)}
    return _send("shrink_fatten", payload)


def set_edge_crease(object_name: str, edge_indices: Optional[Sequence[int]] = None, value: float = 1.0) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"object_name": object_name, "value": float(value)}
    if edge_indices is not None:
        payload["edge_indices"] = list(edge_indices)
    return _send("set_edge_crease", payload)


def set_bevel_weight(object_name: str, edge_indices: Optional[Sequence[int]] = None, value: float = 1.0) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"object_name": object_name, "value": float(value)}
    if edge_indices is not None:
        payload["edge_indices"] = list(edge_indices)
    return _send("set_bevel_weight", payload)


def mark_sharp(object_name: str, edge_indices: Optional[Sequence[int]] = None, clear: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"object_name": object_name, "clear": bool(clear)}
    if edge_indices is not None:
        payload["edge_indices"] = list(edge_indices)
    return _send("mark_sharp", payload)


def set_shade_smooth(
    object_name: str,
    smooth: bool = True,
    use_auto_smooth: bool = True,
    auto_smooth_angle: float = 0.523599,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "smooth": bool(smooth),
        "use_auto_smooth": bool(use_auto_smooth),
        "auto_smooth_angle": float(auto_smooth_angle),
    }
    return _send("set_shade_smooth", payload)


# Vertex groups
def create_vertex_group(object_name: str, group_name: str, vertex_indices: Optional[Sequence[int]] = None, weight: float = 1.0) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"object_name": object_name, "group_name": group_name, "weight": float(weight)}
    if vertex_indices is not None:
        payload["vertex_indices"] = list(vertex_indices)
    return _send("create_vertex_group", payload)


def assign_to_vertex_group(
    object_name: str,
    group_name: str,
    vertex_indices: Sequence[int],
    weight: float = 1.0,
    mode: str = "REPLACE",
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "group_name": group_name,
        "vertex_indices": list(vertex_indices),
        "weight": float(weight),
        "mode": mode,
    }
    return _send("assign_to_vertex_group", payload)


def remove_from_vertex_group(object_name: str, group_name: str, vertex_indices: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"object_name": object_name, "group_name": group_name}
    if vertex_indices is not None:
        payload["vertex_indices"] = list(vertex_indices)
    return _send("remove_from_vertex_group", payload)


def get_vertex_groups(object_name: str) -> Dict[str, Any]:
    return _send("get_vertex_groups", {"object_name": object_name})


# Modifiers
def add_solidify(
    object_name: str,
    thickness: float = 0.01,
    offset: float = -1.0,
    use_even_thickness: bool = True,
    use_quality_normals: bool = True,
    use_rim: bool = True,
    use_rim_only: bool = False,
    material_offset: int = 0,
    material_offset_rim: int = 0,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "thickness": float(thickness),
        "offset": float(offset),
        "use_even_thickness": bool(use_even_thickness),
        "use_quality_normals": bool(use_quality_normals),
        "use_rim": bool(use_rim),
        "use_rim_only": bool(use_rim_only),
        "material_offset": int(material_offset),
        "material_offset_rim": int(material_offset_rim),
    }
    return _send("add_solidify", payload)


def add_screw_modifier(
    object_name: str,
    angle: float = 6.283185,
    screw_offset: float = 0.0,
    iterations: int = 1,
    steps: int = 16,
    axis: str = "Z",
    use_merge_vertices: bool = True,
    merge_threshold: float = 0.0001,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "angle": float(angle),
        "screw_offset": float(screw_offset),
        "iterations": int(iterations),
        "steps": int(steps),
        "axis": axis,
        "use_merge_vertices": bool(use_merge_vertices),
        "merge_threshold": float(merge_threshold),
    }
    return _send("add_screw_modifier", payload)


def add_shrinkwrap(
    object_name: str,
    target: str,
    wrap_method: str = "NEAREST_SURFACEPOINT",
    wrap_mode: str = "ON_SURFACE",
    offset: float = 0.0,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "target": target,
        "wrap_method": wrap_method,
        "wrap_mode": wrap_mode,
        "offset": float(offset),
    }
    return _send("add_shrinkwrap", payload)


def add_weighted_normal(
    object_name: str,
    weight: int = 50,
    mode: str = "FACE_AREA",
    keep_sharp: bool = True,
    face_influence: bool = False,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "weight": int(weight),
        "mode": mode,
        "keep_sharp": bool(keep_sharp),
        "face_influence": bool(face_influence),
    }
    return _send("add_weighted_normal", payload)


def add_lattice(
    object_name: str,
    lattice_object: str | None = None,
    resolution: Tuple[int, int, int] = (2, 2, 2),
    interpolation: str = "KEY_LINEAR",
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "lattice_object": lattice_object,
        "resolution": tuple(resolution),
        "interpolation": interpolation,
    }
    return _send("add_lattice", payload)


def add_wireframe(
    object_name: str,
    thickness: float = 0.02,
    use_even_offset: bool = True,
    use_boundary: bool = True,
    use_replace: bool = True,
    material_offset: int = 0,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "thickness": float(thickness),
        "use_even_offset": bool(use_even_offset),
        "use_boundary": bool(use_boundary),
        "use_replace": bool(use_replace),
        "material_offset": int(material_offset),
    }
    return _send("add_wireframe", payload)


def add_skin(object_name: str, branch_smoothing: float = 0.0, use_smooth_shade: bool = False) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "branch_smoothing": float(branch_smoothing),
        "use_smooth_shade": bool(use_smooth_shade),
    }
    return _send("add_skin", payload)


# Curve + conversion helpers
def convert_object(object_name: str, target_type: str = "MESH") -> Dict[str, Any]:
    payload = {"object_name": object_name, "target_type": target_type}
    return _send("convert_object", payload)


def set_curve_bevel(
    curve_name: str,
    depth: float = 0.0,
    resolution: int = 4,
    bevel_object: str | None = None,
    fill_mode: str = "FULL",
) -> Dict[str, Any]:
    payload = {
        "curve_name": curve_name,
        "depth": float(depth),
        "resolution": int(resolution),
        "bevel_object": bevel_object,
        "fill_mode": fill_mode,
    }
    return _send("set_curve_bevel", payload)


def circular_array(
    object_name: str,
    count: int,
    axis: str = "Z",
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    angle: float = 6.283185,
    use_instances: bool = True,
) -> Dict[str, Any]:
    payload = {
        "object_name": object_name,
        "count": int(count),
        "axis": axis,
        "center": validate_vector3(center, "center"),
        "angle": float(angle),
        "use_instances": bool(use_instances),
    }
    return _send("circular_array", payload)
