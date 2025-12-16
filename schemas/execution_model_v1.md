# Execution Model v1 (NEW)

**Version:** v1  
**Scope:** Contract-first tool execution lifecycle for NEW (MCP for Blender).  
**Principle:** Headless-first (data-first) by default; UI-assisted is optional and explicitly gated.

---

## Goals

- Define a predictable lifecycle for every tool invocation.
- Make capabilities explicit: **host profile × blender profile → session contract**.
- Prefer deterministic, reproducible behavior.
- Provide explicit refusal/error codes with actionable messages.
- Support partial execution reporting and verification hooks.

---

## Core Concepts

### Tool
A named callable capability exposed over MCP (JSON-RPC).

### Host Profile
Properties/limits of the LLM host environment (transport, max payload, streaming support, cancellation support).

### Blender Profile
Properties of the Blender runtime (version, headless/UI, engine availability, permissions, sandbox rules).

### Contract
The negotiated execution constraints and guarantees for the session/tool call.

### Determinism Class
Declared per tool: `deterministic`, `seeded`, or `nondeterministic` (see `determinism_rules_v1.md`).

### Scene Snapshot
Structured state representation used for verification and reproducibility (see `scene_state_v1.md`).

---

## Safety Modes

Tools are tagged with a safety mode:

- `headless_safe` (default): data-first APIs, headless-compatible, minimal context.
- `ui_assisted`: requires Blender UI; may use UI context and limited ops.
- `unsafe_ops`: requires explicit opt-in; context-dependent; higher failure/nondeterminism risk.

A runtime may refuse requests that exceed policy or capability.

---

## Execution Lifecycle (Phases)

Each tool call follows these phases:

### Phase 0 — Parse (Transport Layer)
- Parse JSON-RPC request.
- Validate presence/type of `jsonrpc`, `id`, `method`, `params`.
- Transport errors use JSON-RPC error envelope.

### Phase 1 — Validate Input (Tool Layer)
- Validate params against tool schema: required keys, types, ranges.
- Canonicalize where needed (strings trimming, normalized paths, float normalization policy).
- On failure: return `ToolResult(ok=false, error_code="invalid_input", ...)`.

### Phase 2 — Contract & Capability Gate
- Resolve active contract:
  - host profile (transport limits)
  - blender profile (headless/UI, version)
  - tool metadata (safety mode, determinism class)
- Verify capability requirements:
  - headless required vs UI required
  - Blender version constraints
  - restricted features (filesystem/network) policy
  - unsafe ops permission gates
- If missing/forbidden: refuse with `capability_missing` or `policy_refused`.

### Phase 3 — Optional Plan
Planning is recommended when:
- multi-step tasks are requested
- rollback/partial failure risk exists
- operation is non-idempotent
- operation touches many entities
Plan should be structured and deterministic (ordered steps with stable identifiers).

### Phase 4 — Execute
- Execute with the safest available method (prefer `headless_safe`).
- Follow determinism rules.
- If using ops/UI context, record it in tool metadata/results (future extension).

### Phase 5 — Optional Verify
Verification is recommended when:
- the tool mutates scene state
- the user requested `verify=true`
- returning a handle that must be validated (object exists, material linked, etc.)
Verification should rely on data queries/snapshots, not UI cues.

### Phase 6 — Return
Return a `ToolResult` envelope (tool layer), including determinism metadata.

---

## Idempotence & Partiality

Tools must document idempotence:

- **Idempotent:** repeating with same params yields same end state.
- **Repeatable with accumulation:** repeats add safe duplicates (must disclose).
- **Non-idempotent:** repeats change state; must return stable handles.

If partial work occurs:
- Prefer `ok=false` with a clear `error_code`.
- If the tool succeeds but has degraded outcomes, report as `ok=true` with an explanatory field (future extension), or use `ok=false` to force attention.

---

## Timeouts & Cancellation

- The runtime should respect a time budget if the host provides one.
- If a tool exceeds the budget: return `timeout` and include partial work summary (if any).
- Cancellation support depends on host transport; long-running operations should be designed to checkpoint (future extension).

---

## Refusal / Error Codes (v1)

Tool-level errors use `ToolResult(ok=false, error_code=..., message=...)`.

Common codes:

- `invalid_input` — params invalid/missing/incorrect types
- `capability_missing` — required capability not available (UI/headless mismatch, version mismatch)
- `policy_refused` — violates safety/policy gates (unsafe ops, forbidden access)
- `not_found` — referenced resource/entity missing
- `conflict` — name/handle collision or incompatible state
- `timeout` — exceeded time budget
- `nondeterministic_refused` — determinism requested but cannot be honored
- `internal_error` — unexpected failure (should be rare)

---

## Determinism Requirements (Linkage)

Every successful tool result should include determinism metadata:
- `determinism_class`: `deterministic` | `seeded` | `nondeterministic`
- `seed`: required when `seeded`
- `tolerance`: required when canonicalization/float tolerance applies (future extension)

If the tool cannot honor determinism constraints:
- refuse with `nondeterministic_refused`, or
- explicitly downgrade determinism under a contract update (future extension; not in v1).

---

## Snapshot & Fingerprints (Linkage)

For scene-mutating tools:
- prefer returning stable handles and allow the caller to request a snapshot post-action
- snapshot formats and fingerprinting are defined in `scene_state_v1.md`
