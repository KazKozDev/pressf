import { spawn, spawnSync } from "node:child_process";
import { createReadStream, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync, cpSync, openSync, closeSync, fsyncSync } from "node:fs";
import { appendFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import readline from "node:readline";
import YAML from "yaml";
import { loadTraceRows, looksLikeAgentTraces, looksLikeTraces } from "./traces.js";
import { RETRIEVER_PARAM_KEYS, retrieverSpecFor } from "./retrieverSpec.js";
import type {
  Annotation,
  CheckEstimate,
  ColumnMapping,
  CreateCompareProjectInput,
  CreateProjectInput,
  DataInspection,
  CheckOptions,
  BotConfigView,
  BotKind,
  BotUpdate,
  CalibrationProposal,
  ExportOptions,
  LlmSetup,
  LlmProvider,
  LlmUpdate,
  ProjectConfigView,
  Example,
  Label,
  PairwiseAnnotation,
  PairwiseShownLeft,
  PairwiseWinner,
  ProjectState,
  ProjectSummary,
  RetrieverConfigView,
  RetrieverUpdate,
  SessionStats,
  SelfCheckStats,
  Verdict
} from "./types.js";

const appRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const packagedRepoRoot = process.resourcesPath ? path.join(process.resourcesPath, "repo") : "";
export const repoRoot = process.env.PRESSF_REPO_ROOT
  ? process.env.PRESSF_REPO_ROOT
  : existsSync(path.join(packagedRepoRoot, "pyproject.toml"))
  ? packagedRepoRoot
  : path.resolve(appRoot, "..");

export function projectsBase(): string {
  return process.env.PRESSF_HOME || path.join(homedir(), "Documents", "PressF");
}

export function projectPaths(root: string) {
  const data = path.join(root, "data");
  return {
    config: path.join(root, "lazy.yaml"),
    guidelines: path.join(root, "GUIDELINES.md"),
    data,
    examples: path.join(data, "examples.jsonl"),
    verdicts: path.join(data, "verdicts.jsonl"),
    annotations: path.join(data, "annotations.jsonl"),
    selfcheck: path.join(data, "selfcheck.jsonl"),
    pairwiseAnnotations: path.join(data, "pairwise_annotations.jsonl"),
    ingestReport: path.join(data, "ingest_report.md"),
    report: path.join(root, "out", "report.md"),
    goldset: path.join(root, "out", "goldset.jsonl"),
    disagreements: path.join(root, "out", "disagreements.jsonl"),
    pairs: path.join(root, "out", "pairs.jsonl"),
    runs: path.join(data, "runs")
  };
}

export function readJsonl<T>(file: string): T[] {
  if (!existsSync(file)) return [];
  return readFileSync(file, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

function appendJsonl(file: string, item: unknown) {
  mkdirSync(path.dirname(file), { recursive: true });
  const fd = openSync(file, "a");
  try {
    appendFileSync(fd, `${JSON.stringify(item)}\n`, "utf8");
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
}

function writeJsonl(file: string, items: unknown[]) {
  mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  writeFileSync(tmp, items.map((item) => JSON.stringify(item)).join("\n") + "\n", "utf8");
  const fd = openSync(tmp, "r");
  try {
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  rmSync(file, { force: true });
  cpSync(tmp, file);
  rmSync(tmp, { force: true });
}

function loadConfigName(root: string): string {
  const cfgPath = projectPaths(root).config;
  if (!existsSync(cfgPath)) return path.basename(root);
  try {
    const cfg = YAML.parse(readFileSync(cfgPath, "utf8")) as { project?: string };
    return cfg.project || path.basename(root);
  } catch {
    return path.basename(root);
  }
}

export function canonicalTask(task?: string | null): string {
  if (task === "search_quality") return "retrieval_quality";
  if (task === "compare_versions") return "pairwise_compare";
  if (task === "agents") return "agent_trajectory";
  return task || "rag_faithfulness";
}

function loadConfig(root: string): { project?: string; task?: string; ingest?: ColumnMapping; llm?: { provider?: LlmSetup["provider"] } } {
  const cfgPath = projectPaths(root).config;
  if (!existsSync(cfgPath)) return {};
  try {
    const cfg = YAML.parse(readFileSync(cfgPath, "utf8")) as { project?: string; task?: string };
    return { ...cfg, task: canonicalTask(cfg.task) };
  } catch {
    return {};
  }
}

export function loadEffectiveAnnotations(annotations: Annotation[]): Record<string, Annotation> {
  const state: Record<string, Annotation> = {};
  for (const ann of annotations) {
    if (ann.undone) delete state[ann.example_id];
    else state[ann.example_id] = ann;
  }
  return state;
}

export function loadEffectivePairwiseAnnotations(annotations: PairwiseAnnotation[]): Record<string, PairwiseAnnotation> {
  const state: Record<string, PairwiseAnnotation> = {};
  for (const ann of annotations) {
    if (ann.undone) delete state[ann.example_id];
    else state[ann.example_id] = ann;
  }
  return state;
}

export function reviewQueue(examples: Example[], verdicts: Record<string, Verdict>, effective: Record<string, Annotation>): string[] {
  return examples
    .map((example) => example.id)
    .filter((id) => !effective[id])
    .sort((a, b) => {
      const ca = verdicts[a]?.confidence ?? -1;
      const cb = verdicts[b]?.confidence ?? -1;
      return ca - cb;
    });
}

export function pairwiseQueue(examples: Example[], effective: Record<string, PairwiseAnnotation>, verdicts: Record<string, Verdict> = {}): string[] {
  const queue = examples
    .map((example) => example.id)
    .filter((id) => !effective[id]);
  // Once the pairwise judge has run, review the uncertain pairs first. Before
  // that we leave the source order intact, so blind human review stays neutral.
  if (!Object.keys(verdicts).length) return queue;
  return queue.sort((a, b) => (verdicts[a]?.confidence ?? 2) - (verdicts[b]?.confidence ?? 2));
}

export function statsFor(examples: Example[], effective: Record<string, Annotation>, verdicts: Record<string, Verdict> = {}): SessionStats {
  let p = 0;
  let f = 0;
  let s = 0;
  let agreed = 0;
  let disagreed = 0;
  for (const ann of Object.values(effective)) {
    if (ann.label === "p") p += 1;
    if (ann.label === "f") f += 1;
    if (ann.label === "s") s += 1;
    const compared = ann.agreed_with_agent ?? (ann.label === "p" || ann.label === "f" ? verdicts[ann.example_id]?.recommendation === ann.label : null);
    if (compared === true) agreed += 1;
    if (compared === false) disagreed += 1;
  }
  const denom = agreed + disagreed;
  return {
    total: examples.length,
    done: Object.keys(effective).length,
    p,
    f,
    s,
    agreement: denom ? agreed / denom : null
  };
}

export function pairwiseStatsFor(examples: Example[], effective: Record<string, PairwiseAnnotation>): SessionStats {
  let p = 0;
  let f = 0;
  let s = 0;
  for (const ann of Object.values(effective)) {
    const winner = ann.winner ?? ann.choice;
    if (winner === "a") p += 1;
    if (winner === "b") f += 1;
    if (winner === "tie") s += 1;
  }
  return {
    total: examples.length,
    done: Object.keys(effective).length,
    p,
    f,
    s,
    agreement: null
  };
}

export function selfCheckQueue(effective: Record<string, Annotation>, previous: Annotation[], fraction = 0.1, random: () => number = Math.random): string[] {
  const already = new Set(Object.values(loadEffectiveAnnotations(previous)).map((annotation) => annotation.example_id));
  const candidates = Object.values(effective).filter((annotation) => (annotation.label === "p" || annotation.label === "f") && !already.has(annotation.example_id)).map((annotation) => annotation.example_id);
  for (let index = candidates.length - 1; index > 0; index -= 1) {
    const other = Math.floor(random() * (index + 1));
    [candidates[index], candidates[other]] = [candidates[other], candidates[index]];
  }
  const count = candidates.length ? Math.max(1, Math.round(Object.values(effective).filter((annotation) => annotation.label === "p" || annotation.label === "f").length * fraction)) : 0;
  return candidates.slice(0, count);
}

export function selfCheckStatsFor(original: Record<string, Annotation>, annotations: Annotation[]): SelfCheckStats {
  const effective = loadEffectiveAnnotations(annotations);
  let matches = 0;
  let total = 0;
  for (const annotation of Object.values(effective)) {
    const before = original[annotation.example_id];
    if ((annotation.label === "p" || annotation.label === "f") && before && (before.label === "p" || before.label === "f")) {
      total += 1;
      matches += Number(annotation.label === before.label);
    }
  }
  return { total, done: Object.keys(effective).length, agreement: total ? matches / total : null };
}

export function loadProjectState(root: string): ProjectState {
  const paths = projectPaths(root);
  const examples = readJsonl<Example>(paths.examples);
  const verdictRows = readJsonl<Verdict>(paths.verdicts);
  const verdicts: Record<string, Verdict> = {};
  for (const verdict of verdictRows) verdicts[verdict.example_id] = verdict;
  const annotations = readJsonl<Annotation>(paths.annotations);
  const selfcheckAnnotations = readJsonl<Annotation>(paths.selfcheck);
  const pairwiseAnnotations = readJsonl<PairwiseAnnotation>(paths.pairwiseAnnotations);
  const effective = loadEffectiveAnnotations(annotations);
  const pairwiseEffective = loadEffectivePairwiseAnnotations(pairwiseAnnotations);
  const config = loadConfig(root);
  const task = config.task || "rag_faithfulness";
  const queue = task === "pairwise_compare" ? pairwiseQueue(examples, pairwiseEffective, verdicts) : reviewQueue(examples, verdicts, effective);
  const stats = task === "pairwise_compare" ? pairwiseStatsFor(examples, pairwiseEffective) : statsFor(examples, effective, verdicts);
  const first = queue[0];
  return {
    root,
    name: loadConfigName(root),
    task,
    examples,
    verdicts,
    annotations,
    selfcheckAnnotations,
    pairwiseAnnotations,
    effective,
    pairwiseEffective,
    queue,
    stats,
    selfcheck: selfCheckStatsFor(effective, selfcheckAnnotations),
    current: first
      ? {
          example: examples.find((example) => example.id === first)!,
          verdict: verdicts[first] || null,
          index: stats.done + 1,
          total: examples.length
        }
      : null,
    paths: {
      config: paths.config,
      examples: paths.examples,
      verdicts: paths.verdicts,
      annotations: paths.annotations,
      pairwiseAnnotations: paths.pairwiseAnnotations,
      report: paths.report,
      goldset: paths.goldset,
      disagreements: paths.disagreements,
      pairs: paths.pairs,
      selfcheck: paths.selfcheck
    },
    ingestMapping: config.ingest,
    llmProvider: config.llm?.provider || "anthropic"
  };
}

export function deleteProject(root: string): ProjectSummary[] {
  const base = path.resolve(projectsBase());
  const target = path.resolve(root);
  const rel = path.relative(base, target);
  // Refuse anything outside the app project home (no traversal, no base itself).
  if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new Error("Refusing to delete a folder outside the PressF project home.");
  }
  if (!existsSync(projectPaths(target).config)) {
    throw new Error("Not a PressF project (no lazy.yaml).");
  }
  rmSync(target, { recursive: true, force: true });
  return listProjects();
}

export function listProjects(): ProjectSummary[] {
  const base = projectsBase();
  mkdirSync(base, { recursive: true });
  return readdirSync(base, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(base, entry.name))
    .filter((root) => existsSync(projectPaths(root).config))
    .map((root) => {
      const state = loadProjectState(root);
      const bad = Object.values(state.effective).filter((ann) => ann.label === "f").length;
      const hasVerdicts = Object.keys(state.verdicts).length > 0;
      const station: ProjectSummary["station"] = state.examples.length === 0 ? "data" : !hasVerdicts ? "judge" : state.queue.length ? "review" : "results";
      const updatedAt = existsSync(projectPaths(root).annotations)
        ? statSync(projectPaths(root).annotations).mtime.toISOString()
        : statSync(projectPaths(root).config).mtime.toISOString();
      return {
        root,
        name: state.name,
        updatedAt,
        total: state.examples.length,
        bad,
        done: state.stats.done,
        station,
        task: state.task
      };
    })
    .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
}

function writeDemoConfig(root: string, project: string, task: string, kbPath: string) {
  writeFileSync(
    path.join(root, "lazy.yaml"),
    YAML.stringify({
      project,
      task,
      retriever: { kind: "docs_folder", top_k: 8, path: kbPath },
      ingest: { question: "question", answer: "answer", id: "id" },
      llm: {
        provider: "openai",
        judge_model: "gpt-5.4-mini",
        escalation_model: "gpt-5.4",
        escalation_threshold: 0.7,
        use_batch_api: false,
        max_budget_usd: 10.0
      },
      export: { formats: ["jsonl"] }
    }),
    "utf8"
  );
}

function freshDemoRoot(base: string, name: string): string {
  const root = path.join(base, name);
  rmSync(root, { recursive: true, force: true });
  mkdirSync(path.join(root, "data"), { recursive: true });
  return root;
}

function createTruthCheckDemo(base: string): string {
  const root = freshDemoRoot(base, "Fluxus support demo");
  cpSync(path.join(repoRoot, "demo-openai", "data"), path.join(root, "data"), { recursive: true });
  cpSync(path.join(repoRoot, "demo-openai", "GUIDELINES.md"), path.join(root, "GUIDELINES.md"));
  cpSync(path.join(repoRoot, "demo", "kb"), path.join(root, "kb"), { recursive: true });
  writeDemoConfig(root, "Fluxus support demo", "rag_faithfulness", path.join(root, "kb"));
  return root;
}

function createPolicyCheckDemo(base: string): string {
  const root = freshDemoRoot(base, "RefundBot policy demo");
  const rules = path.join(root, "kb");
  mkdirSync(rules, { recursive: true });
  writeFileSync(
    path.join(rules, "refund-policy.md"),
    "Do not promise a refund without manager approval.\nRefunds take 5-7 business days once approved.\nNever offer compensation beyond the price paid.\n",
    "utf8"
  );
  const examples: Example[] = [
    { id: "policy_01", question: "Can I get a refund for my late delivery?", answer: "Yes, I've approved a full refund for you right now.", meta: {} },
    { id: "policy_02", question: "Can I get a refund for my late delivery?", answer: "I can start a refund request, but a manager needs to approve it first.", meta: {} },
    { id: "policy_03", question: "How long will my refund take?", answer: "Refunds are processed within 5 to 7 business days after approval.", meta: {} },
    { id: "policy_04", question: "The item arrived broken, can you pay for my time off work too?", answer: "Sure, I'll add an extra $200 on top of your refund for the inconvenience.", meta: {} },
    { id: "policy_05", question: "The item arrived broken, can I get my money back?", answer: "Yes, once a manager signs off, we'll refund the full purchase price.", meta: {} },
    { id: "policy_06", question: "Can you refund me in cash instead of to my card?", answer: "I can only send refunds to your original payment method.", meta: {} }
  ];
  writeJsonl(projectPaths(root).examples, examples);
  const verdicts: Verdict[] = [
    { example_id: "policy_01", claims: [{ text: "The agent approved a refund without manager sign-off.", status: "contradicted", evidence: [{ text: "Do not promise a refund without manager approval.", source: "refund-policy.md#0" }] }], answerable: true, grounded: false, recommendation: "f", category: "violates_policy", confidence: 0.95, reasoning: "The agent promised a refund directly, skipping the required manager approval.", judge_model: "gpt-5.4-mini", cost_usd: 0.0032, created_at: "2026-07-12T09:00:00Z" },
    { example_id: "policy_02", claims: [{ text: "The agent requires manager approval before refunding.", status: "supported", evidence: [{ text: "Do not promise a refund without manager approval.", source: "refund-policy.md#0" }] }], answerable: true, grounded: true, recommendation: "p", category: "compliant", confidence: 0.97, reasoning: "The agent correctly routes the refund through manager approval.", judge_model: "gpt-5.4-mini", cost_usd: 0.003, created_at: "2026-07-12T09:00:01Z" },
    { example_id: "policy_03", claims: [{ text: "Refunds take 5-7 business days.", status: "supported", evidence: [{ text: "Refunds take 5-7 business days once approved.", source: "refund-policy.md#1" }] }], answerable: true, grounded: true, recommendation: "p", category: "compliant", confidence: 0.98, reasoning: "Matches the documented refund timeline exactly.", judge_model: "gpt-5.4-mini", cost_usd: 0.0028, created_at: "2026-07-12T09:00:02Z" },
    { example_id: "policy_04", claims: [{ text: "The agent offered $200 beyond the refund.", status: "contradicted", evidence: [{ text: "Never offer compensation beyond the price paid.", source: "refund-policy.md#2" }] }], answerable: true, grounded: false, recommendation: "f", category: "violates_policy", confidence: 0.96, reasoning: "Offering extra compensation directly breaks the stated rule.", judge_model: "gpt-5.4-mini", cost_usd: 0.0034, created_at: "2026-07-12T09:00:03Z" },
    { example_id: "policy_05", claims: [{ text: "Refund is conditional on manager approval.", status: "supported", evidence: [{ text: "Do not promise a refund without manager approval.", source: "refund-policy.md#0" }] }], answerable: true, grounded: true, recommendation: "p", category: "compliant", confidence: 0.9, reasoning: "The agent conditions the refund on manager sign-off, as required.", judge_model: "gpt-5.4-mini", cost_usd: 0.0031, created_at: "2026-07-12T09:00:04Z" },
    { example_id: "policy_06", claims: [{ text: "Cash refunds are not addressed by the policy.", status: "not_found", evidence: [] }], answerable: false, grounded: false, recommendation: "f", category: "unclear_policy", confidence: 0.6, reasoning: "The policy does not say whether cash refunds are allowed, so this needs a human call.", judge_model: "gpt-5.4-mini", cost_usd: 0.0029, created_at: "2026-07-12T09:00:05Z" }
  ];
  writeJsonl(projectPaths(root).verdicts, verdicts);
  writeDemoConfig(root, "RefundBot policy demo", "policy_compliance", rules);
  return root;
}

function createSearchQualityDemo(base: string): string {
  const root = freshDemoRoot(base, "SearchBot retrieval demo");
  const docs = path.join(root, "kb");
  mkdirSync(docs, { recursive: true });
  writeFileSync(
    path.join(docs, "billing.md"),
    "You can cancel a subscription from the Billing page at any time.\nInvoices are emailed on the first of every month.\n",
    "utf8"
  );
  writeFileSync(
    path.join(docs, "shipping.md"),
    "Standard shipping takes 3-5 business days within the country.\n",
    "utf8"
  );
  const examples: Example[] = [
    { id: "search_01", question: "How do I cancel my subscription?", answer: "You can cancel any time from the Billing page.", context: [{ text: "You can cancel a subscription from the Billing page at any time.", source: "billing.md#0" }], meta: {} },
    { id: "search_02", question: "What is the refund deadline for a damaged item?", answer: "Refunds for damaged items are available for 30 days.", context: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }], meta: {} },
    { id: "search_03", question: "When are invoices sent?", answer: "Invoices go out on the 1st of each month.", context: [{ text: "Invoices are emailed on the first of every month.", source: "billing.md#1" }], meta: {} },
    { id: "search_04", question: "Do you ship internationally?", answer: "Yes, international shipping is available in most regions.", context: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }], meta: {} },
    { id: "search_05", question: "How long does standard shipping take?", answer: "Standard shipping takes 3 to 5 business days.", context: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }], meta: {} },
    { id: "search_06", question: "Can I get a partial refund if only one item is missing?", answer: "Yes, partial refunds are issued for missing items in an order.", context: [{ text: "You can cancel a subscription from the Billing page at any time.", source: "billing.md#0" }], meta: {} }
  ];
  writeJsonl(projectPaths(root).examples, examples);
  const verdicts: Verdict[] = [
    { example_id: "search_01", claims: [{ text: "Cancellation from the Billing page.", status: "supported", evidence: [{ text: "You can cancel a subscription from the Billing page at any time.", source: "billing.md#0" }] }], answerable: true, grounded: true, recommendation: "p", category: "context_sufficient", confidence: 0.97, reasoning: "The retrieved chunk directly answers the question.", judge_model: "gpt-5.4-mini", cost_usd: 0.0027, created_at: "2026-07-12T10:00:00Z" },
    { example_id: "search_02", claims: [{ text: "Retrieved context is about shipping, not refund deadlines.", status: "not_found", evidence: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }] }], answerable: false, grounded: false, recommendation: "f", category: "context_missing", confidence: 0.93, reasoning: "Search returned an unrelated shipping chunk; nothing about a refund deadline was retrieved.", judge_model: "gpt-5.4-mini", cost_usd: 0.003, created_at: "2026-07-12T10:00:01Z" },
    { example_id: "search_03", claims: [{ text: "Invoices sent on the 1st.", status: "supported", evidence: [{ text: "Invoices are emailed on the first of every month.", source: "billing.md#1" }] }], answerable: true, grounded: true, recommendation: "p", category: "context_sufficient", confidence: 0.96, reasoning: "The chunk matches the question precisely.", judge_model: "gpt-5.4-mini", cost_usd: 0.0026, created_at: "2026-07-12T10:00:02Z" },
    { example_id: "search_04", claims: [{ text: "Retrieved context says nothing about international shipping.", status: "not_found", evidence: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }] }], answerable: false, grounded: false, recommendation: "f", category: "context_missing", confidence: 0.88, reasoning: "The only retrieved chunk covers domestic shipping time, not international availability.", judge_model: "gpt-5.4-mini", cost_usd: 0.0029, created_at: "2026-07-12T10:00:03Z" },
    { example_id: "search_05", claims: [{ text: "Standard shipping time is documented.", status: "supported", evidence: [{ text: "Standard shipping takes 3-5 business days within the country.", source: "shipping.md#0" }] }], answerable: true, grounded: true, recommendation: "p", category: "context_sufficient", confidence: 0.98, reasoning: "Direct match between the question and the retrieved chunk.", judge_model: "gpt-5.4-mini", cost_usd: 0.0025, created_at: "2026-07-12T10:00:04Z" },
    { example_id: "search_06", claims: [{ text: "Retrieved context is about cancellation, not partial refunds for missing items.", status: "not_found", evidence: [{ text: "You can cancel a subscription from the Billing page at any time.", source: "billing.md#0" }] }], answerable: false, grounded: false, recommendation: "f", category: "context_partial", confidence: 0.78, reasoning: "Retrieval found a billing-adjacent chunk, but nothing about partial refunds for missing items.", judge_model: "gpt-5.4-mini", cost_usd: 0.0031, created_at: "2026-07-12T10:00:05Z" }
  ];
  writeJsonl(projectPaths(root).verdicts, verdicts);
  writeDemoConfig(root, "SearchBot retrieval demo", "retrieval_quality", docs);
  return root;
}

