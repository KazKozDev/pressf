"""WizardEngine: tools + stage state machine, without LLM."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from pressf.config import Project
from pressf.review import ReviewSession
from pressf.wizard import WizardEngine


def _setup_data(tmp_path: Path) -> tuple[Path, Path]:
    data = tmp_path / "qa.jsonl"
    data.write_text(
        '\n'.join(
            json.dumps({"q": f"Question{i}?", "a": f"Answer{i}: limit 600 requests"}, ensure_ascii=False)
            for i in range(3)
        ),
        encoding="utf-8",
    )
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "doc.md").write_text("The limit is 600 requests per hour.", encoding="utf-8")
    return data, kb


def test_finalize_blocked_until_stages_done(tmp_path: Path):
    engine = WizardEngine(tmp_path / "proj")
    out, is_error = engine.handle_tool("finalize", {"project_name": "x"})
    assert is_error and "stages not completed" in out
    assert engine.finalized is False


def test_full_stage_flow(tmp_path: Path):
    data, kb = _setup_data(tmp_path)
    engine = WizardEngine(tmp_path / "proj")

    out, err = engine.handle_tool("peek_file", {"path": str(data)})
    assert not err and "Columns: a, q" in out

    out, err = engine.handle_tool(
        "run_ingest", {"data_path": str(data), "question_col": "q", "answer_col": "a"}
    )
    assert not err and engine.ingest_done and "Accepted 3" in out

    out, err = engine.handle_tool("write_guidelines", {"markdown": "# Guidelines\np/f"})
    assert not err and engine.guidelines_done

    out, err = engine.handle_tool(
        "test_retriever", {"kind": "docs_folder", "params": {"path": str(kb)}}
    )
    assert not err and engine.retriever_tested and "Test search" in out

    out, err = engine.handle_tool("finalize", {"project_name": "my-project"})
    assert not err and engine.finalized

    cfg = engine.project.load_config()
    assert cfg.project == "my-project"
    assert cfg.retriever.kind == "docs_folder"
    assert cfg.ingest.question == "q"  #mapping saved for lazy add
    #the state of the stages comes to the agent in each result
    assert '"finalized": true' in out


def test_tool_errors_are_reported_not_raised(tmp_path: Path):
    engine = WizardEngine(tmp_path / "proj")
    out, is_error = engine.handle_tool("peek_file", {"path": "/no/such.jsonl"})
    assert is_error and "Error" in out
    out, is_error = engine.handle_tool("wat", {})
    assert is_error

#── scenarios: status, label import, done, existing project ───────────


def test_project_status_empty(tmp_path: Path):
    engine = WizardEngine(tmp_path / "proj")
    out, err = engine.handle_tool("project_status", {})
    assert not err and "lazy.yaml: no" in out and "Examples: 0" in out


def test_import_labels_requires_ingest(tmp_path: Path):
    engine = WizardEngine(tmp_path / "proj")
    out, err = engine.handle_tool(
        "import_labels", {"data_path": "x.jsonl", "label_col": "v", "label_map": {"pass": "p"}}
    )
    assert err and "first run_ingest" in out


def test_import_labels_matches_by_question_answer(tmp_path: Path):
    data = tmp_path / "examples.jsonl"
    data.write_text(
        "\n".join(
            json.dumps({"q": f"Question {i}?", "a": f"Answer {i}"}, ensure_ascii=False) for i in (1, 2, 3)
        ),
        encoding="utf-8",
    )
    labels = tmp_path / "gold.jsonl"
    rows = [
        {"q": "Question 1?", "a": "Answer 1", "verdict": "PASS"},
        {"q": "Question 2?", "a": "Answer 2", "verdict": "fail"},
        {"q": "Question 3?", "a": "Answer 3", "verdict": "I don't know"},          #unknown value
        {"q": "Wrong question?", "a": "Answer 1", "verdict": "pass"},  #no such example
    ]
    labels.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    engine = WizardEngine(tmp_path / "proj")
    engine.handle_tool("run_ingest", {"data_path": str(data), "question_col": "q", "answer_col": "a"})

    out, err = engine.handle_tool(
        "import_labels",
        {"data_path": str(labels), "label_col": "verdict", "label_map": {"pass": "p", "fail": "f"}},
    )
    assert not err
    assert "Imported labels: 2 (p=1, f=1" in out
    assert "unmatched examples: 1" in out
    assert "unknown values in verdict: 1" in out

    anns = engine.project.effective_annotations()
    assert len(anns) == 2
    assert all(a.annotator == "imported" for a in anns.values())

    #re-importing does not duplicate anything
    out, err = engine.handle_tool(
        "import_labels",
        {"data_path": str(labels), "label_col": "verdict", "label_map": {"pass": "p", "fail": "f"}},
    )
    assert not err and "Imported labels: 0" in out and "already labeled: 2" in out


def test_import_labels_matches_by_id(tmp_path: Path):
    data = tmp_path / "gold.jsonl"
    rows = [
        {"id": "a1", "q": "Question 1?", "a": "Answer 1", "label": "good"},
        {"id": "a2", "q": "Question 2?", "a": "Answer 2", "label": "bad"},
    ]
    data.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    engine = WizardEngine(tmp_path / "proj")
    engine.handle_tool(
        "run_ingest",
        {"data_path": str(data), "question_col": "q", "answer_col": "a", "id_col": "id"},
    )
    out, err = engine.handle_tool(
        "import_labels",
        {
            "data_path": str(data),
            "label_col": "label",
            "label_map": {"good": "p", "bad": "f"},
            "id_col": "id",
        },
    )
    assert not err and "Imported labels: 2" in out
    assert set(engine.project.effective_annotations()) == {"a1", "a2"}


def test_done_completes_without_config(tmp_path: Path):
    engine = WizardEngine(tmp_path / "proj")
    _, err = engine.handle_tool("done", {"summary": "Bring the logs to jsonl."})
    assert not err and engine.completed and not engine.finalized
    assert not engine.project.exists()  #lazy.yaml not written


def test_existing_project_recognized_and_refinalized(tmp_path: Path):
    data, kb = _setup_data(tmp_path)
    first = WizardEngine(tmp_path / "proj")
    first.handle_tool("run_ingest", {"data_path": str(data), "question_col": "q", "answer_col": "a"})
    first.handle_tool("write_guidelines", {"markdown": "# Guidelines"})
    first.handle_tool("test_retriever", {"kind": "docs_folder", "params": {"path": str(kb)}})
    first.handle_tool("finalize", {"project_name": "project"})

    engine = WizardEngine(tmp_path / "proj")  #second session in the same folder
    assert engine.ingest_done and engine.guidelines_done and engine.retriever_tested

    out, err = engine.handle_tool("project_status", {})
    assert not err and "lazy.yaml: yes" in out and "Examples: 3" in out

    #can be re-finalized without repeated ingest - for example, change the judge
    out, err = engine.handle_tool(
        "finalize", {"project_name": "project", "llm_provider": "openai"}
    )
    assert not err
    cfg = engine.project.load_config()
    assert cfg.llm.provider == "openai"
    assert cfg.llm.judge_model == "gpt-5.4-mini"  #anthropic-default did not leak
    assert cfg.retriever.kind == "docs_folder"    #the retriever was saved from the old config


def test_finalize_openai_compatible_requires_model(tmp_path: Path):
    data, kb = _setup_data(tmp_path)
    engine = WizardEngine(tmp_path / "proj")
    engine.handle_tool("run_ingest", {"data_path": str(data), "question_col": "q", "answer_col": "a"})
    engine.handle_tool("write_guidelines", {"markdown": "# Guidelines"})
    engine.handle_tool("test_retriever", {"kind": "docs_folder", "params": {"path": str(kb)}})

    out, err = engine.handle_tool(
        "finalize", {"project_name": "n", "llm_provider": "openai_compatible"}
    )
    assert err and "judge_model" in out  #without a model - an error, the agent will ask

    out, err = engine.handle_tool(
        "finalize",
        {
            "project_name": "n",
            "llm_provider": "openai_compatible",
            "judge_model": "llama3.3:70b",
            "base_url": "http://localhost:11434/v1",
        },
    )
    assert not err
    cfg = engine.project.load_config()
    assert cfg.llm.base_url == "http://localhost:11434/v1"


def test_wizard_finalizes_agent_trajectory_without_retriever(tmp_path: Path):
    engine = WizardEngine(tmp_path / "agent")
    traces = tmp_path / "traces.jsonl"
    traces.write_text(
        '{"id":"t1","question":"Q","answer":"A","trajectory":[{"kind":"answer","content":"A","tool":null}]}\n',
        encoding="utf-8",
    )
    out, err = engine.handle_tool(
        "run_ingest",
        {"data_path": str(traces), "question_col": "question", "answer_col": "answer",
         "trajectory_col": "trajectory", "id_col": "id"},
    )
    assert not err and "Accepted 1" in out
    engine.handle_tool("write_guidelines", {"markdown": "# Agent rules"})
    out, err = engine.handle_tool(
        "finalize", {"project_name": "agent", "task": "agent_trajectory"}
    )
    assert not err and "lazy.yaml" in out
    cfg = Project(tmp_path / "agent").load_config()
    assert cfg.task == "agent_trajectory" and cfg.retriever is None


class _Console:
    def __init__(self, user_input: str = ""):
        self.lines: list[str] = []
        self.user_input = user_input

    def print(self, text):
        self.lines.append(str(text))

    def input(self, prompt):
        return self.user_input


def test_run_wizard_processes_tool_results_and_completes(monkeypatch, tmp_path: Path):
    from pressf.wizard import run_wizard

    responses = iter([
        SimpleNamespace(
            stop_reason="tool_use",
            content=[
                SimpleNamespace(type="text", text="I will finish this"),
                SimpleNamespace(type="tool_use", name="done", input={"summary": "enough"}, id="tool-1"),
            ],
        ),
        SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Finished")]),
    ])
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: next(responses)))
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: client))
    console = _Console()
    assert run_wizard(tmp_path / "project", console, first_message="start") is True
    assert any("Finished" in line for line in console.lines)


def test_run_wizard_returns_false_when_the_user_exits(monkeypatch, tmp_path: Path):
    from pressf.wizard import run_wizard

    response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Need input")])
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: client))
    console = _Console("/quit")
    assert run_wizard(tmp_path / "project", console) is False
    assert any("Need input" in line for line in console.lines)


def test_wizard_status_lists_verdicts_labels_exports_and_directories(project: Project):
    ReviewSession(project).decide("f")
    project.out_dir.mkdir()
    (project.out_dir / "report.md").write_text("report", encoding="utf-8")
    engine = WizardEngine(project.root)
    status, is_error = engine.handle_tool("project_status", {})
    assert not is_error and "Judge verdicts: 3" in status and "Human labels: 1" in status and "Exported: report.md" in status

    nested = project.root / "nested"
    nested.mkdir()
    (nested / "file.txt").write_text("x", encoding="utf-8")
    listing, is_error = engine.handle_tool("list_dir", {"path": str(project.root)})
    assert not is_error and "[dir] nested" in listing
    _, is_error = engine.handle_tool("list_dir", {"path": str(project.root / "missing")})
    assert is_error


def test_run_wizard_handles_eof_and_turn_limit(monkeypatch, tmp_path: Path):
    from pressf import wizard

    response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="More")])
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: client))

    class EofConsole(_Console):
        def input(self, prompt):
            raise EOFError

    assert wizard.run_wizard(tmp_path / "eof", EofConsole()) is False
    monkeypatch.setattr(wizard, "MAX_TURNS", 1)
    assert wizard.run_wizard(tmp_path / "limit", _Console("continue")) is False
