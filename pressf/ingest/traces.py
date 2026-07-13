"""Importing traces from LLM logging systems (LangSmith / Langfuse).

Product logs most often are not in a neat question/answer, but in the traces of these platforms.
Thin adapter: expands exported JSONL traces into flat lines
{question, answer, context}, then the usual ingest.

Expected forms (both JSONL, one object per line):

LangSmith run export:
  {"inputs": {"question": "..."} , "outputs": {"answer": "..."},
   "extra": {"context": ["chunk1", "chunk2"]}}
  (the question is searched in inputs using the keys question/query/input/prompt; the answer is found in outputs using
   answer/output/response/generation/text; context - in inputs/outputs/extra
   context/contexts/documents/retrieved.)

Langfuse trace/observation export:
  {"input": {"question": "..."}, "output": "...", "metadata": {"context": [...]}}
  (input can be a string or an object; output can be a string or an object with text/answer.)"""

from __future__ import annotations

import json
from typing import Any

_Q_KEYS = ("question", "query", "input", "prompt", "text")
_A_KEYS = ("answer", "output", "response", "generation", "completion", "text")
_CTX_KEYS = ("context", "contexts", "documents", "retrieved", "retrieved_documents", "sources")


def _first_str(obj: Any, keys: tuple[str, ...]) -> str:
    """Get the first non-empty string from the list of keys (or obj itself, if it is a string)."""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                inner = _first_str(v, keys)
                if inner:
                    return inner
    return ""


def _context_to_json(obj: Any) -> str:
    """Collect the context into a JSON array of strings (compatible with _parse_context ingest)."""
    found: Any = None
    if isinstance(obj, dict):
        for k in _CTX_KEYS:
            if obj.get(k):
                found = obj[k]
                break
    if found is None:
        return ""
    chunks: list[str] = []
    items = found if isinstance(found, list) else [found]
    for item in items:
        if isinstance(item, str) and item.strip():
            chunks.append(item.strip())
        elif isinstance(item, dict):
            txt = _first_str(item, ("text", "page_content", "content", "document"))
            if txt:
                chunks.append(txt)
    return json.dumps(chunks, ensure_ascii=False) if chunks else ""


def trace_to_row(trace: dict[str, Any]) -> dict[str, str] | None:
    """One trace → flat string {question, answer, context}. None if there is no Q or A."""
    inputs = trace.get("inputs") if isinstance(trace.get("inputs"), (dict, str)) else trace.get("input")
    outputs = trace.get("outputs") if trace.get("outputs") is not None else trace.get("output")
    extra = trace.get("extra") or trace.get("metadata") or {}

    question = _first_str(inputs, _Q_KEYS)
    answer = _first_str(outputs, _A_KEYS)
    if not question or not answer:
        return None
    context = _context_to_json(inputs) or _context_to_json(outputs) or _context_to_json(extra)
    row: dict[str, str] = {"question": question, "answer": answer}
    if context:
        row["context"] = context
    if trace.get("id"):
        row["id"] = str(trace["id"])
    return row


def load_traces(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Expand the list of raw traces into ingest lines. Empty/broken ones are skipped."""
    out: list[dict[str, str]] = []
    for trace in rows:
        if not isinstance(trace, dict) or "_parse_error" in trace:
            continue
        row = trace_to_row(trace)
        if row is not None:
            out.append(row)
    return out
