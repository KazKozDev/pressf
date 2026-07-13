"""Dialog agent pressf (PLAN.md §4.1): lazy init --chat.

The principle of «offers, not interrogates»: the agent himself looks at the material through
tools and offers options; the person answers in free text.
The first move is to inspect the project (project_status), then find out the scenario:
mark up logs / calibrate the judge using a ready-made goldset / assemble a goldset
from scratch / continue an existing project.
Under the hood is a state machine of stages: finalize will not take place until the stages are closed.

WizardEngine (tools + state) is decoupled from the conversation loop and tested without LLM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import (
    ExportConfig,
    IngestConfig,
    LLMConfig,
    Project,
    ProjectConfig,
    RetrieverConfig,
)
from .ingest import ColumnMapping, load_rows, run_ingest
from .ingest.validate import example_key
from .io import append_jsonl
from .schemas import Annotation

WIZARD_MODEL = "claude-opus-4-8"
MAX_TURNS = 60

TOOLS: list[dict[str, Any]] = [
    {
        "name": "project_status",
        "description": "Inspect the project directory: is there lazy.yaml, how many examples,"
        "judge's verdicts and human marks, human/judge agreement."
        "Call FIRST - before any questions to the user.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_dir",
        "description": "Show directory contents (file and subdirectory names).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        },
    },
    {
        "name": "peek_file",
        "description": "Look at the data file: number of lines, columns, first 3 lines."
        "Call BEFORE offering the user task options and mapping.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path (jsonl/csv/tsv/xlsx)"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_ingest",
        "description": "Load data into the project: validation, dedup, report."
        "Call after the user has confirmed the column mapping.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_path": {"type": "string"},
                "question_col": {"type": "string"},
                "answer_col": {"type": "string"},
                "context_col": {"type": "string", "description": "Optional: column with chunks RAG-a"},
                "id_col": {"type": "string", "description": "Optional: column with id"},
            },
            "required": ["data_path", "question_col", "answer_col"],
        },
    },
    {
        "name": "write_guidelines",
        "description": "Write GUIDELINES.md — markup guidelines generated from the task description"
        "user. Markdown: problem, p/f/s definitions, edge cases with examples.",
        "input_schema": {
            "type": "object",
            "properties": {"markdown": {"type": "string"}},
            "required": ["markdown"],
        },
    },
    {
        "name": "test_retriever",
        "description": "Connect to the knowledge base and perform a test search (smoke test)."
        "kind: docs_folder | chunks_file | chroma | faiss | qdrant | pgvector | pinecone | weaviate | milvus | elastic | lancedb. "
        "params — parameters of a specific adapter (path, collection, url, dsn, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "params": {"type": "object", "description": "Adapter settings"},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "import_labels",
        "description": "Import ready-made human markup (script «is marked up"
        "goldset - calibrating the judge »). Call after run_ingest of the same file."
        'label_map translates column values ​​into p/f/s, for example {"pass": "p", "fail": "f"}.'
        "Comparison with examples: by id_col, otherwise by question+answer pair.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_path": {"type": "string"},
                "label_col": {"type": "string", "description": "Column with human mark"},
                "label_map": {"type": "object", "description": "column value → p | f | s"},
                "id_col": {"type": "string", "description": "Optional: column with example id"},
                "question_col": {"type": "string", "description": "For mapping without id (default - ingest mapping)"},
                "answer_col": {"type": "string"},
            },
            "required": ["data_path", "label_col", "label_map"],
        },
    },
    {
        "name": "finalize",
        "description": "Complete setup: write lazy.yaml. Will only work when passed"
        "all stages (ingest, guidelines, retriever). Call after user confirmation."
        "Judge: llm_provider anthropic (default) | openai | openai_compatible"
        "(for the latter, judge_model and base_url are required).",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "llm_provider": {"type": "string", "description": "anthropic | openai | openai_compatible"},
                "judge_model": {"type": "string"},
                "base_url": {"type": "string", "description": "URL OpenAI-compatible server (Ollama/vLLM/...)"},
            },
            "required": ["project_name"],
        },
    },
    {
        "name": "done",
        "description": "End the session WITHOUT the lazy.yaml entry - only when the new config is not needed:"
        "the project has already been configured (scenario «continue») or there is no data yet and we were only consulting."
        "To set up a new project, use finalize."
        "summary - what has been done and what commands to run next.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]

SYSTEM = """You are a pressf agent: LLM-judge fact-checks the answers of RAG-bot against the knowledge base,
the person quickly reviews the verdicts at TUI (p/f/s). The result is a goldset verified by a person,
and understanding where the judge can be trusted.

The first move is ALWAYS project_status: look at what is already on the disk before asking questions.

