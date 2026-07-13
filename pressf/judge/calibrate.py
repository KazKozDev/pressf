"""Referee calibration assistant.

Problem: the report shows «the judge agrees with the person to N%» - that's all. Next
the person doesn’t know how to raise the number. This module closes the loop:
person/judge discrepancies → LLM offers clarification of guidelines + few-shot examples
from the discrepancies themselves → the person accepts → they are added to GUIDELINES.md and
automatically fall into the judge's system prompt at the next lazy check.

All work with LLM is done through the same parse() interface as the judge - in tests
replaced by a fake, a live key is not needed."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

CALIBRATION_MARKER = "<!-- pressf:calibration -->"


class FewShotExample(BaseModel):
    """An example precedent from a real discrepancy: how it should have been resolved and why."""

    question: str
    answer: str
    correct_label: str = Field(description="Correct label according to person: p | f | s")
    why: str = Field(description="A short explanation of why this is the rule for a judge")


class CalibrationProposal(BaseModel):
    """What LLM suggests adding to the guidelines, sorting out the discrepancies."""

    summary: str = Field(description="1-2 sentences: what the judge systematically gets wrong")
    clarifications: list[str] = Field(description="Specific clarifications of markup rules (2-5 points)")
    fewshot: list[FewShotExample] = Field(description="2-4 examples-precedents of discrepancies")


CALIBRATE_SYSTEM = """You are a marking methodologist. They give you cases where the AI judge went wrong
with a live human annotator when checking the bot’s answers. A person is right by definition
(this is the standard). Your task is to understand where the judge is systematically mistaken and to suggest
clarification of guidelines and precedent examples, so that next time the judge decides like a human being.

Rules:
- clarifications - specific rules («If the answer is rejected, but the answer is in the database - this is f»),
  not general words. 2-5 points.
- fewshot - 2-4 REAL examples from submitted discrepancies, with the correct person’s label
  and short «why». Take the most revealing ones.
- Write in the user's data language. Short and to the point."""


def build_calibrate_user(disagreements: list[dict]) -> str:
    """Collect a user prompt from discrepancy records (export_disagreements format)."""
    lines = ["Discrepancies judge/person (person - standard):", ""]
    for i, r in enumerate(disagreements, 1):
        lines.append(f"[{i}] Question: {r.get('question', '')}")
        lines.append(f"Bot response: {r.get('answer', '')}")
        lines.append(f"Judge: {r.get('agent_recommendation', '?')} "
                     f"({r.get('agent_category', '?')}, conf {r.get('agent_confidence', '?')})")
        lines.append(f"Judge reasoning: {r.get('agent_reasoning', '')}")
        lines.append(f"Human label: {r.get('label', '?')}"
                     + (f" (note: {r['note']})" if r.get("note") else ""))
        lines.append("")
    return "\n".join(lines)


def render_calibration_md(proposal: CalibrationProposal) -> str:
    """Markdown section for adding to GUIDELINES.md (idempotently marked with a marker)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = [
        "",
        CALIBRATION_MARKER,
        f"## Judge calibration ({ts})",
        "",
        f"_{proposal.summary}_",
        "",
        "### Rule clarifications",
    ]
    out += [f"- {c}" for c in proposal.clarifications]
    out += ["", "### Examples-precedents (human standard)"]
    for ex in proposal.fewshot:
        out.append(f"- **Question:**{ex.question}")
        out.append(f"**Bot response:**{ex.answer}")
        out.append(f"**Correct:** `{ex.correct_label}` — {ex.why}")
    out.append("")
    return "\n".join(out)


def propose_calibration(client, model: str, disagreements: list[dict]) -> tuple[CalibrationProposal, float]:
    """One LLM-call: discrepancies → sentence. Returns (proposal, value $)."""
    return client.parse(
        model=model,
        system=CALIBRATE_SYSTEM,
        user=build_calibrate_user(disagreements),
        schema=CalibrationProposal,
        max_tokens=2000,
    )


def append_calibration(guidelines_text: str, proposal: CalibrationProposal) -> str:
    """Add a calibration section to the text of the guidelines."""
    return guidelines_text.rstrip() + "\n" + render_calibration_md(proposal)
