"""Estimate before the run: count_tokens on the sample → forecast of the cost of the case."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Project
from ..llm import prompts
from ..llm.client import PRICING
from ..llm.batch import BATCH_DISCOUNT

SAMPLE_SIZE = 3
OUTPUT_TOKENS_GUESS = 500  #average structured-response of the judge
ESCALATION_RATE_GUESS = 0.15


@dataclass
class Estimate:
    n_examples: int
    avg_input_tokens: int
    sync_usd: float
    batch_usd: float


def estimate_check(project: Project, llm_client, *, limit: int | None = None) -> Estimate:
    """Calculates the average length of prompts on a sample and extrapolates.

    Top-down evaluation is fair but rough: verify prompt depends on the ones found
    chunks, we count escalations using ESCALATION_RATE_GUESS."""
    cfg = project.load_config()
    system = (
        prompts.task_system(cfg.task, project.load_guidelines())
        if cfg.task == "agent_trajectory"
        else prompts.judge_system(project.load_guidelines())
    )

    existing = set(project.load_verdicts())
    todo = [ex for ex in project.load_examples() if ex.id not in existing]
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        return Estimate(0, 0, 0.0, 0.0)

    sample = todo[:SAMPLE_SIZE]
    total = 0
    if cfg.task == "agent_trajectory":
        for ex in sample:
            total += llm_client.count_tokens(
                model=cfg.llm.judge_model, system=system, user=prompts.agent_trajectory_user(ex)
            )
        avg_input = total // len(sample)
    else:
        from ..retrievers import build_retriever
        from . import gather_chunks

        assert cfg.retriever is not None
        retriever = build_retriever(cfg.retriever, cfg.embeddings)
        for ex in sample:
            total += llm_client.count_tokens(
                model=cfg.llm.judge_model, system=system, user=prompts.claims_user(ex)
            )
            chunks = gather_chunks(retriever, ex.question, [], top_k=8)
            total += llm_client.count_tokens(
                model=cfg.llm.judge_model,
                system=system,
                user=prompts.verify_user(ex, ["statement for evaluation"] * 3, chunks),
            )
        avg_input = total // len(sample)

    if cfg.llm.provider == "openai_compatible":
        inp = esc_inp = cfg.llm.price_input_per_mtok
        outp = esc_outp = cfg.llm.price_output_per_mtok
    elif cfg.llm.provider == "openai":
        from ..llm.openai_client import _pricing as openai_pricing

        inp, outp = openai_pricing(cfg.llm.judge_model)
        esc_inp, esc_outp = openai_pricing(cfg.llm.escalation_model)
    else:
        inp, outp = PRICING.get(cfg.llm.judge_model, (1.0, 5.0))
        esc_inp, esc_outp = PRICING.get(cfg.llm.escalation_model, (5.0, 25.0))
    output_calls = 1 if cfg.task == "agent_trajectory" else 2
    per_example = avg_input / 1e6 * inp + output_calls * OUTPUT_TOKENS_GUESS / 1e6 * outp
    per_escalation = (avg_input / 2) / 1e6 * esc_inp + OUTPUT_TOKENS_GUESS / 1e6 * esc_outp
    sync_usd = len(todo) * (per_example + ESCALATION_RATE_GUESS * per_escalation)
    return Estimate(
        n_examples=len(todo),
        avg_input_tokens=avg_input,
        sync_usd=round(sync_usd, 4),
        batch_usd=round(sync_usd * BATCH_DISCOUNT, 4),
    )