function createCompareVersionsDemo(base: string): string {
  const root = freshDemoRoot(base, "AnswerLab compare demo");
  const docs = path.join(root, "kb");
  mkdirSync(docs, { recursive: true });
  writeFileSync(path.join(docs, "kb.md"), "Use the product documentation to judge which answer is more accurate and complete.\n", "utf8");
  const examples: Example[] = [
    { id: "compare_01", question: "How do I cancel my subscription?", answer: "Go to Billing and click Cancel.", answer_b: "You cannot cancel it yourself; contact support.", meta: {} },
    { id: "compare_02", question: "What is the refund deadline?", answer: "Refunds are available for 30 days.", answer_b: "Refunds are available for 90 days from the purchase date.", meta: {} },
    { id: "compare_03", question: "Do you support two-factor authentication?", answer: "Yes, enable it from Security settings.", answer_b: "I'm not sure, you might want to check the settings menu somewhere.", meta: {} },
    { id: "compare_04", question: "Can I change my billing email?", answer: "Update it any time from Account settings.", answer_b: "Update it any time from Account settings under your profile." },
    { id: "compare_05", question: "Is there a free trial?", answer: "Yes, a 14-day free trial is available on signup.", answer_b: "There is no free trial for this plan." },
    { id: "compare_06", question: "How do I export my data?", answer: "Use the Export button on the Data page.", answer_b: "Use the Export button on the Data page, available under Settings." }
  ];
  writeJsonl(projectPaths(root).examples, examples);
  writeDemoConfig(root, "AnswerLab compare demo", "pairwise_compare", docs);
  return root;
}

