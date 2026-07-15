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

from ..schemas import TrajectoryStep

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


def trace_to_row(trace: dict[str, Any]) -> dict[str, Any] | None:
    """One supported trace shape → normalized ingest row, including trajectory when present."""
    if not isinstance(trace, dict):
        return None
    trace_format = detect_trace_format(trace)
    if trace_format == "openai_messages":
        return _openai_messages_row(trace)
    if trace_format == "native":
        return _native_row(trace)
    if trace_format == "langfuse":
        return _langfuse_row(trace)
    if trace_format == "langsmith":
        return _langsmith_row(trace)
    inputs = trace.get("inputs") if isinstance(trace.get("inputs"), (dict, str)) else trace.get("input")
    outputs = trace.get("outputs") if trace.get("outputs") is not None else trace.get("output")
    extra = trace.get("extra") or trace.get("metadata") or {}

    question = _first_str(inputs, _Q_KEYS)
    answer = _first_str(outputs, _A_KEYS)
    if not question or not answer:
        return None
    context = _context_to_json(inputs) or _context_to_json(outputs) or _context_to_json(extra)
    row: dict[str, Any] = {"question": question, "answer": answer}
    if context:
        row["context"] = context
    if trace.get("id"):
        row["id"] = str(trace["id"])
    return row


def detect_trace_format(trace: dict[str, Any]) -> str:
    """Classify supported trace shapes by structural signals, never by file name."""
    if "messages" in trace:
        return "openai_messages"
    if "trajectory" in trace:
        return "native"
    if "observations" in trace or trace.get("type") in {"TRACE", "SPAN", "GENERATION", "TOOL"}:
        return "langfuse"
    if "child_runs" in trace:
        return "langsmith"
    return "flat"


def _arguments(value: Any) -> dict | str:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else value
        except json.JSONDecodeError:
            return value
    return str(value if value is not None else "")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, dict):
        return _first_str(value, _A_KEYS) or json.dumps(value, ensure_ascii=False)
    return str(value)


