import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const cyrillic = /[\u0400-\u052f]/;

async function launchPressF(home: string, extraEnv: Record<string, string> = {}): Promise<{ app: ElectronApplication; page: Page }> {
  const app = await electron.launch({
    args: ["."],
    env: {
      ...process.env,
      PRESSF_HOME: home,
      PRESSF_E2E: "1",
      PRESSF_FIXED_NOW: "2026-07-12T00:00:00.000Z",
      PRESSF_FIXED_ELAPSED_MS: "1234",
      ...extraEnv
    }
  });
  return { app, page: await app.firstWindow() };
}

async function assertMainPathEnglish(page: Page) {
  const text = await page.getByTestId("main-path").innerText();
  expect(text, "main path should not contain Cyrillic UI copy").not.toMatch(cyrillic);
}

function projectNameInput(page: Page) {
  return page.locator("input.bigInput");
}

async function createPreparedFixture(page: Page, home: string) {
  const docs = path.join(home, "docs");
  mkdirSync(docs);
  writeFileSync(path.join(docs, "kb.md"), "The base plan allows 600 requests per hour. The API returns HTTP 429.\n", "utf8");
  const csv = path.resolve("tests/fixtures/labeled.csv");

  await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
  await projectNameInput(page).fill("Helpdesk");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Paste file path").fill(csv);
  await page.getByLabel("Paste file path").blur();
  await expect(page.getByText("I found human decisions")).toBeVisible();
  await page.getByLabel("I found human decisions in this file. Import them too?").uncheck();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Paste folder path").fill(docs);
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Ready.")).toBeVisible();

  const projectRoot = path.join(home, "Helpdesk");
  cpSync(path.resolve("tests/fixtures/labeled-verdicts.jsonl"), path.join(projectRoot, "data", "verdicts.jsonl"));
  await expect(page.getByRole("button", { name: "Start" })).toBeVisible();
  await page.getByRole("button", { name: "Start" }).click();
}

