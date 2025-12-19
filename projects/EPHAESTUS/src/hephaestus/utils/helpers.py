"""
Hephaestus Helper Utilities
Common helper functions for tools
"""

from typing import Any, Dict, List, Tuple, Union
import logging

logger = logging.getLogger(__name__)


def validate_color(color: Union[Tuple, List]) -> Tuple[float, float, float, float]:
    """
    Validate and normalize color to RGBA format

    Args:
        color: Color as (R, G, B) or (R, G, B, A)

    Returns:
        RGBA tuple with values 0.0-1.0
    """
    if not isinstance(color, (tuple, list)):
        raise ValueError("Color must be a tuple or list")

    if len(color) == 3:
        r, g, b = color
        a = 1.0
    elif len(color) == 4:
        r, g, b, a = color
    else:
        raise ValueError("Color must have 3 (RGB) or 4 (RGBA) components")

    # Validate range
    for component in [r, g, b, a]:
        if not isinstance(component, (int, float)):
            raise ValueError("Color components must be numbers")
        if component < 0.0 or component > 1.0:
            raise ValueError("Color components must be between 0.0 and 1.0")

    return (float(r), float(g), float(b), float(a))


def validate_vector3(vector: Union[Tuple, List], name: str = "vector") -> Tuple[float, float, float]:
    """
    Validate and normalize 3D vector

    Args:
        vector: Vector as (X, Y, Z)
        name: Name for error messages

    Returns:
        Normalized (X, Y, Z) tuple
    """
    if not isinstance(vector, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")

    if len(vector) != 3:
        raise ValueError(f"{name} must have exactly 3 components (X, Y, Z)")

    x, y, z = vector
    for component in [x, y, z]:
        if not isinstance(component, (int, float)):
            raise ValueError(f"{name} components must be numbers")

    return (float(x), float(y), float(z))


def success_response(message: str, data: Any = None) -> Dict[str, Any]:
    """
    Create a success response dict

    Args:
        message: Success message
        data: Optional data payload

    Returns:
        Response dict
    """
    response = {
        "success": True,
        "message": message
    }
    if data is not None:
        response["data"] = data
    return response


def error_response(message: str, error: Exception = None) -> Dict[str, Any]:
    """
    Create an error response dict

    Args:
        message: Error message
        error: Optional exception

    Returns:
        Response dict
    """
    response = {
        "success": False,
        "message": message
    }
    if error:
        response["error"] = str(error)
        logger.error(f"{message}: {error}")
    else:
        logger.error(message)
    return response


def format_object_name(name: str) -> str:
    """
    Format object name to be Blender-safe

    Args:
        name: Object name

    Returns:
        Formatted name
    """
    # Replace invalid characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()


def degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians"""
    import math
    return degrees * (math.pi / 180.0)


def radians_to_degrees(radians: float) -> float:
    """Convert radians to degrees"""
    import math
    return radians * (180.0 / math.pi)
