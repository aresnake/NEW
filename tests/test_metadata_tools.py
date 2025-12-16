import json
import subprocess
import sys


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


def test_tools_list_contains_scene_snapshot():
    resp = run_rpc({"jsonrpc": "2.0", "id": 10, "method": "tools.list", "params": {} })
    assert resp["id"] == 10
    assert resp["result"]["ok"] is True
    tools = resp["result"]["data"]["tools"]
    names = {t["name"] for t in tools}
    assert "scene.snapshot" in names
    assert "contract.get" in names
    assert "runtime.capabilities" in names


def test_runtime_capabilities_shape():
    resp = run_rpc({"jsonrpc": "2.0", "id": 11, "method": "runtime.capabilities", "params": {} })
    assert resp["id"] == 11
    assert resp["result"]["ok"] is True
    data = resp["result"]["data"]
    assert "python" in data and "os" in data and "blender" in data
    assert isinstance(data["blender"]["available"], bool)


def test_contract_get_minimal():
    resp = run_rpc(
        {"jsonrpc": "2.0", "id": 12, "method": "contract.get", "params": {"requested_determinism": "deterministic", "timeout_sec": 90}},
        timeout=10,
    )
    assert resp["id"] == 12
    assert resp["result"]["ok"] is True
    c = resp["result"]["data"]["contract"]
    assert c["version"] == "contract_v0"
    assert c["requested_determinism"] == "deterministic"
    assert isinstance(c["tools"], list)
