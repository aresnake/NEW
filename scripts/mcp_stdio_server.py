#!/usr/bin/env python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blender_mcp.server import StdioServer  # noqa: E402


def main() -> None:
    server = StdioServer()
    server.run()


if __name__ == "__main__":
    main()
