"""Mode «folder with documents»: we read, chunk and index ourselves.

The default and most «for a fool» mode - it doesn’t require you to know which one you have
vector base. In M1 the index is BM25; M2 will add an option with embeddings."""

from __future__ import annotations

from pathlib import Path

from ..config import RetrieverConfig
from ..schemas import Chunk
from .bm25 import BM25Index

DEFAULT_GLOBS = ("**/*.md", "**/*.txt", "**/*.rst")
CHUNK_CHARS = 1500
OVERLAP_PARAGRAPHS = 1


def chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """We cut into paragraphs, glue up to ~max_chars, overlap - the last paragraph."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paragraphs:
        if buf and size + len(p) > max_chars:
            chunks.append("\n\n".join(buf))
            buf = buf[-OVERLAP_PARAGRAPHS:]
            size = sum(len(x) for x in buf)
        buf.append(p)
        size += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


class DocsFolderRetriever:
    def __init__(self, cfg: RetrieverConfig):
        extra = cfg.model_dump()
        path = extra.get("path")
        if not path:
            raise ValueError("retriever.kind=docs_folder requires the path parameter (folder with documents)")
        self.path = Path(path).expanduser()
        if not self.path.is_dir():
            raise FileNotFoundError(f"Folder not found:{self.path}")
        globs = extra.get("glob")
        globs = [globs] if isinstance(globs, str) else (globs or list(DEFAULT_GLOBS))
        docs: list[tuple[str, str]] = []
        self.n_files = 0
        for pattern in globs:
            for fp in sorted(self.path.glob(pattern)):
                if not fp.is_file():
                    continue
                self.n_files += 1
                rel = fp.relative_to(self.path).as_posix()
                pieces = chunk_text(fp.read_text(encoding="utf-8", errors="replace"))
                for i, piece in enumerate(pieces):
                    docs.append((piece, f"{rel}#{i}"))
        self._index = BM25Index(docs)

    def search(self, query: str, top_k: int) -> list[Chunk]:
        return self._index.search(query, top_k)

    def healthcheck(self) -> str:
        if len(self._index) == 0:
            raise RuntimeError(f"IN{self.path}no documents found for masks")
        return f"docs_folder: {self.n_files}files,{len(self._index)}chunks (BM25)"
