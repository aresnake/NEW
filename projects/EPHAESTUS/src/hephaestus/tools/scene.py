"""
Hephaestus Scene Tools
Tools for scene information and management
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response, validate_vector3
from hephaestus.tools import camera, objects
import math
import logging

logger = logging.getLogger(__name__)


def get_scene_info() -> Dict[str, Any]:
    """
    Get comprehensive scene information

    Returns:
        Dict with scene objects, collections, materials, cameras, lights
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("get_scene_info")

        if response["status"] == "success":
            return success_response(
                "Scene info retrieved successfully",
                data=response.get("result", {})
            )
        else:
            return error_response(response.get("message", "Failed to get scene info"))

    except Exception as e:
        return error_response("Failed to get scene info", e)


def get_object_info(object_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific object

    Args:
        object_name: Name of the object

    Returns:
        Dict with object details (type, location, rotation, scale, materials, etc.)
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("get_object_info", {"object_name": object_name})

        if response["status"] == "success":
            return success_response(
                f"Object info for '{object_name}' retrieved",
                data=response.get("result", {})
            )
        else:
            return error_response(response.get("message", f"Failed to get object info for '{object_name}'"))

    except Exception as e:
        return error_response(f"Failed to get object info for '{object_name}'", e)


def get_viewport_screenshot(
    max_size: int = 800,
    shading: Optional[str] = None,
    output_dir: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a screenshot of the current viewport

    Args:
        max_size: Maximum size in pixels for the largest dimension
        shading: Optional shading override ("SOLID", "WIREFRAME", ...)

    Returns:
        Dict with screenshot path and info
    """
    try:
        conn = ensure_connected()
        payload = {"max_size": max_size}
        if shading:
            payload["shading"] = shading
        if output_dir:
            payload["output_dir"] = output_dir
        if prefix:
            payload["prefix"] = prefix
        response = conn.send_command("get_viewport_screenshot", payload)

        if response["status"] == "success":
            return success_response(
                "Viewport screenshot captured",
                data=response.get("result", {})
            )
        else:
            return error_response(response.get("message", "Failed to capture screenshot"))

    except Exception as e:
        return error_response("Failed to capture screenshot", e)


def capture_view(
    camera_name: Optional[str] = None,
    preset: Optional[str] = None,
    max_size: int = 800,
    shading: Optional[str] = None,
    output_dir: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a screenshot after optionally setting a camera + preset.
    """
    try:
        conn = ensure_connected()
        payload: Dict[str, Any] = {"max_size": max_size}
        if camera_name:
            payload["camera_name"] = camera_name
        if preset:
            payload["preset"] = preset
        if shading:
            payload["shading"] = shading
        if output_dir:
            payload["output_dir"] = output_dir
        if prefix:
            payload["prefix"] = prefix
        response = conn.send_command("capture_view", payload)
        if response["status"] == "success":
            return success_response("View captured", data=response.get("result", {}))
        return error_response(response.get("message", "Failed to capture view"))
    except Exception as e:
        return error_response("Failed to capture view", e)


def describe_view(
    camera_name: Optional[str] = None,
    preset: Optional[str] = None,
    object_names: Optional[List[str]] = None,
    max_size: int = 800,
    shading: Optional[str] = None,
    output_dir: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a view and return screenshot + bbox info for listed (or selected) objects.
    """
    try:
        conn = ensure_connected()
        payload: Dict[str, Any] = {"max_size": max_size}
        if camera_name:
            payload["camera_name"] = camera_name
        if preset:
            payload["preset"] = preset
        if object_names:
            payload["object_names"] = object_names
        if shading:
            payload["shading"] = shading
        if output_dir:
            payload["output_dir"] = output_dir
        if prefix:
            payload["prefix"] = prefix
        response = conn.send_command("describe_view", payload)
        if response["status"] == "success":
            return success_response("View described", data=response.get("result", {}))
        return error_response(response.get("message", "Failed to describe view"))
    except Exception as e:
        return error_response("Failed to describe view", e)


def measure_angle(
    point_a: Tuple[float, float, float],
    point_b: Tuple[float, float, float],
    point_c: Tuple[float, float, float],
) -> Dict[str, Any]:
    """
    Measure angle at point B formed by A-B-C (in radians/degrees).
    """
    try:
        conn = ensure_connected()
        payload = {
            "point_a": validate_vector3(point_a, "point_a"),
            "point_b": validate_vector3(point_b, "point_b"),
            "point_c": validate_vector3(point_c, "point_c"),
        }
        response = conn.send_command("measure_angle", payload)
        if response["status"] == "success":
            return success_response("Angle measured", data=response.get("result"))
        return error_response(response.get("message", "Failed to measure angle"))
    except Exception as e:
        return error_response("Failed to measure angle", e)


def measure_mesh(
    object_name: str,
    mode: str = "AREA",
) -> Dict[str, Any]:
    """
    Measure area or volume of an object mesh (evaluated).
    mode: "AREA" | "VOLUME"
    """
    try:
        conn = ensure_connected()
        payload = {"object_name": object_name, "mode": mode}
        response = conn.send_command("measure_mesh", payload)
        if response["status"] == "success":
            return success_response("Mesh measured", data=response.get("result"))
        return error_response(response.get("message", "Failed to measure mesh"))
    except Exception as e:
        return error_response("Failed to measure mesh", e)


def set_viewport_shading(shading: str) -> Dict[str, Any]:
    try:
        conn = ensure_connected()
        response = conn.send_command("set_viewport_shading", {"shading": shading})
        if response["status"] == "success":
            return success_response("Viewport shading set", data=response.get("result"))
        return error_response(response.get("message", "Failed to set shading"))
    except Exception as e:
        return error_response("Failed to set viewport shading", e)


def scatter_on_surface(
    target_mesh: str,
    source_object: str,
    count: int | None = None,
    seed: int = 0,
    jitter: float = 0.2,
    align_normal: bool = True,
    density: float | None = None,
    max_points: int | None = None,
) -> Dict[str, Any]:
    """
    Scatter copies of source_object onto target_mesh surface.
    Optional density (points per unit area) and max_points cap.
    """
    try:
        conn = ensure_connected()
        payload: Dict[str, Any] = {
            "target_mesh": target_mesh,
            "source_object": source_object,
            "seed": seed,
            "jitter": jitter,
            "align_normal": align_normal,
        }
        if count is not None:
            payload["count"] = count
        if density is not None:
            payload["density"] = density
        if max_points is not None:
            payload["max_points"] = max_points
        response = conn.send_command("scatter_on_surface", payload)
        if response["status"] == "success":
            return success_response("Scattered on surface", data=response.get("result"))
        return error_response(response.get("message", "Failed to scatter"))
    except Exception as e:
        return error_response("Failed to scatter on surface", e)


def render_preview(
    camera_name: str | None = None,
    filepath: str | None = None,
    res_x: int = 800,
    res_y: int = 800,
    engine: str = "BLENDER_EEVEE",
    samples: int = 16,
) -> Dict[str, Any]:
    """
    Low-sample render for quick preview.
    """
    try:
        conn = ensure_connected()
        payload: Dict[str, Any] = {
            "camera_name": camera_name,
            "filepath": filepath,
            "res_x": res_x,
            "res_y": res_y,
            "engine": engine,
            "samples": samples,
        }
        response = conn.send_command("render_preview", payload)
        if response["status"] == "success":
            return success_response("Render preview done", data=response.get("result"))
        return error_response(response.get("message", "Failed to render preview"))
    except Exception as e:
        return error_response("Failed to render preview", e)


def measure_distance(
    object_a: Optional[str] = None,
    object_b: Optional[str] = None,
    point_a: Optional[Tuple[float, float, float]] = None,
    point_b: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, Any]:
    """
    Measure distance between two objects (origins) or two points.
    """
    try:
        params: Dict[str, Any] = {}
        if object_a and object_b:
            params["object_a"] = object_a
            params["object_b"] = object_b
        if point_a and point_b:
            params["point_a"] = validate_vector3(point_a, "point_a")
            params["point_b"] = validate_vector3(point_b, "point_b")
        if not params:
            return error_response("Provide either object_a/object_b or point_a/point_b")

        conn = ensure_connected()
        response = conn.send_command("measure_distance", params)
        if response["status"] == "success":
            return success_response(response.get("message", "Distance measured"), data=response.get("result"))
        return error_response(response.get("message", "Failed to measure distance"))
    except Exception as e:
        return error_response("Failed to measure distance", e)


def bbox_info(object_name: str) -> Dict[str, Any]:
    """
    Get bounding box info (local/world).
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("bbox_info", {"object_name": object_name})
        if response["status"] == "success":
            return success_response(response.get("message", "BBox info"), data=response.get("result"))
        return error_response(response.get("message", "Failed to get bbox info"))
    except Exception as e:
        return error_response("Failed to get bbox info", e)


def multi_view_screenshots(
    camera_name: str,
    presets: List[str] = None,
    max_size: int = 800,
    shading: Optional[str] = None,
    output_dir: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture multiple screenshots from a camera using a list of presets.
    Presets can be: product, top, front, isometric, etc. (must be supported by set_camera_preset).
    """
    presets = presets or ["product", "top", "front", "isometric"]
    paths = []
    for p in presets:
        camera.set_camera_preset(camera_name, p)
        shot = get_viewport_screenshot(max_size, shading=shading, output_dir=output_dir, prefix=prefix)
        if shot.get("success"):
            paths.append(shot.get("data", {}).get("path"))
    return success_response("Captured multi-view screenshots", {"paths": paths, "presets": presets})


def orbit_screenshots(
    camera_name: str,
    center: Tuple[float, float, float] = (0, 0, 0),
    radius: float = 8.0,
    shots: int = 8,
    max_size: int = 800,
    shading: Optional[str] = None,
    output_dir: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture screenshots while orbiting around a center point on the XY plane.
    """
    paths = []
    cx, cy, cz = center
    for i in range(max(1, shots)):
        theta = (2 * math.pi * i) / shots
        loc = (cx + radius * math.cos(theta), cy + radius * math.sin(theta), cz + radius * 0.5)
        objects.transform_object(camera_name, location=loc)
        camera.point_camera_at(camera_name, center)
        shot = get_viewport_screenshot(max_size, shading=shading, output_dir=output_dir, prefix=prefix)
        if shot.get("success"):
            paths.append(shot.get("data", {}).get("path"))
    return success_response("Orbit screenshots captured", {"paths": paths, "center": center})


def create_collection(name: str, parent: Optional[str] = None, color: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new collection

    Args:
        name: Collection name
        parent: Optional parent collection name
        color: Optional color tag (e.g., "COLOR_01" to "COLOR_08")

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        params = {"name": name}
        if parent:
            params["parent"] = parent
        if color:
            params["color"] = color

        response = conn.send_command("create_collection", params)

        if response["status"] == "success":
            return success_response(f"Collection '{name}' created", data=response.get("result"))
        else:
            return error_response(response.get("message", f"Failed to create collection '{name}'"))

    except Exception as e:
        return error_response(f"Failed to create collection '{name}'", e)


def move_to_collection(object_names: Union[str, List[str]], collection_name: str) -> Dict[str, Any]:
    """
    Move objects to a collection

    Args:
        object_names: Single object name or list of object names
        collection_name: Target collection name

    Returns:
        Success/error dict
    """
    try:
        # Normalize to list
        if isinstance(object_names, str):
            object_names = [object_names]

        conn = ensure_connected()
        response = conn.send_command("move_to_collection", {
            "object_names": object_names,
            "collection_name": collection_name
        })

        if response["status"] == "success":
            count = len(object_names)
            return success_response(
                f"Moved {count} object(s) to collection '{collection_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to move objects to collection"))

    except Exception as e:
        return error_response("Failed to move objects to collection", e)


def get_collection_tree() -> Dict[str, Any]:
    """
    Get the complete collection hierarchy

    Returns:
        Dict with collection tree structure
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("get_collection_tree")

        if response["status"] == "success":
            return success_response(
                "Collection tree retrieved",
                data=response.get("result", {})
            )
        else:
            return error_response(response.get("message", "Failed to get collection tree"))

    except Exception as e:
        return error_response("Failed to get collection tree", e)


def batch_select(pattern: str, object_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Select objects by name pattern

    Args:
        pattern: Regex pattern for object names
        object_type: Optional filter by type (MESH, LIGHT, CAMERA, etc.)

    Returns:
        Dict with selected objects
    """
    try:
        conn = ensure_connected()
        params = {"pattern": pattern}
        if object_type:
            params["object_type"] = object_type

        response = conn.send_command("batch_select", params)

        if response["status"] == "success":
            return success_response(
                f"Objects selected by pattern '{pattern}'",
                data=response.get("result", {})
            )
        else:
            return error_response(response.get("message", "Failed to select objects"))

    except Exception as e:
        return error_response("Failed to select objects", e)


def clear_scene() -> Dict[str, Any]:
    """Delete all objects in the scene."""
    try:
        conn = ensure_connected()
        response = conn.send_command("clear_scene")
        if response["status"] == "success":
            return success_response("Scene cleared", data=response.get("result"))
        return error_response(response.get("message", "Failed to clear scene"))
    except Exception as e:
        return error_response("Failed to clear scene", e)
