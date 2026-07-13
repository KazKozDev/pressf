# Contributing to PressF

Thanks for improving PressF. Keep changes small, evidence-based, and compatible with both the CLI and desktop app.

## Local setup

```bash
uv venv
uv pip install --python .venv/bin/python -e '.[dev]'

cd app
npm ci
```

Run the checks before opening a pull request:

```bash
# Repository root
.venv/bin/python -m pytest

# Desktop app
cd app
npm test
npm run build
```

## Project conventions

- Keep project data portable: examples, verdicts, and annotations remain plain JSONL plus `lazy.yaml`.
- Keep desktop behavior aligned with the CLI. Reuse CLI helpers rather than duplicating judging, ingest, or export logic in Electron.
- Add or update tests for a behavior change. Python tests live in `tests/`; desktop tests live under `app/src/` and end in `.test.ts`.
- Do not commit API keys, generated desktop builds, virtual environments, or local evaluation data.

## Pull requests

Explain the user-visible behavior change, include the tests you ran, and call out any migration or compatibility concern. Screenshots are useful for visible desktop changes.
