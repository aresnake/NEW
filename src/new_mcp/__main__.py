from __future__ import annotations

import sys

from .mcp_stdio_server import StdioJsonRpcServer, toolresult_to_json
from .tool_registry import TOOLS


def _wrap_tools():
    methods = {}
    for name, fn in TOOLS.items():

        def _make(f):
            return lambda params, _f=f: toolresult_to_json(_f(params))

        methods[name] = _make(fn)
    return methods


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    once = "--once" in argv

    server = StdioJsonRpcServer(_wrap_tools())
    if once:
        server.serve_once()
    else:
        server.serve_forever()


if __name__ == "__main__":
    main()