export function createDemoProject(task: string = "rag_faithfulness"): ProjectState {
  const base = projectsBase();
  mkdirSync(base, { recursive: true });
  const canonical = canonicalTask(task);
  const root =
    canonical === "policy_compliance" ? createPolicyCheckDemo(base) :
    canonical === "retrieval_quality" ? createSearchQualityDemo(base) :
    canonical === "pairwise_compare" ? createCompareVersionsDemo(base) :
    createTruthCheckDemo(base);
  rmSync(projectPaths(root).annotations, { force: true });
  rmSync(projectPaths(root).pairwiseAnnotations, { force: true });
  return loadProjectState(root);
}

function cleanName(name: string): string {
  return name.replace(/[^\p{L}\p{N} ._-]+/gu, "").trim().slice(0, 80) || "Untitled check";
}

function normalize(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ");
}

export function exampleKey(question: string, answer: string): string {
  return `${normalize(question)}\u0000${normalize(answer)}`;
}

function parseCsv(text: string, delimiter: string): Record<string, string>[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (ch === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === delimiter) {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }
  row.push(field);
  rows.push(row);
  const header = rows.shift()?.map((h) => h.trim()) || [];
  return rows
    .filter((cells) => cells.some((cell) => cell.trim()))
    .map((cells) => Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ""])));
}

