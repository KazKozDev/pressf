import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { inspectDataFile, loadRows, parseContextChunks } from "./projectData.js";
import { loadTraceRows, looksLikeTraces, traceToRow } from "./traces.js";

describe("traceToRow", () => {
  it("unrolls a LangSmith run export", () => {
    const row = traceToRow({
      id: "run-1",
      inputs: { question: "How do I cancel?" },
      outputs: { answer: "From the Billing page." },
      extra: { context: ["You can cancel from Billing.", { page_content: "Invoices monthly." }] }
    });
    expect(row).toEqual({
      id: "run-1",
      question: "How do I cancel?",
      answer: "From the Billing page.",
      context: JSON.stringify(["You can cancel from Billing.", "Invoices monthly."])
    });
  });

  it("unrolls a Langfuse export with string input/output", () => {
    const row = traceToRow({
      input: "What is the refund window?",
      output: { text: "30 days." },
      metadata: { documents: [{ text: "Refunds are accepted for 30 days." }] }
    });
    expect(row).toEqual({
      question: "What is the refund window?",
      answer: "30 days.",
      context: JSON.stringify(["Refunds are accepted for 30 days."])
    });
  });

  it("returns null when question or answer is missing", () => {
    expect(traceToRow({ inputs: { question: "Q" }, outputs: {} })).toBeNull();
    expect(traceToRow({ inputs: {}, outputs: { answer: "A" } })).toBeNull();
  });
});

describe("looksLikeTraces", () => {
  it("detects trace-shaped rows and leaves flat files alone", () => {
    expect(looksLikeTraces([{ inputs: { question: "q" }, outputs: { answer: "a" } }])).toBe(true);
    expect(looksLikeTraces([{ question: "q", answer: "a" }])).toBe(false);
    expect(looksLikeTraces([])).toBe(false);
  });

  it("does not treat flat files with input/output columns plus question/answer as traces", () => {
    expect(looksLikeTraces([{ question: "q", answer: "a", input: "raw", output: "raw" }])).toBe(false);
  });
});

describe("loadTraceRows", () => {
  it("skips broken traces and keeps good ones", () => {
    const rows = loadTraceRows([
      { inputs: { question: "q1" }, outputs: { answer: "a1" } },
      { inputs: {}, outputs: {} },
      { _parse_error: true, inputs: { question: "x" }, outputs: { answer: "y" } }
    ]);
    expect(rows).toEqual([{ question: "q1", answer: "a1" }]);
  });
});

describe("loadRows trace integration", () => {
  it("auto-unrolls a trace JSONL export so inspection sees flat columns", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "pressf-traces-"));
    const file = path.join(dir, "runs.jsonl");
    writeFileSync(
      file,
      [
        JSON.stringify({ id: "r1", inputs: { question: "How do I cancel?" }, outputs: { answer: "From Billing." }, extra: { context: ["Cancel from Billing."] } }),
        JSON.stringify({ id: "r2", inputs: { query: "Refund window?" }, outputs: { response: "30 days." } })
      ].join("\n") + "\n",
      "utf8"
    );
    const rows = loadRows(file);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ question: "How do I cancel?", answer: "From Billing." });

    const inspection = inspectDataFile(file);
    expect(inspection.detected.question).toBe("question");
    expect(inspection.detected.answer).toBe("answer");
    expect(inspection.detected.context).toBe("context");
    expect(inspection.detected.id).toBe("id");
  });
});

describe("parseContextChunks", () => {
  it("keeps plain text as a single chunk", () => {
    expect(parseContextChunks("just text")).toEqual([{ text: "just text" }]);
  });

  it("parses JSON arrays of strings and of chunks", () => {
    expect(parseContextChunks('["a", "b"]')).toEqual([{ text: "a" }, { text: "b" }]);
    expect(parseContextChunks('[{"text": "a", "source": "doc.md#0"}]')).toEqual([{ text: "a", source: "doc.md#0" }]);
  });

  it("falls back to plain text for malformed JSON", () => {
    expect(parseContextChunks("[not json")).toEqual([{ text: "[not json" }]);
  });
});
