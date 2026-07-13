"""Weaviate (v4). Config: url (default http://localhost:8080), grpc_port (default 50051),
api_key?, collection, mode: near_text (collection vectorizer, default) | near_vector (our embedder),
text_field (default text), source_field (default source)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def objects_to_chunks(objects: list[Any], text_field: str, source_field: str) -> list[Chunk]:
    out: list[Chunk] = []
    for obj in objects:
        props = getattr(obj, "properties", None) or {}
        text = props.get(text_field)
        if not text:
            continue
        meta = getattr(obj, "metadata", None)
        distance = getattr(meta, "distance", None) if meta else None
        score = round(1.0 - float(distance), 4) if distance is not None else None
        out.append(
            Chunk(
                text=str(text),
                source=str(props.get(source_field) or getattr(obj, "uuid", "?")),
                score=score,
            )
        )
    return out


class WeaviateRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            import weaviate
            from weaviate.connect import ConnectionParams
        except ImportError as e:
            raise RuntimeError("Need weaviate-client: pip install 'pressf[weaviate]'") from e
        extra = cfg.model_dump()
        collection = extra.get("collection")
        if not collection:
            raise ValueError("weaviate requires the collection parameter")
        auth = None
        if extra.get("api_key"):
            from weaviate.auth import AuthApiKey

            auth = AuthApiKey(extra["api_key"])
        self._client = weaviate.WeaviateClient(
            connection_params=ConnectionParams.from_url(
                extra.get("url", "http://localhost:8080"), grpc_port=int(extra.get("grpc_port", 50051))
            ),
            auth_client_secret=auth,
        )
        self._client.connect()
        self._collection = self._client.collections.get(collection)
        self._mode = extra.get("mode", "near_text")
        self._text_field = extra.get("text_field", "text")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder
        if self._mode == "near_vector" and get_embedder is None:
            raise RuntimeError("weaviate mode=near_vector requires the embeddings section in lazy.yaml")

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        from weaviate.classes.query import MetadataQuery

        meta = MetadataQuery(distance=True)
        if self._mode == "near_vector":
            res = self._collection.query.near_vector(
                near_vector=self._get_embedder()(query), limit=top_k, return_metadata=meta
            )
        else:
            res = self._collection.query.near_text(query=query, limit=top_k, return_metadata=meta)
        return objects_to_chunks(res.objects, self._text_field, self._source_field)

    def healthcheck(self) -> str:
        agg = self._collection.aggregate.over_all(total_count=True)
        n = getattr(agg, "total_count", 0) or 0
        if n == 0:
            raise RuntimeError("Weaviate collection is empty")
        return f"weaviate: collection,{n}objects"
