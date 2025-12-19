"""
Hephaestus Urban/Utility Tools
Higher-level helpers for snapping, alignment, scattering, roads, and facades.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response, validate_vector3
import logging

logger = logging.getLogger(__name__)


def snap_to_grid(step: float = 1.0, object_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Snap objects to a grid with the given step."""
    try:
        if step <= 0:
            return error_response("Step must be greater than 0")
        conn = ensure_connected()
        response = conn.send_command("snap_to_grid", {
            "step": step,
            "object_names": object_names or []
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Snapped objects"), data=response.get("result"))
        return error_response(response.get("message", "Failed to snap objects"))
    except Exception as e:
        return error_response("Failed to snap objects", e)


def align_objects(target: str, mode: str = "center", object_names: Optional[List[str]] = None, reference: Optional[float] = None) -> Dict[str, Any]:
    """Align objects along an axis (x/y/z) using min/center/max or a reference value."""
    try:
        if target.upper() not in {"X", "Y", "Z"}:
            return error_response("Target must be X, Y, or Z")
        if mode not in {"min", "center", "max", "value"}:
            return error_response("Mode must be min, center, max, or value")

        conn = ensure_connected()
        response = conn.send_command("align_objects", {
            "target": target.upper(),
            "mode": mode,
            "reference": reference,
            "object_names": object_names or []
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Aligned objects"), data=response.get("result"))
        return error_response(response.get("message", "Failed to align objects"))
    except Exception as e:
        return error_response("Failed to align objects", e)


def scatter_along_curve(source_object: str, curve_name: str, count: int, jitter: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
    """Scatter duplicates of a source object along a curve."""
    try:
        if count < 1:
            return error_response("Count must be at least 1")
        if jitter is not None:
            jitter = validate_vector3(jitter, "jitter")
        conn = ensure_connected()
        response = conn.send_command("scatter_along_curve", {
            "source_object": source_object,
            "curve_name": curve_name,
            "count": count,
            "jitter": jitter
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Scattered objects"), data=response.get("result"))
        return error_response(response.get("message", "Failed to scatter along curve"))
    except Exception as e:
        return error_response("Failed to scatter along curve", e)


def create_road(width: float, length: float, segments: int = 4, add_sidewalk: bool = True, sidewalk_width: float = 1.5, sidewalk_height: float = 0.15) -> Dict[str, Any]:
    """Create a simple road mesh (and optional sidewalks)."""
    try:
        if width <= 0 or length <= 0:
            return error_response("Width and length must be greater than 0")
        conn = ensure_connected()
        response = conn.send_command("create_road", {
            "width": width,
            "length": length,
            "segments": segments,
            "add_sidewalk": add_sidewalk,
            "sidewalk_width": sidewalk_width,
            "sidewalk_height": sidewalk_height
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Road created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create road"))
    except Exception as e:
        return error_response("Failed to create road", e)


def repeat_facade(base_object: str, floors: int = 5, bays: int = 4, floor_height: float = 3.0, bay_width: float = 3.0) -> Dict[str, Any]:
    """Repeat a base object to form a facade grid (floors x bays)."""
    try:
        if floors < 1 or bays < 1:
            return error_response("Floors and bays must be at least 1")
        conn = ensure_connected()
        response = conn.send_command("repeat_facade", {
            "base_object": base_object,
            "floors": floors,
            "bays": bays,
            "floor_height": floor_height,
            "bay_width": bay_width
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Facade created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to repeat facade"))
    except Exception as e:
        return error_response("Failed to repeat facade", e)


def macro_city_block(style: str = "modern", buildings: int = 6, lamps_per_side: int = 6) -> Dict[str, Any]:
    """High-level macro to create a simple city block with road, sidewalks, buildings, lamps."""
    try:
        conn = ensure_connected()
        response = conn.send_command("macro_city_block", {
            "style": style,
            "buildings": buildings,
            "lamps_per_side": lamps_per_side
        })
        if response["status"] == "success":
            return success_response(response.get("message", "City block created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to run macro_city_block"))
    except Exception as e:
        return error_response("Failed to run macro_city_block", e)


def mech_rig(style: str = "basic", include_chain: bool = True) -> Dict[str, Any]:
    """
    Convenience macro to build a small mech rig: two sprockets + optional chain + arm base.
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("mech_rig", {"style": style, "include_chain": include_chain})
        if response["status"] == "success":
            return success_response(response.get("message", "Mech rig created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create mech rig"))
    except Exception as e:
        return error_response("Failed to create mech rig", e)


def create_building_box(
    width: float = 10.0,
    depth: float = 10.0,
    height: float = 15.0,
    floors: int = 5,
    name: str = "Building"
) -> Dict[str, Any]:
    """Create a parametric building volume with floor divisions."""
    try:
        if width <= 0 or depth <= 0 or height <= 0:
            return error_response("Dimensions must be greater than 0")
        if floors < 1:
            return error_response("Floors must be at least 1")

        conn = ensure_connected()
        response = conn.send_command("create_building_box", {
            "width": width,
            "depth": depth,
            "height": height,
            "floors": floors,
            "name": name
        })

        if response["status"] == "success":
            return success_response(response.get("message", "Building created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create building"))
    except Exception as e:
        return error_response("Failed to create building", e)


def create_window_grid(
    building_name: str,
    floors: int = 5,
    windows_per_floor: int = 4,
    window_width: float = 1.5,
    window_height: float = 2.0,
    spacing: float = 0.5,
    inset: float = 0.1
) -> Dict[str, Any]:
    """Create a parametric grid of windows on a building."""
    try:
        if floors < 1 or windows_per_floor < 1:
            return error_response("Floors and windows_per_floor must be at least 1")
        if window_width <= 0 or window_height <= 0:
            return error_response("Window dimensions must be greater than 0")

        conn = ensure_connected()
        response = conn.send_command("create_window_grid", {
            "building_name": building_name,
            "floors": floors,
            "windows_per_floor": windows_per_floor,
            "window_width": window_width,
            "window_height": window_height,
            "spacing": spacing,
            "inset": inset
        })

        if response["status"] == "success":
            return success_response(response.get("message", "Windows created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create windows"))
    except Exception as e:
        return error_response("Failed to create windows", e)


def array_along_path(
    source_object: str,
    curve_name: str,
    count: int = 10,
    align_to_curve: bool = True,
    spacing_factor: float = 1.0
) -> Dict[str, Any]:
    """Array objects along a curve path."""
    try:
        if count < 1:
            return error_response("Count must be at least 1")

        conn = ensure_connected()
        response = conn.send_command("array_along_path", {
            "source_object": source_object,
            "curve_name": curve_name,
            "count": count,
            "align_to_curve": align_to_curve,
            "spacing_factor": spacing_factor
        })

        if response["status"] == "success":
            return success_response(response.get("message", "Array created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create array"))
    except Exception as e:
        return error_response("Failed to create array", e)


def randomize_transform(
    object_names: Optional[List[str]] = None,
    location_range: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_range: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale_range: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    seed: int = 0
) -> Dict[str, Any]:
    """Add random variation to object transforms."""
    try:
        conn = ensure_connected()
        response = conn.send_command("randomize_transform", {
            "object_names": object_names or [],
            "location_range": list(location_range),
            "rotation_range": list(rotation_range),
            "scale_range": list(scale_range),
            "seed": seed
        })

        if response["status"] == "success":
            return success_response(response.get("message", "Transforms randomized"), data=response.get("result"))
        return error_response(response.get("message", "Failed to randomize"))
    except Exception as e:
        return error_response("Failed to randomize transforms", e)


def create_stairs(
    steps: int = 10,
    step_width: float = 2.0,
    step_depth: float = 0.3,
    step_height: float = 0.2,
    name: str = "Stairs",
    location: Tuple[float, float, float] = (0, 0, 0)
) -> Dict[str, Any]:
    """Create parametric stairs."""
    try:
        if steps < 1:
            return error_response("Steps must be at least 1")
        if step_width <= 0 or step_depth <= 0 or step_height <= 0:
            return error_response("Step dimensions must be greater than 0")

        conn = ensure_connected()
        response = conn.send_command("create_stairs", {
            "steps": steps,
            "step_width": step_width,
            "step_depth": step_depth,
            "step_height": step_height,
            "name": name,
            "location": list(location)
        })

        if response["status"] == "success":
            return success_response(response.get("message", "Stairs created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create stairs"))
    except Exception as e:
        return error_response("Failed to create stairs", e)
