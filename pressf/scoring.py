"""Assessing the quality of a bot based on the gold set is the basis of the regression gate.

faithfulness = share of «good» answers (p) among marked ones (p+f, ignore skips).
Label source priority: human marking (standard) → judge’s verdicts (if human
haven’t marked it yet). Pure functions - tested without Project and without LLM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Score:
    faithfulness: float   #share of p among p+f
    passed: int           #how many p
    failed: int           #how much f
    n: int                #p+f (marked, no skips)
    source: str           # "human" | "judge" | "none"


def faithfulness_from_labels(labels: list[str]) -> tuple[float, int, int]:
    """labels in {p,f,s}. Returns (faithfulness, p, f); skips are discarded."""
    passed = sum(1 for x in labels if x == "p")
    failed = sum(1 for x in labels if x == "f")
    n = passed + failed
    return (passed / n if n else 0.0, passed, failed)


def score_project(project) -> Score:
    """Rate the bot by goldset. Human marks are more important than the judge's verdicts."""
    human = project.effective_annotations() if project.annotations_path.exists() else {}
    human_labels = [a.label for a in human.values() if a.label in ("p", "f")]
    if human_labels:
        f, p, fail = faithfulness_from_labels(human_labels)
        return Score(f, p, fail, p + fail, "human")

    verdicts = project.load_verdicts() if project.verdicts_path.exists() else {}
    judge_labels = [v.recommendation for v in verdicts.values() if v.recommendation in ("p", "f")]
    if judge_labels:
        f, p, fail = faithfulness_from_labels(judge_labels)
        return Score(f, p, fail, p + fail, "judge")

    return Score(0.0, 0, 0, 0, "none")
