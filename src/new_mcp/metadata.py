from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

JsonDict = Dict[str, Any]


# ---------- Tool metadata (discoverability) ----------

@dataclass(frozen=True)
class ToolMeta:
    name: str
    description: str
    determinism_class: str  # "deterministic" | "seeded" | "nondeterministic"
    safety_mode: str        # "headless_safe" | "ui_assisted" | "unsafe_ops"
    params_schema: JsonDict


def tool_meta_list() -> List[ToolMeta]:
    # Keep this list in sync with tool_registry.TOOLS keys.
    return [
        ToolMeta(
            name="system.ping",
            description="Ping the MCP server (returns pong).",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "additionalProperties": True,
            },
        ),
        ToolMeta(
            name="schemas.get",
            description="Return the content of a schema markdown file from /schemas.",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        ),
        ToolMeta(
            name="scene.snapshot",
            description="Run Blender headless and return a Scene Snapshot v1.",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={
                "type": "object",
                "properties": {"timeout_sec": {"type": "integer", "minimum": 5, "maximum": 600}},
                "additionalProperties": False,
            },
        ),
        ToolMeta(
            name="runtime.capabilities",
            description="Report runtime capabilities (python, OS, blender availability).",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolMeta(
            name="tools.list",
            description="List available tools with metadata (schemas, determinism, safety mode).",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolMeta(
            name="contract.get",
            description="Return a minimal session contract (v0) derived from environment and policy.",
            determinism_class="deterministic",
            safety_mode="headless_safe",
            params_schema={
                "type": "object",
                "properties": {
                    "requested_determinism": {"type": "string", "enum": ["deterministic", "seeded", "nondeterministic"]},
                    "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 600},
                },
                "additionalProperties": False,
            },
        ),
    ]


# ---------- Blender discovery ----------

def find_blender_exe() -> Optional[str]:
    env = os.environ.get("BLENDER_EXE", "").strip()
    if env and Path(env).exists():
        return str(Path(env).resolve())

    c1 = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    if Path(c1).exists():
        return str(Path(c1).resolve())

    c2 = r"D:\Blender_5.0.0_Portable\blender.exe"
    if Path(c2).exists():
        return str(Path(c2).resolve())

    return None


def probe_blender_version(blender_exe: str, timeout_sec: int = 15) -> Optional[str]:
    """
    Best-effort: try to run blender --version and parse the first line.
    """
    try:
        p = subprocess.run(
            [blender_exe, "--version"],
            capture_output=True,
            text=True,
            timeout=float(timeout_sec),
        )
        if p.returncode != 0:
            return None
        lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
        return lines[0] if lines else None
    except Exception:
        return None


# ---------- Contract (v0 minimal) ----------

def make_contract_v0(
    requested_determinism: str = "deterministic",
    timeout_sec: int = 90,
) -> JsonDict:
    """
    Minimal contract structure (v0) to prepare for future MCP-host negotiation.
    """
    blender_exe = find_blender_exe()
    blender_version = probe_blender_version(blender_exe) if blender_exe else None

    # Determinism policy: today we only guarantee deterministic tools in this repo baseline.
    if requested_determinism not in {"deterministic", "seeded", "nondeterministic"}:
        requested_determinism = "deterministic"

    contract: JsonDict = {
        "version": "contract_v0",
        "requested_determinism": requested_determinism,
        "timeout_sec": int(timeout_sec),
        "capabilities": {
            "headless_supported": True,
            "ui_supported": False,
            "blender_available": bool(blender_exe),
            "blender_exe": blender_exe,
            "blender_version": blender_version,
        },
        "policy": {
            "allowed_safety_modes": ["headless_safe"],
            "unsafe_ops_allowed": False,
        },
        "tools": [tm.name for tm in tool_meta_list()],
    }
    return contract


# ---------- Runtime capabilities ----------

def runtime_capabilities() -> JsonDict:
    blender_exe = find_blender_exe()
    blender_version = probe_blender_version(blender_exe) if blender_exe else None

    return {
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "os": {
            "platform": sys.platform,
        },
        "cwd": str(Path.cwd()),
        "env": {
            "BLENDER_EXE_set": bool(os.environ.get("BLENDER_EXE")),
        },
        "blender": {
            "available": bool(blender_exe),
            "exe": blender_exe,
            "version_string": blender_version,
            "headless_supported": True,
        },
    }


def tool_meta_json() -> List[JsonDict]:
    out: List[JsonDict] = []
    for tm in tool_meta_list():
        out.append(
            {
                "name": tm.name,
                "description": tm.description,
                "determinism_class": tm.determinism_class,
                "safety_mode": tm.safety_mode,
                "params_schema": tm.params_schema,
            }
        )
    return out


def dumps_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
