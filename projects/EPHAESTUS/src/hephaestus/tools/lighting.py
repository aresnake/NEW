"""
Hephaestus Lighting Tools
Light creation, presets, and world HDRI helpers
"""

from typing import Dict, Any, Optional, Tuple
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response, validate_color, validate_vector3
import json
import os
import logging

logger = logging.getLogger(__name__)


def _preset_path(preset_name: str) -> Optional[str]:
    """Return path to lighting preset JSON."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base_dir, "presets", "lighting", f"{preset_name}.json")
    return path if os.path.exists(path) else None


def _load_preset(preset_name: str) -> Optional[Dict[str, Any]]:
    path = _preset_path(preset_name)
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load lighting preset '{preset_name}': {e}")
        return None


def create_light(light_type: str, name: str, location: Tuple[float, float, float], energy: float = 100.0, color: Optional[Tuple] = None) -> Dict[str, Any]:
    """Create a Blender light."""
    try:
        location = validate_vector3(location, "location")
        payload = {
            "type": light_type.upper(),
            "name": name,
            "location": location,
            "energy": float(energy),
        }
        if color is not None:
            payload["color"] = validate_color(color)

        conn = ensure_connected()
        response = conn.send_command("create_light", payload)
        if response["status"] == "success":
            return success_response(f"Light '{name}' created", data=response.get("result"))
        return error_response(response.get("message", "Failed to create light"))
    except Exception as e:
        return error_response(f"Failed to create light '{name}'", e)


def set_light_property(light_name: str, property_name: str, value: Any) -> Dict[str, Any]:
    """Set a light property (energy, color, size, angle)."""
    try:
        payload = {"light_name": light_name, "property_name": property_name, "value": value}
        if property_name == "color":
            payload["value"] = validate_color(value)

        conn = ensure_connected()
        response = conn.send_command("set_light_property", payload)
        if response["status"] == "success":
            return success_response(f"Set '{property_name}' on light '{light_name}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to set light property"))
    except Exception as e:
        return error_response(f"Failed to set light '{light_name}' property", e)


def apply_lighting_preset(preset_name: str) -> Dict[str, Any]:
    """Apply a multi-light preset from JSON."""
    try:
        preset = _load_preset(preset_name)
        if not preset:
            return error_response(f"Lighting preset '{preset_name}' not found")

        conn = ensure_connected()
        response = conn.send_command("apply_lighting_preset", {
            "preset_name": preset_name,
            "preset_data": preset
        })
        if response["status"] == "success":
            return success_response(f"Applied lighting preset '{preset_name}'", data=response.get("result"))
        return error_response(response.get("message", "Failed to apply lighting preset"))
    except Exception as e:
        return error_response(f"Failed to apply lighting preset '{preset_name}'", e)


def set_world_hdri(hdri_path: str, rotation: float = 0.0, strength: float = 1.0) -> Dict[str, Any]:
    """Set an HDRI environment texture."""
    try:
        conn = ensure_connected()
        response = conn.send_command("set_world_hdri", {
            "hdri_path": hdri_path,
            "rotation": rotation,
            "strength": strength
        })
        if response["status"] == "success":
            return success_response("HDRI applied to world", data=response.get("result"))
        return error_response(response.get("message", "Failed to set HDRI"))
    except Exception as e:
        return error_response("Failed to set world HDRI", e)
