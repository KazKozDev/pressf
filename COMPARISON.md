# How PressF compares

PressF is one of several tools for evaluating RAG systems and LLM assistants. This page
places it next to common alternatives so you can pick the right tool — or combine PressF
with one of them. The aim is a fair map, not a scoreboard.

> **Verification.** All competitor columns — RAGAS, DeepEval, TruLens, LangSmith,
> Braintrust, Arize Phoenix — were checked against each tool's official docs on
> **2026-07-16** (sources at the bottom). Evaluation tools evolve quickly; if a cell looks
> out of date, check the linked source and open a PR.
>
> `✓` = first-class support · `~` = partial, custom-code, or platform-tier · `✗` = not
> offered. Columns describe the typical product, not every edge case.

## Capability matrix

| Capability | RAGAS | DeepEval | TruLens | LangSmith | Braintrust | Arize Phoenix | PressF |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Faithfulness / groundedness / hallucination | ✓ | ✓ | ✓ | ~ | ~ | ✓ | ✓ |
| Deterministic IR ranking suite (P@k, recall@k, MRR, nDCG, hit-rate) from gold labels | ~ | ~ | ~ | ~ | ~ | ✓ | ✓ |
| LLM-judged context precision / recall / relevancy | ✓ | ✓ | ✓ | ~ | ~ | ✓ | ✓ |
| Policy / guardrail rubric compliance | ~ | ✓ | ~ | ~ | ~ | ~ | ✓ |
| Dedicated safety autoscores (toxicity / PII / jailbreak / bias) | ✗ | ✓ | ~ | ~ | ~ | ~ | ✗ |
| Pairwise / A-B preference | ✗ | ✓ | ~ | ✓ | ✓ | ~ | ✓ |
| Pairwise with statistical inference (win-rate + 95% CI + sign test + release call) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Agent / tool-trajectory evaluation | ~ | ✓ | ~ | ✓ | ~ | ✓ | ✓ |
| Human review / annotation workflow | ✗ | ~ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Blind review + human self-consistency ceiling | ✗ | ✗ | ✗ | ~ | ~ | ✗ | ✓ |
| Judge↔human agreement measurement | ✗ | ~ | ~ | ✓ | ✓ | ~ | ✓ |
| Judge calibration loop (human disagreements fed back into the judge) | ✗ | ~ | ✗ | ~ | ~ | ~ | ✓ |
| Human-verified goldset as the output artifact + provenance (labels, evidence, agreement, guidelines hash) | ✗ | ~ | ✗ | ~ | ✓ | ~ | ✓ |
| Online / production monitoring, tracing, drift, live guardrails | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Multi-turn / conversational eval | ~ | ✓ | ~ | ✓ | ✓ | ✓ | ~ |
| Local files, no vendor lock-in, self-hostable | ✓ | ✓ | ✓ | ✗ | ✗ | ~ | ✓ |
| Answer relevancy / correctness-to-reference as a distinct metric | ✓ | ✓ | ✓ | ~ | ~ | ~ | ~ |

## Notes by tool

- **RAGAS** — the widely adopted open-source RAG metric library (~15 metrics), including
  agentic ones (Tool Call Accuracy/F1, Agent Goal Accuracy) and multi-turn. Its context
  precision/recall are rank-aware but LLM-based, not the classic deterministic MRR/nDCG
  suite. No human-review workflow or pairwise.
- **DeepEval** — 50+ metrics, first-class blinded pairwise (Arena G-Eval), a full agentic
  suite (plan/tool/task/step), and dedicated safety metrics (toxicity, bias, PII, misuse,
  role violation). Human review comes via its Confident AI platform.
- **TruLens** — the RAG Triad (context relevance, groundedness, answer relevance) plus
  toxicity/bias feedback functions and agent tracing; open-source and self-hostable.
- **LangSmith** — tracing + evaluation platform with pairwise annotation queues, human
  annotation, online production evals, agent-trajectory evaluation, and human-correction
  calibration of judges. Hosted.
- **Braintrust** — eval-first observability with pairwise scoring, human review over
  golden datasets, online scoring on production traces, and rubric refinement from
  reviewed findings. Hosted.
- **Arize Phoenix** — observability with 50+ built-in evals, documented retrieval ranking
  metrics (nDCG, Precision@K), agent/tool tracing, human labels, and online evals; the
  closest match to PressF on deterministic retrieval numbers.

## What's distinctive about PressF

1. **Statistically honest pairwise.** Compare Versions returns a win rate, a 95% interval,
   an exact sign test, and a release recommendation out of the box. Other tools do
   pairwise, but ship the winner without the significance layer needed for a defensible
   release call.
2. **The human is the standard, and its ceiling is measured.** Blind, resumable review,
   plus a self-consistency check (`--self-check`) that quantifies how often a human agrees
   with their own earlier labels — the upper bound any judge can reach.
3. **Offline, in plain files.** The output is a human-verified goldset — labels, evidence,
   confidence, reviewer agreement, and a hash of the guidelines used — as ordinary
   JSONL/YAML, with no hosted service.

Individually, calibration, pairwise, agent eval, and human review each exist somewhere.
PressF's position is the combination: offline, local-files, human-as-the-standard, with
judge calibration and statistically honest A-B.

## When another tool fits better

- **Live production monitoring** (tracing, drift, real-time guardrails): TruLens,
  LangSmith, Braintrust, or Arize. PressF is an offline goldset + review tool.
- **Turnkey safety classifiers** (toxicity / PII / jailbreak / bias as separate scores):
  DeepEval or an observability platform. PressF folds safety into rubric-based Policy Check.
- **A large prebuilt metric catalog:** RAGAS (~15) or DeepEval (50+). PressF ships a
  focused set of six evaluation types.
- **First-class multi-turn or answer-relevancy-to-reference metrics:** available in several
  tools; only partial in PressF today.

Many teams pair PressF with an observability platform: the platform watches production,
PressF builds the trustworthy goldset those judges are measured against.

## In one line

PressF turns an unreliable LLM-judge into a trustworthy, human-verified goldset — with a
calibration loop, statistically honest A-B, and a review workflow that keeps the human as
the standard, all as local files.

## Sources (verified 2026-07-16)

- RAGAS — available metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- DeepEval — metrics intro: https://deepeval.com/docs/metrics-introduction
- DeepEval — Arena G-Eval (pairwise): https://deepeval.com/docs/metrics-arena-g-eval
- DeepEval — AI agent evaluation metrics: https://deepeval.com/guides/guides-ai-agent-evaluation-metrics
- TruLens — RAG Triad: https://www.trulens.org/getting_started/core_concepts/rag_triad/
- LangSmith — evaluation concepts: https://docs.langchain.com/langsmith/evaluation-concepts
- LangSmith — calibrating LLM-as-judge with human corrections: https://www.langchain.com/resources/llm-as-a-judge
- Braintrust — evaluate: https://www.braintrust.dev/docs/evaluate
- Braintrust — human review & golden datasets: https://www.braintrust.dev/blog/human-review-golden-datasets
- Arize Phoenix — evaluate RAG (nDCG, Precision@K): https://phoenix.arize.com/evaluate-rag-with-llm-evals-and-benchmarking/
- Arize Phoenix — LLM evals: https://arize.com/docs/phoenix/evaluation/llm-evals