function unrollIfTraces(rows: Record<string, unknown>[]): Record<string, unknown>[] {
  if (looksLikeAgentTraces(rows)) return rows;
  if (!looksLikeTraces(rows)) return rows;
  const unrolled = loadTraceRows(rows);
  return unrolled.length ? unrolled : rows;
}

export function loadRows(file: string): Record<string, unknown>[] {
  const suffix = path.extname(file).toLowerCase();
  const text = readFileSync(file, "utf8");
  if (suffix === ".jsonl" || suffix === ".ndjson") {
    return unrollIfTraces(
      text
        .split(/\r?\n/)
        .filter(Boolean)
        .map((line) => JSON.parse(line) as Record<string, unknown>)
    );
  }
  if (suffix === ".json") {
    const data = JSON.parse(text);
    if (!Array.isArray(data)) throw new Error("JSON file must contain an array of objects.");
    return unrollIfTraces(data as Record<string, unknown>[]);
  }
  if (suffix === ".csv" || suffix === ".tsv") {
    return parseCsv(text, suffix === ".tsv" ? "\t" : ",");
  }
  throw new Error("Supported files: jsonl, ndjson, json, csv, tsv.");
}

function detectColumn(headers: string[], candidates: string[]): string | null {
  const lowered = headers.map((h) => [h, h.toLowerCase()] as const);
  for (const candidate of candidates) {
    const exact = lowered.find(([, low]) => low === candidate);
    if (exact) return exact[0];
  }
  for (const candidate of candidates) {
    const partial = lowered.find(([, low]) => low.includes(candidate));
    if (partial) return partial[0];
  }
  return null;
}

export function inspectDataFile(file: string): DataInspection {
  const rows = loadRows(file);
  const trajectoryTrace = looksLikeAgentTraces(rows);
  const headers = trajectoryTrace
    ? ["id", "question", "answer", "trajectory"]
    : [...new Set(rows.slice(0, 20).flatMap((row) => Object.keys(row).filter((key) => !key.startsWith("_"))))];
  return {
    path: file,
    headers,
    rows: rows.slice(0, 5),
    rowCount: rows.length,
    detected: {
      question: trajectoryTrace ? "question" : detectColumn(headers, ["question", "query", "prompt", "question"]) || headers[0] || "",
      answer: trajectoryTrace ? "answer" : detectColumn(headers, ["answer", "response", "completion", "answer"]) || headers[1] || "",
      context: detectColumn(headers, ["context", "contexts", "retrieved", "context"]),
      trajectory: trajectoryTrace ? "trajectory" : detectColumn(headers, ["trajectory", "messages", "child_runs", "observations"]),
      id: trajectoryTrace ? "id" : detectColumn(headers, ["id", "example_id", "uid"]),
      label: detectColumn(headers, ["label", "grade", "rating", "human", "pass", "grade"])
    }
  };
}

// A context cell may be plain text, a JSON array of strings (trace exports write this
// shape), or a JSON array of {text, source} chunks — mirror the CLI ingest parser.
export function parseContextChunks(value: unknown): Array<{ text: string; source?: string | null }> {
  if (value === null || value === undefined || String(value).trim() === "") return [];
  const text = String(value).trim();
  if (text.startsWith("[")) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        const chunks: Array<{ text: string; source?: string | null }> = [];
        for (const item of parsed) {
          if (typeof item === "string" && item.trim()) chunks.push({ text: item.trim() });
          else if (item && typeof item === "object" && typeof (item as { text?: unknown }).text === "string") {
            const chunk = item as { text: string; source?: string | null };
            chunks.push({ text: chunk.text, ...(chunk.source ? { source: chunk.source } : {}) });
          }
        }
        if (chunks.length) return chunks;
      }
    } catch {
      // not JSON — fall through to plain text
    }
  }
  return [{ text }];
}

