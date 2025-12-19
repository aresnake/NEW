"""Fix random import issue in randomize_transform"""
import re

with open(r'D:\EPHAESTUS\addon.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the randomize_transform function
old_code = '''        # randomize_transform - Add random variation to transforms
        elif command_type == "randomize_transform":
            object_names = params.get("object_names", [])
            location_range = params.get("location_range", [0.0, 0.0, 0.0])
            rotation_range = params.get("rotation_range", [0.0, 0.0, 0.0])
            scale_range = params.get("scale_range", [0.0, 0.0, 0.0])
            seed = params.get("seed", 0)

            if seed:
                random.seed(seed)'''

new_code = '''        # randomize_transform - Add random variation to transforms
        elif command_type == "randomize_transform":
            import random as rand_module  # Local import to avoid UnboundLocalError

            object_names = params.get("object_names", [])
            location_range = params.get("location_range", [0.0, 0.0, 0.0])
            rotation_range = params.get("rotation_range", [0.0, 0.0, 0.0])
            scale_range = params.get("scale_range", [0.0, 0.0, 0.0])
            seed = params.get("seed", 0)

            if seed:
                rand_module.seed(seed)'''

content = content.replace(old_code, new_code)

# Also replace all random.uniform with rand_module.uniform in this section
# Find the randomize_transform section
start_idx = content.find('elif command_type == "randomize_transform"')
end_idx = content.find('elif command_type == "create_stairs"', start_idx)

if start_idx > 0 and end_idx > 0:
    section = content[start_idx:end_idx]
    fixed_section = section.replace('random.uniform', 'rand_module.uniform')
    content = content[:start_idx] + fixed_section + content[end_idx:]

with open(r'D:\EPHAESTUS\addon.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed random import issue")
