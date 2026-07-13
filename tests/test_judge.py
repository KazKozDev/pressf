"""Judge pipeline with fake LLM: fault routing, escalation, idempotency, budget."""

from __future__ import annotations

import pytest

from pressf.config import Project
from pressf.io import write_jsonl_atomic
from pressf.judge import run_check
from pressf.schemas import (
    AnswerabilityResult,
    ClaimCheck,
    EvidenceRef,
    Example,
    ExtractedClaims,
    VerificationResult,
)


class FakeClient:
    """Returns blanks by schema type; counts calls based on models."""

    def __init__(self, *, refusal: bool = False, confidence: float = 0.9, cost: float = 0.01):
        self.refusal = refusal
        self.confidence = confidence
        self.cost = cost
        self.calls: list[tuple[str, str]] = []  # (model, schema)

    def parse(self, *, model, system, user, schema, max_tokens=4000):
        self.calls.append((model, schema.__name__))
        if schema is ExtractedClaims:
            return ExtractedClaims(is_refusal=self.refusal, claims=[] if self.refusal else ["limit 600 per hour"]), self.cost
        if schema is VerificationResult:
            return VerificationResult(
                checks=[ClaimCheck(claim_index=0, status="supported",
                                   evidence=[EvidenceRef(chunk_index=0, quote="600 requests")])],
                confidence=self.confidence,
                reasoning="OK",
            ), self.cost
        if schema is AnswerabilityResult:
            return AnswerabilityResult(answerable=False, evidence=[], confidence=self.confidence, reasoning="not in the database"), self.cost
        raise AssertionError(schema)


def test_normal_flow_writes_verdicts(project: Project):
    project.verdicts_path.unlink()
    client = FakeClient()
    summary = run_check(project, client)
    assert summary.checked == 3
    verdicts = project.load_verdicts()
    assert set(verdicts) == {"e1", "e2", "e3"}
    assert verdicts["e1"].category == "correct"
    assert verdicts["e1"].cost_usd > 0


def test_refusal_goes_through_answerability(project: Project):
    project.verdicts_path.unlink()
    client = FakeClient(refusal=True)
    run_check(project, client, limit=1)
    assert ("claude-haiku-4-5", "AnswerabilityResult") in client.calls
    v = next(iter(project.load_verdicts().values()))
    assert v.category == "correct_refusal"


def test_escalation_on_low_confidence(project: Project):
    project.verdicts_path.unlink()
    client = FakeClient(confidence=0.4)  #below threshold 0.7
    run_check(project, client, limit=1)
    models = [m for m, s in client.calls if s == "VerificationResult"]
    assert models == ["claude-haiku-4-5", "claude-opus-4-8"]
    v = next(iter(project.load_verdicts().values()))
    assert v.escalated is True
    assert v.judge_model == "claude-opus-4-8"


def test_only_ids_judges_just_the_sampled_subset(project: Project):
    #phase B: check --sample throws only_ids → exactly selected examples are judged
    project.verdicts_path.unlink()
    client = FakeClient()
    summary = run_check(project, client, only_ids={"e2"})
    assert summary.checked == 1
    assert set(project.load_verdicts()) == {"e2"}


def test_idempotent_recheck(project: Project):
    #all 3 verdicts are already in the fixture
    client = FakeClient()
    summary = run_check(project, client)
    assert summary.checked == 0
    assert summary.skipped_existing == 3
    assert client.calls == []


def test_budget_stop(project: Project):
    project.verdicts_path.unlink()
    cfg = project.load_config()
    cfg.llm.max_budget_usd = 0.015  #enough for ~1 example of 0.02
    project.save_config(cfg)
    client = FakeClient(cost=0.01)  #2 calls per example = 0.02
    summary = run_check(project, client)
    assert summary.budget_stop is True
    assert summary.checked == 1


def test_example_without_id_column(project: Project):
    write_jsonl_atomic(project.examples_path, [Example(id="only", question="IN?", answer="ABOUT")])
    project.verdicts_path.unlink()
    summary = run_check(project, FakeClient())
    assert summary.checked == 1


def test_search_quality_refuses_to_substitute_pressf_retrieval(project: Project):
    cfg = project.load_config()
    cfg.task = "retrieval_quality"
    project.save_config(cfg)
    project.verdicts_path.unlink()
    with pytest.raises(ValueError, match="requires the retrieved context"):
        run_check(project, FakeClient())
