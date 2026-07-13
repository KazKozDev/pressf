// TypeScript port of pressf/ingest/traces.py: unroll LangSmith/Langfuse trace exports
// into flat {question, answer, context} rows so the rest of ingestion stays unchanged.
//
// LangSmith run export:
//   {"inputs": {"question": "..."}, "outputs": {"answer": "..."}, "extra": {"context": [...]}}
// Langfuse trace/observation export:
//   {"input": {"question": "..."} | "...", "output": "..." | {"text": "..."}, "metadata": {"context": [...]}}

const Q_KEYS = ["question", "query", "input", "prompt", "text"] as const;
const A_KEYS = ["answer", "output", "response", "generation", "completion", "text"] as const;
const CTX_KEYS = ["context", "contexts", "documents", "retrieved", "retrieved_documents", "sources"] as const;
const CHUNK_TEXT_KEYS = ["text", "page_content", "content", "document"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function firstStr(obj: unknown, keys: readonly string[]): string {
  if (typeof obj === "string") return obj.trim();
  if (isRecord(obj)) {
    for (const key of keys) {
      const value = obj[key];
      if (typeof value === "string" && value.trim()) return value.trim();
      if (isRecord(value)) {
        const inner = firstStr(value, keys);
        if (inner) return inner;
      }
    }
  }
  return "";
}

function contextToJson(obj: unknown): string {
  let found: unknown = null;
  if (isRecord(obj)) {
    for (const key of CTX_KEYS) {
      if (obj[key]) {
        found = obj[key];
        break;
      }
    }
  }
  if (found === null) return "";
  const chunks: string[] = [];
  for (const item of Array.isArray(found) ? found : [found]) {
    if (typeof item === "string" && item.trim()) chunks.push(item.trim());
    else if (isRecord(item)) {
      const text = firstStr(item, CHUNK_TEXT_KEYS);
      if (text) chunks.push(text);
    }
  }
  return chunks.length ? JSON.stringify(chunks) : "";
}

export function traceToRow(trace: Record<string, unknown>): Record<string, string> | null {
  const rawInputs = trace.inputs;
  const inputs = isRecord(rawInputs) || typeof rawInputs === "string" ? rawInputs : trace.input;
  const outputs = trace.outputs !== undefined && trace.outputs !== null ? trace.outputs : trace.output;
  const extra = trace.extra ?? trace.metadata ?? {};

  const question = firstStr(inputs, Q_KEYS);
  const answer = firstStr(outputs, A_KEYS);
  if (!question || !answer) return null;
  const context = contextToJson(inputs) || contextToJson(outputs) || contextToJson(extra);
  const row: Record<string, string> = { question, answer };
  if (context) row.context = context;
  if (trace.id) row.id = String(trace.id);
  return row;
}

export function looksLikeTraces(rows: Record<string, unknown>[]): boolean {
  if (!rows.length) return false;
  const traceShaped = rows.filter((row) =>
    isRecord(row) &&
    ("inputs" in row || "input" in row) &&
    ("outputs" in row || "output" in row) &&
    !("question" in row && "answer" in row)
  );
  return traceShaped.length >= Math.ceil(rows.length / 2);
}

export function loadTraceRows(rows: Record<string, unknown>[]): Record<string, string>[] {
  const out: Record<string, string>[] = [];
  for (const trace of rows) {
    if (!isRecord(trace) || "_parse_error" in trace) continue;
    const row = traceToRow(trace);
    if (row) out.push(row);
  }
  return out;
}
