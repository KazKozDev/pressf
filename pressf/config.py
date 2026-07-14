"""Project config (lazy.yaml) and layout of working directory files."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .io import read_jsonl
from .schemas import Annotation, Example, PairwiseAnnotation, Verdict


class RetrieverConfig(BaseModel):
    """The parameters depend on kind - extra fields are allowed (the adapter itself knows what it needs)."""

    model_config = ConfigDict(extra="allow")

    kind: str
    top_k: int = 8


class EmbeddingsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "sentence_transformers"
    model: str = ""


class LLMConfig(BaseModel):
    provider: str = "anthropic"  # anthropic | openai | openai_compatible (Ollama/vLLM/Together/DeepSeek/...)
    judge_model: str = "claude-haiku-4-5"
    escalation_model: str = "claude-opus-4-8"
    escalation_threshold: float = 0.7
    use_batch_api: bool = True  #50% discount; for < batch_min_examples it is still sync
    batch_min_examples: int = 5
    batch_poll_seconds: int = 20
    max_budget_usd: float = 10.0
    #only for openai_compatible:
    base_url: str | None = None  #for example http://localhost:11434/v1 (Ollama)
    price_input_per_mtok: float = 0.0  #$/MTok; local models - 0
    price_output_per_mtok: float = 0.0

    @model_validator(mode="after")
    def _provider_defaults(self):
        """We do not allow anthropic model defaults to leak to someone else's provider."""
        if self.provider == "openai":
            if self.judge_model.startswith("claude"):
                self.judge_model = "gpt-5.4-mini"
            if self.escalation_model.startswith("claude"):
                self.escalation_model = "gpt-5.4"
        elif self.provider == "openai_compatible":
            if self.judge_model.startswith("claude"):
                raise ValueError(
                    "provider=openai_compatible requires an explicit judge_model"
                    "(model name on your server, for example llama3.3:70b)"
                )
            if self.escalation_model.startswith("claude"):
                self.escalation_model = self.judge_model  #escalation is disabled by default
        return self


class IngestConfig(BaseModel):
    """Column mapping is stored so that lazy add can reload data without any questions."""

    question: str = "question"
    answer: str = "answer"
    context: str | None = None
    id: str | None = None


class ExportConfig(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["jsonl"])


class BotConfig(BaseModel):
    """How to call the bot you are checking to run goldset questions through it.

    Two universal methods (see pressf/bot):
    - kind=command — shell command template; {question} is substituted into the arguments,
      or (if there is no placeholder) the question goes to the bot on stdin; the response is read from stdout;
    - kind=http — POST/GET on endpoint; body - JSON-template with {question};
      the answer is obtained from JSON via the dotted answer_path.
    The supported connector fields are explicit so invalid configuration is rejected."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # command | http
    timeout: float = 60.0
    answer_path: str | None = None  #dotted-path to response, if the bot responds with JSON-th
    command: str | None = None
    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] | None = None
    body: str | None = None


def canonical_task(task: str | None) -> str:
    task = task or "rag_faithfulness"
    return {"search_quality": "retrieval_quality", "compare_versions": "pairwise_compare"}.get(task, task)


class ProjectConfig(BaseModel):
    project: str
    task: str = "rag_faithfulness"
    retriever: RetrieverConfig
    embeddings: EmbeddingsConfig | None = None
    ingest: IngestConfig | None = None
    llm: LLMConfig = Field(default_factory=LLMConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    bot: BotConfig | None = None

    @model_validator(mode="after")
    def _canonical_task(self):
        self.task = canonical_task(self.task)
        return self


CONFIG_FILE = "lazy.yaml"


class Project:
    """Project working directory: config + all data files."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    #── layout ─────────────────────────── ───────────────────────────
    @property
    def config_path(self) -> Path:
        return self.root / CONFIG_FILE

    @property
    def guidelines_path(self) -> Path:
        return self.root / "GUIDELINES.md"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def examples_path(self) -> Path:
        return self.data_dir / "examples.jsonl"

    @property
    def verdicts_path(self) -> Path:
        return self.data_dir / "verdicts.jsonl"

    @property
    def annotations_path(self) -> Path:
        return self.data_dir / "annotations.jsonl"

    @property
    def pairwise_annotations_path(self) -> Path:
        return self.data_dir / "pairwise_annotations.jsonl"

    @property
    def ingest_report_path(self) -> Path:
        return self.data_dir / "ingest_report.md"

    @property
    def selfcheck_path(self) -> Path:
        return self.data_dir / "selfcheck.jsonl"

    @property
    def out_dir(self) -> Path:
        return self.root / "out"

    #── config ──────────────────────────── ─────────────────────────────
    def exists(self) -> bool:
        return self.config_path.exists()

    def load_config(self) -> ProjectConfig:
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return ProjectConfig.model_validate(raw)

    def save_config(self, cfg: ProjectConfig) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(cfg.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def load_guidelines(self) -> str:
        if self.guidelines_path.exists():
            return self.guidelines_path.read_text(encoding="utf-8")
        return ""

    #── data ──────────────────────────── ─────────────────────────────
    def load_examples(self) -> list[Example]:
        return read_jsonl(self.examples_path, Example)

    def load_verdicts(self) -> dict[str, Verdict]:
        """Last verdict for each example_id (re-check overwrites)."""
        out: dict[str, Verdict] = {}
        for v in read_jsonl(self.verdicts_path, Verdict):
            out[v.example_id] = v
        return out

    def load_annotation_log(self) -> list[Annotation]:
        return read_jsonl(self.annotations_path, Annotation)

    def load_pairwise_annotation_log(self) -> list[PairwiseAnnotation]:
        return read_jsonl(self.pairwise_annotations_path, PairwiseAnnotation)

    def effective_annotations(self) -> dict[str, Annotation]:
        """Effective markup state: the undone=True event clears the previous decision."""
        state: dict[str, Annotation] = {}
        for a in self.load_annotation_log():
            if a.undone:
                state.pop(a.example_id, None)
            else:
                state[a.example_id] = a
        return state

    def effective_annotations_by_annotator(self) -> dict[str, dict[str, str]]:
        """Effective labels per annotator - for inter-annotator agreement.

        {annotator_name: {example_id: label}}. undo is taken into account within the annotator.
        An empty name ("") is also considered a separate «marker»."""
        state: dict[str, dict[str, str]] = {}
        for a in self.load_annotation_log():
            who = a.annotator or ""
            bucket = state.setdefault(who, {})
            if a.undone:
                bucket.pop(a.example_id, None)
            else:
                bucket[a.example_id] = a.label
        return {who: labels for who, labels in state.items() if labels}

    def effective_pairwise_annotations(self) -> dict[str, PairwiseAnnotation]:
        state: dict[str, PairwiseAnnotation] = {}
        for a in self.load_pairwise_annotation_log():
            if a.undone:
                state.pop(a.example_id, None)
            else:
                state[a.example_id] = a
        return state
