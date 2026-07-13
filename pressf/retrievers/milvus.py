"""Milvus. Config: uri (default http://localhost:19530), token?, collection,
vec_field (default vector), text_field (default text), source_field (default source)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def hits_to_chunks(hits: list[Any], text_field: str, source_field: str) -> list[Chunk]:
    out: list[Chunk] = []
    for h in hits:
        entity = h.get("entity", {}) if isinstance(h, dict) else getattr(h, "entity", {})
        text = entity.get(text_field)
        if not text:
            continue
        distance = h.get("distance") if isinstance(h, dict) else getattr(h, "distance", None)
        out.append(
            Chunk(
                text=str(text),
                source=str(entity.get(source_field) or h.get("id", "?")),
                score=round(float(distance), 4) if distance is not None else None,
            )
        )
    return out


class MilvusRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            from pymilvus import MilvusClient
        except ImportError as e:
            raise RuntimeError("Need pymilvus: pip install 'pressf[milvus]'") from e
        extra = cfg.model_dump()
        self._collection = extra.get("collection")
        if not self._collection:
            raise ValueError("milvus requires the collection parameter")
        if get_embedder is None:
            raise RuntimeError("milvus requires embeddings section in lazy.yaml")
        self._client = MilvusClient(uri=extra.get("uri", "http://localhost:19530"), token=extra.get("token", ""))
        self._vec_field = extra.get("vec_field", "vector")
        self._text_field = extra.get("text_field", "text")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        res = self._client.search(
            collection_name=self._collection,
            data=[self._get_embedder()(query)],
            limit=top_k,
            anns_field=self._vec_field,
            output_fields=[self._text_field, self._source_field],
        )
        hits = res[0] if res else []
        return hits_to_chunks(list(hits), self._text_field, self._source_field)

    def healthcheck(self) -> str:
        stats = self._client.get_collection_stats(self._collection)
        n = int(stats.get("row_count", 0)) if isinstance(stats, dict) else 0
        if n == 0:
            raise RuntimeError(f"Collection milvus «{self._collection}» empty")
        return f"milvus: collection «{self._collection}», {n}lines"
