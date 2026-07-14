# pressf — plan

**«Lazy annotation» tool** (pressf, ex-LazyAnnotator; name chosen 2026-07-11: «Press F to pay respects» + p/f/s keys): the agent does all the dirty work of creating a goldset for RAG/LLM systems; the human only presses `p`/`f`/`s`. The output is a human-verified, versioned, ready-to-use dataset. No coding on the user's side. Python package and canonical CLI is `pressf`, short CLI alias is `lazy`, config file is `lazy.yaml`.

## 1. Concept

Four stages, the agent guides the user by the hand:

```
 raw material      wizard          fact-check        TUI-review       dataset
 (CSV/JSONL/       no-code         by agent          by human        + report
  Excel/logs)      setup           (offline/         (p/f/s/u/n)
                                    overnight)
```

Key principles:
- **Human = reviewer, not annotator.** The agent issues a preliminary verdict with reasoning and citations from the knowledge base; the human confirms with a single key.
- **Two verdict axes are never mixed**: answerability (was the answer in the knowledge base at all) and groundedness (does the given answer match the knowledge base). These are different types of RAG errors and are fixed differently.
- **Annotation flies**: all LLM calls are an offline phase; the TUI works instantly.
- **Every keystroke is an atomic write.** Process crash does not lose work; resume from the same spot.
- **Anchoring bias is mitigated** by citations (verifying a citation is easy and honest) and human/agent agreement statistics.

### 1.1 Applicability (descending practical value)

1. **RAG regression testing — the main use case.** Every team with RAG in production has the eternal question: «we changed chunking/embeddings/prompt — is it better or worse?» Without a goldset the answer is «seems fine»; with a goldset it's a number. The tool turns a week-long task into an evening.
2. **LLM judge calibration.** Automated eval cannot be trusted until the judge is calibrated against a human. Our output is exactly this material: human labels + agent verdicts side by side. The tool literally checks itself (see agreement report, §4.4, and self-improving loop in risks).
3. **Data filtering for fine-tuning.** For SFT — directly: p-answers go into training, f-answers are discarded; p/f labeling is exactly that. For DPO — honestly: our labeling gives only the «bad» half of a pair; the «good» answer for the same question must be sourced separately (references, generation by another model). We export pair templates, not a ready DPO dataset.
4. **Production bot audit.** LLM-powered support: run fresh dialogs weekly, review in 30 minutes — a quality metric over time + a collection of failures for review.
5. **Datasets for classifiers and guardrails** — toxicity, off-topic, PII. Same binary cycle, just without the fact-check part.
6. **«Was this a hallucination» labeling** for research and reports — the project's original use case.

Design implications: use cases 1–2 require versioned self-described export and agreement statistics (present in §4.4); use case 3 requires SFT filter export and DPO pair templates (flag `--pairs`: our f-label + slot for «good» answer, M4); use case 4 requires idempotent re-run of fresh data into an existing project (`lazy check` is already idempotent, ingest must support appending); use case 5 requires a task mode without a retriever (judge without fact-check, based on guidelines; in v1 — only stub `task: classification` in config, no implementation). The setup dialog agent (§4.1) offers a task from this exact list, looking at the material.

**v1 focus rule.** Product value is proven by a single path: RAG faithfulness from raw material to goldset (use cases 1, 2, 6; use case 4 is their re-run). Filter for any new feature: «does it help this path?» — if not, it ships after v1, even if «almost ready». Use case 5 (classification without fact-check) is a separate dangerous temptation: it is Prodigy territory where we have no advantage; our uniqueness is fact-check against a knowledge base.

## 2. Architecture

