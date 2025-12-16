# Determinism Rules v1

## Classes
1) Deterministic: same input => same output (within tolerances).
2) Seeded: deterministic given an explicit seed.
3) Non-deterministic: depends on external state/time/UI; must be avoided by default.

## Requirements
- Every tool declares determinism_class.
- Seeded tools accept a seed and propagate it to sub-ops.
- Canonical ordering for lists and maps.

## Float tolerances
- Store floats with a fixed rounding policy for snapshots and fingerprints.

## Reporting
- Tool responses must include determinism metadata (class, seed used, tolerances).
