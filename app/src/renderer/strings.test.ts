import { describe, expect, it } from "vitest";
import { S } from "./strings";

const cyrillic = /[\u0400-\u052f]/;

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (typeof value === "function") return collectStrings((value as (...args: unknown[]) => unknown)("Sample", 1, 2));
  if (!value || typeof value !== "object") return [];
  return Object.values(value).flatMap(collectStrings);
}

describe("UI strings", () => {
  it("keeps renderer copy English-only", () => {
    const allStrings = collectStrings(S);
    expect(allStrings.length).toBeGreaterThan(50);
    for (const text of allStrings) {
      expect(text, text).not.toMatch(cyrillic);
    }
  });

  it("has complete trajectory task and category copy", () => {
    expect(S.tasks.homeTitle.agent_trajectory).toBeTruthy();
    expect(S.tasks.suspiciousTitle.agent_trajectory).toBeTruthy();
    expect(S.tasks.subtitle.agent_trajectory).toBeTruthy();
    expect(S.tasks.steps.agent_trajectory).toHaveLength(3);
    for (const category of ["trajectory_ok", "trajectory_inefficient", "trajectory_unfaithful", "trajectory_unsafe", "trajectory_wrong_answer"] as const) {
      expect(S.categories[category].title).toBeTruthy();
      expect(S.categories[category].cardWord).toBeTruthy();
      expect(S.categoryMarks[category].mark).toBeTruthy();
      expect(S.categoryMarks[category].label).toBeTruthy();
    }
  });
});
