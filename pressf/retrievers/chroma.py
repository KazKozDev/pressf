"""Chroma. Config: path (local database) OR host+port (server), collection.
query_mode: text (collection embedding function, default) | vector (our embedder)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def parse_query_result(res: dict[str, Any]) -> list[Chunk]:
    """chroma returns lists of lists (one per request)."""
    docs = (res.get("documents") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0] or [None] * len(docs)
    dists = (res.get("distances") or [[]])[0] or [None] * len(docs)
    out: list[Chunk] = []
    for doc, cid, meta, dist in zip(docs, ids, metas, dists):
        source = str((meta or {}).get("source") or cid)
        score = None if dist is None else round(1.0 - float(dist), 4)
        out.append(Chunk(text=doc, source=source, score=score))
    return out


class ChromaRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            import chromadb
        except ImportError as e:
            raise RuntimeError("Need chromadb: pip install 'pressf[chroma]'") from e
        extra = cfg.model_dump()
        collection = extra.get("collection")
        if not collection:
            raise ValueError("chroma requires the collection parameter")
        if extra.get("host"):
            client = chromadb.HttpClient(host=extra["host"], port=int(extra.get("port", 8000)))
        elif extra.get("path"):
            client = chromadb.PersistentClient(path=extra["path"])
        else:
            raise ValueError("chroma requires path (local database) or host (server)")
        self._collection = client.get_collection(collection)
        self._query_mode = extra.get("query_mode", "text")
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        n = min(top_k, max(self._collection.count(), 1))
        if self._query_mode == "vector":
            if self._get_embedder is None:
                raise RuntimeError("chroma query_mode=vector requires the embeddings section in lazy.yaml")
            res = self._collection.query(query_embeddings=[self._get_embedder()(query)], n_results=n)
        else:
            res = self._collection.query(query_texts=[query], n_results=n)
        return parse_query_result(res)

    def healthcheck(self) -> str:
        count = self._collection.count()
        if count == 0:
            raise RuntimeError("The chroma collection is empty")
        return f"chroma: collection «{self._collection.name}», {count}vectors"
