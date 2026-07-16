from __future__ import annotations

import json

from pressf.config import Project
from pressf.export import export_goldset, write_report
from pressf.review import ReviewSession


def _annotate_all(project: Project) -> None:
    s = ReviewSession(project)
    s.decide("f")                       #e2 - agreement with the agent
    s.decide("f", note="debatable")        #e3 - disagreement (agent p)
    s.decide("p")                       #e1 - agreement


def test_goldset_jsonl_with_meta(project: Project):
    _annotate_all(project)
    written = export_goldset(project, ["jsonl", "csv"])
    assert len(written) == 2

    lines = [json.loads(l) for l in written[0].read_text(encoding="utf-8").splitlines()]
    meta = lines[0]["_meta"]
    assert meta["total"] == 3
    assert meta["counts"] == {"p": 1, "f": 2, "s": 0}
    assert meta["guidelines_sha256"]
    record = next(r for r in lines[1:] if r["id"] == "e2")
    assert record["label"] == "f"
    assert record["agent_recommendation"] == "f"
    assert record["agreed_with_agent"] is True


def test_unannotated_excluded(project: Project):
    s = ReviewSession(project)
    s.decide("p")  #only e2
    written = export_goldset(project, ["jsonl"])
    lines = written[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  #_meta + 1 entry


def test_report(project: Project):
    _annotate_all(project)
    path = write_report(project)
    text = path.read_text(encoding="utf-8")
    assert "Human/judge agreement: **66.7%**" in text
    assert "Disagreements (1)" in text
    assert "debatable" in text


def test_pairwise_report_states_whether_the_new_version_is_ready(tmp_path):
    from pressf.config import ProjectConfig, RetrieverConfig
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.schemas import Example, PairwiseAnnotation

    root = tmp_path / "compare"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(project="compare", task="pairwise_compare", retriever=RetrieverConfig(kind="docs_folder", path=str(kb))))
    write_jsonl_atomic(project.examples_path, [Example(id="e1", question="q", answer="a", answer_b="b")])
    for index in range(20):
        append_jsonl(project.pairwise_annotations_path, PairwiseAnnotation(example_id=f"e{index}", winner="b" if index < 18 else "a", shown_left="a"))
    text = write_report(project).read_text(encoding="utf-8")
    assert "B win rate" in text
    assert "can be released" in text


def test_retrieval_report_includes_corpus_ranking_metrics(tmp_path):
    from pressf.config import LLMConfig, ProjectConfig, RetrieverConfig
    from pressf.io import write_jsonl_atomic
    from pressf.schemas import ContextChunk, Example, RetrievalMetrics, Verdict

    root = tmp_path / "search"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(
        project="search", task="retrieval_quality",
        retriever=RetrieverConfig(kind="docs_folder", path=str(kb)), llm=LLMConfig(),
    ))
    write_jsonl_atomic(project.examples_path, [Example(
        id="e1", question="q", answer="a", context=[ContextChunk(text="t", source="doc")]
    )])
    write_jsonl_atomic(project.verdicts_path, [Verdict(
        example_id="e1", claims=[], category="context_sufficient", recommendation="p",
        answerable=True, confidence=0.9, reasoning="ok", judge_model="fixture",
        retrieval_metrics=RetrievalMetrics(
            k=[1], precision_at_k={1: 1.0}, recall_at_k={1: 1.0},
            ndcg_at_k={1: 1.0}, hit_at_k={1: 1.0}, mrr=1.0, map=1.0,
        ),
    )])

    text = write_report(project).read_text(encoding="utf-8")

    assert "Retrieval ranking metrics" in text
    assert "| Precision | 1.000 |" in text
    assert "- MRR: 1.000" in text
