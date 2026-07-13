"""Judge on OpenAI: same parse() interface as LLMClient (anthropic).

BYO-provider: key - only OPENAI_API_KEY. Structured outputs - via
chat.completions.parse(response_format=<pydantic>). OpenAI prompt cache
automatic (cached discount is taken into account in the price according to usage).

Limitation: Batch API is implemented only for anthropic - with provider=openai
lazy check works synchronously (see PLAN.md §6)."""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

#$/MTok: (input, output). Prefix matching - Version suffixes change frequently.
OPENAI_PRICING: list[tuple[str, tuple[float, float]]] = [
    ("gpt-5.4-nano", (0.20, 1.25)),
    ("gpt-5.4-mini", (0.75, 4.50)),
    ("gpt-5.4", (1.25, 10.0)),
    ("gpt-5-nano", (0.05, 0.40)),
    ("gpt-5-mini", (0.25, 2.00)),
    ("gpt-5", (1.25, 10.0)),
    ("gpt-4.1-mini", (0.40, 1.60)),
    ("gpt-4.1", (2.00, 8.00)),
    ("gpt-4o", (2.50, 10.0)),
]
_FALLBACK = (1.25, 10.0)
_CACHED_INPUT_MULT = 0.10  #cached-input from OpenAI is 90% cheaper


def _pricing(model: str) -> tuple[float, float]:
    for prefix, price in OPENAI_PRICING:
        if model.startswith(prefix):
            return price
    return _FALLBACK


def usage_cost_openai(model: str, usage) -> float:
    inp, outp = _pricing(model)
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    cost = (prompt - cached) / 1e6 * inp
    cost += cached / 1e6 * inp * _CACHED_INPUT_MULT
    cost += completion / 1e6 * outp
    return cost


def _strip_fences(text: str) -> str:
    """Local models like to wrap JSON in ```json ...```."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


class OpenAILLMClient:
    """Same ParseClient protocol as the anthropic client: the judge does not know
    who is under him? client in the constructor - for tests (DI).

    Openai_compatible servers (Ollama, vLLM,
    LM Studio, Together, DeepSeek, OpenRouter): schema_fallback=True includes
    fallback for servers without strict structured outputs - JSON-scheme
    in the prompt + pydantic validation with one retray."""

    def __init__(
        self,
        client=None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        price_per_mtok: tuple[float, float] | None = None,
        schema_fallback: bool = False,
    ) -> None:
        self._price = price_per_mtok
        self._schema_fallback = schema_fallback
        if client is not None:
            self._client = client
            return
        if base_url is None and not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY not found. Get the key at platform.openai.com"
                "and export: export OPENAI_API_KEY=sk-..."
            )
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "Requires openai package: pip install 'pressf[openai]'"
            ) from e
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        self._client = OpenAI(**kwargs)

    def _cost(self, model: str, usage) -> float:
        if self._price is not None:
            inp, outp = self._price
            prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0
            return prompt / 1e6 * inp + completion / 1e6 * outp
        return usage_cost_openai(model, usage)

    def parse(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4000,
    ) -> tuple[T, float]:
        if not self._schema_fallback:
            return self._parse_strict(model=model, system=system, user=user, schema=schema, max_tokens=max_tokens)
        try:
            return self._parse_strict(model=model, system=system, user=user, schema=schema, max_tokens=max_tokens)
        except Exception:
            #the server does not know how to strictly structured outputs - scheme in prompt + validation
            return self._parse_via_prompt(model=model, system=system, user=user, schema=schema, max_tokens=max_tokens)

    def _parse_strict(self, *, model: str, system: str, user: str, schema: type[T], max_tokens: int) -> tuple[T, float]:
        completions = self._client.chat.completions
        parse_fn = getattr(completions, "parse", None)
        if parse_fn is None:  #old versions of SDK kept parse in beta
            parse_fn = self._client.beta.chat.completions.parse
        response = parse_fn(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
            max_completion_tokens=max_tokens,
        )
        message = response.choices[0].message
        parsed = getattr(message, "parsed", None)
        if parsed is None:
            refusal = getattr(message, "refusal", None)
            raise RuntimeError(
                f"OpenAI did not return a valid one{schema.__name__}"
                + (f" (refusal: {refusal})" if refusal else "")
            )
        return parsed, self._cost(model, response.usage)

    def _parse_via_prompt(self, *, model: str, system: str, user: str, schema: type[T], max_tokens: int) -> tuple[T, float]:
        import json

        from .schema_utils import structured_output_schema

        schema_json = json.dumps(structured_output_schema(schema), ensure_ascii=False)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"{user}\n\nAnswer ONLY valid JSON strictly according to this JSON-scheme,"
                f"no explanation and no markdown:\n{schema_json}",
            },
        ]
        cost = 0.0
        last_error = ""
        for _ in range(2):  #one attempt + one retry with error text
            response = self._client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens
            )
            text = _strip_fences(response.choices[0].message.content or "")
            cost += self._cost(model, response.usage)
            try:
                return schema.model_validate_json(text), cost
            except Exception as e:
                last_error = str(e)
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {"role": "user", "content": f"JSON is invalid:{last_error[:500]}. Repeat strictly according to the scheme, only JSON."}
                )
        raise RuntimeError(f"The model could not produce a valid{schema.__name__}: {last_error[:300]}")

    def count_tokens(self, *, model: str, system: str, user: str) -> int:
        """OpenAI does not have an endpoint count_tokens - a rough estimate for the estimate
        (~3.5 characters/token in mixed Russian-English text)."""
        return int(len(system + user) / 3.5)
