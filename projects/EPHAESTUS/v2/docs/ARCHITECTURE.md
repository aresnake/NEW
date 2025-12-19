# MCP Server v2

## Decisions
- Python-only stack for speed + Blender compatibility.
- MCP via stdio (official), strict JSON-RPC, no stdout logs.
- Single registry of tools; listTools is authoritative.
- Bridge client abstracts Blender transport (IPC/socket later).
- Config via `HEPHAESTUS_CONFIG` JSON file + env vars.

## Next steps
- Implement bridge protocol and addon handshake.
- Port real tool execution in bridge.
- Add tests for tool schema + MCP compliance.