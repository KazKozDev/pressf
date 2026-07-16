from __future__ import annotations

from pathlib import Path

from pressf.config import LLMConfig, Project, ProjectConfig, RetrieverConfig
from pressf.io import write_jsonl_atomic
from pressf.judge import run_check
from pressf.judge.aggregate import aggregate_retrieval_quality_verdict
from pressf.llm import prompts
from pressf.schemas import (
    Chunk,
    ContextChunk,
    Example,
    RetrievalChunkRelevance,
    RetrievalRelevanceResult,
    SearchQualityResult,
)


class SearchClient:
    def __init__(self):
        self.users: list[str] = []

    def parse(self, *, model, system, user, schema, max_tokens=4000):
        self.users.append(user)
        if schema is SearchQualityResult:
            return SearchQualityResult(
                status="context_partial",
                missing_information="The retrieved context does not include the cancellation deadline.",
                helpful_quote="You can cancel from billing.",
                helpful_source_index=0,
                confidence=0.91,
                reasoning="The context has the action but misses the deadline.",
            ), 0.01
        assert schema is RetrievalRelevanceResult
        return RetrievalRelevanceResult(
            relevances=[RetrievalChunkRelevance(chunk_index=0, relevance=2)]
        ), 0.002


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
    assert summary.retrieval_metrics is not None
    assert summary.retrieval_metrics.precision_at_k[1] == 1.0
    assert summary.retrieval_metrics.precision_at_k[10] == 0.1
    assert "rag-log#1" in client.users[0]
    assert "This should not be used" not in client.users[0]


class GoldSearchClient:
    """Gold relevance must not cause a second LLM request."""

    def __init__(self):
        self.calls = 0

    def parse(self, *, model, system, user, schema, max_tokens=4000):
        self.calls += 1
        assert schema is SearchQualityResult
        return SearchQualityResult(
            status="context_sufficient",
            helpful_quote="Cancel from billing.",
            helpful_source_index=0,
            confidence=0.9,
            reasoning="The first result answers the question.",
        ), 0.01


def test_retrieval_quality_gold_metrics_do_not_call_relevance_judge(tmp_path: Path):
    project = Project(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()
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
                context=[
                    ContextChunk(text="Cancel from billing.", source="billing", id="doc-1"),
                    ContextChunk(text="Unrelated", source="other", id="doc-2"),
                ],
                relevant_ids=["doc-1"],
            )
        ],
    )
    client = GoldSearchClient()

    summary = run_check(project, client)

    assert client.calls == 1
    assert summary.retrieval_metrics is not None
    assert summary.retrieval_metrics.examples == 1
    assert summary.retrieval_metrics.mrr == 1.0
    assert summary.retrieval_metrics.recall_at_k[1] == 1.0


class IncompleteGradeClient(SearchClient):
    def parse(self, *, model, system, user, schema, max_tokens=4000):
        if schema is RetrievalRelevanceResult:
            return RetrievalRelevanceResult(
                relevances=[RetrievalChunkRelevance(chunk_index=0, relevance=1)]
            ), 0.002
        return super().parse(model=model, system=system, user=user, schema=schema, max_tokens=max_tokens)


def test_retrieval_quality_omits_metrics_for_incomplete_llm_grades(tmp_path: Path):
    project = Project(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(
        project="search", task="retrieval_quality",
        retriever=RetrieverConfig(kind="docs_folder", path=str(kb)), llm=LLMConfig(),
    ))
    write_jsonl_atomic(project.examples_path, [Example(
        id="e1", question="How do I cancel?", answer="Cancel from billing.",
        context=[
            ContextChunk(text="Cancel from billing.", source="billing"),
            ContextChunk(text="Other", source="other"),
        ],
    )])

    summary = run_check(project, IncompleteGradeClient())

    assert summary.retrieval_metrics is None
    assert project.load_verdicts()["e1"].retrieval_metrics is None
