"""pgvector. Config: dsn, table, text_col (default text), vec_col (default embedding),
source_col (optional). The metric is cosine (operator <=>)."""

from __future__ import annotations

from typing import Callable

from ..config import RetrieverConfig
from ..schemas import Chunk


def rows_to_chunks(rows: list[tuple], has_source: bool) -> list[Chunk]:
    out: list[Chunk] = []
    for i, row in enumerate(rows):
        text = row[0]
        if not text:
            continue
        source = str(row[1]) if has_source and row[1] is not None else f"row_{i}"
        dist = float(row[-1])
        out.append(Chunk(text=str(text), source=source, score=round(1.0 - dist, 4)))
    return out


class PgvectorRetriever:
    def __init__(self, cfg: RetrieverConfig, get_embedder: Callable | None = None):
        try:
            import psycopg
        except ImportError as e:
            raise RuntimeError("Need psycopg: pip install 'pressf[pgvector]'") from e
        extra = cfg.model_dump()
        dsn = extra.get("dsn")
        self._table = extra.get("table")
        if not dsn or not self._table:
            raise ValueError("pgvector requires dsn and table")
        if get_embedder is None:
            raise RuntimeError("pgvector requires the embeddings section in lazy.yaml")
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._text_col = extra.get("text_col", "text")
        self._vec_col = extra.get("vec_col", "embedding")
        self._source_col = extra.get("source_col")
        self._get_embedder = get_embedder

    def _sql(self) -> str:
        from psycopg import sql

        cols = [sql.Identifier(self._text_col)]
        if self._source_col:
            cols.append(sql.Identifier(self._source_col))
        return sql.SQL(
            "SELECT {cols}, ({vec} <=> %s::vector) AS dist FROM {table} ORDER BY dist LIMIT %s"
        ).format(
            cols=sql.SQL(", ").join(cols),
            vec=sql.Identifier(self._vec_col),
            table=sql.Identifier(self._table),
        ).as_string(self._conn)

    def search(self, query: str, top_k: int) -> list[Chunk]:
        if not query.strip():
            return []
        vec = self._get_embedder()(query)
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"
        with self._conn.cursor() as cur:
            cur.execute(self._sql(), (vec_literal, top_k))
            rows = cur.fetchall()
        return rows_to_chunks(rows, has_source=bool(self._source_col))

    def healthcheck(self) -> str:
        from psycopg import sql

        with self._conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT count(*) FROM {t}").format(t=sql.Identifier(self._table)))
            n = cur.fetchone()[0]
        if n == 0:
            raise RuntimeError(f"Table{self._table}empty")
        return f"pgvector: table «{self._table}», {n}lines"
