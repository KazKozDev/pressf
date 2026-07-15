"""All pydantic data schemas for the project.

Schemes are divided into three groups:
- pipeline data: Example, Verdict, Annotation (live in the project’s jsonl files);
- answers LLM (structured outputs): ExtractedClaims, VerificationResult, AnswerabilityResult;
- search: Chunk (retriever contract)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


#── search ───────────────────────────────── ─────────────────────────────────


class Chunk(BaseModel):
    """Retriever issue unit."""

    text: str
    source: str
    score: float | None = None


#── pipeline data ─────────────────────────── ────────────────────────────


class ContextChunk(BaseModel):
    """The chunk that the checked RAG used during generation (from the logs)."""

    text: str
    source: str | None = None


class DialogTurn(BaseModel):
    """One replica of a multi-way dialogue (from the conversation bot logs)."""

    role: Literal["user", "assistant"]
    content: str


class ToolCall(BaseModel):
    """One recorded call to an external tool during an agent run."""

    name: str
    arguments: dict | str
    result: str | None = None
    error: str | None = None
    duration_ms: int | None = None


class TrajectoryStep(BaseModel):
    """A visible step in an agent trajectory; hidden reasoning is never required."""

    kind: Literal["thought", "tool_call", "answer"]
    content: str | None = None
    tool: ToolCall | None = None
    index: int

    @model_validator(mode="after")
    def _shape_matches_kind(self):
        if self.kind == "tool_call" and self.tool is None:
            raise ValueError("tool_call steps require tool")
        if self.kind != "tool_call" and self.tool is not None:
            raise ValueError("only tool_call steps may contain tool")
        return self


class Example(BaseModel):
    """Normalized example after ingest.

    Single case - question→answer pair. For conversational bots there is an optional
    dialog: full history; then question is the user’s last comment, answer is
    The assistant’s last remark (that’s what we’re judging), and the previous moves give the judge context."""

    id: str
    question: str
    answer: str
    answer_b: str | None = None
    context: list[ContextChunk] | None = None
    dialog: list[DialogTurn] | None = None
    trajectory: list[TrajectoryStep] | None = None
    meta: dict = Field(default_factory=dict)


ClaimStatus = Literal["supported", "contradicted", "not_found"]

Category = Literal[
    "correct",
    "partial",
    "hallucination_contradicts",
    "hallucination_unanswerable",
    "false_refusal",
    "correct_refusal",
    "compliant",
    "violates_policy",
    "unclear_policy",
    "context_sufficient",
    "context_partial",
    "context_missing",
    "a_better",
    "b_better",
    "tie",
    "trajectory_ok",
    "trajectory_inefficient",
    "trajectory_unfaithful",
    "trajectory_unsafe",
    "trajectory_wrong_answer",
]


class Evidence(BaseModel):
    """Quote-proof from the knowledge base."""

    text: str
    source: str
    score: float | None = None


class ClaimVerdict(BaseModel):
    text: str
    status: ClaimStatus
    evidence: list[Evidence] = Field(default_factory=list)


class Verdict(BaseModel):
    """The agent-judge's verdict based on one example."""

    example_id: str
    claims: list[ClaimVerdict] = Field(default_factory=list)
    is_refusal: bool = False
    answerable: bool
    grounded: bool | None = None  #None for faults: axis not applicable
    recommendation: Literal["p", "f"]
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    judge_model: str
    step_issues: list["TrajectoryStepVerdict"] | None = None
    escalated: bool = False
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


class Annotation(BaseModel):
    """Human decision. Log append-only; undo is a separate event."""

    example_id: str
    label: Literal["p", "f", "s"]
    note: str | None = None
    agreed_with_agent: bool | None = None
    undone: bool = False
    ts: datetime = Field(default_factory=utcnow)
    annotator: str = ""
    elapsed_ms: int | None = None


class PairwiseAnnotation(BaseModel):
    """Human decision for pairwise_compare. Stored separately from p/f/s labels."""

    example_id: str
    winner: Literal["a", "b", "tie"]
    shown_left: Literal["a", "b"] = "a"
    note: str | None = None
    undone: bool = False
    ts: datetime = Field(default_factory=utcnow)
    annotator: str = ""
    elapsed_ms: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_choice(cls, data: Any):
        if isinstance(data, dict) and "winner" not in data and "choice" in data:
            return {**data, "winner": data["choice"], "shown_left": data.get("shown_left", "a")}
        return data


