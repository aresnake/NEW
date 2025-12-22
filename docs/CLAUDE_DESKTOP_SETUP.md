# Claude Desktop + Blender Bridge

## Claude Desktop MCP entry
Add to your Claude Desktop `mcpServers`:
```json
{
  "command": "python",
  "args": ["-u", "D:\\v3\\scripts\\mcp_stdio_server.py"]
}
```

## Run the Blender bridge
- Blender UI:
  ```powershell
  & "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --factory-startup --python D:\v3\bridge\blender_bridge.py
  ```
- Headless:
  ```powershell
  & "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b --factory-startup --python D:\v3\bridge\blender_bridge.py
  ```

## Troubleshooting
- Ensure nothing else binds `127.0.0.1:8765`; restart Blender after bridge crashes.
- If calls fail, check OS firewall rules for Blender and port 8765.
- Server stdout must be JSON-RPC NDJSON only; any stray prints break the client.
- Confirm `python -u D:\v3\scripts\mcp_stdio_server.py` starts without errors and exits when stdin closes.
- Bridge errors stay in Blender console; restart bridge if it stops responding.
