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
});
