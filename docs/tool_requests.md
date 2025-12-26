# Tool Requests

- Storage: JSONL at `data/tool_requests.jsonl` (+ deltas in `tool_requests_updates.jsonl`), auto-created. Corrupted lines are skipped with warnings. Set `TOOL_REQUEST_DATA_DIR` to redirect for tests.
- Schema (schema_version=2 + revision/updated_at): `session`, `need`, `why`, `type`, `priority`, `domain`, `source`, `status`, `tags`, `related_tool`, `failing_call`, `blender`, `context`, `repro`, `error`, `api_probe`, `proposed_tool_name`, `proposed_params_schema`, `return_schema`, `depends_on`, `blocks`, `estimated_effort`, `assigned_to`, `updated_by`, `examples`, `acceptance_criteria`, `implementation_hint`.
- Create: `tool-request` accepts legacy payloads `{session, need, why}` and upgrades defaults (type=enhancement, priority=medium, domain=system, source=manual).
- Read/List: `tool-request-get(id)`, `tool-request-list(filters?, limit?, cursor?/next_page_token?)` with filters for status (string or array), priority (string or array), domain, session, has_api_probe, has_params_schema, q/text (searches need/why/tags/proposed_tool_name/implementation_hint). Ordered by created_at desc.
- Mutate:
  - `tool-request-update(id, patch..., mode=merge|replace, list_mode=append|replace)` deep-merges dicts (api_probe/schemas) by default; replace mode overwrites fields.
  - `tool-request-delete(id)` hard-deletes.
  - `tool-request-bulk-update(ids, patch, mode?, list_mode?)`, `tool-request-bulk-delete(ids)` (per-id results).
  - Optional `tool-request-purge(status?, older_than_days?)` for cleanup.
- JSON examples:
```json
{"name":"tool-request","arguments":{"session":"legacy","need":"boolean toggle","why":"missing op"}}
{"name":"tool-request-update","arguments":{"id":"<id>","api_probe":{"inputs":{"y":"int"}},"mode":"merge"}}
{"name":"tool-request-delete","arguments":{"id":"<id>"}}
{"name":"tool-request-bulk-update","arguments":{"ids":["<id1>","<id2>"],"patch":{"status":"triaged"},"mode":"merge"}}
{"name":"tool-request-bulk-delete","arguments":{"ids":["<id1>","missing-id"]}}
{"name":"tool-request-list","arguments":{"filters":{"status":["triaged"],"has_api_probe":true,"q":"split mesh"},"limit":20}}
```
