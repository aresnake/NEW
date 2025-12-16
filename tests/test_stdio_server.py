import json
import subprocess
import sys


def run_rpc(req: dict) -> dict:
    """
    Windows-safe single-shot RPC call:
    - spawn server in --once mode
    - write 1 JSON line
    - read 1 JSON line
    - hard kill in finally to avoid any hang
    """
    p = subprocess.Popen(
        [sys.executable, "-m", "new_mcp", "--once"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p.stdin and p.stdout and p.stderr

    try:
        p.stdin.write(json.dumps(req) + "\n")
        p.stdin.flush()

        line = p.stdout.readline()
        err = p.stderr.read()

        # If something goes wrong, show stderr directly
        assert err.strip() == "", f"stderr was not empty:\n{err}"

        line = line.strip()

        # Some terminals/platforms can surface a literal "\n" suffix; tolerate it.
        if line.endswith("\\n"):
            line = line[:-2]

        return json.loads(line)

    finally:
        try:
            p.kill()
        except Exception:
            pass


def test_system_ping():
    resp = run_rpc(
        {"jsonrpc": "2.0", "id": 1, "method": "system.ping", "params": {"message": "yo"}}
    )
    assert resp["id"] == 1
    assert resp["result"]["ok"] is True
    assert resp["result"]["data"]["reply"] == "pong"
    assert resp["result"]["data"]["echo"] == "yo"


def test_schemas_get_not_found():
    resp = run_rpc(
        {"jsonrpc": "2.0", "id": 2, "method": "schemas.get", "params": {"name": "nope.md"}}
    )
    assert resp["id"] == 2
    assert resp["result"]["ok"] is False
    assert resp["result"]["error_code"] == "not_found"