#── answers LLM (structured outputs) ──────────────────── ────────────────────


class ExtractedClaims(BaseModel):
    """Stage 1: answer → atomic verifiable assertions."""

    model_config = ConfigDict(extra="forbid")

    is_refusal: bool = Field(
        description="true if the answer is refusal («this is not in the documentation», «can't answer»)"
    )
    claims: list[str] = Field(
        description="Atomic factual statements from the answer, each verifiable separately. Empty on failure."
    )


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int = Field(description="Chunk number from the list FOUND IN THE BASE (from 0)")
    quote: str = Field(description="Verbatim quote from this chunk")


class ClaimCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(description="Approval number from the list (from 0)")
    status: ClaimStatus
    evidence: list[EvidenceRef] = Field(
        description="Evidence quotes. For not_found - empty."
    )


class VerificationResult(BaseModel):
    """Stage 2: checking all marks against the found chunks."""

    model_config = ConfigDict(extra="forbid")

    checks: list[ClaimCheck]
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the aggregate verdict, 0..1"
    )
    reasoning: str = Field(
        description="2-3 sentences for the annotator: what’s wrong or why everything is ok"
    )


class AnswerabilityResult(BaseModel):
    """For refusal answers: was there an answer to the question in the database at all."""

    model_config = ConfigDict(extra="forbid")

    answerable: bool = Field(description="true if the database contains the answer to the question")
    evidence: list[EvidenceRef] = Field(
        description="Quotes containing the answer (if answerable)"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="2-3 sentences for the annotator")


PolicyStatus = Literal["compliant", "violates_policy", "unclear_policy"]


class PolicyCheckResult(BaseModel):
    """Policy compliance task: answer vs company rules."""

    model_config = ConfigDict(extra="forbid")

    status: PolicyStatus
    offending_sentence: str | None = Field(
        default=None, description="Sentence from the answer that breaks the rule, if any"
    )
    rule_quote: str | None = Field(default=None, description="Verbatim quote from the policy/rule")
    rule_source_index: int | None = Field(default=None, description="Chunk index for the rule quote")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Short explanation for the human reviewer")


SearchQualityStatus = Literal["context_sufficient", "context_partial", "context_missing"]


class SearchQualityResult(BaseModel):
    """Search quality task: retrieved context vs question/answer."""

    model_config = ConfigDict(extra="forbid")

    status: SearchQualityStatus
    missing_information: str | None = Field(
        default=None, description="What the retrieved context lacks, if it is partial or missing"
    )
    helpful_quote: str | None = Field(default=None, description="Best quote from retrieved context")
    helpful_source_index: int | None = Field(default=None, description="Chunk index for helpful_quote")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Short explanation for the human reviewer")


PairwiseStatus = Literal["a_better", "b_better", "tie"]


class PairwiseCompareResult(BaseModel):
    """Pairwise compare task: answer A vs answer B."""

    model_config = ConfigDict(extra="forbid")

    status: PairwiseStatus
    evidence_quote: str | None = Field(default=None, description="Best quote from evidence, if relevant")
    evidence_source_index: int | None = Field(default=None, description="Chunk index for evidence_quote")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="One-sentence reason for the preferred answer or tie")


TrajectoryIssueKind = Literal[
    "fabricated_tool_result",
    "unnecessary_call",
    "wrong_arguments",
    "ignored_result",
    "loop",
    "unsafe_action",
    "other",
]


class TrajectoryStepVerdict(BaseModel):
    """Judge finding for one recorded trajectory step."""

    model_config = ConfigDict(extra="forbid")

    step_index: int
    ok: bool
    issue: str | None = None
    issue_kind: TrajectoryIssueKind | None = None


class TrajectoryResult(BaseModel):
    """Single-call structured judgement of an agent execution trajectory."""

    model_config = ConfigDict(extra="forbid")

    steps: list[TrajectoryStepVerdict]
    final_answer_ok: bool
    efficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
