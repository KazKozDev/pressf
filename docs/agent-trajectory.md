# Agent Trajectory

Agent Trajectory evaluates the execution path rather than judging only the final answer. It detects fabricated or ignored tool results, wrong arguments, unnecessary duplicate calls and loops, unsafe actions, and final claims that are unsupported by the trace.

The verdict categories are `trajectory_ok`, `trajectory_inefficient`, `trajectory_unfaithful`, `trajectory_unsafe`, and `trajectory_wrong_answer`.

A correct-but-wasteful run (`trajectory_inefficient`) passes the gate by default, so extra tool calls do not fail a run that still reached the right answer. To treat inefficiency as a failure, set `llm.trajectory_fail_on_inefficient: true` in `lazy.yaml`.

## Supported traces

Input can be native PressF trajectories, LangSmith runs (including nested `child_runs`), Langfuse observations (`SPAN`, `GENERATION`, `TOOL`), or OpenAI Chat Completions message logs. A native JSONL record looks like this:

```json
{"id":"deploy-1","question":"What is the deployment status?","answer":"It completed successfully.","trajectory":[{"kind":"tool_call","content":null,"tool":{"name":"get_deployment","arguments":{"deployment_id":"dep-123"},"result":"status=completed"}},{"kind":"answer","content":"It completed successfully.","tool":null}]}
```

## Create and run

Create a project without a retriever, then use the normal workflow:

```bash
.venv/bin/lazy init agent-audit --data ./traces.jsonl --task agent_trajectory --yes
.venv/bin/lazy add agent-audit --data ./fresh-traces.jsonl
.venv/bin/lazy check agent-audit --limit 5 --sync
.venv/bin/lazy review agent-audit
.venv/bin/lazy calibrate agent-audit
.venv/bin/lazy export agent-audit
.venv/bin/lazy gate agent-audit --min-faithfulness 0.85
```

The generated `lazy.yaml` has no retriever requirement for this mode:

```yaml
project: agent-audit
task: agent_trajectory
ingest:
  question: question
  answer: answer
  trajectory: trajectory
```

The review TUI shows every recorded step and its corresponding judge finding. The report adds trajectory category and issue-kind breakdowns, average step length, and concise offending-step details. See [`demo-agent`](../demo-agent) for a self-contained dataset and guideline template.
