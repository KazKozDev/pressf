"""Adapter registry and factory. Full list of kind - PLAN.md §5.2."""

from __future__ import annotations

import importlib
from typing import Callable

from ..config import EmbeddingsConfig, RetrieverConfig
from .base import Retriever

#kind → (module, class). Lazy loading: database clients - extras dependencies.
_ADAPTERS: dict[str, tuple[str, str]] = {
    "docs_folder": ("pressf.retrievers.docs_folder", "DocsFolderRetriever"),
    "chunks_file": ("pressf.retrievers.chunks_file", "ChunksFileRetriever"),
    "chroma": ("pressf.retrievers.chroma", "ChromaRetriever"),
    "faiss": ("pressf.retrievers.faiss_", "FaissRetriever"),
    "qdrant": ("pressf.retrievers.qdrant", "QdrantRetriever"),
    "pgvector": ("pressf.retrievers.pgvector", "PgvectorRetriever"),
    "pinecone": ("pressf.retrievers.pinecone_", "PineconeRetriever"),
    "weaviate": ("pressf.retrievers.weaviate_", "WeaviateRetriever"),
    "milvus": ("pressf.retrievers.milvus", "MilvusRetriever"),
    "elastic": ("pressf.retrievers.elastic", "ElasticRetriever"),
    "lancedb": ("pressf.retrievers.lancedb_", "LanceDBRetriever"),
}

#Adapters without LLM embedder (BM25 / server vectorization)
_NO_EMBEDDER = {"docs_folder", "chunks_file"}


def available_kinds() -> list[str]:
    return list(_ADAPTERS)


def build_retriever(
    cfg: RetrieverConfig, embeddings: EmbeddingsConfig | None = None
) -> Retriever:
    if cfg.kind not in _ADAPTERS:
        raise ValueError(
            f"Unknown kind of retriever:{cfg.kind}. Available:{', '.join(available_kinds())}"
        )
    module_name, class_name = _ADAPTERS[cfg.kind]
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)

    if cfg.kind in _NO_EMBEDDER:
        return cls(cfg)

    #embedder is built lazily and once: heavy initialization (model/client)
    #not executed until the adapter actually needs the request vector
    _cache: list[Callable[[str], list[float]]] = []

    def get_embedder() -> Callable[[str], list[float]]:
        if not _cache:
            from ..embeddings import build_embedder

            _cache.append(build_embedder(embeddings))
        return _cache[0]

    return cls(cfg, get_embedder)