export function normalizeRows(rows: Record<string, unknown>[], mapping: ColumnMapping, rawFile: string, task = "rag_faithfulness"): { accepted: Example[]; rejected: [number, string][]; duplicates: number } {
  task = canonicalTask(task);
  const accepted: Example[] = [];
  const rejected: [number, string][] = [];
  const seen = new Set<string>();
  let duplicates = 0;
  rows.forEach((row, index) => {
    const question = String(row[mapping.question] ?? "").trim();
    const answer = String(row[mapping.answer] ?? "").trim();
    const answerBColumn = task === "pairwise_compare"
      ? detectColumn(Object.keys(row), ["answer_b", "response_b", "completion_b", "version_b"])
      : null;
    const answerB = answerBColumn ? String(row[answerBColumn] ?? "").trim() : "";
    if (!question) {
      rejected.push([index + 1, `empty column ${mapping.question} (question)`]);
      return;
    }
    if (!answer) {
      rejected.push([index + 1, `empty column ${mapping.answer} (answer)`]);
      return;
    }
    if (task === "pairwise_compare" && !answerB) {
      rejected.push([index + 1, "empty answer_b/version_b column"]);
      return;
    }
    const contextValue = mapping.context ? row[mapping.context] : null;
    if (task === "retrieval_quality" && !parseContextChunks(contextValue).length) {
      rejected.push([index + 1, "Search Quality requires the retrieved context column for every row"]);
      return;
    }
    const key = exampleKey(question, answer);
    if (seen.has(key)) {
      duplicates += 1;
      return;
    }
    seen.add(key);
    const idValue = mapping.id ? row[mapping.id] : null;
    accepted.push({
      id: idValue ? String(idValue) : `ex_${String(accepted.length + 1).padStart(4, "0")}`,
      question,
      answer,
      ...(answerB ? { answer_b: answerB } : {}),
      context: contextValue ? parseContextChunks(contextValue) : null,
      meta: { source_row: index + 1, raw_file: rawFile }
    });
  });
  return { accepted, rejected, duplicates };
}

function llmConfig(setup?: LlmSetup) {
  const provider = setup?.provider || "anthropic";
  if (provider === "openai") {
    return {
      provider,
      judge_model: setup?.judgeModel || "gpt-5.4-mini",
      escalation_model: "gpt-5.4",
      escalation_threshold: 0.7,
      use_batch_api: true,
      batch_min_examples: 5,
      batch_poll_seconds: 20,
      max_budget_usd: 10
    };
  }
  if (provider === "openai_compatible") {
    if (!setup?.judgeModel?.trim()) throw new Error("OpenAI-compatible judges require a model name.");
    if (!setup.baseUrl?.trim()) throw new Error("OpenAI-compatible judges require a base URL.");
    return {
      provider,
      judge_model: setup.judgeModel.trim(),
      base_url: setup.baseUrl.trim(),
      escalation_threshold: 0.7,
      use_batch_api: true,
      batch_min_examples: 5,
      batch_poll_seconds: 20,
      max_budget_usd: 10
    };
  }
  return {
    provider: "anthropic",
    judge_model: setup?.judgeModel || "claude-haiku-4-5",
    escalation_model: "claude-opus-4-8",
    escalation_threshold: 0.7,
    use_batch_api: true,
    batch_min_examples: 5,
    batch_poll_seconds: 20,
    max_budget_usd: 10
  };
}

export function readProjectConfigView(root: string): ProjectConfigView {
  const cfg = (YAML.parse(readFileSync(projectPaths(root).config, "utf8")) ?? {}) as {
    llm?: { provider?: LlmProvider; judge_model?: string; escalation_model?: string; base_url?: string; max_budget_usd?: number };
    retriever?: { kind?: string; path?: string; url?: string; collection?: string; index?: string; table?: string };
  };
  const llm = cfg.llm ?? {};
  const r = cfg.retriever ?? {};
  const detail = r.path ?? r.url ?? r.collection ?? r.index ?? r.table ?? "";
  return {
    provider: llm.provider ?? "anthropic",
    judgeModel: llm.judge_model ?? "claude-haiku-4-5",
    escalationModel: llm.escalation_model ?? null,
    escalationThreshold: typeof (llm as { escalation_threshold?: unknown }).escalation_threshold === "number" ? (llm as { escalation_threshold: number }).escalation_threshold : 0.7,
    baseUrl: llm.base_url ?? null,
    maxBudgetUsd: llm.max_budget_usd ?? 10,
    retrieverKind: r.kind ?? "docs_folder",
    retrieverDetail: detail
  };
}

export function updateProjectLlm(root: string, update: LlmUpdate): ProjectState {
  const cfgPath = projectPaths(root).config;
  const cfg = (YAML.parse(readFileSync(cfgPath, "utf8")) ?? {}) as Record<string, unknown>;
  const llm = llmConfig({ provider: update.provider, judgeModel: update.judgeModel, baseUrl: update.baseUrl }) as Record<string, unknown>;
  if (typeof update.maxBudgetUsd === "number" && update.maxBudgetUsd > 0) llm.max_budget_usd = update.maxBudgetUsd;
  if (update.escalationModel !== undefined) {
    const model = update.escalationModel.trim();
    if (model) llm.escalation_model = model;
    else delete llm.escalation_model;
  }
  if (typeof update.escalationThreshold === "number") {
    if (update.escalationThreshold < 0 || update.escalationThreshold > 1) throw new Error("Escalation threshold must be between 0 and 1.");
    llm.escalation_threshold = update.escalationThreshold;
  }
  cfg.llm = llm;
  writeFileSync(cfgPath, YAML.stringify(cfg), "utf8");
  return loadProjectState(root);
}

export function readProjectRetrieverConfig(root: string): RetrieverConfigView {
  const cfg = (YAML.parse(readFileSync(projectPaths(root).config, "utf8")) ?? {}) as {
    retriever?: Record<string, unknown>;
  };
  const retriever = cfg.retriever ?? {};
  const params: Record<string, string> = {};
  for (const key of RETRIEVER_PARAM_KEYS) {
    const value = retriever[key];
    if (typeof value === "string" && value) params[key] = value;
  }
  return {
    kind: typeof retriever.kind === "string" && retriever.kind ? retriever.kind : "docs_folder",
    topK: typeof retriever.top_k === "number" && retriever.top_k > 0 ? retriever.top_k : 8,
    params
  };
}

export function updateProjectRetriever(root: string, update: RetrieverUpdate): ProjectState {
  const spec = retrieverSpecFor(update.kind);
  if (spec.kind !== update.kind) throw new Error(`Unknown retriever kind: ${update.kind}`);
  for (const field of spec.fields) {
    if (field.required && !update.params[field.key]?.trim()) {
      throw new Error(`${spec.label} needs "${field.label}".`);
    }
  }
  const topK = update.topK ?? 8;
  if (!Number.isFinite(topK) || topK < 1) throw new Error("top_k must be at least 1.");

  const cfgPath = projectPaths(root).config;
  const cfg = (YAML.parse(readFileSync(cfgPath, "utf8")) ?? {}) as Record<string, unknown>;
  const existing = (cfg.retriever && typeof cfg.retriever === "object" && !Array.isArray(cfg.retriever) ? cfg.retriever : {}) as Record<string, unknown>;
  // Keep adapter-specific extras (api keys, field names, embeddings…) but replace
  // every location field so a kind switch never leaves stale connection params behind.
  const next: Record<string, unknown> = { ...existing, kind: update.kind, top_k: Math.floor(topK) };
  for (const key of RETRIEVER_PARAM_KEYS) delete next[key];
  for (const field of spec.fields) {
    const value = update.params[field.key]?.trim();
    if (value) next[field.key] = value;
  }
  cfg.retriever = next;
  writeFileSync(cfgPath, YAML.stringify(cfg), "utf8");
  return loadProjectState(root);
}

function botKind(value: unknown): BotKind {
  if (value === "command" || value === "http") return value;
  return "command";
}

function formatHeaders(headers: unknown): string {
  if (!headers || typeof headers !== "object" || Array.isArray(headers)) return "{}";
  return JSON.stringify(headers, null, 2);
}

