"""
Hephaestus Object Tools
Tools for object creation, manipulation, and transformation
"""

from typing import Dict, Any, Optional, List, Tuple, Union
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import (
    success_response, error_response,
    validate_vector3, format_object_name
)
import logging
from collections.abc import Iterable
from typing import Literal

logger = logging.getLogger(__name__)


def create_primitive(
    primitive_type: str,
    name: Optional[str] = None,
    location: Tuple[float, float, float] = (0, 0, 0),
    scale: Tuple[float, float, float] = (1, 1, 1),
    rotation: Tuple[float, float, float] = (0, 0, 0)
) -> Dict[str, Any]:
    """
    Create a primitive object

    Args:
        primitive_type: Type of primitive (cube, sphere, cylinder, cone, plane, torus, monkey)
        name: Optional custom name for the object
        location: Location (X, Y, Z)
        scale: Scale (X, Y, Z)
        rotation: Rotation in radians (X, Y, Z)

    Returns:
        Success/error dict with created object info
    """
    try:
        # Validate inputs
        location = validate_vector3(location, "location")
        scale = validate_vector3(scale, "scale")
        rotation = validate_vector3(rotation, "rotation")

        valid_types = ["cube", "sphere", "cylinder", "cone", "plane", "torus", "monkey", "uv_sphere", "ico_sphere"]
        if primitive_type.lower() not in valid_types:
            return error_response(f"Invalid primitive type. Must be one of: {', '.join(valid_types)}")

        # Format name
        if name:
            name = format_object_name(name)

        conn = ensure_connected()
        response = conn.send_command("create_primitive", {
            "type": primitive_type.lower(),
            "name": name,
            "location": location,
            "scale": scale,
            "rotation": rotation
        })

        if response["status"] == "success":
            obj_name = response.get("result", {}).get("name", name or primitive_type)
            return success_response(
                f"Created {primitive_type} '{obj_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", f"Failed to create {primitive_type}"))

    except Exception as e:
        return error_response(f"Failed to create {primitive_type}", e)


def delete_object(object_name: str) -> Dict[str, Any]:
    """
    Delete an object from the scene

    Args:
        object_name: Name of the object to delete

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("delete_object", {"object_name": object_name})

        if response["status"] == "success":
            return success_response(f"Deleted object '{object_name}'")
        else:
            return error_response(response.get("message", f"Failed to delete '{object_name}'"))

    except Exception as e:
        return error_response(f"Failed to delete object '{object_name}'", e)


def delete_objects(object_names: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Delete multiple objects from the scene

    Args:
        object_names: Single name or list of names to delete

    Returns:
        Success/error dict with deleted/missing counts
    """
    try:
        # Normalize to list
        if isinstance(object_names, str):
            names = [object_names]
        elif isinstance(object_names, Iterable):
            names = list(object_names)
        else:
            return error_response("object_names must be a string or list of strings")

        conn = ensure_connected()
        response = conn.send_command("delete_objects", {"object_names": names})

        if response["status"] == "success":
            result = response.get("result", {})
            deleted = result.get("deleted", [])
            missing = result.get("missing", [])
            msg = f"Deleted {len(deleted)} object(s)"
            if missing:
                msg += f"; missing: {', '.join(missing)}"
            return success_response(msg, data=result)
        else:
            return error_response(response.get("message", "Failed to delete objects"))
    except Exception as e:
        return error_response("Failed to delete objects", e)


