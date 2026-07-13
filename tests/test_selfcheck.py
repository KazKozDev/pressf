"""Self-check: blind double-check of yourself, separate log, intra-agreement."""

from __future__ import annotations

from pressf.config import Project
from pressf.review import ReviewSession, SelfCheckSession, selfcheck_agreement


def _annotate_all(project: Project) -> None:
    s = ReviewSession(project)
    while s.current_id():
        s.decide("f" if s.current_id() == "e2" else "p")


def test_selfcheck_queue_and_agreement(project: Project):
    _annotate_all(project)
    sc = SelfCheckSession(project, fraction=1.0, seed=42)
    assert set(sc.queue) <= {"e1", "e2", "e3"} and len(sc.queue) == 3
    #the agent's verdict is always hidden
    assert sc.current()[1] is None

    first = sc.current_id()
    sc.decide("p" if first != "e2" else "f")   #coincide with ourselves
    second = sc.current_id()
    sc.decide("f" if second != "e2" else "p")  #contradicting ourselves
    stats = sc.stats()
    assert stats.done == 2 and stats.agreement == 0.5

    #the log is separate, the main markup is not touched
    assert project.selfcheck_path.exists()
    assert len(project.effective_annotations()) == 3

    agg = selfcheck_agreement(project)
    assert agg == (1, 2)


def test_selfcheck_undo(project: Project):
    _annotate_all(project)
    sc = SelfCheckSession(project, fraction=1.0, seed=1)
    eid = sc.current_id()
    sc.decide("p")
    assert sc.undo() == eid
    assert sc.current_id() == eid
    assert selfcheck_agreement(project) is None  #decision reversed


def test_selfcheck_excludes_already_rechecked(project: Project):
    _annotate_all(project)
    sc1 = SelfCheckSession(project, fraction=1.0, seed=7)
    done_id = sc1.current_id()
    sc1.decide("p")
    sc2 = SelfCheckSession(project, fraction=1.0, seed=7)
    assert done_id not in sc2.queue