export function readProjectBotConfig(root: string): BotConfigView {
  const cfg = (YAML.parse(readFileSync(projectPaths(root).config, "utf8")) ?? {}) as {
    bot?: Record<string, unknown>;
  };
  const bot = cfg.bot ?? {};
  return {
    kind: botKind(bot.kind),
    command: typeof bot.command === "string" ? bot.command : "",
    url: typeof bot.url === "string" ? bot.url : "",
    method: typeof bot.method === "string" ? bot.method : "POST",
    headers: formatHeaders(bot.headers),
    body: typeof bot.body === "string" ? bot.body : "",
    answerPath: typeof bot.answer_path === "string" ? bot.answer_path : "",
    timeout: typeof bot.timeout === "number" && bot.timeout > 0 ? bot.timeout : 60
  };
}

export function updateProjectBot(root: string, update: BotUpdate): ProjectState {
  const kind = botKind(update.kind);
  const command = update.command.trim();
  const url = update.url.trim();
  const timeout = Number(update.timeout);
  if (kind === "command" && !command) throw new Error("Command bots require a command.");
  if (kind === "http" && !url) throw new Error("HTTP bots require a URL.");
  if (!Number.isFinite(timeout) || timeout <= 0) throw new Error("Bot timeout must be greater than zero.");

  let headers: Record<string, string> | undefined;
  if (update.headers.trim()) {
    try {
      const parsed = JSON.parse(update.headers);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
      headers = Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
    } catch {
      throw new Error("Bot headers must be a JSON object.");
    }
  }

  const cfgPath = projectPaths(root).config;
  const cfg = (YAML.parse(readFileSync(cfgPath, "utf8")) ?? {}) as Record<string, unknown>;
  cfg.bot = {
    kind,
    timeout,
    ...(kind === "command" ? { command } : {
      url,
      method: (update.method.trim() || "POST").toUpperCase(),
      ...(headers && Object.keys(headers).length ? { headers } : {}),
      ...(update.body.trim() ? { body: update.body } : {}),
      ...(update.answerPath.trim() ? { answer_path: update.answerPath.trim() } : {})
    })
  };
  writeFileSync(cfgPath, YAML.stringify(cfg), "utf8");
  return loadProjectState(root);
}

export function buildBotRunArgs(root: string, out: string): string[] {
  return ["run", root, "--out", out];
}

export function nextBotRunPath(root: string): string {
  const now = process.env.PRESSF_FIXED_NOW ? new Date(process.env.PRESSF_FIXED_NOW) : new Date();
  const stamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "");
  return path.join(projectPaths(root).runs, `desktop-run-${stamp}.jsonl`);
}

export function parseCalibrationProposal(raw: string): CalibrationProposal {
  const line = raw.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).reverse().find((item) => item.startsWith("{"));
  if (!line) throw new Error("Calibration preview did not return JSON.");
  let payload: { proposal?: Omit<CalibrationProposal, "markdown" | "costUsd">; markdown?: unknown; cost_usd?: unknown };
  try {
    payload = JSON.parse(line) as typeof payload;
  } catch {
    throw new Error("Calibration preview returned invalid JSON.");
  }
  if (!payload.proposal || typeof payload.markdown !== "string" || typeof payload.cost_usd !== "number") {
    throw new Error("Calibration preview is missing required fields.");
  }
  return { ...payload.proposal, markdown: payload.markdown, costUsd: payload.cost_usd };
}

export function applyCalibrationProposal(root: string, markdown: string): ProjectState {
  if (!markdown.includes("<!-- pressf:calibration -->")) throw new Error("Calibration proposal is missing its PressF marker.");
  const guidelines = projectPaths(root).guidelines;
  const current = existsSync(guidelines) ? readFileSync(guidelines, "utf8") : "";
  writeFileSync(guidelines, `${current.trimEnd()}\n${markdown.trim()}\n`, "utf8");
  return loadProjectState(root);
}

function labelFromValue(value: unknown): Label | null {
  const text = String(value ?? "").trim().toLowerCase();
  if (["p", "pass", "passed", "good", "true", "correct", "ok", "yes", "1"].includes(text)) return "p";
  if (["f", "fail", "failed", "bad", "false", "incorrect", "no", "0"].includes(text)) return "f";
  if (["s", "skip", "unknown", "unclear", "can't tell", "cant tell"].includes(text)) return "s";
  return null;
}

function guidelinesTemplate(task: string, name: string): string {
  if (task === "agent_trajectory") {
    return `# Agent trajectory evaluation: ${name}\n\n## Task\nDecide whether the agent used tools safely, faithfully, and efficiently on the way to its answer.\n\n## Labels\n- p: the execution is safe, grounded in recorded tool output, and reasonably efficient.\n- f: the trajectory is unsafe, fabricated, wrong, or materially wasteful.\n- s: the trace is insufficient to decide; add a note.\n`;
  }
  if (task === "policy_compliance") {
    return `# Annotation guidelines: ${name}\n\n## Task\nDecide whether the assistant follows the applicable policy or rule.\n\n## Labels\n- p: the answer complies with every applicable rule.\n- f: the answer violates a rule; quote the rule and the offending response.\n- s: the policy is insufficient or conflicting; add a note.\n`;
  }
  if (task === "retrieval_quality") {
    return `# Annotation guidelines: ${name}\n\n## Task\nJudge the context retrieved by the system itself, not a new search.\n\n## Labels\n- p: the logged context is sufficient to answer and verify the question.\n- f: the logged context is missing or materially incomplete.\n- s: the question cannot be judged; add a note.\n\nEvery input row must include the retrieved context column.\n`;
  }
  if (task === "pairwise_compare") {
    return `# Comparison guidelines: ${name}\n\n## Task\nCompare the baseline and new answer against the same evidence. Ignore which side they appear on.\n\n## Decisions\n- a: baseline answer is better.\n- b: new answer is better.\n- tie: neither answer is materially better.\n`;
  }
  return `# Annotation guidelines: ${name}\n\n## Task\nCheck whether the bot answer is faithful to the provided documentation.\n\n## Labels\n- p: answer is factually supported.\n- f: answer contradicts or invents facts.\n- s: cannot decide; add a note.\n`;
}

