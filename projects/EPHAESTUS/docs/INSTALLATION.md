# Hephaestus – Installation Guide

## Prerequisites
- Python 3.10+
- Blender 3.0+
- `uv` package manager (`pip install uv`)
- Claude Desktop (or any MCP-capable client)

## Install the MCP server
```bash
pip install uv
uv pip install -e .
```

## Install the Blender addon
1. Open Blender.
2. `Edit > Preferences > Add-ons > Install`.
3. Select `addon.py` from this repository.
4. Enable **Hephaestus MCP**.
5. In the 3D View sidebar (press `N`) open **Hephaestus** and click **Start Hephaestus Server**.

## Run the MCP server
- For local dev: `uvx hephaestus`
- The server listens over stdio for MCP clients and relays commands to the Blender addon on `localhost:9876`.

## Claude Desktop configuration
Add the MCP server to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "hephaestus": {
      "command": "uvx",
      "args": ["hephaestus"]
    }
  }
}
```

## Quick smoke test
1. Start the addon server inside Blender (button in the panel).
2. Run `uvx hephaestus` in a terminal.
3. In Claude, ask: “Add a concrete material to the active object.”  
   Claude should call `create_material_preset("concrete")` then `assign_material(...)`.
