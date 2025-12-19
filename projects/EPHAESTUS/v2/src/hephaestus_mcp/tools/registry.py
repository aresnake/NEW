from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft7Validator

from ..shared.errors import SchemaValidationError, UnknownTool
from .defs import TOOL_DEFINITIONS, ToolDefinition

_DEFINITION_INDEX: dict[str, ToolDefinition] = {tool.name: tool for tool in TOOL_DEFINITIONS}
_VALIDATORS: dict[str, Draft7Validator] = {
    tool.name: Draft7Validator(tool.input_schema) for tool in TOOL_DEFINITIONS
}


def list_definitions() -> list[ToolDefinition]:
    return TOOL_DEFINITIONS


def get_definition(name: str) -> ToolDefinition:
    try:
        return _DEFINITION_INDEX[name]
    except KeyError as exc:
        raise UnknownTool(f"Unknown tool '{name}'") from exc


def validate_arguments(tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    validator = _VALIDATORS.get(tool_name)
    if not validator:
        raise UnknownTool(f"Unknown tool '{tool_name}'")

    errors = sorted(validator.iter_errors(arguments), key=lambda e: e.path)
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "<root>"
        raise SchemaValidationError(f"{path}: {first.message}")

    return dict(arguments)


def compact_arguments(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}
