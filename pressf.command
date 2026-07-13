#!/bin/zsh
# Double-click in Finder → Terminal → pressf setup agent.
# The agent inspects your project folder, figures out your scenario
# (label bot logs / calibrate the judge / start from scratch / continue),
# and walks you through it. All the smarts live in `lazy init --chat`.
# API keys are stored in .env next to this file.
set -e
cd "$(dirname "$0")"
export PATH="$PWD/.venv/bin:$PATH"

if [[ -f .env ]]; then set -a; source .env; set +a; fi

show_help() {
  cat <<'HELP'

──────────────────────── pressf — what is this? ────────────────────────
Lazy goldset annotation: the agent does the work, you press F.

An LLM judge fact-checks your RAG bot's answers against the knowledge
base (verdict + verbatim quotes); you review verdicts in a terminal UI
by pressing p (pass) / f (fail) / s (skip). Output: a human-verified
dataset plus a report on how much the judge agrees with you.

Pipeline:   init → check → review → export
            setup   judge   human TUI  goldset.jsonl + report.md

The setup agent handles four scenarios:
  1. You have bot logs (questions + answers)  → main path: label them.
  2. You have an already-labeled goldset      → calibrate the judge:
     import your labels, run the judge, see where it agrees with you.
  3. You have nothing but a bot and docs      → the agent explains the
     data format and what to bring (it cannot run your bot for you).
  4. The folder is an existing project        → it suggests the next step.

Project folder = where the project lives (lazy.yaml, data, verdicts).
  Type a new name (e.g. "mybot") to start fresh, or an existing one
  (e.g. "demo-openai" in this repo) to continue it.

Handy commands afterwards:
  lazy check <dir>                  judge the corpus (--dry-run = cost estimate)
  lazy review <dir>                 human review TUI (--blind, --self-check)
  lazy export <dir>                 goldset.jsonl + report (--pairs, --disagreements)
  lazy add <dir> --data new.jsonl   append fresh logs

Review keys: p pass · f fail · s skip · u undo · n note · c context ·
             g guidelines · h hide verdict · q quit
─────────────────────────────────────────────────────────────────────────

HELP
}

echo "=== pressf: lazy goldset annotation ==="
echo "Type ? for help."

while true; do
  read "dir?Project folder: "
  case "$dir" in
    "?"|help) show_help ;;
    "") echo "Please type a folder name (or ? for help)." ;;
    *) break ;;
  esac
done

# the setup agent itself runs on Claude — this key is always required
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
  read -s "value?Paste ANTHROPIC_API_KEY (console.anthropic.com), input hidden: "
  echo ""
  [[ -z "$value" ]] && { echo "No key, no ride."; exit 1; }
  export ANTHROPIC_API_KEY="$value"
  echo "ANTHROPIC_API_KEY=$value" >> .env
  chmod 600 .env
  echo "Saved to .env — won't ask again."
fi

lazy init "$dir" --chat
