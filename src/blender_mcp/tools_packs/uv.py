from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-uv-unwrap",
        "Mark seams (optional) and unwrap UVs for a mesh",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "method": {"type": "string"},
                "margin": {"type": "number"},
                "mark_seams": {"type": "boolean"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_uv_unwrap,  # noqa: SLF001
    )
