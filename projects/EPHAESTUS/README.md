# Hephaestus - Advanced Blender MCP

> Named after the Greek god of forge and creation, Hephaestus is THE reference MCP for Blender + LLM workflows.

## Overview

Hephaestus is a Model Context Protocol (MCP) server that enables Large Language Models to control Blender through a comprehensive set of high-level, mid-level, and low-level tools. It bridges the gap between AI and 3D creation with an intuitive, layered architecture.

## Features

- **100+ Tools**: Comprehensive coverage of Blender operations
- **Layered Approach**:
  - High-level macros for quick complex setups
  - Mid-level tools for common operations
  - Low-level code execution for flexibility
- **Preset System**: Studio lighting, materials, camera rigs ready to use
- **Production-Ready**: Geometry nodes, modifiers, animation, rendering
- **LLM-Optimized**: Designed for natural language workflows

## Architecture

Hephaestus consists of two components:

1. **Blender Addon** (`addon.py`): Runs inside Blender, listens for commands via socket
2. **MCP Server** (`src/hephaestus/`): FastMCP-based server that translates LLM requests to Blender commands

Communication happens via JSON over a local socket (default: `localhost:9876`)

```
LLM (Claude) → MCP Server → Socket → Blender Addon → Blender Python API
```

## Quick Start

### Installation

```bash
# Install the MCP server
pip install uv
uv pip install -e .
```

### Blender Setup

1. Open Blender (3.0+)
2. Edit → Preferences → Add-ons → Install
3. Select `addon.py`
4. Enable "Hephaestus MCP"
5. Open sidebar (N key) → Hephaestus tab
6. Click "Start Hephaestus Server"

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hephaestus": {
      "command": "uvx",
      "args": ["hephaestus"]
    }
  }
}
```

## Example Usage

```
User: "Create a product showcase for a luxury watch"

Claude:
✓ Camera created with isometric view
✓ Three-point lighting applied
✓ Floor plane added with reflective material
✓ Render settings configured for high quality

User: "Add a concrete material to the base"

Claude:
✓ Material "Concrete" created with preset
✓ Assigned to object "Base"
```

## Use with other LLMs (no Claude quotas)
- Any MCP-capable client works. Example with Smithery (CLI):
  1. `pip install smithery`
  2. Create `smithery.json` (see `smithery.example.json`)
  3. Start Blender addon, then run the MCP server: `uvx --from . hephaestus` (or `python main.py`)
  4. Chat: `smithery chat --config smithery.json`

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest tests/

# Run MCP server directly
python main.py
```

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [API Reference](docs/API.md)
- [Tools List](docs/TOOLS_LIST.md)
- [Examples](docs/EXAMPLES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Smithery (other LLMs)](docs/SMITHERY.md)

## License

MIT License - See LICENSE file

## Credits

Built with [FastMCP](https://github.com/jlowin/fastmcp) and love for 3D creation.
