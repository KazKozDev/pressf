"""Connectors to the bot and a regression loop (lazy run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from pressf.bot import build_bot
from pressf.bot.base import BotError, extract_answer
from pressf.config import BotConfig


# ── extract_answer ────────────────────────────────────────────────────────

def test_extract_plain_answer_trims():
    assert extract_answer("  hello  ", None) == "hello"


def test_extract_json_dotted_path():
    payload = json.dumps({"choices": [{"message": {"content": "the answer"}}]})
    assert extract_answer(payload, "choices.0.message.content") == "the answer"


def test_extract_bad_path_raises():
    with pytest.raises(BotError):
        extract_answer(json.dumps({"a": 1}), "a.b.c")
    with pytest.raises(BotError):
        extract_answer("not json", "a")


# ── command bot ───────────────────────────────────────────────────────────

def test_command_bot_placeholder():
    bot = build_bot(BotConfig(kind="command", command="printf %s {question}"))
    assert bot.ask("hi there") == "hi there"


def test_command_bot_stdin():
    bot = build_bot(BotConfig(kind="command", command="cat"))
    assert bot.ask("via stdin") == "via stdin"


def test_command_bot_json_answer_path(tmp_path: Path):
    script = tmp_path / "bot.py"
    script.write_text(
        "import sys, json\n"
        "q = sys.stdin.read().strip()\n"
        "print(json.dumps({'reply': {'text': 'echo:' + q}}))\n",
        encoding="utf-8",
    )
    bot = build_bot(BotConfig(kind="command", command=f"{sys.executable} {script}", answer_path="reply.text"))
    assert bot.ask("ping") == "echo:ping"


def test_command_bot_nonzero_exit_raises():
    bot = build_bot(BotConfig(kind="command", command="false"))
    with pytest.raises(BotError):
        bot.ask("x")


def test_command_bot_missing_binary_raises():
    bot = build_bot(BotConfig(kind="command", command="definitely-not-a-real-binary-xyz {question}"))
    with pytest.raises(BotError):
        bot.ask("x")


def test_unknown_kind_raises():
    with pytest.raises(BotError):
        build_bot(BotConfig(kind="carrier-pigeon"))


def test_bot_config_rejects_unknown_connector_fields():
    with pytest.raises(ValidationError, match="unknown"):
        BotConfig(kind="command", command="cat", unknown="value")


#── lazy run (regression loop) ──────────────────── ────────────────────

def test_run_collects_fresh_answers(tmp_path: Path):
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import read_jsonl, write_jsonl_atomic
    from pressf.schemas import Example

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "doc.md").write_text("Limit 600.", encoding="utf-8")
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    write_jsonl_atomic(project.examples_path, [
        Example(id="q1", question="First question?", answer="old answer 1"),
        Example(id="q2", question="Second question?", answer="old answer 2"),
    ])

    #«bot» - echo script, responds in a new way
    bot_script = tmp_path / "newbot.py"
    bot_script.write_text(
        "import sys\nq = sys.stdin.read().strip()\nprint('NEW response to: ' + q)\n",
        encoding="utf-8",
    )

    from typer.testing import CliRunner

    from pressf.cli import app

    out = project.data_dir / "fresh.jsonl"
    result = CliRunner().invoke(app, [
        "run", str(root), "--command", f"{sys.executable} {bot_script}", "--out", str(out),
    ])
    assert result.exit_code == 0, result.output

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [r["id"] for r in rows] == ["q1", "q2"]
    assert all(r["answer"].startswith("NEW response to:") for r in rows)
    #the original goldset is not touched
    assert read_jsonl(project.examples_path, Example)[0].answer == "old answer 1"


def test_run_without_bot_config_errors(tmp_path: Path):
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import write_jsonl_atomic
    from pressf.schemas import Example
    from typer.testing import CliRunner

    from pressf.cli import app

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "d.md").write_text("x", encoding="utf-8")
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    write_jsonl_atomic(project.examples_path, [Example(id="q1", question="?", answer="a")])

    result = CliRunner().invoke(app, ["run", str(root)])
    assert result.exit_code == 1
    assert "Bot not specified" in result.output
