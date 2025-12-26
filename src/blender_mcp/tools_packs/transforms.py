from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-scale-object",
        "Scale an object (uniform or vector)",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "scale": {"type": "array"},
                "uniform": {"type": "number"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_scale_object,  # noqa: SLF001
    )
    reg(
        "blender-rotate-object",
        "Rotate an object (degrees)",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "rotation": {"type": "array"}, "space": {"type": "string"}},
            "required": ["name", "rotation"],
            "additionalProperties": False,
        },
        registry._tool_rotate_object,  # noqa: SLF001
    )
    reg(
        "blender-reset-transform",
        "Reset location/rotation/scale of an object",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_reset_transform,  # noqa: SLF001
    )
    reg(
        "blender-apply-transforms",
        "Apply transforms to an object",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "boolean"},
                "rotation": {"type": "boolean"},
                "scale": {"type": "boolean"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_apply_transforms,  # noqa: SLF001
    )
    reg(
        "blender-convert-object",
        "Convert an object to another type",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "target": {"type": "string"}},
            "required": ["name", "target"],
            "additionalProperties": False,
        },
        registry._tool_convert_object,  # noqa: SLF001
    )
    reg(
        "blender-set-origin",
        "Set object origin",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
            "required": ["name", "type"],
            "additionalProperties": False,
        },
        registry._tool_set_origin,  # noqa: SLF001
    )
    reg(
        "blender-set-3d-cursor",
        "Set 3D cursor location/rotation",
        {
            "type": "object",
            "properties": {"location": {"type": "array"}, "rotation": {"type": "array"}},
            "required": ["location"],
            "additionalProperties": False,
        },
        registry._tool_set_3d_cursor,  # noqa: SLF001
    )
    reg(
        "blender-snap",
        "Snap object to grid/cursor/active",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "target": {"type": "string"},
            },
            "required": ["name", "target"],
            "additionalProperties": False,
        },
        registry._tool_snap,  # noqa: SLF001
    )
    reg(
        "blender-align-to-axis",
        "Align transform components to an axis",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "axis": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["name", "axis"],
            "additionalProperties": False,
        },
        registry._tool_align_to_axis,  # noqa: SLF001
    )
    reg(
        "blender-join-objects",
        "Join multiple objects into one",
        {
            "type": "object",
            "properties": {
                "objects": {"type": "array"},
                "name": {"type": "string"},
            },
            "required": ["objects", "name"],
            "additionalProperties": False,
        },
        registry._tool_join_objects,  # noqa: SLF001
    )
