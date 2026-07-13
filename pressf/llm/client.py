"""A wrapper for anthropic SDK: structured outputs, prompt caching, cost counter.

BYO-key: the key is taken only from ANTHROPIC_API_KEY. Retrai 429/5xx is made by SDK himself."""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

#$/MTok: (input, output). Cache: write ~1.25x input, read ~0.1x input.
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
}
_CACHE_WRITE_MULT = 1.25
_CACHE_READ_MULT = 0.10


def usage_cost(model: str, usage) -> float:
    """The cost of one response is $ for the usage field."""
    inp, outp = PRICING.get(model, (5.0, 25.0))
    cost = (getattr(usage, "input_tokens", 0) or 0) / 1e6 * inp
    cost += (getattr(usage, "output_tokens", 0) or 0) / 1e6 * outp
    cost += (getattr(usage, "cache_creation_input_tokens", 0) or 0) / 1e6 * inp * _CACHE_WRITE_MULT
    cost += (getattr(usage, "cache_read_input_tokens", 0) or 0) / 1e6 * inp * _CACHE_READ_MULT
    return cost


class LLMClient:
    """The judge's only entry point is LLM. The judge depends on the parse() interface,
    therefore, in tests it is replaced by a fake with the same method."""

    def __init__(self) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found. Get the key at console.anthropic.com"
                "and export: export ANTHROPIC_API_KEY=sk-ant-..."
            )
        import anthropic

        self._client = anthropic.Anthropic()

    @property
    def anthropic(self):
        """Raw SDK client - for Batch API and count_tokens."""
        return self._client

    def count_tokens(self, *, model: str, system: str, user: str) -> int:
        resp = self._client.messages.count_tokens(
            model=model,
            system=[{"type": "text", "text": system}],
            messages=[{"role": "user", "content": user}],
        )
        return resp.input_tokens

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4000,
    ) -> tuple[T, float]:
        """One call with structured output. system is cached (stable prefix:
        judge's prompt + guidelines), variable part - in user."""
        response = self._client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError(
                f"LLM did not return valid{schema.__name__} (stop_reason={response.stop_reason})"
            )
        return parsed, usage_cost(model, response.usage)
