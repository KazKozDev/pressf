import { describe, expect, it } from "vitest";
import type { Verdict } from "../main/types";
import { categoryForVerdict, findingCategoryCopy, isSuspicious } from "./scanner";

function verdict(overrides: Partial<Verdict>): Verdict {
  return {
    example_id: "x",
    claims: [],
    answerable: true,
    recommendation: "p",
    category: "correct",
    confidence: 0.99,
    reasoning: "",
    judge_model: "fixture",
    ...overrides
  };
}

describe("scanner classification", () => {
  it("marks failed recommendations and low-confidence passes as flagged", () => {
    expect(isSuspicious(verdict({ recommendation: "f", confidence: 0.99 }))).toBe(true);
    expect(isSuspicious(verdict({ recommendation: "p", confidence: 0.69 }))).toBe(true);
    expect(isSuspicious(verdict({ recommendation: "p", confidence: 0.7 }))).toBe(false);
  });

  it("maps categories to user-facing card words", () => {
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "hallucination_contradicts", recommendation: "f" }))].cardWord).toBe("contradicted");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "hallucination_unanswerable", recommendation: "f" }))].cardWord).toBe("not found");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "false_refusal", recommendation: "f" }))].cardWord).toBe("refused");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "partial", recommendation: "f" }))].cardWord).toBe("incomplete");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "violates_policy", recommendation: "f" }))].cardWord).toBe("violates policy");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "context_partial", recommendation: "f" }))].cardWord).toBe("partial context");
    expect(findingCategoryCopy[categoryForVerdict(verdict({ category: "context_missing", recommendation: "f" }))].cardWord).toBe("missing context");
  });
});
