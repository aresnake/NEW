"""
Mesh edit and UV/BMesh helpers for Hephaestus.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import error_response, success_response, validate_vector3


def edit_mode_enter(object_name: str, mode: str = "EDIT") -> Dict[str, Any]:
    """Enter edit/object mode on a mesh."""
    try:
        conn = ensure_connected()
        response = conn.send_command("edit_mode_enter", {"object_name": object_name, "mode": mode})
        if response["status"] == "success":
            return success_response(response.get("message", "Edit mode updated"), data=response.get("result"))
        return error_response(response.get("message", "Failed to switch mode"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to switch edit mode", exc)


def edit_mode_exit(object_name: str) -> Dict[str, Any]:
    """Exit edit mode to object mode."""
    return edit_mode_enter(object_name, mode="OBJECT")


def select_geometry(
    object_name: str,
    mode: str,
    indices: Optional[Sequence[int]] = None,
    pattern: str = "ALL",
    expand: int = 0,
) -> Dict[str, Any]:
    """Select geometry elements by indices or pattern."""
    try:
        payload: Dict[str, Any] = {
            "object_name": object_name,
            "mode": mode,
            "pattern": pattern,
            "expand": expand,
        }
        if indices is not None:
            payload["indices"] = list(indices)
        conn = ensure_connected()
        response = conn.send_command("select_geometry", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Selection updated"), data=response.get("result"))
        return error_response(response.get("message", "Failed to select geometry"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to select geometry", exc)


def extrude(
    object_name: str,
    mode: str,
    offset: Tuple[float, float, float],
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Extrude selected elements with optional offset/scale."""
    try:
        payload = {
            "object_name": object_name,
            "mode": mode,
            "offset": validate_vector3(offset, "offset"),
            "scale": float(scale),
        }
        conn = ensure_connected()
        response = conn.send_command("extrude", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Extrude ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to extrude"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to extrude", exc)


def loop_cut(object_name: str, edge_index: int, cuts: int = 1, slide: float = 0.0, even: bool = False) -> Dict[str, Any]:
    """Insert loop cuts starting from an edge."""
    try:
        payload = {
            "object_name": object_name,
            "edge_index": int(edge_index),
            "cuts": int(cuts),
            "slide": float(slide),
            "even": bool(even),
        }
        conn = ensure_connected()
        response = conn.send_command("loop_cut", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Loop cut ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to add loop cut"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to add loop cut", exc)


def inset_faces(
    object_name: str,
    face_indices: Optional[Sequence[int]],
    thickness: float,
    depth: float = 0.0,
    use_boundary: bool = True,
    use_even_offset: bool = True,
) -> Dict[str, Any]:
    """Inset faces with optional depth."""
    try:
        payload: Dict[str, Any] = {
            "object_name": object_name,
            "thickness": float(thickness),
            "depth": float(depth),
            "use_boundary": bool(use_boundary),
            "use_even_offset": bool(use_even_offset),
        }
        if face_indices is not None:
            payload["face_indices"] = list(face_indices)
        conn = ensure_connected()
        response = conn.send_command("inset_faces", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Inset ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to inset faces"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to inset faces", exc)


def bevel_edges(
    object_name: str,
    edge_indices: Optional[Sequence[int]],
    width: float,
    segments: int = 1,
    profile: float = 0.5,
    clamp: bool = True,
) -> Dict[str, Any]:
    """Selective edge bevel."""
    try:
        payload: Dict[str, Any] = {
            "object_name": object_name,
            "width": float(width),
            "segments": int(segments),
            "profile": float(profile),
            "clamp": bool(clamp),
        }
        if edge_indices is not None:
            payload["edge_indices"] = list(edge_indices)
        conn = ensure_connected()
        response = conn.send_command("bevel_edges", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Bevel ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to bevel edges"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to bevel edges", exc)


