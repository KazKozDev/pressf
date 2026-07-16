# CLI projects, inputs, and review

## Create a project

`init` creates the project, validates the input, writes `GUIDELINES.md`, health-checks the retriever, and saves the configuration.

```bash
.venv/bin/lazy init support-audit \
  --data ./answers.jsonl \
  --question-col question \
  --answer-col answer \
  --retriever docs_folder \
  --kb ./docs
```

Interactive setup is the default. For a guided setup that inspects the local project and asks about the use case, run:

```bash
.venv/bin/lazy init support-audit --chat
```

`--chat` requires `ANTHROPIC_API_KEY`. For scripts, provide all required flags and add `--yes` to skip prompts.

Input can be JSONL, CSV, TSV, or XLSX (`pressf[xlsx]` installs the Excel reader). PressF stores the selected column mapping in `lazy.yaml`, so incremental imports use the same schema. Both `lazy` and `pressf` invoke the same CLI.

## Search Quality input

Search Quality measures retrieval, not PressF's BM25 fallback. Include the retrieved chunks from the system being evaluated and map that column at project creation:

```bash
.venv/bin/lazy init search-audit \
  --data ./traces.jsonl \
  --question-col question \
  --answer-col answer \
  --context-col retrieved_context \
  --relevant-col relevant_ids \
  --retriever docs_folder \
  --kb ./docs \
  --yes

.venv/bin/lazy check search-audit --task retrieval_quality --k 1,3,5,10
```

The context cell can be plain text, a JSON array of strings, or a JSON array of `{ "text", "source", "id" }` chunks. A missing context is an error, because otherwise the result would describe PressF's search rather than yours.

For reproducible IR metrics, map a JSON-array `relevant_ids` column. Its values are matched to the logged chunks' `source` or `id`; repeated chunks from the same gold document count once for Recall and MAP. Precision@k always divides by the requested `k`, including when fewer chunks were returned. The report includes Precision@k, Recall@k, nDCG@k, Hit@k, MRR, and MAP. When gold IDs are absent, one additional judge request grades every chunk 0–2; metrics are written only if every ordered chunk receives exactly one grade. The default cutoffs are `1,3,5,10`, or choose another set with `lazy check search-audit --k 1,5,20`.

## Policy Check

Use the same project structure, point the retriever at the policy documents, then select the task for the check:

```bash
.venv/bin/lazy check support-audit --task policy_compliance
```

The policy judge returns either compliance, a violation with the offending sentence and quoted rule, or an unclear-policy result.

## Review, calibrate, and export

```bash
# Cheap smoke run before a large corpus.
.venv/bin/lazy check support-audit --limit 5 --sync

# Review low-confidence or decision-boundary examples first.
.venv/bin/lazy review support-audit --order informative --annotator alice

# Re-show a sample without the judge verdict to measure self-consistency.
.venv/bin/lazy review support-audit --self-check

# Inspect human/judge disagreements, then propose a GUIDELINES.md update.
.venv/bin/lazy calibrate support-audit

# Export JSONL by default; CSV and Hugging Face Dataset are optional formats.
.venv/bin/lazy export support-audit --formats jsonl,csv,hf
```

`calibrate` never silently edits the project: it proposes a marked section for `GUIDELINES.md`, shows it, and asks before writing it. Re-run `check --force` after accepting a proposal to measure the change.

For multiple reviewers, pass `--annotator`. The report calculates pairwise Cohen's kappa when reviewers labeled overlapping examples.

## Regression gate

Use a reviewed goldset to block a regression in CI. The gate uses human labels when present and falls back to judge verdicts only when no human labels exist.

```bash
.venv/bin/lazy gate support-audit --min-faithfulness 0.85
```

Exit code `0` means the threshold passed, `1` means it failed, and `2` means there is nothing to score. A small GitHub Actions step looks like this:

```yaml
- run: |
    .venv/bin/lazy check support-audit --sample 200 --seed 0
    .venv/bin/lazy gate support-audit --min-faithfulness 0.85
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

`--sample` is deterministic for a given seed. Use a small limit or sample first before paying for a full judge run.

## Useful commands

```bash
lazy check PROJECT --dry-run              # estimate cost without judging
lazy check PROJECT --force                # rejudge existing verdicts
lazy check PROJECT --sample 200 --seed 0  # deterministic sample
lazy add PROJECT --data fresh.jsonl       # append deduplicated examples
lazy run PROJECT --command "python bot.py {question}"
lazy export PROJECT --pairs               # pairwise/DPO-oriented export
lazy export PROJECT --disagreements       # only human/judge disagreements
```

`lazy run` invokes the system under test through a command or HTTP configuration and writes fresh `{id, question, answer}` rows. It is the bridge between a stable goldset and a changed bot version.
