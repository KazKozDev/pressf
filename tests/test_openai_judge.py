"""Judge on OpenAI: parse() protocol, cost with cache, provider routing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pressf.config import LLMConfig, Project
from pressf.judge import run_check
from pressf.llm import build_llm_client
from pressf.llm.openai_client import OpenAILLMClient, usage_cost_openai
from pressf.schemas import (
    AnswerabilityResult,
    ClaimCheck,
    EvidenceRef,
    ExtractedClaims,
    VerificationResult,
)


def _usage(prompt=1000, completion=100, cached=0):
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )


def test_pricing_prefix_and_cache_discount():
    #gpt-5.4-mini: $0.75/$4.50; cached input - 10% of the price
    cost = usage_cost_openai("gpt-5.4-mini-2026-05", _usage(prompt=1000, completion=100, cached=400))
    expected = 600 / 1e6 * 0.75 + 400 / 1e6 * 0.75 * 0.1 + 100 / 1e6 * 4.5
    assert abs(cost - expected) < 1e-12


def test_unknown_model_uses_fallback():
    assert usage_cost_openai("gpt-99-turbo", _usage()) > 0


class FakeOpenAI:
    """Fake SDK: chat.completions.parse returns the template according to the scheme."""

    def __init__(self):
        outer = self

        class _Completions:
            def parse(self, *, model, messages, response_format, max_completion_tokens):
                outer.last_model = model
                if response_format is ExtractedClaims:
                    parsed = ExtractedClaims(is_refusal=False, claims=["limit 600"])
                elif response_format is VerificationResult:
                    parsed = VerificationResult(
                        checks=[ClaimCheck(claim_index=0, status="supported",
                                           evidence=[EvidenceRef(chunk_index=0, quote="600")])],
                        confidence=0.9, reasoning="OK",
                    )
                else:
                    parsed = AnswerabilityResult(answerable=False, evidence=[], confidence=0.9, reasoning="No")
                message = SimpleNamespace(parsed=parsed, refusal=None)
                return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=_usage())

        self.chat = SimpleNamespace(completions=_Completions())


def test_openai_judge_full_pipeline(project: Project):
    """The judge runs the entire pipeline through the OpenAI client, without knowing about the provider."""
    cfg = project.load_config()
    cfg.llm = LLMConfig(provider="openai", judge_model="gpt-5.4-mini", escalation_model="gpt-5.4")
    project.save_config(cfg)
    project.verdicts_path.unlink()

    client = OpenAILLMClient(client=FakeOpenAI())
    summary = run_check(project, client)
    assert summary.checked == 3
    verdicts = project.load_verdicts()
    assert verdicts["e1"].category == "correct"
    assert verdicts["e1"].judge_model == "gpt-5.4-mini"
    assert all(v.cost_usd > 0 for v in verdicts.values())


def test_parse_raises_on_refusal():
    class RefusingOpenAI(FakeOpenAI):
        def __init__(self):
            class _Completions:
                def parse(self, **kwargs):
                    message = SimpleNamespace(parsed=None, refusal="no really")
                    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=_usage())

            self.chat = SimpleNamespace(completions=_Completions())

    client = OpenAILLMClient(client=RefusingOpenAI())
    with pytest.raises(RuntimeError, match="refusal"):
        client.parse(model="gpt-5.4-mini", system="s", user="u", schema=ExtractedClaims)


def test_build_llm_client_unknown_provider():
    with pytest.raises(ValueError, match="Unknown llm.provider"):
        build_llm_client(LLMConfig(provider="grok"))
