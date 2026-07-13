"""Judge calibration assistant: analysis of discrepancies → clarification of guidelines + few-shot."""

from __future__ import annotations

import json
from pathlib import Path

from pressf.judge.calibrate import (
    CALIBRATION_MARKER,
    CalibrationProposal,
    FewShotExample,
    append_calibration,
    build_calibrate_user,
    propose_calibration,
    render_calibration_md,
)


DISAGREEMENTS = [
    {
        "question": "How to revoke API-key?",
        "answer": "Sorry, I can't help.",
        "agent_recommendation": "p",
        "agent_category": "correct_refusal",
        "agent_confidence": 0.9,
        "agent_reasoning": "The refusal seems correct.",
        "label": "f",
        "note": "The answer is in auth.md",
    },
]


class FakeClient:
    """Same parse() interface as LLMClient - no live key needed."""

    def __init__(self, proposal: CalibrationProposal):
        self._proposal = proposal
        self.calls: list[dict] = []

    def parse(self, *, model, system, user, schema, max_tokens=2000):
        self.calls.append({"model": model, "system": system, "user": user})
        assert schema is CalibrationProposal
        return self._proposal, 0.0021


def _proposal() -> CalibrationProposal:
    return CalibrationProposal(
        summary="The judge counts false refusals as correct.",
        clarifications=["If the answer is in the database, but the bot refuses, this is f (false refusal)."],
        fewshot=[FewShotExample(
            question="How to revoke API-key?", answer="Sorry, I can't help.",
            correct_label="f", why="The answer is in auth.md, which means the refusal is false.",
        )],
    )


def test_build_user_includes_human_verdict_and_note():
    text = build_calibrate_user(DISAGREEMENTS)
    assert "Human label: f" in text
    assert "auth.md" in text
    assert "correct_refusal" in text


def test_propose_calibration_uses_parse_interface():
    client = FakeClient(_proposal())
    proposal, cost = propose_calibration(client, "claude-haiku-4-5", DISAGREEMENTS)
    assert cost == 0.0021
    assert client.calls[0]["model"] == "claude-haiku-4-5"
    assert "false" in proposal.summary.lower() or proposal.clarifications


def test_render_markdown_is_marked_and_complete():
    md = render_calibration_md(_proposal())
    assert CALIBRATION_MARKER in md
    assert "### Rule clarifications" in md
    assert "false refusal" in md
    assert "`f`" in md


def test_append_preserves_existing_guidelines():
    original = "# Guidelines\n\n## Tags\n- p / f / s\n"
    updated = append_calibration(original, _proposal())
    assert updated.startswith("# Guidelines")
    assert CALIBRATION_MARKER in updated
    assert updated.count("## Tags") == 1


def test_fewshot_reaches_judge_system_prompt_via_guidelines():
    """Key: after calibration, few-shot actually gets into the judge’s system prompt,
    because the judge’s prompt embeds the entire text of the guidelines."""
    from pressf.llm.prompts import judge_system

    guidelines = append_calibration("# Guidelines", _proposal())
    system = judge_system(guidelines)
    assert "false refusal" in system
    assert "How to revoke API-key?" in system


def test_calibrate_cli_end_to_end(tmp_path: Path, monkeypatch):
    """lazy calibrate: discrepancies → proposal (fake LLM) → added to GUIDELINES.md."""
    from typer.testing import CliRunner

    import pressf.cli as cli
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.schemas import Annotation, ClaimVerdict, Example, Verdict

    root = tmp_path / "proj"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "auth.md").write_text("The key is revoked in the Security section.", encoding="utf-8")
    project.save_config(ProjectConfig(
        project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)),
        ingest=IngestConfig(), llm=LLMConfig(),
    ))
    project.guidelines_path.write_text("# Guidelines\n\n## Tags\n- p / f / s\n", encoding="utf-8")

    ex = Example(id="q1", question="How to revoke API-key?", answer="Sorry, I can't help.")
    write_jsonl_atomic(project.examples_path, [ex])
    append_jsonl(project.verdicts_path, Verdict(
        example_id="q1", claims=[ClaimVerdict(text="refusal", status="not_found", evidence=[])],
        answerable=True, recommendation="p", category="correct_refusal", confidence=0.9,
        reasoning="Failure ok.", judge_model="fake",
    ))
    #person disagrees → agreed_with_agent=False
    append_jsonl(project.annotations_path, Annotation(
        example_id="q1", label="f", agreed_with_agent=False, note="The answer is in auth.md",
    ))

    #replace the LLM-client construction with a fake one
    monkeypatch.setattr(cli, "_load_project", lambda d: project)
    import pressf.llm as llm_mod
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda cfg: FakeClient(_proposal()))

    result = CliRunner().invoke(cli.app, ["calibrate", str(root), "--yes"])
    assert result.exit_code == 0, result.output

    guidelines = project.guidelines_path.read_text(encoding="utf-8")
    assert CALIBRATION_MARKER in guidelines
    assert "false refusal" in guidelines
    assert guidelines.count("## Tags") == 1  #the old guidelines are not lost


def test_calibrate_dry_run_returns_json_without_writing(tmp_path: Path, monkeypatch):
    """The desktop app can preview a proposal without modifying GUIDELINES.md."""
    from typer.testing import CliRunner

    import pressf.cli as cli
    from pressf.config import IngestConfig, LLMConfig, Project, ProjectConfig, RetrieverConfig
    from pressf.io import append_jsonl, write_jsonl_atomic
    from pressf.schemas import Annotation, ClaimVerdict, Example, Verdict

    root = tmp_path / "preview"
    project = Project(root)
    kb = tmp_path / "kb"
    kb.mkdir()
    project.save_config(ProjectConfig(project="p", retriever=RetrieverConfig(kind="docs_folder", path=str(kb)), ingest=IngestConfig(), llm=LLMConfig()))
    original = "# Guidelines\n"
    project.guidelines_path.write_text(original, encoding="utf-8")
    ex = Example(id="q1", question="Q?", answer="A")
    write_jsonl_atomic(project.examples_path, [ex])
    append_jsonl(project.verdicts_path, Verdict(example_id="q1", answerable=True, recommendation="p", category="correct", confidence=0.9, reasoning="ok", judge_model="fake"))
    append_jsonl(project.annotations_path, Annotation(example_id="q1", label="f", agreed_with_agent=False))

    monkeypatch.setattr(cli, "_load_project", lambda d: project)
    import pressf.llm as llm_mod
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda cfg: FakeClient(_proposal()))

    result = CliRunner().invoke(cli.app, ["calibrate", str(root), "--dry-run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["proposal"]["summary"] == _proposal().summary
    assert CALIBRATION_MARKER in payload["markdown"]
    assert project.guidelines_path.read_text(encoding="utf-8") == original
    assert not project.out_dir.exists()
