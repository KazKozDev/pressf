import { BrowserWindow, app, dialog, ipcMain, shell } from "electron";
import { readFileSync } from "node:fs";
import path from "node:path";
import chokidar from "chokidar";
import Store from "electron-store";
import {
  createDemoProject,
  createCompareProjectFromBaseline,
  createProjectFromInputs,
  deleteProject,
  addAnswers,
  decide,
  decideById,
  decidePairwise,
  decideSelfCheck,
  hasAnyApiKey,
  inspectDataFile,
  listProjects,
  loadProjectState,
  parseEstimate,
  buildExportArgs,
  buildCheckArgs,
  projectPaths,
  applyCalibrationProposal,
  buildBotRunArgs,
  nextBotRunPath,
  parseCalibrationProposal,
  readJsonl,
  readProjectBotConfig,
  readProjectRetrieverConfig,
  runLazy,
  updateProjectBot,
  updateProjectRetriever,
  writeApiKey,
  readProjectConfigView,
  updateProjectLlm,
  undo,
  undoPairwise,
  startSelfCheck
} from "./projectData.js";
import type { BotUpdate, CheckOptions, CreateCompareProjectInput, CreateProjectInput, DisagreementRecord, ExportOptions, Label, LlmProvider, LlmUpdate, PairwiseShownLeft, PairwiseWinner, RetrieverUpdate } from "./types.js";

let mainWindow: BrowserWindow | null = null;
const watchers = new Map<string, ReturnType<typeof chokidar.watch>>();
const activeChecks = new Map<string, AbortController>();
const activeBotRuns = new Map<string, AbortController>();
// Under e2e, scope persisted flags to the test's PRESSF_HOME so onboarding/coach state
// doesn't leak between runs via the shared userData dir.
const store = new Store<{ reviewCoachSeen?: boolean; onboardingSeen?: boolean; annotatorName?: string }>(
  process.env.PRESSF_E2E === "1" && process.env.PRESSF_HOME ? { cwd: process.env.PRESSF_HOME } : undefined
);

function annotatorName(): string | undefined {
  const name = store.get("annotatorName");
  return typeof name === "string" && name.trim() ? name.trim() : undefined;
}

// Auto-update: a silent no-op unless a release feed is configured. Only runs in a
// packaged build, never in dev or e2e, never blocks startup.
async function maybeCheckForUpdates() {
  if (process.env.PRESSF_E2E === "1" || !app.isPackaged) return;
  if (!process.env.PRESSF_UPDATE_FEED && !process.env.GH_TOKEN) return; // no feed → do nothing
  try {
    const { autoUpdater } = await import("electron-updater");
    if (process.env.PRESSF_UPDATE_FEED) {
      autoUpdater.setFeedURL({ provider: "generic", url: process.env.PRESSF_UPDATE_FEED });
    }
    autoUpdater.autoDownload = true;
    await autoUpdater.checkForUpdatesAndNotify();
  } catch {
    // never let update checks affect the app
  }
}

function rendererUrl() {
  return process.env.VITE_DEV_SERVER_URL || `file://${path.join(app.getAppPath(), "dist", "renderer", "index.html")}`;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: "PressF",
    show: process.env.PRESSF_E2E !== "1",
    backgroundColor: "#e9eef5",
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(app.getAppPath(), "dist", "main", "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  void mainWindow.loadURL(rendererUrl());
}

// The packaged app may legitimately be open while the isolated Electron e2e
// harness starts. Its test-only home must not be rejected as a duplicate.
const gotSingleInstanceLock = process.env.PRESSF_E2E === "1" || app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  // Another PressF window is already running (or launching): don't start a second
  // process — focus the existing one instead. Prevents duplicate/half-initialized
  // windows when the app is double-clicked more than once, or clicked while a
  // fresh build is still being written to disk.
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(() => {
    createWindow();
    void maybeCheckForUpdates();
  });
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}

