#!/bin/zsh
# Training wheels: double-click → straight to the review cards, no questions asked.
set -e
cd "$(dirname "$0")"
export PATH="$PWD/.venv/bin:$PATH"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
lazy review demo-openai
