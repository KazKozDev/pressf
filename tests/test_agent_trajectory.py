from __future__ import annotations

import json
from pathlib import Path

import pytest

from pressf.config import LLMConfig, Project, ProjectConfig, canonical_task
from pressf.ingest.traces import detect_trace_format, load_traces, trace_to_row
from pressf.ingest.validate import ColumnMapping, normalize_rows, run_ingest
from pressf.io import append_jsonl, write_jsonl_atomic
from pressf.judge import run_check
from pressf.judge.aggregate import aggregate_trajectory_verdict
from pressf.llm.prompts import TOOL_RESULT_CHAR_BUDGET, agent_trajectory_user, truncate_tool_result
from pressf.schemas import Annotation, Example, ToolCall, TrajectoryResult, TrajectoryStep, TrajectoryStepVerdict, Verdict


def _example() -> Example:
    return Example(
        id="t1", question="What is the deployment status?", answer="It completed.",
        trajectory=[
            TrajectoryStep(index=1, kind="tool_call", tool=ToolCall(
                name="get_deployment", arguments={"id": "dep-1"}, result="status=completed")),
            TrajectoryStep(index=2, kind="answer", content="It completed."),
        ],
    )


def test_trajectory_schemas_are_backward_compatible():
    assert Example.model_validate({"id": "old", "question": "Q", "answer": "A"}).trajectory is None
    dumped = _example().model_dump(mode="json")
    assert Example.model_validate(dumped).trajectory[0].tool.name == "get_deployment"
    assert TrajectoryResult(
        steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="fabricated", issue_kind="fabricated_tool_result")],
        final_answer_ok=False, efficient=True, confidence=0.9, reasoning="bad",
    ).steps[0].issue_kind == "fabricated_tool_result"
    assert Verdict.model_validate({
        "example_id": "old", "answerable": True, "recommendation": "p", "category": "correct",
        "confidence": .9, "reasoning": "ok", "judge_model": "fixture",
    }).step_issues is None
    with pytest.raises(Exception):
        ToolCall(arguments={})


def test_task_alias_prompt_and_deterministic_truncation():
    assert canonical_task("agents") == "agent_trajectory"
    prompt = agent_trajectory_user(_example())
    assert "Step 1 — TOOL CALL" in prompt and "get_deployment" in prompt and "FINAL ANSWER" in prompt
    long = "a" * 6000 + "z" * 6000
    clipped = truncate_tool_result(long)
    assert len(clipped) == TOOL_RESULT_CHAR_BUDGET and clipped.startswith("a") and clipped.endswith("z")
    errored = _example().model_copy(update={"trajectory": [TrajectoryStep(
        index=1, kind="tool_call", tool=ToolCall(name="x", arguments="raw", result="ok", error="denied")
    )]})
    rendered = agent_trajectory_user(errored)
    assert "Arguments:\nraw" in rendered and "Error:\ndenied" in rendered


def test_openai_messages_and_native_trajectory_ingest():
    row = trace_to_row({"id": "chat", "messages": [
        {"role": "user", "content": "Status?"},
        {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "status", "arguments": "{\"id\": \"d1\"}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "completed"},
        {"role": "assistant", "content": "Completed."},
    ]})
    assert row["_trace_format"] == "openai_messages"
    assert row["trajectory"][0]["tool"]["arguments"] == {"id": "d1"}
    result = normalize_rows([row], ColumnMapping(question="question", answer="answer", trajectory="trajectory"))
    assert result.accepted[0].id == "chat" and result.accepted[0].trajectory[0].tool.result == "completed"
    native = {"id": "native", "question": "Q", "answer": "A", "trajectory": [
        {"kind": "tool_call", "content": None, "tool": {"name": "x", "arguments": "bad-json", "result": "r"}},
    ]}
    result = normalize_rows([native], ColumnMapping(question="question", answer="answer", trajectory="trajectory"))
    assert result.accepted[0].trajectory[0].index == 1


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"messages": []}, "openai_messages"),
        ({"trajectory": []}, "native"),
        ({"observations": []}, "langfuse"),
        ({"type": "TRACE"}, "langfuse"),
        ({"child_runs": [{"id": "x"}]}, "langsmith"),
        ({"child_runs": []}, "langsmith"),
        ({"question": "Q", "answer": "A"}, "flat"),
    ],
)
def test_trace_format_detection_is_structural_and_deterministic(row, expected):
    assert detect_trace_format(row) == expected


