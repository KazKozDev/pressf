import { describe, expect, it } from "vitest";
import type { Annotation, Verdict } from "../main/types";
import {
  cohenKappa,
  effectiveByAnnotator,
  faithfulnessFromLabels,
  faithfulnessScore,
  flagPrecisionRecall,
  interAnnotatorKappa,
  judgeHumanPairs,
  pairwiseSummary,
  perCategoryAgreement,
  signTestP,
  wilsonInterval
} from "./stats";

function annotation(exampleId: string, label: Annotation["label"], extra: Partial<Annotation> = {}): Annotation {
  return { example_id: exampleId, label, ...extra };
}

function verdict(exampleId: string, recommendation: "p" | "f", extra: Partial<Verdict> = {}): Verdict {
  return {
    example_id: exampleId,
    claims: [],
    answerable: true,
    recommendation,
    category: recommendation === "f" ? "hallucination_contradicts" : "supported",
    confidence: 0.9,
    reasoning: "",
    judge_model: "test",
    ...extra
  };
}

describe("wilsonInterval", () => {
  it("returns zeros for empty samples", () => {
    expect(wilsonInterval(0, 0)).toEqual([0, 0]);
  });

  it("stays inside [0, 1] at the edges", () => {
    const [lo, hi] = wilsonInterval(10, 10);
    expect(lo).toBeGreaterThan(0.6);
    expect(hi).toBe(1);
  });

  it("matches the classic 8/10 interval", () => {
    const [lo, hi] = wilsonInterval(8, 10);
    expect(lo).toBeCloseTo(0.4902, 3);
    expect(hi).toBeCloseTo(0.9433, 3);
  });
});

describe("flagPrecisionRecall", () => {
  it("computes precision and recall for the f class", () => {
    const result = flagPrecisionRecall([
      ["f", "f"],
      ["f", "p"],
      ["p", "f"],
      ["p", "p"]
    ]);
    expect(result).toMatchObject({ tp: 1, fp: 1, fn: 1 });
    expect(result.precision).toBeCloseTo(0.5);
    expect(result.recall).toBeCloseTo(0.5);
    expect(result.f1).toBeCloseTo(0.5);
  });

  it("is all zeros without flagged examples", () => {
    expect(flagPrecisionRecall([["p", "p"]])).toMatchObject({ precision: 0, recall: 0, f1: 0 });
  });
});

describe("perCategoryAgreement", () => {
  it("aggregates agreement per category and skips non-p/f humans", () => {
    const result = perCategoryAgreement([
      ["halluc", "f", "f"],
      ["halluc", "f", "p"],
      ["refusal", "p", "p"],
      ["refusal", "p", "s"]
    ]);
    expect(result.get("halluc")).toEqual({ total: 2, agreement: 0.5 });
    expect(result.get("refusal")).toEqual({ total: 1, agreement: 1 });
  });
});

describe("cohenKappa", () => {
  it("is 0 for no pairs", () => {
    expect(cohenKappa([])).toBe(0);
  });

  it("is 1 for identical single-label annotators", () => {
    expect(cohenKappa([["p", "p"], ["p", "p"]])).toBe(1);
  });

  it("removes chance agreement", () => {
    const kappa = cohenKappa([
      ["p", "p"],
      ["p", "p"],
      ["f", "f"],
      ["p", "f"]
    ]);
    expect(kappa).toBeCloseTo(0.5, 6);
  });
});