```
pressf/  (repository)
│
├── cli.py               # entry point: lazy <command> (typer)
├── config.py            # project config model (pydantic), load/save YAML
├── schemas.py           # ALL pydantic data schemas (Example, Verdict, Annotation, ...)
├── ingest/
│   ├── loaders.py       # CSV / JSONL / Excel / TSV → raw records
│   ├── mapper.py        # LLM column mapping to schema (question/answer/context/id)
│   └── validate.py      # validation, dedup, error report
├── retrievers/
│   ├── __init__.py      # adapter registry, factory from config
│   ├── chroma.py
│   ├── faiss_.py
│   ├── qdrant.py
│   ├── pgvector.py
│   ├── pinecone_.py
│   ├── weaviate_.py
│   ├── milvus.py
│   ├── elastic.py       # Elasticsearch + OpenSearch (one adapter, two clients)
│   ├── lancedb_.py
│   ├── docs_folder.py   # «folder of documents» mode: chunks and indexes itself
│   └── chunks_file.py   # «exported chunks» mode (JSONL) — universal fallback
├── embeddings.py        # embedding layer for adapters that need a query vector
├── llm/
│   ├── client.py        # anthropic SDK wrapper: retry, cache breakpoints, $ counter
│   ├── batch.py         # Batch API: collect/submit/poll/parse
│   └── prompts.py       # all prompts in one place (judge, mapper, wizard)
├── judge/
│   ├── claims.py        # answer → atomic claims
│   ├── verify.py        # claim + chunks → supported/contradicted/not_found
│   ├── aggregate.py     # claims → final verdict (p/f + category + confidence)
│   └── escalate.py      # uncertain verdicts → re-review by senior model
├── review/
│   ├── tui.py           # textual app: card, keys, status bar
│   ├── session.py       # example ordering, resume, undo stack, atomic write
│   └── agreement.py     # human/agent agreement stats, self-check sampling
├── export/
│   └── report.py        # final report (md): numbers, disagreements, skips
└── wizard.py            # setup dialog agent (stage 2): LLM dialog + tools + state machine

tests/
    ├── test_retrievers.py   # contract test, one for all adapters
    ├── test_judge.py        # on fixtures, LLM mocked
    ├── test_session.py      # resume, undo, atomicity
    ├── ...
```

Stack: **Python 3.11+, official `anthropic` SDK, pydantic v2, typer (CLI), textual (TUI), rich**. DB adapters — **extras** in pyproject (`pip install pressf[qdrant]`), so the base install doesn't pull nine clients.

## 3. Data Formats

All project state lives in the working directory `./<project>/`:

```
├── lazy.yaml            # config (see below)
├── GUIDELINES.md        # annotation guidelines (generated by wizard, edited by human)
├── data/
│   ├── raw/…            # raw sources as-is
│   ├── examples.jsonl   # normalized examples after ingest
│   ├── verdicts.jsonl   # agent verdicts after precheck
│   └── annotations.jsonl# human decisions (append-only log)
└── out/
    ├── goldset.jsonl    # final output
    ├── report.md
    └── ...
```

### 3.1 Example (after ingest)

```json
{"id": "ex_0001", "question": "What limit?", "answer": "1000/hour", "context": [...]}
```

`context` — chunks that the evaluated RAG used during generation (if present in logs). The judge searches the knowledge base itself, but the provided context is shown to the human.

### 3.2 Verdict (after precheck)

```json
{"example_id": "ex_0001",
 "claims": [
   {"text": "Limit is 1000 requests per hour",
    "status": "contradicted",
    "evidence": [{"text": "...citation...", "source": "doc_42", "score": 0.87}]}
 ],
 "is_refusal": false, "answerable": true,
 "grounded": false,
 "recommendation": "f", "category": "hallucination_contradicts",
 "confidence": 0.73,
 "reasoning": "2-3 sentences for the human",
 "judge_model": "claude-haiku-4-5", "escalated": false,
 "cost_usd": 0.0012}
```

Categories — product of two axes:
| answerable | model response | grounded | category | recommendation |
|------------|---------------|----------|----------|----------------|
| true | given | true | `correct` | p |
| true | given | false | `hallucination_contradicts` (or `partial`) | f |
| true | refusal | — | `false_refusal` (answer was in knowledge base, model refused) | f |
| false | given | — | `hallucination_unanswerable` | f |
| false | refusal | — | `correct_refusal` (refusal is correct behavior) | p |

For refusal examples, claims are not extracted; instead the judge checks answerability directly: searches for an answer to the question itself and decides whether the refusal was justified.

### 3.3 Annotation (human decisions, append-only)

```json
{"example_id": "ex_0001", "label": "p", "agreed_with_agent": true, "annotator": ""}
```

Undo is implemented not via deletion, but by writing an event `{"undone": true, ...}` — the log stays honest, effective state = last non-undone entry per example_id.

### 3.4 lazy.yaml (config)

```yaml
project: myproject
task: rag_faithfulness          # v1. Reserved: classification (no retriever, use case 5 from §1.1), llm_answers — post-v1
retriever:
  kind: docs_folder
  # parameters depend on kind — see §5
embeddings:                     # needed for faiss/pgvector/milvus/lancedb and docs_folder
  provider: sentence_transformers
  model: all-MiniLM-L6-v2
ingest:
  question: query             # column names in source data
  answer: response
llm:
  provider: anthropic           # anthropic | openai | openai_compatible (Ollama/vLLM/LM Studio/Together/…)
  judge_model: claude-haiku-4-5
  escalation_model: claude-opus-4-8
  escalation_threshold: 0.7     # confidence below — re-review by senior model
  use_batch_api: true
  max_budget_usd: 10.0          # kill switch: precheck stops on exceeding
export:
  formats: [jsonl, csv]
```

