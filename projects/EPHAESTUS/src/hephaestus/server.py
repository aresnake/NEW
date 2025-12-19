"""
Hephaestus MCP Server
Main server implementation using MCP SDK
"""

import logging
import sys
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# Import tools
from hephaestus.tools import (
    camera,
    geonodes,
    io_tools,
    advanced,
    lighting,
    materials,
    mesh_edit,
    modifiers,
    objects,
    scene,
    urban,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hephaestus.log')
    ]
)
logger = logging.getLogger(__name__)

# Create server instance
app = FastMCP("hephaestus")


# Scene tools
@app.tool()
async def get_scene_info() -> list[TextContent]:
    """Get comprehensive scene information from Blender"""
    result = scene.get_scene_info()
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_object_info(object_name: str) -> list[TextContent]:
    """
    Get detailed information about a specific object

    Args:
        object_name: Name of the object to query
    """
    result = scene.get_object_info(object_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_viewport_screenshot(
    max_size: int = 800,
    shading: str | None = None,
    output_dir: str | None = None,
    prefix: str | None = None,
) -> list[TextContent]:
    """
    Capture a screenshot of the current Blender viewport

    Args:
        max_size: Maximum size in pixels for the largest dimension (default: 800)
    """
    result = scene.get_viewport_screenshot(max_size, shading, output_dir, prefix)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def capture_view(
    camera_name: str | None = None,
    preset: str | None = None,
    max_size: int = 800,
    shading: str | None = None,
    output_dir: str | None = None,
    prefix: str | None = None,
) -> list[TextContent]:
    """Capture a view after optionally setting camera + preset."""
    result = scene.capture_view(camera_name, preset, max_size, shading, output_dir, prefix)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def describe_view(
    camera_name: str | None = None,
    preset: str | None = None,
    object_names: list[str] | None = None,
    max_size: int = 800,
    shading: str | None = None,
    output_dir: str | None = None,
    prefix: str | None = None,
) -> list[TextContent]:
    """Capture a view and return screenshot + bbox info for given (or selected) objects."""
    result = scene.describe_view(camera_name, preset, object_names, max_size, shading, output_dir, prefix)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def measure_angle(
    point_a: tuple,
    point_b: tuple,
    point_c: tuple,
) -> list[TextContent]:
    """Measure angle at point B formed by A-B-C (degrees + radians)."""
    result = scene.measure_angle(point_a, point_b, point_c)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def measure_mesh(object_name: str, mode: str = "AREA") -> list[TextContent]:
    """Measure mesh AREA or VOLUME (evaluated)."""
    result = scene.measure_mesh(object_name, mode)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_viewport_shading(shading: str) -> list[TextContent]:
    """Set viewport shading (WIREFRAME, SOLID, MATERIAL, RENDERED)."""
    result = scene.set_viewport_shading(shading)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def scatter_on_surface(
    target_mesh: str,
    source_object: str,
    count: int | None = None,
    seed: int = 0,
    jitter: float = 0.2,
    align_normal: bool = True,
    density: float | None = None,
    max_points: int | None = None,
) -> list[TextContent]:
    """Scatter copies of source_object on target_mesh surface."""
    result = scene.scatter_on_surface(target_mesh, source_object, count, seed, jitter, align_normal, density, max_points)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def render_preview(
    camera_name: str | None = None,
    filepath: str | None = None,
    res_x: int = 800,
    res_y: int = 800,
    engine: str = "BLENDER_EEVEE",
    samples: int = 16,
) -> list[TextContent]:
    """Low-sample render preview to a file."""
    result = scene.render_preview(camera_name, filepath, res_x, res_y, engine, samples)
    return [TextContent(type="text", text=str(result))]
@app.tool()
async def measure_distance(
    object_a: str | None = None,
    object_b: str | None = None,
    point_a: tuple | None = None,
    point_b: tuple | None = None
) -> list[TextContent]:
    """
    Measure distance between two objects (origins) or two points.
    """
    result = scene.measure_distance(object_a, object_b, point_a, point_b)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def bbox_info(object_name: str) -> list[TextContent]:
    """
    Get bounding box info for an object.
    """
    result = scene.bbox_info(object_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_collection(name: str, parent: str = None, color: str = None) -> list[TextContent]:
    """
    Create a new collection in Blender

    Args:
        name: Name of the collection
        parent: Optional parent collection name
        color: Optional color tag (COLOR_01 to COLOR_08)
    """
    result = scene.create_collection(name, parent, color)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def move_to_collection(object_names: str | list[str], collection_name: str) -> list[TextContent]:
    """
    Move objects to a collection

    Args:
        object_names: Single object name or list of object names
        collection_name: Target collection name
    """
    result = scene.move_to_collection(object_names, collection_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_collection_tree() -> list[TextContent]:
    """Get the complete collection hierarchy"""
    result = scene.get_collection_tree()
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def batch_select(pattern: str, object_type: str = None) -> list[TextContent]:
    """
    Select objects by name pattern

    Args:
        pattern: Regex pattern for object names
        object_type: Optional filter by type (MESH, LIGHT, CAMERA, etc.)
    """
    result = scene.batch_select(pattern, object_type)
    return [TextContent(type="text", text=str(result))]


# Object manipulation tools
@app.tool()
async def create_primitive(
    primitive_type: str,
    name: str = None,
    location: tuple = (0, 0, 0),
    scale: tuple = (1, 1, 1),
    rotation: tuple = (0, 0, 0)
) -> list[TextContent]:
    """
    Create a primitive object in Blender

    Args:
        primitive_type: Type (cube, sphere, cylinder, cone, plane, torus, monkey)
        name: Optional custom name
        location: Location (X, Y, Z)
        scale: Scale (X, Y, Z)
        rotation: Rotation in radians (X, Y, Z)
    """
    result = objects.create_primitive(primitive_type, name, location, scale, rotation)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def delete_object(object_name: str) -> list[TextContent]:
    """
    Delete an object from the scene

    Args:
        object_name: Name of the object to delete
    """
    result = objects.delete_object(object_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def delete_objects(object_names: str | list[str]) -> list[TextContent]:
    """
    Delete multiple objects from the scene
    """
    result = objects.delete_objects(object_names)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_parent(child_names: str | list[str], parent_name: str, keep_transform: bool = True) -> list[TextContent]:
    """
    Parent one or multiple objects to a parent object.
    """
    result = objects.set_parent(child_names, parent_name, keep_transform)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def apply_transforms(
    object_names: str | list[str],
    location: bool = True,
    rotation: bool = True,
    scale: bool = True
) -> list[TextContent]:
    """
    Apply transforms to objects (location/rotation/scale baked into geometry).
    """
    result = objects.apply_transforms(object_names, location, rotation, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def join_objects(object_names: str | list[str], new_name: str = "Joined") -> list[TextContent]:
    """
    Join multiple mesh objects into one.
    """
    result = objects.join_objects(object_names, new_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_origin(object_name: str, mode: str = "geometry", target: tuple | None = None) -> list[TextContent]:
    """
    Set object origin without moving geometry in world space.
    """
    result = objects.set_origin(object_name, mode, target)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def instance_collection(
    collection_name: str,
    name: str | None = None,
    location: tuple = (0, 0, 0),
    rotation: tuple = (0, 0, 0),
    scale: tuple = (1, 1, 1),
) -> list[TextContent]:
    """
    Instance a collection as an empty.
    """
    result = objects.instance_collection(collection_name, name, location, rotation, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def transform_object(
    object_name: str,
    location: tuple = None,
    rotation: tuple = None,
    scale: tuple = None
) -> list[TextContent]:
    """
    Transform an object (location, rotation, scale)

    Args:
        object_name: Name of the object
        location: Optional new location (X, Y, Z)
        rotation: Optional new rotation in radians (X, Y, Z)
        scale: Optional new scale (X, Y, Z)
    """
    result = objects.transform_object(object_name, location, rotation, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def duplicate_object(
    object_name: str,
    new_name: str = None,
    location_offset: tuple = None
) -> list[TextContent]:
    """
    Duplicate an object

    Args:
        object_name: Name of the object to duplicate
        new_name: Optional name for the duplicate
        location_offset: Optional offset from original location (X, Y, Z)
    """
    result = objects.duplicate_object(object_name, new_name, location_offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def parent_object(
    child_name: str,
    parent_name: str,
    keep_transform: bool = True
) -> list[TextContent]:
    """
    Parent an object to another object

    Args:
        child_name: Name of the child object
        parent_name: Name of the parent object
        keep_transform: If True, keep world transform (default: True)
    """
    result = objects.parent_object(child_name, parent_name, keep_transform)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def array_objects(
    object_name: str,
    count: int,
    offset: tuple,
    axis: str = "X"
) -> list[TextContent]:
    """
    Create an array of duplicated objects

    Args:
        object_name: Name of the object to array
        count: Number of duplicates (total = count + 1)
        offset: Offset between duplicates (X, Y, Z)
        axis: Primary axis for array (X, Y, or Z)
    """
    result = objects.array_objects(object_name, count, offset, axis)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def select_object(object_name: str, deselect_others: bool = True) -> list[TextContent]:
    """
    Select an object

    Args:
        object_name: Name of the object to select
        deselect_others: If True, deselect all other objects first
    """
    result = objects.select_object(object_name, deselect_others)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def rename_object(old_name: str, new_name: str) -> list[TextContent]:
    """
    Rename an object

    Args:
        old_name: Current name of the object
        new_name: New name for the object
    """
    result = objects.rename_object(old_name, new_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_selected_objects() -> list[TextContent]:
    """Get list of currently selected objects"""
    result = objects.get_selected_objects()
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def create_empty(name: str, location: tuple = (0, 0, 0)) -> list[TextContent]:
    """Create an empty object"""
    result = objects.create_empty(name, location)
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def create_curve_path(name: str, points: list[tuple]) -> list[TextContent]:
    """Create a polyline curve with given points"""
    result = objects.create_curve_path(name, points)
    return [TextContent(type="text", text=str(result))]


# Material tools
@app.tool()
async def create_material(
    name: str,
    base_color: tuple = (0.8, 0.8, 0.8, 1.0),
    roughness: float = 0.5,
    metallic: float = 0.0
) -> list[TextContent]:
    """
    Create a Principled BSDF material

    Args:
        name: Name of the material
        base_color: RGBA tuple values between 0-1
        roughness: Roughness value 0-1
        metallic: Metallic value 0-1
    """
    result = materials.create_material(name, base_color, roughness, metallic)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def assign_material(object_name: str, material_name: str, slot: int = 0) -> list[TextContent]:
    """
    Assign a material to an object

    Args:
        object_name: Name of the object
        material_name: Name of the material
        slot: Material slot index (default 0)
    """
    result = materials.assign_material(object_name, material_name, slot)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_material_preset(preset_name: str, custom_name: str = None) -> list[TextContent]:
    """
    Create a material from a preset

    Args:
        preset_name: Preset key (concrete, metal_dark, etc.)
        custom_name: Optional override name
    """
    result = materials.create_material_preset(preset_name, custom_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_material_property(material_name: str, property_name: str, value: Any) -> list[TextContent]:
    """
    Set a property on a material

    Args:
        material_name: Name of the material to edit
        property_name: Property name (base_color, roughness, etc.)
        value: New value for the property
    """
    result = materials.set_material_property(material_name, property_name, value)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_material_list() -> list[TextContent]:
    """Get list of all materials in the scene"""
    result = materials.get_material_list()
    return [TextContent(type="text", text=str(result))]


# Urban/utility tools
@app.tool()
async def snap_to_grid(step: float = 1.0, object_names: list[str] | None = None) -> list[TextContent]:
    """Snap objects to grid."""
    result = urban.snap_to_grid(step, object_names)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def align_objects(target: str, mode: str = "center", object_names: list[str] | None = None, reference: float = None) -> list[TextContent]:
    """Align objects along an axis."""
    result = urban.align_objects(target, mode, object_names, reference)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def scatter_along_curve(source_object: str, curve_name: str, count: int, jitter: tuple = None) -> list[TextContent]:
    """Scatter duplicates along a curve."""
    result = urban.scatter_along_curve(source_object, curve_name, count, jitter)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_road(width: float, length: float, segments: int = 4, add_sidewalk: bool = True, sidewalk_width: float = 1.5, sidewalk_height: float = 0.15) -> list[TextContent]:
    """Create a road with optional sidewalks."""
    result = urban.create_road(width, length, segments, add_sidewalk, sidewalk_width, sidewalk_height)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def repeat_facade(base_object: str, floors: int = 5, bays: int = 4, floor_height: float = 3.0, bay_width: float = 3.0) -> list[TextContent]:
    """Repeat a base object into a facade grid."""
    result = urban.repeat_facade(base_object, floors, bays, floor_height, bay_width)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def macro_city_block(style: str = "modern", buildings: int = 6, lamps_per_side: int = 6) -> list[TextContent]:
    """High-level macro to create a simple city block."""
    result = urban.macro_city_block(style, buildings, lamps_per_side)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def mech_rig(style: str = "basic", include_chain: bool = True) -> list[TextContent]:
    """Macro helper to create a small mech rig (sprockets + optional chain + arm)."""
    result = urban.mech_rig(style, include_chain)
    return [TextContent(type="text", text=str(result))]


# Modifier tools
@app.tool()
async def add_modifier(object_name: str, modifier_type: str, name: str = None, **params: Any) -> list[TextContent]:
    """Add a modifier to an object."""
    result = modifiers.add_modifier(object_name, modifier_type, name, **params)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def modify_modifier(object_name: str, modifier_name: str, **params: Any) -> list[TextContent]:
    """Modify an existing modifier."""
    result = modifiers.modify_modifier(object_name, modifier_name, **params)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def apply_modifier(object_name: str, modifier_name: str) -> list[TextContent]:
    """Apply a modifier on an object."""
    result = modifiers.apply_modifier(object_name, modifier_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def remove_modifier(object_name: str, modifier_name: str) -> list[TextContent]:
    """Remove a modifier from an object."""
    result = modifiers.remove_modifier(object_name, modifier_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def boolean_operation(object_a: str, object_b: str, operation: str = "DIFFERENCE") -> list[TextContent]:
    """Boolean helper wrapper."""
    result = modifiers.boolean_operation(object_a, object_b, operation)
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def add_bevel(object_name: str, width: float = 0.02, segments: int = 2, limit_method: str = "ANGLE", angle_limit: float = 0.785) -> list[TextContent]:
    """Convenience bevel helper."""
    result = modifiers.add_bevel(object_name, width, segments, limit_method, angle_limit)
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def add_mirror(object_name: str, axes: tuple = (True, False, False), merge: bool = True, merge_threshold: float = 0.001) -> list[TextContent]:
    """Convenience mirror helper."""
    result = modifiers.add_mirror(object_name, axes, merge, merge_threshold)
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def add_array(object_name: str, count: int = 3, offset: tuple = (1.0, 0.0, 0.0), relative: bool = True) -> list[TextContent]:
    """Convenience array helper."""
    result = modifiers.add_array(object_name, count, offset, relative)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_subsurf(object_name: str, levels: int = 2, render_levels: int | None = None) -> list[TextContent]:
    """Add a subdivision surface modifier."""
    result = modifiers.add_subsurf(object_name, levels, render_levels)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_boolean(object_name: str, target: str, operation: str = "DIFFERENCE") -> list[TextContent]:
    """Add a boolean modifier to an object using a target."""
    result = modifiers.add_boolean(object_name, target, operation)
    return [TextContent(type="text", text=str(result))]


# Camera tools
@app.tool()
async def create_camera(name: str, location: tuple, rotation: tuple = None) -> list[TextContent]:
    """Create a camera."""
    result = camera.create_camera(name, location, rotation)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_active_camera(camera_name: str) -> list[TextContent]:
    """Set active camera."""
    result = camera.set_active_camera(camera_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def point_camera_at(camera_name: str, target: Any) -> list[TextContent]:
    """Point camera at object or coordinate."""
    result = camera.point_camera_at(camera_name, target)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_camera_orthographic(camera_name: str, scale: float = 10.0) -> list[TextContent]:
    """Switch camera to orthographic."""
    result = camera.set_camera_orthographic(camera_name, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_camera_preset(camera_name: str, preset: str) -> list[TextContent]:
    """Apply camera preset (isometric, top, front, product)."""
    result = camera.set_camera_preset(camera_name, preset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_camera_rig(rig_type: str = "turntable", target: str = None) -> list[TextContent]:
    """Create simple camera rig."""
    result = camera.create_camera_rig(rig_type, target)
    return [TextContent(type="text", text=str(result))]


# Lighting tools
@app.tool()
async def create_light(light_type: str, name: str, location: tuple, energy: float = 100.0, color: tuple = None) -> list[TextContent]:
    """Create a light in the scene."""
    result = lighting.create_light(light_type, name, location, energy, color)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_light_property(light_name: str, property_name: str, value: Any) -> list[TextContent]:
    """Set property on a light."""
    result = lighting.set_light_property(light_name, property_name, value)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def apply_lighting_preset(preset_name: str) -> list[TextContent]:
    """Apply a multi-light preset."""
    result = lighting.apply_lighting_preset(preset_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_world_hdri(hdri_path: str, rotation: float = 0.0, strength: float = 1.0) -> list[TextContent]:
    """Set world HDRI environment."""
    result = lighting.set_world_hdri(hdri_path, rotation, strength)
    return [TextContent(type="text", text=str(result))]

@app.tool()
async def clear_scene() -> list[TextContent]:
    """Delete all objects in the scene."""
    result = scene.clear_scene()
    return [TextContent(type="text", text=str(result))]


# New Urban Tools
@app.tool()
async def create_building_box(
    width: float = 10.0,
    depth: float = 10.0,
    height: float = 15.0,
    floors: int = 5,
    name: str = "Building"
) -> list[TextContent]:
    """
    Create a parametric building volume with floor divisions.

    Args:
        width: Building width in meters
        depth: Building depth in meters
        height: Total building height in meters
        floors: Number of floors
        name: Name of the building object
    """
    result = urban.create_building_box(width, depth, height, floors, name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_window_grid(
    building_name: str,
    floors: int = 5,
    windows_per_floor: int = 4,
    window_width: float = 1.5,
    window_height: float = 2.0,
    spacing: float = 0.5,
    inset: float = 0.1
) -> list[TextContent]:
    """
    Create a parametric grid of windows on a building.

    Args:
        building_name: Name of the building object to add windows to
        floors: Number of floor levels
        windows_per_floor: Number of windows per floor
        window_width: Width of each window
        window_height: Height of each window
        spacing: Spacing between windows
        inset: Distance windows are inset from building face
    """
    result = urban.create_window_grid(
        building_name, floors, windows_per_floor,
        window_width, window_height, spacing, inset
    )
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def array_along_path(
    source_object: str,
    curve_name: str,
    count: int = 10,
    align_to_curve: bool = True,
    spacing_factor: float = 1.0
) -> list[TextContent]:
    """
    Array objects along a curve path.

    Args:
        source_object: Name of object to duplicate
        curve_name: Name of curve to follow
        count: Number of duplicates
        align_to_curve: Align objects to curve direction
        spacing_factor: Spacing multiplier along curve
    """
    result = urban.array_along_path(
        source_object, curve_name, count,
        align_to_curve, spacing_factor
    )
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def randomize_transform(
    object_names: list[str] | None = None,
    location_range: tuple = (0.0, 0.0, 0.0),
    rotation_range: tuple = (0.0, 0.0, 0.0),
    scale_range: tuple = (0.0, 0.0, 0.0),
    seed: int = 0
) -> list[TextContent]:
    """
    Add random variation to object transforms.

    Args:
        object_names: List of object names (None = use selected)
        location_range: Random range for location (X, Y, Z)
        rotation_range: Random range for rotation (X, Y, Z) in radians
        scale_range: Random range for scale (X, Y, Z) as multiplier
        seed: Random seed for reproducibility
    """
    result = urban.randomize_transform(
        object_names, location_range,
        rotation_range, scale_range, seed
    )
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def create_stairs(
    steps: int = 10,
    step_width: float = 2.0,
    step_depth: float = 0.3,
    step_height: float = 0.2,
    name: str = "Stairs",
    location: tuple = (0, 0, 0)
) -> list[TextContent]:
    """
    Create parametric stairs.

    Args:
        steps: Number of steps
        step_width: Width of each step
        step_depth: Depth of each step
        step_height: Height of each step
        name: Name for the stairs collection
        location: Starting location (X, Y, Z)
    """
    result = urban.create_stairs(
        steps, step_width, step_depth,
        step_height, name, location
    )
    return [TextContent(type="text", text=str(result))]


# Edit mode / mesh tools
@app.tool()
async def edit_mode_enter(object_name: str, mode: str = "EDIT") -> list[TextContent]:
    """Switch an object to edit/object mode."""
    result = mesh_edit.edit_mode_enter(object_name, mode)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def edit_mode_exit(object_name: str) -> list[TextContent]:
    """Exit edit mode to object mode."""
    result = mesh_edit.edit_mode_exit(object_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def select_geometry(
    object_name: str,
    mode: str,
    indices: list[int] | None = None,
    pattern: str = "ALL",
    expand: int = 0,
) -> list[TextContent]:
    """Select geometry elements (verts/edges/faces) with patterns."""
    result = mesh_edit.select_geometry(object_name, mode, indices, pattern, expand)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def extrude(
    object_name: str,
    mode: str,
    offset: tuple[float, float, float],
    scale: float = 1.0,
) -> list[TextContent]:
    """Extrude selected elements."""
    result = mesh_edit.extrude(object_name, mode, offset, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def loop_cut(object_name: str, edge_index: int, cuts: int = 1, slide: float = 0.0, even: bool = False) -> list[TextContent]:
    """Add loop cuts."""
    result = mesh_edit.loop_cut(object_name, edge_index, cuts, slide, even)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def inset_faces(
    object_name: str,
    face_indices: list[int] | None,
    thickness: float,
    depth: float = 0.0,
    use_boundary: bool = True,
    use_even_offset: bool = True,
) -> list[TextContent]:
    """Inset selected faces."""
    result = mesh_edit.inset_faces(object_name, face_indices, thickness, depth, use_boundary, use_even_offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def bevel_edges(
    object_name: str,
    edge_indices: list[int] | None,
    width: float,
    segments: int = 1,
    profile: float = 0.5,
    clamp: bool = True,
) -> list[TextContent]:
    """Selective edge bevel."""
    result = mesh_edit.bevel_edges(object_name, edge_indices, width, segments, profile, clamp)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def bridge_edge_loops(
    object_name: str,
    loop1_indices: list[int],
    loop2_indices: list[int],
    cuts: int = 0,
    twist: int = 0,
) -> list[TextContent]:
    """Bridge two edge loops."""
    result = mesh_edit.bridge_edge_loops(object_name, loop1_indices, loop2_indices, cuts, twist)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def merge_vertices(object_name: str, mode: str = "CENTER", threshold: float = 0.0001) -> list[TextContent]:
    """Merge selected vertices."""
    result = mesh_edit.merge_vertices(object_name, mode, threshold)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def dissolve(object_name: str, mode: str = "EDGE", angle_limit: float = 0.0872665) -> list[TextContent]:
    """Dissolve verts/edges/faces/limited."""
    result = mesh_edit.dissolve(object_name, mode, angle_limit)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def knife_cut(object_name: str, cut_points: list[tuple[float, float, float]], cut_through: bool = False) -> list[TextContent]:
    """Knife projection along a polyline of points."""
    result = mesh_edit.knife_cut(object_name, cut_points, cut_through)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def uv_unwrap(
    object_name: str,
    method: str = "ANGLE_BASED",
    angle_limit: float = 66.0,
    island_margin: float = 0.02,
) -> list[TextContent]:
    """UV unwrap helper (angle, conformal, smart, project view)."""
    result = mesh_edit.uv_unwrap(object_name, method, angle_limit, island_margin)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def uv_mark_seam(object_name: str, edge_indices: list[int], clear: bool = False) -> list[TextContent]:
    """Mark/clear seams by edge indices."""
    result = mesh_edit.uv_mark_seam(object_name, edge_indices, clear)
    return [TextContent(type="text", text=str(result))]


# Geometry Nodes
@app.tool()
async def geonodes_create(object_name: str, tree_name: str) -> list[TextContent]:
    """Create GeoNodes tree and attach modifier."""
    result = geonodes.geonodes_create(object_name, tree_name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def geonodes_add_node(
    tree_name: str,
    node_type: str,
    location: tuple[int, int],
    name: str | None = None,
) -> list[TextContent]:
    """Add node to GeoNodes tree."""
    result = geonodes.geonodes_add_node(tree_name, node_type, location, name)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def geonodes_connect(
    tree_name: str,
    from_node: str,
    from_socket: str | int,
    to_node: str,
    to_socket: str | int,
) -> list[TextContent]:
    """Connect two sockets in GeoNodes."""
    result = geonodes.geonodes_connect(tree_name, from_node, from_socket, to_node, to_socket)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def geonodes_set_input(
    tree_name: str,
    node_name: str,
    input_name: str | int,
    value: Any,
) -> list[TextContent]:
    """Set GeoNodes node input default."""
    result = geonodes.geonodes_set_input(tree_name, node_name, input_name, value)
    return [TextContent(type="text", text=str(result))]


# Import / Export
@app.tool()
async def import_model(filepath: str, format: str, scale: float = 1.0) -> list[TextContent]:
    """Import model from disk."""
    result = io_tools.import_model(filepath, format, scale)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def export_model(
    filepath: str,
    format: str,
    object_names: list[str] | None = None,
    apply_modifiers: bool = True,
) -> list[TextContent]:
    """Export selected or specified objects."""
    result = io_tools.export_model(filepath, format, object_names, apply_modifiers)
    return [TextContent(type="text", text=str(result))]


# BMesh direct
@app.tool()
async def bmesh_create_geometry(
    object_name: str,
    vertices: list[tuple[float, float, float]],
    edges: list[list[int]] | None = None,
    faces: list[list[int]] | None = None,
) -> list[TextContent]:
    """Write raw geometry into a mesh object."""
    result = mesh_edit.bmesh_create_geometry(object_name, vertices, edges, faces)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def bmesh_get_geometry(object_name: str) -> list[TextContent]:
    """Read raw geometry lists from a mesh."""
    result = mesh_edit.bmesh_get_geometry(object_name)
    return [TextContent(type="text", text=str(result))]


# Advanced edit tools
@app.tool()
async def spin(
    object_name: str,
    angle: float = 6.283185,
    steps: int = 12,
    axis: str = "Z",
    center: tuple[float, float, float] | None = None,
    dupli: bool = False,
) -> list[TextContent]:
    """Revolve geometry around an axis."""
    result = advanced.spin(object_name, angle, steps, axis, center, dupli)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def screw(
    object_name: str,
    screw_offset: float = 1.0,
    iterations: int = 2,
    steps: int = 16,
    axis: str = "Z",
) -> list[TextContent]:
    """Helical extrusion operator."""
    result = advanced.screw(object_name, screw_offset, iterations, steps, axis)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def fill_hole(object_name: str, mode: str = "BEAUTY", span: int = 1, offset: int = 0) -> list[TextContent]:
    """Fill holes using beauty or grid fill."""
    result = advanced.fill_hole(object_name, mode, span, offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def shrink_fatten(object_name: str, offset: float, use_even_offset: bool = True) -> list[TextContent]:
    """Normal-based extrusion."""
    result = advanced.shrink_fatten(object_name, offset, use_even_offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_edge_crease(object_name: str, edge_indices: list[int] | None = None, value: float = 1.0) -> list[TextContent]:
    """Set SubD crease on edges."""
    result = advanced.set_edge_crease(object_name, edge_indices, value)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_bevel_weight(object_name: str, edge_indices: list[int] | None = None, value: float = 1.0) -> list[TextContent]:
    """Set bevel weight for bevel modifier."""
    result = advanced.set_bevel_weight(object_name, edge_indices, value)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def mark_sharp(object_name: str, edge_indices: list[int] | None = None, clear: bool = False) -> list[TextContent]:
    """Mark or clear sharp edges."""
    result = advanced.mark_sharp(object_name, edge_indices, clear)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_shade_smooth(
    object_name: str,
    smooth: bool = True,
    use_auto_smooth: bool = True,
    auto_smooth_angle: float = 0.523599,
) -> list[TextContent]:
    """Toggle smooth/flat shading and auto smooth angle."""
    result = advanced.set_shade_smooth(object_name, smooth, use_auto_smooth, auto_smooth_angle)
    return [TextContent(type="text", text=str(result))]


# Vertex groups
@app.tool()
async def create_vertex_group(
    object_name: str,
    group_name: str,
    vertex_indices: list[int] | None = None,
    weight: float = 1.0,
) -> list[TextContent]:
    result = advanced.create_vertex_group(object_name, group_name, vertex_indices, weight)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def assign_to_vertex_group(
    object_name: str,
    group_name: str,
    vertex_indices: list[int],
    weight: float = 1.0,
    mode: str = "REPLACE",
) -> list[TextContent]:
    result = advanced.assign_to_vertex_group(object_name, group_name, vertex_indices, weight, mode)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def remove_from_vertex_group(
    object_name: str,
    group_name: str,
    vertex_indices: list[int] | None = None,
) -> list[TextContent]:
    result = advanced.remove_from_vertex_group(object_name, group_name, vertex_indices)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def get_vertex_groups(object_name: str) -> list[TextContent]:
    result = advanced.get_vertex_groups(object_name)
    return [TextContent(type="text", text=str(result))]


# Modifiers
@app.tool()
async def add_solidify(
    object_name: str,
    thickness: float = 0.01,
    offset: float = -1.0,
    use_even_thickness: bool = True,
    use_quality_normals: bool = True,
    use_rim: bool = True,
    use_rim_only: bool = False,
    material_offset: int = 0,
    material_offset_rim: int = 0,
) -> list[TextContent]:
    result = advanced.add_solidify(
        object_name,
        thickness,
        offset,
        use_even_thickness,
        use_quality_normals,
        use_rim,
        use_rim_only,
        material_offset,
        material_offset_rim,
    )
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_screw_modifier(
    object_name: str,
    angle: float = 6.283185,
    screw_offset: float = 0.0,
    iterations: int = 1,
    steps: int = 16,
    axis: str = "Z",
    use_merge_vertices: bool = True,
    merge_threshold: float = 0.0001,
) -> list[TextContent]:
    result = advanced.add_screw_modifier(
        object_name,
        angle,
        screw_offset,
        iterations,
        steps,
        axis,
        use_merge_vertices,
        merge_threshold,
    )
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_shrinkwrap(
    object_name: str,
    target: str,
    wrap_method: str = "NEAREST_SURFACEPOINT",
    wrap_mode: str = "ON_SURFACE",
    offset: float = 0.0,
) -> list[TextContent]:
    result = advanced.add_shrinkwrap(object_name, target, wrap_method, wrap_mode, offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_weighted_normal(
    object_name: str,
    weight: int = 50,
    mode: str = "FACE_AREA",
    keep_sharp: bool = True,
    face_influence: bool = False,
) -> list[TextContent]:
    result = advanced.add_weighted_normal(object_name, weight, mode, keep_sharp, face_influence)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_lattice(
    object_name: str,
    lattice_object: str | None = None,
    resolution: tuple[int, int, int] = (2, 2, 2),
    interpolation: str = "KEY_LINEAR",
) -> list[TextContent]:
    result = advanced.add_lattice(object_name, lattice_object, resolution, interpolation)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_wireframe(
    object_name: str,
    thickness: float = 0.02,
    use_even_offset: bool = True,
    use_boundary: bool = True,
    use_replace: bool = True,
    material_offset: int = 0,
) -> list[TextContent]:
    result = advanced.add_wireframe(object_name, thickness, use_even_offset, use_boundary, use_replace, material_offset)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def add_skin(object_name: str, branch_smoothing: float = 0.0, use_smooth_shade: bool = False) -> list[TextContent]:
    result = advanced.add_skin(object_name, branch_smoothing, use_smooth_shade)
    return [TextContent(type="text", text=str(result))]


# Curves / conversion / macro
@app.tool()
async def convert_object(object_name: str, target_type: str = "MESH") -> list[TextContent]:
    result = advanced.convert_object(object_name, target_type)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def set_curve_bevel(
    curve_name: str,
    depth: float = 0.0,
    resolution: int = 4,
    bevel_object: str | None = None,
    fill_mode: str = "FULL",
) -> list[TextContent]:
    result = advanced.set_curve_bevel(curve_name, depth, resolution, bevel_object, fill_mode)
    return [TextContent(type="text", text=str(result))]


@app.tool()
async def circular_array(
    object_name: str,
    count: int,
    axis: str = "Z",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    angle: float = 6.283185,
    use_instances: bool = True,
) -> list[TextContent]:
    result = advanced.circular_array(object_name, count, axis, center, angle, use_instances)
    return [TextContent(type="text", text=str(result))]


def main():
    """Main entry point"""
    logger.info("Hephaestus - Advanced Blender MCP v0.1.0")
    logger.info("Connecting to Blender...")

    try:
        logger.info("Starting Hephaestus MCP Server...")
        app.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

