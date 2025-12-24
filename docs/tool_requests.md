# Tool Requests v2

- Tool: `tool-request` now stores schema_version=2 with richer metadata (type, priority, domain, source, context, repro, error, api_probe, tags).
- Legacy payloads `{session, need, why, examples?}` are upgraded automatically with defaults (type=enhancement, priority=medium, domain=system, source=manual).
- Storage: JSONL at `data/tool_requests.jsonl` (+ updates in `tool_requests_updates.jsonl`), auto-created.
- New tools:
  - `tool-request-list(filters?, limit?, cursor?)` -> items summaries.
  - `tool-request-get(id)` -> full entry.
  - `tool-request-update(id, status?, priority?, tags?, owner?, resolution_note?)` -> applies updates deterministically.
- Filters support status/domain/type/priority/session/text. Corrupted JSONL lines are skipped with warnings.

Set `TOOL_REQUEST_DATA_DIR` to redirect storage during tests or custom deployment.
