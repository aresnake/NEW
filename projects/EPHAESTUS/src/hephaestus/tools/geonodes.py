"""
Geometry Nodes helpers for Hephaestus.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple, Union

from hephaestus.connection import ensure_connected
from hephaestus.utils.helpers import error_response, success_response


def geonodes_create(object_name: str, tree_name: str) -> Dict[str, Any]:
    """Attach a Geometry Nodes modifier and create a node tree."""
    try:
        payload = {"object_name": object_name, "tree_name": tree_name}
        conn = ensure_connected()
        response = conn.send_command("geonodes_create", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "GeoNodes created"), data=response.get("result"))
        return error_response(response.get("message", "Failed to create GeoNodes"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to create GeoNodes", exc)


def geonodes_add_node(
    tree_name: str,
    node_type: str,
    location: Tuple[int, int],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a node to a Geometry Nodes tree."""
    try:
        payload: Dict[str, Any] = {"tree_name": tree_name, "node_type": node_type, "location": list(location)}
        if name:
            payload["name"] = name
        conn = ensure_connected()
        response = conn.send_command("geonodes_add_node", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Node added"), data=response.get("result"))
        return error_response(response.get("message", "Failed to add node"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to add node", exc)


def geonodes_connect(
    tree_name: str,
    from_node: str,
    from_socket: Union[str, int],
    to_node: str,
    to_socket: Union[str, int],
) -> Dict[str, Any]:
    """Connect two sockets in a Geometry Nodes tree."""
    try:
        payload = {
            "tree_name": tree_name,
            "from_node": from_node,
            "from_socket": from_socket,
            "to_node": to_node,
            "to_socket": to_socket,
        }
        conn = ensure_connected()
        response = conn.send_command("geonodes_connect", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Nodes connected"), data=response.get("result"))
        return error_response(response.get("message", "Failed to connect nodes"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to connect nodes", exc)


def geonodes_set_input(
    tree_name: str,
    node_name: str,
    input_name: Union[str, int],
    value: Any,
) -> Dict[str, Any]:
    """Set a node input default value."""
    try:
        payload = {
            "tree_name": tree_name,
            "node_name": node_name,
            "input_name": input_name,
            "value": value,
        }
        conn = ensure_connected()
        response = conn.send_command("geonodes_set_input", payload)
        if response["status"] == "success":
            return success_response(response.get("message", "Input set"), data=response.get("result"))
        return error_response(response.get("message", "Failed to set input"))
    except Exception as exc:  # noqa: BLE001
        return error_response("Failed to set input", exc)
