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
- `blender-add-cylinder`
- `blender-move-object`
- `blender-scale-object`
- `blender-rotate-object`
- `blender-delete-object`
- `blender-join-objects`
- `blender-set-origin`
- `blender-apply-transforms`
- `blender-create-material`
- `blender-export`
- `blender-rename-object`
- `macro-blockout`
- `intent-resolve`
- `intent-run`
- `replay-list`
- `replay-run`
- `model-start`
- `model-step`
- `model-end`
- `tool-request`

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
- replay-list:
  ```json
  {"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"replay-list","arguments":{"limit":10}}}
  ```
- replay-run:
  ```json
  {"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"replay-run","arguments":{"id":"<action-id>"}}}
  ```
- model-start:
  ```json
  {"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"model-start","arguments":{"goal":"blockout scene"}}}
  ```
- model-step:
  ```json
  {"jsonrpc":"2.0","id":15,"method":"tools/call","params":{"name":"model-step","arguments":{"session":"<session-id>","intent":"move cube","proposed_tool":"blender-move-object","proposed_args":{"name":"Cube","x":1,"y":2,"z":3}}}}}
  ```
- model-end:
  ```json
  {"jsonrpc":"2.0","id":16,"method":"tools/call","params":{"name":"model-end","arguments":{"session":"<session-id>","summary":"done"}}}
  ```
- tool-request:
  ```json
  {"jsonrpc":"2.0","id":17,"method":"tools/call","params":{"name":"tool-request","arguments":{"session":"<session-id>","need":"boolean toggle","why":"not available yet"}}}
  ```
- blender-add-cylinder:
  ```json
  {"jsonrpc":"2.0","id":18,"method":"tools/call","params":{"name":"blender-add-cylinder","arguments":{"vertices":16,"radius":1.0,"depth":2.0,"location":[0,0,0],"name":"MyCylinder"}}}
  ```
- blender-scale-object:
  ```json
  {"jsonrpc":"2.0","id":19,"method":"tools/call","params":{"name":"blender-scale-object","arguments":{"name":"Cube","uniform":1.5}}}
  ```
- blender-rotate-object:
  ```json
  {"jsonrpc":"2.0","id":20,"method":"tools/call","params":{"name":"blender-rotate-object","arguments":{"name":"Cube","rotation":[0,0,90],"space":"world"}}}
  ```
- blender-join-objects:
  ```json
  {"jsonrpc":"2.0","id":21,"method":"tools/call","params":{"name":"blender-join-objects","arguments":{"objects":["Cube","Cylinder"],"name":"Joined"}}}
  ```
- blender-set-origin:
  ```json
  {"jsonrpc":"2.0","id":22,"method":"tools/call","params":{"name":"blender-set-origin","arguments":{"name":"Cube","type":"geometry"}}}
  ```
- blender-apply-transforms:
  ```json
  {"jsonrpc":"2.0","id":23,"method":"tools/call","params":{"name":"blender-apply-transforms","arguments":{"name":"Cube","location":true,"rotation":true,"scale":true}}}
  ```
- blender-create-material:
  ```json
  {"jsonrpc":"2.0","id":24,"method":"tools/call","params":{"name":"blender-create-material","arguments":{"name":"MyMat","base_color":[1.0,0.0,0.0,1.0]}}}
  ```
- blender-export:
  ```json
  {"jsonrpc":"2.0","id":25,"method":"tools/call","params":{"name":"blender-export","arguments":{"path":"D:\\\\output.fbx","format":"fbx","selected_only":false}}}
  ```
- blender-rename-object:
  ```json
  {"jsonrpc":"2.0","id":26,"method":"tools/call","params":{"name":"blender-rename-object","arguments":{"old_name":"Cube","new_name":"Box"}}}
  ```

Debugging:
- `GET http://127.0.0.1:8765/debug` returns timer tick/queue stats.

## Troubleshooting
- Ensure nothing else binds `127.0.0.1:8765`; restart Blender after bridge crashes.
- If calls fail, check OS firewall rules for Blender and port 8765.
- Server stdout must be JSON-RPC NDJSON only; any stray prints break the client.
- Confirm `python -u D:\v3\scripts\mcp_stdio_server.py` starts without errors and exits when stdin closes.
- Bridge errors stay in Blender console; restart bridge if it stops responding.
