import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_rpc(req: dict, timeout: int = 5) -> dict:
    p = subprocess.Popen(
        [sys.executable, "-m", "new_mcp", "--once"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p.stdin and p.stdout and p.stderr
    out, err = p.communicate(json.dumps(req) + "\n", timeout=timeout)
    assert err.strip() == ""
    return json.loads(out.strip().splitlines()[-1])


def _blender_available() -> bool:
    env = os.environ.get("BLENDER_EXE", "").strip()
    if env and Path(env).exists():
        return True
    c1 = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
    c2 = Path(r"D:\Blender_5.0.0_Portable\blender.exe")
    return c1.exists() or c2.exists()


def test_system_ping():
    resp = run_rpc({"jsonrpc": "2.0", "id": 1, "method": "system.ping", "params": {"message": "yo"}})
    assert resp["id"] == 1
    assert resp["result"]["ok"] is True
    assert resp["result"]["data"]["reply"] == "pong"


def test_schemas_get_not_found():
    resp = run_rpc({"jsonrpc": "2.0", "id": 2, "method": "schemas.get", "params": {"name": "nope.md"}})
    assert resp["id"] == 2
    assert resp["result"]["ok"] is False
    assert resp["result"]["error_code"] == "not_found"


def test_scene_snapshot_smoke():
    if not _blender_available():
        pytest.skip("Blender not available on this machine (set BLENDER_EXE to enable).")

    resp = run_rpc(
        {"jsonrpc": "2.0", "id": 3, "method": "scene.snapshot", "params": {"timeout_sec": 120}},
        timeout=130,
    )
    assert resp["id"] == 3
    assert resp["result"]["ok"] is True
    snap = resp["result"]["data"]["snapshot"]
    assert snap["version"] == "scene_state_v1"
    assert "objects" in snap and isinstance(snap["objects"], list)
