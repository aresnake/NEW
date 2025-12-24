from . import core, materials_scene, mesh_cleanup, mesh_edit, misc, modifiers, primitives_curves, transforms, uv


def register_all(registry, bridge_request, make_tool_result, ToolError) -> None:  # noqa: ANN001, N803
    # Order kept stable to mirror original registration flow.
    core.register(registry, bridge_request, make_tool_result, ToolError)
    primitives_curves.register(registry, bridge_request, make_tool_result, ToolError)
    transforms.register(registry, bridge_request, make_tool_result, ToolError)
    modifiers.register(registry, bridge_request, make_tool_result, ToolError)
    mesh_cleanup.register(registry, bridge_request, make_tool_result, ToolError)
    uv.register(registry, bridge_request, make_tool_result, ToolError)
    materials_scene.register(registry, bridge_request, make_tool_result, ToolError)
    misc.register(registry, bridge_request, make_tool_result, ToolError)
    mesh_edit.register(registry, bridge_request, make_tool_result, ToolError)