def bridge_edge_loops(
    object_name: str,
    loop1_indices: Sequence[int],
    loop2_indices: Sequence[int],
    cuts: int = 0,
    twist: int = 0,
) -> Dict[str, Any]:
    """Bridge between two edge loops."""
    try:
        payload = {
            "object_name": object_name,
            "loop1_indices": list(loop1_indices),
            "loop2_indices": list(loop2_indices),
            "cuts": int(cuts),
            "twist": int(twist),
        }
        conn = ensure_connected()
        response = conn.send_command("bridge_edge_loops", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Bridge ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to bridge edge loops"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to bridge edge loops", exc)


def merge_vertices(object_name: str, mode: str = "CENTER", threshold: float = 0.0001) -> Dict[str, Any]:
    """Merge selected vertices with a given mode."""
    try:
        payload = {
            "object_name": object_name,
            "mode": mode,
            "threshold": float(threshold),
        }
        conn = ensure_connected()
        response = conn.send_command("merge_vertices", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Merge ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to merge vertices"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to merge vertices", exc)


def dissolve(object_name: str, mode: str = "EDGE", angle_limit: float = 0.0872665) -> Dict[str, Any]:
    """Dissolve selected elements."""
    try:
        payload = {"object_name": object_name, "mode": mode, "angle_limit": float(angle_limit)}
        conn = ensure_connected()
        response = conn.send_command("dissolve", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Dissolve ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to dissolve"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to dissolve", exc)


def knife_cut(object_name: str, cut_points: Sequence[Sequence[float]], cut_through: bool = False) -> Dict[str, Any]:
    """Perform a knife projection along a polyline of world points."""
    try:
        points = [validate_vector3(p, "cut_point") for p in cut_points]
        payload = {"object_name": object_name, "cut_points": points, "cut_through": bool(cut_through)}
        conn = ensure_connected()
        response = conn.send_command("knife_cut", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Knife cut ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to knife cut"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to knife cut", exc)


def uv_unwrap(
    object_name: str,
    method: str = "ANGLE_BASED",
    angle_limit: float = 66.0,
    island_margin: float = 0.02,
) -> Dict[str, Any]:
    """UV unwrap helper."""
    try:
        payload = {
            "object_name": object_name,
            "method": method,
            "angle_limit": float(angle_limit),
            "island_margin": float(island_margin),
        }
        conn = ensure_connected()
        response = conn.send_command("uv_unwrap", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "UV unwrap ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to unwrap"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to unwrap", exc)


def uv_mark_seam(object_name: str, edge_indices: Sequence[int], clear: bool = False) -> Dict[str, Any]:
    """Mark or clear seams on edges."""
    try:
        payload = {"object_name": object_name, "edge_indices": list(edge_indices), "clear": bool(clear)}
        conn = ensure_connected()
        response = conn.send_command("uv_mark_seam", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Seams updated"), data=response.get("result"))
        return error_response(response.get("message", "Failed to update seams"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to update seams", exc)


def bmesh_create_geometry(
    object_name: str,
    vertices: Sequence[Sequence[float]],
    edges: Optional[Sequence[Sequence[int]]] = None,
    faces: Optional[Sequence[Sequence[int]]] = None,
) -> Dict[str, Any]:
    """Create/overwrite mesh geometry using explicit lists."""
    try:
        payload: Dict[str, Any] = {
            "object_name": object_name,
            "vertices": [validate_vector3(v, "vertex") for v in vertices],
        }
        if edges is not None:
            payload["edges"] = [list(e) for e in edges]
        if faces is not None:
            payload["faces"] = [list(f) for f in faces]
        conn = ensure_connected()
        response = conn.send_command("bmesh_create_geometry", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Geometry written"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create geometry"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to create geometry", exc)


def bmesh_get_geometry(object_name: str) -> Dict[str, Any]:
    """Return raw mesh geometry lists."""
    try:
        conn = ensure_connected()
        response = conn.send_command("bmesh_get_geometry", {"object_name": object_name})
        if response["status"] == "success":
            return success_response(response.get("message", "Geometry fetched"), data=response.get("result"))
        return error_response(response.get("message", "Failed to get geometry"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to get geometry", exc)
