"""JSONL-helpers. The key property is recording reliability:

- append_jsonl writes a line with flush+fsync - a process crash does not lose the solution;
- write_jsonl_atomic — write-tmp+rename for files that are rewritten entirely."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def read_jsonl(path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    out: list[T] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(model.model_validate_json(line))
    return out


def iter_jsonl_raw(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def append_jsonl(path: Path, item: BaseModel) -> None:
    """Add one record with fsync - atomically at the line level."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(item.model_dump_json() + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_jsonl_atomic(path: Path, items: Iterable[BaseModel | dict[str, Any]]) -> None:
    """Rewrite the entire file using tmp+rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for item in items:
            if isinstance(item, BaseModel):
                f.write(item.model_dump_json() + "\n")
            else:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
