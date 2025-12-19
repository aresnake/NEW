import pytest

from hephaestus_mcp.shared.errors import SchemaValidationError, UnknownTool
from hephaestus_mcp.tools.registry import validate_arguments


def test_validate_arguments_success():
    assert validate_arguments("object.delete", {"name": "Cube"}) == {"name": "Cube"}


def test_validate_arguments_missing_required():
    with pytest.raises(SchemaValidationError):
        validate_arguments("object.delete", {})


def test_validate_unknown_tool():
    with pytest.raises(UnknownTool):
        validate_arguments("unknown.tool", {})
