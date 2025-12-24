from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-create-material",
        "Create a new material with optional base color",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "base_color": {"type": "array"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_create_material,  # noqa: SLF001
    )
    reg(
        "blender-export",
        "Export scene to FBX or glTF format",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "format": {"type": "string"},
                "selected_only": {"type": "boolean"},
            },
            "required": ["path", "format"],
            "additionalProperties": False,
        },
        registry._tool_export,  # noqa: SLF001
    )
    reg(
        "blender-rename-object",
        "Rename an object",
        {
            "type": "object",
            "properties": {
                "old_name": {"type": "string"},
                "new_name": {"type": "string"},
            },
            "required": ["old_name", "new_name"],
            "additionalProperties": False,
        },
        registry._tool_rename_object,  # noqa: SLF001
    )
    reg(
        "blender-assign-material",
        "Assign an existing material to an object",
        {
            "type": "object",
            "properties": {
                "object": {"type": "string"},
                "material": {"type": "string"},
                "slot": {"type": "integer"},
                "create_slot": {"type": "boolean"},
            },
            "required": ["object", "material"],
            "additionalProperties": False,
        },
        registry._tool_assign_material,  # noqa: SLF001
    )
    reg(
        "blender-set-shading",
        "Set object shading to flat or smooth",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["name", "mode"],
            "additionalProperties": False,
        },
        registry._tool_set_shading,  # noqa: SLF001
    )
    reg(
        "blender-list-materials",
        "List materials in scene",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_list_materials,  # noqa: SLF001
    )
    reg(
        "blender-list-material-slots",
        "List material slots for an object",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_list_material_slots,  # noqa: SLF001
    )
    reg(
        "blender-assign-image-texture",
        "Assign image texture to material slot",
        {
            "type": "object",
            "properties": {
                "object": {"type": "string"},
                "material": {"type": "string"},
                "image_path": {"type": "string"},
                "target": {"type": "string"},
                "create_material": {"type": "boolean"},
                "create_slot": {"type": "boolean"},
            },
            "required": ["object", "material", "image_path"],
            "additionalProperties": False,
        },
        registry._tool_assign_image_texture,  # noqa: SLF001
    )
    reg(
        "blender-parent",
        "Parent one object to another",
        {
            "type": "object",
            "properties": {
                "child": {"type": "string"},
                "parent": {"type": "string"},
                "keep_transform": {"type": "boolean"},
            },
            "required": ["child", "parent"],
            "additionalProperties": False,
        },
        registry._tool_parent,  # noqa: SLF001
    )
    reg(
        "blender-move-to-collection",
        "Move an object to a collection (links without unlinking others)",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "collection": {"type": "string"}, "create": {"type": "boolean"}},
            "required": ["name", "collection"],
            "additionalProperties": False,
        },
        registry._tool_move_to_collection,  # noqa: SLF001
    )
