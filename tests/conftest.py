import os
import pytest

@pytest.fixture(autouse=True)
def _isolate_tool_request_store(tmp_path, monkeypatch):
    # isolate tool_requests store for every test session
    monkeypatch.setenv("TOOL_REQUEST_DATA_DIR", str(tmp_path / "tool_requests_store"))