Next, figure out the scenario. If it is obvious from the user's status and words, don't ask.
act. If not, offer a choice (briefly, with a recommendation based on the situation):
1. «There are bot logs: questions + answers» → main path: peek_file → run_ingest →
   write_guidelines → test_retriever → judge's choice → finalize.
   Next: lazy check → lazy review → lazy export.
2. «There is a ready-made marked goldset» → judge calibration: run_ingest → import_labels →
   write_guidelines → test_retriever → finalize. Explain: lazy check will drive the judge away for the same reasons
   examples, the report will show agreement with human markup, lazy export --disagreements
   will unload discrepancies.
3. «There is nothing, just a bot and documentation» → tell me honestly: run questions through someone else
   The bot can't pressf. Help me prepare: data format - jsonl with question/answer fields
   (optional id, context with RAG-a chunks), questions should be taken from real logs or
   write according to the documentation. The base and guidelines can be configured now; no data
   complete done with instructions on what to bring.
4. The project already exists (visible in project_status) → suggest the next step based on the status:
   no verdicts → lazy check; verdicts without markup → lazy review; everything is marked →
   lazy export; fresh logs → lazy add --data. Finish with done.

Give me a hint to the place (don’t just throw out a list):
- f-tags have accumulated → lazy export --pairs (blanks DPO-pairs for additional training);
- there is both marking and verdicts → lazy export --disagreements (judge calibration),
  lazy review --self-check (stability of the annotator itself);
- updated the bot → run the same questions through the new version, upload to a new project
  (or lazy add) and compare reports.

Rules of conduct:
- SUGGEST, DON'T INTERROGATE. First, look at the material yourself (project_status/peek_file/
  list_dir), then offer 2-4 specific options with a recommendation. No empty «what do you want?».
- One question per turn. The user can respond in free text - interpret.
- Options are born from the data: there is a column with chunks → offer a faithfulness check;
  free answer («where the bot is lying») reduce it to the task yourself.
- Write the guidelines yourself from the task description (write_guidelines), show the user the essence
  and ask for confirmation, don’t force him to write.
- Before finalize, ask about the judge: anthropic (default, Batch API −50%) | openai |
  openai_compatible (Ollama/vLLM locally or Together/DeepSeek/... - base_url and
  judge_model). Remind me about the key: ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENAI_COMPAT_API_KEY.
- If there is an error connecting to the database, do not give up: offer to check the parameters or go
  to docs_folder / chunks_file mode.
- Before finalizing, briefly summarize the configuration and wait for confirmation.
- Language: answer in the user’s language (Russian → in Russian); if the language is not clear -
  in English. Short and to the point.