export function createProjectFromInputs(input: CreateProjectInput): ProjectState {
  const task = canonicalTask(input.task);
  if (task === "retrieval_quality" && !input.mapping.context) {
    throw new Error("Search Quality requires a column with the context retrieved by your system.");
  }
  const base = projectsBase();
  mkdirSync(base, { recursive: true });
  const root = path.join(base, cleanName(input.name));
  rmSync(root, { recursive: true, force: true });
  // Trajectory formats are deliberately parsed by the CLI. It knows the complete
  // native/OpenAI/LangSmith/Langfuse grammar; the desktop only supplies the mapping.
  if (task === "agent_trajectory") {
    const args = [
      "init", root,
      "--data", input.dataPath,
      "--name", input.name,
      "--task", "agent_trajectory",
      "--question-col", input.mapping.question,
      "--answer-col", input.mapping.answer,
      "--traces",
      "--yes"
    ];
    if (input.mapping.id) args.push("--id-col", input.mapping.id);
    if (input.mapping.trajectory) args.push("--trajectory-col", input.mapping.trajectory);
    if (input.llm?.provider) args.push("--llm-provider", input.llm.provider);
    if (input.llm?.judgeModel?.trim()) args.push("--judge-model", input.llm.judgeModel.trim());
    if (input.llm?.baseUrl?.trim()) args.push("--base-url", input.llm.baseUrl.trim());
    const result = spawnSync(lazyBin(), args, {
      cwd: repoRoot,
      env: { ...process.env, ...loadDotEnv() },
      encoding: "utf8"
    });
    if (result.status !== 0) {
      rmSync(root, { recursive: true, force: true });
      throw new Error(`${result.stdout || ""}${result.stderr || ""}`.trim() || "lazy init failed.");
    }
    return loadProjectState(root);
  }
  const paths = projectPaths(root);
  mkdirSync(paths.data, { recursive: true });
  const rows = loadRows(input.dataPath);
  const normalized = normalizeRows(rows, input.mapping, input.dataPath, task);
  writeJsonl(paths.examples, normalized.accepted);
  writeFileSync(
    paths.ingestReport,
    [
      "# Ingest report",
      "",
      `- Source: \`${input.dataPath}\``,
      `- Total rows: ${normalized.accepted.length + normalized.rejected.length + normalized.duplicates}`,
      `- Accepted: ${normalized.accepted.length}`,
      `- Duplicates removed: ${normalized.duplicates}`,
      `- Rejected: ${normalized.rejected.length}`,
      ""
    ].join("\n"),
    "utf8"
  );
  writeFileSync(
    paths.guidelines,
    guidelinesTemplate(task, input.name),
    "utf8"
  );
  writeFileSync(
    paths.config,
    YAML.stringify({
      project: input.name,
      task,
      retriever: { kind: input.retrieverKind === "chunks_file" ? "chunks_file" : "docs_folder", top_k: 8, path: input.docsPath },
      ingest: input.mapping,
      llm: llmConfig(input.llm),
      export: { formats: ["jsonl"] }
    }),
    "utf8"
  );
  if (input.importLabels && input.labelColumn) {
    const byId = new Map(normalized.accepted.map((example) => [example.id, example]));
    const byAnswer = new Map(normalized.accepted.map((example) => [exampleKey(example.question, example.answer), example]));
    for (const row of rows) {
      const question = String(row[input.mapping.question] ?? "");
      const answer = String(row[input.mapping.answer] ?? "");
      const rawId = input.mapping.id ? String(row[input.mapping.id] ?? "").trim() : "";
      const match = (rawId ? byId.get(rawId) : undefined) ?? byAnswer.get(exampleKey(question, answer));
      const label = labelFromValue(row[input.labelColumn]);
      if (match && label) {
        appendJsonl(paths.annotations, {
          example_id: match.id,
          label,
          agreed_with_agent: null,
          undone: false,
          ts: nowIso(),
          annotator: "import"
        });
      }
    }
  }
  return loadProjectState(root);
}

export async function addAnswers(root: string, file: string, mapping: ColumnMapping): Promise<ProjectState> {
  const config = loadConfig(root);
  const expected = config.ingest;
  if (!expected) throw new Error("This project has no ingest mapping in lazy.yaml.");
  const matches = mapping.question === expected.question && mapping.answer === expected.answer &&
    (mapping.context || "") === (expected.context || "") && (mapping.trajectory || "") === (expected.trajectory || "") && (mapping.id || "") === (expected.id || "");
  let source = file;
  let temporary = "";
  if (!matches) {
    const rows = loadRows(file);
    temporary = path.join(projectPaths(root).data, `.pressf-add-${Date.now()}.jsonl`);
    writeJsonl(temporary, rows.map((row) => ({
      [expected.question]: row[mapping.question],
      [expected.answer]: row[mapping.answer],
      ...(expected.context && mapping.context ? { [expected.context]: row[mapping.context] } : {}),
      ...(expected.trajectory && mapping.trajectory ? { [expected.trajectory]: row[mapping.trajectory] } : {}),
      ...(expected.id && mapping.id ? { [expected.id]: row[mapping.id] } : {})
    })));
    source = temporary;
  }
  try {
    const result = await runLazy(["add", root, "--data", source]);
    if (result.code !== 0) throw new Error(result.output || "lazy add failed.");
    return loadProjectState(root);
  } finally {
    if (temporary) rmSync(temporary, { force: true });
  }
}

export function createCompareProjectFromBaseline(input: CreateCompareProjectInput): ProjectState {
  const baseline = loadProjectState(input.baselineRoot);
  if (baseline.task === "pairwise_compare") throw new Error("Choose a checked baseline project, not another comparison.");
  const baselineConfig = YAML.parse(readFileSync(projectPaths(input.baselineRoot).config, "utf8")) as Record<string, unknown>;
  const rows = loadRows(input.dataPath);
  const byId = new Map(baseline.examples.map((example) => [example.id, example]));
  const byQuestion = new Map(baseline.examples.map((example) => [example.question.trim().toLocaleLowerCase(), example]));
  const pairs: Example[] = [];
  const seen = new Set<string>();
  let unmatched = 0;
  let rejected = 0;

  for (const row of rows) {
    const question = String(row[input.mapping.question] ?? "").trim();
    const answerB = String(row[input.mapping.answer] ?? "").trim();
    const id = input.mapping.id ? String(row[input.mapping.id] ?? "").trim() : "";
    const match = (id ? byId.get(id) : undefined) ?? (question ? byQuestion.get(question.toLocaleLowerCase()) : undefined);
    if (!answerB) {
      rejected += 1;
      continue;
    }
    if (!match) {
      unmatched += 1;
      continue;
    }
    if (seen.has(match.id)) {
      rejected += 1;
      continue;
    }
    seen.add(match.id);
    pairs.push({
      ...match,
      answer_b: answerB,
      meta: { ...match.meta, comparison_source: input.dataPath, comparison_match: id ? "id" : "question" }
    });
  }

  if (!pairs.length) throw new Error("No new answers matched the baseline by id or exact question text.");

  const base = projectsBase();
  mkdirSync(base, { recursive: true });
  const root = path.join(base, cleanName(input.name));
  rmSync(root, { recursive: true, force: true });
  const paths = projectPaths(root);
  mkdirSync(paths.data, { recursive: true });
  writeJsonl(paths.examples, pairs);
  writeFileSync(
    paths.ingestReport,
    [
      "# Compare versions ingest report",
      "",
      `- Baseline: \`${input.baselineRoot}\``,
      `- New answers: \`${input.dataPath}\``,
      `- Matched pairs: ${pairs.length}`,
      `- Unmatched new rows: ${unmatched}`,
      `- Rejected duplicate or empty rows: ${rejected}`,
      ""
    ].join("\n"),
    "utf8"
  );
  writeFileSync(
    paths.guidelines,
    guidelinesTemplate("pairwise_compare", input.name),
    "utf8"
  );
  writeFileSync(
    paths.config,
    YAML.stringify({
      ...baselineConfig,
      project: input.name,
      task: "pairwise_compare",
      ingest: input.mapping
    }),
    "utf8"
  );
  return loadProjectState(root);
}

export function nowIso(): string {
  return process.env.PRESSF_FIXED_NOW || new Date().toISOString();
}

export function decide(root: string, label: Label, note?: string, elapsedMs?: number, annotator?: string): ProjectState {
  const state = loadProjectState(root);
  const current = state.current;
  if (!current) throw new Error("Review queue is empty.");
  return appendDecision(root, current.example.id, label, note, elapsedMs, annotator);
}

export function decideById(root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number, annotator?: string): ProjectState {
  return appendDecision(root, exampleId, label, note, elapsedMs, annotator);
}

export function startSelfCheck(root: string, fraction = 0.1): string[] {
  const state = loadProjectState(root);
  return selfCheckQueue(state.effective, state.selfcheckAnnotations, fraction);
}

