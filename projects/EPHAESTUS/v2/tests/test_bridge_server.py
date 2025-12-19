import time

import pytest

from bridge.server import BridgeServer, default_handlers
from hephaestus_mcp.bridge.client import BridgeClient
from hephaestus_mcp.shared.config import BridgeConfig
from hephaestus_mcp.shared.errors import BridgeUnavailable


def test_bridge_server_handshake_and_call():
    server = BridgeServer(host="127.0.0.1", port=0, token=None, handlers=default_handlers())
    host, port = server.start()

    client = BridgeClient(BridgeConfig(transport="tcp", host=host, port=port, timeout_ms=2000))
    client.connect()
    payload = client.call("ping", {})
    assert payload.get("pong") is True

    server.stop()


def test_bridge_server_rejects_bad_token():
    server = BridgeServer(host="127.0.0.1", port=0, token="secret", handlers=default_handlers())
    host, port = server.start()

    client = BridgeClient(BridgeConfig(transport="tcp", host=host, port=port, timeout_ms=2000, token="wrong"))
    with pytest.raises(BridgeUnavailable):
        client.connect()

    server.stop()
