import type { Annotation, Label, Verdict } from "../main/types";

// TypeScript port of pressf/stats.py and pressf/scoring.py so the desktop app can
// show the same trust numbers as out/report.md without spawning the CLI.

export function wilsonInterval(successes: number, n: number, z = 1.96): [number, number] {
  if (n <= 0) return [0, 0];
  const p = successes / n;
  const denom = 1 + (z * z) / n;
  const center = (p + (z * z) / (2 * n)) / denom;
  const margin = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, center - margin), Math.min(1, center + margin)];
}

export type FlagQuality = {
  tp: number;
  fp: number;
  fn: number;
  precision: number;
  recall: number;
  f1: number;
};

export function flagPrecisionRecall(pairs: Array<[string, string]>): FlagQuality {
  let tp = 0;
  let fp = 0;
  let fn = 0;
  for (const [judge, human] of pairs) {
    if (judge === "f" && human === "f") tp += 1;
    else if (judge === "f" && human === "p") fp += 1;
    else if (judge === "p" && human === "f") fn += 1;
  }
  const precision = tp + fp ? tp / (tp + fp) : 0;
  const recall = tp + fn ? tp / (tp + fn) : 0;
  const f1 = precision + recall ? (2 * precision * recall) / (precision + recall) : 0;
  return { tp, fp, fn, precision, recall, f1 };
}

export function perCategoryAgreement(rows: Array<[string, string, string]>): Map<string, { total: number; agreement: number }> {
  const agg = new Map<string, { total: number; agreed: number }>();
  for (const [category, judge, human] of rows) {
    if (human !== "p" && human !== "f") continue;
    const bucket = agg.get(category) ?? { total: 0, agreed: 0 };
    bucket.total += 1;
    bucket.agreed += Number(judge === human);
    agg.set(category, bucket);
  }
  return new Map([...agg.entries()].map(([category, { total, agreed }]) => [category, { total, agreement: total ? agreed / total : 0 }]));
}

export function cohenKappa(pairs: Array<[string, string]>): number {
  const n = pairs.length;
  if (n === 0) return 0;
  const labels = [...new Set(pairs.flat())];
  const observed = pairs.filter(([a, b]) => a === b).length / n;
  const expected = labels.reduce((sum, label) => {
    const aFreq = pairs.filter(([a]) => a === label).length / n;
    const bFreq = pairs.filter(([, b]) => b === label).length / n;
    return sum + aFreq * bFreq;
  }, 0);
  if (expected >= 1) return 1; // everyone used one identical label — full agreement
  return (observed - expected) / (1 - expected);
}

export type AnnotatorKappa = { a: string; b: string; common: number; kappa: number };

export function interAnnotatorKappa(perAnnotator: Map<string, Map<string, Label>>): AnnotatorKappa[] {
  const names = [...perAnnotator.keys()].sort();
  const out: AnnotatorKappa[] = [];
  for (let i = 0; i < names.length; i += 1) {
    for (let j = i + 1; j < names.length; j += 1) {
      const a = perAnnotator.get(names[i])!;
      const b = perAnnotator.get(names[j])!;
      const common = [...a.keys()].filter((id) => b.has(id)).sort();
      if (!common.length) continue;
      const pairs = common.map((id) => [a.get(id)!, b.get(id)!] as [string, string]);
      out.push({ a: names[i], b: names[j], common: common.length, kappa: cohenKappa(pairs) });
    }
  }
  return out;
}

// Effective (last non-undone) label per example, split by annotator — the input
// interAnnotatorKappa needs. Mirrors effective_annotations_by_annotator() in config.py.
export function effectiveByAnnotator(annotations: Annotation[]): Map<string, Map<string, Label>> {
  const out = new Map<string, Map<string, Label>>();
  for (const ann of annotations) {
    const name = ann.annotator?.trim() || "unknown";
    const byExample = out.get(name) ?? new Map<string, Label>();
    if (ann.undone) byExample.delete(ann.example_id);
    else byExample.set(ann.example_id, ann.label);
    out.set(name, byExample);
  }
  for (const [name, byExample] of out) if (!byExample.size) out.delete(name);
  return out;
}

