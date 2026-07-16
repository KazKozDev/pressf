"""Normalization of raw strings in Example: column mapping, validation, dedup, report."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ..config import Project
from ..io import write_jsonl_atomic
from ..schemas import ContextChunk, DialogTurn, Example, TrajectoryStep


def _parse_dialog(value: Any) -> list[DialogTurn] | None:
    """Dialogue from the logs: JSON-array {role, content}. User/assistant roles."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, list):
        return None
    turns: list[DialogTurn] = []
    for item in value:
        if isinstance(item, dict) and item.get("content"):
            role = item.get("role")
            role = "assistant" if role not in ("user", "assistant") else role
            turns.append(DialogTurn(role=role, content=str(item["content"])))
    return turns or None


class ColumnMapping(BaseModel):
    question: str
    answer: str
    context: str | None = None
    relevant: str | None = None
    dialog: str | None = None  #column with multi-way dialog (JSON-array {role, content})
    trajectory: str | None = None
    id: str | None = None


@dataclass
class IngestResult:
    accepted: list[Example] = field(default_factory=list)
    rejected: list[tuple[int, str]] = field(default_factory=list)  #(line number, reason)
    duplicates: int = 0

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected) + self.duplicates


_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower())


def _parse_context(value: Any) -> list[ContextChunk] | None:
    """The context in the logs can be: JSON-array of strings/objects, or already a list."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [ContextChunk(text=value)]
    if isinstance(value, list):
        out: list[ContextChunk] = []
        for item in value:
            if isinstance(item, str):
                out.append(ContextChunk(text=item))
            elif isinstance(item, dict) and item.get("text"):
                out.append(ContextChunk(
                    text=str(item["text"]), source=item.get("source"), id=item.get("id")
                ))
        return out or None
    return None


def _parse_relevant_ids(value: Any) -> list[str] | None:
    """Gold relevance is a JSON array of source or document identifiers."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid relevant_ids JSON: {exc.msg}") from exc
    if not isinstance(value, list):
        raise ValueError("relevant_ids must be a JSON array")
    return list(dict.fromkeys(str(item) for item in value))


def _parse_trajectory(value: Any) -> list[TrajectoryStep] | None:
    """Normalize native/trace trajectory input and assign stable one-based indices."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid trajectory JSON: {exc.msg}") from exc
    if not isinstance(value, list):
        raise ValueError("trajectory must be an array of steps")
    try:
        return [TrajectoryStep.model_validate({**step, "index": index})
                for index, step in enumerate(value, 1)]
    except Exception as exc:
        raise ValueError(f"invalid trajectory: {exc}") from exc


def example_key(
    question: str, answer: str, trajectory: list[TrajectoryStep] | None = None
) -> tuple[str, ...]:
    """Deduplicate normal examples by Q/A and trajectories by their full visible execution."""
    key: tuple[str, ...] = (_normalize(question), _normalize(answer))
    if trajectory is None:
        return key
    trace = json.dumps(
        [step.model_dump(mode="json") for step in trajectory],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (*key, trace)


def normalize_rows(
    rows: list[dict[str, Any]],
    mapping: ColumnMapping,
    raw_file: str = "",
    *,
    existing_keys: set[tuple[str, ...]] | None = None,
    id_start: int = 1,
) -> IngestResult:
    """existing_keys/id_start - for additional loading (lazy add): dedup versus already
    downloaded examples and continuation of id numbering."""
    result = IngestResult()
    seen: set[tuple[str, ...]] = set(existing_keys or ())
    for i, row in enumerate(rows, 1):
        if "_parse_error" in row:
            result.rejected.append((i, str(row["_parse_error"])))
            continue
        #Trace exports can be mixed with regular rows; structural detection is deterministic.
        if any(key in row for key in ("messages", "child_runs", "observations", "trajectory")):
            from .traces import detect_trace_format, trace_to_row
            detected = detect_trace_format(row)
            parsed = trace_to_row(row)
            if parsed is None:
                result.rejected.append((i, f"{detected}: trajectory trace could not be parsed"))
                continue
            row = parsed
        dialog = _parse_dialog(row.get(mapping.dialog)) if mapping.dialog else None
        #from the dialogue we display question/answer: the last comment is user and the last answer is assistant
        if dialog:
            last_user = next((t.content for t in reversed(dialog) if t.role == "user"), "")
            last_assistant = next((t.content for t in reversed(dialog) if t.role == "assistant"), "")
            question = str(row.get(mapping.question) or last_user).strip()
            answer = str(row.get(mapping.answer) or last_assistant).strip()
        else:
            question = str(row.get(mapping.question) or "").strip()
            answer = str(row.get(mapping.answer) or "").strip()
        if not question:
            result.rejected.append((i, f"empty column «{mapping.question}» (question)"))
            continue
        if not answer:
            result.rejected.append((i, f"empty column «{mapping.answer}» (answer)"))
            continue
        trajectory_value = row.get(mapping.trajectory) if mapping.trajectory else row.get("trajectory")
        try:
            trajectory = _parse_trajectory(trajectory_value)
            relevant_ids = _parse_relevant_ids(row.get(mapping.relevant)) if mapping.relevant else None
        except ValueError as exc:
            result.rejected.append((i, str(exc)))
            continue
        key = example_key(question, answer, trajectory)
        if key in seen:
            result.duplicates += 1
            continue
        seen.add(key)
        source_id_column = mapping.id or ("id" if row.get("_trace_format") and row.get("id") else None)
        ex_id = (
            str(row[source_id_column])
            if source_id_column and row.get(source_id_column)
            else f"ex_{id_start + len(result.accepted):04d}"
        )
        result.accepted.append(Example(
            id=ex_id,
            question=question,
            answer=answer,
            context=_parse_context(row.get(mapping.context)) if mapping.context else None,
            relevant_ids=relevant_ids,
            dialog=dialog,
            trajectory=trajectory,
            meta={"source_row": i, "raw_file": raw_file,
                  **({"trace_format": row["_trace_format"]} if row.get("_trace_format") else {})},
        ))
    return result


def ingest_report_md(result: IngestResult, raw_file: str) -> str:
    lines = [
        "# Ingest report",
        "",
        f"- Source: `{raw_file}`",
        f"- Total lines:{result.total}",
        f"- Accepted:{len(result.accepted)}",
        f"- Doubles discarded:{result.duplicates}",
        f"- Marriage:{len(result.rejected)}",
    ]
    if result.rejected:
        lines += ["", "## Discarded lines", ""]
        lines += [f"- line{n}: {reason}" for n, reason in result.rejected]
    return "\n".join(lines) + "\n"


def run_ingest(project: Project, rows: list[dict[str, Any]], mapping: ColumnMapping, raw_file: str) -> IngestResult:
    result = normalize_rows(rows, mapping, raw_file)
    write_jsonl_atomic(project.examples_path, result.accepted)
    project.ingest_report_path.parent.mkdir(parents=True, exist_ok=True)
    project.ingest_report_path.write_text(ingest_report_md(result, raw_file), encoding="utf-8")
    return result
