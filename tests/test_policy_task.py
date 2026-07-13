from __future__ import annotations

from pressf.judge.aggregate import aggregate_policy_verdict
from pressf.llm import prompts
from pressf.schemas import Chunk, PolicyCheckResult


def test_policy_prompt_selected():
    system = prompts.task_system("policy_compliance", "Never promise refunds.")
    assert "compliance with company rules" in system
    assert "Never promise refunds" in system


def test_policy_violation_maps_to_f_with_rule_quote():
    chunks = [Chunk(text="Do not promise refunds.", source="policy.md#0", score=1.0)]
    verdict = aggregate_policy_verdict(
        example_id="e1",
        result=PolicyCheckResult(
            status="violates_policy",
            offending_sentence="You will get a refund.",
            rule_quote="Do not promise refunds.",
            rule_source_index=0,
            confidence=0.92,
            reasoning="The answer promises a refund.",
        ),
        chunks=chunks,
        judge_model="fixture",
        escalated=False,
        cost_usd=0.01,
    )
    assert verdict.category == "violates_policy"
    assert verdict.recommendation == "f"
    assert verdict.claims[0].evidence[0].source == "policy.md#0"


def test_policy_compliant_maps_to_p():
    verdict = aggregate_policy_verdict(
        example_id="e1",
        result=PolicyCheckResult(
            status="compliant",
            confidence=0.9,
            reasoning="No rule is broken.",
        ),
        chunks=[],
        judge_model="fixture",
        escalated=False,
        cost_usd=0.01,
    )
    assert verdict.category == "compliant"
    assert verdict.recommendation == "p"
