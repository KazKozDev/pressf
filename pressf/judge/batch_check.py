"""Batch fact-check: three phases of batches instead of a synchronous cycle.

Phase A: whole body stamps → Phase B: whole body verification/answerability
→ Phase C: escalation of the unsure on the older model. Retrieving (between A and B) - local
and fast. Verdicts are written after B and rewritten after C."""

from __future__ import annotations

from typing import Callable

from ..config import Project
from ..io import append_jsonl
from ..llm import prompts
from ..llm.batch import BatchItem, BatchRunner
from ..retrievers.base import Chunk
from ..schemas import (
    AnswerabilityResult,
    Example,
    ExtractedClaims,
    Verdict,
    VerificationResult,
)
from . import CheckSummary, gather_chunks
from .aggregate import aggregate_claims_verdict, aggregate_refusal_verdict


def _stage_b_item(
    ex: Example, extracted: ExtractedClaims, chunks: list[Chunk], model: str, system: str
) -> BatchItem:
    if extracted.is_refusal:
        return BatchItem(
            custom_id=ex.id, model=model, system=system,
            user=prompts.answerability_user(ex, chunks), schema=AnswerabilityResult,
        )
    return BatchItem(
        custom_id=ex.id, model=model, system=system,
        user=prompts.verify_user(ex, extracted.claims, chunks), schema=VerificationResult,
    )


def _aggregate(
    ex_id: str, extracted: ExtractedClaims, parsed, chunks: list[Chunk],
    model: str, escalated: bool, cost: float,
) -> Verdict:
    if extracted.is_refusal:
        return aggregate_refusal_verdict(
            example_id=ex_id, answerability=parsed, chunks=chunks,
            judge_model=model, escalated=escalated, cost_usd=cost,
        )
    return aggregate_claims_verdict(
        example_id=ex_id, extracted=extracted, verification=parsed, chunks=chunks,
        judge_model=model, escalated=escalated, cost_usd=cost,
    )


def run_check_batch(
    project: Project,
    llm_client,
    *,
    force: bool = False,
    limit: int | None = None,
    only_ids: set[str] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> CheckSummary:
    from ..retrievers import build_retriever

    cfg = project.load_config()
    retriever = build_retriever(cfg.retriever, cfg.embeddings)
    system = prompts.judge_system(project.load_guidelines())
    runner = BatchRunner(llm_client.anthropic, poll_seconds=cfg.llm.batch_poll_seconds)
    say = on_status or (lambda s: None)

    existing = set() if force else set(project.load_verdicts())
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
    summary = CheckSummary(skipped_existing=len(examples) - len(todo))
    if only_ids is not None:
        todo = [ex for ex in todo if ex.id in only_ids]
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        return summary
    by_id = {ex.id: ex for ex in todo}

    #── Phase A: stamps ──────────────────────── ────────────────────────
    say(f"phase A: extraction of stamps ({len(todo)}examples)")
    a_out = runner.run(
        [
            BatchItem(custom_id=ex.id, model=cfg.llm.judge_model, system=system,
                      user=prompts.claims_user(ex), schema=ExtractedClaims)
            for ex in todo
        ],
        on_status=say,
    )
    extracted: dict[str, ExtractedClaims] = {}
    costs: dict[str, float] = {}
    for ex in todo:
        out = a_out.get(ex.id)
        if out is None or out.parsed is None:
            say(f"[warn] {ex.id}: phase A failed ({out.error if out else 'no result'}) - pass")
            continue
        extracted[ex.id] = out.parsed
        costs[ex.id] = out.cost_usd

    #── Retriever (local) ────────────────────── ───────────────────────
    chunks_map: dict[str, list[Chunk]] = {
        eid: gather_chunks(retriever, by_id[eid].question,
                           [] if ext.is_refusal else ext.claims, top_k=8)
        for eid, ext in extracted.items()
    }

    #── Phase B: verification ───────────────────── ──────────────────────
    say(f"phase B: verification ({len(extracted)}examples)")
    b_out = runner.run(
        [
            _stage_b_item(by_id[eid], ext, chunks_map[eid], cfg.llm.judge_model, system)
            for eid, ext in extracted.items()
        ],
        on_status=say,
    )
    verdicts: dict[str, Verdict] = {}
    for eid, ext in extracted.items():
        out = b_out.get(eid)
        if out is None or out.parsed is None:
            say(f"[warn] {eid}: phase B failed ({out.error if out else 'no result'}) - pass")
            continue
        verdicts[eid] = _aggregate(
            eid, ext, out.parsed, chunks_map[eid],
            cfg.llm.judge_model, escalated=False, cost=costs[eid] + out.cost_usd,
        )

    #── Phase C: Escalation of Uncertainties
    escalate_ids = [
        eid for eid, v in verdicts.items()
        if v.confidence < cfg.llm.escalation_threshold
        and cfg.llm.escalation_model and cfg.llm.escalation_model != cfg.llm.judge_model
    ]
    if escalate_ids:
        say(f"Phase C: Escalation{len(escalate_ids)}unsure about{cfg.llm.escalation_model}")
        c_out = runner.run(
            [
                _stage_b_item(by_id[eid], extracted[eid], chunks_map[eid],
                              cfg.llm.escalation_model, system)
                for eid in escalate_ids
            ],
            on_status=say,
        )
        for eid in escalate_ids:
            out = c_out.get(eid)
            if out is None or out.parsed is None:
                continue  #we leave the verdict to the younger model
            verdicts[eid] = _aggregate(
                eid, extracted[eid], out.parsed, chunks_map[eid],
                cfg.llm.escalation_model, escalated=True,
                cost=verdicts[eid].cost_usd + out.cost_usd,
            )

    #──Record ──────────────────────────── ────────────────────────────
    for eid, verdict in verdicts.items():
        append_jsonl(project.verdicts_path, verdict)
        summary.checked += 1
        summary.cost_usd += verdict.cost_usd
        summary.escalated += int(verdict.escalated)
        summary.recommendations[verdict.recommendation] = (
            summary.recommendations.get(verdict.recommendation, 0) + 1
        )
    summary.cost_usd = round(summary.cost_usd, 4)
    return summary
