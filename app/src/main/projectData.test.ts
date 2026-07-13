import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { addAnswers, applyCalibrationProposal, buildBotRunArgs, buildCheckArgs, buildExportArgs, createCompareProjectFromBaseline, createDemoProject, createProjectFromInputs, decide, decidePairwise, decideSelfCheck, inspectDataFile, listProjects, loadEffectiveAnnotations, loadProjectState, deleteProject, parseCalibrationProposal, parseEstimate, projectsBase, readProjectBotConfig, readProjectConfigView, readProjectRetrieverConfig, updateProjectBot, updateProjectLlm, updateProjectRetriever, selfCheckQueue, selfCheckStatsFor, undo, undoPairwise } from "./projectData.js";

let tempHome = "";

beforeEach(() => {
  tempHome = mkdtempSync(path.join(tmpdir(), "pressf-unit-"));
  process.env.PRESSF_HOME = tempHome;
  process.env.PRESSF_FIXED_NOW = "2026-07-12T00:00:00.000Z";
  process.env.PRESSF_FIXED_ELAPSED_MS = "1234";
});

afterEach(() => {
  delete process.env.PRESSF_HOME;
  delete process.env.PRESSF_FIXED_NOW;
  delete process.env.PRESSF_FIXED_ELAPSED_MS;
  rmSync(tempHome, { recursive: true, force: true });
});

