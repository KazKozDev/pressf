"""FAISS. The index does not store texts, so two files are needed:
index_path (binary index) + mapping_path (JSONL: {text, source?} in the order added to the index).
Embedder is required - it was used to build the index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def rows_to_chunks(
    ids: list[int], scores: list[float], mapping: list[dict]
) -> list[Chunk]:
    out: list[Chunk] = []
    for idx, score in zip(ids, scores):
        if idx < 0 or idx >= len(mapping):
            continue
        row = mapping[idx]
        out.append(
            Chunk(
                text=row.get("text", ""),
                source=str(row.get("source") or f"row_{idx}"),
                score=round(float(score), 4),
            )
        )
    return out


class FaissRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            import faiss  # noqa: F401
        except ImportError as e:
            raise RuntimeError("Need faiss: pip install faiss-cpu") from e
        import faiss

        extra = cfg.model_dump()
        index_path = extra.get("index_path") or extra.get("path")
        mapping_path = extra.get("mapping_path")
        if not index_path or not mapping_path:
            raise ValueError("faiss requires index_path and mapping_path (JSONL id→text)")
        if get_embedder is None:
            raise RuntimeError("faiss requires the embeddings section in lazy.yaml (the model used to build the index)")
        self._index = faiss.read_index(str(Path(index_path).expanduser()))
        self._mapping: list[dict] = []
        with Path(mapping_path).expanduser().open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self._mapping.append(json.loads(line))
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        import numpy as np

        vec = np.array([self._get_embedder()(query)], dtype="float32")
        scores, ids = self._index.search(vec, top_k)
        return rows_to_chunks(ids[0].tolist(), scores[0].tolist(), self._mapping)

    def healthcheck(self) -> str:
        n = self._index.ntotal
        if n == 0:
            raise RuntimeError("FAISS-index is empty")
        if n != len(self._mapping):
            raise RuntimeError(
                f"Out of sync: in the index{n}vectors, in mapping -{len(self._mapping)}lines"
            )
        return f"faiss: {n}vectors, dimension{self._index.d}"
