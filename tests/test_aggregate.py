"""Category table from PLAN.md §3.2 - deterministic aggregate logic."""

from __future__ import annotations

from pressf.judge.aggregate import aggregate_claims_verdict, aggregate_refusal_verdict
from pressf.schemas import (
    AnswerabilityResult,
    Chunk,
    ClaimCheck,
    EvidenceRef,
    ExtractedClaims,
    VerificationResult,
)

CHUNKS = [Chunk(text="Limit 600 per hour", source="doc.md#0", score=1.0)]


def _verify(statuses: list[str]) -> VerificationResult:
    checks = [
        ClaimCheck(
            claim_index=i,
            status=s,  # type: ignore[arg-type]
            evidence=[EvidenceRef(chunk_index=0, quote="Limit 600 per hour")] if s != "not_found" else [],
        )
        for i, s in enumerate(statuses)
    ]
    return VerificationResult(checks=checks, confidence=0.9, reasoning="test")


def _run(statuses: list[str]):
    extracted = ExtractedClaims(is_refusal=False, claims=[f"brands{i}" for i in range(len(statuses))])
    return aggregate_claims_verdict(
        example_id="e",
        extracted=extracted,
        verification=_verify(statuses),
        chunks=CHUNKS,
        judge_model="m",
        escalated=False,
        cost_usd=0.001,
    )


def test_all_supported_is_correct():
    v = _run(["supported", "supported"])
    assert (v.category, v.recommendation, v.answerable, v.grounded) == ("correct", "p", True, True)


def test_any_contradicted_is_hallucination():
    v = _run(["supported", "contradicted"])
    assert (v.category, v.recommendation) == ("hallucination_contradicts", "f")
    assert v.grounded is False


def test_all_not_found_is_unanswerable():
    v = _run(["not_found", "not_found"])
    assert (v.category, v.recommendation, v.answerable) == ("hallucination_unanswerable", "f", False)


def test_mixed_supported_not_found_is_partial():
    v = _run(["supported", "not_found"])
    assert (v.category, v.recommendation) == ("partial", "f")


def test_missing_check_treated_as_not_found():
    extracted = ExtractedClaims(is_refusal=False, claims=["a", "b"])
    verification = _verify(["supported"])  #the judge lost his second mark
    v = aggregate_claims_verdict(
        example_id="e", extracted=extracted, verification=verification,
        chunks=CHUNKS, judge_model="m", escalated=False, cost_usd=0,
    )
    assert v.category == "partial"
    assert v.claims[1].status == "not_found"


def test_false_refusal():
    ans = AnswerabilityResult(
        answerable=True,
        evidence=[EvidenceRef(chunk_index=0, quote="Limit 600 per hour")],
        confidence=0.85,
        reasoning="the answer is in the database",
    )
    v = aggregate_refusal_verdict(
        example_id="e", answerability=ans, chunks=CHUNKS,
        judge_model="m", escalated=False, cost_usd=0,
    )
    assert (v.category, v.recommendation, v.is_refusal, v.grounded) == ("false_refusal", "f", True, None)
    assert v.claims[0].evidence[0].source == "doc.md#0"


def test_correct_refusal():
    ans = AnswerabilityResult(answerable=False, evidence=[], confidence=0.9, reasoning="not in the database")
    v = aggregate_refusal_verdict(
        example_id="e", answerability=ans, chunks=CHUNKS,
        judge_model="m", escalated=False, cost_usd=0,
    )
    assert (v.category, v.recommendation) == ("correct_refusal", "p")
