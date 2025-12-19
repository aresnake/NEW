import asyncio
import json
import socket
import struct
import threading
from typing import Iterator

import pytest

from hephaestus_mcp import server
from hephaestus_mcp.bridge.client import BridgeClient
from hephaestus_mcp.shared.config import BridgeConfig
from hephaestus_mcp.shared.errors import ToolExecutionError


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


@pytest.fixture
def mock_bridge_server() -> Iterator[tuple[str, int]]:
    """TCP bridge that echoes tool/args after handshake."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    host, port = server_sock.getsockname()
    stop_event = threading.Event()

    def _serve() -> None:
        server_sock.listen(1)
        server_sock.settimeout(5)
        try:
            conn, _ = server_sock.accept()
        except OSError:
            return
        with conn:
            # Handshake
            header = _recv_exact(conn, 4)
            if len(header) != 4:
                return
            (size,) = struct.unpack("!I", header)
            raw = _recv_exact(conn, size)
            try:
                json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return
            handshake_resp = json.dumps({"ok": True, "version": "1.0"}).encode("utf-8")
            conn.sendall(struct.pack("!I", len(handshake_resp)) + handshake_resp)

            # Calls
            while not stop_event.is_set():
                header = _recv_exact(conn, 4)
                if len(header) != 4:
                    break
                (size,) = struct.unpack("!I", header)
                raw = _recv_exact(conn, size)
                if not raw:
                    break
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    break
                if msg.get("type") != "call":
                    break
                response = {
                    "ok": True,
                    "result": {"echo_tool": msg.get("tool"), "args": msg.get("args")},
                }
                encoded = json.dumps(response).encode("utf-8")
                conn.sendall(struct.pack("!I", len(encoded)) + encoded)
        server_sock.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        stop_event.set()
        server_sock.close()
        thread.join(timeout=1)


@pytest.fixture(autouse=True)
def reset_bridge() -> Iterator[None]:
    """Ensure bridge client is fresh per test."""
    server.bridge = BridgeClient()
    yield
    server.bridge = BridgeClient()


@pytest.mark.asyncio
async def test_list_tools_contains_ping() -> None:
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert "ping" in names


@pytest.mark.asyncio
async def test_ping_returns_pong() -> None:
    result = await server.ping()
    assert result and result[0].text == "pong"


@pytest.mark.asyncio
async def test_schema_validation_error_is_raised() -> None:
    with pytest.raises(ToolExecutionError):
        await server.object_transform(name="Cube", location=[0.0, 1.0])  # minItems=3


@pytest.mark.asyncio
async def test_bridge_unavailable_raises() -> None:
    with pytest.raises(ToolExecutionError):
        await server.scene_get_info()


@pytest.mark.asyncio
async def test_bridge_call_succeeds_with_mock(mock_bridge_server: tuple[str, int]) -> None:
    host, port = mock_bridge_server
    server.bridge = BridgeClient(
        BridgeConfig(transport="tcp", host=host, port=port, timeout_ms=2000)
    )
    server.bridge.connect()

    result = await server.object_create_primitive("cube", name="Box", location=[0.0, 0.0, 0.0])
    assert result
    text_payload = result[0].text
    assert "object.create_primitive" in text_payload
    assert "Box" in text_payload
