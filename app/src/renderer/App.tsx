import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  FileSpreadsheet,
  FolderOpen,
  GitCompareArrows,
  HelpCircle,
  Moon,
  Play,
  Radar,
  RotateCcw,
  Save,
  Plus,
  Settings as SettingsIcon,
  Trash2,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Sun,
  X
} from "lucide-react";
import type { BotConfigView, BotKind, CalibrationProposal, CheckEstimate, CheckOptions, ColumnMapping, DataInspection, DisagreementRecord, Example, Label, LlmProvider, PairwiseShownLeft, PairwiseWinner, ProjectConfigView, ProjectState, ProjectSummary, RetrieverConfigView, TrajectoryStep, TrajectoryStepVerdict, Verdict } from "../main/types";
import { RETRIEVER_KINDS, retrieverSpecFor } from "../main/retrieverSpec";
import { categoryForVerdict, findingCategoryCopy, isSuspicious, proofMarks, trustCaption, type FindingCategory } from "../shared/scanner";
import { effectiveByAnnotator, faithfulnessScore, flagPrecisionRecall, interAnnotatorKappa, judgeHumanPairs, pairwiseSummary, perCategoryAgreement, wilsonInterval } from "../shared/stats";
import { S } from "./strings";
import wordmark from "./assets/wordmark.png";
import "./styles.css";

type Screen = "home" | "name" | "baseline" | "answers" | "docs" | "judge" | "columns" | "ready" | "scan" | "hub" | "list" | "card" | "finish" | "disagreements" | "judgeEvaluation" | "judgeCase" | "key" | "addAnswers" | "help";
type ReviewMode = "suspicious" | "fine" | FindingCategory;
type ReviewOrder = "confidence" | "informative" | "random" | "original";
type ModuleTask = "rag_faithfulness" | "policy_compliance" | "retrieval_quality" | "pairwise_compare" | "agent_trajectory";
type Theme = "light" | "dark";
type ScanStatus = {
  phase: "running" | "complete" | "cancelled" | "failed";
  message: string;
  reportedChecked: number;
  reportedFlagged: number;
};

function keycap(key: string) {
  return <kbd>{key}</kbd>;
}

function assistantName(state: ProjectState | null, draft: string) {
  return draft.trim() || state?.name || "Helpdesk bot";
}

function evidenceFor(verdict: Verdict | null | undefined) {
  return verdict?.claims?.flatMap((claim) => claim.evidence.map((ev) => ({ ...ev, claim: claim.text, status: claim.status }))) ?? [];
}

function bestEvidence(verdict: Verdict | null | undefined) {
  return evidenceFor(verdict)[0] ?? null;
}

function reviewedCount(state: ProjectState | null) {
  if (!state) return 0;
  return state.task === "pairwise_compare" ? Object.keys(state.pairwiseEffective).length : Object.keys(state.effective).length;
}

function projectCounts(state: ProjectState | null) {
  if (!state) return { total: 0, suspicious: 0, fine: 0 };
  if (state.task === "pairwise_compare") return { total: state.examples.length, suspicious: state.queue.length, fine: state.examples.length - state.queue.length };
  const suspicious = state.examples.filter((example) => isSuspicious(state.verdicts[example.id])).length;
  return { total: state.examples.length, suspicious, fine: state.examples.length - suspicious };
}

function suspiciousTitle(state: ProjectState | null) {
  if (state?.task === "policy_compliance") return S.tasks.suspiciousTitle.policy_compliance;
  if (state?.task === "retrieval_quality") return S.tasks.suspiciousTitle.retrieval_quality;
  if (state?.task === "pairwise_compare") return S.tasks.suspiciousTitle.pairwise_compare;
  if (state?.task === "agent_trajectory") return S.tasks.suspiciousTitle.agent_trajectory;
  return S.tasks.suspiciousTitle.rag_faithfulness;
}

function moduleName(task: ModuleTask) {
  if (task === "policy_compliance") return S.modules.policy;
  if (task === "retrieval_quality") return S.modules.search;
  if (task === "pairwise_compare") return S.modules.compare;
  if (task === "agent_trajectory") return S.modules.trajectory;
  return S.moduleTruth;
}

function homeTitle(task: ModuleTask) {
  return S.tasks.homeTitle[task];
}

function homeSubtitle(task: ModuleTask) {
  return S.tasks.subtitle[task];
}

function homeSteps(task: ModuleTask) {
  return S.tasks.steps[task];
}

function docsQuestion(task: ModuleTask, assistant: string) {
  if (task === "policy_compliance") return S.interview.rulesQ(assistant);
  if (task === "retrieval_quality") return S.interview.searchQ(assistant);
  if (task === "pairwise_compare") return S.interview.docsQ(assistant);
  return S.interview.docsQ(assistant);
}

function answersQuestion(task: ModuleTask, assistant: string) {
  if (task === "policy_compliance") return S.interview.policyAnswersQ(assistant);
  if (task === "retrieval_quality") return S.interview.searchAnswersQ(assistant);
  if (task === "pairwise_compare") return S.interview.newAnswersQ(assistant);
  if (task === "agent_trajectory") return S.interview.tracesQ(assistant);
  return S.interview.answersQ(assistant);
}

function docsHint(task: ModuleTask) {
  if (task === "policy_compliance") return S.interview.rulesHint;
  if (task === "retrieval_quality") return S.interview.searchHint;
  return S.interview.docsHint;
}

function evidenceHeading(task: string) {
  if (task === "policy_compliance") return S.card.rulesSay;
  if (task === "retrieval_quality") return S.card.searchFound;
  return S.card.docsSay;
}

function categoryCounts(state: ProjectState | null) {
  const counts = new Map<FindingCategory, Example[]>();
  if (!state) return counts;
  for (const example of state.examples) {
    const verdict = state.verdicts[example.id];
    const category = categoryForVerdict(verdict);
    if (!counts.has(category)) counts.set(category, []);
    counts.get(category)!.push(example);
  }
  return counts;
}

// "informative" is active learning: answers where the judge sat right at the 0.7 flag
// threshold teach the calibration most, so they go first. Verdict-less examples lead.
function orderKey(verdict: Verdict | null | undefined, order: ReviewOrder) {
  if (!verdict) return -1;
  return order === "informative" ? Math.abs(verdict.confidence - 0.7) : verdict.confidence;
}

function idsForMode(state: ProjectState | null, mode: ReviewMode, order: ReviewOrder = "confidence") {
  if (!state) return [];
  if (state.task === "pairwise_compare") {
    if (mode === "fine") return [];
    return state.examples
      .filter((example) => !state.pairwiseEffective[example.id])
      .map((example) => example.id);
  }
  return state.examples
    .filter((example) => {
      const verdict = state.verdicts[example.id];
      if (mode === "suspicious") return isSuspicious(verdict);
      if (mode === "fine") return !isSuspicious(verdict);
      return categoryForVerdict(verdict) === mode;
    })
    .filter((example) => !state.effective[example.id])
    .sort((a, b) => order === "original" ? 0 : order === "random" ? Math.random() - 0.5 : orderKey(state.verdicts[a.id], order) - orderKey(state.verdicts[b.id], order))
    .map((example) => example.id);
}

function firstCardId(state: ProjectState | null, mode: ReviewMode, order: ReviewOrder = "confidence") {
  return idsForMode(state, mode, order)[0] ?? null;
}

function shownLeftFor(id: string): PairwiseShownLeft {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % 2 === 0 ? "a" : "b";
}

function Rail({ activeTask, onSelectTask, devOpen, setDevOpen, theme, onThemeToggle, onHelp }: { activeTask: ModuleTask; onSelectTask: (task: ModuleTask) => void; devOpen: boolean; setDevOpen: (open: boolean) => void; theme: Theme; onThemeToggle: () => void; onHelp: () => void }) {
  const items: Array<{ task: ModuleTask; label: string; icon: React.ReactNode }> = [
    { task: "rag_faithfulness", label: S.moduleTruth, icon: <ShieldCheck size={15} /> },
    { task: "policy_compliance", label: S.modules.policy, icon: <ClipboardCheck size={15} /> },
    { task: "retrieval_quality", label: S.modules.search, icon: <SearchCheck size={15} /> },
    { task: "pairwise_compare", label: S.modules.compare, icon: <GitCompareArrows size={15} /> },
    { task: "agent_trajectory", label: S.modules.trajectory, icon: <Radar size={15} /> }
  ];
  return (
    <aside className="rail">
      <div className="sidebarBrand">
        <img className="brandImg" src={wordmark} alt={S.appName} />
      </div>
      <nav aria-label="Evaluation modules">
        {items.map((item) => <button key={item.task} className={`railItem ${activeTask === item.task ? "active" : ""}`} onClick={() => onSelectTask(item.task)}>{item.icon}<span>{item.label}</span></button>)}
      </nav>
      <div className="sidebarFooter">
        <button className="railTool" aria-label={S.help.nav} title={S.help.nav} onClick={onHelp}><HelpCircle size={17} /></button>
        <button className="railTool" aria-label={S.dev.title} title={S.dev.title} onClick={() => setDevOpen(!devOpen)}><SettingsIcon size={17} /></button>
        <button className="railTool" aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"} title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"} onClick={onThemeToggle}>{theme === "light" ? <Moon size={17} /> : <Sun size={17} />}</button>
      </div>
    </aside>
  );
}