def test_openai_multi_call_pairing_marks_only_final_answer_and_preserves_errors():
    row = trace_to_row({"messages": [
        {"role": "user", "content": "Old question"},
        {"role": "user", "content": "Current question"},
        {"role": "assistant", "content": "I will check."},
        {"role": "assistant", "tool_calls": [
            {"id": "a", "function": {"name": "first", "arguments": {"one": 1}}},
            {"id": "b", "function": {"name": "second", "arguments": "not json"}},
        ]},
        {"role": "tool", "tool_call_id": "b", "content": '{"error":"denied"}', "duration_ms": "17"},
        {"role": "tool", "tool_call_id": "a", "content": "first result"},
        {"role": "assistant", "content": "Final answer."},
    ]})
    assert row["question"] == "Current question"
    assert [step["kind"] for step in row["trajectory"]] == ["thought", "tool_call", "tool_call", "answer"]
    assert row["trajectory"][1]["tool"]["result"] == "first result"
    assert row["trajectory"][2]["tool"]["arguments"] == "not json"
    assert row["trajectory"][2]["tool"]["error"] == "denied"
    assert row["trajectory"][2]["tool"]["duration_ms"] == 17


def test_langsmith_and_langfuse_trajectory_ingest():
    langsmith = trace_to_row({"id": "ls", "inputs": {"question": "Q"}, "outputs": {"answer": "A"}, "child_runs": [
        {"id": "tool", "run_type": "tool", "name": "search", "inputs": {"q": "Q"}, "outputs": {"text": "fact"}, "start_time": "2026-01-01"},
    ]})
    assert langsmith["trajectory"][0]["tool"]["name"] == "search"
    langfuse = trace_to_row({"id": "lf", "input": {"question": "Q"}, "output": "A", "observations": [
        {"id": "tool", "type": "TOOL", "name": "lookup", "input": {"id": "1"}, "output": "found", "startTime": "2026-01-01"},
    ]})
    assert langfuse["trajectory"][0]["tool"]["result"] == "found"


def test_langsmith_nested_runs_are_deduplicated_and_time_ordered():
    repeated = {"id": "one", "run_type": "tool", "name": "first", "inputs": {}, "outputs": "one", "start_time": "2026-01-01T00:00:01Z"}
    second = {"id": "two", "run_type": "tool", "name": "second", "inputs": {}, "outputs": "two", "start_time": "2026-01-01T00:00:02Z", "child_runs": [repeated]}
    row = trace_to_row({"inputs": {"question": "Q"}, "outputs": {"answer": "A"}, "child_runs": [second, repeated]})
    assert [step["tool"]["name"] for step in row["trajectory"] if step["kind"] == "tool_call"] == ["first", "second"]
    assert [step["index"] for step in row["trajectory"]] == [1, 2, 3]


def test_malformed_trace_rows_remain_in_ingest_report(tmp_path: Path):
    rows = load_traces([
        {"messages": [{"role": "user", "content": "Q"}]},
        {"id": "ok", "question": "Q", "answer": "A", "trajectory": [
            {"kind": "answer", "content": "A", "tool": None},
        ]},
        {"_parse_error": "line 3: malformed JSON"},
    ])
    project = Project(tmp_path)
    outcome = run_ingest(project, rows, ColumnMapping(question="question", answer="answer", trajectory="trajectory"), "traces.jsonl")
    assert len(outcome.accepted) == 1 and len(outcome.rejected) == 2
    report = project.ingest_report_path.read_text(encoding="utf-8")
    assert "openai_messages trace could not be parsed" in report and "malformed JSON" in report


def test_trajectory_ingest_keeps_distinct_runs_with_same_question_and_answer():
    rows = [
        {"id": "one", "question": "Q", "answer": "A", "trajectory": [
            {"kind": "tool_call", "content": None, "tool": {"name": "first", "arguments": {}, "result": "A"}},
        ]},
        {"id": "two", "question": "Q", "answer": "A", "trajectory": [
            {"kind": "tool_call", "content": None, "tool": {"name": "second", "arguments": {}, "result": "A"}},
        ]},
    ]
    result = normalize_rows(rows, ColumnMapping(question="question", answer="answer", trajectory="trajectory"))
    assert [ex.id for ex in result.accepted] == ["one", "two"] and result.duplicates == 0


