# Hephaestus – API Notes

- Transport: MCP stdio between client and `hephaestus.server` (FastMCP).
- Bridge: TCP socket between MCP and Blender addon (`localhost:9876`).
- Message format: `{"type": "<command_name>", "params": {...}}` newline-delimited.
- Responses: `{"status": "success"|"error", "result": {...}, "message": "..."}`.
- MCP tools mirror `src/hephaestus/tools/*` and are registered in `src/hephaestus/server.py`.
- Addon executes the corresponding command in `execute_blender_command` and returns the same response shape.
