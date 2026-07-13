"""Qdrant. Config: url, api_key?, collection, text_field (default text), source_field (default source)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def points_to_chunks(points: list[Any], text_field: str, source_field: str) -> list[Chunk]:
    out: list[Chunk] = []
    for p in points:
        payload = getattr(p, "payload", None) or {}
        text = payload.get(text_field)
        if not text:
            continue
        out.append(
            Chunk(
                text=str(text),
                source=str(payload.get(source_field) or getattr(p, "id", "?")),
                score=round(float(getattr(p, "score", 0.0) or 0.0), 4),
            )
        )
    return out


class QdrantRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            from qdrant_client import QdrantClient
        except ImportError as e:
            raise RuntimeError("Need qdrant-client: pip install 'pressf[qdrant]'") from e
        extra = cfg.model_dump()
        self._collection = extra.get("collection")
        if not self._collection:
            raise ValueError("qdrant requires the collection parameter")
        if get_embedder is None:
            raise RuntimeError("qdrant requires embeddings section in lazy.yaml")
        self._client = QdrantClient(url=extra.get("url", "http://localhost:6333"), api_key=extra.get("api_key"))
        self._text_field = extra.get("text_field", "text")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        vec = self._get_embedder()(query)
        if hasattr(self._client, "query_points"):  # qdrant-client >= 1.10
            points = self._client.query_points(
                collection_name=self._collection, query=vec, limit=top_k, with_payload=True
            ).points
        else:
            points = self._client.search(
                collection_name=self._collection, query_vector=vec, limit=top_k, with_payload=True
            )
        return points_to_chunks(points, self._text_field, self._source_field)

    def healthcheck(self) -> str:
        info = self._client.get_collection(self._collection)
        n = getattr(info, "points_count", None) or 0
        if n == 0:
            raise RuntimeError(f"Collection qdrant «{self._collection}» empty")
        return f"qdrant: collection «{self._collection}», {n}points"
