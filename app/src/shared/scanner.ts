import type { Verdict } from "../main/types";
import { S, type FindingCategory } from "../renderer/strings";

export type { FindingCategory };

export const findingCategoryCopy = S.categories;

export const proofMarks = S.categoryMarks;

export function isSuspicious(verdict: Verdict | null | undefined): boolean {
  if (!verdict) return true;
  if (verdict.category === "trajectory_inefficient") return verdict.recommendation === "f";
  if (verdict.category.startsWith("trajectory_")) return verdict.category !== "trajectory_ok";
  return verdict.recommendation === "f" || verdict.confidence < 0.7;
}

export function categoryForVerdict(verdict: Verdict | null | undefined): FindingCategory {
  if (!verdict) return "uncertain";
  if (verdict.category === "trajectory_ok") return "trajectory_ok";
  if (verdict.category === "trajectory_inefficient") return "trajectory_inefficient";
  if (verdict.category === "trajectory_unfaithful") return "trajectory_unfaithful";
  if (verdict.category === "trajectory_unsafe") return "trajectory_unsafe";
  if (verdict.category === "trajectory_wrong_answer") return "trajectory_wrong_answer";
  if (verdict.confidence < 0.7) return "uncertain";
  if (verdict.category === "hallucination_contradicts") return "contradicts";
  if (verdict.category === "hallucination_unanswerable") return "made_up";
  if (verdict.category === "false_refusal") return "bad_refusal";
  if (verdict.category === "partial") return "incomplete";
  if (verdict.category === "violates_policy") return "policy_break";
  if (verdict.category === "unclear_policy") return "uncertain";
  if (verdict.category === "context_partial") return "search_partial";
  if (verdict.category === "context_missing") return "search_missing";
  return verdict.recommendation === "f" ? "uncertain" : "looks_fine";
}

export function trustCaption(score: number | null): string {
  if (score === null) return S.trustCaption.unavailable;
  if (score >= 0.9) return S.trustCaption.high;
  if (score >= 0.75) return S.trustCaption.medium;
  return S.trustCaption.low;
}