def test_trajectory_category_precedence():
    def verdict(kind: str | None, *, answer_ok=True, efficient=True):
        return aggregate_trajectory_verdict(
            example_id="x", result=TrajectoryResult(
                steps=[TrajectoryStepVerdict(step_index=1, ok=kind is None, issue="issue" if kind else None, issue_kind=kind)],
                final_answer_ok=answer_ok, efficient=efficient, confidence=.9, reasoning="r"),
            judge_model="fake", escalated=False, cost_usd=0,
        )
    assert verdict("unsafe_action").category == "trajectory_unsafe"
    assert verdict("fabricated_tool_result").category == "trajectory_unfaithful"
    assert verdict("wrong_arguments").category == "trajectory_unfaithful"
    assert verdict(None, answer_ok=False).category == "trajectory_wrong_answer"
    assert verdict("loop").category == "trajectory_inefficient"
    assert verdict(None).category == "trajectory_ok"


def test_trajectory_inefficient_passes_unless_strict():
    inefficient = TrajectoryResult(
        steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="repeat", issue_kind="loop")],
        final_answer_ok=True, efficient=False, confidence=.9, reasoning="wasteful but correct",
    )
    lenient = aggregate_trajectory_verdict(
        example_id="x", result=inefficient, judge_model="fake", escalated=False, cost_usd=0)
    strict = aggregate_trajectory_verdict(
        example_id="x", result=inefficient, judge_model="fake", escalated=False, cost_usd=0,
        fail_on_inefficient=True)
    assert lenient.category == strict.category == "trajectory_inefficient"
    assert lenient.recommendation == "p" and strict.recommendation == "f"


class TrajectoryClient:
    def __init__(self):
        self.models: list[str] = []

    def parse(self, *, model, system, user, schema, max_tokens=4000):
        self.models.append(model)
        return TrajectoryResult(steps=[], final_answer_ok=True, efficient=True,
                                confidence=.4 if len(self.models) == 1 else .9, reasoning="ok"), .01


def test_trajectory_pipeline_escalates_without_retriever(tmp_path: Path):
    project = Project(tmp_path)
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None, llm=LLMConfig()))
    write_jsonl_atomic(project.examples_path, [_example()])
    client = TrajectoryClient()
    summary = run_check(project, client)
    verdict = project.load_verdicts()["t1"]
    assert summary.checked == 1 and client.models == ["claude-haiku-4-5", "claude-opus-4-8"]
    assert verdict.category == "trajectory_ok" and verdict.escalated and verdict.step_issues == []


def test_trajectory_check_rejects_examples_without_recorded_steps(tmp_path: Path):
    project = Project(tmp_path)
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None, llm=LLMConfig()))
    write_jsonl_atomic(project.examples_path, [Example(id="missing", question="Q", answer="A")])
    with pytest.raises(ValueError, match="requires a recorded trajectory"):
        run_check(project, TrajectoryClient())


@pytest.mark.parametrize(
    ("result", "category", "recommendation"),
    [
        (TrajectoryResult(steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="unsafe", issue_kind="unsafe_action")], final_answer_ok=True, efficient=True, confidence=.9, reasoning="unsafe"), "trajectory_unsafe", "f"),
        (TrajectoryResult(steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="invented", issue_kind="fabricated_tool_result")], final_answer_ok=True, efficient=True, confidence=.9, reasoning="invented"), "trajectory_unfaithful", "f"),
        (TrajectoryResult(steps=[], final_answer_ok=False, efficient=True, confidence=.9, reasoning="wrong"), "trajectory_wrong_answer", "f"),
        #correct-but-wasteful run passes the gate by default
        (TrajectoryResult(steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="repeat", issue_kind="loop")], final_answer_ok=True, efficient=False, confidence=.9, reasoning="loop"), "trajectory_inefficient", "p"),
    ],
)
def test_trajectory_pipeline_maps_failure_categories(tmp_path: Path, result: TrajectoryResult, category: str, recommendation: str):
    class FixedClient:
        def parse(self, **kwargs):
            return result, .01

    project = Project(tmp_path)
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None, llm=LLMConfig(escalation_model="")))
    write_jsonl_atomic(project.examples_path, [_example()])
    run_check(project, FixedClient())
    verdict = project.load_verdicts()["t1"]
    assert verdict.category == category and verdict.recommendation == recommendation


