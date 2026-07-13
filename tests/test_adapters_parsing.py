"""Pure parsers of M2 adapter results - without live database clients."""

from __future__ import annotations

from types import SimpleNamespace

from pressf.retrievers.chroma import parse_query_result
from pressf.retrievers.elastic import hits_to_chunks as es_hits
from pressf.retrievers.faiss_ import rows_to_chunks as faiss_rows
from pressf.retrievers.lancedb_ import rows_to_chunks as lance_rows
from pressf.retrievers.milvus import hits_to_chunks as milvus_hits
from pressf.retrievers.pgvector import rows_to_chunks as pg_rows
from pressf.retrievers.pinecone_ import matches_to_chunks
from pressf.retrievers.qdrant import points_to_chunks


def test_chroma_parse():
    res = {
        "ids": [["a", "b"]],
        "documents": [["text 1", "text 2"]],
        "metadatas": [[{"source": "doc1"}, None]],
        "distances": [[0.2, 0.5]],
    }
    chunks = parse_query_result(res)
    assert chunks[0].source == "doc1" and chunks[0].score == 0.8
    assert chunks[1].source == "b"


def test_qdrant_parse():
    points = [
        SimpleNamespace(id=1, score=0.9, payload={"text": "T", "source": "s1"}),
        SimpleNamespace(id=2, score=0.5, payload={"no_text": True}),  #skipped
    ]
    chunks = points_to_chunks(points, "text", "source")
    assert len(chunks) == 1 and chunks[0].source == "s1"


def test_pgvector_parse():
    rows = [("text", "src", 0.25), ("", None, 0.1)]
    chunks = pg_rows(rows, has_source=True)
    assert len(chunks) == 1 and chunks[0].score == 0.75


def test_pinecone_parse():
    matches = [{"id": "m1", "score": 0.88, "metadata": {"text": "T", "source": "s"}}]
    chunks = matches_to_chunks(matches, "text", "source")
    assert chunks[0].score == 0.88


def test_faiss_parse():
    mapping = [{"text": "a", "source": "d1"}, {"text": "b"}]
    chunks = faiss_rows([1, 0, -1], [0.7, 0.9, 0.0], mapping)
    assert [c.source for c in chunks] == ["row_1", "d1"]  #-1 discarded


def test_milvus_parse():
    hits = [{"id": 5, "distance": 0.33, "entity": {"text": "T", "source": "s"}}]
    chunks = milvus_hits(hits, "text", "source")
    assert chunks[0].source == "s" and chunks[0].score == 0.33


def test_elastic_parse():
    res = {"hits": {"hits": [{"_id": "x", "_score": 3.2, "_source": {"text": "T"}}]}}
    chunks = es_hits(res, "text", "source")
    assert chunks[0].source == "x" and chunks[0].score == 3.2


def test_lancedb_parse():
    rows = [{"text": "T", "source": "s", "_distance": 1.0}]
    chunks = lance_rows(rows, "text", "source")
    assert chunks[0].score == 0.5
