from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Callable

from .contracts import ToolResult
from .metadata import make_contract_v0, runtime_capabilities, tool_meta_json, find_blender_exe

JsonDict = Dict[str, Any]


def tool_system_ping(params: JsonDict) -> ToolResult:
    msg = params.get("message", "ping")
    return ToolResult.success({"reply": "pong", "echo": msg})


def tool_schemas_get(params: JsonDict) -> ToolResult:
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return ToolResult.failure("invalid_input", "name must be a non-empty string")
    root = Path(__file__).resolve().parents[2]  # repo root
    p = root / "schemas" / name
    if not p.exists() or not p.is_file():
        return ToolResult.failure("not_found", f"schema not found: {name}")
    text = p.read_text(encoding="utf-8")
    return ToolResult.success({"name": name, "content": text})


def _extract_last_json_line(stdout: str) -> JsonDict:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.endswith("\\n"):
            ln = ln[:-2]
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise ValueError("No JSON object line found in Blender stdout.")


def tool_scene_snapshot(params: JsonDict) -> ToolResult:
    timeout_sec = params.get("timeout_sec", 90)
    if not isinstance(timeout_sec, int) or timeout_sec < 5 or timeout_sec > 600:
        return ToolResult.failure("invalid_input", "timeout_sec must be an int between 5 and 600")

    root = Path(__file__).resolve().parents[2]  # repo root
    script = root / "bridge" / "blender_snapshot.py"
    if not script.exists():
        return ToolResult.failure("not_found", f"missing blender script: {script}")

    blender = find_blender_exe()
    if not blender:
        return ToolResult.failure("capability_missing", "Blender not available (set BLENDER_EXE or install Blender).")

    try:
        p = subprocess.run(
            [blender, "--background", "--factory-startup", "--python", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=float(timeout_sec),
        )
    except subprocess.TimeoutExpired:
        return ToolResult.failure("timeout", f"Blender snapshot exceeded timeout_sec={timeout_sec}")
    except Exception as e:
        return ToolResult.failure("internal_error", f"Failed to run Blender: {e}")

    if p.returncode != 0:
        msg = f"Blender failed (code={p.returncode}). STDERR tail: {p.stderr.strip()[-800:]}"
        return ToolResult.failure("internal_error", msg)

    try:
        snap = _extract_last_json_line(p.stdout)
    except Exception as e:
        tail = "\n".join([ln for ln in p.stdout.splitlines() if ln.strip()][-30:])
        return ToolResult.failure("internal_error", f"Could not parse snapshot JSON: {e}. STDOUT tail:\n{tail}")

    if snap.get("version") != "scene_state_v1":
        return ToolResult.failure("internal_error", f"Unexpected snapshot version: {snap.get('version')}")

    return ToolResult.success({"snapshot": snap})


def tool_runtime_capabilities(_: JsonDict) -> ToolResult:
    return ToolResult.success(runtime_capabilities())


def tool_tools_list(_: JsonDict) -> ToolResult:
    return ToolResult.success({"tools": tool_meta_json()})


def tool_contract_get(params: JsonDict) -> ToolResult:
    requested = params.get("requested_determinism", "deterministic")
    timeout_sec = params.get("timeout_sec", 90)

    if requested not in {"deterministic", "seeded", "nondeterministic"}:
        return ToolResult.failure("invalid_input", "requested_determinism must be deterministic|seeded|nondeterministic")
    if not isinstance(timeout_sec, int) or timeout_sec < 5 or timeout_sec > 600:
        return ToolResult.failure("invalid_input", "timeout_sec must be an int between 5 and 600")

    contract = make_contract_v0(requested_determinism=requested, timeout_sec=timeout_sec)
    return ToolResult.success({"contract": contract})


TOOLS: dict[str, Callable[[JsonDict], ToolResult]] = {
    "system.ping": tool_system_ping,
    "schemas.get": tool_schemas_get,
    "scene.snapshot": tool_scene_snapshot,
    "runtime.capabilities": tool_runtime_capabilities,
    "tools.list": tool_tools_list,
    "contract.get": tool_contract_get,
}
