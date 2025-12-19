from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="ping",
        description="Basic health check.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ToolDefinition(
        name="scene.get_info",
        description="Get high-level scene info.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ToolDefinition(
        name="scene.clear",
        description="Delete all objects in the scene.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ToolDefinition(
        name="object.create_primitive",
        description="Create a primitive mesh object.",
        input_schema={
            "type": "object",
            "properties": {
                "primitive_type": {"type": "string"},
                "name": {"type": "string"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            },
            "required": ["primitive_type"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="object.delete",
        description="Delete an object by name.",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="object.transform",
        description="Transform an object.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="material.create",
        description="Create a basic material.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "base_color": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="material.assign",
        description="Assign a material to an object.",
        input_schema={
            "type": "object",
            "properties": {
                "object_name": {"type": "string"},
                "material_name": {"type": "string"},
            },
            "required": ["object_name", "material_name"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="camera.create",
        description="Create a camera.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            },
            "required": ["name", "location"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name="render.preview",
        description="Render a low-quality preview.",
        input_schema={
            "type": "object",
            "properties": {
                "camera_name": {"type": "string"},
                "filepath": {"type": "string"},
                "res_x": {"type": "integer"},
                "res_y": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    ),
]