"""LanceDB. Config: uri (path to the database), table, text_field (default text), source_field (default source)."""

from __future__ import annotations

from typing import Any, Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def rows_to_chunks(rows: list[dict[str, Any]], text_field: str, source_field: str) -> list[Chunk]:
    out: list[Chunk] = []
    for i, row in enumerate(rows):
        text = row.get(text_field)
        if not text:
            continue
        dist = row.get("_distance")
        out.append(
            Chunk(
                text=str(text),
                source=str(row.get(source_field) or f"row_{i}"),
                score=round(1.0 / (1.0 + float(dist)), 4) if dist is not None else None,
            )
        )
    return out


class LanceDBRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            import lancedb
        except ImportError as e:
            raise RuntimeError("Need lancedb: pip install 'pressf[lancedb]'") from e
        extra = cfg.model_dump()
        uri = extra.get("uri") or extra.get("path")
        table = extra.get("table")
        if not uri or not table:
            raise ValueError("lancedb requires uri (path to database) and table")
        if get_embedder is None:
            raise RuntimeError("lancedb requires embeddings section in lazy.yaml")
        self._table = lancedb.connect(uri).open_table(table)
        self._text_field = extra.get("text_field", "text")
        self._source_field = extra.get("source_field", "source")
        self._get_embedder = get_embedder

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        rows = self._table.search(self._get_embedder()(query)).limit(top_k).to_list()
        return rows_to_chunks(rows, self._text_field, self._source_field)

    def healthcheck(self) -> str:
        n = self._table.count_rows()
        if n == 0:
            raise RuntimeError("The lancedb table is empty")
        return f"lancedb: table,{n}lines"
