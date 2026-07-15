export type Label = "p" | "f" | "s";
export type ClaimStatus = "supported" | "contradicted" | "not_found";

export type ContextChunk = {
  text: string;
  source?: string | null;
};

export type ToolCall = {
  name: string;
  arguments: Record<string, unknown> | string;
  result?: string | null;
  error?: string | null;
  duration_ms?: number | null;
};

export type TrajectoryStep = {
  kind: "thought" | "tool_call" | "answer";
  content?: string | null;
  tool?: ToolCall | null;
  index: number;
};

export type TrajectoryStepVerdict = {
  step_index: number;
  ok: boolean;
  issue?: string | null;
  issue_kind?: string | null;
};

export type Example = {
  id: string;
  question: string;
  answer: string;
  answer_b?: string | null;
  context?: ContextChunk[] | null;
  trajectory?: TrajectoryStep[] | null;
  meta?: Record<string, unknown>;
};

export type Evidence = {
  text: string;
  source: string;
  score?: number | null;
};

export type ClaimVerdict = {
  text: string;
  status: ClaimStatus;
  evidence: Evidence[];
};

export type Verdict = {
  example_id: string;
  claims?: ClaimVerdict[];
  is_refusal?: boolean;
  answerable: boolean;
  grounded?: boolean | null;
  recommendation: "p" | "f";
  category: string;
  confidence: number;
  reasoning: string;
  judge_model: string;
  escalated?: boolean;
  cost_usd?: number;
  created_at?: string;
  step_issues?: TrajectoryStepVerdict[] | null;
};

export type Annotation = {
  example_id: string;
  label: Label;
  note?: string;
  agreed_with_agent?: boolean | null;
  undone?: boolean;
  ts?: string;
  annotator?: string;
  elapsed_ms?: number;
};

export type PairwiseWinner = "a" | "b" | "tie";
export type PairwiseShownLeft = "a" | "b";

export type PairwiseAnnotation = {
  example_id: string;
  winner: PairwiseWinner;
  choice?: PairwiseWinner;
  shown_left: PairwiseShownLeft;
  note?: string;
  undone?: boolean;
  ts?: string;
  annotator?: string;
  elapsed_ms?: number;
};

export type SessionStats = {
  total: number;
  done: number;
  p: number;
  f: number;
  s: number;
  agreement: number | null;
};

export type SelfCheckStats = {
  total: number;
  done: number;
  agreement: number | null;
};

export type ProjectSummary = {
  root: string;
  name: string;
  updatedAt: string | null;
  total: number;
  bad: number;
  done: number;
  station: "data" | "judge" | "review" | "results";
  task: string;
};

export type ReviewCard = {
  example: Example;
  verdict: Verdict | null;
  index: number;
  total: number;
};

export type ProjectState = {
  root: string;
  name: string;
  task: string;
  examples: Example[];
  verdicts: Record<string, Verdict>;
  annotations: Annotation[];
  selfcheckAnnotations: Annotation[];
  pairwiseAnnotations: PairwiseAnnotation[];
  effective: Record<string, Annotation>;
  pairwiseEffective: Record<string, PairwiseAnnotation>;
  queue: string[];
  stats: SessionStats;
  selfcheck: SelfCheckStats;
  current: ReviewCard | null;
  paths: {
    config: string;
    examples: string;
    verdicts: string;
    annotations: string;
    pairwiseAnnotations: string;
    report: string;
    goldset: string;
    disagreements: string;
    pairs: string;
    selfcheck: string;
  };
  ingestMapping?: ColumnMapping;
  llmProvider?: LlmProvider;
};

export type ColumnMapping = {
  question: string;
  answer: string;
  context?: string | null;
  trajectory?: string | null;
  id?: string | null;
};

export type DataInspection = {
  path: string;
  headers: string[];
  rows: Record<string, unknown>[];
  detected: ColumnMapping & { label?: string | null };
  rowCount: number;
};

export type CreateProjectInput = {
  name: string;
  task?: string;
  dataPath: string;
  docsPath: string;
  /** Knowledge-base shape chosen in the wizard: a folder of documents (default) or an exported chunks JSONL. */
  retrieverKind?: "docs_folder" | "chunks_file";
  mapping: ColumnMapping;
  labelColumn?: string | null;
  importLabels?: boolean;
  llm?: LlmSetup;
};

export type LlmProvider = "anthropic" | "openai" | "openai_compatible";

export type LlmSetup = {
  provider: LlmProvider;
  judgeModel?: string;
  baseUrl?: string;
};

export type ProjectConfigView = {
  provider: LlmProvider;
  judgeModel: string;
  escalationModel: string | null;
  escalationThreshold: number;
  baseUrl: string | null;
  maxBudgetUsd: number;
  retrieverKind: string;
  retrieverDetail: string;
};

export type LlmUpdate = {
  provider: LlmProvider;
  judgeModel?: string;
  baseUrl?: string;
  maxBudgetUsd?: number;
  escalationModel?: string;
  escalationThreshold?: number;
};

export type RetrieverConfigView = {
  kind: string;
  topK: number;
  params: Record<string, string>;
};

export type RetrieverUpdate = {
  kind: string;
  topK?: number;
  params: Record<string, string>;
};

export type BotKind = "command" | "http";

export type BotConfigView = {
  kind: BotKind;
  command: string;
  url: string;
  method: string;
  headers: string;
  body: string;
  answerPath: string;
  timeout: number;
};

export type BotUpdate = BotConfigView;

export type BotRunResult = {
  code: number | null;
  cancelled: boolean;
  output: string;
  file: string;
};

export type CalibrationProposal = {
  summary: string;
  clarifications: string[];
  fewshot: Array<{ question: string; answer: string; correct_label: Label; why: string }>;
  markdown: string;
  costUsd: number;
};

export type CheckOptions = {
  force?: boolean;
  limit?: number;
  sync?: boolean;
};

export type ExportOptions = {
  disagreements?: boolean;
  pairs?: boolean;
  formats?: string[];
};

export type CreateCompareProjectInput = {
  name: string;
  baselineRoot: string;
  dataPath: string;
  mapping: ColumnMapping;
};

export type CheckEstimate = {
  examples: number;
  syncUsd: number | null;
  batchUsd: number | null;
  raw: string;
};

export type CheckRunResult = {
  state: ProjectState;
  code: number | null;
  cancelled: boolean;
  output: string;
};

export type ExportResult = ProjectState & {
  output: string;
};

export type DisagreementRecord = {
  id: string;
  question: string;
  answer: string;
  label: Label;
  note?: string | null;
  agent_recommendation?: "p" | "f" | null;
  agent_category?: string | null;
  agent_confidence?: number | null;
  agent_reasoning?: string | null;
  agreed_with_agent?: boolean | null;
};

export type CliProgress = {
  projectRoot: string;
  line: string;
};