def set_parent(
    child_names: Union[str, List[str]],
    parent_name: str,
    keep_transform: bool = True
) -> Dict[str, Any]:
    """
    Parent one or multiple objects to a parent object.

    Args:
        child_names: Object name or list of object names to parent
        parent_name: Name of parent object
        keep_transform: Keep world transform when parenting (default True)

    Returns:
        Success/error dict
    """
    try:
        if isinstance(child_names, str):
            children = [child_names]
        elif isinstance(child_names, Iterable):
            children = list(child_names)
        else:
            return error_response("child_names must be a string or list of strings")

        params = {
            "child_names": children,
            "parent_name": parent_name,
            "keep_transform": bool(keep_transform)
        }
        conn = ensure_connected()
        response = conn.send_command("set_parent", params)

        if response["status"] == "success":
            return success_response(
                response.get("message", "Parenting completed"),
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to parent objects"))
    except Exception as e:
        return error_response("Failed to parent objects", e)


def apply_transforms(
    object_names: Union[str, List[str]],
    location: bool = True,
    rotation: bool = True,
    scale: bool = True
) -> Dict[str, Any]:
    """
    Apply transforms to objects (location/rotation/scale baked into geometry).

    Args:
        object_names: Single or list of object names
        location: Apply location
        rotation: Apply rotation
        scale: Apply scale
    """
    try:
        if isinstance(object_names, str):
            names = [object_names]
        elif isinstance(object_names, Iterable):
            names = list(object_names)
        else:
            return error_response("object_names must be a string or list of strings")

        conn = ensure_connected()
        response = conn.send_command("apply_transforms", {
            "object_names": names,
            "location": bool(location),
            "rotation": bool(rotation),
            "scale": bool(scale)
        })
        if response["status"] == "success":
            return success_response(response.get("message", "Transforms applied"), data=response.get("result"))
        else:
            return error_response(response.get("message", "Failed to apply transforms"))
    except Exception as e:
        return error_response("Failed to apply transforms", e)


def join_objects(object_names: Union[str, List[str]], new_name: str = "Joined") -> Dict[str, Any]:
    """
    Join multiple mesh objects into one.

    Args:
        object_names: Objects to join
        new_name: Name of resulting object
    """
    try:
        if isinstance(object_names, str):
            names = [object_names]
        elif isinstance(object_names, Iterable):
            names = list(object_names)
        else:
            return error_response("object_names must be a string or list of strings")

        conn = ensure_connected()
        response = conn.send_command("join_objects", {"object_names": names, "new_name": new_name})
        if response["status"] == "success":
            return success_response(response.get("message", "Joined objects"), data=response.get("result"))
        else:
            return error_response(response.get("message", "Failed to join objects"))
    except Exception as e:
        return error_response("Failed to join objects", e)


def set_origin(
    object_name: str,
    mode: Literal["geometry", "center_of_mass", "cursor"] = "geometry",
    target: Optional[Tuple[float, float, float]] = None
) -> Dict[str, Any]:
    """
    Set object origin without moving geometry in world space.

    Args:
        object_name: Object to edit
        mode: geometry|center_of_mass|cursor
        target: Optional world target (used for cursor mode); default (0,0,0)
    """
    try:
        params = {"object_name": object_name, "mode": mode}
        if target is not None:
            params["target"] = validate_vector3(target, "target")
        conn = ensure_connected()
        response = conn.send_command("set_origin", params)
        if response["status"] == "success":
            return success_response(response.get("message", "Origin set"), data=response.get("result"))
        else:
            return error_response(response.get("message", "Failed to set origin"))
    except Exception as e:
        return error_response("Failed to set origin", e)


def instance_collection(
    collection_name: str,
    name: Optional[str] = None,
    location: Tuple[float, float, float] = (0, 0, 0),
    rotation: Tuple[float, float, float] = (0, 0, 0),
    scale: Tuple[float, float, float] = (1, 1, 1),
) -> Dict[str, Any]:
    """
    Instance a collection as an empty.
    """
    try:
        params = {
            "collection_name": collection_name,
            "name": name or f"Instance_{collection_name}",
            "location": validate_vector3(location, "location"),
            "rotation": validate_vector3(rotation, "rotation"),
            "scale": validate_vector3(scale, "scale"),
        }
        conn = ensure_connected()
        response = conn.send_command("instance_collection", params)
        if response["status"] == "success":
            return success_response(response.get("message", "Collection instanced"), data=response.get("result"))
        else:
            return error_response(response.get("message", "Failed to instance collection"))
    except Exception as e:
        return error_response("Failed to instance collection", e)

def transform_object(
    object_name: str,
    location: Optional[Tuple[float, float, float]] = None,
    rotation: Optional[Tuple[float, float, float]] = None,
    scale: Optional[Tuple[float, float, float]] = None
) -> Dict[str, Any]:
    """
    Transform an object (location, rotation, scale)

    Args:
        object_name: Name of the object
        location: Optional new location (X, Y, Z)
        rotation: Optional new rotation in radians (X, Y, Z)
        scale: Optional new scale (X, Y, Z)

    Returns:
        Success/error dict
    """
    try:
        params = {"object_name": object_name}

        if location is not None:
            params["location"] = validate_vector3(location, "location")

        if rotation is not None:
            params["rotation"] = validate_vector3(rotation, "rotation")

        if scale is not None:
            params["scale"] = validate_vector3(scale, "scale")

        if len(params) == 1:  # Only object_name provided
            return error_response("No transformation parameters provided")

        conn = ensure_connected()
        response = conn.send_command("transform_object", params)

        if response["status"] == "success":
            return success_response(f"Transformed object '{object_name}'", data=response.get("result"))
        else:
            return error_response(response.get("message", f"Failed to transform '{object_name}'"))

    except Exception as e:
        return error_response(f"Failed to transform object '{object_name}'", e)


def duplicate_object(
    object_name: str,
    new_name: Optional[str] = None,
    location_offset: Optional[Tuple[float, float, float]] = None
) -> Dict[str, Any]:
    """
    Duplicate an object

    Args:
        object_name: Name of the object to duplicate
        new_name: Optional name for the duplicate
        location_offset: Optional offset from original location

    Returns:
        Success/error dict with duplicate object info
    """
    try:
        params = {"object_name": object_name}

        if new_name:
            params["new_name"] = format_object_name(new_name)

        if location_offset is not None:
            params["location_offset"] = validate_vector3(location_offset, "location_offset")

        conn = ensure_connected()
        response = conn.send_command("duplicate_object", params)

        if response["status"] == "success":
            duplicate_name = response.get("result", {}).get("name", new_name)
            return success_response(
                f"Duplicated '{object_name}' as '{duplicate_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", f"Failed to duplicate '{object_name}'"))

    except Exception as e:
        return error_response(f"Failed to duplicate object '{object_name}'", e)


