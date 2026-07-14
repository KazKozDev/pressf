"""Configuration validation and backward-compatible task names."""

import pytest
from pydantic import ValidationError

from pressf.config import EmbeddingsConfig, canonical_task


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