test("new scanner flow: fixture file, prepared results, categories, cards, finish, export", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-redesign-"));
  const { app, page } = await launchPressF(home);
  try {
    await createPreparedFixture(page, home);
    await expect(page.getByText("Flagged answers")).toBeVisible({ timeout: 8000 });
    await expect(page.getByText("3", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: /Hallucination - contradicts docs/i }).click();
    await expect(page.getByRole("heading", { name: "Hallucination - contradicts docs" })).toBeVisible();
    await page.getByRole("button", { name: /What is the base limit/i }).click();
    await expect(page.getByText("Is the answer correct?")).toBeVisible();
    await page.getByRole("button", { name: /Back/i }).click();

    await page.getByRole("button", { name: /Back/i }).click();
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("p");
    await page.keyboard.press("u");
    await page.keyboard.press("p");
    await page.getByRole("button", { name: "Can't assess S", exact: true }).click();
    await expect(page.getByPlaceholder("Why can't this case be assessed?")).toBeVisible();
    await page.getByPlaceholder("Why can't this case be assessed?").fill("Need product owner.");
    await page.getByRole("button", { name: "Can't assess", exact: true }).click();
    await page.keyboard.press("f");

    await expect(page.getByText("Done!")).toBeVisible();
    await expect(page.getByText("You checked 3 answers — 1 real errors, 1 false alarms.")).toBeVisible();
    await expect(page.getByText("Checker trust")).toBeVisible();
    await page.getByRole("button", { name: /Save report/i }).click();
    await expect(page.getByText("Report saved.")).toBeVisible();

    const out = path.join(home, "Helpdesk", "out");
    expect(existsSync(path.join(out, "goldset.jsonl"))).toBe(true);
    expect(existsSync(path.join(out, "report.md"))).toBe(true);

    const firstLine = readFileSync(path.join(home, "Helpdesk", "data", "annotations.jsonl"), "utf8").split("\n")[0];
    expect(firstLine).toBe(
      '{"example_id":"1","label":"p","agreed_with_agent":true,"undone":false,"ts":"2026-07-12T00:00:00.000Z","annotator":"PressF Desktop","elapsed_ms":1234}'
    );
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("help screen explains what PressF is and returns home", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-help-"));
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: "Help", exact: true }).click();
    await expect(page.getByRole("heading", { name: "About PressF" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "The key idea" })).toBeVisible();
    await expect(page.getByText(/goldset-quality labels at a fraction of the cost/)).toBeVisible();
    await page.getByRole("button", { name: /Back/i }).click();
    await expect(page.getByRole("heading", { name: "The evaluation workspace for everyone" })).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("deletes a project from Recent checks after confirmation", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-delete-"));
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: /Show a real error/i }).click();
    await expect(page.getByText("Flagged answers")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Truth Check" }).click();
    await expect(page.getByText("Fluxus support demo")).toBeVisible();
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page.getByText("Delete this project and all its data?")).toBeVisible();
    await page.getByRole("button", { name: "Delete", exact: true }).last().click();
    await expect(page.getByText("Fluxus support demo")).toHaveCount(0);
    await expect(page.getByText("No checks yet. The example is ready.")).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("try the example reaches the scanner hub without setup", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-example-"));
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: /Show a real error/i }).click();
    await expect(page.getByText("Flagged answers")).toBeVisible({ timeout: 8000 });
    await expect(page.getByRole("button", { name: "Review flagged" })).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("settings panel edits and persists the judge configuration", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-settings-"));
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: /Show a real error/i }).click();
    await expect(page.getByText("Flagged answers")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByRole("heading", { name: "LLM judge" })).toBeVisible();
    await page.getByLabel("Provider").selectOption("anthropic");
    await page.getByLabel("Judge model").fill("claude-haiku-4-5");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByText(/Saved\./)).toBeVisible();
    const cfg = readFileSync(path.join(home, "Fluxus support demo", "lazy.yaml"), "utf8");
    expect(cfg).toContain("provider: anthropic");
    expect(cfg).toContain("claude-haiku-4-5");
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("adds a second answers file to an existing project and returns to the hub", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-add-"));
  const fresh = path.join(home, "fresh.csv");
  writeFileSync(fresh, "prompt,completion\nWhat is Fluxus?,A creative arts movement.\n", "utf8");
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: /Show a real error/i }).click();
    await expect(page.getByText("Flagged answers")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Add answers", exact: true }).click();
    await page.getByLabel("Paste file path").fill(fresh);
    await page.getByLabel("Paste file path").blur();
    await expect(page.getByText("These columns differ from the original import")).toBeVisible();
    await page.getByRole("button", { name: "Add answers", exact: true }).last().click();
    await expect(page.getByText("9 answers checked")).toBeVisible();
    expect(readFileSync(path.join(home, "Fluxus support demo", "data", "examples.jsonl"), "utf8").trim().split("\n")).toHaveLength(9);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("exports and shows the actual human-versus-judge disagreements", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-disagreements-"));
  const { app, page } = await launchPressF(home);
  try {
    await createPreparedFixture(page, home);
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await expect(page.getByText("Done!")).toBeVisible();
    await page.getByRole("button", { name: "View disagreements" }).click();
    await expect(page.getByRole("heading", { name: "Judge disagreements" })).toBeVisible();
    await expect(page.getByText("Judge recommendation")).toHaveCount(2);
    expect(existsSync(path.join(home, "Helpdesk", "out", "disagreements.jsonl"))).toBe(true);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("judge evaluation opens mismatches and revises a human label through the normal review log", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-judge-evaluation-"));
  const { app, page } = await launchPressF(home);
  try {
    await createPreparedFixture(page, home);
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await expect(page.getByText("Done!")).toBeVisible();

    await page.getByRole("button", { name: "Evaluate judge" }).click();
    await expect(page.getByRole("heading", { name: "Judge evaluation" })).toBeVisible();
    await expect(page.getByText("3 / 3 human-reviewed")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Disagreements" })).toBeVisible();
    await page.getByRole("button", { name: "Open case" }).first().click();
    await expect(page.getByRole("heading", { name: "Evaluate case" })).toBeVisible();
    await page.getByRole("button", { name: /^Fail F$/ }).click();
    await page.getByRole("button", { name: /Back/ }).click();
    await expect(page.getByText("1 case to inspect")).toBeVisible();
    expect(readFileSync(path.join(home, "Helpdesk", "data", "annotations.jsonl"), "utf8").trim().split("\n")).toHaveLength(4);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("exports DPO training pairs from f labels", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-pairs-"));
  const { app, page } = await launchPressF(home);
  try {
    await createPreparedFixture(page, home);
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("f");
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await expect(page.getByText("Done!")).toBeVisible();
    await page.getByRole("button", { name: "Export training pairs (DPO)" }).click();
    await expect(page.getByRole("button", { name: "Show DPO pairs in Finder" })).toBeVisible();
    expect(existsSync(path.join(home, "Helpdesk", "out", "pairs.jsonl"))).toBe(true);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("blind self-check hides judge evidence and records a re-review", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-selfcheck-"));
  const { app, page } = await launchPressF(home);
  try {
    await createPreparedFixture(page, home);
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("p");
    await page.getByRole("button", { name: /Back/ }).click();
    await page.getByRole("button", { name: /Back/ }).click();
    await page.getByRole("button", { name: "Re-check yourself" }).click();
    await expect(page.getByText("Your documents say:")).toHaveCount(0);
    await page.keyboard.press("p");
    await expect(page.getByText("Done!")).toBeVisible();
    expect(existsSync(path.join(home, "Helpdesk", "data", "selfcheck.jsonl"))).toBe(true);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("each module has its own home copy and its own example demo", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-modules-"));
  const { app, page } = await launchPressF(home);
  try {
    await expect(page.getByRole("heading", { name: "The evaluation workspace for everyone" })).toBeVisible();
    await expect(page.getByText(/support bots, knowledge assistants/)).toBeVisible();

    await page.getByRole("button", { name: "Policy Check" }).click();
    await expect(page.getByRole("heading", { name: "The evaluation workspace for everyone" })).toBeVisible();
    await expect(page.getByText(/customer support, finance, HR/)).toBeVisible();
    await page.getByText("How it works").click();
    await expect(page.getByText("PressF checks each answer against your rules document.")).toBeVisible();
    await page.getByRole("button", { name: /Show a real error/i }).click();
    await expect(page.getByText("Policy violations")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByText(/RefundBot policy demo/).first()).toBeVisible(); // its own demo, distinct from the Truth Check one
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("policy check works end to end with prepared rule findings", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-policy-"));
  const { app, page } = await launchPressF(home);
  try {
    const rules = path.join(home, "rules");
    mkdirSync(rules);
    writeFileSync(path.join(rules, "rules.md"), "Do not promise refunds without manager approval.\n", "utf8");
    await page.getByRole("button", { name: "Policy Check" }).click();
    await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("RefundBot");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste file path").fill(path.resolve("tests/fixtures/policy.csv"));
    await page.getByLabel("Paste file path").blur();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Show me the rules RefundBot should follow")).toBeVisible();
    await page.getByLabel("Paste folder path").fill(rules);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Ready.")).toBeVisible();
    const projectRoot = path.join(home, "RefundBot");
    cpSync(path.resolve("tests/fixtures/policy-verdicts.jsonl"), path.join(projectRoot, "data", "verdicts.jsonl"));
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByText("Policy violations")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Review flagged" }).click();
    await expect(page.getByText("Your rules say:")).toBeVisible();
    await page.keyboard.press("f");
    await expect(page.getByText("Done!")).toBeVisible();
    await page.getByRole("button", { name: /Save report/i }).click();
    await expect(page.getByText("Report saved.")).toBeVisible();
    expect(existsSync(path.join(projectRoot, "out", "report.md"))).toBe(true);
    const line = readFileSync(path.join(projectRoot, "data", "annotations.jsonl"), "utf8").split("\n")[0];
    expect(line).toContain('"example_id":"1"');
    expect(line).toContain('"label":"f"');
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("search quality works end to end with prepared context findings", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-search-"));
  const { app, page } = await launchPressF(home);
  try {
    const docs = path.join(home, "docs");
    mkdirSync(docs);
    writeFileSync(path.join(docs, "billing.md"), "Refund deadlines live in billing policy pages.\n", "utf8");
    await page.getByRole("button", { name: "Search Quality" }).click();
    await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("SearchBot");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste file path").fill(path.resolve("tests/fixtures/search.csv"));
    await page.getByLabel("Paste file path").blur();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Show me the documents SearchBot's search should find")).toBeVisible();
    await page.getByLabel("Paste folder path").fill(docs);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Ready.")).toBeVisible();
    const projectRoot = path.join(home, "SearchBot");
    cpSync(path.resolve("tests/fixtures/search-verdicts.jsonl"), path.join(projectRoot, "data", "verdicts.jsonl"));
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByText("Retrieval gaps")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: /Partial retrieval/i }).click();
    await expect(page.getByRole("heading", { name: "Partial retrieval" })).toBeVisible();
    await page.getByRole("button", { name: /What is the refund deadline/i }).click();
    await expect(page.getByText("Search found:")).toBeVisible();
    await page.keyboard.press("f");
    await expect(page.getByText("Done!")).toBeVisible();
    await page.getByRole("button", { name: /Save report/i }).click();
    await expect(page.getByText("Report saved.")).toBeVisible();
    expect(existsSync(path.join(projectRoot, "out", "report.md"))).toBe(true);
    const report = readFileSync(path.join(projectRoot, "out", "report.md"), "utf8");
    expect(report).toContain("## Search problems");
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("compare versions writes pairwise decisions and exports pairs", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-compare-"));
  const baselineRoot = path.join(home, "Baseline");
  mkdirSync(path.join(baselineRoot, "data"), { recursive: true });
  writeFileSync(path.join(baselineRoot, "lazy.yaml"), "project: Baseline\ntask: rag_faithfulness\nretriever:\n  kind: docs_folder\n  path: /tmp\n", "utf8");
  writeFileSync(path.join(baselineRoot, "data", "examples.jsonl"), [
    '{"id":"1","question":"Cancel?","answer":"Use billing.","meta":{}}',
    '{"id":"2","question":"Refund deadline?","answer":"30 days.","meta":{}}'
  ].join("\n") + "\n", "utf8");
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: "Compare Versions" }).click();
    await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("AnswerLab");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Baseline" }).click();
    await page.getByLabel("Paste file path").fill(path.resolve("tests/fixtures/compare.csv"));
    await page.getByLabel("Paste file path").blur();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Ready.")).toBeVisible();
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByText("Version pairs")).toBeVisible({ timeout: 8000 });
    await page.getByTestId("main-path").getByRole("button", { name: "Compare versions" }).click();
    await expect(page.getByText("Which version is better?")).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowRight");
    await expect(page.getByText("Done!")).toBeVisible();
    await expect(page.getByText(/New version: better on \d+, worse on \d+, tie on 0\./)).toBeVisible();
    await page.getByRole("button", { name: /Save report/i }).click();
    await expect(page.getByText("Report saved.")).toBeVisible();
    const projectRoot = path.join(home, "AnswerLab");
    const pairwise = readFileSync(path.join(projectRoot, "data", "pairwise_annotations.jsonl"), "utf8").trim().split("\n");
    expect(pairwise[0]).toContain('"winner":');
    expect(pairwise[0]).toContain('"shown_left":');
    expect(pairwise[1]).toContain('"winner":');
    expect(pairwise[1]).toContain('"shown_left":');
    const pairs = readFileSync(path.join(projectRoot, "out", "pairs.jsonl"), "utf8").trim().split("\n").map((line) => JSON.parse(line) as { winner: string; shown_left: string });
    expect(pairs.map((row) => row.winner)).toHaveLength(2);
    expect(pairs.every((row) => row.shown_left === "a" || row.shown_left === "b")).toBe(true);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("configures a command bot, runs it on the baseline, and reaches pairwise review", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-bot-run-"));
  const baselineRoot = path.join(home, "Baseline");
  const botScript = path.join(home, "fixture-bot.js");
  mkdirSync(path.join(baselineRoot, "data"), { recursive: true });
  writeFileSync(botScript, "process.stdin.on('data', value => process.stdout.write('Fresh: ' + value.toString().trim()));\n", "utf8");
  writeFileSync(path.join(baselineRoot, "lazy.yaml"), "project: Baseline\ntask: rag_faithfulness\nretriever:\n  kind: docs_folder\n  path: /tmp\n", "utf8");
  writeFileSync(path.join(baselineRoot, "data", "examples.jsonl"), [
    '{"id":"1","question":"Cancel?","answer":"Use billing.","meta":{}}',
    '{"id":"2","question":"Refund deadline?","answer":"30 days.","meta":{}}'
  ].join("\n") + "\n", "utf8");
  const { app, page } = await launchPressF(home);
  try {
    await page.getByText("Baseline", { exact: true }).click();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByRole("textbox", { name: "Command", exact: true }).fill(`${process.execPath} ${botScript}`);
    await page.getByRole("button", { name: "Save bot connector" }).click();
    await expect(page.getByText("Bot connector saved.")).toBeVisible();
    expect(readFileSync(path.join(baselineRoot, "lazy.yaml"), "utf8")).toContain("kind: command");
    await page.getByRole("button", { name: "Close", exact: true }).click();

    await page.getByRole("button", { name: "Compare Versions" }).click();
    await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("AnswerLab");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Baseline" }).click();
    await page.getByRole("button", { name: "Run my bot on this goldset" }).click();
    await expect(page.getByText("Fresh answers are ready and selected for comparison.")).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByText("Version pairs")).toBeVisible({ timeout: 8000 });
    await page.getByTestId("main-path").getByRole("button", { name: "Compare versions" }).click();
    await expect(page.getByText("Which version is better?")).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("previews, rejects, and accepts a mocked calibration proposal", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-calibration-"));
  const fixture = path.join(home, "calibration.json");
  writeFileSync(fixture, JSON.stringify({
    proposal: { summary: "Refusals are too permissive.", clarifications: ["A refusal with evidence is a failure."], fewshot: [{ question: "How do I cancel?", answer: "I cannot help.", correct_label: "f", why: "The answer is documented." }] },
    markdown: "<!-- pressf:calibration -->\n## Judge calibration\n\n- A refusal with evidence is a failure.",
    cost_usd: 0.002
  }), "utf8");
  const { app, page } = await launchPressF(home, { PRESSF_CALIBRATION_FIXTURE: fixture });
  try {
    await createPreparedFixture(page, home);
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await page.keyboard.press("p");
    await expect(page.getByText("Done!")).toBeVisible();
    await page.getByRole("button", { name: "Improve the judge" }).click();
    await expect(page.getByRole("heading", { name: "Suggested guideline update" })).toBeVisible();
    await page.getByRole("button", { name: "Reject" }).click();
    await expect(page.getByRole("heading", { name: "Suggested guideline update" })).toHaveCount(0);
    await page.getByRole("button", { name: "Improve the judge" }).click();
    await page.getByRole("button", { name: "Accept update" }).click();
    await expect(page.getByText("Guidelines updated. Re-check answers with the improved judge?")).toBeVisible();
    expect(readFileSync(path.join(home, "Helpdesk", "GUIDELINES.md"), "utf8")).toContain("<!-- pressf:calibration -->");
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("main path is English-only", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-words-"));
  const { app, page } = await launchPressF(home);
  try {
    await assertMainPathEnglish(page);
    await page.getByTestId("main-path").getByRole("button", { name: "New evaluation", exact: true }).click();
    await assertMainPathEnglish(page);
    await projectNameInput(page).fill("Helpdesk");
    await page.getByRole("button", { name: "Next" }).click();
    await assertMainPathEnglish(page);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("setup writes an OpenAI judge configuration", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-openai-"));
  const docs = path.join(home, "docs");
  mkdirSync(docs);
  writeFileSync(path.join(docs, "kb.md"), "Facts.\n", "utf8");
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("OpenAI bot");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste file path").fill(path.resolve("tests/fixtures/labeled.csv"));
    await page.getByLabel("Paste file path").blur();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste folder path").fill(docs);
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByRole("heading", { name: "Choose a judge" })).toBeVisible();
    await page.getByLabel("Judge provider").selectOption("openai");
    await page.getByRole("button", { name: "Next" }).click();
    expect(readFileSync(path.join(home, "OpenAI bot", "lazy.yaml"), "utf8")).toContain("provider: openai");
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("imports existing human labels and shows agreement after prepared judging", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-label-import-"));
  const docs = path.join(home, "docs");
  mkdirSync(docs);
  writeFileSync(path.join(docs, "kb.md"), "Facts.\n", "utf8");
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: "New evaluation", exact: true }).click();
    await projectNameInput(page).fill("Imported labels");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste file path").fill(path.resolve("tests/fixtures/labeled.csv"));
    await page.getByLabel("Paste file path").blur();
    await expect(page.getByLabel("I found human decisions in this file. Import them too?")).toBeChecked();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByLabel("Paste folder path").fill(docs);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    const root = path.join(home, "Imported labels");
    cpSync(path.resolve("tests/fixtures/labeled-verdicts.jsonl"), path.join(root, "data", "verdicts.jsonl"));
    await page.getByRole("button", { name: "Start" }).click();
    await page.getByRole("button", { name: "Review flagged" }).click();
    await page.keyboard.press("f");
    await expect(page.getByText("Done!")).toBeVisible();
    await expect(page.getByText("Checker trust")).toBeVisible();
    await page.getByRole("button", { name: "Save report" }).click();
    await expect(page.getByText("Report saved.")).toBeVisible();
    expect(readFileSync(path.join(root, "out", "report.md"), "utf8")).toContain("Human/judge agreement:");
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("sidebar modules always return from an inner flow to their workspace", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-sidebar-nav-"));
  const { app, page } = await launchPressF(home);
  try {
    await page.getByRole("button", { name: "New evaluation", exact: true }).click();
    await expect(projectNameInput(page)).toBeVisible();

    await page.getByRole("button", { name: "Policy Check" }).click();
    await expect(page.getByRole("heading", { name: "The evaluation workspace for everyone" })).toBeVisible();
    await expect(page.getByText(/customer support, finance, HR/)).toBeVisible();
    await page.getByRole("button", { name: "New evaluation", exact: true }).click();
    await expect(projectNameInput(page)).toBeVisible();

    await page.getByRole("button", { name: "Search Quality" }).click();
    await expect(page.getByRole("heading", { name: "The evaluation workspace for everyone" })).toBeVisible();
    await expect(page.getByText(/enterprise search, help centres/)).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});
