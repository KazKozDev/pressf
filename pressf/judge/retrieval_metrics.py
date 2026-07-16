"""Deterministic IR ranking metrics for Search Quality's ordered context."""

from __future__ import annotations

from collections.abc import Iterable
from math import log2

from ..schemas import Chunk, RetrievalMetrics, RetrievalMetricsSummary


def _requested_k(k_values: Iterable[int]) -> list[int]:
    """Keep requested cutoffs: absent results count as non-relevant for precision."""
    return list(dict.fromkeys(k_values))


def _dcg(relevances: list[int], k: int) -> float:
    return sum(
        (2 ** relevance - 1) / log2(rank + 1)
        for rank, relevance in enumerate(relevances[:k], 1)
    )


def _average_precision(binary: list[int], total_relevant: int) -> float:
    if total_relevant <= 0:
        return 0.0
    hits = 0
    total = 0.0
    for rank, relevance in enumerate(binary, 1):
        if relevance:
            hits += 1
            total += hits / rank
    return total / total_relevant


def from_gold(
    chunks: list[Chunk], relevant_ids: list[str], k_values: list[int]
) -> RetrievalMetrics:
    """Calculate binary metrics from an explicit, deterministic relevance set."""
    relevant = set(relevant_ids)
    matched_ids = [
        chunk.id if chunk.id in relevant else chunk.source if chunk.source in relevant else None
        for chunk in chunks
    ]
    return calculate(
        [int(identifier is not None) for identifier in matched_ids],
        total_relevant=len(relevant),
        k_values=k_values,
        relevance_ids=matched_ids,
    )


def from_graded(
    chunks: list[Chunk], relevances: list[int], k_values: list[int]
) -> RetrievalMetrics | None:
    """Calculate metrics from one grade per logged chunk; incomplete grades are unusable."""
    if len(relevances) != len(chunks) or any(value not in (0, 1, 2) for value in relevances):
        return None
    return calculate(relevances, total_relevant=sum(value >= 1 for value in relevances), k_values=k_values)


def calculate(
    relevances: list[int],
    total_relevant: int,
    k_values: list[int],
    relevance_ids: list[str | None] | None = None,
) -> RetrievalMetrics:
    """Implement precision, recall, hit, MRR, nDCG and MAP on a ranked list."""
    binary = [int(value >= 1) for value in relevances]
    if relevance_ids is not None and len(relevance_ids) != len(relevances):
        raise ValueError("relevance_ids must align with relevances")
    unique_binary = binary
    if relevance_ids is not None:
        seen_ids: set[str] = set()
        unique_binary = []
        for relevance, identifier in zip(binary, relevance_ids):
            is_new_relevant = relevance and identifier is not None and identifier not in seen_ids
            if is_new_relevant:
                seen_ids.add(identifier)
            unique_binary.append(int(is_new_relevant))

    used_k = _requested_k(k_values)
    precision: dict[int, float] = {}
    recall: dict[int, float] = {}
    ndcg: dict[int, float] = {}
    hit: dict[int, float] = {}
    ideal_relevances = sorted(relevances, reverse=True)
    for k in used_k:
        relevant_at_k = sum(binary[:k])
        unique_relevant_at_k = sum(unique_binary[:k])
        precision[k] = relevant_at_k / k
        recall[k] = unique_relevant_at_k / total_relevant if total_relevant else 0.0
        hit[k] = float(relevant_at_k > 0)
        ideal = _dcg(ideal_relevances, k)
        ndcg[k] = _dcg(relevances, k) / ideal if ideal else 0.0
    first = next((rank for rank, value in enumerate(binary, 1) if value), None)
    return RetrievalMetrics(
        k=used_k,
        precision_at_k=precision,
        recall_at_k=recall,
        ndcg_at_k=ndcg,
        hit_at_k=hit,
        mrr=1 / first if first else 0.0,
        map=_average_precision(unique_binary, total_relevant),
    )


def summarize(metrics: Iterable[RetrievalMetrics]) -> RetrievalMetricsSummary | None:
    """Mean each metric only across rows where that cutoff is available."""
    rows = list(metrics)
    if not rows:
        return None
    all_k = sorted({k for row in rows for k in row.k})

    def mean_by_k(field: str) -> dict[int, float]:
        return {
            k: sum(getattr(row, field)[k] for row in rows if k in getattr(row, field))
            / sum(k in getattr(row, field) for row in rows)
            for k in all_k
        }

    return RetrievalMetricsSummary(
        examples=len(rows),
        k=all_k,
        precision_at_k=mean_by_k("precision_at_k"),
        recall_at_k=mean_by_k("recall_at_k"),
        ndcg_at_k=mean_by_k("ndcg_at_k"),
        hit_at_k=mean_by_k("hit_at_k"),
        mrr=sum(row.mrr for row in rows) / len(rows),
        map=sum(row.map for row in rows) / len(rows),
    )
