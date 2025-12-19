# Hephaestus – Architecture

```
Claude (MCP client)
   |
   | stdio MCP
   v
hephaestus.server (FastMCP)  <---> hephaestus.tools.*  (scene, objects, materials, modifiers, camera, lighting)
   |
   | TCP JSON (localhost:9876)
   v
Blender addon (addon.py)  <---> Blender Python API
```

- **MCP server** (`src/hephaestus/server.py`): registers tools and forwards calls to `hephaestus.tools.*`.
- **Connection** (`src/hephaestus/connection.py`): small socket client, newline-delimited JSON.
- **Addon** (`addon.py`): TCP server inside Blender; executes commands; UI panel to start/stop the server.
- **Presets** (`src/hephaestus/presets/`): JSON for materials and lighting.
- **Entry point**: `uvx hephaestus` -> `hephaestus.server:main`.
