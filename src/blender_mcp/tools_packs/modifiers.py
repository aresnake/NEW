from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-add-modifier",
        "Add a modifier to an object",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string"},
                "settings": {"type": "object"},
            },
            "required": ["name", "type"],
            "additionalProperties": False,
        },
        registry._tool_add_modifier,  # noqa: SLF001
    )
    reg(
        "blender-apply-modifier",
        "Apply a modifier on an object",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier": {"type": "string"},
            },
            "required": ["name", "modifier"],
            "additionalProperties": False,
        },
        registry._tool_apply_modifier,  # noqa: SLF001
    )
    reg(
        "blender-list-modifiers",
        "List modifiers on an object",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_list_modifiers,  # noqa: SLF001
    )
    reg(
        "blender-boolean",
        "Add a boolean modifier",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "cutter": {"type": "string"},
                "operation": {"type": "string"},
            },
            "required": ["name", "cutter"],
            "additionalProperties": False,
        },
        registry._tool_boolean,  # noqa: SLF001
    )
