from __future__ import annotations

import json

from pressf.config import ProjectConfig, RetrieverConfig
from pressf.export import export_pairs
from pressf.io import write_jsonl_atomic
from pressf.judge import run_check
from pressf.schemas import Example, PairwiseAnnotation, PairwiseCompareResult


class PairwiseClient:
    def parse(self, *, model, system, user, schema, max_tokens=4000):
        assert schema is PairwiseCompareResult
        assert "ANSWER A" in user
        assert "ANSWER B" in user
        return PairwiseCompareResult(
            status="b_better",
            evidence_quote="Use billing.",
            evidence_source_index=0,
            confidence=0.93,
            reasoning="Answer B is more complete.",
        ), 0.01


def test_compare_pairs_export_uses_pairwise_annotations(project):
    cfg = project.load_config()
    project.save_config(
        ProjectConfig(
            project=cfg.project,
            task="pairwise_compare",
            retriever=RetrieverConfig(kind="docs_folder", path=cfg.retriever.path),
            llm=cfg.llm,
        )
    )
    write_jsonl_atomic(
        project.examples_path,
        [
            Example(
                id="pair1",
                question="Cancel?",
                answer="Use billing.",
                answer_b="Ask support.",
            )
        ],
    )
    write_jsonl_atomic(
        project.pairwise_annotations_path,
        [PairwiseAnnotation(example_id="pair1", winner="a", shown_left="b", annotator="test")],
    )
    path = export_pairs(project)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["winner"] == "a"
    assert rows[0]["shown_left"] == "b"
    assert rows[0]["chosen"] == "Use billing."
    assert rows[0]["rejected"] == "Ask support."


def test_pairwise_compare_headless_check(project):
    cfg = project.load_config()
    project.save_config(
        ProjectConfig(
            project=cfg.project,
            task="pairwise_compare",
            retriever=RetrieverConfig(kind="docs_folder", path=cfg.retriever.path),
            llm=cfg.llm,
        )
    )
    write_jsonl_atomic(
        project.examples_path,
        [Example(id="pair1", question="Cancel?", answer="Ask support.", answer_b="Use billing.")],
    )
    project.verdicts_path.unlink(missing_ok=True)
    summary = run_check(project, PairwiseClient(), limit=1)
    verdict = project.load_verdicts()["pair1"]
    assert summary.checked == 1
    assert verdict.category == "b_better"
    assert verdict.recommendation == "p"
