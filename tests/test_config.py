"""Configuration validation and backward-compatible task names."""

import pytest
from pydantic import ValidationError

from pressf.config import EmbeddingsConfig, canonical_task, parse_retrieval_k


def test_embeddings_config_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EmbeddingsConfig(provider="openai", api_key="not-supported-here")


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (None, "rag_faithfulness"),
        ("search_quality", "retrieval_quality"),
        ("compare_versions", "pairwise_compare"),
    ],
)
def test_canonical_task_preserves_legacy_task_names(task: str | None, expected: str):
    assert canonical_task(task) == expected


def test_parse_retrieval_k_validates_and_deduplicates_cutoffs():
    assert parse_retrieval_k("1, 3, 3, 10") == [1, 3, 10]
    with pytest.raises(ValueError):
        parse_retrieval_k("0,3")
