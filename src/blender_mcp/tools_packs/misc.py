from typing import Any


def register(registry, _: Any, __: Any, ___: Any) -> None:  # noqa: ANN001
    reg = registry._register  # noqa: SLF001

    reg(
        "intent-resolve",
        "Resolve natural text to a tool call",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        registry._tool_intent_resolve,  # noqa: SLF001
    )
    reg(
        "intent-run",
        "Resolve natural text and run the resolved tool",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        registry._tool_intent_run,  # noqa: SLF001
    )
    reg(
        "replay-list",
        "List recent tool executions",
        {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
            "additionalProperties": False,
        },
        registry._tool_replay_list,  # noqa: SLF001
    )
    reg(
        "replay-run",
        "Re-run a previous tool execution by id",
        {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        registry._tool_replay_run,  # noqa: SLF001
    )
    reg(
        "model-start",
        "Start an observation session",
        {
            "type": "object",
            "properties": {"goal": {"type": "string"}, "constraints": {"type": "string"}},
            "required": ["goal"],
            "additionalProperties": False,
        },
        registry._tool_model_start,  # noqa: SLF001
    )
    reg(
        "model-step",
        "Record an observation step",
        {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "intent": {"type": "string"},
                "proposed_tool": {"type": "string"},
                "proposed_args": {"type": "object"},
                "notes": {"type": "string"},
            },
            "required": ["session", "intent"],
            "additionalProperties": False,
        },
        registry._tool_model_step,  # noqa: SLF001
    )
    reg(
        "model-end",
        "End an observation session",
        {
            "type": "object",
            "properties": {"session": {"type": "string"}, "summary": {"type": "string"}},
            "required": ["session", "summary"],
            "additionalProperties": False,
        },
        registry._tool_model_end,  # noqa: SLF001
    )
    reg(
        "tool-request",
        "Request a new tool capability",
        {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "need": {"type": "string"},
                "why": {"type": "string"},
                "examples": {"type": "array"},
                "type": {"type": "string"},
                "priority": {"type": "string"},
                "domain": {"type": "string"},
                "source": {"type": "string"},
                "related_tool": {"type": "string"},
                "failing_call": {"type": "object"},
                "blender": {"type": "object"},
                "context": {"type": "object"},
                "repro": {"type": "object"},
                "error": {"type": "object"},
                "api_probe": {"type": "object"},
                "status": {"type": "string"},
                "tags": {"type": "array"},
                "proposed_tool_name": {"type": "string"},
                "proposed_params_schema": {"type": "object"},
                "return_schema": {"type": "object"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "blocks": {"type": "array", "items": {"type": "string"}},
                "estimated_effort": {"type": "string"},
                "assigned_to": {"type": "string"},
                "updated_by": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "implementation_hint": {"type": "string"},
            },
            "required": ["session", "need", "why"],
            "additionalProperties": False,
        },
        registry._tool_tool_request,  # noqa: SLF001
    )
    reg(
        "tool-request-list",
        "List tool requests",
        {
            "type": "object",
            "properties": {
                "filters": {"type": "object"},
                "limit": {"type": "integer"},
                "cursor": {"type": "string"},
                "next_page_token": {"type": "string"},
            },
            "additionalProperties": False,
        },
        registry._tool_tool_request_list,  # noqa: SLF001
    )
    reg(
        "tool-request-get",
        "Get a tool request by id",
        {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        registry._tool_tool_request_get,  # noqa: SLF001
    )
    reg(
        "tool-request-update",
        "Update a tool request status/priority/tags",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "tags": {"type": "array"},
                "owner": {"type": "string"},
                "resolution_note": {"type": "string"},
                "tests_passed": {"type": "boolean"},
                "proposed_tool_name": {"type": "string"},
                "proposed_params_schema": {"type": "object"},
                "return_schema": {"type": "object"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "blocks": {"type": "array", "items": {"type": "string"}},
                "estimated_effort": {"type": "string"},
                "assigned_to": {"type": "string"},
                "updated_by": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "implementation_hint": {"type": "string"},
                "need": {"type": "string"},
                "why": {"type": "string"},
                "type": {"type": "string"},
                "source": {"type": "string"},
                "related_tool": {"type": "string"},
                "failing_call": {"type": "object"},
                "blender": {"type": "object"},
                "context": {"type": "object"},
                "repro": {"type": "object"},
                "error": {"type": "object"},
                "api_probe": {"type": "object"},
                "list_mode": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
        registry._tool_tool_request_update,  # noqa: SLF001
    )
    reg(
        "tool-request-delete",
        "Hard delete a tool request by id",
        {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        registry._tool_tool_request_delete,  # noqa: SLF001
    )
    reg(
        "tool-request-bulk-update",
        "Bulk update multiple tool requests",
        {
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "string"}},
                "patch": {"type": "object"},
                "mode": {"type": "string"},
                "list_mode": {"type": "string"},
                "tests_passed": {"type": "boolean"},
            },
            "required": ["ids", "patch"],
            "additionalProperties": False,
        },
        registry._tool_tool_request_bulk_update,  # noqa: SLF001
    )
    reg(
        "tool-request-bulk-delete",
        "Bulk delete tool requests",
        {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["ids"],
            "additionalProperties": False,
        },
        registry._tool_tool_request_bulk_delete,  # noqa: SLF001
    )
    reg(
        "tool-request-purge",
        "Purge tool requests by status and age",
        {
            "type": "object",
            "properties": {
                "status": {"type": "array", "items": {"type": "string"}},
                "older_than_days": {"type": "integer"},
            },
            "additionalProperties": False,
        },
        registry._tool_tool_request_purge,  # noqa: SLF001
    )
    reg(
        "tool-request-lint",
        "Lint tool requests for duplicates and implementation status",
        {
            "type": "object",
            "properties": {
                "tests_passed": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        registry._tool_tool_request_lint,  # noqa: SLF001
    )
