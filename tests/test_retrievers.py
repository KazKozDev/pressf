"""Contract test: one for all adapters (M1 - two; the rest will be added to M2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pressf.config import RetrieverConfig
from pressf.retrievers import build_retriever
from pressf.retrievers.bm25 import BM25Index


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "limits.md").write_text(
        "# Limits\n\nThe basic tariff allows 600 requests per hour.\n\nIf exceeded, HTTP 429 is returned.",
        encoding="utf-8",
    )
    (kb / "auth.md").write_text(
        "# Authentication\n\nThe key is transmitted in the X-Key header.", encoding="utf-8"
    )
    return kb


@pytest.fixture
def chunks_path(tmp_path: Path) -> Path:
    path = tmp_path / "chunks.jsonl"
    rows = [
        {"text": "Basic tariff allows 600 requests per hour", "source": "doc_1"},
        {"text": "The key is transmitted in the X-Key header", "source": "doc_2"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return path


def _contract(retriever):
    """General contract: healthcheck works, the relevant chunk is found first."""
    assert retriever.healthcheck()
    hits = retriever.search("how many requests per hour does the limit allow?", top_k=2)
    assert hits, "a relevant query must find something"
    assert "600" in hits[0].text
    assert hits[0].source
    assert retriever.search("", top_k=3) == []


def test_docs_folder_contract(kb_dir: Path):
    _contract(build_retriever(RetrieverConfig(kind="docs_folder", path=str(kb_dir))))


def test_chunks_file_contract(chunks_path: Path):
    _contract(build_retriever(RetrieverConfig(kind="chunks_file", path=str(chunks_path))))


def test_vector_kind_without_params_gives_clear_error():
    #qdrant without collection crashes meaningfully even before attempting to import the client
    with pytest.raises((ValueError, RuntimeError), match="collection|qdrant"):
        build_retriever(RetrieverConfig(kind="qdrant"))


def test_unknown_kind():
    with pytest.raises(ValueError, match="Unknown kind"):
        build_retriever(RetrieverConfig(kind="wat"))


def test_bm25_ranking():
    idx = BM25Index([
        ("cats love fish", "a"),
        ("dogs love bones and meat", "b"),
        ("the request limit is six hundred", "c"),
    ])
    hits = idx.search("what do dogs like", top_k=3)
    assert hits[0].source == "b"
