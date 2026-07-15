<p align="center">
  <img src="docs/pressf-wordmark.png" alt="PressF" width="210">
</p>

<p align="center"><strong>Verify AI before it ships.</strong></p>

PressF is a Python CLI and macOS desktop workbench for evaluating RAG systems and LLM assistants. It checks answers against your documents, drafts evidence-backed verdicts, and leaves the final label to a human. The result is a human-verified goldset, not an unreviewed LLM score.

> **Beta** — PressF is under active development. Workflows and report formats may change; validate results before using them in production.

The design priority is simple: automate the repetitive investigation, not the decision. The judge finds relevant evidence, quotes it, and explains its verdict; the reviewer confirms, rejects, or skips it. Projects stay as ordinary files: `lazy.yaml`, JSONL examples, verdicts, annotations, and exported reports.

![PressF reviewing a document-backed finding](docs/pressf-demo.png)

## Quick start

Requires Python 3.11+ and an Anthropic API key for the default judge.

```bash
uv venv
uv pip install --python .venv/bin/python -e '.[dev]'
export ANTHROPIC_API_KEY=sk-ant-...

# Estimate first; this does not send a judge request.
.venv/bin/lazy check demo-project --dry-run

# Write verdicts, review them, then export a goldset and report.
.venv/bin/lazy check demo-project
.venv/bin/lazy review demo-project
.venv/bin/lazy export demo-project
```

The included demo uses `docs_folder` retrieval over [`demo/kb`](demo/kb) and eight mixed answers from [`demo/qa.jsonl`](demo/qa.jsonl). `check` is idempotent; `review` resumes from the first unanswered card.

## What PressF evaluates

- **Truth Check** — find answers that contradict or invent facts relative to the knowledge base.
- **Policy Check** — find answers that break a supplied rule or policy.
- **Search Quality** — judge the context returned by *your* retrieval system.
- **Compare Versions** — compare a baseline and new answer on the same question.
- **Agent Trajectory** — evaluate recorded tool use, execution order, safety, evidence grounding, and the final answer.

## Documentation

- [CLI projects, input formats, review, export, and regression gates](docs/cli.md)
- [Agent Trajectory: supported traces, setup, categories, and reports](docs/agent-trajectory.md)
- [Desktop app: run, test, build, and package](docs/desktop.md)
- [Retrievers and judge providers](docs/retrievers.md)
- [Desktop release and signing notes](app/RELEASE.md)
- [In-app help](app/DOCS.md)

## Test the repository

```bash
.venv/bin/python -m pytest
cd app && npm test
```

Python tests cover the CLI, ingest, judging, retrieval adapters, export, and scoring. The desktop suite covers its project-data layer, trace ingestion, scanner logic, strings, and shared statistics.

## License

[MIT](LICENSE)
