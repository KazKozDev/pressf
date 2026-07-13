"""Judge pipeline: claims → retrieve → verify → aggregate (+ escalation).

The judge accepts client as a parameter (DI) - in tests it is replaced by a fake."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel

from ..config import LLMConfig, Project
from ..io import append_jsonl
from ..llm import prompts
from ..retrievers.base import Chunk, Retriever
from ..schemas import (
    AnswerabilityResult,
    Example,
    ExtractedClaims,
    PairwiseCompareResult,
    PolicyCheckResult,
    SearchQualityResult,
    Verdict,
    VerificationResult,
)
from .aggregate import (
    aggregate_claims_verdict,
    aggregate_pairwise_compare_verdict,
    aggregate_policy_verdict,
    aggregate_refusal_verdict,
    aggregate_retrieval_quality_verdict,
)

T = TypeVar("T", bound=BaseModel)


class ParseClient(Protocol):
    def parse(
        self, *, model: str, system: str, user: str, schema: type[T], max_tokens: int = ...
    ) -> tuple[T, float]: ...


class BudgetExceeded(RuntimeError):
    def __init__(self, spent: float, budget: float):
        super().__init__(f"Budget exhausted: $ spent{spent:.2f}from ${budget:.2f}")
        self.spent = spent
        self.budget = budget


def gather_chunks(
    retriever: Retriever, question: str, claims: list[str], top_k: int
) -> list[Chunk]:
    """The search is wider than that of the person being checked RAG: question + each mark as a request,
    dedup, cap on 2*top_k best."""
    seen: set[tuple[str, str]] = set()
    merged: list[Chunk] = []
    for query in [question, *claims]:
        for ch in retriever.search(query, top_k):
            key = (ch.source, ch.text)
            if key not in seen:
                seen.add(key)
                merged.append(ch)
    merged.sort(key=lambda c: c.score or 0.0, reverse=True)
    return merged[: top_k * 2]


def context_chunks(ex: Example, retriever: Retriever) -> list[Chunk]:
    """Use logged RAG context when present; otherwise search the configured corpus.

    The fallback is appropriate for Truth Check and Compare Versions. Retrieval
    Quality is guarded in run_check: there, a fallback would grade PressF's own
    retriever instead of the system being evaluated.
    """
    if ex.context:
        return [
            Chunk(text=item.text, source=item.source or "provided context", score=None)
            for item in ex.context
        ]
    return gather_chunks(retriever, ex.question, [ex.answer], top_k=8)


def check_example(
    client: ParseClient,
    retriever: Retriever,
    cfg: LLMConfig,
    system_prompt: str,
    ex: Example,
    *,
    task: str = "rag_faithfulness",
) -> Verdict:
    """A complete fact check of one example."""
    cost = 0.0
    if task == "policy_compliance":
        chunks = gather_chunks(retriever, ex.question, [ex.answer], top_k=8)

        def run_policy(model: str, escalated: bool, base_cost: float) -> Verdict:
            result, c = client.parse(
                model=model,
                system=system_prompt,
                user=prompts.policy_user(ex, chunks),
                schema=PolicyCheckResult,
            )
            return aggregate_policy_verdict(
                example_id=ex.id,
                result=result,
                chunks=chunks,
                judge_model=model,
                escalated=escalated,
                cost_usd=base_cost + c,
            )

        verdict = run_policy(cfg.judge_model, escalated=False, base_cost=0.0)
        if (
            verdict.confidence < cfg.escalation_threshold
            and cfg.escalation_model
            and cfg.escalation_model != cfg.judge_model
        ):
            verdict = run_policy(cfg.escalation_model, escalated=True, base_cost=verdict.cost_usd)
        return verdict

    if task == "retrieval_quality":
        chunks = context_chunks(ex, retriever)

        def run_search(model: str, escalated: bool, base_cost: float) -> Verdict:
            result, c = client.parse(
                model=model,
                system=system_prompt,
                user=prompts.retrieval_quality_user(ex, chunks),
                schema=SearchQualityResult,
            )
            return aggregate_retrieval_quality_verdict(
                example_id=ex.id,
                result=result,
                chunks=chunks,
                judge_model=model,
                escalated=escalated,
                cost_usd=base_cost + c,
            )

        verdict = run_search(cfg.judge_model, escalated=False, base_cost=0.0)
        if (
            verdict.confidence < cfg.escalation_threshold
            and cfg.escalation_model
            and cfg.escalation_model != cfg.judge_model
        ):
            verdict = run_search(cfg.escalation_model, escalated=True, base_cost=verdict.cost_usd)
        return verdict

    if task == "pairwise_compare":
        chunks = context_chunks(ex, retriever)

        def run_pairwise(model: str, escalated: bool, base_cost: float) -> Verdict:
            result, c = client.parse(
                model=model,
                system=system_prompt,
                user=prompts.pairwise_compare_user(ex, chunks),
                schema=PairwiseCompareResult,
            )
            return aggregate_pairwise_compare_verdict(
                example_id=ex.id,
                result=result,
                chunks=chunks,
                judge_model=model,
                escalated=escalated,
                cost_usd=base_cost + c,
            )

        verdict = run_pairwise(cfg.judge_model, escalated=False, base_cost=0.0)
        if (
            verdict.confidence < cfg.escalation_threshold
            and cfg.escalation_model
            and cfg.escalation_model != cfg.judge_model
        ):
            verdict = run_pairwise(cfg.escalation_model, escalated=True, base_cost=verdict.cost_usd)
        return verdict

    #1. Stamps
    extracted, c = client.parse(
        model=cfg.judge_model,
        system=system_prompt,
        user=prompts.claims_user(ex),
        schema=ExtractedClaims,
    )
    cost += c

    def run_verdict(model: str, escalated: bool, base_cost: float) -> Verdict:
        nonlocal cost
        if extracted.is_refusal:
            chunks = gather_chunks(retriever, ex.question, [], top_k=8)
            answerability, c2 = client.parse(
                model=model,
                system=system_prompt,
                user=prompts.answerability_user(ex, chunks),
                schema=AnswerabilityResult,
            )
            cost = base_cost + c2
            return aggregate_refusal_verdict(
                example_id=ex.id,
                answerability=answerability,
                chunks=chunks,
                judge_model=model,
                escalated=escalated,
                cost_usd=cost,
            )
        chunks = gather_chunks(retriever, ex.question, extracted.claims, top_k=8)
        verification, c2 = client.parse(
            model=model,
            system=system_prompt,
            user=prompts.verify_user(ex, extracted.claims, chunks),
            schema=VerificationResult,
        )
        cost = base_cost + c2
        return aggregate_claims_verdict(
            example_id=ex.id,
            extracted=extracted,
            verification=verification,
            chunks=chunks,
            judge_model=model,
            escalated=escalated,
            cost_usd=cost,
        )

    verdict = run_verdict(cfg.judge_model, escalated=False, base_cost=cost)

    #2. Escalation of an uncertain verdict by a senior model
    if (
        verdict.confidence < cfg.escalation_threshold
        and cfg.escalation_model
        and cfg.escalation_model != cfg.judge_model
    ):
        verdict = run_verdict(cfg.escalation_model, escalated=True, base_cost=cost)

    return verdict


@dataclass
class CheckSummary:
    checked: int = 0
    skipped_existing: int = 0
    cost_usd: float = 0.0
    recommendations: dict[str, int] = field(default_factory=dict)
    escalated: int = 0
    budget_stop: bool = False


def run_check(
    project: Project,
    client: ParseClient,
    *,
    force: bool = False,
    limit: int | None = None,
    only_ids: set[str] | None = None,
    on_progress: Callable[[Example, Verdict], None] | None = None,
) -> CheckSummary:
    """Running a fact check on the body. Idempotent: already verified ids are skipped.
    Verdicts are added to jsonl as soon as they are ready."""
    from ..retrievers import build_retriever

    cfg = project.load_config()
    retriever = build_retriever(cfg.retriever)
    system_prompt = prompts.task_system(cfg.task, project.load_guidelines())

    existing = set() if force else set(project.load_verdicts())
    summary = CheckSummary()

    examples = project.load_examples()
    if cfg.task == "retrieval_quality":
        missing_context = [ex.id for ex in examples if not ex.context]
        if missing_context:
            sample = ", ".join(missing_context[:5])
            suffix = "…" if len(missing_context) > 5 else ""
            raise ValueError(
                "Search Quality requires the retrieved context from the system being evaluated. "
                f"Missing context for {len(missing_context)} example(s): {sample}{suffix}. "
                "Map the context column and ingest again; PressF will not substitute its own search."
            )
    todo = [ex for ex in examples if ex.id not in existing]
    summary.skipped_existing = len(examples) - len(todo)
    if only_ids is not None:
        todo = [ex for ex in todo if ex.id in only_ids]
    if limit is not None:
        todo = todo[:limit]

    for ex in todo:
        if summary.cost_usd >= cfg.llm.max_budget_usd:
            summary.budget_stop = True
            break
        verdict = check_example(client, retriever, cfg.llm, system_prompt, ex, task=cfg.task)
        append_jsonl(project.verdicts_path, verdict)
        summary.checked += 1
        summary.cost_usd += verdict.cost_usd
        summary.escalated += int(verdict.escalated)
        summary.recommendations[verdict.recommendation] = (
            summary.recommendations.get(verdict.recommendation, 0) + 1
        )
        if on_progress:
            on_progress(ex, verdict)

    summary.cost_usd = round(summary.cost_usd, 4)
    return summary
