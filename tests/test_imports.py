def test_import_package():
    import new_mcp  # noqa: F401

def test_toolresult_shapes():
    from new_mcp.contracts import ToolResult
    ok = ToolResult.success({"x": 1})
    assert ok.ok is True
    bad = ToolResult.failure("invalid_input", "nope")
    assert bad.ok is False
    assert bad.error_code == "invalid_input"
