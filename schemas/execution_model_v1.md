# Execution Model v1

## Overview
This document defines the canonical execution phases for NEW tools.

Phases:
1) Validate input
2) Capability check (host+blender profile)
3) Optional plan (when needed)
4) Execute
5) Optional verify
6) Return result

## Safety Modes
- headless_safe (default): data-first, deterministic, no UI assumptions
- ui_assisted: UI open, still contract-first, limited ops allowed
- unsafe_ops: explicit opt-in, bpy.ops allowed with guardrails

## Idempotence & Atomicity
- Tools should be idempotent when possible.
- If not idempotent, tool must declare it in its contract and return a stable handle.
- Prefer atomic operations; if partial work occurs, report it explicitly.

## Timeouts / Cancellation
- Every tool call supports a timeout budget.
- Long tasks must report progress checkpoints when feasible.

## Refusal & Errors
- refusal codes are structured (e.g., capability_missing, invalid_input, unsafe_request).
- errors must be non-ambiguous and actionable.
