"""Phase D: regression gate for CI and import of LangSmith/Langfuse traces."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pressf.ingest.traces import load_traces, trace_to_row
from pressf.scoring import faithfulness_from_labels, score_project


# ── scoring ───────────────────────────────────────────────────────────────

def test_faithfulness_ignores_skips():
    f, p, fail = faithfulness_from_labels(["p", "p", "f", "s"])
    assert (p, fail) == (2, 1)
    assert abs(f - 2 / 3) < 1e-9


def test_faithfulness_empty():
    assert faithfulness_from_labels([]) == (0.0, 0, 0)


def _project(tmp_path: Path, *, human=None, judge=None):
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.schemas import Annotation, Example, Verdict

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir(exist_ok=True)
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    n = max(len(human or []), len(judge or []))
    write_jsonl_atomic(project.examples_path, [Example(id=f"q{i}", question="Q", answer="a") for i in range(n)])
    for i, rec in enumerate(judge or []):
        append_jsonl(project.verdicts_path, Verdict(
            example_id=f"q{i}", answerable=True, recommendation=rec, category="correct",
            confidence=0.9, reasoning="", judge_model="fake",
        ))
    for i, lbl in enumerate(human or []):
        append_jsonl(project.annotations_path, Annotation(example_id=f"q{i}", label=lbl))
    return project


def test_score_prefers_human_over_judge(tmp_path: Path):
    #the judge says all the p, the man says half the f: the man's standard must win
    project = _project(tmp_path, human=["p", "f", "f", "f"], judge=["p", "p", "p", "p"])
    score = score_project(project)
    assert score.source == "human"
    assert score.faithfulness == 0.25


def test_score_falls_back_to_judge(tmp_path: Path):
    project = _project(tmp_path, judge=["p", "p", "f"])
    score = score_project(project)
    assert score.source == "judge"
    assert abs(score.faithfulness - 2 / 3) < 1e-9


# ── lazy gate exit codes ──────────────────────────────────────────────────

def test_gate_passes_above_threshold(tmp_path: Path, monkeypatch):
    import pressf.cli as cli
    project = _project(tmp_path, human=["p", "p", "p", "f"])  # 75%
    monkeypatch.setattr(cli, "_load_project", lambda d: project)
    result = CliRunner().invoke(cli.app, ["gate", str(project.root), "--min-faithfulness", "0.7"])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_gate_fails_below_threshold(tmp_path: Path, monkeypatch):
    import pressf.cli as cli
    project = _project(tmp_path, human=["p", "f", "f", "f"])  # 25%
    monkeypatch.setattr(cli, "_load_project", lambda d: project)
    result = CliRunner().invoke(cli.app, ["gate", str(project.root), "--min-faithfulness", "0.8"])
    assert result.exit_code == 1
    assert "FAIL" in result.output


def test_gate_exit2_when_nothing_to_score(tmp_path: Path, monkeypatch):
    import pressf.cli as cli
    project = _project(tmp_path)  #no markings, no verdicts
    monkeypatch.setattr(cli, "_load_project", lambda d: project)
    result = CliRunner().invoke(cli.app, ["gate", str(project.root)])
    assert result.exit_code == 2


# ── trace importer ────────────────────────────────────────────────────────

def test_langsmith_shape():
    trace = {"inputs": {"question": "What's the limit?"}, "outputs": {"answer": "600 per hour"},
             "extra": {"context": ["limit 600 per hour"]}}
    row = trace_to_row(trace)
    assert row == {"question": "What's the limit?", "answer": "600 per hour", "context": '["limit 600 per hour"]'}


def test_langfuse_shape_string_io():
    trace = {"input": "How to cancel?", "output": {"text": "In billing"},
             "metadata": {"documents": [{"text": "cancellation in billing"}]}}
    row = trace_to_row(trace)
    assert row["question"] == "How to cancel?"
    assert row["answer"] == "In billing"
    assert "cancellation in billing" in row["context"]


def test_trace_without_answer_skipped():
    assert trace_to_row({"inputs": {"question": "Q"}, "outputs": {}}) is None


def test_load_traces_preserves_broken_rows_for_ingest_reporting():
    rows = [
        {"inputs": {"question": "Q1"}, "outputs": {"answer": "A1"}},
        {"_parse_error": "line 2"},
        {"inputs": {"question": ""}, "outputs": {"answer": "A"}},  #no question
    ]
    out = load_traces(rows)
    assert out[0]["question"] == "Q1"
    assert out[1]["_parse_error"] == "line 2"
    assert "trace could not be parsed" in out[2]["_parse_error"]


def test_init_from_traces_end_to_end(tmp_path: Path):
    """lazy init --traces: trace export → expanded → project created."""
    import pressf.cli as cli

    traces_file = tmp_path / "traces.jsonl"
    traces_file.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in [
        {"inputs": {"query": "Limit?"}, "outputs": {"response": "600"}},
        {"input": {"question": "Cancellation?"}, "output": "In billing"},
    ]), encoding="utf-8")
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "d.md").write_text("Limit 600.", encoding="utf-8")

    root = tmp_path / "proj"
    result = CliRunner().invoke(cli.app, [
        "init", str(root), "--data", str(traces_file), "--traces",
        "--retriever", "docs_folder", "--kb", str(kb), "--yes",
    ])
    assert result.exit_code == 0, result.output
    from pressf.config import Project
    from pressf.schemas import Example
    from pressf.io import read_jsonl
    examples = read_jsonl(Project(root).examples_path, Example)
    assert len(examples) == 2
    assert {e.question for e in examples} == {"Limit?", "Cancellation?"}
