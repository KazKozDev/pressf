"""Mode «exported chunks»: JSONL with {text, source?} - universal fallback
for any exotic database from which chunks can be unloaded."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import RetrieverConfig
from ..schemas import Chunk
from .bm25 import BM25Index


class ChunksFileRetriever:
    def __init__(self, cfg: RetrieverConfig):
        extra = cfg.model_dump()
        path = extra.get("path")
        if not path:
            raise ValueError("retriever.kind=chunks_file requires path parameter (JSONL with chunks)")
        self.path = Path(path).expanduser()
        if not self.path.is_file():
            raise FileNotFoundError(f"File not found:{self.path}")
        docs: list[tuple[str, str]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = row.get("text", "")
                if not text:
                    continue
                docs.append((text, str(row.get("source") or f"chunk_{i}")))
        self._index = BM25Index(docs)

    def search(self, query: str, top_k: int) -> list[Chunk]:
        return self._index.search(query, top_k)

    def healthcheck(self) -> str:
        if len(self._index) == 0:
            raise RuntimeError(f"IN{self.path}there is not a single chunk with text")
        return f"chunks_file: {len(self._index)}chunks (BM25)"
