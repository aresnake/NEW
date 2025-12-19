"""
Import/export helpers for common 3D formats.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import error_response, success_response


def import_model(filepath: str, format: str, scale: float = 1.0) -> Dict[str, Any]:
    """Import a model (FBX/OBJ/GLTF/STL)."""
    try:
        payload = {"filepath": filepath, "format": format, "scale": float(scale)}
        conn = ensure_connected()
        response = conn.send_command("import_model", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Import ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to import model"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to import model", exc)


def export_model(
    filepath: str,
    format: str,
    object_names: Optional[Sequence[str]] = None,
    apply_modifiers: bool = True,
) -> Dict[str, Any]:
    """Export selected or specified objects."""
    try:
        payload: Dict[str, Any] = {
            "filepath": filepath,
            "format": format,
            "apply_modifiers": bool(apply_modifiers),
        }
        if object_names is not None:
            payload["object_names"] = list(object_names)
        conn = ensure_connected()
        response = conn.send_command("export_model", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Export ok"), data=response.get("result"))
        return error_response(response.get("message", "Failed to export model"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to export model", exc)
