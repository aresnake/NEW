from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "blender-delete-all",
        "Delete all objects (safety confirm required)",
        {
            "type": "object",
            "properties": {"confirm": {"type": "string"}},
            "required": ["confirm"],
            "additionalProperties": False,
        },
        registry._tool_delete_all,  # noqa: SLF001
    )
    reg(
        "blender-get-mesh-stats",
        "Get mesh vertex/edge/face/triangle counts",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_get_mesh_stats,  # noqa: SLF001
    )
    reg(
        "blender-merge-by-distance",
        "Merge mesh vertices by distance",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "distance": {"type": "number"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_merge_by_distance,  # noqa: SLF001
    )
    reg(
        "blender-recalc-normals",
        "Recalculate mesh normals (outside or inside)",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "inside": {"type": "boolean"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_recalc_normals,  # noqa: SLF001
    )
    reg(
        "blender-triangulate",
        "Triangulate mesh faces",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "method": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        registry._tool_triangulate,  # noqa: SLF001
    )