def _indexed(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, step in enumerate(steps, 1):
        step["index"] = index
    return steps


def _duration_ms(value: Any) -> int | None:
    """Keep numeric source durations without making malformed trace records fail."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _error_text(value: Any) -> str | None:
    """Return a trace error only when the source actually marked one."""
    if not value:
        return None
    return _as_text(value) or None


def _openai_messages_row(trace: dict[str, Any]) -> dict[str, Any] | None:
    messages = trace.get("messages")
    if not isinstance(messages, list):
        return None
    question = ""
    answer = ""
    steps: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    assistant_text_steps: list[int] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = _as_text(message.get("content"))
        if role == "user" and content:
            question = content
        if role == "assistant":
            calls = message.get("tool_calls") or []
            if calls:
                if content:
                    steps.append({"kind": "thought", "content": content, "tool": None})
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function") if isinstance(call.get("function"), dict) else call
                    item = {"kind": "tool_call", "content": None, "tool": {
                        "name": str(function.get("name") or "unknown_tool"),
                        "arguments": _arguments(function.get("arguments", call.get("arguments", {}))),
                        "result": None,
                        "error": None,
                    }}
                    steps.append(item)
                    if call.get("id"):
                        pending[str(call["id"])] = item
            elif content:
                answer = content
                assistant_text_steps.append(len(steps))
                steps.append({"kind": "thought", "content": content, "tool": None})
        elif role == "tool":
            target = pending.get(str(message.get("tool_call_id")))
            raw_result = message.get("content")
            result = _as_text(raw_result)
            error = _error_text(message.get("error"))
            if error is None and isinstance(raw_result, str):
                try:
                    decoded = json.loads(raw_result)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, dict) and decoded.get("error"):
                    error = _error_text(decoded["error"])
                    result = ""
            elif error is None and isinstance(raw_result, dict) and raw_result.get("error"):
                error = _error_text(raw_result["error"])
                result = ""
            if target:
                target["tool"]["result"] = result or None
                target["tool"]["error"] = error
                target["tool"]["duration_ms"] = _duration_ms(message.get("duration_ms"))
            else:
                steps.append({"kind": "tool_call", "content": None, "tool": {
                    "name": str(message.get("name") or "unknown_tool"), "arguments": {},
                    "result": result or None, "error": error,
                    "duration_ms": _duration_ms(message.get("duration_ms")),
                }})
    if not question or not answer:
        return None
    if assistant_text_steps:
        steps[assistant_text_steps[-1]]["kind"] = "answer"
    return {"id": str(trace.get("id", "")), "question": question, "answer": answer,
            "trajectory": _indexed(steps), "_trace_format": "openai_messages"}


def _native_row(trace: dict[str, Any]) -> dict[str, Any] | None:
    question, answer = _as_text(trace.get("question")), _as_text(trace.get("answer"))
    if not question or not answer or not isinstance(trace.get("trajectory"), list):
        return None
    try:
        if any(not isinstance(item, dict) for item in trace["trajectory"]):
            return None
        steps = [TrajectoryStep.model_validate({**item, "index": n}).model_dump(mode="json")
                 for n, item in enumerate(trace["trajectory"], 1)]
    except Exception:
        return None
    return {"id": str(trace.get("id", "")), "question": question, "answer": answer,
            "trajectory": steps, "_trace_format": "native"}


def _time_key(record: dict[str, Any]) -> tuple[str, str]:
    return (str(record.get("start_time") or record.get("startTime") or record.get("timestamp") or ""),
            str(record.get("id") or record.get("run_id") or ""))


def _langsmith_row(trace: dict[str, Any]) -> dict[str, Any] | None:
    inputs = trace.get("inputs", {})
    outputs = trace.get("outputs", {})
    question = _first_str(inputs, _Q_KEYS)
    answer = _first_str(outputs, _A_KEYS)
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    def visit(run: dict[str, Any]) -> None:
        ident = str(run.get("id") or run.get("run_id") or id(run))
        if ident in seen:
            return
        seen.add(ident)
        records.append(run)
        for child in run.get("child_runs", []) or []:
            if isinstance(child, dict):
                visit(child)
    visit(trace)
    records.sort(key=_time_key)
    steps: list[dict[str, Any]] = []
    for run in records:
        kind = str(run.get("run_type") or run.get("type") or "").lower()
        if kind == "tool":
            output = run.get("outputs") if run.get("outputs") is not None else run.get("output")
            steps.append({"kind": "tool_call", "content": None, "tool": {
                "name": str(run.get("name") or "tool"),
                "arguments": _arguments(run.get("inputs") or run.get("input") or {}),
                "result": _as_text(output) or None,
                "error": _error_text(run.get("error")),
                "duration_ms": _duration_ms(run.get("duration_ms")),
            }})
        elif kind in {"llm", "chain", "generation"}:
            text = _first_str(run.get("outputs") or run.get("output"), _A_KEYS)
            if text and text != answer:
                steps.append({"kind": "thought", "content": text, "tool": None})
    if not question or not answer:
        return None
    steps.append({"kind": "answer", "content": answer, "tool": None})
    return {"id": str(trace.get("id", "")), "question": question, "answer": answer,
            "trajectory": _indexed(steps), "_trace_format": "langsmith"}


def _langfuse_row(trace: dict[str, Any]) -> dict[str, Any] | None:
    observations = trace.get("observations") or []
    if not isinstance(observations, list):
        observations = []
    question = _first_str(trace.get("input"), _Q_KEYS)
    answer = _first_str(trace.get("output"), _A_KEYS)
    observations = sorted((o for o in observations if isinstance(o, dict)), key=_time_key)
    steps: list[dict[str, Any]] = []
    for observation in observations:
        kind = str(observation.get("type") or "").upper()
        output = observation.get("output")
        if kind == "TOOL":
            steps.append({"kind": "tool_call", "content": None, "tool": {
                "name": str(observation.get("name") or "tool"),
                "arguments": _arguments(observation.get("input") or {}),
                "result": _as_text(output) or None,
                "error": _error_text(observation.get("error")),
                "duration_ms": _duration_ms(observation.get("duration") or observation.get("durationMs")),
            }})
        elif kind in {"GENERATION", "SPAN"}:
            text = _as_text(output)
            if text and text != answer:
                steps.append({"kind": "thought", "content": text, "tool": None})
    if not answer:
        for observation in reversed(observations):
            if str(observation.get("type") or "").upper() == "GENERATION":
                answer = _as_text(observation.get("output"))
                if answer:
                    break
    if not question or not answer:
        return None
    steps.append({"kind": "answer", "content": answer, "tool": None})
    return {"id": str(trace.get("id", "")), "question": question, "answer": answer,
            "trajectory": _indexed(steps), "_trace_format": "langfuse"}


def load_traces(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand traces while retaining malformed records for the normal ingest report."""
    out: list[dict[str, Any]] = []
    for line, trace in enumerate(rows, 1):
        if not isinstance(trace, dict) or "_parse_error" in trace:
            out.append(trace if isinstance(trace, dict) else {"_parse_error": f"line {line}: not an object"})
            continue
        row = trace_to_row(trace)
        if row is not None:
            out.append(row)
        else:
            out.append({"_parse_error": f"line {line}: {detect_trace_format(trace)} trace could not be parsed"})
    return out
