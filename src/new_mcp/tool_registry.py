from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Callable

from .contracts import ToolResult

JsonDict = Dict[str, Any]


def tool_system_ping(params: JsonDict) -> ToolResult:
    msg = params.get("message", "ping")
    return ToolResult.success({"reply": "pong", "echo": msg})


def tool_schemas_get(params: JsonDict) -> ToolResult:
    """
    Read a schema file from /schemas and return its content.

    params:
      - name: filename like "execution_model_v1.md"
    """
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        return ToolResult.failure("invalid_input", "name must be a non-empty string")

    # repo root = .../src/new_mcp/tool_registry.py -> parents[2] == repo root
    root = Path(__file__).resolve().parents[2]
    p = root / "schemas" / name

    if not p.exists() or not p.is_file():
        return ToolResult.failure("not_found", f"schema not found: {name}")

    content = p.read_text(encoding="utf-8")
    return ToolResult.success({"name": name, "content": content})


TOOLS: dict[str, Callable[[JsonDict], ToolResult]] = {
    "system.ping": tool_system_ping,
    "schemas.get": tool_schemas_get,
}
