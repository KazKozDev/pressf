from __future__ import annotations

from pathlib import Path

import pytest

from pressf.config import LLMConfig, Project, ProjectConfig, RetrieverConfig
from pressf.io import write_jsonl_atomic
from pressf.schemas import Example, Verdict


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """Ready-made mini-project with 3 examples and verdicts (without knowledge base)."""
    p = Project(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "doc.md").write_text("The limit is 600 requests per hour.\n\nResponse 429 if exceeded.", encoding="utf-8")
    p.save_config(
        ProjectConfig(
            project="test",
            retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
            llm=LLMConfig(),
        )
    )
    p.guidelines_path.write_text("# Guidelines\nTrue - p, lies - f.", encoding="utf-8")
    examples = [
        Example(id="e1", question="What's the limit?", answer="600 per hour."),
        Example(id="e2", question="What's the limit?", answer="1000 per hour."),
        Example(id="e3", question="Are there webhooks?", answer="I don't know, it's not at the docks."),
    ]
    write_jsonl_atomic(p.examples_path, examples)
    verdicts = [
        _verdict("e1", "p", "correct", 0.95),
        _verdict("e2", "f", "hallucination_contradicts", 0.55),
        _verdict("e3", "p", "correct_refusal", 0.8),
    ]
    write_jsonl_atomic(p.verdicts_path, verdicts)
    return p


def _verdict(eid: str, rec: str, category: str, conf: float) -> Verdict:
    return Verdict(
        example_id=eid,
        answerable=True,
        grounded=rec == "p",
        recommendation=rec,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        confidence=conf,
        reasoning="test",
        judge_model="claude-haiku-4-5",
    )
