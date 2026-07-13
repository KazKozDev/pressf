"""openai_compatible: config defaults, fallback structured outputs, own price."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from pressf.config import LLMConfig
from pressf.llm import build_llm_client
from pressf.llm.openai_client import OpenAILLMClient, _strip_fences
from pressf.schemas import ExtractedClaims


def _usage(prompt=1000, completion=100):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=None)


#── config ───────────────────────────────── ─────────────────────────────────


def test_compat_requires_explicit_judge_model():
    with pytest.raises(ValueError, match="judge_model"):
        LLMConfig(provider="openai_compatible", base_url="http://localhost:11434/v1")


def test_compat_escalation_defaults_to_judge():
    cfg = LLMConfig(provider="openai_compatible", judge_model="llama3.3:70b", base_url="http://x/v1")
    assert cfg.escalation_model == "llama3.3:70b"  #escalation is actually turned off


def test_openai_provider_replaces_claude_defaults():
    cfg = LLMConfig(provider="openai")
    assert cfg.judge_model == "gpt-5.4-mini"
    assert cfg.escalation_model == "gpt-5.4"


def test_build_client_requires_base_url():
    cfg = LLMConfig(provider="openai_compatible", judge_model="llama3.3:70b")
    with pytest.raises(ValueError, match="base_url"):
        build_llm_client(cfg)


# ── fallback structured outputs ─────────────────────────────────────────────


def test_strip_fences():
    assert _strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_fences('{"a": 1}') == '{"a": 1}'


class OllamaLikeClient:
    """A server without structured outputs: parse crashes, create responds with text.
    The first answer is invalid, the second (after the retray with an error) is valid in fences."""

    def __init__(self):
        self.create_calls = []
        outer = self

        class _Completions:
            def parse(self, **kwargs):
                raise TypeError("response_format not supported")  #like old compat servers

            def create(self, *, model, messages, max_tokens):
                outer.create_calls.append(list(messages))  #copy: client mutates list
                if len(outer.create_calls) == 1:
                    text = '{"is_refusal": "maybe"}'  # invalid according to the schema
                else:
                    text = '```json\n' + json.dumps({"is_refusal": False, "claims": ["limit 600"]}) + '\n```'
                msg = SimpleNamespace(content=text)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage())

        self.chat = SimpleNamespace(completions=_Completions())


def test_fallback_prompt_json_with_retry():
    fake = OllamaLikeClient()
    client = OpenAILLMClient(client=fake, price_per_mtok=(0.0, 0.0), schema_fallback=True)
    parsed, cost = client.parse(model="llama3.3:70b", system="s", user="u", schema=ExtractedClaims)
    assert parsed.claims == ["limit 600"]
    assert cost == 0.0  #local model - free
    assert len(fake.create_calls) == 2
    #the scheme was included in the prompt, the retray contains the text of a validation error
    assert "JSON-scheme" in fake.create_calls[0][-1]["content"]
    assert "invalid" in fake.create_calls[1][-1]["content"]


def test_custom_pricing_applied():
    fake = OllamaLikeClient()
    #hosted-open source: $0.5/$1.5 per MTok, two create calls (retry) are summed up
    client = OpenAILLMClient(client=fake, price_per_mtok=(0.5, 1.5), schema_fallback=True)
    _, cost = client.parse(model="deepseek-v4", system="s", user="u", schema=ExtractedClaims)
    per_call = 1000 / 1e6 * 0.5 + 100 / 1e6 * 1.5
    assert abs(cost - 2 * per_call) < 1e-12
