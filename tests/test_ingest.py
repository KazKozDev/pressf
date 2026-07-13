from __future__ import annotations

import json
from pathlib import Path

from pressf.ingest import ColumnMapping, load_rows
from pressf.ingest.validate import normalize_rows


MAPPING = ColumnMapping(question="q", answer="a")


def test_validation_and_dedup():
    rows = [
        {"q": "Question 1?", "a": "Answer 1"},
        {"q": "Question 1?", "a": "answer 1"},   #double (case/space normalization)
        {"q": "", "a": "Answer"},                 #marriage: an empty question
        {"q": "Question 2?", "a": ""},             #marriage: empty answer
        {"q": "Question 3?", "a": "Answer 3"},
    ]
    result = normalize_rows(rows, MAPPING)
    assert len(result.accepted) == 2
    assert result.duplicates == 1
    assert len(result.rejected) == 2
    assert result.total == 5
    assert result.accepted[0].id == "ex_0001"


def test_context_parsing_variants():
    rows = [
        {"q": "IN?", "a": "ABOUT", "ctx": json.dumps([{"text": "chunk", "source": "d1"}])},
        {"q": "B2?", "a": "O2", "ctx": "just a string"},
        {"q": "Q3?", "a": "O3", "ctx": ""},
    ]
    mapping = ColumnMapping(question="q", answer="a", context="ctx")
    result = normalize_rows(rows, mapping)
    assert result.accepted[0].context[0].source == "d1"
    assert result.accepted[1].context[0].text == "just a string"
    assert result.accepted[2].context is None


def test_load_jsonl_and_csv(tmp_path: Path):
    jl = tmp_path / "x.jsonl"
    jl.write_text('{"q": "Q?", "a": "A"}\nnot json\n', encoding="utf-8")
    rows = load_rows(jl)
    assert rows[0]["q"] == "Q?"
    assert "_parse_error" in rows[1]

    cs = tmp_path / "x.csv"
    cs.write_text("q,a\nQ?,A\n", encoding="utf-8")
    assert load_rows(cs) == [{"q": "Q?", "a": "A"}]
