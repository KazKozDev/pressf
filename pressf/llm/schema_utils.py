"""Preparing pydantic circuits for structured outputs API.

client.messages.parse() cleans the schema itself, but in Batch API we pass
output_config.format manually - and API does not accept numeric/string
restrictions (minimum/maximum/minLength/...). We remove them and guarantee
additionalProperties: false on each object."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_UNSUPPORTED_KEYS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
}


def _sanitize(node: Any) -> Any:
    if isinstance(node, dict):
        cleaned = {k: _sanitize(v) for k, v in node.items() if k not in _UNSUPPORTED_KEYS}
        if cleaned.get("type") == "object":
            cleaned.setdefault("additionalProperties", False)
        return cleaned
    if isinstance(node, list):
        return [_sanitize(v) for v in node]
    return node


def structured_output_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _sanitize(model.model_json_schema())


def output_format(model: type[BaseModel]) -> dict[str, Any]:
    return {"type": "json_schema", "schema": structured_output_schema(model)}
