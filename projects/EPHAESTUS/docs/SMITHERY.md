# Using Hephaestus with Smithery (other LLMs)

You can drive Hephaestus without Claude Desktop by using either:
- A simple OpenAI function-calling client (`scripts/openai_tool_client.py`)
- [Smithery](https://github.com/jlowin/smithery) if you want to build your own MCP client/server.

## Setup
### Option A — OpenAI/compatible function-calling client (fastest)
1) `pip install openai`
2) Start Blender addon (Start Hephaestus Server on port 9876).
3) In one terminal: `.\.venv\Scripts\python main.py` (MCP server not required for this client, but safe to keep running).
4) In another terminal: set your endpoint/key/model, then run the client:
   - OpenAI payant :
     ```pwsh
     $env:OPENAI_API_KEY="REPLACE_ME_DO_NOT_COMMIT"
     python scripts/openai_tool_client.py
     ```
   - Gratuit/local (ollama avec API OpenAI-compatible) :
     ```pwsh
     $env:OPENAI_BASE_URL="http://localhost:11434/v1"
     $env:OPENAI_API_KEY="ollama"
     $env:OPENAI_MODEL="llama3.1"   # ou un modèle dispo dans ollama
     python scripts/openai_tool_client.py
     ```
5) Prompt naturellement (ex: “Create a cube at 0,0,0 and apply the concrete preset”).

### Option B — Smithery (build your own MCP client)
1) Install Smithery: `pip install smithery`
2) Create `smithery.json` in `D:\EPHAESTUS` (example: `smithery.example.json`)
   - For OpenAI: set `provider` to `openai`, set `model` and `api_key`.
   - For ollama: use
   ```json
   "llm": { "provider": "ollama", "base_url": "http://localhost:11434", "model": "llama3" }
   ```
3) Start Blender addon (Start Hephaestus Server on port 9876).
4) Start MCP server from the repo: `.\.venv\Scripts\python main.py` (or `uvx --from . hephaestus`).
5) Build your own thin client that reads `smithery.json` and routes tool calls to Hephaestus (Smithery itself doesn’t ship a chat REPL).

## Quick prompts to test
- “Create a cube named Cube01 and apply the concrete material preset.”
- “Apply the three_point lighting preset and set a camera with the product preset.”
- “Add a cylinder through the cube and run a boolean difference on the cube with the cylinder.”