def parent_object(
    child_name: str,
    parent_name: str,
    keep_transform: bool = True
) -> Dict[str, Any]:
    """
    Parent an object to another object

    Args:
        child_name: Name of the child object
        parent_name: Name of the parent object
        keep_transform: If True, keep world transform (default: True)

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("parent_object", {
            "child_name": child_name,
            "parent_name": parent_name,
            "keep_transform": keep_transform
        })

        if response["status"] == "success":
            return success_response(f"Parented '{child_name}' to '{parent_name}'")
        else:
            return error_response(response.get("message", f"Failed to parent objects"))

    except Exception as e:
        return error_response(f"Failed to parent '{child_name}' to '{parent_name}'", e)


def array_objects(
    object_name: str,
    count: int,
    offset: Tuple[float, float, float],
    axis: str = "X"
) -> Dict[str, Any]:
    """
    Create an array of duplicated objects

    Args:
        object_name: Name of the object to array
        count: Number of duplicates (total objects = count + 1)
        offset: Offset between each duplicate (X, Y, Z)
        axis: Primary axis for array ("X", "Y", or "Z")

    Returns:
        Success/error dict with created object names
    """
    try:
        if count < 1:
            return error_response("Count must be at least 1")

        offset = validate_vector3(offset, "offset")

        if axis.upper() not in ["X", "Y", "Z"]:
            return error_response("Axis must be X, Y, or Z")

        conn = ensure_connected()
        response = conn.send_command("array_objects", {
            "object_name": object_name,
            "count": count,
            "offset": offset,
            "axis": axis.upper()
        })

        if response["status"] == "success":
            created = response.get("result", {}).get("created", [])
            return success_response(
                f"Created array of {len(created)} objects",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", f"Failed to create array"))

    except Exception as e:
        return error_response(f"Failed to create array", e)


def select_object(object_name: str, deselect_others: bool = True) -> Dict[str, Any]:
    """
    Select an object

    Args:
        object_name: Name of the object to select
        deselect_others: If True, deselect all other objects first

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("select_object", {
            "object_name": object_name,
            "deselect_others": deselect_others
        })

        if response["status"] == "success":
            return success_response(f"Selected object '{object_name}'")
        else:
            return error_response(response.get("message", f"Failed to select '{object_name}'"))

    except Exception as e:
        return error_response(f"Failed to select object '{object_name}'", e)


def rename_object(old_name: str, new_name: str) -> Dict[str, Any]:
    """
    Rename an object

    Args:
        old_name: Current name of the object
        new_name: New name for the object

    Returns:
        Success/error dict
    """
    try:
        new_name = format_object_name(new_name)

        conn = ensure_connected()
        response = conn.send_command("rename_object", {
            "old_name": old_name,
            "new_name": new_name
        })

        if response["status"] == "success":
            return success_response(f"Renamed '{old_name}' to '{new_name}'")
        else:
            return error_response(response.get("message", f"Failed to rename object"))

    except Exception as e:
        return error_response(f"Failed to rename object", e)


def get_selected_objects() -> Dict[str, Any]:
    """
    Get list of currently selected objects

    Returns:
        Dict with list of selected object names
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("get_selected_objects")

        if response["status"] == "success":
            selected = response.get("result", {}).get("selected", [])
            return success_response(
                f"Found {len(selected)} selected objects",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to get selected objects"))

    except Exception as e:
        return error_response("Failed to get selected objects", e)


def create_empty(name: str, location: Tuple[float, float, float] = (0, 0, 0)) -> Dict[str, Any]:
    """Create an empty object."""
    try:
        location = validate_vector3(location, "location")
        conn = ensure_connected()
        response = conn.send_command("create_empty", {"name": name, "location": location})
        if response["status"] == "success":
            return success_response(f"Empty '{name}' created", data=response.get("result"))
        return error_response(response.get("message", f"Failed to create empty '{name}'"))
    except Exception as e:
        return error_response(f"Failed to create empty '{name}'", e)


def create_curve_path(name: str, points: List[Tuple[float, float, float]]) -> Dict[str, Any]:
    """Create a polyline curve with given points."""
    try:
        if len(points) < 2:
            return error_response("At least two points are required for a path")
        norm_points = [validate_vector3(p, "point") for p in points]
        conn = ensure_connected()
        response = conn.send_command("create_curve_path", {"name": name, "points": norm_points})
        if response["status"] == "success":
            return success_response(f"Curve '{name}' created", data=response.get("result"))
        return error_response(response.get("message", f"Failed to create curve '{name}'"))
    except Exception as e:
        return error_response(f"Failed to create curve '{name}'", e)