describe("PressF Desktop project data", () => {
  it("copies the demo into the app project home and resumes doubtful cards first", () => {
    const state = createDemoProject();
    expect(state.root.startsWith(projectsBase())).toBe(true);
    expect(state.examples).toHaveLength(8);
    expect(state.current?.example.id).toBe("demo_05");
  });

  it("appends decisions in the CLI-compatible annotation log and undoes by append event", () => {
    const state = createDemoProject();
    const next = decide(state.root, "p", undefined, 55);
    expect(next.stats.done).toBe(1);
    expect(next.stats.agreement).toBe(0);

    const line = readFileSync(path.join(state.root, "data", "annotations.jsonl"), "utf8").trim();
    expect(line).toBe(
      '{"example_id":"demo_05","label":"p","agreed_with_agent":false,"undone":false,"ts":"2026-07-12T00:00:00.000Z","annotator":"PressF Desktop","elapsed_ms":1234}'
    );

    const undone = undo(state.root);
    expect(undone.stats.done).toBe(0);
    expect(undone.current?.example.id).toBe("demo_05");
    const lines = readFileSync(path.join(state.root, "data", "annotations.jsonl"), "utf8").trim().split("\n");
    expect(lines[1]).toBe('{"example_id":"demo_05","label":"p","undone":true,"ts":"2026-07-12T00:00:00.000Z","annotator":"PressF Desktop"}');
  });

  it("skips already annotated examples on resume", () => {
    const state = createDemoProject();
    decide(state.root, "f");
    const resumed = loadProjectState(state.root);
    expect(resumed.current?.example.id).not.toBe("demo_05");
    expect(resumed.queue).not.toContain("demo_05");
  });

  it("skips garbage folders inside PRESSF_HOME", () => {
    mkdirSync(path.join(tempHome, "Fluxus support demo", "data"), { recursive: true });
    expect(listProjects()).toEqual([]);
  });

  it("pins real Russian dry-run estimate output patterns", () => {
    const raw = [
      "Estimate for 8 examples (average input ~1120 current):",
      "synchronously: ~$0.42",
      "Batch API: ~$0.21 (default mode)",
      "Budget stop tap: $10.0 (llm.max_budget_usd)"
    ].join("\n");
    expect(parseEstimate(raw, 8)).toMatchObject({ examples: 8, syncUsd: 0.42, batchUsd: 0.21 });
  });

  it("builds CLI export arguments for DPO pairs and requested formats", () => {
    expect(buildExportArgs("/tmp/project", { pairs: true, formats: ["jsonl", "csv", "hf"] })).toEqual([
      "export", "/tmp/project", "--pairs", "--formats", "jsonl,csv,hf"
    ]);
  });

  it("builds CLI check arguments for force, a cheap limit, and synchronous mode", () => {
    expect(buildCheckArgs("/tmp/project", { force: true, limit: 3, sync: true })).toEqual([
      "check", "/tmp/project", "--force", "--limit", "3", "--sync"
    ]);
  });

  it("selects un-rechecked p/f labels and reports intra-annotator agreement", () => {
    const original = loadEffectiveAnnotations([
      { example_id: "one", label: "p" }, { example_id: "two", label: "f" }, { example_id: "skip", label: "s" }
    ]);
    expect(selfCheckQueue(original, [{ example_id: "one", label: "p" }], 0.5, () => 0)).toEqual(["two"]);
    expect(selfCheckStatsFor(original, [{ example_id: "one", label: "p" }, { example_id: "two", label: "p" }])).toEqual({ total: 2, done: 2, agreement: 0.5 });
  });

  it("writes self-check annotations without overwriting the primary review log", () => {
    const state = createDemoProject();
    decide(state.root, "p");
    const id = loadProjectState(state.root).current?.example.id;
    expect(id).toBeTruthy();
    const primary = loadProjectState(state.root).annotations[0].example_id;
    const next = decideSelfCheck(state.root, primary, "p");
    expect(next.selfcheck.done).toBe(1);
    expect(next.annotations).toHaveLength(1);
  });

  it("detects and imports pass/fail-like label columns", () => {
    const data = path.join(tempHome, "labeled.csv");
    const docs = path.join(tempHome, "docs");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "kb.md"), "The base limit is 600 requests per hour.\n", "utf8");
    writeFileSync(data, "qid,prompt,completion,grade\n1,What is the limit?,600 per hour,pass\n2,What is the limit?,1000 per hour,fail\n3,Webhooks?,Yes,fail\n", "utf8");
    const inspected = inspectDataFile(data);
    expect(inspected.detected.label).toBe("grade");
    const state = createProjectFromInputs({
      name: "Labeled import",
      dataPath: data,
      docsPath: docs,
      mapping: { question: "prompt", answer: "completion", id: "qid" },
      labelColumn: "grade",
      importLabels: true
    });
    expect(state.stats.done).toBe(3);
    expect(state.stats.p).toBe(1);
    expect(state.stats.f).toBe(2);
  });

  it("writes CLI provider settings and rejects an incomplete compatible setup", () => {
    const docs = path.join(tempHome, "docs");
    const data = path.join(tempHome, "answers.csv");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "kb.md"), "Facts.\n", "utf8");
    writeFileSync(data, "question,answer\nOne?,First.\n", "utf8");
    const openai = createProjectFromInputs({ name: "OpenAI judge", dataPath: data, docsPath: docs, mapping: { question: "question", answer: "answer" }, llm: { provider: "openai" } });
    expect(readFileSync(path.join(openai.root, "lazy.yaml"), "utf8")).toContain("provider: openai");
    expect(() => createProjectFromInputs({ name: "Compatible judge", dataPath: data, docsPath: docs, mapping: { question: "question", answer: "answer" }, llm: { provider: "openai_compatible", baseUrl: "http://localhost:11434/v1" } })).toThrow("require a model name");
  });

  it("requires the logged retrieval context for Search Quality and writes task-specific guidelines", () => {
    const docs = path.join(tempHome, "docs");
    const data = path.join(tempHome, "answers.csv");
    mkdirSync(docs);
    writeFileSync(data, "question,answer\nOne?,First.\n", "utf8");
    expect(() => createProjectFromInputs({ name: "Search", task: "retrieval_quality", dataPath: data, docsPath: docs, mapping: { question: "question", answer: "answer" } })).toThrow(/requires a column/i);

    writeFileSync(data, "question,answer,retrieved_context\nOne?,First.,Source says First.\n", "utf8");
    const state = createProjectFromInputs({ name: "Search", task: "retrieval_quality", dataPath: data, docsPath: docs, mapping: { question: "question", answer: "answer", context: "retrieved_context" } });
    expect(state.examples[0].context?.[0].text).toBe("Source says First.");
    expect(readFileSync(path.join(state.root, "GUIDELINES.md"), "utf8")).toContain("system itself");
  });

  it("deletes a project folder but refuses paths outside the project home", () => {
    const state = createDemoProject();
    expect(existsSync(state.root)).toBe(true);
    const remaining = deleteProject(state.root);
    expect(existsSync(state.root)).toBe(false);
    expect(remaining.find((p) => p.root === state.root)).toBeUndefined();

    expect(() => deleteProject(projectsBase())).toThrow(/outside/);
    expect(() => deleteProject(path.join(projectsBase(), "..", "escape"))).toThrow(/outside/);
    expect(() => deleteProject(path.join(projectsBase(), "not-a-project"))).toThrow(/lazy\.yaml/);
  });

  it("reads and rewrites the judge configuration of an existing project", () => {
    const state = createDemoProject();
    const before = readProjectConfigView(state.root);
    expect(before.provider).toBe("openai");
    expect(before.retrieverKind).toBe("docs_folder");

    const next = updateProjectLlm(state.root, { provider: "anthropic", judgeModel: "claude-haiku-4-5", maxBudgetUsd: 25 });
    expect(next.task).toBe("rag_faithfulness");
    const after = readProjectConfigView(state.root);
    expect(after.provider).toBe("anthropic");
    expect(after.judgeModel).toBe("claude-haiku-4-5");
    expect(after.maxBudgetUsd).toBe(25);

    expect(() => updateProjectLlm(state.root, { provider: "openai_compatible", judgeModel: "" })).toThrow(/model name|base URL/);
  });

  it("writes the reviewer name into annotations when one is set", () => {
    const state = createDemoProject();
    decide(state.root, "p", undefined, 55, "alice");
    const line = readFileSync(path.join(state.root, "data", "annotations.jsonl"), "utf8").trim();
    expect(line).toContain('"annotator":"alice"');

    const primary = loadProjectState(state.root).annotations[0].example_id;
    decideSelfCheck(state.root, primary, "p", undefined, 10, "alice");
    expect(readFileSync(path.join(state.root, "data", "selfcheck.jsonl"), "utf8")).toContain('"annotator":"alice self-check"');
  });

  it("updates escalation model and threshold in lazy.yaml", () => {
    const state = createDemoProject();
    updateProjectLlm(state.root, { provider: "anthropic", escalationModel: "claude-opus-4-8", escalationThreshold: 0.55 });
    const view = readProjectConfigView(state.root);
    expect(view.escalationModel).toBe("claude-opus-4-8");
    expect(view.escalationThreshold).toBe(0.55);

    updateProjectLlm(state.root, { provider: "anthropic", escalationModel: "" });
    expect(readProjectConfigView(state.root).escalationModel).toBeNull();
    expect(() => updateProjectLlm(state.root, { provider: "anthropic", escalationThreshold: 3 })).toThrow(/between 0 and 1/);
  });

  it("reads and rewrites the retriever, dropping stale location params on a kind switch", () => {
    const state = createDemoProject();
    const before = readProjectRetrieverConfig(state.root);
    expect(before.kind).toBe("docs_folder");
    expect(before.params.path).toBeTruthy();

    updateProjectRetriever(state.root, { kind: "qdrant", topK: 12, params: { url: "http://localhost:6333", collection: "kb" } });
    const after = readProjectRetrieverConfig(state.root);
    expect(after).toEqual({ kind: "qdrant", topK: 12, params: { url: "http://localhost:6333", collection: "kb" } });
    expect(readFileSync(path.join(state.root, "lazy.yaml"), "utf8")).not.toContain("path:");

    expect(() => updateProjectRetriever(state.root, { kind: "qdrant", params: {} })).toThrow(/URL/);
    expect(() => updateProjectRetriever(state.root, { kind: "martian_db", params: {} })).toThrow(/Unknown retriever/);
    expect(() => updateProjectRetriever(state.root, { kind: "docs_folder", topK: 0, params: { path: "/tmp/kb" } })).toThrow(/top_k/);
  });

  it("reads and writes command and HTTP bot configuration in lazy.yaml", () => {
    const state = createDemoProject();
    expect(readProjectBotConfig(state.root)).toMatchObject({ kind: "command", command: "", timeout: 60 });

    updateProjectBot(state.root, { kind: "command", command: "python bot.py {question}", url: "", method: "POST", headers: "{}", body: "", answerPath: "", timeout: 12 });
    expect(readProjectBotConfig(state.root)).toMatchObject({ kind: "command", command: "python bot.py {question}", timeout: 12 });

    updateProjectBot(state.root, { kind: "http", command: "", url: "http://localhost:8000/ask", method: "post", headers: '{"Authorization":"Bearer test"}', body: '{"question":"{question}"}', answerPath: "answer.text", timeout: 20 });
    const http = readProjectBotConfig(state.root);
    expect(http).toMatchObject({ kind: "http", url: "http://localhost:8000/ask", method: "POST", answerPath: "answer.text", timeout: 20 });
    expect(http.headers).toContain("Authorization");
    expect(() => updateProjectBot(state.root, { ...http, kind: "command", command: "", timeout: 60 })).toThrow("require a command");
    expect(() => updateProjectBot(state.root, { ...http, headers: "not-json" })).toThrow("headers");
    expect(buildBotRunArgs(state.root, "/tmp/fresh.jsonl")).toEqual(["run", state.root, "--out", "/tmp/fresh.jsonl"]);
  });

  it("parses and applies a dry-run calibration proposal without reimplementing it", () => {
    const state = createDemoProject();
    const raw = JSON.stringify({
      proposal: { summary: "Refusals are too permissive.", clarifications: ["A refusal with evidence is f."], fewshot: [{ question: "Q", answer: "A", correct_label: "f", why: "Evidence exists." }] },
      markdown: "<!-- pressf:calibration -->\n## Calibration\n- Rule",
      cost_usd: 0.002
    });
    const proposal = parseCalibrationProposal(raw);
    expect(proposal.costUsd).toBe(0.002);
    expect(proposal.fewshot[0].correct_label).toBe("f");
    applyCalibrationProposal(state.root, proposal.markdown);
    expect(readFileSync(path.join(state.root, "GUIDELINES.md"), "utf8")).toContain("<!-- pressf:calibration -->");
  });

  it("adds a second file through lazy add, preserving dedupe and continuing generated ids", async () => {
    const docs = path.join(tempHome, "docs");
    const initial = path.join(tempHome, "initial.csv");
    const fresh = path.join(tempHome, "fresh.csv");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "kb.md"), "Facts.\n", "utf8");
    writeFileSync(initial, "question,answer\nOne?,First.\nTwo?,Second.\n", "utf8");
    writeFileSync(fresh, "prompt,completion\nTwo?,Second.\nThree?,Third.\n", "utf8");
    const project = createProjectFromInputs({
      name: "Weekly audit",
      dataPath: initial,
      docsPath: docs,
      mapping: { question: "question", answer: "answer" }
    });

    const next = await addAnswers(project.root, fresh, { question: "prompt", answer: "completion" });

    expect(next.examples).toHaveLength(3);
    expect(next.examples.map((example) => example.id)).toEqual(["ex_0001", "ex_0002", "ex_0003"]);
    expect(next.examples.at(-1)?.question).toBe("Three?");
  });

  it("builds a distinct demo per module instead of reusing the truth-check demo", () => {
    const policy = createDemoProject("policy_compliance");
    expect(policy.name).toBe("RefundBot policy demo");
    expect(policy.task).toBe("policy_compliance");
    expect(policy.examples.length).toBeGreaterThan(0);
    expect(Object.values(policy.verdicts).some((v) => v.category === "violates_policy")).toBe(true);

    const search = createDemoProject("retrieval_quality");
    expect(search.name).toBe("SearchBot retrieval demo");
    expect(search.task).toBe("retrieval_quality");
    expect(Object.values(search.verdicts).some((v) => v.category === "context_missing")).toBe(true);

    const compare = createDemoProject("pairwise_compare");
    expect(compare.name).toBe("AnswerLab compare demo");
    expect(compare.task).toBe("pairwise_compare");
    expect(compare.examples.every((example) => Boolean(example.answer_b))).toBe(true);

    const truth = createDemoProject("rag_faithfulness");
    expect(truth.name).toBe("Fluxus support demo");
    const names = new Set([policy.root, search.root, compare.root, truth.root]);
    expect(names.size).toBe(4);
  });

  it("stores compare decisions in a separate pairwise log", () => {
    const data = path.join(tempHome, "compare.csv");
    const docs = path.join(tempHome, "docs");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "kb.md"), "Choose the clearer answer.\n", "utf8");
    writeFileSync(data, "qid,prompt,answer_a,answer_b\n1,Cancel?,Use billing.,Ask support.\n", "utf8");
    const state = createProjectFromInputs({
      name: "Compare import",
      task: "pairwise_compare",
      dataPath: data,
      docsPath: docs,
      mapping: { question: "prompt", answer: "answer_a", id: "qid" },
      importLabels: false
    });
    expect(state.examples[0].answer_b).toBe("Ask support.");
    const next = decidePairwise(state.root, "1", "a", "b", undefined, 77);
    expect(next.stats.done).toBe(1);
    expect(next.stats.p).toBe(1);
    expect(existsSync(path.join(state.root, "data", "annotations.jsonl"))).toBe(false);
    const pairwiseLog = readFileSync(path.join(state.root, "data", "pairwise_annotations.jsonl"), "utf8");
    expect(pairwiseLog).toContain('"winner":"a"');
    expect(pairwiseLog).toContain('"shown_left":"b"');
    const undone = undoPairwise(state.root);
    expect(undone.stats.done).toBe(0);
  });

  it("creates compare pairs from a baseline and matches new answers by id then question", () => {
    const baselineData = path.join(tempHome, "baseline.csv");
    const newData = path.join(tempHome, "new.csv");
    const docs = path.join(tempHome, "docs");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "kb.md"), "The base limit is 600 requests per hour.\n", "utf8");
    writeFileSync(baselineData, "id,question,answer\n1,What is the limit?,600 per hour\n2,Do you support webhooks?,Yes\n", "utf8");
    const baseline = createProjectFromInputs({
      name: "Baseline",
      dataPath: baselineData,
      docsPath: docs,
      mapping: { id: "id", question: "question", answer: "answer" }
    });
    writeFileSync(newData, "id,question,answer\n1,What is the limit?,1000 per hour\n,Do you support webhooks?,No\n9,Unknown?,Ignored\n", "utf8");

    const comparison = createCompareProjectFromBaseline({
      name: "Comparison",
      baselineRoot: baseline.root,
      dataPath: newData,
      mapping: { id: "id", question: "question", answer: "answer" }
    });

    expect(comparison.task).toBe("pairwise_compare");
    expect(comparison.examples).toHaveLength(2);
    expect(comparison.examples.map((example) => example.answer_b)).toEqual(["1000 per hour", "No"]);
    const ingest = readFileSync(path.join(comparison.root, "data", "ingest_report.md"), "utf8");
    expect(ingest).toContain("- Matched pairs: 2");
    expect(ingest).toContain("- Unmatched new rows: 1");
  });
});
