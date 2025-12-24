from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-add-cube",
        "Add a cube at the origin",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_add_cube,  # noqa: SLF001
    )
    reg(
        "blender-move-object",
        "Move an object to (x,y,z)",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"},
            },
            "required": ["name", "x", "y", "z"],
            "additionalProperties": False,
        },
        registry._tool_move_object,  # noqa: SLF001
    )
    reg(
        "blender-delete-object",
        "Delete an object by name",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_delete_object,  # noqa: SLF001
    )
    reg(
        "macro-blockout",
        "Create a blockout cube scaled to (2,1,1) at origin",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_macro_blockout,  # noqa: SLF001
    )
    reg(
        "blender-add-cylinder",
        "Add a low-poly cylinder",
        {
            "type": "object",
            "properties": {
                "vertices": {"type": "integer"},
                "radius": {"type": "number"},
                "depth": {"type": "number"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        registry._tool_add_cylinder,  # noqa: SLF001
    )
    reg(
        "blender-add-sphere",
        "Add a sphere (UV or Ico)",
        {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "segments": {"type": "integer"},
                "rings": {"type": "integer"},
                "subdivisions": {"type": "integer"},
                "radius": {"type": "number"},
                "diameter": {"type": "number"},
                "location": {"type": "array"},
                "name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        registry._tool_add_sphere,  # noqa: SLF001
    )
    reg(
        "blender-add-plane",
        "Add a plane",
        {
            "type": "object",
            "properties": {"size": {"type": "number"}, "location": {"type": "array"}, "name": {"type": "string"}},
            "additionalProperties": False,
        },
        registry._tool_add_plane,  # noqa: SLF001
    )
    reg(
        "blender-add-cone",
        "Add a cone",
        {
            "type": "object",
            "properties": {
                "vertices": {"type": "integer"},
                "radius1": {"type": "number"},
                "radius2": {"type": "number"},
                "depth": {"type": "number"},
                "location": {"type": "array"},
                "name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        registry._tool_add_cone,  # noqa: SLF001
    )
    reg(
        "blender-add-torus",
        "Add a torus",
        {
            "type": "object",
            "properties": {
                "major_radius": {"type": "number"},
                "minor_radius": {"type": "number"},
                "major_segments": {"type": "integer"},
                "minor_segments": {"type": "integer"},
                "location": {"type": "array"},
                "name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        registry._tool_add_torus,  # noqa: SLF001
    )
    reg(
        "blender-duplicate-object",
        "Duplicate an object",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "new_name": {"type": "string"},
                "offset": {"type": "array"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_duplicate_object,  # noqa: SLF001
    )
    reg(
        "blender-list-objects",
        "List all objects in the scene",
        {"type": "object", "properties": {}, "additionalProperties": False},
        registry._tool_list_objects,  # noqa: SLF001
    )
    reg(
        "blender-get-object-info",
        "Get info about an object",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_get_object_info,  # noqa: SLF001
    )
    reg(
        "blender-select-object",
        "Select an object by name",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_select_object,  # noqa: SLF001
    )
    reg(
        "blender-add-camera",
        "Add a camera",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "array"},
                "rotation": {"type": "array"},
            },
            "additionalProperties": False,
        },
        registry._tool_add_camera,  # noqa: SLF001
    )
    reg(
        "blender-add-light",
        "Add a point light",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "location": {"type": "array"}, "energy": {"type": "number"}},
            "additionalProperties": False,
        },
        registry._tool_add_light,  # noqa: SLF001
    )
