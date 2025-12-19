# Hephaestus – Tools Overview (MVP)

## Scene
- `get_scene_info()`: Objects, collections, materials, active object.
- `get_object_info(object_name)`: Per-object details.
- `get_viewport_screenshot(max_size=800)`: PNG path + dimensions.
- `measure_distance(object_a/object_b | point_a/point_b)`: Distance between two objects (origins) or two points.
- `bbox_info(object_name)`: Bounding box info (min/max/size/centers).
- `multi_view_screenshots(camera_name, presets=["product","top","front","isometric"], max_size=800)`: Capture several views with presets.
- `orbit_screenshots(camera_name, center=(0,0,0), radius=8.0, shots=8, max_size=800)`: Orbit around a center and capture screenshots.
- `create_collection(name, parent=None, color=None)`
- `move_to_collection(object_names, collection_name)`
- `get_collection_tree()`
- `clear_scene()`: Delete all objects.
- `create_empty(name, location)`: Create an empty.
- `create_curve_path(name, points)`: Create a polyline curve from points.
- `batch_select(pattern, object_type=None)`

## Objects
- `create_primitive(type, name=None, location=(0,0,0), scale=(1,1,1), rotation=(0,0,0))`
- `delete_object(name)`
- `delete_objects(object_names)`
- `set_parent(child_names, parent_name, keep_transform=True)`
- `apply_transforms(object_names, location=True, rotation=True, scale=True)`: Bake transforms into geometry.
- `join_objects(object_names, new_name="Joined")`: Join multiple meshes.
- `set_origin(object_name, mode="geometry|center_of_mass|cursor", target=(0,0,0))`: Move origin without moving geometry.
- `instance_collection(collection_name, name?, location, rotation?, scale?)`: Instance a collection as an empty.
- `transform_object(name, location=None, rotation=None, scale=None)`
- `duplicate_object(name, new_name=None, location_offset=None)`
- `array_objects(object_name, count, offset, axis="X")`
- `select_object(name, deselect_others=True)`
- `rename_object(old_name, new_name)`
- `get_selected_objects()`

## Materials
- `create_material(name, base_color, roughness=0.5, metallic=0.0)`
- `assign_material(object_name, material_name, slot=0)`
- `create_material_preset(preset_name, custom_name=None)` presets: concrete, metal_dark, metal_chrome, glass, plastic, wood, emission.
- `set_material_property(material_name, property_name, value)`
- `get_material_list()`

## Modifiers
- `add_modifier(object_name, modifier_type, name=None, **params)` ARRAY, MIRROR, SUBDIVISION, BOOLEAN, SOLIDIFY, BEVEL.
- `modify_modifier(object_name, modifier_name, **params)`
- `apply_modifier(object_name, modifier_name)`
- `remove_modifier(object_name, modifier_name)`
- `boolean_operation(object_a, object_b, operation="DIFFERENCE")`
- `add_bevel(object_name, width=0.02, segments=2, limit_method="ANGLE", angle_limit=0.785)`
- `add_mirror(object_name, axes=(True,False,False), merge=True, merge_threshold=0.001)`
- `add_array(object_name, count=3, offset=(1,0,0), relative=True)`

## Camera
- `create_camera(name, location, rotation=None)`
- `set_active_camera(camera_name)`
- `point_camera_at(camera_name, target)` target = object name or (x, y, z)
- `set_camera_orthographic(camera_name, scale=10)`
- `set_camera_preset(camera_name, preset)` presets: isometric, top, front, product.
- `create_camera_rig(type="turntable", target=None)`

## Lighting
- `create_light(type, name, location, energy=100, color=None)`
- `set_light_property(light_name, property_name, value)`
- `apply_lighting_preset(preset_name)` presets: three_point, studio, soft, dramatic, sunset.
- `set_world_hdri(hdri_path, rotation=0, strength=1.0)`

## Urban / Utilities
- `snap_to_grid(step=1.0, object_names=None)`: Snap selection or given objects to a grid.
- `align_objects(target, mode="center", object_names=None, reference=None)`: Align along X/Y/Z with min/center/max/value.
- `scatter_along_curve(source_object, curve_name, count, jitter=None)`: Duplicate an object along a curve.
- `create_road(width, length, segments=4, add_sidewalk=True, sidewalk_width=1.5, sidewalk_height=0.15)`: Simple road + sidewalks.
- `repeat_facade(base_object, floors=5, bays=4, floor_height=3.0, bay_width=3.0)`: Grid of facade elements.
- `macro_city_block(style="modern", buildings=6, lamps_per_side=6)`: Quick city block (road, sidewalks, buildings, lamps).
- `mech_rig(style="basic", include_chain=True)`: Small mech rig (2 sprockets + optional chain + arm base).
- `clear_scene()`: Delete all objects.
- `create_empty(name, location)`: Create an empty.
- `create_curve_path(name, points)`: Create a polyline curve from points.
