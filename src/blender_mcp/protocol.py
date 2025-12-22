import json
from typing import Any, Dict, Optional

PROTOCOL_VERSION = "2024-11-05"


class ProtocolError(Exception):
    """Raised when a message cannot be parsed or is invalid."""


def parse_message(line: str) -> Dict[str, Any]:
    """Parse a single NDJSON line into a JSON-RPC message."""
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Invalid JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Message must be a JSON object")
    if message.get("jsonrpc") != "2.0":
        raise ProtocolError("Invalid or missing jsonrpc version")
    return message


def serialize_message(message: Dict[str, Any]) -> str:
    """Serialize a JSON-RPC message as a compact JSON line."""
    return json.dumps(message, separators=(",", ":")) + "\n"


def make_result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(
    request_id: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}
