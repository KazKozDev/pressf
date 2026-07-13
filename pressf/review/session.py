"""Review session logic: order, resume, undo, atomic record, statistics.

Separated from TUI to allow testing without a terminal."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Project
from ..io import append_jsonl, read_jsonl
from ..schemas import Annotation, Example, Verdict


@dataclass
class SessionStats:
    total: int
    done: int
    p: int
    f: int
    s: int
    agreement: float | None  #percentage of matches with the agent’s recommendation (by p/f)


class ReviewSession:
    def __init__(
        self,
        project: Project,
        *,
        order: str = "confidence",
        annotator: str = "",
    ):
        self.project = project
        self.annotator = annotator
        self.examples: dict[str, Example] = {ex.id: ex for ex in project.load_examples()}
        self.verdicts: dict[str, Verdict] = project.load_verdicts()
        self._effective: dict[str, Annotation] = project.effective_annotations()
        self._undo_stack: list[str] = []  #ID of solutions for this session

        pending = [eid for eid in self.examples if eid not in self._effective]
        if order == "confidence":
            #doubtful first; examples without a verdict - at the very beginning
            pending.sort(key=lambda eid: self.verdicts[eid].confidence if eid in self.verdicts else -1.0)
        elif order == "informative":
            #active learning: first those where the judge is on the verge of a decision (confidence is at the threshold
            #flag 0.7) - their marking moves the calibration the most; no verdict - go ahead
            threshold = 0.7
            pending.sort(key=lambda eid: abs(self.verdicts[eid].confidence - threshold)
                         if eid in self.verdicts else -1.0)
        elif order == "random":
            import random

            random.shuffle(pending)
        #"original" - examples.jsonl order, do nothing
        self.queue: list[str] = pending

    #── current example ──────────────────────── ─────────────────────────
    def current_id(self) -> str | None:
        return self.queue[0] if self.queue else None

    def current(self) -> tuple[Example, Verdict | None] | None:
        eid = self.current_id()
        if eid is None:
            return None
        return self.examples[eid], self.verdicts.get(eid)

    #── solutions ──────────────────────────── ────────────────────────────
    def decide(self, label: str, *, note: str | None = None, elapsed_ms: int | None = None) -> None:
        eid = self.current_id()
        if eid is None:
            raise RuntimeError("The queue is empty")
        verdict = self.verdicts.get(eid)
        agreed = None
        if verdict is not None and label in ("p", "f"):
            agreed = label == verdict.recommendation
        ann = Annotation(
            example_id=eid,
            label=label,  # type: ignore[arg-type]
            note=note,
            agreed_with_agent=agreed,
            annotator=self.annotator,
            elapsed_ms=elapsed_ms,
        )
        append_jsonl(self.project.annotations_path, ann)
        self._effective[eid] = ann
        self._undo_stack.append(eid)
        self.queue.pop(0)

    def undo(self) -> str | None:
        """Cancel the last decision of this session; the example is returned to the head of the queue."""
        if not self._undo_stack:
            return None
        eid = self._undo_stack.pop()
        prev = self._effective.pop(eid, None)
        event = Annotation(
            example_id=eid,
            label=prev.label if prev else "s",
            undone=True,
            annotator=self.annotator,
        )
        append_jsonl(self.project.annotations_path, event)
        self.queue.insert(0, eid)
        return eid

    #── statistics ────────────────────────── ───────────────────────────
    def stats(self) -> SessionStats:  #noqa: C901 - ​​linear counting
        counts = {"p": 0, "f": 0, "s": 0}
        agreed = disagreed = 0
        for ann in self._effective.values():
            counts[ann.label] = counts.get(ann.label, 0) + 1
            if ann.agreed_with_agent is True:
                agreed += 1
            elif ann.agreed_with_agent is False:
                disagreed += 1
        agreement = agreed / (agreed + disagreed) if (agreed + disagreed) else None
        return SessionStats(
            total=len(self.examples),
            done=len(self._effective),
            p=counts["p"],
            f=counts["f"],
            s=counts["s"],
            agreement=agreement,
        )


class SelfCheckSession:
    """Self-check (PLAN.md §4.3): random fraction of already marked examples
    presented repeatedly blindly; solutions are written in a separate selfcheck.jsonl.
    agreement here means agreement with YOURSELF (intra-annotator), not with the agent.

    The interface is compatible with ReviewSession - TUI works with both (duck typing)."""

    def __init__(self, project: Project, *, fraction: float = 0.1, annotator: str = "", seed: int | None = None):
        import random

        self.project = project
        self.annotator = annotator or "self-check"
        self.examples = {ex.id: ex for ex in project.load_examples()}
        self.verdicts = project.load_verdicts()
        self._original = {
            eid: a for eid, a in project.effective_annotations().items() if a.label in ("p", "f")
        }
        already = {a.example_id for a in read_jsonl(project.selfcheck_path, Annotation) if not a.undone}
        candidates = [eid for eid in self._original if eid not in already]
        rng = random.Random(seed)
        rng.shuffle(candidates)
        n = max(1, round(len(self._original) * fraction)) if candidates else 0
        self.queue: list[str] = candidates[:n]
        self._undo_stack: list[str] = []
        self._decisions: dict[str, str] = {}

    def current_id(self) -> str | None:
        return self.queue[0] if self.queue else None

    def current(self) -> tuple[Example, Verdict | None] | None:
        eid = self.current_id()
        if eid is None:
            return None
        return self.examples[eid], None  #We always hide the verdict: we check ourselves, not the agent

    def decide(self, label: str, *, note: str | None = None, elapsed_ms: int | None = None) -> None:
        eid = self.current_id()
        if eid is None:
            raise RuntimeError("The queue is empty")
        ann = Annotation(
            example_id=eid,
            label=label,  # type: ignore[arg-type]
            note=note,
            agreed_with_agent=None,
            annotator=self.annotator,
            elapsed_ms=elapsed_ms,
        )
        append_jsonl(self.project.selfcheck_path, ann)
        self._decisions[eid] = label
        self._undo_stack.append(eid)
        self.queue.pop(0)

    def undo(self) -> str | None:
        if not self._undo_stack:
            return None
        eid = self._undo_stack.pop()
        label = self._decisions.pop(eid, "s")
        append_jsonl(
            self.project.selfcheck_path,
            Annotation(example_id=eid, label=label, undone=True, annotator=self.annotator),  # type: ignore[arg-type]
        )
        self.queue.insert(0, eid)
        return eid

    def stats(self) -> SessionStats:
        counts = {"p": 0, "f": 0, "s": 0}
        match = mismatch = 0
        for eid, label in self._decisions.items():
            counts[label] += 1
            if label in ("p", "f"):
                if label == self._original[eid].label:
                    match += 1
                else:
                    mismatch += 1
        agreement = match / (match + mismatch) if (match + mismatch) else None
        return SessionStats(
            total=len(self.queue) + len(self._decisions),
            done=len(self._decisions),
            p=counts["p"],
            f=counts["f"],
            s=counts["s"],
            agreement=agreement,  #agreement with oneself
        )


def selfcheck_agreement(project: Project) -> tuple[int, int] | None:
    """(coincidentally, total re-labeled p/f) throughout the entire selfcheck log - for the report."""
    log = read_jsonl(project.selfcheck_path, Annotation)
    if not log:
        return None
    effective: dict[str, Annotation] = {}
    for a in log:
        if a.undone:
            effective.pop(a.example_id, None)
        else:
            effective[a.example_id] = a
    original = project.effective_annotations()
    match = total = 0
    for eid, a in effective.items():
        orig = original.get(eid)
        if a.label in ("p", "f") and orig and orig.label in ("p", "f"):
            total += 1
            match += int(a.label == orig.label)
    return (match, total) if total else None
