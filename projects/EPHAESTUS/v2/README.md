# Hephaestus MCP v2

## Vision
Serveur MCP Blender officiel, robuste, multi-LLM, installable en 1 minute.

## Quickstart (dev)
```powershell
cd v2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
hephaestus-mcp
```

## Architecture
- `v2/src/hephaestus_mcp`: serveur MCP + registry d'outils
- `v2/bridge`: transport TCP (bridge server dev + mock)
- `v2/addon`: addon Blender (stub)
- `v2/shared`: types + config (stub)
- `v2/docs`: specs, install, API
- `v2/docs/COMPLIANCE.md`: règles JSON-RPC/MCP strictes
- `v2/docs/CLIENTS.md`: configs clients (Claude, Codex, Smithery/Ollama)

## MCP compliance
- `initialize`, `listTools`, `callTool`
- JSON-RPC 2.0 strict
- stdout reserve au protocole MCP
- logs sur stderr ou fichier
