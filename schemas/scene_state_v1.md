# Scene State Snapshot v1 (NEW)

**Version:** v1  
**Purpose:** A headless-safe, reproducible scene snapshot format for verification, diffing, and deterministic workflows.

---

## Snapshot Envelope

A snapshot is a JSON object with:

- `version`: `"scene_state_v1"`
- `blender`: runtime metadata
- `scene`: scene-level metadata
- `objects`: list of objects (canonical order)
- `indices`: optional lookup structures
- `fingerprints`: optional hashes for integrity

---

## Blender Metadata

Recommended fields:

- `version_string` (e.g., `"Blender 5.0.0"`)
- `version_tuple` (e.g., `[5,0,0]`)
- `headless` (boolean)
- `engine` (e.g., `"BLENDER_EEVEE_NEXT"` or `"CYCLES"` when relevant)

---

## Scene Metadata

Recommended fields:

- `name`
- `unit_settings` (scale, unit system)
- `frame_current`
- `collections` (names/ids only; avoid UI-only details)

---

## Object Shape

Each object entry (recommended minimal):

- `name` (string, stable)
- `type` (string, Blender type: `MESH`, `LIGHT`, `CAMERA`, etc.)
- `transform`:
  - `location` [x,y,z]
  - `rotation_euler` [x,y,z] or `rotation_quaternion` [w,x,y,z]
  - `scale` [x,y,z]
- `visibility`:
  - `hide_viewport`
  - `hide_render`
- `collections`: list of collection names (canonical order)
- `data_ref`:
  - pointer-like stable reference (mesh name, camera datablock name, etc.) if needed
- `materials`:
  - list of material names applied (canonical order)

Optional fields for richer snapshots:
- `modifiers` (names/types only, parameters optional)
- `custom_props` (only if explicitly whitelisted; avoid leaking large blobs)

---

## Canonical Ordering Rules

To ensure stable diffs and fingerprints:

- `objects` list MUST be sorted by:
  1) `type`
  2) `name`
- `collections` lists MUST be sorted lexicographically.
- `materials` lists MUST be sorted lexicographically.
- Nested lists (modifiers, etc.) must be sorted by stable keys where possible.

---

## Float Canonicalization

Recommended:
- represent floats with a consistent rounding strategy (e.g., 6 decimals) when exporting
- or declare a tolerance in tooling that compares snapshots

Do not claim byte-identical snapshots across platforms unless you enforce canonical float formatting.

---

## Indices (Optional)

Indices are derived aids, never authoritative.

Examples:
- `by_name`: `{ "Cube": 0, "Camera": 1 }`
- `by_type`: `{ "MESH": [0,3,5], "LIGHT": [1] }`

If included, indices must match canonical ordering.

---

## Fingerprints (Optional)

Fingerprints are hashes of canonicalized snapshot content.

Recommended:
- `algorithm`: `"sha256"`
- `scene_fingerprint`: hash of the canonical snapshot (excluding indices)

Rules:
- canonicalize ordering
- canonicalize float formatting (if fingerprinting)
- hash on UTF-8 encoded canonical JSON (stable key ordering)

---

## Partial vs Full Snapshot

A snapshot may be:
- **full**: covers all objects and relevant scene metadata
- **partial**: covers a subset (e.g., only affected objects)

If partial, include:
- `partial=true`
- `scope`: description of what is included (names/types or selection criteria)

---

## Headless-Safe Notes

- Snapshot generation must not depend on UI context, selection, or active object.
- Prefer data API access over ops.
- Avoid properties that require UI evaluation or heavy deps unless explicitly requested.
