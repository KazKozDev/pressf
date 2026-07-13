"""Elasticsearch / OpenSearch - one adapter, two clients.

Config: url, api_key?, index, flavor: elasticsearch (default) | opensearch
mode: bm25 (default - no embeddings!) | knn, text_field (default text),
vec_field (default embedding), source_field (default source)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def hits_to_chunks(res: dict[str, Any], text_field: str, source_field: str) -> list[Chunk]:
    hits = (res.get("hits") or {}).get("hits") or []
    out: list[Chunk] = []
    for h in hits:
        src = h.get("_source") or {}
        text = src.get(text_field)
        if not text:
            continue
        out.append(
            Chunk(
                text=str(text),
                source=str(src.get(source_field) or h.get("_id", "?")),
                score=round(float(h.get("_score") or 0.0), 4),
            )
        )
    return out


class ElasticRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        extra = cfg.model_dump()
        self._index = extra.get("index")
        if not self._index:
            raise ValueError("elastic requires index parameter")
        flavor = extra.get("flavor", "elasticsearch")
        url = extra.get("url", "http://localhost:9200")
        if flavor == "opensearch":
            try:
                from opensearchpy import OpenSearch
            except ImportError as e:
                raise RuntimeError("Need opensearch-py: pip install opensearch-py") from e
            self._client = OpenSearch(url)
        else:
            try:
                from elasticsearch import Elasticsearch
            except ImportError as e:
                raise RuntimeError("Need elasticsearch: pip install 'pressf[elastic]'") from e
            kwargs = {"api_key": extra["api_key"]} if extra.get("api_key") else {}
            self._client = Elasticsearch(url, **kwargs)
        self._mode = extra.get("mode", "bm25")
        self._text_field = extra.get("text_field", "text")
        self._vec_field = extra.get("vec_field", "embedding")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder
        if self._mode == "knn" and get_embedder is None:
            raise RuntimeError("elastic mode=knn requires embeddings section in lazy.yaml")

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        if self._mode == "knn":
            res = self._client.search(
                index=self._index,
                knn={
                    "field": self._vec_field,
                    "query_vector": self._get_embedder()(query),
                    "k": top_k,
                    "num_candidates": top_k * 10,
                },
                size=top_k,
            )
        else:
            res = self._client.search(
                index=self._index,
                query={"match": {self._text_field: query}},
                size=top_k,
            )
        body = res.body if hasattr(res, "body") else dict(res)
        return hits_to_chunks(body, self._text_field, self._source_field)

    def healthcheck(self) -> str:
        res = self._client.count(index=self._index)
        n = res.get("count", 0) if isinstance(res, dict) else getattr(res, "body", {}).get("count", 0)
        if not n:
            raise RuntimeError(f"Index «{self._index}» empty")
        return f"elastic ({self._mode}): index «{self._index}», {n}documents"
