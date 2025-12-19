#!/usr/bin/env python3
"""Test MCP server startup"""
import sys
import traceback

try:
    print("Python executable:", sys.executable, file=sys.stderr)
    print("Python version:", sys.version, file=sys.stderr)
    print("Importing hephaestus.server...", file=sys.stderr)

    from hephaestus import server

    print("Import successful!", file=sys.stderr)
    print("Server app:", server.app, file=sys.stderr)
    print("Calling main()...", file=sys.stderr)

    server.main()

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
