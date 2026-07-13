from __future__ import annotations

from pressf.schemas import Annotation, Example, Verdict


def test_verdict_roundtrip():
    v = Verdict(
        example_id="e1",
        answerable=False,
        grounded=None,
        recommendation="p",
        category="correct_refusal",
        confidence=0.9,
        reasoning="there is no answer in the database",
        judge_model="claude-haiku-4-5",
    )
    restored = Verdict.model_validate_json(v.model_dump_json())
    assert restored == v
    assert restored.grounded is None


def test_annotation_defaults():
    a = Annotation(example_id="e1", label="s", note="Why")
    assert a.undone is False
    assert a.ts.tzinfo is not None


def test_example_meta_default_not_shared():
    a, b = Example(id="1", question="q", answer="a"), Example(id="2", question="q", answer="a")
    a.meta["x"] = 1
    assert b.meta == {}
