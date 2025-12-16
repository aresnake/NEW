from __future__ import annotations

"""
Minimal JSON-RPC 2.0 stdio server for MCP-style tooling.

Design goals:
- Headless-first, deterministic
- Windows-safe stdio (no fancy buffering tricks)
- Two modes:
    - serve_forever(): long-lived stdio server
    - serve_once(): read 1 request, write 1 response, exit (tests / CI)
- No dependency on OpenAI / Claude SDKs
"""

import json
import sys
from dataclasses import asdict
from typing import Any, Dict, Callable

from .contracts import ToolResult

JsonDict = Dict[str, Any]


class StdioJsonRpcServer:
    def __init__(self, methods: dict[str, Callable[[JsonDict], JsonDict]]):
        """
        methods: dict mapping method_name -> callable(params) -> JsonDict
        """
        self._methods = methods

    # -------------------------
    # Public entrypoints
    # -------------------------

    def serve_forever(self) -> None:
        """Long-lived stdio loop (production / MCP host)."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            resp = self._handle_safe_line(line)
            self._write_response(resp)

    def serve_once(self) -> None:
        """
        Single-shot mode:
        - read exactly one non-empty line
        - write exactly one response
        - exit immediately

        Used for tests and CI to avoid hanging subprocesses.
        """
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            resp = self._handle_safe_line(line)
            self._write_response(resp)
            return

    # -------------------------
    # Internal helpers
    # -------------------------

    def _handle_safe_line(self, line: str) -> JsonDict:
        try:
            req = json.loads(line)
            return self._handle_request(req)
        except Exception as e:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"internal_error: {e}",
                },
            }

    def _handle_request(self, req: JsonDict) -> JsonDict:
        if req.get("jsonrpc") != "2.0":
            return self._error(req.get("id"), -32600, "invalid_request")

        method = req.get("method")
        params = req.get("params") or {}
        rpc_id = req.get("id")

        if not isinstance(method, str) or method not in self._methods:
            return self._error(rpc_id, -32601, "method_not_found")

        if not isinstance(params, dict):
            return self._error(rpc_id, -32602, "invalid_params")

        result = self._methods[method](params)
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": result,
        }

    def _error(self, rpc_id: Any, code: int, message: str) -> JsonDict:
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _write_response(self, resp: JsonDict) -> None:
        # Always write exactly one JSON object per line
        sys.stdout.write(json.dumps(resp, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stdout.flush()


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------

def toolresult_to_json(tr: ToolResult) -> JsonDict:
    """
    Convert ToolResult dataclass to a compact JSON-serializable dict.
    None fields are stripped to keep payloads clean.
    """
    data = asdict(tr)
    return {k: v for k, v in data.items() if v is not None}
