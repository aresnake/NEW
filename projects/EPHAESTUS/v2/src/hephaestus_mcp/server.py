from __future__ import annotations

from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .bridge.client import BridgeClient
from .shared.config import load_config
from .shared.errors import (
    BridgeUnavailable,
    SchemaValidationError,
    ToolExecutionError,
    UnknownTool,
)
from .shared.logging import configure_logging, get_logger
from .tools.registry import compact_arguments, list_definitions, validate_arguments

app = Server("hephaestus_mcp")
logger = get_logger(__name__)
bridge = BridgeClient()


def _tool_definitions() -> list[Tool]:
    return [
        Tool(name=tool.name, description=tool.description, inputSchema=tool.input_schema)
        for tool in list_definitions()
    ]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return _tool_definitions()


@app.call_tool()
async def ping() -> list[TextContent]:
    validate_arguments("ping", {})
    return [TextContent(type="text", text="pong")]


async def _call_bridge(tool_name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        payload = bridge.call(tool_name, arguments)
    except BridgeUnavailable as exc:
        raise ToolExecutionError(str(exc)) from exc

    return [TextContent(type="text", text=str(payload))]


async def _execute_tool(tool_name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        validated_args = validate_arguments(tool_name, arguments)
    except (SchemaValidationError, UnknownTool) as exc:
        raise ToolExecutionError(str(exc)) from exc

    return await _call_bridge(tool_name, validated_args)


@app.call_tool()
async def scene_get_info() -> list[TextContent]:
    return await _execute_tool("scene.get_info", {})


@app.call_tool()
async def scene_clear() -> list[TextContent]:
    return await _execute_tool("scene.clear", {})


@app.call_tool()
async def object_create_primitive(
    primitive_type: str,
    name: str | None = None,
    location: list[float] | None = None,
) -> list[TextContent]:
    arguments = compact_arguments(
        primitive_type=primitive_type,
        name=name,
        location=location,
    )
    return await _execute_tool("object.create_primitive", arguments)


@app.call_tool()
async def object_delete(name: str) -> list[TextContent]:
    return await _execute_tool("object.delete", {"name": name})


@app.call_tool()
async def object_transform(
    name: str,
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
) -> list[TextContent]:
    arguments = compact_arguments(
        name=name,
        location=location,
        rotation=rotation,
        scale=scale,
    )
    return await _execute_tool("object.transform", arguments)


@app.call_tool()
async def material_create(
    name: str,
    base_color: list[float] | None = None,
) -> list[TextContent]:
    arguments = compact_arguments(
        name=name,
        base_color=base_color,
    )
    return await _execute_tool("material.create", arguments)


@app.call_tool()
async def material_assign(object_name: str, material_name: str) -> list[TextContent]:
    return await _execute_tool(
        "material.assign",
        {"object_name": object_name, "material_name": material_name},
    )


@app.call_tool()
async def camera_create(name: str, location: list[float]) -> list[TextContent]:
    return await _execute_tool("camera.create", {"name": name, "location": location})


@app.call_tool()
async def render_preview(
    camera_name: str | None = None,
    filepath: str | None = None,
    res_x: int | None = None,
    res_y: int | None = None,
) -> list[TextContent]:
    arguments = compact_arguments(
        camera_name=camera_name,
        filepath=filepath,
        res_x=res_x,
        res_y=res_y,
    )
    return await _execute_tool("render.preview", arguments)


async def run_server() -> None:
    config = load_config()
    configure_logging(config.logging)
    logger.info("Starting Hephaestus MCP v2")

    global bridge
    bridge = BridgeClient(config.bridge)
    try:
        bridge.connect()
    except BridgeUnavailable as exc:
        logger.error("Bridge unavailable: %s", exc)
        raise

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    import asyncio

    try:
        asyncio.run(run_server())
    except BridgeUnavailable as exc:
        logger.error("Bridge unavailable: %s", exc)
        raise SystemExit(1) from exc
    except ToolExecutionError as exc:
        logger.error("Tool execution error: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
