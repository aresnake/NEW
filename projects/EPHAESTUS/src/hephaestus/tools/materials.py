"""
Hephaestus Materials Tools
Tools for material creation and manipulation
"""

from typing import Dict, Any, Optional, Tuple
from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import success_response, error_response, validate_color
import json
import os
import logging

logger = logging.getLogger(__name__)


def get_preset_path(preset_name: str) -> Optional[str]:
    """Get path to material preset file"""
    # Get the directory where this file is located
    current_dir = os.path.dirname(os.path.dirname(__file__))
    preset_path = os.path.join(current_dir, "presets", "materials", f"{preset_name}.json")

    if os.path.exists(preset_path):
        return preset_path
    return None


def load_preset(preset_name: str) -> Optional[Dict[str, Any]]:
    """Load material preset from JSON file"""
    preset_path = get_preset_path(preset_name)
    if not preset_path:
        return None

    try:
        with open(preset_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load preset '{preset_name}': {e}")
        return None


def create_material(
    name: str,
    base_color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    roughness: float = 0.5,
    metallic: float = 0.0
) -> Dict[str, Any]:
    """
    Create a Principled BSDF material

    Args:
        name: Material name
        base_color: Base color as (R, G, B, A) with values 0.0-1.0
        roughness: Roughness value 0.0-1.0
        metallic: Metallic value 0.0-1.0

    Returns:
        Success/error dict
    """
    try:
        # Validate color
        base_color = validate_color(base_color)

        # Validate roughness and metallic
        if not (0.0 <= roughness <= 1.0):
            return error_response("Roughness must be between 0.0 and 1.0")
        if not (0.0 <= metallic <= 1.0):
            return error_response("Metallic must be between 0.0 and 1.0")

        conn = ensure_connected()
        response = conn.send_command("create_material", {
            "name": name,
            "base_color": base_color,
            "roughness": roughness,
            "metallic": metallic
        })

        if response["status"] == "success":
            return success_response(f"Material '{name}' created", data=response.get("result"))
        else:
            return error_response(response.get("message", f"Failed to create material '{name}'"))

    except Exception as e:
        return error_response(f"Failed to create material '{name}'", e)


def assign_material(object_name: str, material_name: str, slot: int = 0) -> Dict[str, Any]:
    """
    Assign a material to an object

    Args:
        object_name: Name of the object
        material_name: Name of the material
        slot: Material slot index (default: 0)

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("assign_material", {
            "object_name": object_name,
            "material_name": material_name,
            "slot": slot
        })

        if response["status"] == "success":
            return success_response(
                f"Assigned material '{material_name}' to '{object_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to assign material"))

    except Exception as e:
        return error_response(f"Failed to assign material", e)


def create_material_preset(preset_name: str, custom_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a material from a preset

    Args:
        preset_name: Name of the preset (concrete, metal_dark, metal_chrome, glass, plastic, wood, emission)
        custom_name: Optional custom name for the material (defaults to preset name)

    Returns:
        Success/error dict
    """
    try:
        # Load preset
        preset = load_preset(preset_name)
        if not preset:
            available = ["concrete", "metal_dark", "metal_chrome", "glass", "plastic", "wood", "emission"]
            return error_response(f"Preset '{preset_name}' not found. Available: {', '.join(available)}")

        # Use custom name or preset name
        material_name = custom_name or preset.get("name", preset_name)

        conn = ensure_connected()
        response = conn.send_command("create_material_preset", {
            "preset_name": preset_name,
            "custom_name": material_name,
            "preset_data": preset
        })

        if response["status"] == "success":
            return success_response(
                f"Material '{material_name}' created from preset '{preset_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to create material from preset"))

    except Exception as e:
        return error_response(f"Failed to create material from preset '{preset_name}'", e)


def set_material_property(material_name: str, property_name: str, value: Any) -> Dict[str, Any]:
    """
    Set a property of a material

    Args:
        material_name: Name of the material
        property_name: Property name (base_color, roughness, metallic, emission_strength, etc.)
        value: Property value

    Returns:
        Success/error dict
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("set_material_property", {
            "material_name": material_name,
            "property_name": property_name,
            "value": value
        })

        if response["status"] == "success":
            return success_response(
                f"Set '{property_name}' on material '{material_name}'",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to set material property"))

    except Exception as e:
        return error_response(f"Failed to set material property", e)


def get_material_list() -> Dict[str, Any]:
    """
    Get list of all materials in the scene

    Returns:
        Dict with list of material names
    """
    try:
        conn = ensure_connected()
        response = conn.send_command("get_material_list")

        if response["status"] == "success":
            materials = response.get("result", {}).get("materials", [])
            return success_response(
                f"Found {len(materials)} materials",
                data=response.get("result")
            )
        else:
            return error_response(response.get("message", "Failed to get material list"))

    except Exception as e:
        return error_response("Failed to get material list", e)
