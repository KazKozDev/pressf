"""Phase B: confidence intervals, judge accuracy, sampling, active-learning order."""

from __future__ import annotations

from pathlib import Path

from pressf.stats import (
    flag_precision_recall,
    pairwise_summary,
    per_category_agreement,
    seeded_sample,
    sign_test_p,
    wilson_interval,
)


# ── Wilson interval ───────────────────────────────────────────────────────

def test_wilson_zero_n():
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_wilson_stays_in_bounds_at_extremes():
    lo, hi = wilson_interval(10, 10)  #100% success
    assert 0.0 <= lo <= hi <= 1.0
    assert lo < 1.0  #doesn't collapse to a point like a naive interval
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == 0.0 or lo0 >= 0.0
    assert hi0 > 0.0


def test_wilson_narrows_with_more_data():
    lo_s, hi_s = wilson_interval(8, 10)
    lo_l, hi_l = wilson_interval(800, 1000)
    assert (hi_l - lo_l) < (hi_s - lo_s)  #greater than n → already an interval


def test_pairwise_summary_excludes_ties_and_requires_ci_above_half_to_ship():
    from types import SimpleNamespace

    summary = pairwise_summary([
        *[SimpleNamespace(winner="b", shown_left="b") for _ in range(18)],
        *[SimpleNamespace(winner="a", shown_left="a") for _ in range(2)],
        *[SimpleNamespace(winner="tie", shown_left="a") for _ in range(4)],
    ])
    assert (summary.a_wins, summary.b_wins, summary.ties, summary.decided) == (2, 18, 4, 20)
    assert summary.b_win_rate == 0.9
    assert summary.ci_low > 0.5
    assert summary.p_value is not None and summary.p_value < 0.001
    assert "can be released" in summary.decision
    assert sign_test_p(9, 10) == 22 / 1024


# ── judge precision/recall on the "f" class ───────────────────────────────

def test_flag_precision_recall_basic():
    #judge: f,f,f,p ; person: f,p,f,f → tp=2, fp=1, fn=1
    pairs = [("f", "f"), ("f", "p"), ("f", "f"), ("p", "f")]
    m = flag_precision_recall(pairs)
    assert m["tp"] == 2 and m["fp"] == 1 and m["fn"] == 1
    assert abs(m["precision"] - 2 / 3) < 1e-9
    assert abs(m["recall"] - 2 / 3) < 1e-9


def test_flag_precision_recall_empty():
    m = flag_precision_recall([])
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0


# ── per-category agreement ────────────────────────────────────────────────

def test_per_category_agreement():
    rows = [
        ("false_refusal", "p", "f"),   #separated
        ("false_refusal", "p", "f"),   #separated
        ("correct", "p", "p"),         #agree
    ]
    agg = per_category_agreement(rows)
    assert agg["false_refusal"] == (2, 0.0)
    assert agg["correct"] == (1, 1.0)


# ── seeded sampling ───────────────────────────────────────────────────────

def test_seeded_sample_deterministic_and_sized():
    items = list(range(100))
    a = seeded_sample(items, 10, seed=42)
    b = seeded_sample(items, 10, seed=42)
    assert a == b               #reproducible
    assert len(a) == 10
    assert a == sorted(a)       #preserves original order
    assert seeded_sample(items, 10, seed=7) != a  #different seed - different sample


def test_seeded_sample_edge_cases():
    items = [1, 2, 3]
    assert seeded_sample(items, 5) == items   #n >= len → all
    assert seeded_sample(items, 0) == []


# ── active-learning review order ──────────────────────────────────────────

def test_informative_order_puts_borderline_first(tmp_path: Path):
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.review import ReviewSession
    from pressf.schemas import Example, Verdict

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    examples = [Example(id=f"q{i}", question=f"Q{i}?", answer="a") for i in range(3)]
    write_jsonl_atomic(project.examples_path, examples)
    #confidence: q0=0.99 (confident), q1=0.70 (on the verge), q2=0.10 (confident in the other direction)
    for eid, conf in [("q0", 0.99), ("q1", 0.70), ("q2", 0.10)]:
        append_jsonl(project.verdicts_path, Verdict(
            example_id=eid, answerable=True, recommendation="p",
            category="correct", confidence=conf, reasoning="", judge_model="fake",
        ))

    order = ReviewSession(project, order="informative").queue
    assert order[0] == "q1"  #closest to the threshold 0.7 - the most informative
