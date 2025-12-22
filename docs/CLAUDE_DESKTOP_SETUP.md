# Claude Desktop + Blender Bridge

## Claude Desktop MCP entry
Add to your Claude Desktop `mcpServers`:
```json
{
  "command": "python",
  "args": ["-u", "D:\\v3\\scripts\\mcp_stdio_server.py"]
}
```

## Tools exposed
- `health`
- `blender-ping`
- `blender-snapshot`
- `blender-exec` (debug)
- `blender-add-cube`
- `blender-move-object`
- `blender-delete-object`
- `macro-blockout`
- `intent-resolve`
- `intent-run`

## Run the Blender bridge (background HTTP server)
- Blender UI:
  ```powershell
  & "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --factory-startup --python D:\v3\bridge\blender_bridge.py
  ```
- Headless:
  ```powershell
  & "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b --factory-startup --python D:\v3\bridge\blender_bridge.py
  ```

The bridge runs an HTTP server on `127.0.0.1:8765` in a background thread and keeps Blender responsive. The MCP server works even if the bridge is down; bridge errors return JSON-RPC errors without stdout noise.

Environment:
- `NEW_MCP_EXEC_TIMEOUT`: max seconds to wait for bridge code execution (default 10.0).
- `NEW_MCP_BRIDGE_URL`/`BLENDER_MCP_BRIDGE_URL`: bridge base URL (default http://127.0.0.1:8765)
- `NEW_MCP_BRIDGE_TIMEOUT`/`BLENDER_MCP_BRIDGE_TIMEOUT`: bridge HTTP timeout in seconds.
- `NEW_MCP_DEBUG_EXEC`/`BLENDER_MCP_DEBUG_EXEC`: set to `1` to allow `blender-exec` and `exec:` intents.

Examples:
- intent-resolve:
  ```json
  {"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"intent-resolve","arguments":{"text":"move cube 1 2 3"}}}
  ```
- intent-run:
  ```json
  {"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"intent-run","arguments":{"text":"add cube"}}}
  ```

Debugging:
- `GET http://127.0.0.1:8765/debug` returns timer tick/queue stats.

## Troubleshooting
- Ensure nothing else binds `127.0.0.1:8765`; restart Blender after bridge crashes.
- If calls fail, check OS firewall rules for Blender and port 8765.
- Server stdout must be JSON-RPC NDJSON only; any stray prints break the client.
- Confirm `python -u D:\v3\scripts\mcp_stdio_server.py` starts without errors and exits when stdin closes.
- Bridge errors stay in Blender console; restart bridge if it stops responding.
