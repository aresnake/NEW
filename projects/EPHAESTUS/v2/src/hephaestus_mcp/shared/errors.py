from __future__ import annotations


class HephaestusError(Exception):
    code = "hephaestus_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BridgeUnavailable(HephaestusError):
    code = "bridge_unavailable"


class ToolExecutionError(HephaestusError):
    code = "tool_execution_error"


class UnknownTool(HephaestusError):
    code = "unknown_tool"


class SchemaValidationError(HephaestusError):
    code = "schema_validation_error"
