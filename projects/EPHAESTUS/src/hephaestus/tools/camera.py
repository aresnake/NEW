"""
Hephaestus Camera Tools
Camera creation and common helpers
"""

from typing import Dict, Any, Optional, Tuple, Union
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response, validate_vector3
import logging

logger = logging.getLogger(__name__)


def create_camera(name: str, location: Tuple[float, float, float], rotation: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
    """Create a camera at the given location/rotation."""
    try:
        location = validate_vector3(location, "location")
        payload = {"name": name, "location": location}
        if rotation is not None:
            payload["rotation"] = validate_vector3(rotation, "rotation")

        conn = ensure_connected()
        response = conn.send_command("create_camera", payload)

        if response["status"] == "success":
            return success_response(f"Camera '{name}' created", data=response.get("result"))
        return error_response(response.get("message", "Failed to create camera"))
    except Exception as e:
        return error_response(f"Failed to create camera '{name}'", e)


def set_active_camera(camera_name: str) -> Dict[str, Any]:
    """Set active scene camera."""
    try:
        conn = ensure_connected()
        response = conn.send_command("set_active_camera", {"camera_name": camera_name})
        if response["status"] == "success":
            return success_response(f"Active camera set to '{camera_name}'")
        return error_response(response.get("message", "Failed to set active camera"))
    except Exception as e:
        return error_response(f"Failed to set active camera '{camera_name}'", e)


def point_camera_at(camera_name: str, target: Union[str, Tuple[float, float, float]]) -> Dict[str, Any]:
    """Point a camera at an object or world-space coordinate."""
    try:
        payload = {"camera_name": camera_name}
        if isinstance(target, (tuple, list)):
            payload["target_location"] = validate_vector3(target, "target")
        else:
            payload["target_object"] = target

        conn = ensure_connected()
        response = conn.send_command("point_camera_at", payload)
        if response["status"] == "success":
            return success_response(f"Camera '{camera_name}' pointed at target", data=response.get("result"))
        return error_response(response.get("message", "Failed to point camera"))
    except Exception as e:
        return error_response(f"Failed to point camera '{camera_name}'", e)


def set_camera_orthographic(camera_name: str, scale: float = 10.0) -> Dict[str, Any]:
    """Switch a camera to orthographic mode."""
    try:
        conn = ensure_connected()
        response = conn.send_command("set_camera_orthographic", {"camera_name": camera_name, "scale": scale})
        if response["status"] == "success":
            return success_response(f"Camera '{camera_name}' set to orthographic", data=response.get("result"))
        return error_response(response.get("message", "Failed to set orthographic"))
    except Exception as e:
        return error_response(f"Failed to set orthographic camera '{camera_name}'", e)


def set_camera_preset(camera_name: str, preset: str) -> Dict[str, Any]:
    """Apply a simple camera preset (isometric, top, front, product)."""
    try:
        conn = ensure_connected()
        response = conn.send_command("set_camera_preset", {"camera_name": camera_name, "preset": preset})
        if response["status"] == "success":
            return success_response(f"Applied preset '{preset}' to '{camera_name}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to apply camera preset"))
    except Exception as e:
        return error_response(f"Failed to apply preset '{preset}'", e)


def create_camera_rig(rig_type: str = "turntable", target: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a simple camera rig.
    rig_type: turntable currently supported.
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("create_camera_rig", {
            "rig_type": rig_type,
            "target": target
        })
        if response["status"] == "success":
            return success_response(f"Created camera rig '{rig_type}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to create camera rig"))
    except Exception as e:
        return error_response("Failed to create camera rig", e)
