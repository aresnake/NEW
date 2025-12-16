# Scene Snapshot v1

## Purpose
Provide a deterministic, structured snapshot of Blender state for LLM planning and verification.

## High-level structure (conceptual)
- scene: metadata (name, frame range, fps, unit settings, render engine)
- objects: list with stable ordering + per-object summary
- collections: hierarchy summary
- materials: node-based summary + fingerprints
- cameras/lights: parameters summary
- indices: helper maps (by name, by type)

## Canonicalization
- Sort objects by (type, name) for stable ordering.
- Float values rounded to tolerances before fingerprinting.

## Fingerprinting guidance
- Fingerprints should be derived from canonicalized data.
- Include: object transforms, mesh topology hash (when feasible), material node graph hash, key render settings.
