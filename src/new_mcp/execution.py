from __future__ import annotations

from typing import Any, Dict, Callable

from .contracts import (
    ToolResult,
    ERR_INVALID_INPUT,
    ERR_REFUSED,
    ERR_INTERNAL,
)

JsonDict = Dict[str, Any]


def run_enveloped(
    *,
    tool_name: str,
    tool_params: JsonDict,
    tools: Dict[str, Callable[[JsonDict], ToolResult]],
    contract: JsonDict,
) -> ToolResult:
    """
    Execution Model v1 (minimal):
      1) validate presence
      2) capability / policy gate (minimal today)
      3) execute tool
      4) verify stub (future)
      5) return envelope
    """
    # 1) Validate
    if not isinstance(tool_name, str) or not tool_name:
        return ToolResult.failure(ERR_INVALID_INPUT, "tool_name must be a non-empty string")
    if not isinstance(tool_params, dict):
        return ToolResult.failure(ERR_INVALID_INPUT, "tool_params must be an object")
    if tool_name not in tools:
        return ToolResult.failure(ERR_INVALID_INPUT, f"unknown tool: {tool_name}")

    # 2) Capability / policy gate (minimal)
    policy = (contract or {}).get("policy", {})
    allowed_modes = set(policy.get("allowed_safety_modes", []))
    # Today: all registered tools are headless_safe
    if allowed_modes and "headless_safe" not in allowed_modes:
        return ToolResult.failure(ERR_REFUSED, "tool blocked by policy")

    # 3) Execute
    try:
        result = tools[tool_name](tool_params)
    except Exception as e:  # noqa: BLE001
        return ToolResult.failure(ERR_INTERNAL, f"execution failed: {e}")

    # 4) Verify stub (future)
    # Placeholder for snapshot verification / determinism checks.

    # 5) Return
    return result
