"""
Hephaestus Modifier Tools
Tools for adding, editing, applying, and removing modifiers
"""

from typing import Dict, Any, Optional
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response
import logging

logger = logging.getLogger(__name__)


def add_modifier(object_name: str, modifier_type: str, name: Optional[str] = None, **params) -> Dict[str, Any]:
    """
    Add a modifier to an object.

    Supported modifier_type values (uppercase):
    ARRAY, MIRROR, SUBDIVISION, BOOLEAN, SOLIDIFY, BEVEL
    """
    try:
        supported = {"ARRAY", "MIRROR", "SUBDIVISION", "SUBSURF", "BOOLEAN", "SOLIDIFY", "BEVEL"}
        mod_type = modifier_type.upper()
        if mod_type == "SUBDIVISION":
            mod_type = "SUBSURF"
        if mod_type not in supported:
            return error_response(f"Unsupported modifier type '{modifier_type}'. Supported: {', '.join(sorted(supported))}")

        payload = {"object_name": object_name, "modifier_type": mod_type}
        if name:
            payload["name"] = name
        payload.update(params)

        conn = ensure_connected()
        response = conn.send_command("add_modifier", payload)

        if response["status"] == "success":
            return success_response(f"Added {mod_type} modifier to '{object_name}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to add modifier"))

    except Exception as e:
        return error_response(f"Failed to add modifier to '{object_name}'", e)


def modify_modifier(object_name: str, modifier_name: str, **params) -> Dict[str, Any]:
    """Update properties on an existing modifier."""
    try:
        if not params:
            return error_response("No modifier parameters provided")

        conn = ensure_connected()
        response = conn.send_command("modify_modifier", {
            "object_name": object_name,
            "modifier_name": modifier_name,
            **params
        })

        if response["status"] == "success":
            return success_response(f"Modified modifier '{modifier_name}' on '{object_name}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to modify modifier"))

    except Exception as e:
        return error_response(f"Failed to modify modifier '{modifier_name}' on '{object_name}'", e)


def apply_modifier(object_name: str, modifier_name: str) -> Dict[str, Any]:
    """Apply a modifier on an object."""
    try:
        conn = ensure_connected()
        response = conn.send_command("apply_modifier", {
            "object_name": object_name,
            "modifier_name": modifier_name
        })

        if response["status"] == "success":
            return success_response(f"Applied modifier '{modifier_name}' on '{object_name}'")
        return error_response(response.get("message", "Failed to apply modifier"))

    except Exception as e:
        return error_response(f"Failed to apply modifier '{modifier_name}' on '{object_name}'", e)


def remove_modifier(object_name: str, modifier_name: str) -> Dict[str, Any]:
    """Remove a modifier from an object."""
    try:
        conn = ensure_connected()
        response = conn.send_command("remove_modifier", {
            "object_name": object_name,
            "modifier_name": modifier_name
        })

        if response["status"] == "success":
            return success_response(f"Removed modifier '{modifier_name}' from '{object_name}'")
        return error_response(response.get("message", "Failed to remove modifier"))

    except Exception as e:
        return error_response(f"Failed to remove modifier '{modifier_name}' from '{object_name}'", e)


def boolean_operation(object_a: str, object_b: str, operation: str = "DIFFERENCE") -> Dict[str, Any]:
    """
    Apply a Boolean modifier helper on object_a using object_b.
    operation: DIFFERENCE, UNION, INTERSECT
    """
    try:
        op = operation.upper()
        if op not in {"DIFFERENCE", "UNION", "INTERSECT"}:
            return error_response("operation must be one of DIFFERENCE, UNION, INTERSECT")

        conn = ensure_connected()
        response = conn.send_command("boolean_operation", {
            "object_a": object_a,
            "object_b": object_b,
            "operation": op
        })

        if response["status"] == "success":
            return success_response(f"Boolean {op} applied between '{object_a}' and '{object_b}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to apply boolean operation"))

    except Exception as e:
        return error_response("Failed to apply boolean operation", e)


def add_bevel(object_name: str, width: float = 0.02, segments: int = 2, limit_method: str = "ANGLE", angle_limit: float = 0.785) -> Dict[str, Any]:
    """Convenience bevel helper."""
    return add_modifier(
        object_name,
        modifier_type="BEVEL",
        width=width,
        segments=segments,
        limit_method=limit_method,
        angle_limit=angle_limit
    )


def add_mirror(object_name: str, axes: tuple = (True, False, False), merge: bool = True, merge_threshold: float = 0.001) -> Dict[str, Any]:
    """Convenience mirror helper."""
    return add_modifier(
        object_name,
        modifier_type="MIRROR",
        use_axis=axes,
        use_mirror_merge=merge,
        merge_threshold=merge_threshold
    )


def add_array(object_name: str, count: int = 3, offset: tuple = (1.0, 0.0, 0.0), relative: bool = True) -> Dict[str, Any]:
    """Convenience array helper."""
    return add_modifier(
        object_name,
        modifier_type="ARRAY",
        count=count,
        use_relative_offset=relative,
        relative_offset_displace=offset,
        use_constant_offset=not relative,
        constant_offset_displace=offset
    )


def add_subsurf(object_name: str, levels: int = 2, render_levels: Optional[int] = None) -> Dict[str, Any]:
    """Add a subdivision surface modifier."""
    params = {"levels": levels}
    if render_levels is not None:
        params["render_levels"] = render_levels
    return add_modifier(object_name, modifier_type="SUBSURF", **params)


def add_boolean(object_name: str, target: str, operation: str = "DIFFERENCE") -> Dict[str, Any]:
    """Add a boolean modifier to object_name using target."""
    op = operation.upper()
    if op not in {"UNION", "DIFFERENCE", "INTERSECT"}:
        return error_response("operation must be UNION/DIFFERENCE/INTERSECT")
    mod_name = f"Boolean_{target}"
    return add_modifier(object_name, modifier_type="BOOLEAN", object=target, operation=op, name=mod_name)


def add_solidify(object_name: str, thickness: float = 0.05) -> Dict[str, Any]:
    return add_modifier(object_name, modifier_type="SOLIDIFY", thickness=thickness)


def add_decimate(object_name: str, ratio: float = 0.5) -> Dict[str, Any]:
    return add_modifier(object_name, modifier_type="DECIMATE", ratio=ratio)


def add_simple_deform(object_name: str, mode: str = "BEND", angle: float = 0.5, factor: float = 0.0, axis: str = "Z") -> Dict[str, Any]:
    # SIMPLE_DEFORM params: deform_method, angle, factor, axis?
    return add_modifier(object_name, modifier_type="SIMPLE_DEFORM", deform_method=mode, angle=angle, factor=factor, deform_axis=f"AXIS_{axis.upper()}")


def add_curve_deform(object_name: str, curve_name: str) -> Dict[str, Any]:
    return add_modifier(object_name, modifier_type="CURVE", object=curve_name)


def add_remesh(object_name: str, voxel_size: float = 0.1, mode: str = "VOXEL") -> Dict[str, Any]:
    return add_modifier(object_name, modifier_type="REMESH", voxel_size=voxel_size, mode=mode)
