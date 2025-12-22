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
- `blender-add-sphere`
- `blender-add-plane`
- `blender-add-cone`
- `blender-add-torus`
- `blender-move-object`
- `blender-scale-object`
- `blender-rotate-object`
- `blender-duplicate-object`
- `blender-list-objects`
- `blender-get-object-info`
- `blender-select-object`
- `blender-add-camera`
- `blender-add-light`
- `blender-delete-object`
- `blender-join-objects`
- `blender-set-origin`
- `blender-apply-transforms`
- `blender-create-material`
- `blender-export`
- `blender-rename-object`
- `blender-assign-material`
- `blender-set-shading`
- `blender-delete-all`
- `blender-reset-transform`
- `blender-get-mesh-stats`
- `blender-extrude`
- `blender-inset`
- `blender-loop-cut`
- `blender-bevel-edges`
- `blender-add-modifier`
- `blender-apply-modifier`
- `blender-boolean`
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
- blender-add-sphere:
  ```json
  {"jsonrpc":"2.0","id":27,"method":"tools/call","params":{"name":"blender-add-sphere","arguments":{"type":"uv","segments":32,"rings":16,"radius":1.0,"location":[0,0,0],"name":"MySphere"}}}
  ```
- blender-add-plane:
  ```json
  {"jsonrpc":"2.0","id":28,"method":"tools/call","params":{"name":"blender-add-plane","arguments":{"size":2.0,"location":[0,0,0],"name":"MyPlane"}}}
  ```
- blender-add-cone:
  ```json
  {"jsonrpc":"2.0","id":29,"method":"tools/call","params":{"name":"blender-add-cone","arguments":{"vertices":32,"radius1":1.0,"radius2":0.0,"depth":2.0,"location":[0,0,0],"name":"MyCone"}}}
  ```
- blender-add-torus:
  ```json
  {"jsonrpc":"2.0","id":30,"method":"tools/call","params":{"name":"blender-add-torus","arguments":{"major_radius":1.0,"minor_radius":0.25,"major_segments":24,"minor_segments":16,"location":[0,0,0],"name":"MyTorus"}}}
  ```
- blender-duplicate-object:
  ```json
  {"jsonrpc":"2.0","id":31,"method":"tools/call","params":{"name":"blender-duplicate-object","arguments":{"name":"Cube","new_name":"Cube_copy","offset":[1,0,0]}}}
  ```
- blender-list-objects:
  ```json
  {"jsonrpc":"2.0","id":32,"method":"tools/call","params":{"name":"blender-list-objects","arguments":{}}}
  ```
- blender-get-object-info:
  ```json
  {"jsonrpc":"2.0","id":33,"method":"tools/call","params":{"name":"blender-get-object-info","arguments":{"name":"Cube"}}}
  ```
- blender-select-object:
  ```json
  {"jsonrpc":"2.0","id":34,"method":"tools/call","params":{"name":"blender-select-object","arguments":{"names":["Cube","Sphere"]}}}
  ```
- blender-add-camera:
  ```json
  {"jsonrpc":"2.0","id":35,"method":"tools/call","params":{"name":"blender-add-camera","arguments":{"location":[0,0,10],"rotation":[-90,0,0],"name":"Cam"}}}
  ```
- blender-add-light:
  ```json
  {"jsonrpc":"2.0","id":36,"method":"tools/call","params":{"name":"blender-add-light","arguments":{"type":"sun","power":2.0,"location":[0,0,5],"rotation":[-45,0,0],"name":"KeyLight"}}}
  ```
- blender-assign-material:
  ```json
  {"jsonrpc":"2.0","id":37,"method":"tools/call","params":{"name":"blender-assign-material","arguments":{"object":"Cube","material":"LampMat","slot":0,"create_slot":true}}}
  ```
- blender-set-shading:
  ```json
  {"jsonrpc":"2.0","id":38,"method":"tools/call","params":{"name":"blender-set-shading","arguments":{"name":"Cube","mode":"smooth"}}}
  ```
- blender-delete-all:
  ```json
  {"jsonrpc":"2.0","id":39,"method":"tools/call","params":{"name":"blender-delete-all","arguments":{"confirm":"DELETE_ALL"}}}
  ```
- blender-reset-transform:
  ```json
  {"jsonrpc":"2.0","id":40,"method":"tools/call","params":{"name":"blender-reset-transform","arguments":{"name":"Cube"}}}
  ```
- blender-get-mesh-stats:
  ```json
  {"jsonrpc":"2.0","id":41,"method":"tools/call","params":{"name":"blender-get-mesh-stats","arguments":{"name":"Cube"}}}
  ```
- blender-extrude:
  ```json
  {"jsonrpc":"2.0","id":42,"method":"tools/call","params":{"name":"blender-extrude","arguments":{"name":"Cube","mode":"faces","distance":0.1}}}
  ```
- blender-inset:
  ```json
  {"jsonrpc":"2.0","id":43,"method":"tools/call","params":{"name":"blender-inset","arguments":{"name":"Cube","thickness":0.02}}}
  ```
- blender-loop-cut:
  ```json
  {"jsonrpc":"2.0","id":44,"method":"tools/call","params":{"name":"blender-loop-cut","arguments":{"name":"Cube","cuts":2,"position":0.5}}}
  ```
- blender-bevel-edges:
  ```json
  {"jsonrpc":"2.0","id":45,"method":"tools/call","params":{"name":"blender-bevel-edges","arguments":{"name":"Cube","width":0.05,"segments":2}}}
  ```
- blender-add-modifier:
  ```json
  {"jsonrpc":"2.0","id":46,"method":"tools/call","params":{"name":"blender-add-modifier","arguments":{"name":"Cube","type":"array","settings":{"count":2,"relative_offset":[1,0,0]}}}}
  ```
- blender-apply-modifier:
  ```json
  {"jsonrpc":"2.0","id":47,"method":"tools/call","params":{"name":"blender-apply-modifier","arguments":{"name":"Cube","modifier":"Array"}}}
  ```
- blender-boolean:
  ```json
  {"jsonrpc":"2.0","id":48,"method":"tools/call","params":{"name":"blender-boolean","arguments":{"name":"Cube","cutter":"Cutter","operation":"union","apply":true}}}
  ```

Debugging:
- `GET http://127.0.0.1:8765/debug` returns timer tick/queue stats.

## Troubleshooting
- Ensure nothing else binds `127.0.0.1:8765`; restart Blender after bridge crashes.
- If calls fail, check OS firewall rules for Blender and port 8765.
- Server stdout must be JSON-RPC NDJSON only; any stray prints break the client.
- Confirm `python -u D:\v3\scripts\mcp_stdio_server.py` starts without errors and exits when stdin closes.
- Bridge errors stay in Blender console; restart bridge if it stops responding.
