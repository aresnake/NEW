"""
Patch to add to addon.py execute_blender_command function
Add these commands just before the final 'else:' statement (line 2113)
"""

# create_building_box - Create parametric building volume
elif command_type == "create_building_box":
    width = params.get("width", 10.0)
    depth = params.get("depth", 10.0)
    height = params.get("height", 15.0)
    floors = params.get("floors", 5)
    name = params.get("name", "Building")

    # Create base cube
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, height/2))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width/2, depth/2, height/2)

    # Add custom properties for floors
    obj["floors"] = floors
    obj["floor_height"] = height / floors

    result = {
        "name": obj.name,
        "dimensions": [width, depth, height],
        "floors": floors,
        "floor_height": height / floors
    }
    return {"status": "success", "result": result, "message": f"Building box '{name}' created"}

# create_window_grid - Create parametric window grid
elif command_type == "create_window_grid":
    building_name = params.get("building_name")
    floors = params.get("floors", 5)
    windows_per_floor = params.get("windows_per_floor", 4)
    window_width = params.get("window_width", 1.5)
    window_height = params.get("window_height", 2.0)
    spacing = params.get("spacing", 0.5)
    inset = params.get("inset", 0.1)

    building = bpy.data.objects.get(building_name)
    if not building:
        return {"status": "error", "message": f"Building '{building_name}' not found"}

    # Get building dimensions
    dims = building.dimensions
    floor_height = dims[2] / floors

    windows_created = []

    # Create windows on one face (front)
    for floor in range(floors):
        for win in range(windows_per_floor):
            # Create window primitive
            bpy.ops.mesh.primitive_cube_add(size=1)
            window = bpy.context.active_object
            window.name = f"Window_F{floor}_W{win}"

            # Scale to window size
            window.scale = (window_width/2, 0.05, window_height/2)

            # Position window
            x_pos = -dims[0]/2 + spacing + win * (window_width + spacing)
            y_pos = dims[1]/2 + inset
            z_pos = floor * floor_height + floor_height/2

            window.location = (x_pos, y_pos, z_pos)

            # Parent to building
            window.parent = building

            windows_created.append(window.name)

    result = {
        "building": building_name,
        "windows_created": len(windows_created),
        "window_names": windows_created[:10]  # First 10 for brevity
    }
    return {"status": "success", "result": result, "message": f"Created {len(windows_created)} windows"}

# array_along_path - Array objects along a curve
elif command_type == "array_along_path":
    source_object = params.get("source_object")
    curve_name = params.get("curve_name")
    count = params.get("count", 10)
    align_to_curve = params.get("align_to_curve", True)
    spacing_factor = params.get("spacing_factor", 1.0)

    source = bpy.data.objects.get(source_object)
    curve = bpy.data.objects.get(curve_name)

    if not source:
        return {"status": "error", "message": f"Source object '{source_object}' not found"}
    if not curve or curve.type != 'CURVE':
        return {"status": "error", "message": f"Curve '{curve_name}' not found or not a curve"}

    # Get curve spline
    spline = curve.data.splines[0]
    curve_length = len(spline.points) if spline.type == 'POLY' else len(spline.bezier_points)

    created_objects = []

    for i in range(count):
        # Duplicate source
        new_obj = source.copy()
        if source.data:
            new_obj.data = source.data.copy()
        bpy.context.collection.objects.link(new_obj)
        new_obj.name = f"{source.name}_Path_{i}"

        # Calculate position along curve (0 to 1)
        t = (i / max(count - 1, 1)) * spacing_factor

        # Simple linear interpolation along curve
        if spline.type == 'POLY':
            idx = int(t * (curve_length - 1))
            idx = min(idx, curve_length - 1)
            point = spline.points[idx]
            local_pos = Vector((point.co[0], point.co[1], point.co[2]))
        else:
            idx = int(t * (curve_length - 1))
            idx = min(idx, curve_length - 1)
            point = spline.bezier_points[idx]
            local_pos = point.co

        # Transform to world space
        world_pos = curve.matrix_world @ local_pos
        new_obj.location = world_pos

        created_objects.append(new_obj.name)

    result = {
        "source": source_object,
        "curve": curve_name,
        "objects_created": len(created_objects),
        "object_names": created_objects
    }
    return {"status": "success", "result": result, "message": f"Created {len(created_objects)} objects along path"}

# randomize_transform - Add random variation to transforms
elif command_type == "randomize_transform":
    object_names = params.get("object_names", [])
    location_range = params.get("location_range", [0.0, 0.0, 0.0])
    rotation_range = params.get("rotation_range", [0.0, 0.0, 0.0])
    scale_range = params.get("scale_range", [0.0, 0.0, 0.0])
    seed = params.get("seed", 0)

    if seed:
        random.seed(seed)

    if not object_names:
        object_names = [obj.name for obj in bpy.context.selected_objects]

    randomized = []

    for obj_name in object_names:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        # Randomize location
        if any(location_range):
            obj.location.x += random.uniform(-location_range[0], location_range[0])
            obj.location.y += random.uniform(-location_range[1], location_range[1])
            obj.location.z += random.uniform(-location_range[2], location_range[2])

        # Randomize rotation
        if any(rotation_range):
            obj.rotation_euler.x += random.uniform(-rotation_range[0], rotation_range[0])
            obj.rotation_euler.y += random.uniform(-rotation_range[1], rotation_range[1])
            obj.rotation_euler.z += random.uniform(-rotation_range[2], rotation_range[2])

        # Randomize scale
        if any(scale_range):
            obj.scale.x *= 1.0 + random.uniform(-scale_range[0], scale_range[0])
            obj.scale.y *= 1.0 + random.uniform(-scale_range[1], scale_range[1])
            obj.scale.z *= 1.0 + random.uniform(-scale_range[2], scale_range[2])

        randomized.append(obj_name)

    result = {
        "objects_randomized": len(randomized),
        "object_names": randomized
    }
    return {"status": "success", "result": result, "message": f"Randomized {len(randomized)} objects"}

# create_stairs - Create parametric stairs
elif command_type == "create_stairs":
    steps = params.get("steps", 10)
    step_width = params.get("step_width", 2.0)
    step_depth = params.get("step_depth", 0.3)
    step_height = params.get("step_height", 0.2)
    name = params.get("name", "Stairs")
    location = params.get("location", [0, 0, 0])

    created_steps = []

    for i in range(steps):
        # Create step
        bpy.ops.mesh.primitive_cube_add(size=1)
        step = bpy.context.active_object
        step.name = f"{name}_Step_{i}"

        # Scale step
        step.scale = (step_width/2, step_depth/2, step_height/2)

        # Position step
        step.location = (
            location[0],
            location[1] + i * step_depth,
            location[2] + i * step_height + step_height/2
        )

        created_steps.append(step.name)

    # Create collection for stairs
    if name not in bpy.data.collections:
        stairs_col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(stairs_col)
    else:
        stairs_col = bpy.data.collections[name]

    # Move steps to collection
    for step_name in created_steps:
        step = bpy.data.objects.get(step_name)
        if step:
            for col in step.users_collection:
                col.objects.unlink(step)
            stairs_col.objects.link(step)

    result = {
        "name": name,
        "steps_created": len(created_steps),
        "total_height": steps * step_height,
        "total_length": steps * step_depth
    }
    return {"status": "success", "result": result, "message": f"Stairs '{name}' with {steps} steps created"}
