# Clients MCP supportés

Configurations rapides pour brancher Hephaestus MCP v2 sur différents clients. Remplace les chemins si nécessaire.

## Claude Desktop (Chat/Code)
`claude_desktop_config.json` :
```json
{
  "mcpServers": {
    "hephaestus": {
      "command": "uvx",
      "args": ["--from", ".", "hephaestus-mcp"],
      "env": { "HEPHAESTUS_CONFIG": "D:\\\\EPHAESTUS\\\\v2\\\\config.json" },
      "cwd": "D:\\\\EPHAESTUS\\\\v2"
    }
  }
}
```

## VS Code + Codex
`settings.json` :
```json
"codex.mcpServers": [
  {
    "id": "hephaestus",
    "command": "uvx",
    "args": ["--from", ".", "hephaestus-mcp"],
    "cwd": "D:\\\\EPHAESTUS\\\\v2",
    "env": { "HEPHAESTUS_CONFIG": "D:\\\\EPHAESTUS\\\\v2\\\\config.json" }
  }
]
```

## Smithery / Ollama (CLI)
Exemple `smithery.json` :
```json
{
  "mcpServers": {
    "hephaestus": {
      "command": "uvx",
      "args": ["--from", ".", "hephaestus-mcp"],
      "cwd": "D:\\\\EPHAESTUS\\\\v2"
    }
  },
  "models": {
    "default": { "provider": "ollama", "model": "qwen2.5:14b" }
  }
}
```

## Checks rapides
- `initialize` → `listTools` → `callTool` `ping` doit répondre `pong`.
- Paramètres invalides doivent renvoyer une erreur de validation lisible.
- Si l’addon/bridge est éteint, les tools Blender renvoient `bridge_unavailable`.
