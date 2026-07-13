import { contextBridge, ipcRenderer } from "electron";
import type { BotConfigView, BotRunResult, BotUpdate, CalibrationProposal, CheckEstimate, CheckOptions, CheckRunResult, CliProgress, CreateCompareProjectInput, CreateProjectInput, DataInspection, DisagreementRecord, ExportOptions, ExportResult, Label, LlmProvider, LlmUpdate, PairwiseShownLeft, PairwiseWinner, ProjectConfigView, ProjectState, ProjectSummary, RetrieverConfigView, RetrieverUpdate } from "./types.js";

const api = {
  listProjects: (): Promise<ProjectSummary[]> => ipcRenderer.invoke("projects:list"),
  deleteProject: (root: string): Promise<ProjectSummary[]> => ipcRenderer.invoke("projects:delete", root),
  createDemo: (task?: string): Promise<ProjectState> => ipcRenderer.invoke("projects:demo", task),
  projectState: (root: string): Promise<ProjectState> => ipcRenderer.invoke("projects:state", root),
  createProject: (input: CreateProjectInput): Promise<ProjectState> => ipcRenderer.invoke("projects:create", input),
  createCompareProject: (input: CreateCompareProjectInput): Promise<ProjectState> => ipcRenderer.invoke("projects:createCompare", input),
  readConfig: (root: string): Promise<ProjectConfigView> => ipcRenderer.invoke("config:read", root),
  updateLlm: (root: string, update: LlmUpdate): Promise<ProjectState> => ipcRenderer.invoke("config:updateLlm", root, update),
  readBotConfig: (root: string): Promise<BotConfigView> => ipcRenderer.invoke("config:readBot", root),
  updateBot: (root: string, update: BotUpdate): Promise<ProjectState> => ipcRenderer.invoke("config:updateBot", root, update),
  readRetrieverConfig: (root: string): Promise<RetrieverConfigView> => ipcRenderer.invoke("config:readRetriever", root),
  updateRetriever: (root: string, update: RetrieverUpdate): Promise<ProjectState> => ipcRenderer.invoke("config:updateRetriever", root, update),
  addAnswers: (root: string, file: string, mapping: import("./types.js").ColumnMapping): Promise<ProjectState> => ipcRenderer.invoke("project:add", root, file, mapping),
  chooseDataFile: (): Promise<string | null> => ipcRenderer.invoke("dialog:dataFile"),
  chooseDocsFolder: (): Promise<string | null> => ipcRenderer.invoke("dialog:docsFolder"),
  chooseChunksFile: (): Promise<string | null> => ipcRenderer.invoke("dialog:chunksFile"),
  inspectDataFile: (file: string): Promise<DataInspection> => ipcRenderer.invoke("data:inspect", file),
  estimateCheck: (root: string, options?: CheckOptions): Promise<CheckEstimate> => ipcRenderer.invoke("check:estimate", root, options),
  runCheck: (root: string, options?: CheckOptions): Promise<CheckRunResult> => ipcRenderer.invoke("check:run", root, options),
  cancelCheck: (root: string): Promise<boolean> => ipcRenderer.invoke("check:cancel", root),
  runBot: (root: string): Promise<BotRunResult> => ipcRenderer.invoke("bot:run", root),
  cancelBot: (root: string): Promise<boolean> => ipcRenderer.invoke("bot:cancel", root),
  proposeCalibration: (root: string): Promise<CalibrationProposal> => ipcRenderer.invoke("calibrate:propose", root),
  applyCalibration: (root: string, markdown: string): Promise<ProjectState> => ipcRenderer.invoke("calibrate:apply", root, markdown),
  decide: (root: string, label: Label, note?: string, elapsedMs?: number): Promise<ProjectState> => ipcRenderer.invoke("review:decide", root, label, note, elapsedMs),
  decideById: (root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number): Promise<ProjectState> => ipcRenderer.invoke("review:decideById", root, exampleId, label, note, elapsedMs),
  startSelfCheck: (root: string, fraction?: number): Promise<string[]> => ipcRenderer.invoke("review:selfCheckStart", root, fraction),
  decideSelfCheck: (root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number): Promise<ProjectState> => ipcRenderer.invoke("review:decideSelfCheck", root, exampleId, label, note, elapsedMs),
  decidePairwise: (root: string, exampleId: string, winner: PairwiseWinner, shownLeft: PairwiseShownLeft, note?: string, elapsedMs?: number): Promise<ProjectState> => ipcRenderer.invoke("review:decidePairwise", root, exampleId, winner, shownLeft, note, elapsedMs),
  undo: (root: string): Promise<ProjectState> => ipcRenderer.invoke("review:undo", root),
  undoPairwise: (root: string): Promise<ProjectState> => ipcRenderer.invoke("review:undoPairwise", root),
  runExport: (root: string, options?: ExportOptions): Promise<ExportResult> => ipcRenderer.invoke("export:run", root, options),
  exportDisagreements: (root: string): Promise<DisagreementRecord[]> => ipcRenderer.invoke("export:disagreements", root),
  saveKey: (provider: LlmProvider, key: string): Promise<void> => ipcRenderer.invoke("key:save", provider, key),
  hasKey: (provider?: LlmProvider): Promise<boolean> => ipcRenderer.invoke("key:has", provider),
  openFile: (file: string): Promise<string> => ipcRenderer.invoke("file:open", file),
  openLink: (url: string): Promise<void> => ipcRenderer.invoke("link:open", url),
  revealFile: (file: string): Promise<void> => ipcRenderer.invoke("file:reveal", file),
  getAnnotatorName: (): Promise<string> => ipcRenderer.invoke("annotator:get"),
  setAnnotatorName: (name: string): Promise<void> => ipcRenderer.invoke("annotator:set", name),
  getReviewCoachSeen: (): Promise<boolean> => ipcRenderer.invoke("coach:get"),
  setReviewCoachSeen: (seen: boolean): Promise<void> => ipcRenderer.invoke("coach:set", seen),
  getOnboardingSeen: (): Promise<boolean> => ipcRenderer.invoke("onboarding:get"),
  setOnboardingSeen: (seen: boolean): Promise<void> => ipcRenderer.invoke("onboarding:set", seen),
  watchProject: (root: string): Promise<void> => ipcRenderer.invoke("watch:start", root),
  onProjectChanged: (callback: (state: ProjectState) => void) => {
    const listener = (_event: unknown, state: ProjectState) => callback(state);
    ipcRenderer.on("project:changed", listener);
    return () => ipcRenderer.off("project:changed", listener);
  },
  onCheckProgress: (callback: (progress: CliProgress) => void) => {
    const listener = (_event: unknown, progress: CliProgress) => callback(progress);
    ipcRenderer.on("check:progress", listener);
    return () => ipcRenderer.off("check:progress", listener);
  },
  onBotProgress: (callback: (progress: CliProgress) => void) => {
    const listener = (_event: unknown, progress: CliProgress) => callback(progress);
    ipcRenderer.on("bot:progress", listener);
    return () => ipcRenderer.off("bot:progress", listener);
  }
};

contextBridge.exposeInMainWorld("pressf", api);

export type PressFApi = typeof api;
