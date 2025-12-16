import json
import os
import subprocess
from pathlib import Path


def _find_blender_exe() -> str:
    env = os.environ.get("BLENDER_EXE", "").strip()
    if env and Path(env).exists():
        return str(Path(env).resolve())

    c1 = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    if Path(c1).exists():
        return str(Path(c1).resolve())

    c2 = r"D:\Blender_5.0.0_Portable\blender.exe"
    if Path(c2).exists():
        return str(Path(c2).resolve())

    raise RuntimeError("BLENDER_EXE not found. Set env BLENDER_EXE to your blender.exe path.")


def _extract_last_json_line(stdout: str) -> dict:
    """
    Blender often prints trailer lines like 'Blender quit'.
    Our snapshot JSON is one full line. We scan from bottom for a JSON object line.
    """
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        # tolerate literal "\n" suffix if any toolchain echoes it
        if ln.endswith("\\n"):
            ln = ln[:-2]
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise RuntimeError(f"No JSON object line found in stdout. Tail:\n{lines[-20:] if lines else lines}")


def _run_blender_snapshot() -> dict:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "bridge" / "blender_snapshot.py"
    blender = _find_blender_exe()

    if not script.exists():
        raise RuntimeError(f"Missing blender script: {script}")

    p = subprocess.run(
        [blender, "--background", "--factory-startup", "--python", str(script)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=90,
    )

    if p.returncode != 0:
        raise RuntimeError(
            f"Blender failed ({p.returncode}).\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )

    try:
        return _extract_last_json_line(p.stdout)
    except Exception as e:
        raise RuntimeError(
            f"Could not parse JSON snapshot. Error: {e}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        ) from e


def test_blender_snapshot_v1_minimal_shape():
    snap = _run_blender_snapshot()

    assert snap["version"] == "scene_state_v1"
    assert "blender" in snap and "scene" in snap and "objects" in snap

    blender = snap["blender"]
    assert isinstance(blender.get("version_string"), str)
    assert isinstance(blender.get("version_tuple"), list)
    assert blender.get("headless") is True

    scene = snap["scene"]
    assert isinstance(scene.get("name"), str)
    assert isinstance(scene.get("frame_current"), int)
    assert isinstance(scene.get("unit_settings"), dict)

    objects = snap["objects"]
    assert isinstance(objects, list)
    assert len(objects) >= 1

    # Canonical ordering: (type, name) sorted
    keys = [(o.get("type"), o.get("name")) for o in objects]
    assert keys == sorted(keys)

    # Minimal envelope
    o0 = objects[0]
    assert isinstance(o0.get("name"), str)
    assert isinstance(o0.get("type"), str)
    tr = o0.get("transform")
    assert isinstance(tr, dict)
    assert "location" in tr and "scale" in tr
    vis = o0.get("visibility")
    assert isinstance(vis, dict)
    assert isinstance(vis.get("hide_render"), bool)
    assert isinstance(vis.get("hide_viewport"), bool)
