"""Retriever contract. One for all adapters - see PLAN.md §5."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas import Chunk

__all__ = ["Chunk", "Retriever"]


@runtime_checkable
class Retriever(Protocol):
    def search(self, query: str, top_k: int) -> list[Chunk]:
        """Query → top_k chunks sorted by relevance."""
        ...

    def healthcheck(self) -> str:
        """Human-readable «connected, ~N units in the database». Throws an exception when there is a problem."""
        ...