export type FaithfulnessScore = {
  faithfulness: number;
  passed: number;
  failed: number;
  n: number;
  source: "human" | "judge" | "none";
};

export function faithfulnessFromLabels(labels: string[]): FaithfulnessScore {
  const passed = labels.filter((label) => label === "p").length;
  const failed = labels.filter((label) => label === "f").length;
  const n = passed + failed;
  return { faithfulness: n ? passed / n : 0, passed, failed, n, source: "none" };
}

// Port of scoring.py score_project: human labels are the reference, judge verdicts
// only stand in while nothing is reviewed yet.
export function faithfulnessScore(effective: Record<string, Annotation>, verdicts: Record<string, Verdict>): FaithfulnessScore {
  const human = Object.values(effective).map((ann) => ann.label).filter((label) => label === "p" || label === "f");
  if (human.length) return { ...faithfulnessFromLabels(human), source: "human" };
  const judge = Object.values(verdicts).map((verdict) => verdict.recommendation).filter((label) => label === "p" || label === "f");
  if (judge.length) return { ...faithfulnessFromLabels(judge), source: "judge" };
  return { faithfulness: 0, passed: 0, failed: 0, n: 0, source: "none" };
}

// Exact two-sided sign test: probability of an outcome at least as extreme as k
// successes out of n fair coin flips. Log-space so n in the thousands doesn't underflow.
export function signTestP(k: number, n: number): number {
  if (n <= 0) return 1;
  const logC: number[] = [0];
  for (let i = 1; i <= n; i += 1) logC.push(logC[i - 1] + Math.log(n - i + 1) - Math.log(i));
  const logHalfN = n * Math.log(0.5);
  const logPmf = (i: number) => logC[i] + logHalfN;
  const observed = logPmf(k);
  let p = 0;
  for (let i = 0; i <= n; i += 1) {
    if (logPmf(i) <= observed + 1e-9) p += Math.exp(logPmf(i));
  }
  return Math.min(1, p);
}

export type PairwiseSummary = {
  aWins: number;
  bWins: number;
  ties: number;
  decided: number;
  winRate: number | null;      // share of decided pairs won by B (the new version)
  ci: [number, number];        // Wilson 95% CI on winRate
  pValue: number | null;       // sign test on decided pairs
  leftShare: number | null;    // how often the reviewer picked whichever answer was shown left
};

export function pairwiseSummary(effective: Record<string, { winner?: string; choice?: string; shown_left?: string }>): PairwiseSummary {
  let aWins = 0;
  let bWins = 0;
  let ties = 0;
  let leftPicks = 0;
  for (const ann of Object.values(effective)) {
    const winner = ann.winner ?? ann.choice;
    if (winner === "a") aWins += 1;
    else if (winner === "b") bWins += 1;
    else if (winner === "tie") ties += 1;
    if ((winner === "a" || winner === "b") && ann.shown_left) leftPicks += Number(winner === ann.shown_left);
  }
  const decided = aWins + bWins;
  return {
    aWins,
    bWins,
    ties,
    decided,
    winRate: decided ? bWins / decided : null,
    ci: wilsonInterval(bWins, decided),
    pValue: decided ? signTestP(bWins, decided) : null,
    leftShare: decided ? leftPicks / decided : null
  };
}

// (judge recommendation, human label) pairs for every reviewed example with a verdict.
export function judgeHumanPairs(effective: Record<string, Annotation>, verdicts: Record<string, Verdict>): Array<[string, string]> {
  const pairs: Array<[string, string]> = [];
  for (const ann of Object.values(effective)) {
    if (ann.label !== "p" && ann.label !== "f") continue;
    const verdict = verdicts[ann.example_id];
    if (verdict) pairs.push([verdict.recommendation, ann.label]);
  }
  return pairs;
}
