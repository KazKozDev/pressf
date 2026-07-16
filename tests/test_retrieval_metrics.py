from __future__ import annotations

import pytest

from pressf.judge.retrieval_metrics import calculate, from_gold, summarize
from pressf.schemas import Chunk


def test_known_binary_ranking_metrics_and_requested_k():
    metrics = calculate([0, 1, 0, 1], total_relevant=2, k_values=[1, 3, 5])

    assert metrics.k == [1, 3, 5]
    assert metrics.precision_at_k == {1: 0.0, 3: pytest.approx(1 / 3), 5: 0.4}
    assert metrics.recall_at_k == {1: 0.0, 3: 0.5, 5: 1.0}
    assert metrics.hit_at_k == {1: 0.0, 3: 1.0, 5: 1.0}
    assert metrics.mrr == 0.5
    assert metrics.map == pytest.approx((1 / 2 + 2 / 4) / 2)


def test_no_docs_and_all_relevant_edge_cases():
    no_docs = calculate([], total_relevant=0, k_values=[1, 3])
    all_relevant = calculate([2, 1], total_relevant=2, k_values=[10])

    assert no_docs.k == [1, 3]
    assert no_docs.precision_at_k == {1: 0.0, 3: 0.0}
    assert no_docs.mrr == 0.0
    assert no_docs.map == 0.0
    assert all_relevant.k == [10]
    assert all_relevant.precision_at_k[10] == 0.2
    assert all_relevant.recall_at_k[10] == 1.0
    assert all_relevant.hit_at_k[10] == 1.0


def test_gold_ids_match_either_document_id_or_source_and_handle_empty_labels():
    chunks = [
        Chunk(text="billing", source="billing.md", id="doc-1"),
        Chunk(text="other", source="faq.md", id="doc-2"),
    ]

    metrics = from_gold(chunks, ["billing.md"], [1, 3])
    empty_gold = from_gold(chunks, [], [1])

    assert metrics.precision_at_k[1] == 1.0
    assert metrics.recall_at_k[1] == 1.0
    assert empty_gold.precision_at_k[1] == 0.0
    assert empty_gold.recall_at_k[1] == 0.0
    assert empty_gold.mrr == 0.0
    assert empty_gold.map == 0.0


def test_gold_metrics_deduplicate_multiple_chunks_from_one_document():
    chunks = [
        Chunk(text="first chunk", source="docA"),
        Chunk(text="second chunk", source="docA"),
    ]

    metrics = from_gold(chunks, ["docA"], [2])

    assert metrics.precision_at_k[2] == 1.0
    assert metrics.recall_at_k[2] == 1.0
    assert metrics.map == 1.0


def test_ndcg_uses_graded_relevance_gain():
    metrics = calculate([1, 2], total_relevant=2, k_values=[2])

    # DCG=(1 + 3/log2(3)); ideal=(3 + 1/log2(3)).
    assert metrics.ndcg_at_k[2] == pytest.approx((1 + 3 / 1.5849625) / (3 + 1 / 1.5849625))


def test_summary_averages_only_examples_with_the_cutoff():
    first = calculate([1, 0], total_relevant=1, k_values=[1, 3])
    second = calculate([0], total_relevant=0, k_values=[1, 3])

    summary = summarize([first, second])

    assert summary is not None
    assert summary.examples == 2
    assert summary.k == [1, 3]
    assert summary.precision_at_k[1] == 0.5
    assert summary.precision_at_k[3] == pytest.approx(1 / 6)
