"""Phase C: multi-turn dialogues and inter-annotator agreement (Cohen's kappa)."""

from __future__ import annotations

import json
from pathlib import Path

from pressf.ingest.validate import ColumnMapping, normalize_rows
from pressf.llm.prompts import claims_user, dialog_history
from pressf.schemas import DialogTurn, Example
from pressf.stats import cohen_kappa, inter_annotator_kappa


#── multi-way dialogues ───────────────────────── ─────────────────────────

def test_single_turn_prompt_unchanged():
    """Single Q→A: no background, the prompt is the same as before - additivity."""
    ex = Example(id="q1", question="What's the limit?", answer="600 per hour")
    assert dialog_history(ex) == ""
    prompt = claims_user(ex)
    assert "BACKGROUND" not in prompt
    assert "What's the limit?" in prompt and "600 per hour" in prompt


def test_dialog_history_gives_prior_turns_to_judge():
    ex = Example(
        id="q1", question="And on it?", answer="On Pro - 5000 per hour.",
        dialog=[
            DialogTurn(role="user", content="What is the limit on the basic tariff?"),
            DialogTurn(role="assistant", content="600 requests per hour."),
            DialogTurn(role="user", content="And on it?"),
            DialogTurn(role="assistant", content="On Pro - 5000 per hour."),
        ],
    )
    hist = dialog_history(ex)
    assert "600 requests per hour" in hist       #the last move is visible to the judge
    assert "On Pro - 5000 per hour." not in hist  #verifiable answer is not in the background
    prompt = claims_user(ex)
    assert "BACKGROUND" in prompt
    assert "On Pro - 5000 per hour." in prompt     #but the answer itself is judged


def test_ingest_dialog_column_derives_question_and_answer():
    dialog = json.dumps([
        {"role": "user", "content": "How can I cancel my subscription?"},
        {"role": "assistant", "content": "In the Billing section."},
        {"role": "user", "content": "Will the money be returned?"},
        {"role": "assistant", "content": "Yes, within 7 days."},
    ], ensure_ascii=False)
    rows = [{"conv": dialog}]
    result = normalize_rows(rows, ColumnMapping(question="q", answer="a", dialog="conv"))
    assert len(result.accepted) == 1
    ex = result.accepted[0]
    assert ex.question == "Will the money be returned?"       #user's last replica
    assert ex.answer == "Yes, within 7 days."    #assistant's last replica
    assert ex.dialog and len(ex.dialog) == 4


def test_ingest_without_dialog_still_plain_qa():
    rows = [{"q": "Question?", "a": "Answer."}]
    result = normalize_rows(rows, ColumnMapping(question="q", answer="a"))
    assert result.accepted[0].dialog is None
    assert result.accepted[0].question == "Question?"


# ── Cohen's kappa ─────────────────────────────────────────────────────────

def test_kappa_perfect_agreement():
    pairs = [("p", "p"), ("f", "f"), ("p", "p")]
    assert cohen_kappa(pairs) == 1.0


def test_kappa_removes_chance_agreement():
    #both put p in 8/10, agreed in 8 - but random agreement is high → kappa low
    pairs = [("p", "p")] * 7 + [("p", "f"), ("f", "p"), ("f", "f")]
    k = cohen_kappa(pairs)
    observed = sum(1 for a, b in pairs if a == b) / len(pairs)  # 0.8
    assert k < observed  #kappa is stricter than the bare share of consent


def test_kappa_empty():
    assert cohen_kappa([]) == 0.0


def test_inter_annotator_only_overlapping_pairs():
    per = {
        "alice": {"q1": "p", "q2": "f", "q3": "p"},
        "bob":   {"q1": "p", "q2": "p", "q3": "p"},   #common q1,q2,q3
        "carol": {"q9": "f"},                          #no intersection
    }
    result = inter_annotator_kappa(per)
    pairs = {(a, b) for a, b, _, _ in result}
    assert ("alice", "bob") in pairs
    assert ("alice", "carol") not in pairs and ("bob", "carol") not in pairs
    ab = next(r for r in result if r[0] == "alice" and r[1] == "bob")
    assert ab[2] == 3  #three common examples


def test_report_includes_kappa_when_two_annotators(tmp_path: Path):
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.export.report import write_report
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.schemas import Annotation, Verdict

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    exs = [Example(id=f"q{i}", question=f"Q{i}", answer="a") for i in range(3)]
    write_jsonl_atomic(project.examples_path, exs)
    for eid in ("q0", "q1", "q2"):
        append_jsonl(project.verdicts_path, Verdict(
            example_id=eid, answerable=True, recommendation="p", category="correct",
            confidence=0.9, reasoning="", judge_model="fake",
        ))
    #two annotators marking the same examples
    for eid, lbl in [("q0", "p"), ("q1", "f"), ("q2", "p")]:
        append_jsonl(project.annotations_path, Annotation(example_id=eid, label=lbl, annotator="alice"))
    for eid, lbl in [("q0", "p"), ("q1", "f"), ("q2", "f")]:
        append_jsonl(project.annotations_path, Annotation(example_id=eid, label=lbl, annotator="bob"))

    report = write_report(project).read_text(encoding="utf-8")
    assert "Cohen's kappa" in report
    assert "alice × bob" in report