function DeveloperPanel({ state, onState, onClose }: { state: ProjectState | null; onState: (next: ProjectState) => void; onClose: () => void }) {
  const [cfg, setCfg] = useState<ProjectConfigView | null>(null);
  const [bot, setBot] = useState<BotConfigView | null>(null);
  const [provider, setProvider] = useState<LlmProvider>("anthropic");
  const [judgeModel, setJudgeModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [budget, setBudget] = useState("10");
  const [escalationModel, setEscalationModel] = useState("");
  const [escalationThreshold, setEscalationThreshold] = useState("0.7");
  const [saved, setSaved] = useState(false);
  const [botSaved, setBotSaved] = useState(false);
  const [error, setError] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [reviewerSaved, setReviewerSaved] = useState(false);
  const [retriever, setRetriever] = useState<RetrieverConfigView | null>(null);
  const [retrieverSaved, setRetrieverSaved] = useState(false);

  useEffect(() => {
    void window.pressf.getAnnotatorName().then(setReviewer);
  }, []);

  useEffect(() => {
    if (!state) { setCfg(null); setBot(null); setRetriever(null); return; }
    void Promise.all([window.pressf.readConfig(state.root), window.pressf.readBotConfig(state.root), window.pressf.readRetrieverConfig(state.root)]).then(([view, botView, retrieverView]) => {
      setCfg(view);
      setBot(botView);
      setRetriever(retrieverView);
      setProvider(view.provider);
      setJudgeModel(view.judgeModel);
      setBaseUrl(view.baseUrl ?? "");
      setBudget(String(view.maxBudgetUsd));
      setEscalationModel(view.escalationModel ?? "");
      setEscalationThreshold(String(view.escalationThreshold));
    });
  }, [state?.root]);

  async function save() {
    if (!state) return;
    setError(""); setSaved(false);
    try {
      const next = await window.pressf.updateLlm(state.root, {
        provider,
        judgeModel: judgeModel.trim() || undefined,
        baseUrl: baseUrl.trim() || undefined,
        maxBudgetUsd: Number(budget) || undefined,
        escalationModel,
        escalationThreshold: escalationThreshold.trim() === "" ? undefined : Number(escalationThreshold)
      });
      onState(next);
      const view = await window.pressf.readConfig(state.root);
      setCfg(view);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveReviewer() {
    setReviewerSaved(false);
    await window.pressf.setAnnotatorName(reviewer.trim());
    setReviewerSaved(true);
  }

  async function saveRetriever() {
    if (!state || !retriever) return;
    setError(""); setRetrieverSaved(false);
    try {
      const next = await window.pressf.updateRetriever(state.root, { kind: retriever.kind, topK: retriever.topK, params: retriever.params });
      onState(next);
      setRetriever(await window.pressf.readRetrieverConfig(state.root));
      setRetrieverSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveBot() {
    if (!state || !bot) return;
    setError(""); setBotSaved(false);
    try {
      const next = await window.pressf.updateBot(state.root, bot);
      onState(next);
      setBot(await window.pressf.readBotConfig(state.root));
      setBotSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="devPanel">
      <button className="iconOnly" aria-label={S.close} onClick={onClose}><X size={18} /></button>
      <h2>{S.dev.title}</h2>
      <p>{S.dev.body}</p>
      <h3>{S.dev.reviewerHeading}</h3>
      <label className="devField"><span>{S.dev.reviewerName}</span>
        <input aria-label={S.dev.reviewerName} value={reviewer} onChange={(e) => { setReviewer(e.target.value); setReviewerSaved(false); }} placeholder="alice" />
      </label>
      <p className="devNote">{S.dev.reviewerHint}</p>
      <button onClick={saveReviewer}>{S.dev.reviewerSave}</button>
      {reviewerSaved && <p className="devSaved">{S.dev.reviewerSaved}</p>}
      {!state ? (
        <p className="devNote">{S.dev.noProject}</p>
      ) : (
        <>
          <h3>{S.dev.judgeHeading}</h3>
          <label className="devField"><span>{S.dev.provider}</span>
            <select value={provider} onChange={(e) => { setProvider(e.target.value as LlmProvider); setSaved(false); }}>
              <option value="anthropic">{S.dev.providerAnthropic}</option>
              <option value="openai">{S.dev.providerOpenai}</option>
              <option value="openai_compatible">{S.dev.providerCompatible}</option>
            </select>
          </label>
          <label className="devField"><span>{S.dev.judgeModel}</span>
            <input value={judgeModel} onChange={(e) => { setJudgeModel(e.target.value); setSaved(false); }} placeholder={provider === "openai" ? "gpt-5.4-mini" : provider === "openai_compatible" ? "llama3.3:70b" : "claude-haiku-4-5"} />
          </label>
          {provider === "openai_compatible" && (
            <label className="devField"><span>{S.dev.baseUrl}</span>
              <input value={baseUrl} onChange={(e) => { setBaseUrl(e.target.value); setSaved(false); }} placeholder={S.dev.baseUrlPlaceholder} />
            </label>
          )}
          <label className="devField"><span>{S.dev.escalation}</span>
            <input aria-label={S.dev.escalation} value={escalationModel} onChange={(e) => { setEscalationModel(e.target.value); setSaved(false); }} placeholder={provider === "openai" ? "gpt-5.4" : provider === "anthropic" ? "claude-opus-4-8" : ""} />
          </label>
          <p className="devNote">{S.dev.escalationHint}</p>
          <label className="devField"><span>{S.dev.escalationThreshold}</span>
            <input aria-label={S.dev.escalationThreshold} type="number" min="0" max="1" step="0.05" value={escalationThreshold} onChange={(e) => { setEscalationThreshold(e.target.value); setSaved(false); }} />
          </label>
          <label className="devField"><span>{S.dev.budget}</span>
            <input type="number" min="1" step="1" value={budget} onChange={(e) => { setBudget(e.target.value); setSaved(false); }} />
          </label>
          <p className="devNote">{S.dev.keyHint}</p>
          <button className="primaryAction" onClick={save}>{S.dev.save}</button>
          {saved && <p className="devSaved">{S.dev.saved}</p>}
          {error && <p className="devError">{error}</p>}

          {bot && <>
            <h3>{S.dev.botHeading}</h3>
            <label className="devField"><span>{S.dev.botKind}</span>
              <select value={bot.kind} onChange={(e) => { setBot({ ...bot, kind: e.target.value as BotKind }); setBotSaved(false); }}>
                <option value="command">Command</option>
                <option value="http">HTTP</option>
              </select>
            </label>
            {bot.kind === "command" ? (
              <label className="devField"><span>{S.dev.botCommand}</span>
                <input aria-label={S.dev.botCommand} value={bot.command} placeholder="python bot.py {question}" onChange={(e) => { setBot({ ...bot, command: e.target.value }); setBotSaved(false); }} />
              </label>
            ) : <>
              <label className="devField"><span>{S.dev.botUrl}</span>
                <input aria-label={S.dev.botUrl} value={bot.url} placeholder="https://example.com/ask" onChange={(e) => { setBot({ ...bot, url: e.target.value }); setBotSaved(false); }} />
              </label>
              <label className="devField"><span>{S.dev.botMethod}</span>
                <input aria-label={S.dev.botMethod} value={bot.method} onChange={(e) => { setBot({ ...bot, method: e.target.value }); setBotSaved(false); }} />
              </label>
              <label className="devField"><span>{S.dev.botHeaders}</span>
                <textarea aria-label={S.dev.botHeaders} value={bot.headers} onChange={(e) => { setBot({ ...bot, headers: e.target.value }); setBotSaved(false); }} />
              </label>
              <label className="devField"><span>{S.dev.botBody}</span>
                <textarea aria-label={S.dev.botBody} value={bot.body} placeholder={'{"question":"{question}"}'} onChange={(e) => { setBot({ ...bot, body: e.target.value }); setBotSaved(false); }} />
              </label>
              <label className="devField"><span>{S.dev.botAnswerPath}</span>
                <input aria-label={S.dev.botAnswerPath} value={bot.answerPath} placeholder="answer" onChange={(e) => { setBot({ ...bot, answerPath: e.target.value }); setBotSaved(false); }} />
              </label>
            </>}
            <label className="devField"><span>{S.dev.botTimeout}</span>
              <input aria-label={S.dev.botTimeout} type="number" min="1" value={bot.timeout} onChange={(e) => { setBot({ ...bot, timeout: Number(e.target.value) }); setBotSaved(false); }} />
            </label>
            <button className="primaryAction" onClick={saveBot}>{S.dev.botSave}</button>
            {botSaved && <p className="devSaved">{S.dev.botSaved}</p>}
          </>}

          {state.task !== "agent_trajectory" && <><h3>{S.dev.retrieverHeading}</h3>
          {retriever && <>
            <p className="devNote">{S.dev.retrieverHint}</p>
            <label className="devField"><span>{S.dev.retrieverKind}</span>
              <select aria-label={S.dev.retrieverKind} value={retriever.kind} onChange={(e) => { setRetriever({ ...retriever, kind: e.target.value }); setRetrieverSaved(false); }}>
                {RETRIEVER_KINDS.map((spec) => <option key={spec.kind} value={spec.kind}>{spec.label}</option>)}
              </select>
            </label>
            {retrieverSpecFor(retriever.kind).fields.map((field) => (
              <label className="devField" key={field.key}><span>{field.label}</span>
                <input aria-label={field.label} value={retriever.params[field.key] ?? ""} placeholder={field.placeholder} onChange={(e) => { setRetriever({ ...retriever, params: { ...retriever.params, [field.key]: e.target.value } }); setRetrieverSaved(false); }} />
              </label>
            ))}
            <label className="devField"><span>{S.dev.retrieverTopK}</span>
              <input aria-label={S.dev.retrieverTopK} type="number" min="1" step="1" value={retriever.topK} onChange={(e) => { setRetriever({ ...retriever, topK: Number(e.target.value) }); setRetrieverSaved(false); }} />
            </label>
            <button className="primaryAction" onClick={saveRetriever}>{S.dev.retrieverSave}</button>
            {retrieverSaved && <p className="devSaved">{S.dev.retrieverSaved}</p>}
          </>}</>}

          <h3>{S.dev.files}</h3>
          <button onClick={() => window.pressf.openFile(state.paths.examples)}>{S.developerFiles.examples}</button>
          <button onClick={() => window.pressf.openFile(state.paths.verdicts)}>{S.developerFiles.verdicts}</button>
          <button onClick={() => window.pressf.openFile(state.paths.annotations)}>{S.developerFiles.annotations}</button>
          <h3>{S.dev.command}</h3>
          <code>{S.developerFiles.exportCommand(state.root)}</code>
        </>
      )}
    </div>
  );
}

function Home({ projects, activeTask, onCheck, onDemo, onOpen, onDelete }: { projects: ProjectSummary[]; activeTask: ModuleTask; onCheck: () => void; onDemo: () => void; onOpen: (root: string) => void; onDelete: (root: string) => void }) {
  const moduleProjects = projects.filter((project) => project.task === activeTask);
  const activeProjects = moduleProjects.filter((project) => project.station !== "results");
  const reviewed = moduleProjects.reduce((total, project) => total + project.done, 0);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  return (
    <main className="workspaceHome mainPath" data-testid="main-path">
      <header className="workspaceHeader">
        <div className="workspaceIdentity">
          <div><p className="sectionEyebrow">{moduleName(activeTask)}</p><h1>{S.home.workspaceTitle}</h1></div>
          <p className="subtitle">{homeSubtitle(activeTask)}</p>
        </div>
        <div className="workspaceActions">
          <button className="primaryAction" onClick={onCheck}>{S.home.newEvaluation}</button>
          <button onClick={() => onDemo()}>{S.home.tryExample}</button>
        </div>
      </header>
      <section className="workspaceMeta" aria-label={S.home.status}>
        <div><strong>{activeProjects.length}</strong><span>{S.home.active}</span></div>
        <div><strong>{reviewed}</strong><span>{S.home.reviewed}</span></div>
        <div><strong>{moduleProjects.length}</strong><span>{S.home.projects}</span></div>
        <details className="howWorks"><summary>{S.home.how}</summary><p>{homeSteps(activeTask).join(" ")}</p></details>
      </section>
      <section className="projectWorkspace" aria-label={S.home.past}>
        <div className="sectionHeading"><div><h2>{S.home.past}</h2><p>{S.home.projectHint}</p></div><span>{moduleProjects.length}</span></div>
        {moduleProjects.length === 0 ? <p className="emptyWorkspace">{S.home.empty}</p> : <div className="projectTable" role="list">{moduleProjects.map((project) => (
          confirmDelete === project.root ? (
          <div className="projectRow projectRowConfirm" key={project.root} role="listitem">
            <span className="projectName"><strong>{project.name}</strong><small>{S.home.removeConfirm}</small></span>
            <div className="rowConfirm">
              <button className="rowDeleteYes" onClick={() => { setConfirmDelete(null); onDelete(project.root); }}><Trash2 size={14} /> {S.home.removeYes}</button>
              <button onClick={() => setConfirmDelete(null)}>{S.home.removeNo}</button>
            </div>
          </div>
          ) : (
          <div className="projectRow" key={project.root} role="listitem">
            <button className="projectOpen" onClick={() => onOpen(project.root)}>
            <span className="projectName"><strong>{project.name}</strong><small>{project.task.replaceAll("_", " ")}</small></span>
            <span>{project.total} {S.home.answers}</span>
            <span>{project.bad} {S.home.flagged}</span>
            <span>{project.done} {S.home.reviewed}</span>
            <span className="projectState">{project.station}</span>
            </button>
            <button className="rowDelete" aria-label={S.home.remove} title={S.home.remove} onClick={() => setConfirmDelete(project.root)}><Trash2 size={15} /></button>
          </div>
          )
        ))}</div>}
      </section>
    </main>
  );
}

function AddAnswersScreen({ state, inspection, file, mapping, onFile, onMapping, onAdd, onBack }: { state: ProjectState; inspection: DataInspection | null; file: string; mapping: ColumnMapping; onFile: (file: string) => void; onMapping: (mapping: ColumnMapping) => void; onAdd: () => void; onBack: () => void }) {
  const expected = state.ingestMapping;
  const needsMapping = Boolean(inspection && expected && (mapping.question !== expected.question || mapping.answer !== expected.answer));
  return (
    <InterviewShell onBack={onBack}>
      <h1>{S.addAnswers.title(state.name)}</h1>
      <p className="readyLine">{S.addAnswers.body}</p>
      <PathPicker label="Answers file" ariaLabel={S.interview.pasteFile} placeholder={S.interview.answersPath} value={file} onChange={onFile} onBlur={() => onFile(file)} onChoose={() => void window.pressf.chooseDataFile().then((next) => next && onFile(next))} chooseLabel={S.interview.chooseFile} />
      {needsMapping && inspection && <div className="columnPicker"><p>{S.addAnswers.mapping}</p><label>{S.interview.questionColumn}<select value={mapping.question} onChange={(event) => onMapping({ ...mapping, question: event.target.value })}>{inspection.headers.map((header) => <option key={header}>{header}</option>)}</select></label><label>{S.interview.answerColumn}<select value={mapping.answer} onChange={(event) => onMapping({ ...mapping, answer: event.target.value })}>{inspection.headers.map((header) => <option key={header}>{header}</option>)}</select></label></div>}
      <button className="primaryAction" disabled={!file || !mapping.question || !mapping.answer} onClick={onAdd}>{S.addAnswers.confirm}</button>
    </InterviewShell>
  );
}

function BotRunSetup({ running, ready, error, onRun }: { running: boolean; ready: boolean; error: string; onRun: () => void }) {
  return (
    <section className="botRunSetup">
      <p>{S.interview.runBotHint}</p>
      <button className="secondaryAction" disabled={running} onClick={onRun}>{running ? S.interview.runningBot : S.interview.runBot}</button>
      {ready && <p className="devSaved">{S.interview.botOutputReady}</p>}
      {error && <p className="devError">{error}</p>}
    </section>
  );
}

function BaselinePicker({ projects, onChoose, onBack }: { projects: ProjectSummary[]; onChoose: (root: string) => void; onBack: () => void }) {
  const baselines = projects.filter((project) => project.task !== "pairwise_compare" && project.total > 0);
  return (
    <main className="interview mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <h1>{S.interview.baselineQ}</h1>
      <p className="readyLine">{S.interview.baselineHint}</p>
      {baselines.length ? <div className="answerRows">{baselines.map((project) => <button className="pastCard" key={project.root} onClick={() => onChoose(project.root)}><strong>{project.name}</strong><span>{project.total} answers · {project.done} reviewed</span></button>)}</div> : <p>{S.interview.noBaseline}</p>}
    </main>
  );
}

function InterviewShell({ children, onBack }: { children: React.ReactNode; onBack: () => void }) {
  return (
    <main className="interview mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      {children}
    </main>
  );
}

function FileShape({ task }: { task: ModuleTask }) {
  const sample = S.interview.fileSamples[task];
  return (
    <div className="fileShape" aria-label={sample.columns.join(" | ")}>
      {sample.columns.map((column) => <div key={column}>{column}</div>)}
      {sample.rows.map((row) => <p key={row}>{row}</p>)}
    </div>
  );
}

function WorkflowGuide({ task }: { task: ModuleTask }) {
  return <details className="workflowGuide"><summary>{S.interview.workflowTitle}</summary><ol>{S.interview.workflowGuide[task].map((step) => <li key={step.label}><strong>{step.label}</strong><span>{step.body}</span></li>)}</ol></details>;
}

function PathPicker({ label, ariaLabel, value, placeholder, onChange, onBlur, onChoose, chooseLabel }: { label: string; ariaLabel: string; value: string; placeholder: string; onChange: (value: string) => void; onBlur?: () => void; onChoose: () => void; chooseLabel: string }) {
  return (
    <div className="pathPicker">
      <label>{label}<input aria-label={ariaLabel} placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} /></label>
      <button type="button" className="choosePath" onClick={onChoose}><FolderOpen size={15} /> {chooseLabel}</button>
    </div>
  );
}

function ScanScreen({ state, status, onDone, onCancel }: { state: ProjectState | null; status: ScanStatus; onDone: () => void; onCancel: () => void }) {
  const counts = projectCounts(state);
  const completedFromFiles = Object.keys(state?.verdicts ?? {}).length;
  const flaggedFromFiles = state?.examples.filter((example) => isSuspicious(state.verdicts[example.id])).length ?? 0;
  const visibleChecked = Math.min(counts.total, Math.max(completedFromFiles, status.reportedChecked));
  const visibleSuspicious = Math.min(counts.total, Math.max(flaggedFromFiles, status.reportedFlagged));
  const findingRows = state?.examples.filter((example) => isSuspicious(state.verdicts[example.id])).slice(0, visibleSuspicious) ?? [];
  const title = status.phase === "complete" ? S.scan.done : status.phase === "cancelled" ? S.scan.cancelled : status.phase === "failed" ? S.scan.failed : S.scan.title;
  return (
    <main className="scanScreen mainPath" data-testid="main-path">
      <section className="scanCenter">
        <div className={`scanRing ${status.phase !== "running" ? "complete" : ""}`}>
          <Radar size={64} />
          <span>{visibleChecked}</span>
        </div>
        <h1>{title}</h1>
        <p>{S.scan.progress(visibleChecked, counts.total, visibleSuspicious)}</p>
        <p className="scanMessage">{status.message}</p>
        {status.phase === "running" ? <button onClick={onCancel}>{S.scan.cancel}</button> : <button className="primaryAction" onClick={onDone}>{S.scan.viewResults}</button>}
      </section>
      <section className="streamList">
        {findingRows.map((example) => (
          <article key={example.id}>
            <strong>{example.question}</strong>
            <span><b>{proofMarks[categoryForVerdict(state?.verdicts[example.id])].mark}</b> {findingCategoryCopy[categoryForVerdict(state?.verdicts[example.id])].title}</span>
          </article>
        ))}
      </section>
    </main>
  );
}

function hubMeta(state: ProjectState) {
  const verdicts = Object.values(state.verdicts);
  if (!verdicts.length) return null;
  const byModel = new Map<string, number>();
  let cost = 0;
  let escalations = 0;
  let confidenceSum = 0;
  let lastRun = "";
  for (const verdict of verdicts) {
    byModel.set(verdict.judge_model, (byModel.get(verdict.judge_model) ?? 0) + 1);
    cost += verdict.cost_usd ?? 0;
    escalations += verdict.escalated ? 1 : 0;
    confidenceSum += verdict.confidence ?? 0;
    if (verdict.created_at && verdict.created_at > lastRun) lastRun = verdict.created_at;
  }
  const model = [...byModel.entries()].sort((a, b) => b[1] - a[1])[0][0];
  return {
    model,
    lastRun: lastRun ? new Date(lastRun).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) : "—",
    cost: `$${cost.toFixed(2)}`,
    escalations,
    meanConfidence: (confidenceSum / verdicts.length).toFixed(2)
  };
}

function gateStrip(state: ProjectState): string {
  const score = faithfulnessScore(state.effective, state.verdicts);
  if (score.source === "none" || score.n === 0) return "";
  const [lo, hi] = wilsonInterval(score.passed, score.n);
  return ` · ${S.hub.meta.faithfulness} ${Math.round(score.faithfulness * 100)}% (${S.gate.ci(`${Math.round(lo * 100)}%`, `${Math.round(hi * 100)}%`)})`;
}

type SortKey = "question" | "category" | "confidence" | "status";

function FlaggedTable({ state, onOpen }: { state: ProjectState; onOpen: (id: string) => void }) {
  const [sortKey, setSortKey] = useState<SortKey>("confidence");
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [category, setCategory] = useState("all");
  const [confidence, setConfidence] = useState("all");
  const allRows = state.examples
    .filter((example) => isSuspicious(state.verdicts[example.id]))
    .map((example) => {
      const verdict = state.verdicts[example.id];
      return {
        id: example.id,
        question: example.question,
        category: findingCategoryCopy[categoryForVerdict(verdict)].title,
        confidence: verdict?.confidence ?? 0,
        reviewed: Boolean(state.effective[example.id])
      };
    })
  const categories = [...new Set(allRows.map((row) => row.category))];
  const rows = allRows
    .filter((row) => category === "all" || row.category === category)
    .filter((row) => confidence === "all" || confidence === "high" && row.confidence >= 0.9 || confidence === "medium" && row.confidence >= 0.7 && row.confidence < 0.9 || confidence === "low" && row.confidence < 0.7)
    .sort((a, b) => {
      if (sortKey === "confidence") return (a.confidence - b.confidence) * sortDir;
      if (sortKey === "status") return (Number(a.reviewed) - Number(b.reviewed)) * sortDir;
      return a[sortKey].localeCompare(b[sortKey]) * sortDir;
    });
  if (!allRows.length) return null;
  const header = (key: SortKey, label: string, numeric = false) => (
    <th className={numeric ? "num" : undefined} aria-sort={sortKey === key ? (sortDir === 1 ? "ascending" : "descending") : "none"}>
      <button onClick={() => (sortKey === key ? setSortDir((dir) => (dir === 1 ? -1 : 1)) : (setSortKey(key), setSortDir(1)))}>
        {label}{sortKey === key ? (sortDir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );
  return (
    <>
      <div className="tableFilters">
        <label>{S.hub.filters.category}<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">{S.hub.filters.all}</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label>{S.hub.filters.confidence}<select value={confidence} onChange={(event) => setConfidence(event.target.value)}><option value="all">{S.hub.filters.all}</option><option value="high">{S.hub.filters.high}</option><option value="medium">{S.hub.filters.medium}</option><option value="low">{S.hub.filters.low}</option></select></label>
      </div>
      <div className="tableWrap">
        <table className="flaggedTable">
        <thead>
          <tr>
            {header("question", S.hub.table.question)}
            {header("category", S.hub.table.category)}
            {header("confidence", S.hub.table.confidence, true)}
            {header("status", S.hub.table.status)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={row.reviewed ? "reviewed" : "pending"} onClick={() => !row.reviewed && onOpen(row.id)}>
              <td title={row.question}>{row.question}</td>
              <td>{row.category}</td>
              <td className="num">{row.confidence.toFixed(2)}</td>
              <td>{row.reviewed ? S.hub.table.reviewed : S.hub.table.pending}</td>
            </tr>
          ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function DisagreementsScreen({ rows, onBack }: { rows: DisagreementRecord[]; onBack: () => void }) {
  return (
    <main className="listScreen mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <h1>{S.disagreements.title}</h1>
      {rows.length ? <div className="answerRows">{rows.map((row) => <article className="disagreementRow" key={row.id}><strong>{row.question}</strong><p>{row.answer}</p><dl><div><dt>{S.disagreements.judge}</dt><dd>{row.agent_recommendation ?? "—"} · {row.agent_category ?? "—"} · {(row.agent_confidence ?? 0).toFixed(2)}</dd></div><div><dt>{S.disagreements.human}</dt><dd>{row.label}</dd></div>{row.note && <div><dt>{S.disagreements.note}</dt><dd>{row.note}</dd></div>}</dl></article>)}</div> : <p>{S.disagreements.none}</p>}
    </main>
  );
}

function Hub({ state, onMode, onList, onOpenCard, onFinish, onAdd, order, onOrder, onSelfCheck, onJudgeEvaluation }: { state: ProjectState; onMode: (mode: ReviewMode) => void; onList: (mode: ReviewMode) => void; onOpenCard: (id: string) => void; onFinish: () => void; onAdd: () => void; order: ReviewOrder; onOrder: (order: ReviewOrder) => void; onSelfCheck: () => void; onJudgeEvaluation: () => void }) {
  const [pairsSaved, setPairsSaved] = useState(false);
  const counts = projectCounts(state);
  const categories = categoryCounts(state);
  const meta = state.task === "pairwise_compare" ? null : hubMeta(state);
  const remainingSuspicious = idsForMode(state, "suspicious").length;
  useEffect(() => {
    if (remainingSuspicious === 0 && reviewedCount(state) > 0) onFinish();
  }, [remainingSuspicious, state.stats.done]);
  return (
    <main className="hub mainPath" data-testid="main-path">
      <section className="bigResult">
        <span>{counts.suspicious}</span>
        <h1>{suspiciousTitle(state)}</h1>
        <p>{S.hub.checked(counts.total)}</p>
        {meta && (
          <dl className="metaRow">
            <div><dt>{S.hub.meta.model}</dt><dd>{meta.model}</dd></div>
            <div><dt>{S.hub.meta.lastRun}</dt><dd>{meta.lastRun}</dd></div>
            <div><dt>{S.hub.meta.cost}</dt><dd>{meta.cost}</dd></div>
            <div><dt>{S.hub.meta.escalations}</dt><dd>{meta.escalations}</dd></div>
          </dl>
        )}
        {meta && counts.total > 0 && (
          <p className="statStrip">
            {S.hub.meta.flaggedShare} {Math.round((counts.suspicious / counts.total) * 100)}% · {S.hub.meta.passShare} {Math.round((counts.fine / counts.total) * 100)}% · {S.hub.meta.meanConfidence} {meta.meanConfidence}{gateStrip(state)}
          </p>
        )}
        <div className="hubPrimaryRow">
          <button className="primaryAction" onClick={() => onMode("suspicious")}>{state.task === "pairwise_compare" ? S.hub.compare : S.hub.primary}</button>
          {state.task !== "pairwise_compare" && <button className="hubFineAction" onClick={() => onMode("fine")}>{S.hub.fine}</button>}
          {state.task !== "pairwise_compare" && <label className="reviewOrder">{S.review.order}<select value={order} onChange={(event) => onOrder(event.target.value as ReviewOrder)}><option value="confidence">{S.review.confidence}</option><option value="informative">{S.review.informative}</option><option value="random">{S.review.random}</option><option value="original">{S.review.original}</option></select></label>}
        </div>
        {state.task !== "pairwise_compare" && (
          <div className="hubActions">
            <button className="hubAction" onClick={onAdd}><Plus size={15} /> {S.addAnswers.action}</button>
            <button className="hubAction" onClick={onSelfCheck}><RotateCcw size={15} /> {S.review.selfCheck}</button>
            <button className="hubAction" onClick={onJudgeEvaluation}><ShieldCheck size={15} /> {S.judgeEvaluation.action}</button>
            <button className="hubAction" onClick={async () => { await window.pressf.runExport(state.root, { pairs: true }); setPairsSaved(true); }}><Save size={15} /> {S.export.pairs}</button>
            {pairsSaved && <button className="hubAction" onClick={() => window.pressf.revealFile(state.paths.pairs)}>{S.export.showPairs}</button>}
          </div>
        )}
      </section>
      {state.task !== "pairwise_compare" && <section className="categoryGrid">
        {((state.task === "policy_compliance" ? ["policy_break", "uncertain"] : state.task === "retrieval_quality" ? ["search_missing", "search_partial", "uncertain"] : state.task === "agent_trajectory" ? ["trajectory_ok", "trajectory_inefficient", "trajectory_unfaithful", "trajectory_unsafe", "trajectory_wrong_answer"] : ["contradicts", "made_up", "bad_refusal", "incomplete", "uncertain"]) as FindingCategory[]).map((category) => {
          const items = categories.get(category) ?? [];
          return (
            <button key={category} className="categoryCard" onClick={() => onList(category)} disabled={items.length === 0}>
              <strong>{items.length}</strong>
              <b className="proofMark" title={proofMarks[category].label}>{proofMarks[category].mark}</b>
              <span>{findingCategoryCopy[category].title}</span>
              <small>{findingCategoryCopy[category].detail}</small>
            </button>
          );
        })}
      </section>}
      {state.task !== "pairwise_compare" && <FlaggedTable state={state} onOpen={onOpenCard} />}
    </main>
  );
}

function CategoryList({ state, mode, onOpen, onBack }: { state: ProjectState; mode: ReviewMode; onOpen: (id: string) => void; onBack: () => void }) {
  const ids = idsForMode(state, mode);
  const title = mode === "suspicious" ? S.hub.title : mode === "fine" ? S.hub.looksFine : findingCategoryCopy[mode].title;
  return (
    <main className="listScreen mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <h1>{title}</h1>
      <div className="answerRows">
        {ids.length === 0 ? <p>{S.hub.none}</p> : ids.map((id) => {
          const example = state.examples.find((item) => item.id === id)!;
          return (
            <button key={id} className="answerRow" onClick={() => onOpen(id)}>
              <span>{example.question}</span>
              <em title={proofMarks[categoryForVerdict(state.verdicts[id])].label}>{proofMarks[categoryForVerdict(state.verdicts[id])].mark} {findingCategoryCopy[categoryForVerdict(state.verdicts[id])].cardWord}</em>
            </button>
          );
        })}
      </div>
    </main>
  );
}

function trajectoryArguments(step: TrajectoryStep) {
  const value = step.tool?.arguments;
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

function TrajectoryReview({ trajectory, issues }: { trajectory: TrajectoryStep[] | null | undefined; issues: TrajectoryStepVerdict[] | null | undefined }) {
  if (!trajectory?.length) return <p className="noDoc">{S.card.noTrajectory}</p>;
  const issuesByStep = new Map((issues ?? []).filter((issue) => !issue.ok).map((issue) => [issue.step_index, issue]));
  return (
    <section className="trajectoryReview" aria-label={S.card.trajectory}>
      <h2>{S.card.trajectory}</h2>
      <ol className="trajectorySteps">
        {trajectory.map((step) => {
          const issue = issuesByStep.get(step.index);
          const label = step.kind === "tool_call" ? S.card.toolCall : step.kind === "answer" ? S.card.finalAnswer : S.card.thought;
          return (
            <li key={`${step.index}-${step.kind}`} className={issue ? "trajectoryStep hasIssue" : "trajectoryStep"}>
              <div className="trajectoryStepHead"><span>{S.card.step(step.index)}</span><strong>{label}</strong></div>
              {step.kind === "tool_call" && step.tool && <div className="toolCallBody">
                <strong className="toolName">{step.tool.name}</strong>
                <dl>
                  <div><dt>{S.card.arguments}</dt><dd><pre>{trajectoryArguments(step)}</pre></dd></div>
                  {step.tool.result && <div><dt>{S.card.result}</dt><dd><pre className="toolResult">{step.tool.result}</pre></dd></div>}
                  {step.tool.error && <div><dt>{S.card.error}</dt><dd className="toolError">{step.tool.error}</dd></div>}
                </dl>
              </div>}
              {step.kind !== "tool_call" && step.content && <blockquote>{step.content}</blockquote>}
              {issue && <aside className="stepIssue"><strong>{S.card.stepIssue}{issue.issue_kind ? `: ${issue.issue_kind}` : ""}</strong><span>{issue.issue || ""}</span></aside>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function CardScreen({ state, assistant, currentId, mode, onState, onDone, onBack, blind = false, selfCheckQueue, onSelfCheckAdvance }: { state: ProjectState; assistant: string; currentId: string; mode: ReviewMode; onState: (state: ProjectState) => void; onDone: () => void; onBack: () => void; blind?: boolean; selfCheckQueue?: string[]; onSelfCheckAdvance?: () => void }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [startedAt, setStartedAt] = useState(Date.now());
  const [coachOpen, setCoachOpen] = useState(false);
  const [blindReview, setBlindReview] = useState(blind);
  const example = state.examples.find((item) => item.id === currentId);
  const verdict = currentId ? state.verdicts[currentId] : null;
  const quote = bestEvidence(verdict);
  const left = selfCheckQueue?.length ?? idsForMode(state, mode).length;

  useEffect(() => setStartedAt(Date.now()), [currentId]);
  useEffect(() => setBlindReview(blind), [blind, currentId]);
  useEffect(() => {
    void window.pressf.getReviewCoachSeen().then((seen) => setCoachOpen(!seen));
  }, []);

  function dismissCoach() {
    setCoachOpen(false);
    void window.pressf.setReviewCoachSeen(true);
  }

  async function submit(label: Label) {
    if (!example) return;
    if (label === "s" && !note.trim()) {
      setNoteOpen(true);
      return;
    }
    const next = selfCheckQueue ? await window.pressf.decideSelfCheck(state.root, example.id, label, label === "s" ? note : undefined, Date.now() - startedAt) : await window.pressf.decideById(state.root, example.id, label, label === "s" ? note : undefined, Date.now() - startedAt);
    onState(next);
    setNote("");
    setNoteOpen(false);
    const nextId = selfCheckQueue ? selfCheckQueue[1] : firstCardId(next, mode);
    if (selfCheckQueue && nextId) onSelfCheckAdvance?.();
    if (!nextId) onDone();
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key.toLowerCase() === "p") void submit("p");
      if (event.key.toLowerCase() === "f") void submit("f");
      if (event.key.toLowerCase() === "s") setNoteOpen(true);
      if (event.key.toLowerCase() === "u") void window.pressf.undo(state.root).then(onState);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  if (!example) return null;
  return (
    <main className="cardScreen mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <button className="coachHelp" aria-label={S.card.coachHelp} onClick={() => setCoachOpen(true)}><HelpCircle size={18} /></button>
      <section className="decisionCard">
        <div className="cardTop">
          <strong>{example.question}</strong>
          <span>{S.card.left(Math.max(0, left - 1))}</span>
        </div>
        {state.task === "agent_trajectory" ? <TrajectoryReview trajectory={example.trajectory} issues={verdict?.step_issues} /> : <div className="faceOff">
          <article>
            <h2>{S.card.answered(assistant)}</h2>
            <blockquote>{example.answer}</blockquote>
          </article>
          {!blindReview && <article>
            <h2>{evidenceHeading(state.task)}</h2>
            {quote ? <><blockquote>{quote.text}</blockquote><small>{quote.source}</small></> : <p className="noDoc">{S.card.noDoc}</p>}
          </article>}
        </div>}
        {!blindReview && verdict && (
          <div className={`judgeTake ${verdict.recommendation === "f" ? "judgeFail" : "judgePass"}`}>
            <span className="judgeTag">{S.card.judgeLabel}</span>
            <span className="judgeVerdict">{verdict.recommendation === "f" ? S.card.judgeFail : S.card.judgePass}</span>
            <span className="judgeReason">{findingCategoryCopy[categoryForVerdict(verdict)].detail}</span>
            <span className="judgeConf">{S.card.judgeConfidence(verdict.confidence)}</span>
          </div>
        )}
        <h1>{S.card.question}</h1>
        <div className="decisionActions">
          <button className="yesBtn" onClick={() => submit("p")}>{S.card.yes} {keycap("P")}</button>
          <button className="noBtn" onClick={() => submit("f")}>{S.card.no} {keycap("F")}</button>
          <button className="skipBtn" onClick={() => setNoteOpen(true)}>{S.card.skip} {keycap("S")}</button>
        </div>
        <div className="reviewTools">
          <button className="undoSmall" onClick={() => window.pressf.undo(state.root).then(onState)}><RotateCcw size={16} /> {S.card.undo}</button>
          {!selfCheckQueue && <button className="skipLink" onClick={() => setBlindReview((current) => !current)}>{blindReview ? S.card.revealJudge : S.card.blind}</button>}
        </div>
        {noteOpen && (
          <div className="noteLine">
            <input value={note} onChange={(event) => setNote(event.target.value)} placeholder={S.card.skipNote} autoFocus />
            <button onClick={() => submit("s")}>{S.card.skip}</button>
          </div>
        )}
        {!blindReview && <details className="detailsPanel">
          <summary>{S.card.details}</summary>
          <p>{S.card.rawCaption}</p>
          {verdict?.claims?.map((claim) => <p key={claim.text}><strong>{findingCategoryCopy[categoryForVerdict(verdict)].cardWord}</strong> · {claim.text}</p>)}
          {verdict?.reasoning && <blockquote>{verdict.reasoning}</blockquote>}
        </details>}
      </section>
      {coachOpen && <div className="reviewCoach" role="dialog" aria-modal="true" aria-label={S.card.coachTitle}><section><h2>{S.card.coachTitle}</h2><p>{S.card.coachBody}</p><button className="primaryAction" onClick={dismissCoach}>{S.card.coachDone}</button></section></div>}
    </main>
  );
}

function CompareCardScreen({ state, currentId, mode, onState, onDone, onBack }: { state: ProjectState; currentId: string; mode: ReviewMode; onState: (state: ProjectState) => void; onDone: () => void; onBack: () => void }) {
  const [startedAt, setStartedAt] = useState(Date.now());
  const example = state.examples.find((item) => item.id === currentId);
  const left = idsForMode(state, mode).length;
  const shownLeft = example ? shownLeftFor(example.id) : "a";
  const leftAnswer = shownLeft === "a" ? example?.answer : example?.answer_b;
  const rightAnswer = shownLeft === "a" ? example?.answer_b : example?.answer;

  useEffect(() => setStartedAt(Date.now()), [currentId]);

  async function submit(side: "left" | "right" | "tie") {
    if (!example) return;
    const winner: PairwiseWinner = side === "tie" ? "tie" : side === "left" ? shownLeft : shownLeft === "a" ? "b" : "a";
    const next = await window.pressf.decidePairwise(state.root, example.id, winner, shownLeft, undefined, Date.now() - startedAt);
    onState(next);
    const nextId = firstCardId(next, mode);
    if (!nextId) onDone();
  }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "ArrowLeft") void submit("left");
      if (event.key === "ArrowRight") void submit("right");
      if (event.key.toLowerCase() === "t") void submit("tie");
      if (event.key.toLowerCase() === "u") void window.pressf.undoPairwise(state.root).then(onState);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  if (!example) return null;
  return (
    <main className="cardScreen mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <section className="decisionCard">
        <div className="cardTop">
          <strong>{example.question}</strong>
          <span>{S.card.left(Math.max(0, left - 1))}</span>
        </div>
        <div className="faceOff">
          <article>
            <h2>{S.compare.leftAnswer}</h2>
            <blockquote>{leftAnswer}</blockquote>
          </article>
          <article>
            <h2>{S.compare.rightAnswer}</h2>
            <blockquote>{rightAnswer}</blockquote>
          </article>
        </div>
        <h1>{S.compare.question}</h1>
        <div className="decisionActions compareDecisionActions">
          <button className="yesBtn" onClick={() => submit("left")}>{S.compare.left} {keycap("←")}</button>
          <button className="noBtn" onClick={() => submit("right")}>{S.compare.right} {keycap("→")}</button>
          <button className="skipLink" onClick={() => submit("tie")}>{S.compare.tie} {keycap("T")}</button>
          <button className="undoSmall" onClick={() => window.pressf.undoPairwise(state.root).then(onState)}><RotateCcw size={16} /> {S.card.undo}</button>
        </div>
      </section>
    </main>
  );
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function GatePanel({ state }: { state: ProjectState }) {
  const [threshold, setThreshold] = useState("0.8");
  const score = faithfulnessScore(state.effective, state.verdicts);
  const bar = Math.min(1, Math.max(0, Number(threshold) || 0.8));
  if (score.source === "none" || score.n === 0) {
    return (
      <section className="gatePanel" aria-label={S.gate.title}>
        <h2>{S.gate.title}</h2>
        <p>{S.gate.empty}</p>
      </section>
    );
  }
  const [lo, hi] = wilsonInterval(score.passed, score.n);
  const passed = score.faithfulness >= bar;
  return (
    <section className="gatePanel" aria-label={S.gate.title}>
      <h2>{S.gate.title}</h2>
      <p>{S.gate.body}</p>
      <div className="gateRow">
        <span className={`gateBadge ${passed ? "gatePass" : "gateFail"}`}>{passed ? S.gate.pass : S.gate.fail}</span>
        <strong>{S.gate.score(pct(score.faithfulness), score.passed, score.n)}</strong>
        <small>{S.gate.ci(pct(lo), pct(hi))} · {score.source === "human" ? S.gate.sourceHuman : S.gate.sourceJudge}</small>
      </div>
      <label className="gateThreshold">{S.gate.threshold}
        <input type="number" min="0" max="1" step="0.05" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
      </label>
      <code>{S.gate.cliHint(state.root, String(bar))}</code>
    </section>
  );
}

function PairwiseGatePanel({ state }: { state: ProjectState }) {
  const summary = pairwiseSummary(state.pairwiseEffective);
  if (!summary.decided || summary.winRate === null || summary.pValue === null) {
    return <section className="gatePanel" aria-label={S.compareResult.title}><h2>{S.compareResult.title}</h2><p>{S.compareResult.empty}</p></section>;
  }
  const [lo, hi] = summary.ci;
  const decision = lo > 0.5 ? S.compareResult.ship : hi < 0.5 ? S.compareResult.worse : S.compareResult.hold;
  return (
    <section className="gatePanel" aria-label={S.compareResult.title}>
      <h2>{S.compareResult.title}</h2>
      <p>{S.compareResult.winRate(pct(summary.winRate), pct(lo), pct(hi), summary.decided)}</p>
      <p>{S.compareResult.pValue(summary.pValue.toFixed(4))}</p>
      {summary.leftShare !== null && <p>{S.compareResult.leftBias(pct(summary.leftShare))}</p>}
      <strong>{decision}</strong>
    </section>
  );
}

function PairwiseJudgePanel({ state }: { state: ProjectState }) {
  const pairs = Object.values(state.pairwiseEffective).flatMap((annotation) => {
    const category = state.verdicts[annotation.example_id]?.category;
    const judge = category === "a_better" ? "a" : category === "b_better" ? "b" : category === "tie" ? "tie" : null;
    return judge ? [[judge, annotation.winner ?? annotation.choice] as const] : [];
  });
  if (!pairs.length) return null;
  const agreed = pairs.filter(([judge, human]) => judge === human).length;
  return <section className="qualityPanel" aria-label={S.quality.title}><h2>{S.quality.title}</h2><p>{S.compareResult.judgeAgreement(pct(agreed / pairs.length), pairs.length)}</p></section>;
}

function JudgeQualityPanel({ state }: { state: ProjectState }) {
  const pairs = judgeHumanPairs(state.effective, state.verdicts);
  const kappas = interAnnotatorKappa(effectiveByAnnotator(state.annotations));
  if (!pairs.length && !kappas.length && !state.selfcheck.total) {
    return (
      <section className="qualityPanel" aria-label={S.quality.title}>
        <h2>{S.quality.title}</h2>
        <p>{S.quality.needMore}</p>
      </section>
    );
  }
  const agreed = pairs.filter(([judge, human]) => judge === human).length;
  const [lo, hi] = wilsonInterval(agreed, pairs.length);
  const flag = flagPrecisionRecall(pairs);
  const categoryRows = [...perCategoryAgreement(
    Object.values(state.effective)
      .filter((ann) => (ann.label === "p" || ann.label === "f") && state.verdicts[ann.example_id])
      .map((ann) => {
        const verdict = state.verdicts[ann.example_id];
        return [findingCategoryCopy[categoryForVerdict(verdict)].title, verdict.recommendation, ann.label] as [string, string, string];
      })
  ).entries()].sort((a, b) => b[1].total - a[1].total);
  return (
    <section className="qualityPanel" aria-label={S.quality.title}>
      <h2>{S.quality.title}</h2>
      {pairs.length > 0 && (
        <>
          <p>{S.quality.agreement(pct(agreed / pairs.length), pct(lo), pct(hi), pairs.length)}</p>
          <p>{S.quality.flagLine(pct(flag.precision), pct(flag.recall), pct(flag.f1))} <small>{S.quality.flagCaption}</small></p>
        </>
      )}
      {categoryRows.length > 0 && (
        <div className="qualityCategories">
          <h3>{S.quality.perCategory}</h3>
          <dl>
            {categoryRows.map(([category, row]) => (
              <div key={category}><dt>{category}</dt><dd>{pct(row.agreement)} <small>{S.quality.perCategoryRow(row.total)}</small></dd></div>
            ))}
          </dl>
        </div>
      )}
      {state.selfcheck.total > 0 && state.selfcheck.agreement !== null && (
        <p>{S.quality.selfCheck(pct(state.selfcheck.agreement), state.selfcheck.total)}</p>
      )}
      {kappas.length > 0 && (
        <div className="qualityCategories">
          <h3>{S.quality.kappa}</h3>
          <dl>
            {kappas.map((row) => (
              <div key={`${row.a}-${row.b}`}><dt>{S.quality.kappaRow(row.a, row.b, row.common)}</dt><dd>{row.kappa.toFixed(2)}</dd></div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}

type JudgeDisagreement = {
  id: string;
  question: string;
  verdict: Verdict;
  label: Label;
};

function judgeDisagreements(state: ProjectState): JudgeDisagreement[] {
  return state.examples.flatMap((example) => {
    const verdict = state.verdicts[example.id];
    const annotation = state.effective[example.id];
    return verdict && annotation && (annotation.label === "p" || annotation.label === "f") && verdict.recommendation !== annotation.label
      ? [{ id: example.id, question: example.question, verdict, label: annotation.label }]
      : [];
  });
}

function judgeDecision(label: "p" | "f") {
  return label === "f" ? S.judgeEvaluation.fail : S.judgeEvaluation.pass;
}

function JudgeEvaluationScreen({ state, onBack, onOpenCase }: { state: ProjectState; onBack: () => void; onOpenCase: (id: string) => void }) {
  const [calibration, setCalibration] = useState<CalibrationProposal | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [calibrationError, setCalibrationError] = useState("");
  const [calibrationApplied, setCalibrationApplied] = useState(false);
  const verdictCount = Object.keys(state.verdicts).length;
  const reviewed = judgeHumanPairs(state.effective, state.verdicts).length;
  const disagreements = judgeDisagreements(state);

  async function proposeCalibration() {
    setCalibrating(true); setCalibrationError(""); setCalibrationApplied(false);
    try {
      setCalibration(await window.pressf.proposeCalibration(state.root));
    } catch (e) {
      setCalibrationError(e instanceof Error ? e.message : String(e));
    } finally {
      setCalibrating(false);
    }
  }

  async function applyCalibration() {
    if (!calibration) return;
    await window.pressf.applyCalibration(state.root, calibration.markdown);
    setCalibrationApplied(true);
  }

  return (
    <main className="judgeEvaluation mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <header className="judgeEvaluationHead">
        <div><p className="sectionEyebrow">{S.judgeEvaluation.action}</p><h1>{S.judgeEvaluation.title}</h1><p>{S.judgeEvaluation.body}</p></div>
        <strong className="reviewCoverage">{S.judgeEvaluation.coverage(reviewed, verdictCount)}</strong>
      </header>
      {!verdictCount ? <section className="judgeEmpty"><h2>{S.quality.title}</h2><p>{S.judgeEvaluation.noVerdicts}</p></section> : !reviewed ? <section className="judgeEmpty"><h2>{S.quality.title}</h2><p>{S.judgeEvaluation.noHumanLabels}</p></section> : <>
        <JudgeQualityPanel state={state} />
        <section className="judgeDisagreements" aria-labelledby="judge-disagreements-title">
          <div className="judgeSectionHead"><div><h2 id="judge-disagreements-title">{S.judgeEvaluation.disagreements}</h2><p>{S.judgeEvaluation.disagreementCount(disagreements.length)}</p></div></div>
          {!disagreements.length ? <p className="judgeEmptyInline">{S.judgeEvaluation.noDisagreements}</p> : <div className="judgeDisagreementList">{disagreements.map((row) => {
            const category = findingCategoryCopy[categoryForVerdict(row.verdict)].title;
            return <article className="judgeDisagreement" key={row.id}>
              <header><span className="caseId">{row.id}</span><strong>{row.question}</strong><button onClick={() => onOpenCase(row.id)}>{S.judgeEvaluation.openCase}<ChevronRight size={16} /></button></header>
              <div className="decisionStrip" aria-label={`${S.judgeEvaluation.judge} and ${S.judgeEvaluation.human} decisions`}>
                <div className={row.verdict.recommendation === "f" ? "negative" : "positive"}><span>{S.judgeEvaluation.judge}</span><strong>{judgeDecision(row.verdict.recommendation)}</strong></div>
                <div className={row.label === "f" ? "negative" : "positive"}><span>{S.judgeEvaluation.human}</span><strong>{judgeDecision(row.label)}</strong></div>
                <dl><div><dt>{S.judgeEvaluation.category}</dt><dd>{category}</dd></div><div><dt>{S.judgeEvaluation.confidence}</dt><dd>{row.verdict.confidence.toFixed(2)}</dd></div></dl>
              </div>
            </article>;
          })}</div>}
        </section>
        <section className="judgeCalibration">
          <div><h2>{S.judgeEvaluation.propose}</h2><p>{S.judgeEvaluation.proposeBody}</p></div>
          <button className="primaryAction" onClick={proposeCalibration} disabled={calibrating}>{calibrating ? S.judgeEvaluation.proposing : S.judgeEvaluation.propose}</button>
        </section>
      </>}
      {calibrationError && <p className="devError">{calibrationError}</p>}
      {calibration && !calibrationApplied && <section className="calibrationProposal"><h2>{S.judgeEvaluation.proposalTitle}</h2><p>{S.judgeEvaluation.proposalBody}</p><pre>{calibration.markdown}</pre><div className="finishActions"><button className="primaryAction" onClick={applyCalibration}>{S.judgeEvaluation.accept}</button><button onClick={() => setCalibration(null)}>{S.judgeEvaluation.reject}</button></div></section>}
      {calibrationApplied && <section className="calibrationProposal"><p className="devSaved">{S.judgeEvaluation.applied}</p></section>}
    </main>
  );
}

function JudgeCaseScreen({ state, currentId, onBack, onState }: { state: ProjectState; currentId: string; onBack: () => void; onState: (state: ProjectState) => void }) {
  const [note, setNote] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [startedAt, setStartedAt] = useState(Date.now());
  const example = state.examples.find((item) => item.id === currentId);
  const verdict = state.verdicts[currentId];
  const annotation = state.effective[currentId];
  useEffect(() => setStartedAt(Date.now()), [currentId]);
  if (!example || !verdict) return null;
  async function decide(label: Label) {
    if (label === "s" && !note.trim()) { setNoteOpen(true); return; }
    onState(await window.pressf.decideById(state.root, example.id, label, label === "s" ? note : undefined, Date.now() - startedAt));
    setNote(""); setNoteOpen(false);
  }
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key.toLowerCase() === "p") void decide("p");
      if (event.key.toLowerCase() === "f") void decide("f");
      if (event.key.toLowerCase() === "s") setNoteOpen(true);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
  const evidence = evidenceFor(verdict);
  return <main className="judgeCase mainPath" data-testid="main-path">
    <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
    <header className="judgeCaseHead"><p className="sectionEyebrow">{example.id}</p><h1>{S.judgeEvaluation.caseTitle}</h1><p>{S.judgeEvaluation.caseBody}</p></header>
    <section className="judgeCaseQuestion"><h2>{example.question}</h2><div className="decisionStrip compact"><div className={verdict.recommendation === "f" ? "negative" : "positive"}><span>{S.judgeEvaluation.judge}</span><strong>{judgeDecision(verdict.recommendation)}</strong></div><div className={annotation?.label === "f" ? "negative" : "positive"}><span>{S.judgeEvaluation.human}</span><strong>{annotation?.label === "p" || annotation?.label === "f" ? judgeDecision(annotation.label) : S.judgeEvaluation.skipped}</strong></div><dl><div><dt>{S.judgeEvaluation.category}</dt><dd>{findingCategoryCopy[categoryForVerdict(verdict)].title}</dd></div><div><dt>{S.judgeEvaluation.confidence}</dt><dd>{verdict.confidence.toFixed(2)}</dd></div></dl></div></section>
    <section className="judgeCaseGrid"><article><h2>{S.judgeEvaluation.answer}</h2><blockquote>{example.answer}</blockquote></article><article><h2>{S.judgeEvaluation.reasoning}</h2><blockquote>{verdict.reasoning}</blockquote></article></section>
    <section className="caseEvidence"><h2>{S.judgeEvaluation.claims}</h2>{evidence.length ? evidence.map((item, index) => <article key={`${item.claim}-${index}`}><p>{item.claim}</p><blockquote>{item.text}</blockquote><small>{item.source}</small></article>) : <p>{S.judgeEvaluation.noEvidence}</p>}{example.context?.length ? <><h2>{S.judgeEvaluation.context}</h2>{example.context.map((item, index) => <article key={`${item.source}-${index}`}><blockquote>{item.text}</blockquote><small>{item.source ?? "—"}</small></article>)}</> : null}</section>
    <section className="humanDecision"><div><h2>{S.judgeEvaluation.humanDecision}</h2><p>{S.judgeEvaluation.reviseHint}</p></div><div className="decisionActions"><button className="yesBtn" onClick={() => void decide("p")}>{S.judgeEvaluation.passAction} {keycap("P")}</button><button className="noBtn" onClick={() => void decide("f")}>{S.judgeEvaluation.failAction} {keycap("F")}</button><button className="skipBtn" onClick={() => setNoteOpen(true)}>{S.judgeEvaluation.skipAction} {keycap("S")}</button></div>{noteOpen && <div className="noteLine"><input value={note} onChange={(event) => setNote(event.target.value)} placeholder={S.judgeEvaluation.notePlaceholder} autoFocus /><button onClick={() => void decide("s")}>{S.judgeEvaluation.skipAction}</button></div>}</section>
  </main>;
}

function Finish({ state, assistant, onNew, onDisagreements, onRecheck, onJudgeEvaluation }: { state: ProjectState; assistant: string; onNew: () => void; onDisagreements: (rows: DisagreementRecord[]) => void; onRecheck: () => void; onJudgeEvaluation: () => void }) {
  const [saved, setSaved] = useState(false);
  const [reportPath, setReportPath] = useState<string | null>(null);
  const [formats, setFormats] = useState<string[]>(["jsonl"]);
  const [pairsSaved, setPairsSaved] = useState(false);
  const [calibration, setCalibration] = useState<CalibrationProposal | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [calibrationError, setCalibrationError] = useState("");
  const [calibrationApplied, setCalibrationApplied] = useState(false);
  const realErrors = state.stats.f;
  const falseAlarms = state.stats.p;
  const score = state.stats.agreement;
  async function save() {
    const exported = await window.pressf.runExport(state.root, { formats });
    setReportPath(exported.paths.report);
    setSaved(true);
  }
  async function viewDisagreements() {
    onDisagreements(await window.pressf.exportDisagreements(state.root));
  }
  function toggleFormat(format: string) {
    setFormats((current) => current.includes(format) ? current.filter((item) => item !== format) : [...current, format]);
  }
  async function improveJudge() {
    setCalibrating(true); setCalibrationError(""); setCalibrationApplied(false);
    try {
      setCalibration(await window.pressf.proposeCalibration(state.root));
    } catch (e) {
      setCalibrationError(e instanceof Error ? e.message : String(e));
    } finally {
      setCalibrating(false);
    }
  }
  async function acceptCalibration() {
    if (!calibration) return;
    await window.pressf.applyCalibration(state.root, calibration.markdown);
    setCalibrationApplied(true);
  }
  return (
    <main className="finish mainPath" data-testid="main-path">
      <div className="celebrate"><CheckCircle2 size={68} /></div>
      <h1>{S.finish.done}</h1>
      <p>{state.task === "pairwise_compare" ? S.finish.pairwiseSummary(state.stats.f, state.stats.p, state.stats.s) : S.finish.summary(state.stats.done, realErrors, falseAlarms)}</p>
      {state.task !== "pairwise_compare" && <section className="trustGauge">
        <div style={{ "--score": `${Math.round((score ?? 0) * 100)}%` } as React.CSSProperties}><span>{score === null ? "—" : `${Math.round(score * 100)}%`}</span></div>
        <strong>{S.finish.trust}</strong>
        <p>{trustCaption(score)}</p>
      </section>}
      {state.task === "pairwise_compare" && <PairwiseGatePanel state={state} />}
      {state.task === "pairwise_compare" && <PairwiseJudgePanel state={state} />}
      {state.task !== "pairwise_compare" && <GatePanel state={state} />}
      {state.task !== "pairwise_compare" && <JudgeQualityPanel state={state} />}
      <div className="finishActions">
        <div className="finishActionGroup finishExportActions">
          <fieldset className="formatPicker"><legend>{S.export.formats}</legend>{["jsonl", "csv", "hf"].map((format) => <label key={format}><input type="checkbox" checked={formats.includes(format)} onChange={() => toggleFormat(format)} /> {format}</label>)}</fieldset>
          <button className="primaryAction" onClick={save}><Save size={18} /> {S.finish.save}</button>
          <button onClick={async () => { await window.pressf.runExport(state.root, { pairs: true }); setPairsSaved(true); }}>{S.export.pairs}</button>
        </div>
        <div className="finishActionGroup finishReviewActions">
          <button onClick={viewDisagreements}>{S.finish.disagreements}</button>
          {state.task !== "pairwise_compare" && <button onClick={onJudgeEvaluation}>{S.judgeEvaluation.openFromFinish}</button>}
          {score !== null && <button onClick={improveJudge} disabled={calibrating}>{calibrating ? "Preparing suggestion…" : S.finish.improveJudge}</button>}
          <button className="finishRecheck" onClick={onNew}>{S.finish.again}</button>
        </div>
      </div>
      {saved && <div className="savedReport"><p className="saved">{S.finish.saved}</p><button onClick={() => reportPath && window.pressf.revealFile(reportPath)}><FolderOpen size={16} /> {S.finish.showInFinder}</button></div>}
      {pairsSaved && <button onClick={() => window.pressf.revealFile(state.paths.pairs)}>{S.export.showPairs}</button>}
      {calibrationError && <p className="devError">{calibrationError}</p>}
      {calibration && !calibrationApplied && <section className="calibrationProposal">
        <h2>{S.finish.calibrationTitle}</h2>
        <p>{S.finish.calibrationBody}</p>
        <pre>{calibration.markdown}</pre>
        <div className="finishActions"><button className="primaryAction" onClick={acceptCalibration}>{S.finish.calibrationAccept}</button><button onClick={() => setCalibration(null)}>{S.finish.calibrationReject}</button></div>
      </section>}
      {calibrationApplied && <section className="calibrationProposal"><p className="devSaved">{S.finish.calibrationApplied}</p><button className="primaryAction" onClick={onRecheck}>{S.finish.calibrationRecheck}</button></section>}
    </main>
  );
}

function KeyScreen({ provider, onSaved }: { provider: LlmProvider; onSaved: () => void }) {
  const [key, setKey] = useState("");
  return (
    <main className="keyScreen mainPath" data-testid="main-path">
      <h1>{S.key.title(provider)}</h1>
      <p>{S.key.body(provider)}</p>
      <input type="password" placeholder={S.key.placeholder} value={key} onChange={(event) => setKey(event.target.value)} />
      <button className="primaryAction" disabled={!key.trim()} onClick={async () => { await window.pressf.saveKey(provider, key); onSaved(); }}>{S.key.save}</button>
    </main>
  );
}

function HelpScreen({ onBack }: { onBack: () => void }) {
  return (
    <main className="helpScreen mainPath" data-testid="main-path">
      <button className="backBtn" onClick={onBack}><ArrowLeft size={18} /> {S.interview.back}</button>
      <header className="helpHead">
        <h1>{S.help.title}</h1>
        <p className="helpTagline">{S.help.tagline}</p>
      </header>
      <section className="helpCard">
        <h2>{S.help.whatTitle}</h2>
        <p>{S.help.whatBody}</p>
      </section>
      <section className="helpCard">
        <h2>{S.help.whoTitle}</h2>
        <p>{S.help.whoBody}</p>
      </section>
      <section className="helpCard helpEdge">
        <h2>{S.help.edgeTitle}</h2>
        <p>{S.help.edgeBody}</p>
      </section>
      <section className="helpCard">
        <h2>{S.help.modulesTitle}</h2>
        <div className="helpModules">
          {S.help.modules.map((m) => (
            <div key={m.name} className="helpModule"><strong>{m.name}</strong><span>{m.body}</span></div>
          ))}
        </div>
      </section>
      <section className="helpCard">
        <h2>{S.help.trustTitle}</h2>
        <p>{S.help.trustBody}</p>
      </section>
      <section className="helpCard">
        <h2>{S.help.hoodTitle}</h2>
        <p>{S.help.hoodBody}</p>
      </section>
      <section className="helpCard">
        <h2>{S.help.contactTitle}</h2>
        <p>{S.help.contactBody}</p>
        <div className="helpLinks">
          {S.help.links.map((link) => (
            <button key={link.label} className="helpLink" onClick={() => window.pressf.openLink(link.href)}>
              <strong>{link.label}</strong><span>{link.value}</span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

function Onboarding({ onTryExample, onClose }: { onTryExample: () => void; onClose: () => void }) {
  const [step, setStep] = useState(0);
  const steps = S.onboarding.steps;
  const current = steps[step];
  const last = step === steps.length - 1;
  return (
    <div className="reviewCoach onboarding" role="dialog" aria-modal="true" aria-label={current.title}>
      <section>
        <p className="onboardingStep">{S.onboarding.stepLabel(step + 1, steps.length)}</p>
        <h2>{current.title}</h2>
        <p>{current.body}</p>
        {step === 1 && <button className="secondaryAction" onClick={onTryExample}><Sparkles size={16} /> {S.onboarding.tryExample}</button>}
        <div className="onboardingActions">
          <button className="linkAction" onClick={onClose}>{S.onboarding.skip}</button>
          <button className="primaryAction" onClick={() => last ? onClose() : setStep((s) => s + 1)}>{current.next}</button>
        </div>
      </section>
    </div>
  );
}

function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [screen, setScreen] = useState<Screen>("home");
  const [state, setState] = useState<ProjectState | null>(null);
  const [name, setName] = useState("");
  const [dataPath, setDataPath] = useState("");
  const [docsPath, setDocsPath] = useState("");
  const [kbKind, setKbKind] = useState<"docs_folder" | "chunks_file">("docs_folder");
  const [inspection, setInspection] = useState<DataInspection | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({ question: "", answer: "" });
  const [labelColumn, setLabelColumn] = useState<string | null>(null);
  const [importLabels, setImportLabels] = useState(true);
  const [estimate, setEstimate] = useState<CheckEstimate | null>(null);
  const [mode, setMode] = useState<ReviewMode>("suspicious");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [devOpen, setDevOpen] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [activeTask, setActiveTask] = useState<ModuleTask>("rag_faithfulness");
  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [baselineRoot, setBaselineRoot] = useState<string | null>(null);
  const [disagreements, setDisagreements] = useState<DisagreementRecord[]>([]);
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("pressf-theme") === "dark" ? "dark" : "light");
  const [addFile, setAddFile] = useState("");
  const [addInspection, setAddInspection] = useState<DataInspection | null>(null);
  const [addMapping, setAddMapping] = useState<ColumnMapping>({ question: "", answer: "" });
  const [checkOptions, setCheckOptions] = useState<CheckOptions>({});
  const [judgeProvider, setJudgeProvider] = useState<LlmProvider>("anthropic");
  const [judgeModel, setJudgeModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [reviewOrder, setReviewOrder] = useState<ReviewOrder>("confidence");
  const [selfCheckIds, setSelfCheckIds] = useState<string[]>([]);
  const [botRunning, setBotRunning] = useState(false);
  const [botReady, setBotReady] = useState(false);
  const [botError, setBotError] = useState("");

  const assistant = assistantName(state, name);

  async function refreshProjects() {
    setProjects(await window.pressf.listProjects());
  }

  async function deleteProject(root: string) {
    setProjects(await window.pressf.deleteProject(root));
  }

  useEffect(() => { void refreshProjects(); }, []);
  useEffect(() => {
    void window.pressf.getOnboardingSeen().then((seen) => setOnboardingOpen(!seen));
  }, []);

  function dismissOnboarding() {
    setOnboardingOpen(false);
    void window.pressf.setOnboardingSeen(true);
  }

  useEffect(() => {
    localStorage.setItem("pressf-theme", theme);
    document.documentElement.style.colorScheme = theme;
  }, [theme]);
  useEffect(() => {
    if (!state) return;
    void window.pressf.watchProject(state.root);
    return window.pressf.onProjectChanged(setState);
  }, [state?.root]);
  useEffect(() => window.pressf.onCheckProgress((progress) => {
    if (!state || progress.projectRoot !== state.root) return;
    setScan((current) => {
      if (!current || current.phase !== "running") return current;
      const completed = /\b[pf]\s+\S+\s+\(/.test(progress.line);
      const flagged = /\bf\s+\S+\s+\(/.test(progress.line);
      return {
        ...current,
        message: progress.line,
        reportedChecked: current.reportedChecked + Number(completed),
        reportedFlagged: current.reportedFlagged + Number(flagged)
      };
    });
  }), [state?.root]);

  useEffect(() => window.pressf.onBotProgress((progress) => {
    if (progress.projectRoot === baselineRoot) setBotError(progress.line.includes("error") ? progress.line : "");
  }), [baselineRoot]);

  async function openProject(root: string) {
    const next = await window.pressf.projectState(root);
    setState(next);
    setName(next.name);
    setActiveTask(next.task === "policy_compliance" ? "policy_compliance" : next.task === "retrieval_quality" ? "retrieval_quality" : next.task === "pairwise_compare" ? "pairwise_compare" : next.task === "agent_trajectory" || next.task === "agents" ? "agent_trajectory" : "rag_faithfulness");
    setScreen(Object.keys(next.verdicts).length ? "hub" : "ready");
  }

  async function tryDemo(openFirstFinding = false) {
    const next = await window.pressf.createDemo(activeTask);
    setState(next);
    setName(next.name);
    await refreshProjects();
    // The first experience should prove the value immediately: show a concrete
    // document-backed finding, not a dashboard the user has to interpret.
    const first = openFirstFinding ? firstCardId(next, "suspicious") : null;
    if (first) {
      setMode("suspicious");
      setCurrentId(first);
      setScreen("card");
    } else {
      setScreen("hub");
    }
  }

  async function inspectFile(file: string) {
    if (!file) return;
    const inspected = await window.pressf.inspectDataFile(file);
    const comparisonAnswer = activeTask === "pairwise_compare"
      ? inspected.headers.find((header) => ["answer_b", "response_b", "completion_b", "version_b"].includes(header.toLowerCase()))
      : null;
    setInspection(inspected);
    setMapping({ question: inspected.detected.question, answer: comparisonAnswer || inspected.detected.answer, context: inspected.detected.context, trajectory: inspected.detected.trajectory, id: inspected.detected.id });
    setLabelColumn(inspected.detected.label || null);
  }

  async function inspectAddFile(file: string) {
    setAddFile(file);
    if (!file) return;
    const inspected = await window.pressf.inspectDataFile(file);
    setAddInspection(inspected);
    setAddMapping({ question: inspected.detected.question, answer: inspected.detected.answer, context: inspected.detected.context, trajectory: inspected.detected.trajectory, id: inspected.detected.id });
  }

  async function beginAddAnswers(root: string) {
    const next = state?.root === root ? state : await window.pressf.projectState(root);
    setState(next);
    setAddFile("");
    setAddInspection(null);
    setAddMapping({ question: "", answer: "" });
    setScreen("addAnswers");
  }

  async function addAnswers() {
    if (!state || !addFile) return;
    const next = await window.pressf.addAnswers(state.root, addFile, addMapping);
    setState(next);
    await refreshProjects();
    setScreen("hub");
  }

  async function chooseDataFile() {
    const file = await window.pressf.chooseDataFile();
    if (!file) return;
    setDataPath(file);
    await inspectFile(file);
  }

  async function chooseDocsFolder() {
    const folder = await window.pressf.chooseDocsFolder();
    if (folder) setDocsPath(folder);
  }

  async function chooseChunksFile() {
    const file = await window.pressf.chooseChunksFile();
    if (file) setDocsPath(file);
  }

  async function runBaselineBot() {
    if (!baselineRoot) return;
    setBotRunning(true); setBotReady(false); setBotError("");
    try {
      const result = await window.pressf.runBot(baselineRoot);
      if (result.cancelled || result.code !== 0) throw new Error(result.output || "Bot run failed.");
      setDataPath(result.file);
      await inspectFile(result.file);
      setBotReady(true);
    } catch (e) {
      setBotError(e instanceof Error ? e.message : String(e));
    } finally {
      setBotRunning(false);
    }
  }

  async function createProject() {
    if (activeTask === "pairwise_compare") {
      if (!baselineRoot) return;
      const next = await window.pressf.createCompareProject({
        name: assistant,
        baselineRoot,
        dataPath,
        mapping
      });
      setState(next);
      await refreshProjects();
      setEstimate(null);
      setScreen("ready");
      return;
    }
    const next = await window.pressf.createProject({
      name: assistant,
      task: activeTask,
      dataPath,
      docsPath,
      retrieverKind: kbKind,
      mapping,
      labelColumn,
      importLabels,
      llm: { provider: judgeProvider, judgeModel, baseUrl }
    });
    setState(next);
    await refreshProjects();
    try {
      if (activeTask === "pairwise_compare") {
        setEstimate(null);
      } else if (await window.pressf.hasKey(judgeProvider)) {
        setEstimate(await window.pressf.estimateCheck(next.root));
      }
    } catch {
      setEstimate(null);
    }
    setScreen("ready");
  }

  async function startRealScan(options: CheckOptions = checkOptions) {
    if (!state) return;
    const current = await window.pressf.projectState(state.root);
    setState(current);
    if (!options.force && Object.keys(current.verdicts).length >= current.examples.length && current.examples.length > 0) {
      setScreen("hub");
      return;
    }
    // Pairwise comparison is human review by design; it has no required judge run.
    if (current.task === "pairwise_compare") {
      setScreen("hub");
      return;
    }
    if (!(await window.pressf.hasKey(current.llmProvider))) {
      setScreen("key");
      return;
    }
    setScan({ phase: "running", message: S.scan.starting, reportedChecked: 0, reportedFlagged: 0 });
    setScreen("scan");
    const result = await window.pressf.runCheck(state.root, options);
    setState(result.state);
    setScan({
      phase: result.cancelled ? "cancelled" : result.code === 0 ? "complete" : "failed",
      message: result.cancelled ? S.scan.cancelled : result.code === 0 ? S.scan.done : S.scan.failed,
      reportedChecked: Object.keys(result.state.verdicts).length,
      reportedFlagged: result.state.examples.filter((example) => isSuspicious(result.state.verdicts[example.id])).length
    });
  }

  async function cancelScan() {
    if (!state) return;
    setScan((current) => current ? { ...current, message: "Cancelling judge check…" } : current);
    await window.pressf.cancelCheck(state.root);
  }

  function selectTask(task: ModuleTask) {
    setActiveTask(task);
    setMode("suspicious");
    setCurrentId(null);
    setBaselineRoot(null);
    setEstimate(null);
    setCheckOptions({});
    setKbKind("docs_folder");
    setScreen("home");
  }

  function startMode(nextMode: ReviewMode) {
    if (!state) return;
    setMode(nextMode);
    const id = firstCardId(state, nextMode, reviewOrder);
    if (id) {
      setCurrentId(id);
      setScreen("card");
    } else {
      setScreen("finish");
    }
  }

  async function beginSelfCheck() {
    if (!state) return;
    const ids = await window.pressf.startSelfCheck(state.root, 0.1);
    if (!ids.length) return;
    setSelfCheckIds(ids);
    setCurrentId(ids[0]);
    setScreen("card");
  }

  const content = useMemo(() => {
    if (screen === "help") return <HelpScreen onBack={() => setScreen("home")} />;
    if (screen === "home") return <Home projects={projects} activeTask={activeTask} onCheck={() => setScreen("name")} onDemo={tryDemo} onOpen={openProject} onDelete={deleteProject} />;
    if (screen === "name") return <InterviewShell onBack={() => setScreen("home")}><h1>{S.interview.nameQ}</h1><div className="nameRow"><input className="bigInput" value={name} placeholder={S.interview.namePlaceholders[activeTask]} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") setScreen(activeTask === "pairwise_compare" ? "baseline" : "answers"); }} /><button className="primaryAction" onClick={() => setScreen(activeTask === "pairwise_compare" ? "baseline" : "answers")}>{S.interview.next}</button></div></InterviewShell>;
    if (screen === "baseline") return <BaselinePicker projects={projects} onBack={() => setScreen("name")} onChoose={(root) => { setBaselineRoot(root); setBotReady(false); setBotError(""); setScreen("answers"); }} />;
    if (screen === "answers") { const needsContext = activeTask === "retrieval_quality" && !mapping.context; const needsTrajectory = activeTask === "agent_trajectory" && !mapping.trajectory; const isTrajectory = activeTask === "agent_trajectory"; return <InterviewShell onBack={() => setScreen(activeTask === "pairwise_compare" ? "baseline" : "name")}><h1>{answersQuestion(activeTask, assistant)}</h1><section className="setupPanel"><WorkflowGuide task={activeTask} /><div className="setupDivider" /><div className="dropInterview"><FileSpreadsheet size={28} /><p>{S.interview.inputHints[activeTask]}</p><FileShape task={activeTask} /><PathPicker label={S.interview.inputFileLabels[activeTask]} ariaLabel={S.interview.pasteFile} placeholder={isTrajectory ? S.interview.tracesPath : S.interview.answersPath} value={dataPath} onChange={setDataPath} onBlur={() => inspectFile(dataPath)} onChoose={chooseDataFile} chooseLabel={S.interview.chooseFile} /></div></section>{needsContext && <p className="devError">{S.interview.searchContextRequired}</p>}{activeTask === "pairwise_compare" && baselineRoot && <BotRunSetup running={botRunning} ready={botReady} error={botError} onRun={runBaselineBot} />}{labelColumn && activeTask !== "pairwise_compare" && !isTrajectory && <label className="importLine"><input type="checkbox" checked={importLabels} onChange={(event) => setImportLabels(event.target.checked)} /> {S.interview.labelOffer}</label>}<button className="primaryAction" disabled={!dataPath} onClick={() => !mapping.question || !mapping.answer || needsContext || needsTrajectory ? setScreen("columns") : activeTask === "pairwise_compare" ? createProject() : isTrajectory ? setScreen("judge") : setScreen("docs")}>{S.interview.next}</button></InterviewShell>; }
    if (screen === "docs") return <InterviewShell onBack={() => setScreen("answers")}><h1>{docsQuestion(activeTask, assistant)}</h1><div className="kbKindToggle" role="radiogroup" aria-label={S.dev.retrieverKind}><button className={kbKind === "docs_folder" ? "active" : ""} aria-pressed={kbKind === "docs_folder"} onClick={() => { if (kbKind !== "docs_folder") { setKbKind("docs_folder"); setDocsPath(""); } }}>{S.interview.kbFolder}</button><button className={kbKind === "chunks_file" ? "active" : ""} aria-pressed={kbKind === "chunks_file"} onClick={() => { if (kbKind !== "chunks_file") { setKbKind("chunks_file"); setDocsPath(""); } }}>{S.interview.kbChunks}</button></div><div className="dropInterview">{kbKind === "chunks_file" ? <FileSpreadsheet size={28} /> : <FolderOpen size={28} />}<p>{kbKind === "chunks_file" ? S.interview.chunksHint : docsHint(activeTask)}</p>{kbKind === "chunks_file" ? <PathPicker label="Chunks file" ariaLabel={S.interview.pasteChunks} placeholder={S.interview.chunksPath} value={docsPath} onChange={setDocsPath} onChoose={chooseChunksFile} chooseLabel={S.interview.chooseFile} /> : <PathPicker label="Documentation folder" ariaLabel={S.interview.pasteDocs} placeholder={S.interview.docsPath} value={docsPath} onChange={setDocsPath} onChoose={chooseDocsFolder} chooseLabel={S.interview.chooseFolder} />}</div><button className="primaryAction" disabled={!docsPath} onClick={() => inspection && (!mapping.question || !mapping.answer) ? setScreen("columns") : setScreen("judge")}>{S.interview.next}</button></InterviewShell>;
    if (screen === "judge") return <InterviewShell onBack={() => setScreen(activeTask === "agent_trajectory" ? "answers" : "docs")}><h1>{S.judge.title}</h1><p className="readyLine">{S.judge.body}</p><label>{S.judge.provider}<select value={judgeProvider} onChange={(event) => setJudgeProvider(event.target.value as LlmProvider)}><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="openai_compatible">OpenAI-compatible</option></select></label><label>{S.judge.model}<input value={judgeModel} placeholder={judgeProvider === "openai_compatible" ? "qwen3:latest" : S.judge.modelOptional} onChange={(event) => setJudgeModel(event.target.value)} /></label>{judgeProvider === "openai_compatible" && <label>{S.judge.baseUrl}<input value={baseUrl} placeholder="http://localhost:11434/v1" onChange={(event) => setBaseUrl(event.target.value)} /></label>}<p>{S.judge.keyHint(judgeProvider)}</p><button className="primaryAction" disabled={judgeProvider === "openai_compatible" && (!judgeModel.trim() || !baseUrl.trim())} onClick={createProject}>{S.interview.next}</button></InterviewShell>;
    if (screen === "columns" && inspection) { const needsContext = activeTask === "retrieval_quality" && !mapping.context; const needsTrajectory = activeTask === "agent_trajectory" && !mapping.trajectory; return <InterviewShell onBack={() => setScreen("answers")}><h1>{!mapping.question ? S.interview.questionColumn : !mapping.answer ? S.interview.answerColumn : needsTrajectory ? S.interview.trajectoryColumn : S.interview.contextColumn}</h1><div className="columnPicker">{inspection.headers.map((header) => <button key={header} onClick={() => setMapping((prev) => !prev.question ? { ...prev, question: header } : !prev.answer ? { ...prev, answer: header } : needsTrajectory ? { ...prev, trajectory: header } : { ...prev, context: header })}>{header}</button>)}</div><button className="primaryAction" disabled={!mapping.question || !mapping.answer || needsContext || needsTrajectory || (activeTask !== "pairwise_compare" && activeTask !== "agent_trajectory" && !docsPath)} onClick={() => activeTask === "pairwise_compare" ? createProject() : setScreen("judge")}>{S.interview.next}</button></InterviewShell>; }
    if (screen === "ready") {
      const hasPreparedChecks = Boolean(state && Object.keys(state.verdicts).length >= state.examples.length && state.examples.length > 0);
      const estimateCost = estimate?.batchUsd !== null && estimate?.batchUsd !== undefined ? `$${estimate.batchUsd.toFixed(2)}` : estimate?.syncUsd !== null && estimate?.syncUsd !== undefined ? `$${estimate.syncUsd.toFixed(2)}` : null;
      return <InterviewShell onBack={() => setScreen(state?.task === "agent_trajectory" ? "judge" : "docs")}><h1>{S.interview.ready}</h1><p className="readyLine">{S.interview.readyLine(checkOptions.limit ? Math.min(checkOptions.limit, state?.examples.length ?? 0) : state?.examples.length ?? 0, estimateCost)}</p>{!estimate && !hasPreparedChecks && <p>{S.interview.estimateFallback}</p>}<details className="advancedCheck"><summary>{S.check.advanced}</summary><label><input type="checkbox" checked={Boolean(checkOptions.force)} onChange={(event) => setCheckOptions((current) => ({ ...current, force: event.target.checked }))} /> {S.check.force}</label><label>{S.check.limit}<input type="number" min="1" max={state?.examples.length || 1} value={checkOptions.limit || ""} onChange={(event) => setCheckOptions((current) => ({ ...current, limit: event.target.value ? Number(event.target.value) : undefined }))} /></label>{checkOptions.limit && <small>{S.check.limitHint(checkOptions.limit)}</small>}<label><input type="checkbox" checked={Boolean(checkOptions.sync)} onChange={(event) => setCheckOptions((current) => ({ ...current, sync: event.target.checked }))} /> {S.check.sync}</label></details><button className="primaryAction" onClick={startRealScan}>{estimate || hasPreparedChecks || state?.task === "pairwise_compare" ? S.interview.start : S.interview.connectKey}</button></InterviewShell>;
    }
    if (screen === "scan" && scan) return <ScanScreen state={state} status={scan} onDone={() => setScreen("hub")} onCancel={cancelScan} />;
    if (screen === "hub" && state) return <Hub state={state} onMode={startMode} onList={(nextMode) => { setMode(nextMode); setScreen("list"); }} onOpenCard={(id) => { setMode("suspicious"); setCurrentId(id); setScreen("card"); }} onFinish={() => setScreen("finish")} onAdd={() => beginAddAnswers(state.root)} order={reviewOrder} onOrder={setReviewOrder} onSelfCheck={beginSelfCheck} onJudgeEvaluation={() => setScreen("judgeEvaluation")} />;
    if (screen === "addAnswers" && state) return <AddAnswersScreen state={state} inspection={addInspection} file={addFile} mapping={addMapping} onFile={inspectAddFile} onMapping={setAddMapping} onAdd={addAnswers} onBack={() => setScreen("hub")} />;
    if (screen === "list" && state) return <CategoryList state={state} mode={mode} onOpen={(id) => { setCurrentId(id); setScreen("card"); }} onBack={() => setScreen("hub")} />;
    if (screen === "card" && state && currentId && state.task === "pairwise_compare") return <CompareCardScreen state={state} currentId={currentId} mode={mode} onState={(next) => { setState(next); const id = firstCardId(next, mode); if (id) setCurrentId(id); }} onDone={() => setScreen("finish")} onBack={() => setScreen("hub")} />;
    if (screen === "card" && state && currentId) return <CardScreen state={state} assistant={assistant} currentId={currentId} mode={mode} blind={selfCheckIds.length > 0} selfCheckQueue={selfCheckIds.length ? selfCheckIds : undefined} onSelfCheckAdvance={() => { const next = selfCheckIds.slice(1); setSelfCheckIds(next); setCurrentId(next[0] || null); }} onState={(next) => { setState(next); if (!selfCheckIds.length) { const id = firstCardId(next, mode, reviewOrder); if (id) setCurrentId(id); } }} onDone={() => { setSelfCheckIds([]); setScreen("finish"); }} onBack={() => { setSelfCheckIds([]); setScreen("list"); }} />;
    if (screen === "finish" && state) return <Finish state={state} assistant={assistant} onNew={() => setScreen("name")} onDisagreements={(rows) => { setDisagreements(rows); setScreen("disagreements"); }} onRecheck={() => { setCheckOptions({ force: true }); void startRealScan({ force: true }); }} onJudgeEvaluation={() => setScreen("judgeEvaluation")} />;
    if (screen === "disagreements") return <DisagreementsScreen rows={disagreements} onBack={() => setScreen("finish")} />;
    if (screen === "judgeEvaluation" && state) return <JudgeEvaluationScreen state={state} onBack={() => setScreen("hub")} onOpenCase={(id) => { setCurrentId(id); setScreen("judgeCase"); }} />;
    if (screen === "judgeCase" && state && currentId) return <JudgeCaseScreen state={state} currentId={currentId} onState={setState} onBack={() => setScreen("judgeEvaluation")} />;
    if (screen === "key") return <KeyScreen provider={state?.llmProvider || judgeProvider} onSaved={() => state ? startRealScan() : setScreen("ready")} />;
    return <Home projects={projects} activeTask={activeTask} onCheck={() => setScreen("name")} onDemo={tryDemo} onOpen={openProject} onDelete={deleteProject} />;
  }, [projects, screen, state, name, dataPath, docsPath, kbKind, inspection, mapping, labelColumn, importLabels, estimate, mode, currentId, assistant, activeTask, baselineRoot, disagreements, addFile, addInspection, addMapping, checkOptions, judgeProvider, judgeModel, baseUrl, reviewOrder, selfCheckIds, botRunning, botReady, botError]);

  return (
    <div className="appShell" data-task={activeTask} data-theme={theme} data-screen={screen}>
      <Rail activeTask={activeTask} onSelectTask={selectTask} devOpen={devOpen} setDevOpen={setDevOpen} theme={theme} onThemeToggle={() => setTheme((current) => current === "light" ? "dark" : "light")} onHelp={() => setScreen("help")} />
      {content}
      {devOpen && <DeveloperPanel state={state} onState={setState} onClose={() => setDevOpen(false)} />}
      {onboardingOpen && <Onboarding onTryExample={() => { dismissOnboarding(); void tryDemo(true); }} onClose={dismissOnboarding} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
