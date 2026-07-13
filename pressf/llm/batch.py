"""Batch API: 50% discount on mass precheck (PLAN.md §4.2).

BatchRunner collects requests from structured outputs (output_config.format manually,
because parse() is not available in batches), polls until completion and parses the results
back to pydantic models. The results are matched by custom_id = example_id."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from pydantic import BaseModel

from .client import usage_cost
from .schema_utils import output_format

T = TypeVar("T", bound=BaseModel)

BATCH_DISCOUNT = 0.5


@dataclass
class BatchItem:
    custom_id: str
    model: str
    system: str
    user: str
    schema: type[BaseModel]
    max_tokens: int = 4000


@dataclass
class BatchOutcome:
    parsed: BaseModel | None
    cost_usd: float
    error: str | None = None


def build_request(item: BatchItem) -> dict:
    return {
        "custom_id": item.custom_id,
        "params": {
            "model": item.model,
            "max_tokens": item.max_tokens,
            "system": [
                {"type": "text", "text": item.system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": item.user}],
            "output_config": {"format": output_format(item.schema)},
        },
    }


def parse_result(result, schema: type[BaseModel]) -> BatchOutcome:
    """result is an element of client.messages.batches.results()."""
    rtype = result.result.type
    if rtype != "succeeded":
        err = getattr(getattr(result.result, "error", None), "type", rtype)
        return BatchOutcome(parsed=None, cost_usd=0.0, error=str(err))
    message = result.result.message
    cost = usage_cost(message.model, message.usage) * BATCH_DISCOUNT
    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return BatchOutcome(parsed=schema.model_validate_json(text), cost_usd=cost)
    except Exception as e:  #structured outputs guarantee the scheme, but let's play it safe
        return BatchOutcome(parsed=None, cost_usd=cost, error=f"parse: {e}")


class BatchRunner:
    def __init__(self, anthropic_client, poll_seconds: int = 20):
        self._client = anthropic_client
        self._poll = poll_seconds

    def run(
        self,
        items: list[BatchItem],
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, BatchOutcome]:
        """Send the batch, wait, return {custom_id: BatchOutcome}."""
        if not items:
            return {}
        schemas = {it.custom_id: it.schema for it in items}
        batch = self._client.messages.batches.create(
            requests=[build_request(it) for it in items]
        )
        if on_status:
            on_status(f"batch{batch.id}: {len(items)}requests sent")
        while True:
            batch = self._client.messages.batches.retrieve(batch.id)
            if batch.processing_status == "ended":
                break
            if on_status:
                counts = batch.request_counts
                on_status(
                    f"batch{batch.id}: being processed{counts.processing}, ready{counts.succeeded}"
                )
            time.sleep(self._poll)

        outcomes: dict[str, BatchOutcome] = {}
        for result in self._client.messages.batches.results(batch.id):
            outcomes[result.custom_id] = parse_result(result, schemas[result.custom_id])
        return outcomes
