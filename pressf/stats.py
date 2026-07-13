"""Statistics for trusting numbers: confidence intervals, judge's accuracy, sampling.

Everything is pure functions with no Project dependencies to test directly."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson confidence interval for the proportion (default 95%).

    Wilson, and not the normal approximation - it is correct both at small n and at the edges 0/1,
    where the usual «p ± z·se» goes beyond [0,1] or collapses to zero."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def sign_test_p(successes: int, n: int) -> float:
    """Accurate two-way sign test for pairwise comparisons.

    Draws do not fall into n: the test answers whether one version could win so many times
    happen by chance with equal versions."""
    if n <= 0:
        return 1.0
    observed = math.comb(n, successes)
    numerator = sum(math.comb(n, i) for i in range(n + 1) if math.comb(n, i) <= observed)
    return min(1.0, numerator / (2**n))


@dataclass(frozen=True)
class PairwiseSummary:
    a_wins: int
    b_wins: int
    ties: int
    decided: int
    b_win_rate: float | None
    ci_low: float
    ci_high: float
    p_value: float | None
    left_pick_rate: float | None

    @property
    def decision(self) -> str:
        """Conservative recommendation for version B release."""
        if not self.decided:
            return "There are not enough solved pairs for withdrawal."
        if self.ci_low > 0.5:
            return "Version B is better: lower bound 95% CI greater than 50%; can be released."
        if self.ci_high < 0.5:
            return "Version B is worse: the upper limit of the 95% CI is below 50%; don't let her out."
        return "We can't say for sure that version B is better; add steam for marking."


def pairwise_summary(annotations: Sequence[object]) -> PairwiseSummary:
    """Aggregate effective PairwiseAnnotation without depending on Project."""
    a_wins = b_wins = ties = left_picks = 0
    for ann in annotations:
        winner = getattr(ann, "winner", None) or getattr(ann, "choice", None)
        if winner == "a":
            a_wins += 1
        elif winner == "b":
            b_wins += 1
        elif winner == "tie":
            ties += 1
        shown_left = getattr(ann, "shown_left", None)
        if winner in ("a", "b") and shown_left:
            left_picks += int(winner == shown_left)
    decided = a_wins + b_wins
    ci_low, ci_high = wilson_interval(b_wins, decided)
    return PairwiseSummary(
        a_wins=a_wins,
        b_wins=b_wins,
        ties=ties,
        decided=decided,
        b_win_rate=b_wins / decided if decided else None,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=sign_test_p(b_wins, decided) if decided else None,
        left_pick_rate=left_picks / decided if decided else None,
    )


def flag_precision_recall(pairs: Sequence[tuple[str, str]]) -> dict[str, float | int]:
    """Judge's accuracy on class «problem» (f) against a human reference.

    pairs - list (judge's recommendation, person's tag), tags in {p, f}.
    Positive class - f (found a problem). precision = of those marked by the judge as f,
    how much f is real per person; recall = from real f, how many the judge caught."""
    tp = fp = fn = 0
    for judge, human in pairs:
        if judge == "f" and human == "f":
            tp += 1
        elif judge == "f" and human == "p":
            fp += 1
        elif judge == "p" and human == "f":
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def per_category_agreement(rows: Sequence[tuple[str, str, str]]) -> dict[str, tuple[int, float]]:
    """Agreement between a judge and a person in terms of verdict categories.

    rows — (judge category, judge recommendation, person tag). Returns for each
    categories (how many are marked, percentage of agreement). Shows what types of errors
    the judge systematically disagrees with the person."""
    agg: dict[str, list[int]] = {}
    for category, judge, human in rows:
        if human not in ("p", "f"):
            continue
        total, agreed = agg.setdefault(category, [0, 0])
        agg[category] = [total + 1, agreed + int(judge == human)]
    return {cat: (total, agreed / total if total else 0.0) for cat, (total, agreed) in agg.items()}


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float:
    """Cohen's kappa for the agreement of two markers on common examples.

    pairs - labels (annotator A, annotator B) for the same examples. Kappa cleans up
    agreement by chance: 1.0 - perfect, 0 - at the level of chance, <0 - worse than chance."""
    n = len(pairs)
    if n == 0:
        return 0.0
    labels = sorted({lbl for pair in pairs for lbl in pair})
    observed = sum(1 for a, b in pairs if a == b) / n
    a_freq = {lbl: sum(1 for a, _ in pairs if a == lbl) / n for lbl in labels}
    b_freq = {lbl: sum(1 for _, b in pairs if b == lbl) / n for lbl in labels}
    expected = sum(a_freq[lbl] * b_freq[lbl] for lbl in labels)
    if expected >= 1.0:
        return 1.0  #all marks match and are the same - complete agreement
    return (observed - expected) / (1 - expected)


def inter_annotator_kappa(
    per_annotator: dict[str, dict[str, str]]
) -> list[tuple[str, str, int, float]]:
    """Pairwise kappa between all markers who have common examples.

    per_annotator - {name: {example_id: label}}. Returns a list
    (annotator A, annotator B, number of common examples, kappa), only for pairs with overlap."""
    names = sorted(per_annotator)
    out: list[tuple[str, str, int, float]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            common = set(per_annotator[a]) & set(per_annotator[b])
            if not common:
                continue
            pairs = [(per_annotator[a][eid], per_annotator[b][eid]) for eid in sorted(common)]
            out.append((a, b, len(common), cohen_kappa(pairs)))
    return out


def seeded_sample(items: Sequence[T], n: int, seed: int = 0) -> list[T]:
    """Deterministic random sampling of n elements (for cheap representative testing).

    Preserves the original order of the selected ones - the run is predictable and reproducible by seed."""
    if n >= len(items):
        return list(items)
    if n <= 0:
        return []
    rng = random.Random(seed)
    idx = sorted(rng.sample(range(len(items)), n))
    return [items[i] for i in idx]