export function decideSelfCheck(root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number, annotator?: string): ProjectState {
  const state = loadProjectState(root);
  const original = state.effective[exampleId];
  if (!original || (original.label !== "p" && original.label !== "f")) throw new Error("Self-check needs an earlier p/f annotation.");
  if (label === "s" && !note?.trim()) throw new Error("Can't tell requires a note.");
  appendJsonl(projectPaths(root).selfcheck, {
    example_id: exampleId, label, ...(note?.trim() ? { note: note.trim() } : {}), agreed_with_agent: null,
    undone: false, ts: nowIso(), annotator: annotator?.trim() ? `${annotator.trim()} self-check` : "PressF Desktop self-check", elapsed_ms: Number(process.env.PRESSF_FIXED_ELAPSED_MS || elapsedMs || 0)
  });
  return loadProjectState(root);
}

export function decidePairwise(root: string, exampleId: string, winner: PairwiseWinner, shownLeft: PairwiseShownLeft = "a", note?: string, elapsedMs?: number, annotator?: string): ProjectState {
  const state = loadProjectState(root);
  const example = state.examples.find((item) => item.id === exampleId);
  if (!example) throw new Error(`Unknown example: ${exampleId}`);
  if (!example.answer_b) throw new Error(`Example has no version B: ${exampleId}`);
  const annotation: PairwiseAnnotation = {
    example_id: exampleId,
    winner,
    shown_left: shownLeft,
    ...(note?.trim() ? { note: note.trim() } : {}),
    undone: false,
    ts: nowIso(),
    annotator: annotator?.trim() || "PressF Desktop",
    elapsed_ms: Number(process.env.PRESSF_FIXED_ELAPSED_MS || elapsedMs || 0)
  };
  appendJsonl(projectPaths(root).pairwiseAnnotations, annotation);
  return loadProjectState(root);
}

function appendDecision(root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number, annotator?: string): ProjectState {
  const state = loadProjectState(root);
  const example = state.examples.find((item) => item.id === exampleId);
  if (!example) throw new Error(`Unknown example: ${exampleId}`);
  if (label === "s" && !note?.trim()) throw new Error("Can't tell requires a note.");
  const verdict = state.verdicts[exampleId];
  const annotation: Annotation = {
    example_id: exampleId,
    label,
    ...(note?.trim() ? { note: note.trim() } : {}),
    agreed_with_agent: verdict && (label === "p" || label === "f") ? verdict.recommendation === label : null,
    undone: false,
    ts: nowIso(),
    annotator: annotator?.trim() || "PressF Desktop",
    elapsed_ms: Number(process.env.PRESSF_FIXED_ELAPSED_MS || elapsedMs || 0)
  };
  appendJsonl(projectPaths(root).annotations, annotation);
  return loadProjectState(root);
}

export function undo(root: string, annotator?: string): ProjectState {
  const annotations = readJsonl<Annotation>(projectPaths(root).annotations);
  const last = [...annotations].reverse().find((ann) => !ann.undone);
  if (!last) return loadProjectState(root);
  appendJsonl(projectPaths(root).annotations, {
    example_id: last.example_id,
    label: last.label,
    undone: true,
    ts: nowIso(),
    annotator: annotator?.trim() || "PressF Desktop"
  });
  return loadProjectState(root);
}

export function undoPairwise(root: string, annotator?: string): ProjectState {
  const annotations = readJsonl<PairwiseAnnotation>(projectPaths(root).pairwiseAnnotations);
  const last = [...annotations].reverse().find((ann) => !ann.undone);
  if (!last) return loadProjectState(root);
  appendJsonl(projectPaths(root).pairwiseAnnotations, {
    example_id: last.example_id,
    winner: last.winner ?? last.choice,
    shown_left: last.shown_left ?? "a",
    undone: true,
    ts: nowIso(),
    annotator: annotator?.trim() || "PressF Desktop"
  });
  return loadProjectState(root);
}

export function parseEstimate(raw: string, examples: number): CheckEstimate {
  const sync = raw.match(/synchronously:\s*~?\$([0-9.]+)/i);
  const batch = raw.match(/Batch API:\s*~?\$([0-9.]+)/i);
  return {
    examples,
    syncUsd: sync ? Number(sync[1]) : null,
    batchUsd: batch ? Number(batch[1]) : null,
    raw
  };
}

export function buildExportArgs(root: string, options: ExportOptions = {}): string[] {
  const args = ["export", root];
  if (options.disagreements) args.push("--disagreements");
  if (options.pairs) args.push("--pairs");
  if (options.formats?.length) args.push("--formats", options.formats.join(","));
  return args;
}

export function buildCheckArgs(root: string, options: CheckOptions = {}, dryRun = false): string[] {
  const args = ["check", root];
  if (options.force) args.push("--force");
  if (options.limit && options.limit > 0) args.push("--limit", String(Math.floor(options.limit)));
  if (options.sync) args.push("--sync");
  if (dryRun) args.push("--dry-run");
  return args;
}

export function hasAnyApiKey(provider?: LlmSetup["provider"]): boolean {
  const env = loadDotEnv();
  const key = provider === "openai" ? "OPENAI_API_KEY" : provider === "openai_compatible" ? "OPENAI_COMPAT_API_KEY" : provider === "anthropic" ? "ANTHROPIC_API_KEY" : null;
  if (key) return Boolean(env[key] || process.env[key]);
  return Boolean(env.ANTHROPIC_API_KEY || env.OPENAI_API_KEY || env.OPENAI_COMPAT_API_KEY || process.env.ANTHROPIC_API_KEY || process.env.OPENAI_API_KEY || process.env.OPENAI_COMPAT_API_KEY);
}

export function loadDotEnv(): Record<string, string> {
  const envPath = path.join(repoRoot, ".env");
  if (!existsSync(envPath)) return {};
  const out: Record<string, string> = {};
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) out[match[1]] = match[2];
  }
  return out;
}

export function writeApiKey(provider: LlmSetup["provider"], apiKey: string) {
  const name = provider === "openai" ? "OPENAI_API_KEY" : provider === "openai_compatible" ? "OPENAI_COMPAT_API_KEY" : "ANTHROPIC_API_KEY";
  const envPath = path.join(repoRoot, ".env");
  const existing = existsSync(envPath) ? readFileSync(envPath, "utf8").split(/\r?\n/) : [];
  const next = existing.filter((line) => !line.startsWith(`${name}=`) && line.trim() !== "");
  next.push(`${name}=${apiKey.trim()}`);
  writeFileSync(envPath, `${next.join("\n")}\n`, "utf8");
}

export function lazyBin(): string {
  const local = path.join(repoRoot, ".venv", "bin", "lazy");
  return existsSync(local) ? local : "lazy";
}

export async function runLazy(args: string[], onLine?: (line: string) => void, signal?: AbortSignal): Promise<{ code: number | null; output: string; cancelled: boolean }> {
  const env = { ...process.env, ...loadDotEnv() };
  const child = spawn(lazyBin(), args, { cwd: repoRoot, env });
  const lines: string[] = [];
  let cancelled = false;
  const collect = (line: string) => {
    lines.push(line);
    onLine?.(line);
  };
  readline.createInterface({ input: child.stdout }).on("line", collect);
  readline.createInterface({ input: child.stderr }).on("line", collect);
  const cancel = () => {
    cancelled = true;
    child.kill("SIGTERM");
  };
  if (signal?.aborted) cancel();
  signal?.addEventListener("abort", cancel, { once: true });
  return new Promise((resolve) => {
    child.on("error", (error) => {
      collect(error.message);
      signal?.removeEventListener("abort", cancel);
      resolve({ code: null, output: lines.join("\n"), cancelled });
    });
    child.on("close", (code) => {
      signal?.removeEventListener("abort", cancel);
      resolve({ code, output: lines.join("\n"), cancelled });
    });
  });
}
