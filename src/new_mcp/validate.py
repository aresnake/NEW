from __future__ import annotations

from typing import Any, Dict, Tuple

from .contracts import ToolResult, ERR_INVALID_INPUT

JsonDict = Dict[str, Any]


def _is_type(val: Any, t: str) -> bool:
    if t == "object":
        return isinstance(val, dict)
    if t == "string":
        return isinstance(val, str)
    if t == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if t == "boolean":
        return isinstance(val, bool)
    if t == "array":
        return isinstance(val, list)
    return True  # unknown -> don't block


def validate_params(params: JsonDict, schema: JsonDict) -> Tuple[bool, str]:
    """
    Minimal JSON-schema-like validator (subset):
      - type: object
      - properties + simple types
      - required
      - additionalProperties (bool)
      - integer minimum/maximum
      - enum (for strings)
    """
    if schema.get("type") == "object" and not isinstance(params, dict):
        return False, "params must be an object"

    props = schema.get("properties", {}) or {}
    required = schema.get("required", []) or []
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in params:
            return False, f"missing required param: {key}"

    if additional is False:
        for k in params.keys():
            if k not in props:
                return False, f"unexpected param: {k}"

    for k, spec in props.items():
        if k not in params:
            continue
        v = params[k]
        t = spec.get("type")
        if t and not _is_type(v, t):
            return False, f"param '{k}' must be {t}"
        if t == "integer":
            if "minimum" in spec and v < int(spec["minimum"]):
                return False, f"param '{k}' must be >= {spec['minimum']}"
            if "maximum" in spec and v > int(spec["maximum"]):
                return False, f"param '{k}' must be <= {spec['maximum']}"
        if "enum" in spec and v not in spec["enum"]:
            return False, f"param '{k}' must be one of {spec['enum']}"
    return True, ""


def validated_or_failure(params: JsonDict, schema: JsonDict) -> ToolResult | None:
    ok, msg = validate_params(params, schema)
    if not ok:
        return ToolResult.failure(ERR_INVALID_INPUT, msg)
    return None
