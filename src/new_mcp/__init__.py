"""Lightweight MCP stdio server package for Claude Desktop."""

from .protocol import PROTOCOL_VERSION, make_error, make_result, parse_message, serialize_message
from .server import StdioServer
from .tools import ToolRegistry, ToolError

__all__ = [
    "PROTOCOL_VERSION",
    "StdioServer",
    "ToolRegistry",
    "ToolError",
    "make_error",
    "make_result",
    "parse_message",
    "serialize_message",
]