Stages for finalize (the state comes in the results of the tools): ingest → guidelines → retriever."""


class WizardEngine:
    """Tools + state machine. No LLM calls inside - tested directly."""

    def __init__(self, root: Path | str):
        self.project = Project(root)
        self.project.root.mkdir(parents=True, exist_ok=True)
        #We recognize an existing project by its config: its stages have already been completed during the initial setup
        self._existing_cfg: ProjectConfig | None = None
        if self.project.exists():
            try:
                self._existing_cfg = self.project.load_config()
            except Exception:
                self._existing_cfg = None  #Broken config - set it up again
        self.ingest_done = self.project.examples_path.exists()
        self.guidelines_done = self.project.guidelines_path.exists()
        self.retriever_tested = self._existing_cfg is not None
        self.finalized = False
        self.completed = False  #completion via done - without writing the config
        self._mapping: IngestConfig | None = self._existing_cfg.ingest if self._existing_cfg else None
        self._retr_cfg: RetrieverConfig | None = self._existing_cfg.retriever if self._existing_cfg else None
        self._first_question: str | None = None

    #── stages ──────────────────────────── ─────────────────────────────
    def stages(self) -> dict[str, bool]:
        return {
            "ingest": self.ingest_done,
            "guidelines": self.guidelines_done,
            "retriever": self.retriever_tested,
            "finalized": self.finalized,
        }

    def _with_stages(self, text: str) -> str:
        return f"{text}\n\n[stages:{json.dumps(self.stages(), ensure_ascii=False)}]"

    #── tools ────────────────────────── ──────────────────────────
    def handle_tool(self, name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        """Returns (result text, is_error)."""
        try:
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                return f"Unknown tool:{name}", True
            return self._with_stages(handler(**tool_input)), False
        except Exception as e:
            return self._with_stages(f"Error:{e}"), True

    def _tool_project_status(self) -> str:
        p = self.project
        lines = [f"Directory: {p.root}"]
        if self._existing_cfg:
            cfg = self._existing_cfg
            lines.append(
                f"lazy.yaml: yes - project «{cfg.project}», "
                f"judge {cfg.llm.provider}/{cfg.llm.judge_model}, retriever {cfg.retriever.kind}"
            )
        else:
            lines.append("lazy.yaml: no - the project is not configured")
        examples = p.load_examples() if p.examples_path.exists() else []
        lines.append(f"Examples: {len(examples)}")
        verdicts = p.load_verdicts() if p.verdicts_path.exists() else {}
        if verdicts:
            recs: dict[str, int] = {}
            for v in verdicts.values():
                recs[v.recommendation] = recs.get(v.recommendation, 0) + 1
            lines.append(f"Judge verdicts: {len(verdicts)} ({json.dumps(recs, ensure_ascii=False)})")
        else:
            lines.append("Judge's verdicts: 0")
        anns = p.effective_annotations() if p.annotations_path.exists() else {}
        if anns:
            counts = {"p": 0, "f": 0, "s": 0}
            agreed = judged = 0
            for eid, a in anns.items():
                counts[a.label] += 1
                v = verdicts.get(eid)
                if v is not None and a.label in ("p", "f"):
                    judged += 1
                    agreed += int(a.label == v.recommendation)
            agr = f", agreement with the judge {agreed}/{judged}" if judged else ""
            lines.append(
                f"Human labels: {len(anns)} (p={counts['p']}, f={counts['f']}, s={counts['s']}{agr})"
            )
            lines.append(f"Unreviewed: {sum(1 for ex in examples if ex.id not in anns)}")
        else:
            lines.append("Human labels: 0")
        if p.out_dir.is_dir():
            names = sorted(f.name for f in p.out_dir.iterdir())
            if names:
                lines.append("Exported: " + ", ".join(names[:6]))
        return "\n".join(lines)

    def _tool_list_dir(self, path: str) -> str:
        p = Path(path).expanduser()
        if not p.is_dir():
            raise FileNotFoundError(f"Not a directory:{p}")
        entries = sorted(p.iterdir())[:50]
        return "\n".join(("[dir] " if e.is_dir() else "") + e.name for e in entries) or "(empty)"

    def _tool_peek_file(self, path: str) -> str:
        rows = load_rows(Path(path))
        cols = sorted({k for r in rows[:20] for k in r if not str(k).startswith("_")})
        sample = json.dumps(rows[:3], ensure_ascii=False, indent=1)[:1500]
        return f"Rows: {len(rows)}\nColumns: {', '.join(map(str, cols))}\nFirst rows:\n{sample}"

    def _tool_run_ingest(
        self,
        data_path: str,
        question_col: str,
        answer_col: str,
        context_col: str | None = None,
        id_col: str | None = None,
    ) -> str:
        rows = load_rows(Path(data_path))
        mapping = ColumnMapping(question=question_col, answer=answer_col, context=context_col, id=id_col)
        result = run_ingest(self.project, rows, mapping, raw_file=data_path)
        if not result.accepted:
            raise ValueError("not a single valid example - check the column mapping")
        self.ingest_done = True
        self._mapping = IngestConfig(question=question_col, answer=answer_col, context=context_col, id=id_col)
        self._first_question = result.accepted[0].question
        rejected = "; ".join(f"line{n}: {r}" for n, r in result.rejected[:5])
        return (
            f"Accepted {len(result.accepted)} of {result.total} "
            f"(duplicates {result.duplicates}, rejected {len(result.rejected)}). "
            + (f"Rejected examples: {rejected}" if rejected else "")
        )

    def _tool_write_guidelines(self, markdown: str) -> str:
        self.project.guidelines_path.write_text(markdown, encoding="utf-8")
        self.guidelines_done = True
        return f"GUIDELINES.md recorded ({len(markdown)}characters)"

    def _tool_test_retriever(self, kind: str, params: dict[str, Any] | None = None) -> str:
        from .retrievers import build_retriever

        cfg = RetrieverConfig(kind=kind, **(params or {}))
        retriever = build_retriever(cfg)
        health = retriever.healthcheck()
        query = self._first_question or "test request"
        hits = retriever.search(query, 3)
        preview = "\n".join(f"- {h.source}: {h.text[:120]}" for h in hits[:2]) or "(nothing found!)"
        self._retr_cfg = cfg
        self.retriever_tested = True
        return f"{health}\nTest search by «{query[:80]}»: {len(hits)}chunks\n{preview}"

    def _tool_import_labels(
        self,
        data_path: str,
        label_col: str,
        label_map: dict[str, str],
        id_col: str | None = None,
        question_col: str | None = None,
        answer_col: str | None = None,
    ) -> str:
        if not self.ingest_done:
            raise RuntimeError("first run_ingest - labels are attached to loaded examples")
        examples = self.project.load_examples()
        by_id = {ex.id: ex for ex in examples}
        by_key = {example_key(ex.question, ex.answer): ex for ex in examples}
        q_col = question_col or (self._mapping.question if self._mapping else None)
        a_col = answer_col or (self._mapping.answer if self._mapping else None)
        norm_map = {str(k).strip().lower(): v for k, v in label_map.items()}
        verdicts = self.project.load_verdicts() if self.project.verdicts_path.exists() else {}
        already = set(self.project.effective_annotations())
        counts = {"p": 0, "f": 0, "s": 0}
        unmatched = unknown = skipped = 0
        for row in load_rows(Path(data_path)):
            label = norm_map.get(str(row.get(label_col, "")).strip().lower())
            if label not in ("p", "f", "s"):
                unknown += 1
                continue
            ex = by_id.get(str(row[id_col])) if id_col and row.get(id_col) is not None else None
            if ex is None and q_col and a_col:
                ex = by_key.get(example_key(str(row.get(q_col) or ""), str(row.get(a_col) or "")))
            if ex is None:
                unmatched += 1
                continue
            if ex.id in already:
                skipped += 1
                continue
            v = verdicts.get(ex.id)
            agreed = (label == v.recommendation) if v is not None and label in ("p", "f") else None
            append_jsonl(
                self.project.annotations_path,
                Annotation(example_id=ex.id, label=label, agreed_with_agent=agreed, annotator="imported"),  # type: ignore[arg-type]
            )
            already.add(ex.id)
            counts[label] += 1
        total = sum(counts.values())
        return (
            f"Imported labels: {total} (p={counts['p']}, f={counts['f']}, s={counts['s']}); "
            f"unmatched examples: {unmatched}, "
            f"unknown values in {label_col}: {unknown}, already labeled: {skipped}"
        )

    def _tool_finalize(
        self,
        project_name: str,
        llm_provider: str | None = None,
        judge_model: str | None = None,
        base_url: str | None = None,
    ) -> str:
        missing = [k for k, done in self.stages().items() if not done and k != "finalized"]
        if missing:
            raise RuntimeError(f"cannot be completed: stages not completed{missing}")
        llm_kwargs = (self._existing_cfg.llm if self._existing_cfg else LLMConfig()).model_dump()
        if llm_provider:
            llm_kwargs["provider"] = llm_provider
        if judge_model:
            llm_kwargs["judge_model"] = judge_model
        if base_url:
            llm_kwargs["base_url"] = base_url
        cfg = ProjectConfig(
            project=project_name,
            task=self._existing_cfg.task if self._existing_cfg else "rag_faithfulness",
            retriever=self._retr_cfg,  # type: ignore[arg-type]
            embeddings=self._existing_cfg.embeddings if self._existing_cfg else None,
            ingest=self._mapping,
            llm=LLMConfig.model_validate(llm_kwargs),
            export=self._existing_cfg.export if self._existing_cfg else ExportConfig(),
        )
        self.project.save_config(cfg)
        self.finalized = True
        return f"lazy.yaml is written:{self.project.config_path}. Next: lazy check → lazy review → lazy export"

    def _tool_done(self, summary: str) -> str:
        self.completed = True
        return f"The session ended without changing the config.{summary}"


def run_wizard(root: Path | str, console, first_message: str | None = None) -> bool:
    """Conversation cycle. Returns True if the project is finalized."""
    import anthropic

    client = anthropic.Anthropic()
    engine = WizardEngine(root)
    intro = first_message or (
        "Inspect the project (project_status) and figure out my scenario: help me label "
        "bot logs, calibrate the judge against an existing goldset, start a goldset from "
        "scratch, or continue an existing project. Reply in English until I switch language."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": intro}]

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=WIZARD_MODEL,
            max_tokens=2000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    console.print(block.text)
                elif block.type == "tool_use":
                    console.print(f"[dim]⚙ {block.name}[/dim]")
                    output, is_error = engine.handle_tool(block.name, block.input)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id,
                         "content": output, "is_error": is_error}
                    )
            messages.append({"role": "user", "content": results})
            continue

        text = next((b.text for b in response.content if b.type == "text"), "")
        if text.strip():
            console.print(text)
        if engine.finalized or engine.completed:
            return True
        try:
            user_input = console.input("[b cyan]you>[/b cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            return engine.finalized or engine.completed
        if user_input.lower() in ("/q", "/quit", "exit"):
            return engine.finalized or engine.completed
        messages.append({"role": "user", "content": user_input or "continue"})

    console.print("[yellow]The dialogue turn limit has been reached. The progress of the stages is saved on disk.[/yellow]")
    return engine.finalized or engine.completed