ipcMain.handle("projects:list", () => listProjects());
ipcMain.handle("projects:demo", (_event, task?: string) => createDemoProject(task));
ipcMain.handle("projects:state", (_event, root: string) => loadProjectState(root));
ipcMain.handle("projects:create", (_event, input: CreateProjectInput) => createProjectFromInputs(input));
ipcMain.handle("projects:delete", (_event, root: string) => deleteProject(root));
ipcMain.handle("config:read", (_event, root: string) => readProjectConfigView(root));
ipcMain.handle("config:updateLlm", (_event, root: string, update: LlmUpdate) => updateProjectLlm(root, update));
ipcMain.handle("config:readBot", (_event, root: string) => readProjectBotConfig(root));
ipcMain.handle("config:updateBot", (_event, root: string, update: BotUpdate) => updateProjectBot(root, update));
ipcMain.handle("config:readRetriever", (_event, root: string) => readProjectRetrieverConfig(root));
ipcMain.handle("config:updateRetriever", (_event, root: string, update: RetrieverUpdate) => updateProjectRetriever(root, update));
ipcMain.handle("projects:createCompare", (_event, input: CreateCompareProjectInput) => createCompareProjectFromBaseline(input));
ipcMain.handle("project:add", (_event, root: string, file: string, mapping) => addAnswers(root, file, mapping));
ipcMain.handle("review:decide", (_event, root: string, label: Label, note?: string, elapsedMs?: number) => decide(root, label, note, elapsedMs, annotatorName()));
ipcMain.handle("review:decideById", (_event, root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number) => decideById(root, exampleId, label, note, elapsedMs, annotatorName()));
ipcMain.handle("review:selfCheckStart", (_event, root: string, fraction?: number) => startSelfCheck(root, fraction));
ipcMain.handle("review:decideSelfCheck", (_event, root: string, exampleId: string, label: Label, note?: string, elapsedMs?: number) => decideSelfCheck(root, exampleId, label, note, elapsedMs, annotatorName()));
ipcMain.handle("review:decidePairwise", (_event, root: string, exampleId: string, winner: PairwiseWinner, shownLeft: PairwiseShownLeft, note?: string, elapsedMs?: number) => decidePairwise(root, exampleId, winner, shownLeft, note, elapsedMs, annotatorName()));
ipcMain.handle("review:undo", (_event, root: string) => undo(root, annotatorName()));
ipcMain.handle("review:undoPairwise", (_event, root: string) => undoPairwise(root, annotatorName()));
ipcMain.handle("annotator:get", () => store.get("annotatorName") ?? "");
ipcMain.handle("annotator:set", (_event, name: string) => store.set("annotatorName", String(name ?? "").trim()));
ipcMain.handle("data:inspect", (_event, file: string) => inspectDataFile(file));
ipcMain.handle("key:save", (_event, provider: LlmProvider, key: string) => writeApiKey(provider, key));
ipcMain.handle("key:has", (_event, provider?: LlmProvider) => hasAnyApiKey(provider));
ipcMain.handle("file:open", (_event, file: string) => shell.openPath(file));
ipcMain.handle("link:open", (_event, url: string) => {
  if (/^(https?:|mailto:)/.test(url)) return shell.openExternal(url);
  return Promise.resolve();
});
ipcMain.handle("file:reveal", (_event, file: string) => shell.showItemInFolder(file));
ipcMain.handle("coach:get", () => process.env.PRESSF_E2E === "1" || Boolean(store.get("reviewCoachSeen")));
ipcMain.handle("coach:set", (_event, seen: boolean) => store.set("reviewCoachSeen", seen));
// Onboarding defaults to "seen" under E2E so existing journeys aren't disrupted;
// a test opts in to see it with PRESSF_E2E_ONBOARDING=1.
ipcMain.handle("onboarding:get", () =>
  (process.env.PRESSF_E2E === "1" && process.env.PRESSF_E2E_ONBOARDING !== "1")
    ? true
    : Boolean(store.get("onboardingSeen")));
ipcMain.handle("onboarding:set", (_event, seen: boolean) => store.set("onboardingSeen", seen));

