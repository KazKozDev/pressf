"""Review session: order, decisions, undo, resume, agreement."""

from __future__ import annotations

from pressf.config import Project
from pressf.review import ReviewSession


def test_order_confidence_uncertain_first(project: Project):
    s = ReviewSession(project)
    # e2 (conf 0.55) → e3 (0.8) → e1 (0.95)
    assert s.queue == ["e2", "e3", "e1"]


def test_decide_and_stats(project: Project):
    s = ReviewSession(project)
    s.decide("f")            #e2: agent recommended f → agreement
    s.decide("f", note="X")  #e3: agent p, person f → disagreement
    stats = s.stats()
    assert (stats.done, stats.f) == (2, 2)
    assert stats.agreement == 0.5


def test_undo_returns_example_and_survives_in_log(project: Project):
    s = ReviewSession(project)
    s.decide("p")
    assert s.current_id() == "e3"
    assert s.undo() == "e2"
    assert s.current_id() == "e2"
    #log: decision + undo event
    log = project.load_annotation_log()
    assert [a.undone for a in log] == [False, True]
    assert project.effective_annotations() == {}


def test_resume_after_restart(project: Project):
    s1 = ReviewSession(project)
    s1.decide("f")
    s1.decide("p")
    #«process restart»
    s2 = ReviewSession(project)
    assert s2.queue == ["e1"]
    assert s2.stats().done == 2


def test_skip_with_note(project: Project):
    s = ReviewSession(project)
    s.decide("s", note="it is not clear what is considered a limit")
    ann = project.effective_annotations()["e2"]
    assert ann.label == "s"
    assert ann.note
    assert ann.agreed_with_agent is None