describe("effectiveByAnnotator + interAnnotatorKappa", () => {
  it("keeps the last non-undone label per annotator and pairs them", () => {
    const annotations: Annotation[] = [
      annotation("e1", "p", { annotator: "alice" }),
      annotation("e1", "f", { annotator: "alice" }),
      annotation("e2", "p", { annotator: "alice" }),
      annotation("e2", "p", { annotator: "alice", undone: true }),
      annotation("e1", "f", { annotator: "bob" }),
      annotation("e3", "p", { annotator: "bob" })
    ];
    const byAnnotator = effectiveByAnnotator(annotations);
    expect(byAnnotator.get("alice")?.get("e1")).toBe("f");
    expect(byAnnotator.get("alice")?.has("e2")).toBe(false);
    const kappa = interAnnotatorKappa(byAnnotator);
    expect(kappa).toHaveLength(1);
    expect(kappa[0]).toMatchObject({ a: "alice", b: "bob", common: 1, kappa: 1 });
  });

  it("skips pairs without common examples", () => {
    const byAnnotator = effectiveByAnnotator([
      annotation("e1", "p", { annotator: "alice" }),
      annotation("e2", "p", { annotator: "bob" })
    ]);
    expect(interAnnotatorKappa(byAnnotator)).toEqual([]);
  });
});

describe("faithfulness", () => {
  it("ignores skips", () => {
    const score = faithfulnessFromLabels(["p", "p", "f", "s"]);
    expect(score.passed).toBe(2);
    expect(score.failed).toBe(1);
    expect(score.faithfulness).toBeCloseTo(2 / 3);
  });

  it("prefers human labels over judge verdicts", () => {
    const effective = { e1: annotation("e1", "p"), e2: annotation("e2", "f") };
    const verdicts = { e1: verdict("e1", "f"), e2: verdict("e2", "f"), e3: verdict("e3", "f") };
    const score = faithfulnessScore(effective, verdicts);
    expect(score.source).toBe("human");
    expect(score.faithfulness).toBeCloseTo(0.5);
  });

  it("falls back to judge verdicts, then to none", () => {
    expect(faithfulnessScore({}, { e1: verdict("e1", "p") })).toMatchObject({ source: "judge", faithfulness: 1 });
    expect(faithfulnessScore({}, {})).toMatchObject({ source: "none", n: 0 });
  });
});

describe("signTestP", () => {
  it("is 1 for a perfectly balanced outcome and for empty samples", () => {
    expect(signTestP(0, 0)).toBe(1);
    expect(signTestP(5, 10)).toBeCloseTo(1, 6);
  });

  it("matches the exact binomial for a known case", () => {
    // P(X <= 1 or X >= 9) for n=10, p=0.5 => 2 * (1 + 10) / 1024
    expect(signTestP(9, 10)).toBeCloseTo((2 * 11) / 1024, 10);
  });

  it("stays finite for large n", () => {
    const p = signTestP(1300, 2000);
    expect(p).toBeGreaterThan(0);
    expect(p).toBeLessThan(1e-30);
  });
});

describe("pairwiseSummary", () => {
  it("counts wins, ties, win rate and left-side share", () => {
    const summary = pairwiseSummary({
      e1: { winner: "b", shown_left: "b" },
      e2: { winner: "b", shown_left: "a" },
      e3: { winner: "a", shown_left: "a" },
      e4: { winner: "tie", shown_left: "b" }
    });
    expect(summary).toMatchObject({ aWins: 1, bWins: 2, ties: 1, decided: 3 });
    expect(summary.winRate).toBeCloseTo(2 / 3);
    expect(summary.leftShare).toBeCloseTo(2 / 3);
    expect(summary.pValue).toBeCloseTo(1, 6);
  });

  it("handles empty and legacy choice-only records", () => {
    expect(pairwiseSummary({})).toMatchObject({ decided: 0, winRate: null, pValue: null, leftShare: null });
    expect(pairwiseSummary({ e1: { choice: "a" } }).aWins).toBe(1);
  });
});

describe("judgeHumanPairs", () => {
  it("pairs reviewed p/f labels with their verdicts", () => {
    const effective = {
      e1: annotation("e1", "p"),
      e2: annotation("e2", "s"),
      e3: annotation("e3", "f")
    };
    const verdicts = { e1: verdict("e1", "p"), e3: verdict("e3", "p") };
    expect(judgeHumanPairs(effective, verdicts).sort()).toEqual([
      ["p", "f"],
      ["p", "p"]
    ]);
  });
});
