"""Exercise CLI-only branches that do not need a live model or terminal TUI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

import pressf.cli as cli
from pressf.config import Project
from pressf.config import IngestConfig
from pressf.bot import BotError
from pressf.review import ReviewSession


def test_load_project_and_next_step_branches(monkeypatch, tmp_path: Path):
    with pytest.raises(typer.Exit):
        cli._load_project(tmp_path / "missing")

    project_root = tmp_path / "project"
    project_root.mkdir()
    examples = project_root / "examples.jsonl"
    examples.write_text("{}\n", encoding="utf-8")
    base = dict(
        root=project_root,
        exists=lambda: True,
        examples_path=examples,
        verdicts_path=project_root / "verdicts.jsonl",
        annotations_path=project_root / "annotations.jsonl",
        load_verdicts=lambda: {},
        effective_annotations=lambda: {},
    )
    project = SimpleNamespace(**base)
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(cli, "check", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no key")))
    cli._offer_next(project)

    called = {}
    project.verdicts_path.write_text("present", encoding="utf-8")
    project.load_verdicts = lambda: {"e1": object()}
    monkeypatch.setattr(cli, "review", lambda **kwargs: called.update(kwargs))
    cli._offer_next(project)
    assert called["dir"] == project_root

    project.effective_annotations = lambda: {"e1": object()}
    cli._offer_next(project)


def test_print_summary_and_commands_without_a_live_judge(project: Project, monkeypatch, tmp_path: Path):
    metrics = SimpleNamespace(
        k=[1], precision_at_k={1: 1.0}, recall_at_k={1: 0.5}, ndcg_at_k={1: 0.75},
        hit_at_k={1: 1.0}, examples=2, mrr=0.75, map=0.5,
    )
    cli._print_check_summary(
        SimpleNamespace(
            checked=2, skipped_existing=1, recommendations={"p": 2}, escalated=1,
            cost_usd=0.12, budget_stop=True, retrieval_metrics=metrics,
        )
    )

    monkeypatch.setattr("pressf.llm.build_llm_client", lambda cfg: SimpleNamespace(count_tokens=lambda **kwargs: 12))
    cli.check(dir=project.root, force=True, limit=1, sync=False, dry_run=True, k="1,3", task=None, sample=None, seed=0)
    with pytest.raises(typer.Exit):
        cli.check(dir=project.root, force=True, limit=None, sync=False, dry_run=False, k="bad", task=None, sample=None, seed=0)
    cli.check(dir=project.root, force=False, limit=None, sync=False, dry_run=False, k=None, task=None, sample=None, seed=0)

    session = ReviewSession(project)
    while session.current_id() is not None:
        current = session.current()
        session.decide(current[1].recommendation if current and current[1] else "p")
    cli.review(dir=project.root, order="confidence", annotator="", blind=False, self_check=False, fraction=0.1)

    class SelfCheck:
        def __init__(self, project, fraction, annotator):
            self.project = project
            self.queue = ["e1"]

        def stats(self):
            return SimpleNamespace(done=1, total=1, p=1, f=0, s=0, agreement=1.0)

    started = {}
    monkeypatch.setattr("pressf.review.SelfCheckSession", SelfCheck)
    monkeypatch.setattr("pressf.review.tui.ReviewApp", lambda session, blind: SimpleNamespace(run=lambda: started.update(blind=blind)))
    cli.review(dir=project.root, order="confidence", annotator="tester", blind=False, self_check=True, fraction=0.5)
    assert started["blind"] is True

    cli.export(dir=project.root, formats="jsonl,csv", pairs=True, disagreements=True)
    with pytest.raises(typer.Exit):
        cli.calibrate(dir=project.root, yes=False, dry_run=False)

    with pytest.raises(typer.Exit):
        cli.run(dir=project.root, out=None, bot_kind=None, command=None, url=None, answer_path=None, limit=None)

    class Bot:
        calls = 0

        def ask(self, question):
            self.calls += 1
            if self.calls == 2:
                raise BotError("temporary failure")
            return "fresh answer"

    monkeypatch.setattr("pressf.bot.build_bot", lambda cfg: Bot())
    out = tmp_path / "answers.jsonl"
    cli.run(
        dir=project.root, out=out, bot_kind="command", command="ignored", url=None,
        answer_path=None, limit=2,
    )
    assert out.exists() and "fresh answer" in out.read_text(encoding="utf-8")

    with pytest.raises(typer.Exit):
        cli.add(dir=project.root, data=out)
    cfg = project.load_config()
    cfg.ingest = IngestConfig()
    project.save_config(cfg)
    cli.add(dir=project.root, data=out)


def test_init_chat_without_a_key_and_with_a_completed_fake_wizard(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(typer.Exit):
        cli.init(dir=tmp_path / "no-key", chat=True)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("pressf.wizard.run_wizard", lambda root, console: True)
    with pytest.raises(typer.Exit) as done:
        cli.init(dir=tmp_path / "with-key", chat=True)
    assert done.value.exit_code == 0
