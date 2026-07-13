"""M4 export: pairs for DPO, disagreements, additional data loading."""

from __future__ import annotations

import json

from pressf.config import Project
from pressf.export import export_disagreements, export_pairs
from pressf.ingest import ColumnMapping
from pressf.ingest.validate import example_key, normalize_rows
from pressf.io import write_jsonl_atomic
from pressf.review import ReviewSession
from pressf.schemas import Example


def test_export_pairs_fills_chosen_from_same_question(project: Project):
    #e1 and e2 - one question («What is the limit?»), e1 is correct, e2 is a lie
    s = ReviewSession(project, order="original")
    s.decide("p")   # e1
    s.decide("f")   # e2
    s.decide("p")   # e3
    path = export_pairs(project)
    pairs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(pairs) == 1
    assert pairs[0]["rejected"] == "1000 per hour."
    assert pairs[0]["chosen"] == "600 per hour."  #will tighten up the p-answer to the same question


def test_export_pairs_chosen_null_when_no_good_answer(project: Project):
    write_jsonl_atomic(project.examples_path, [Example(id="e9", question="Unique?", answer="Lies")])
    write_jsonl_atomic(project.verdicts_path, [])
    s = ReviewSession(project)
    s.decide("f")
    pairs = [json.loads(l) for l in export_pairs(project).read_text(encoding="utf-8").splitlines()]
    assert pairs[0]["chosen"] is None


def test_export_disagreements(project: Project):
    s = ReviewSession(project, order="original")
    s.decide("f")   #e1: agent p → disagreement
    s.decide("f")   #e2: agent f → consent
    path = export_disagreements(project)
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["e1"]
    assert rows[0]["agent_recommendation"] == "p"


def test_add_dedups_against_existing(project: Project):
    existing = project.load_examples()
    keys = {example_key(ex.question, ex.answer) for ex in existing}
    rows = [
        {"q": "What's the limit?", "a": "600 per hour."},   #duplicate of existing e1
        {"q": "New question?", "a": "New answer"},
    ]
    result = normalize_rows(
        rows, ColumnMapping(question="q", answer="a"),
        existing_keys=keys, id_start=len(existing) + 1,
    )
    assert len(result.accepted) == 1
    assert result.duplicates == 1
    assert result.accepted[0].id == "ex_0004"  #numbering continued