API key — only `ANTHROPIC_API_KEY` from the environment (BYO-key), never written to config.

## 4. Pipeline Stages

### 4.1 `lazy init` — setup dialog agent (INGEST + SETUP stages in one conversation)

Not a questionnaire, but a **dialog led by the agent**. Principle: *agent offers, not interrogates* — no empty «what do you want?»; the agent first looks at the material, then offers concrete options based on what it sees. The human responds in free text («I need to know where the bot lies to customers») or picks an option number — the LLM interprets both.

Design: LLM dialog (Opus 4.8) with a small tool set + **state machine under the hood**. The conversation form is free, but the dialog has mandatory output stages, and the agent leads toward the goal instead of chatting:

```
[data source] → [schema mapping] → [validation/dedup] → [task]
   → [guidelines approved] → [knowledge base connected and verified] → [estimate] → lazy.yaml
```

Wizard agent tools: `peek_file` (headers + sample rows), `list_dir`, `run_ingest` (validation+dedup, returns report), `test_retriever` (connection + 1 probe search), `estimate_cost` (count_tokens on sample), `write_config`, `write_guidelines`.

Stage behavior:
1. **Source**: human provides a path — agent reads headers and sample and says what it sees («this is RAG logs: questions, answers, retrieved chunks»).
2. **Task — options from the material, not a fixed menu**: agent offers 2–4 options relevant to this specific data (faithfulness / relevance / SFT filtering), with a recommendation. Free-form response («where the bot lies») is resolved to a task by the agent.
3. **Schema mapping**: suggestion («`query` → question, `response` → answer — correct?»), human confirms or corrects in words.
4. **Validation + dedup**: empty/broken rows, exact and near-duplicates; report «accepted 480 of 500, here's why rejected» → `data/ingest_report.md`.
5. **Guidelines**: from the task description, `GUIDELINES.md` is generated (positive/negative, edge cases, examples); human reads and approves, the file is open for editing.
6. **Knowledge base**: choice of retriever kind, parameters, **mandatory embedding model question** where we build the query vector. Smoke test immediately, showing real results («found 8 chunks — does this look like your database?»).
7. **Estimate**: approximate tokens and $ for precheck; confirmation → `lazy.yaml`.

