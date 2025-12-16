from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

JsonDict = Dict[str, Any]


# Canonical error/refusal codes (stable surface)
ERR_INVALID_INPUT = "invalid_input"
ERR_NOT_FOUND = "not_found"
ERR_CAPABILITY_MISSING = "capability_missing"
ERR_TIMEOUT = "timeout"
ERR_REFUSED = "refused"
ERR_INTERNAL = "internal_error"


@dataclass
class ToolResult:
    ok: bool
    data: Optional[JsonDict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    determinism_class: str = "deterministic"

    @staticmethod
    def success(data: JsonDict, determinism_class: str = "deterministic") -> "ToolResult":
        return ToolResult(ok=True, data=data, determinism_class=determinism_class)

    @staticmethod
    def failure(code: str, message: str, determinism_class: str = "deterministic") -> "ToolResult":
        return ToolResult(ok=False, error_code=code, error_message=message, determinism_class=determinism_class)
