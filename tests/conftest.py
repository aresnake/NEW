import pytest

@pytest.fixture(autouse=True)
def _isolate_tool_request_store(tmp_path, monkeypatch):
    # isolate tool_requests store for every test session
    monkeypatch.setenv("TOOL_REQUEST_DATA_DIR", str(tmp_path / "tool_requests_store"))
    # silence warnings in most tests (tests that need warnings can unset it)
    monkeypatch.setenv("BLENDER_MCP_SILENCE_TOOL_REQUEST_WARNINGS", "1")
