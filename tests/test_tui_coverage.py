"""Exercise the Textual review surface in its real headless test harness."""

from __future__ import annotations

import asyncio

from textual.widgets import Input, Static

from pressf.config import Project
from pressf.review import ReviewSession
from pressf.review.tui import ReviewApp
from pressf.schemas import ClaimVerdict, ContextChunk, Evidence, Example, ToolCall, TrajectoryStep, TrajectoryStepVerdict, Verdict


def test_review_app_renders_cards_and_keyboard_actions(project: Project):
    async def exercise() -> None:
        session = ReviewSession(project)
        app = ReviewApp(session)
        async with app.run_test() as pilot:
            assert "QUESTION" in str(app.query_one("#question", Static).render())
            await pilot.press("c")
            await pilot.press("h")
            assert app.blind is True
            await pilot.press("n")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.press("n")
            await pilot.pause()
            app.screen.query_one(Input).value = "useful note"
            await pilot.press("enter")
            await pilot.press("p")
            assert session.stats().done == 1
            await pilot.press("u")
            assert session.stats().done == 0
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("enter")
            app.screen.query_one(Input).value = "reason"
            await pilot.press("enter")
            assert session.stats().s == 1
            await pilot.press("g")
            await pilot.pause()
            await pilot.press("g")
            await pilot.press("p", "p", "p", "s", "n")

    asyncio.run(exercise())


def test_review_renderers_show_evidence_and_trajectory_details(project: Project):
    app = ReviewApp(ReviewSession(project))
    example = Example(
        id="trace",
        question="What happened?",
        answer="Done",
        trajectory=[
            TrajectoryStep(
                kind="tool_call", index=1,
                tool=ToolCall(name="search", arguments={"q": "docs"}, result="a useful result", error="warning"),
            ),
            TrajectoryStep(kind="answer", index=2, content="Done"),
        ],
    )
    verdict = Verdict(
        example_id="trace", answerable=True, recommendation="f", category="trajectory_unfaithful",
        confidence=0.5, reasoning="bad evidence", judge_model="judge", escalated=True,
        claims=[ClaimVerdict(text="claim", status="contradicted", evidence=[Evidence(text="proof", source="docs")])],
        step_issues=[TrajectoryStepVerdict(step_index=1, ok=False, issue="wrong query", issue_kind="wrong_arguments")],
    )
    assert "CONTRADICTS" in app._render_verdict(example, verdict)
    rendered = app._render_trajectory(example, verdict)
    assert "TOOL CALL" in rendered and "wrong query" in rendered and "warning" in rendered
    assert "no agent verdict" in app._render_verdict(example, None)


def test_review_app_renders_and_toggles_logged_context(project: Project):
    example = Example(id="context", question="Q", answer="A", context=[ContextChunk(text="proof", source="docs")])
    session = type(
        "Session",
        (),
        {
            "project": project,
            "current": lambda self: (example, None),
            "stats": lambda self: type("Stats", (), {"done": 0, "total": 1, "p": 0, "f": 0, "s": 0, "agreement": None})(),
        },
    )()

    async def exercise() -> None:
        app = ReviewApp(session)
        async with app.run_test() as pilot:
            await pilot.press("c")
            assert app.query_one("#context-panel", Static).display is True

    asyncio.run(exercise())
