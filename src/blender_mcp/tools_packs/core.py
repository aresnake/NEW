from typing import Any


def register(registry, bridge_request: Any, make_tool_result: Any, ToolError: Any) -> None:  # noqa: ANN001, N803
    reg = registry._register  # noqa: SLF001

    reg(
        "health",
        "Health check",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_health,  # noqa: SLF001
    )
    reg(
        "blender-ping",
        "Ping Blender bridge",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_blender_ping,  # noqa: SLF001
    )
    reg(
        "blender-snapshot",
        "Get Blender scene snapshot",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_blender_snapshot,  # noqa: SLF001
    )
    reg(
        "blender-exec",
        "Execute Python code in Blender (code <= 20000 chars)",
        {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        registry._tool_blender_exec,  # noqa: SLF001
    )
