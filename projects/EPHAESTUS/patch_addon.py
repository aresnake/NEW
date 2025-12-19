"""
Script to patch addon.py with new urban tools
"""

# Read the addon file
with open(r'D:\EPHAESTUS\addon.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Read the patch content
with open(r'D:\EPHAESTUS\urban_tools_addon_patch.py', 'r', encoding='utf-8') as f:
    patch_lines = f.readlines()[5:]  # Skip the docstring header
    patch_content = ''.join(patch_lines)

# Find the line with the final else statement
target = '        else:\n            return {"status": "error", "message": f"Unknown command type: {command_type}"}'

if target in content:
    # Insert patch before the else statement
    new_content = content.replace(
        target,
        '\n        ' + patch_content.strip() + '\n\n        ' + target.strip()
    )

    # Write back
    with open(r'D:\EPHAESTUS\addon.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("SUCCESS: Patch applied successfully!")
    print(f"Added {len(patch_lines)} lines of code")
else:
    print("ERROR: Target location not found in addon.py")
    print("Looking for:")
    print(target)