Error resilience is part of the dialog: if the knowledge base smoke test fails, the agent doesn't crash with a traceback but offers options («can't reach Qdrant — check port? or switch to "folder of documents" mode?»); you can go back to any stage («let's change the task»). Each completed stage is persisted to disk — interrupted `lazy init` resumes from the stopping point.

Intelligence boundary: LLM dialog exists **only** at the setup stage, where there is uncertainty. Its sole output is the same `lazy.yaml` + `GUIDELINES.md`; after that, precheck and TUI run deterministically, without agency. Technically it's a tool-use loop on the official SDK (tool runner), not a framework.

### 4.2 `lazy check` — fact-check (PRECHECK)

For each example:
1. **Claims**: answer → list of atomic verifiable claims (1 call, structured output). Refusal answer («this is not in the documentation») is marked `is_refusal` and has no claims.
2. **Retrieve**: for each claim — search in knowledge base. Own query is broader than the evaluated RAG's: (a) original question, (b) claim rephrased as a query, results merged, top_k=8. This reduces inheriting blind spots of the evaluated retriever.
3. **Verify**: claim + found chunks → `supported/contradicted/not_found` + evidence citations (1 call per example — all claims batched in one prompt).
4. **Aggregate**: deterministic logic (not LLM) maps claim statuses to a verdict per the table in §3.2 + confidence.
5. **Escalate**: if confidence < threshold — re-review by Opus 4.8 (full context, fresh look), flag `escalated: true`.

Mechanics:
- **Batch API** (50% discount) — default mode: stage 1 on entire corpus → stage 3 on entire corpus. Sync mode — flag `--sync` for small datasets/debugging.
- **Prompt caching**: judge's system prompt + GUIDELINES.md — stable cacheable prefix, variable part (example) — after breakpoint.
- **Idempotency**: verdicts.jsonl is appended as ready; re-running `lazy check` skips already-checked ids (`--force` for recalculation).
- **Budget kill switch**: total cost is computed on the fly; on exceeding `max_budget_usd` — pause with question.
- Progress: rich progress bar, summary at end (how many p/f recommendations, average confidence, how many escalations, total cost).

### 4.3 `lazy review` — TUI review

Display order: **doubtful first** (sorted by confidence ascending), confident — at the end. Flag `--order random|confidence|original`.

Card (textual):

```
┌ myproject ── 42/480 ── p:31 f:8 s:3 ── agent agreement: 92% ─────────────────┐
│                                                                                │
│ QUESTION                                                                       │
│ What is the API rate limit?                                                    │
│                                                                                │
│ RAG RESPONSE                                                                   │
│ The limit is 1000 requests per hour; exceeding it returns 429.                 │
│                                                                                │
│ ─── AGENT: recommends [f]  ── confidence 0.62 ── (escalated) ──               │
│ First claim contradicts the knowledge base: docs say limit is 600/hour.        │
│  ✗ «limit 1000 requests per hour» — CONTRADICTS                               │
│    ▸ pricing.md: «Basic plan: 600 req/hour»                                    │
│  ✓ «exceeding returns 429» — CONFIRMED                                         │
│    ▸ rate-limits.md: «HTTP 429 on exceeding»                                  │
│                                                                                │
│ [p] positive  [f] negative  [s] skip  [u] undo  [n] note                       │
│ [c] RAG context  [g] guidelines  [h] hide verdict  [q] exit                    │
└────────────────────────────────────────────────────────────────────────────────┘
```

- `p`/`f`/`s` — decision + auto-advance to next. Skip is mandatory with a note (skip = signal of a hole in guidelines).
- `u` — undo (stack within session + event in log).
- `n` — note for the current example.
- `c` — expand the context used by the evaluated RAG (if present in the data).
- `h` — «blind annotation» mode: agent verdict hidden until decision is made (combat anchoring; also used for self-check).
- `q` — exit; resume on next launch automatically.
- **Self-check**: random 10% of already-labeled examples after N days are presented again blindly (`lazy review --self-check`) — agreement with oneself = proxy for intra-annotator agreement.

### 4.4 `lazy export` — output

- `out/goldset.jsonl` — final: example + agent verdict + human label + notes. Header record `_meta`: date, tool version, GUIDELINES.md hash, statistics, judge config — the dataset is self-described and reproducible.
- Formats: JSONL (always), CSV, HuggingFace `datasets` (`save_to_disk` / push to hub via flag).
- `out/report.md`: how many p/f/s; agent×human matrix and % agreement (overall and per confidence bucket — basis for future auto-labeling of confident examples); list of disagreements with notes; list of skips; cost; time per example.
- `lazy export --disagreements` — separate file with disagreements only (material for judge calibration).

## 5. Retriever Layer

### 5.1 Contract

```python
class Chunk(BaseModel):
    text: str
    source: str          # id/document name
    score: float | None = None

class Retriever(Protocol):
    def search(self, query: str, top_k: int) -> list[Chunk]: ...
    def healthcheck(self) -> str: ...   # human-readable «connected, ~N vectors in database»
```

One **contract test** runs against all adapters (mocked clients + optional integration via docker-compose for chroma/qdrant/pgvector/elastic/milvus/weaviate).

### 5.2 Adapters (all at once, extras dependencies)

| kind | dependency | query embedding | config |
|------|-----------|----------------|--------|
| `chroma` | `chromadb` | usually built into collection; otherwise ours | `path`/`host`, `collection` |
| `faiss` | `faiss-cpu` | **ours (required)** | `index_path`, `mapping_path` (id→text) |
| `qdrant` | `qdrant-client` | ours | `url`, `api_key?`, `collection` |
| `pgvector` | `psycopg` | ours | `dsn`, `table`, `text_col`, `vec_col` |
| `pinecone` | `pinecone` | ours | `api_key`, `index`, `namespace?` |
| `weaviate` | `weaviate-client` | often built-in (vectorizer); otherwise ours | `url`, `api_key?`, `collection` |
| `milvus` | `pymilvus` | ours | `uri`, `collection`, fields |
| `elastic` | `elasticsearch`/`opensearch-py` | ours for kNN; **BM25 doesn't need it** | `url`, `index`, `mode: knn\|bm25\|hybrid` |
| `lancedb` | `lancedb` | ours | `uri`, `table` |
| `docs_folder` | — (chroma under the hood) | ours | `path`, `glob`, chunker (default ~500 tok., overlap 50) |
| `chunks_file` | — | ours (in-memory) or BM25 | `path` (JSONL: `{text, source}`) |

`embeddings.py`: sentence-transformers (local, default for docs_folder), OpenAI, Voyage — per config; human specifies the model used to build their index. Elastic/bm25 and chunks_file+bm25 — path «no embeddings at all».

## 6. LLM Layer

- Models: judge `claude-haiku-4-5`, escalation `claude-opus-4-8` (both overridable in config).
- **Structured outputs**: `client.messages.parse()` with pydantic schemas (`ClaimsExtraction`, `ClaimVerification`) — valid JSON guaranteed, no parse retries needed.
- **Batch API** for bulk precheck (`client.messages.batches.*`), results matched by `custom_id = example_id`.
- **Prompt caching**: `cache_control` on judge's system prompt (includes GUIDELINES.md).
- Error handling: typed SDK exceptions, exponential retry on 429/5xx (SDK's own), `usage` tracking per response in cost counter.
- BYO-key: `ANTHROPIC_API_KEY` from environment; if absent — clear message on how to get a key.
- **BYO-provider** (added 2026-07-11): `llm.provider: anthropic | openai | openai_compatible`. All clients implement a single protocol `parse()/count_tokens()` — the judge doesn't know who's underneath. OpenAI: structured outputs via `chat.completions.parse`, automatic caching, default judge gpt-5.4-mini + escalation gpt-5.4. `openai_compatible` (Ollama/vLLM/LM Studio/Together/DeepSeek/OpenRouter): `base_url` + explicit `judge_model`, price from config (local $0), fallback for servers without strict structured outputs (schema in prompt + pydantic validation with retry), escalation disabled by default. Batch API implemented only for anthropic (rest — sync); non-anthropic estimate — character heuristic.
- No agent frameworks: judge is a deterministic pipeline of 2 LLM calls per example + pure functions.

## 7. Implementation Milestones

**M1 — core (working skeleton)** ✅ 2026-07-11: schemas, config, `chunks_file` + `docs_folder` retrievers (BM25), judge (claims→verify→aggregate, sync mode), TUI with p/f/s/u/resume/atomic write, export to JSONL. Full init→check→review→export path run on demo.

**M2 — all databases** ✅ 2026-07-11: 9 adapters (chroma/faiss/qdrant/pgvector/pinecone/weaviate/milvus/elastic/lancedb), embedding layer (sentence_transformers/openai/voyage), extras dependencies, unit tests for parsers, docker-compose. ⚠ not tested against live services — verify on first real connection.

**M3 — scale and cost** ✅ 2026-07-11: Batch API (three phases: claims → verification → escalation, 50% discount, default for ≥5 examples), prompt caching, estimate `lazy check --dry-run`, budget kill switch, idempotent re-check. ⚠ live Batch run not verified (no key in environment).

**M4 — annotation quality** ✅ 2026-07-11: dialog agent `lazy init --chat` (tool-use loop + stage state machine), self-check (`lazy review --self-check`, intra-agreement in report), blind mode, agreement per confidence buckets, `--pairs` (DPO templates), `--disagreements`, HF export, `lazy add` (append with dedup — weekly audit use case).

**M5 — polish** ✅ 2026-07-11: README, demo dataset in repo, 56 tests. Left for later: gif, PyPI publication.

Not verified live (needs ANTHROPIC_API_KEY): real judge/batch/wizard calls; adapters against real databases.

## 8. Risks and Solutions

| Risk | Solution |
|------|----------|
| Judge inherits user's retriever blind spots | Own broader search (question + claim rephrasings); docs_folder mode indexes itself |
| Anchoring bias | Citations instead of bare verdicts; blind mode `h`; % agreement in status bar; self-check |
| Wrong embedding model → garbage search | Mandatory question in wizard + smoke test showing real results to human |
| Cost spirals out of control | Estimate before run, live counter, `max_budget_usd`, Batch API + cache by default |
| Crash mid-work | Append-only JSONL, atomic write (write-tmp+rename), resume everywhere |
| Refusal answer labeled as error | Explicit `is_refusal` branch + «unanswerable refusal = correct» category |
| 9 database clients bloat install | extras: `pressf[all]` / `[qdrant]` / … ; base install is lightweight |
| Judge makes systematic errors | Disagreement report = dataset for calibrating judge prompts (self-improving loop) |
| Setup dialog degenerates into chatter / loops | Stage state machine with mandatory exits; turn limit per stage; progress persisted to disk |

## 9. Out of v1 Scope (deliberately)

- Multi-annotator mode and Cohen's kappa between humans (`annotator` field reserved in schema — enable later).
- Auto-labeling confident examples without a human (accumulate agreement stats first).
- Web interface. Terminal only.
- ~~Other LLM providers~~ → OpenAI added (see §6); others — on request, same protocol.
- Evaluating answer relevance/completeness — v1 measures only factual faithfulness (faithfulness + answerability).
