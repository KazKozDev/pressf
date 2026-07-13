"""TUI-review on textual: question/answer/verdict card, one-button solutions."""

from __future__ import annotations

import time

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from ..schemas import Example, Verdict
from .session import ReviewSession, SelfCheckSession

_STATUS_MARK = {"supported": "[green]✓[/green]", "contradicted": "[red]✗[/red]", "not_found": "[yellow]?[/yellow]"}
_STATUS_WORD = {"supported": "CONFIRMED", "contradicted": "CONTRADICTS", "not_found": "NOT FOUND"}


class NoteScreen(ModalScreen[str | None]):
    """Modal for entering notes. Returns text or None (cancel with Esc)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str, required: bool = False):
        super().__init__()
        self._prompt = prompt
        self._required = required

    def compose(self) -> ComposeResult:
        yield Label(self._prompt, id="note-prompt")
        yield Input(placeholder="note text...", id="note-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if self._required and not text:
            self.query_one("#note-prompt", Label).update(
                f"{self._prompt}[red](note required)[/red]"
            )
            return
        self.dismiss(text or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GuidelinesScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("g", "close", "Close")]

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="guidelines-scroll"):
            yield Static(escape(self._text or "GUIDELINES.md is empty"), id="guidelines-text")

    def action_close(self) -> None:
        self.dismiss(None)


class ReviewApp(App[None]):
    TITLE = "pressf"

    CSS = """
    #status { dock: top; height: 1; background: $primary-darken-2; color: $text; padding: 0 1; }
    #footer { dock: bottom; height: 1; background: $primary-darken-2; color: $text; padding: 0 1; }
    #card { padding: 1 2; }
    .section-title { color: $text-muted; margin-top: 1; }
    #verdict-panel { border: round $secondary; padding: 0 1; margin-top: 1; }
    #context-panel { border: round $surface-lighten-2; padding: 0 1; margin-top: 1; }
    NoteScreen { align: center middle; }
    #note-prompt { margin: 1 2 0 2; }
    #note-input { margin: 0 2 1 2; width: 80; }
    GuidelinesScreen { align: center middle; }
    #guidelines-scroll { width: 90%; height: 80%; border: round $secondary; background: $surface; padding: 1 2; }
    """

    BINDINGS = [
        Binding("p", "decide('p')", "positive"),
        Binding("f", "decide('f')", "negative"),
        Binding("s", "skip", "skip"),
        Binding("u", "undo", "undo"),
        Binding("n", "note", "note"),
        Binding("c", "toggle_context", "context"),
        Binding("g", "guidelines", "guidelines"),
        Binding("h", "toggle_blind", "hide verdict"),
        Binding("q", "quit", "exit"),
    ]

    def __init__(self, session: ReviewSession | SelfCheckSession, *, blind: bool = False):
        super().__init__()
        self.session = session
        self.blind = blind
        self._show_context = False
        self._card_started = time.monotonic()
        self._pending_note: str | None = None

    #── layout ────────────────────────── ───────────────────────────
    def compose(self) -> ComposeResult:
        yield Static("", id="status")
        with VerticalScroll(id="card"):
            yield Static("", id="question")
            yield Static("", id="answer")
            yield Static("", id="context-panel")
            yield Static("", id="verdict-panel")
        yield Static("", id="footer")

    def on_mount(self) -> None:
        self.refresh_card()

    #── rendering ─────────────────────────── ───────────────────────────
    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._card_started) * 1000)

    def refresh_card(self) -> None:
        self._card_started = time.monotonic()
        self._pending_note = None
        cur = self.session.current()
        stats = self.session.stats()
        agreement = f"{stats.agreement:.0%}" if stats.agreement is not None else "—"
        self.query_one("#status", Static).update(
            f"[b]{self.session.project.load_config().project}[/b] ── "
            f"{stats.done}/{stats.total} ── p:{stats.p} f:{stats.f} s:{stats.s} ── "
            f"agreement with the agent:{agreement}"
        )
        footer = (
            "[b]p[/b] positive [b]f[/b] negative [b]s[/b] skip [b]u[/b] undo [b]n[/b] note"
            "[b]c[/b] context [b]g[/b] guidelines [b]h[/b] verdict [b]q[/b] exit"
        )
        self.query_one("#footer", Static).update(footer)

        question_w = self.query_one("#question", Static)
        answer_w = self.query_one("#answer", Static)
        context_w = self.query_one("#context-panel", Static)
        verdict_w = self.query_one("#verdict-panel", Static)

        if cur is None:
            question_w.update("[b green]Done![/b green] All examples are marked.")
            answer_w.update("Next: [b]lazy export[/b] - collect the gold set and report. [b]q[/b] — exit.")
            context_w.display = False
            verdict_w.display = False
            return

        ex, verdict = cur
        question_w.update(f"[dim]QUESTION[/dim]\n[b]{escape(ex.question)}[/b]")
        answer_w.update(f"\n[dim]RESPONSE RAG-a[/dim]\n{escape(ex.answer)}")
        context_w.display = self._show_context and bool(ex.context)
        if ex.context:
            ctx = "\n\n".join(
                f"[dim]{escape(c.source or '')}[/dim]\n{escape(c.text)}" for c in ex.context
            )
            context_w.update(f"[dim]CONTEXT OF THE VERIFICATE RAG-a[/dim]\n{ctx}")

        verdict_w.display = not self.blind
        verdict_w.update(self._render_verdict(ex, verdict))

    def _render_verdict(self, ex: Example, verdict: Verdict | None) -> str:
        if verdict is None:
            return "[yellow]There is no agent verdict - the example did not pass the lazy check.[/yellow]"
        rec_color = "green" if verdict.recommendation == "p" else "red"
        esc = "[magenta](escalated)[/magenta]" if verdict.escalated else ""
        lines = [
            f"[dim]AGENT:[/dim] recommends [{rec_color} b]\\[{verdict.recommendation}][/{rec_color} b]"
            f" ── confidence {verdict.confidence:.2f} ── {verdict.category}{esc}",
            escape(verdict.reasoning),
            "",
        ]
        for cv in verdict.claims:
            mark = _STATUS_MARK[cv.status]
            lines.append(f"{mark} «{escape(cv.text)}» — {_STATUS_WORD[cv.status]}")
            for ev in cv.evidence[:2]:
                lines.append(f"   [dim]▸ {escape(ev.source)}:[/dim] [i]«{escape(ev.text)}»[/i]")
        return "\n".join(lines)

    #── actions ─────────────────────────── ────────────────────────────
    def _commit(self, label: str, note: str | None) -> None:
        self.session.decide(label, note=note, elapsed_ms=self._elapsed_ms())
        self.refresh_card()

    def action_decide(self, label: str) -> None:
        if self.session.current_id() is None:
            return
        self._commit(label, self._pending_note)

    def action_skip(self) -> None:
        if self.session.current_id() is None:
            return

        def on_note(note: str | None) -> None:
            if note is not None:  #Esc—cancel skip; a note is required (skip = signal about a hole in the guidelines)
                self._commit("s", note)

        self.push_screen(NoteScreen("Skip: why is the example skipped?", required=True), on_note)

    def action_undo(self) -> None:
        if self.session.undo() is not None:
            self.refresh_card()

    def action_note(self) -> None:
        if self.session.current_id() is None:
            return

        def on_note(note: str | None) -> None:
            if note:
                self._pending_note = note

        self.push_screen(NoteScreen("Note on the current example (will go with the solution):"), on_note)

    def action_toggle_context(self) -> None:
        self._show_context = not self._show_context
        cur = self.session.current()
        panel = self.query_one("#context-panel", Static)
        panel.display = self._show_context and bool(cur and cur[0].context)

    def action_guidelines(self) -> None:
        self.push_screen(GuidelinesScreen(self.session.project.load_guidelines()))

    def action_toggle_blind(self) -> None:
        self.blind = not self.blind
        self.query_one("#verdict-panel", Static).display = (
            not self.blind and self.session.current_id() is not None
        )
