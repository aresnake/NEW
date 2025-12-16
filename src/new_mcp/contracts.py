from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

SafetyMode = Literal["headless_safe", "ui_assisted", "unsafe_ops"]
DeterminismClass = Literal["deterministic", "seeded", "nondeterministic"]


@dataclass(frozen=True)
class ToolMeta:
    name: str
    safety_mode: SafetyMode = "headless_safe"
    determinism_class: DeterminismClass = "deterministic"
    description: str = ""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    determinism_class: DeterminismClass = "deterministic"
    seed: Optional[int] = None
    tolerance: Optional[float] = None

    @staticmethod
    def success(data: Any = None, *, determinism_class: DeterminismClass = "deterministic", seed: int | None = None, tolerance: float | None = None) -> "ToolResult":
        return ToolResult(ok=True, data=data, determinism_class=determinism_class, seed=seed, tolerance=tolerance)

    @staticmethod
    def failure(code: str, message: str) -> "ToolResult":
        return ToolResult(ok=False, error_code=code, error_message=message)
