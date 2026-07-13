from __future__ import annotations

from pathlib import Path

from pressf.config import LLMConfig, Project, ProjectConfig, RetrieverConfig
from pressf.io import write_jsonl_atomic
from pressf.judge import run_check
from pressf.judge.aggregate import aggregate_retrieval_quality_verdict
from pressf.llm import prompts
from pressf.schemas import Chunk, ContextChunk, Example, SearchQualityResult


class SearchClient:
    def __init__(self):
        self.users: list[str] = []

    def parse(self, *, model, system, user, schema, max_tokens=4000):
        self.users.append(user)
        assert schema is SearchQualityResult
        return SearchQualityResult(
            status="context_partial",
            missing_information="The retrieved context does not include the cancellation deadline.",
            helpful_quote="You can cancel from billing.",
            helpful_source_index=0,
            confidence=0.91,
            reasoning="The context has the action but misses the deadline.",
        ), 0.01


def test_retrieval_quality_prompt_selected():
    system = prompts.task_system("retrieval_quality", "Prefer complete retrieval.")
    assert "search quality" in system
    assert "Prefer complete retrieval" in system


def test_retrieval_quality_missing_maps_to_f():
    verdict = aggregate_retrieval_quality_verdict(
        example_id="e1",
        result=SearchQualityResult(
            status="context_missing",
            missing_information="No pricing facts were retrieved.",
            confidence=0.88,
            reasoning="The context is unrelated.",
        ),
        chunks=[],
        judge_model="fixture",
        escalated=False,
        cost_usd=0.01,
    )
    assert verdict.category == "context_missing"
    assert verdict.recommendation == "f"
    assert verdict.answerable is False


def test_retrieval_quality_sufficient_maps_to_p_with_quote():
    chunks = [Chunk(text="The base plan allows 600 requests per hour.", source="kb.md#0")]
    verdict = aggregate_retrieval_quality_verdict(
        example_id="e1",
        result=SearchQualityResult(
            status="context_sufficient",
            helpful_quote="600 requests per hour",
            helpful_source_index=0,
            confidence=0.94,
            reasoning="The context contains the answer.",
        ),
        chunks=chunks,
        judge_model="fixture",
        escalated=False,
        cost_usd=0.01,
    )
    assert verdict.category == "context_sufficient"
    assert verdict.recommendation == "p"
    assert verdict.claims[0].evidence[0].source == "kb.md#0"


def test_retrieval_quality_uses_logged_context(tmp_path: Path):
    project = Project(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "doc.md").write_text("This should not be used when logged context exists.", encoding="utf-8")
    project.save_config(
        ProjectConfig(
            project="search",
            task="retrieval_quality",
            retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
            llm=LLMConfig(),
        )
    )
    write_jsonl_atomic(
        project.examples_path,
        [
            Example(
                id="e1",
                question="How do I cancel?",
                answer="Cancel from billing.",
                context=[ContextChunk(text="You can cancel from billing.", source="rag-log#1")],
            )
        ],
    )
    client = SearchClient()
    summary = run_check(project, client)
    assert summary.checked == 1
    assert "rag-log#1" in client.users[0]
    assert "This should not be used" not in client.users[0]