ipcMain.handle("dialog:dataFile", async () => {
  const result = await dialog.showOpenDialog({
    title: "Choose a questions and answers file",
    properties: ["openFile"],
    filters: [{ name: "Data files", extensions: ["csv", "tsv", "json", "jsonl", "ndjson"] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("dialog:docsFolder", async () => {
  const result = await dialog.showOpenDialog({
    title: "Choose the documentation folder",
    properties: ["openDirectory"]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("dialog:chunksFile", async () => {
  const result = await dialog.showOpenDialog({
    title: "Choose the exported chunks file",
    properties: ["openFile"],
    filters: [{ name: "Chunks (JSONL)", extensions: ["jsonl", "ndjson", "json"] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("check:estimate", async (_event, root: string, options: CheckOptions = {}) => {
  if (!hasAnyApiKey(loadProjectState(root).llmProvider)) {
    throw new Error("NO_API_KEY");
  }
  const state = loadProjectState(root);
  const result = await runLazy(buildCheckArgs(root, options, true));
  return parseEstimate(result.output, state.examples.length);
});

ipcMain.handle("check:run", async (event, root: string, options: CheckOptions = {}) => {
  if (!hasAnyApiKey(loadProjectState(root).llmProvider)) {
    throw new Error("NO_API_KEY");
  }
  if (activeChecks.has(root)) throw new Error("CHECK_IN_PROGRESS");
  const controller = new AbortController();
  activeChecks.set(root, controller);
  try {
    const result = await runLazy(buildCheckArgs(root, options), (line) => {
      event.sender.send("check:progress", { projectRoot: root, line });
    }, controller.signal);
    const line = result.cancelled
      ? "Judge check cancelled."
      : result.code === 0
        ? "Judge check finished."
        : "Judge check stopped with an error.";
    event.sender.send("check:progress", { projectRoot: root, line });
    return { state: loadProjectState(root), ...result };
  } finally {
    activeChecks.delete(root);
  }
});

ipcMain.handle("check:cancel", (_event, root: string) => {
  const controller = activeChecks.get(root);
  if (!controller) return false;
  controller.abort();
  return true;
});

ipcMain.handle("bot:run", async (event, root: string) => {
  if (activeBotRuns.has(root)) throw new Error("BOT_RUN_IN_PROGRESS");
  const controller = new AbortController();
  activeBotRuns.set(root, controller);
  const file = nextBotRunPath(root);
  try {
    const result = await runLazy(buildBotRunArgs(root, file), (line) => {
      event.sender.send("bot:progress", { projectRoot: root, line });
    }, controller.signal);
    event.sender.send("bot:progress", {
      projectRoot: root,
      line: result.cancelled ? "Bot run cancelled." : result.code === 0 ? "Bot run finished." : "Bot run stopped with an error."
    });
    return { ...result, file };
  } finally {
    activeBotRuns.delete(root);
  }
});

ipcMain.handle("bot:cancel", (_event, root: string) => {
  const controller = activeBotRuns.get(root);
  if (!controller) return false;
  controller.abort();
  return true;
});

ipcMain.handle("calibrate:propose", async (_event, root: string) => {
  const fixture = process.env.PRESSF_CALIBRATION_FIXTURE;
  if (fixture) return parseCalibrationProposal(readFileSync(fixture, "utf8"));
  const result = await runLazy(["calibrate", root, "--dry-run"]);
  if (result.code !== 0) throw new Error(result.output || "Calibration proposal failed.");
  return parseCalibrationProposal(result.output);
});

ipcMain.handle("calibrate:apply", (_event, root: string, markdown: string) => applyCalibrationProposal(root, markdown));

ipcMain.handle("export:run", async (_event, root: string, options: ExportOptions = {}) => {
  const result = await runLazy(buildExportArgs(root, options));
  return { ...loadProjectState(root), output: result.output };
});

ipcMain.handle("export:disagreements", async (_event, root: string): Promise<DisagreementRecord[]> => {
  await runLazy(["export", root, "--disagreements"]);
  return readJsonl<DisagreementRecord>(projectPaths(root).disagreements);
});

ipcMain.handle("watch:start", (_event, root: string) => {
  if (watchers.has(root)) return;
  const paths = projectPaths(root);
  const watcher = chokidar.watch([paths.examples, paths.verdicts, paths.annotations, paths.pairwiseAnnotations, paths.config], { ignoreInitial: true });
  watcher.on("all", () => {
    mainWindow?.webContents.send("project:changed", loadProjectState(root));
  });
  watchers.set(root, watcher);
});
