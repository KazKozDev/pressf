"""Pinecone. Config: api_key (or PINECONE_API_KEY from the environment), index, namespace?,
text_field (default text), source_field (default source)."""

from __future__ import annotations

import os
from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def matches_to_chunks(matches: list[Any], text_field: str, source_field: str) -> list[Chunk]:
    out: list[Chunk] = []
    for m in matches:
        meta = (m.get("metadata") if isinstance(m, dict) else getattr(m, "metadata", None)) or {}
        text = meta.get(text_field)
        if not text:
            continue
        mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", "?")
        score = m.get("score") if isinstance(m, dict) else getattr(m, "score", None)
        out.append(
            Chunk(
                text=str(text),
                source=str(meta.get(source_field) or mid),
                score=round(float(score), 4) if score is not None else None,
            )
        )
    return out


class PineconeRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            from pinecone import Pinecone
        except ImportError as e:
            raise RuntimeError("Need pinecone: pip install 'pressf[pinecone]'") from e
        extra = cfg.model_dump()
        index = extra.get("index")
        if not index:
            raise ValueError("pinecone requires index parameter")
        api_key = extra.get("api_key") or os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("pinecone requires api_key (in the config or PINECONE_API_KEY)")
        if get_embedder is None:
            raise RuntimeError("pinecone requires embeddings section in lazy.yaml")
        self._index = Pinecone(api_key=api_key).Index(index)
        self._namespace = extra.get("namespace")
        self._text_field = extra.get("text_field", "text")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        res = self._index.query(
            vector=self._get_embedder()(query),
            top_k=top_k,
            include_metadata=True,
            namespace=self._namespace,
        )
        matches = res.get("matches") if isinstance(res, dict) else getattr(res, "matches", [])
        return matches_to_chunks(matches or [], self._text_field, self._source_field)

    def healthcheck(self) -> str:
        stats = self._index.describe_index_stats()
        total = stats.get("total_vector_count") if isinstance(stats, dict) else getattr(stats, "total_vector_count", 0)
        if not total:
            raise RuntimeError("pinecone index is empty")
        return f"pinecone: {total}vectors"