def test_trajectory_batch_pipeline_preserves_step_issues(tmp_path: Path):
    from types import SimpleNamespace
    from pressf.judge.batch_check import run_check_batch
    from test_batch import _fake_anthropic, _ok_result

    project = Project(tmp_path)
    llm = LLMConfig(batch_min_examples=1, escalation_model="")
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None, llm=llm))
    write_jsonl_atomic(project.examples_path, [_example()])

    def responder(request):
        props = request["params"]["output_config"]["format"]["schema"]["properties"]
        assert "final_answer_ok" in props
        return _ok_result(request["custom_id"], {
            "steps": [{"step_index": 1, "ok": False, "issue": "Repeated call", "issue_kind": "loop"}],
            "final_answer_ok": True, "efficient": False, "confidence": .9, "reasoning": "loop",
        })

    summary = run_check_batch(project, SimpleNamespace(anthropic=_fake_anthropic(responder)))
    verdict = project.load_verdicts()["t1"]
    assert summary.checked == 1 and verdict.category == "trajectory_inefficient"
    assert verdict.step_issues[0].issue_kind == "loop"


def test_agent_trajectory_cli_smoke_flow(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    import pressf.cli as cli
    import pressf.llm as llm

    source = tmp_path / "traces.jsonl"
    source.write_text(json.dumps({
        "id": "one", "question": "Status?", "answer": "Completed.", "trajectory": [
            {"kind": "tool_call", "content": None, "tool": {"name": "status", "arguments": {}, "result": "completed"}},
            {"kind": "answer", "content": "Completed.", "tool": None},
        ],
    }) + "\n", encoding="utf-8")
    root = tmp_path / "agent-project"
    runner = CliRunner()
    initialized = runner.invoke(cli.app, ["init", str(root), "--data", str(source), "--task", "agents", "--yes"])
    assert initialized.exit_code == 0, initialized.output
    cfg = Project(root).load_config()
    assert cfg.task == "agent_trajectory" and cfg.retriever is None and cfg.ingest.trajectory == "trajectory"
    monkeypatch.setattr(llm, "build_llm_client", lambda cfg: TrajectoryClient())
    checked = runner.invoke(cli.app, ["check", str(root), "--sync"])
    assert checked.exit_code == 0, checked.output
    added = runner.invoke(cli.app, ["add", str(root), "--data", str(source)])
    assert added.exit_code == 0, added.output
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"messages":[{"role":"user","content":"missing final"}]}\n', encoding="utf-8")
    added_bad = runner.invoke(cli.app, ["add", str(root), "--data", str(malformed)])
    assert added_bad.exit_code == 0, added_bad.output
    assert "trajectory trace could not be parsed" in (root / "data" / "ingest_report.md").read_text(encoding="utf-8")
    exported = runner.invoke(cli.app, ["export", str(root)])
    assert exported.exit_code == 0, exported.output
    assert "Trajectory analysis" in (root / "out" / "report.md").read_text(encoding="utf-8")
    gated = runner.invoke(cli.app, ["gate", str(root)])
    assert gated.exit_code == 0, gated.output


def test_trajectory_estimate_does_not_build_a_retriever(tmp_path: Path):
    from pressf.judge.estimate import estimate_check

    project = Project(tmp_path)
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None))
    write_jsonl_atomic(project.examples_path, [_example()])

    class Counter:
        def count_tokens(self, **kwargs):
            assert "RECORDED TRAJECTORY" in kwargs["user"]
            return 123

    estimate = estimate_check(project, Counter())
    assert estimate.n_examples == 1 and estimate.avg_input_tokens == 123


def test_trajectory_review_and_report_show_step_findings(tmp_path: Path):
    pytest.importorskip("textual")
    from pressf.export.report import write_report
    from pressf.review import ReviewSession
    from pressf.review.tui import ReviewApp

    project = Project(tmp_path)
    project.save_config(ProjectConfig(project="trajectory", task="agent_trajectory", retriever=None))
    ex = _example()
    write_jsonl_atomic(project.examples_path, [ex])
    verdict = aggregate_trajectory_verdict(
        example_id=ex.id,
        result=TrajectoryResult(
            steps=[TrajectoryStepVerdict(step_index=1, ok=False, issue="Repeated request", issue_kind="loop")],
            final_answer_ok=True, efficient=False, confidence=.9, reasoning="Looped request"),
        judge_model="fixture", escalated=False, cost_usd=.01,
    )
    append_jsonl(project.verdicts_path, verdict)
    append_jsonl(project.annotations_path, Annotation(example_id=ex.id, label="f"))
    card = ReviewApp(ReviewSession(project))._render_trajectory(ex, verdict)
    assert "loop" in card and "Repeated request" in card
    report = write_report(project).read_text(encoding="utf-8")
    assert "Trajectory analysis" in report and "Average trajectory length" in report and "Repeated request" in report
