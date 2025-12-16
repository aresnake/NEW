from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Callable, List

from .contracts import ToolResult

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


def _find_blender_exe() -> str:
    # Priority: env override
    env = os.environ.get("BLENDER_EXE", "").strip()
    if env and Path(env).exists():
        return str(Path(env).resolve())

    # Common paths (match your known installs)
    c1 = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    if Path(c1).exists():
        return str(Path(c1).resolve())

    c2 = r"D:\Blender_5.0.0_Portable\blender.exe"
    if Path(c2).exists():
        return str(Path(c2).resolve())

    raise FileNotFoundError("BLENDER_EXE not found. Set env BLENDER_EXE to your blender.exe path.")


def _extract_last_json_line(stdout: str) -> JsonDict:
    # Blender may append lines like "Blender quit" after our JSON.
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.endswith("\\n"):
            ln = ln[:-2]
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise ValueError("No JSON object line found in Blender stdout.")


def tool_scene_snapshot(params: JsonDict) -> ToolResult:
    """
    Launch Blender headless and return a Scene Snapshot v1 (as dict).

    Params (optional):
      - timeout_sec: int (default 90)
    """
    timeout_sec = params.get("timeout_sec", 90)
    if not isinstance(timeout_sec, int) or timeout_sec < 5 or timeout_sec > 600:
        return ToolResult.failure("invalid_input", "timeout_sec must be an int between 5 and 600")

    root = Path(__file__).resolve().parents[2]  # repo root
    script = root / "bridge" / "blender_snapshot.py"
    if not script.exists():
        return ToolResult.failure("not_found", f"missing blender script: {script}")

    try:
        blender = _find_blender_exe()
    except Exception as e:
        return ToolResult.failure("capability_missing", f"Blender not available: {e}")

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
        msg = (
            f"Blender failed (code={p.returncode}). "
            f"STDERR tail: {p.stderr.strip()[-800:]}"
        )
        return ToolResult.failure("internal_error", msg)

    try:
        snap = _extract_last_json_line(p.stdout)
    except Exception as e:
        tail = "\n".join([ln for ln in p.stdout.splitlines() if ln.strip()][-30:])
        return ToolResult.failure("internal_error", f"Could not parse snapshot JSON: {e}. STDOUT tail:\n{tail}")

    # Basic sanity check against our schema expectations
    if snap.get("version") != "scene_state_v1":
        return ToolResult.failure("internal_error", f"Unexpected snapshot version: {snap.get('version')}")

    return ToolResult.success({"snapshot": snap})


TOOLS: dict[str, Callable[[JsonDict], ToolResult]] = {
    "system.ping": tool_system_ping,
    "schemas.get": tool_schemas_get,
    "scene.snapshot": tool_scene_snapshot,
}
