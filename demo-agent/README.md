# Agent trajectory demo

This self-contained project evaluates tool-using agent runs. Its traces cover clean paths, duplicate calls, fabricated outcomes, unsafe deletion, wrong arguments, tool-error handling, and a multi-tool path.

From the repository root, run:

```bash
# Make a fresh project from the same native trace file.
.venv/bin/lazy init /tmp/agent-audit --data demo-agent/traces.jsonl --task agent_trajectory --yes
.venv/bin/lazy add /tmp/agent-audit --data demo-agent/traces.jsonl
.venv/bin/lazy check /tmp/agent-audit --limit 5 --sync
.venv/bin/lazy review /tmp/agent-audit
.venv/bin/lazy export /tmp/agent-audit
.venv/bin/lazy gate /tmp/agent-audit --min-faithfulness 0.8
```

`check` requires a configured real judge (`ANTHROPIC_API_KEY` by default). The repository has mocked judge clients only in its automated test suite; there is no invented offline CLI mode. The checked-in [`lazy.yaml`](lazy.yaml) can also be used directly after copying `traces.jsonl` into its `data/` directory.
