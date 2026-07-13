import type { LlmProvider } from "../main/types";

export type FindingCategory = "contradicts" | "made_up" | "bad_refusal" | "incomplete" | "policy_break" | "search_partial" | "search_missing" | "uncertain" | "looks_fine";

export const S = {
  appName: "PressF",
  moduleTruth: "Truth Check",
  soon: "soon",
  onboarding: {
    steps: [
      {
        title: "Welcome to PressF",
        body: "An evaluation workbench for RAG systems and LLM assistants. An LLM judge fact-checks every answer against your documents; you confirm each verdict with one keypress.",
        next: "Next"
      },
      {
        title: "Start with the sample",
        body: "The bundled sample project has answers and a knowledge base ready to review — no setup. It's the fastest way to see the whole flow end to end.",
        next: "Next"
      },
      {
        title: "Connect your judge",
        body: "To check your own data, the judge runs on Claude (or OpenAI). Add your API key in Settings when you're ready — it stays only on this Mac.",
        next: "Get started"
      }
    ],
    skip: "Skip",
    tryExample: "Show the first real error",
    stepLabel: (i: number, n: number) => `${i} of ${n}`
  },
  close: "Close",
  help: {
    nav: "Help",
    title: "About PressF",
    tagline: "An evaluation workbench for RAG systems and LLM assistants.",
    whatTitle: "What it is",
    whatBody: "An LLM judge fact-checks every answer against your own documents and drafts a verdict with verbatim quotes. You confirm or overrule each one with a single keypress. The output is a human-verified goldset and a measured level of trust in the judge itself.",
    whoTitle: "Who it's for",
    whoBody: "Teams shipping anything that answers from documents — support bots, RAG apps, knowledge-base assistants, and AI agents. Anyone who needs evidence, not a hunch, that their system tells the truth, follows the rules, retrieves the right context, or actually improved after a change.",
    edgeTitle: "The key idea",
    edgeBody: "Manual evaluation is accurate but slow; automatic evaluation is fast but unproven. PressF splits the work: the judge does the tedious part — breaking each answer into claims, searching the docs, and quoting evidence — while you do only the fast part, yes or no. You get goldset-quality labels at a fraction of the cost, plus a number that tells you how far the judge can be trusted on its own.",
    modulesTitle: "Four kinds of evaluation",
    modules: [
      { name: "Truth Check", body: "Does the answer contradict or invent facts against your documents?" },
      { name: "Policy Check", body: "Does the answer break a rule your system must never break?" },
      { name: "Search Quality", body: "Did retrieval return enough context to answer at all?" },
      { name: "Compare Versions", body: "Is the new version better than the old one on the same questions?" }
    ],
    trustTitle: "How trust is earned",
    trustBody: "First you label answers with the judge's help. The report then shows how often you and the judge agreed. High agreement means the judge can triage routine cases on its own; low agreement means tighter guidelines or a stronger model. A human always stays in the loop for doubtful and high-impact answers.",
    hoodTitle: "No lock-in",
    hoodBody: "PressF is a graphical layer over the pressf command-line tool. Every project is plain files — examples, verdicts, and annotations as JSONL — that the terminal reads and writes too. Open Settings to inspect them or copy the equivalent CLI command.",
    contactTitle: "Author & contact",
    contactBody: "Built by KazKozDev. Questions, ideas, or bug reports are welcome.",
    links: [
      { label: "GitHub", value: "github.com/KazKozDev", href: "https://github.com/KazKozDev" },
      { label: "Email", value: "kazkozdev@gmail.com", href: "mailto:kazkozdev@gmail.com" },
      { label: "LinkedIn", value: "linkedin.com/in/kazkozdev", href: "https://www.linkedin.com/in/kazkozdev" }
    ]
  },
  modules: {
    policy: "Policy Check",
    search: "Search Quality",
    compare: "Compare Versions"
  },
  tasks: {
    homeTitle: {
      rag_faithfulness: "Is your AI telling the truth?",
      policy_compliance: "Does your AI follow the rules?",
      retrieval_quality: "Did your AI find the right context?",
      pairwise_compare: "Which answer should win?"
    },
    suspiciousTitle: {
      rag_faithfulness: "Flagged answers",
      policy_compliance: "Policy violations",
      retrieval_quality: "Retrieval gaps",
      pairwise_compare: "Version pairs"
    },
    subtitle: {
      rag_faithfulness: "Works with anything that answers from your documents: support bots, RAG apps, knowledge-base assistants, AI agents.",
      policy_compliance: "For teams with rules the system must never break: refund limits, compliance language, escalation requirements.",
      retrieval_quality: "For RAG pipelines where wrong answers might be a retrieval problem, not a model problem.",
      pairwise_compare: "For comparing two versions of the same system on the same questions before you ship a change."
    },
    steps: {
      rag_faithfulness: [
        "PressF compares each answer with your documents.",
        "It flags answers that contradict or invent facts.",
        "You confirm or overrule each flagged answer."
      ],
      policy_compliance: [
        "PressF checks each answer against your rules document.",
        "It flags answers that break a rule, and quotes which one.",
        "You confirm or overrule each flagged violation."
      ],
      retrieval_quality: [
        "PressF looks at what your search retrieved for each question.",
        "It flags cases where retrieval didn't return enough to answer.",
        "You confirm whether the retrieved context was really insufficient."
      ],
      pairwise_compare: [
        "PressF shows the old and new answer side by side.",
        "You judge which one is better, or call it a tie.",
        "The results tell you whether the new version is an improvement."
      ]
    }
  },
  home: {
    title: "Is your AI telling the truth?",
    workspaceTitle: "Evaluation workspace",
    check: "New evaluation",
    newEvaluation: "New evaluation",
    tryExample: "Show a real error",
    how: "How it works",
    past: "Recent checks",
    status: "Workspace status",
    active: "Active checks",
    reviewed: "Reviewed answers",
    projects: "Projects",
    answers: "answers",
    flagged: "flagged",
    projectHint: "Open a project to resume review, inspect results, or export evidence.",
    empty: "No checks yet. The example is ready.",
    recentSummary: (bad: number, done: number) => `${bad} flagged · ${done} checked · Continue`,
    remove: "Delete",
    removeConfirm: "Delete this project and all its data?",
    removeYes: "Delete",
    removeNo: "Cancel"
  },
  addAnswers: {
    action: "Add answers",
    title: (name: string) => `Add fresh ${name} answers`,
    body: "PressF will deduplicate them against this project and continue example IDs. Only new answers will need a judge check.",
    mapping: "These columns differ from the original import. Confirm how to map them.",
    confirm: "Add answers"
  },
  export: {
    pairs: "Export training pairs (DPO)",
    showPairs: "Show DPO pairs in Finder",
    formats: "Goldset formats"
  },
  check: {
    advanced: "Advanced check controls",
    force: "Re-run all answers (force)",
    limit: "Only first N answers",
    limitHint: (count: number) => `Partial dry-run: estimate and spend cover only ${count} answers.`,
    sync: "Synchronous (no Batch API)"
  },
  review: {
    order: "Review order",
    confidence: "Confidence",
    informative: "Most informative",
    random: "Random",
    original: "Original file order",
    selfCheck: "Re-check yourself"
  },
  gate: {
    title: "Quality gate",
    body: "The same pass/fail bar the CI command uses: share of good answers among everything labeled.",
    threshold: "Minimum share of good answers",
    pass: "PASS",
    fail: "FAIL",
    empty: "Nothing to score yet — run the judge or review some answers first.",
    score: (share: string, passed: number, n: number) => `${share} good answers — ${passed} of ${n}`,
    ci: (lo: string, hi: string) => `95% CI ${lo}–${hi}`,
    sourceHuman: "based on your labels",
    sourceJudge: "based on judge verdicts only — review answers to confirm",
    cliHint: (root: string, threshold: string) => `lazy gate ${root} --min-faithfulness ${threshold}`
  },
  quality: {
    title: "Judge quality",
    agreement: (share: string, lo: string, hi: string, n: number) => `Agreement with you: ${share} (95% CI ${lo}–${hi}, n=${n})`,
    flagLine: (precision: string, recall: string, f1: string) => `Flag precision ${precision} · recall ${recall} · F1 ${f1}`,
    flagCaption: "How well judge flags (f) match your f labels.",
    perCategory: "Agreement by finding type",
    perCategoryRow: (n: number) => `on ${n}`,
    selfCheck: (share: string, n: number) => `Self-consistency: ${share} on ${n} re-checked answers`,
    kappa: "Between reviewers (Cohen's kappa)",
    kappaRow: (a: string, b: string, n: number) => `${a} × ${b} · ${n} shared`,
    needMore: "Review a few answers to unlock judge quality numbers."
  },
  interview: {
    back: "Back",
    next: "Next",
    nameQ: "What are you evaluating?",
    namePlaceholder: "Helpdesk bot",
    baselineQ: "Choose the baseline check",
    baselineHint: "PressF will compare its answers with a new answers file. The baseline project stays unchanged.",
    noBaseline: "Finish at least one check before comparing versions.",
    answersQ: (name: string) => `Show me ${name}'s answers`,
    newAnswersQ: (name: string) => `Show me the new ${name} answers`,
    runBot: "Run my bot on this goldset",
    runBotHint: "Use the bot connector saved on the baseline project instead of dropping a file.",
    runningBot: "Running your bot on the baseline questions…",
    botOutputReady: "Fresh answers are ready and selected for comparison.",
    answersHint: "CSV, JSONL, or a simple table with one question and one answer per row.",
    pasteFile: "Paste file path",
    chooseFile: "Choose file",
    docsQ: (name: string) => `Show me the documents ${name} should answer from`,
    rulesQ: (name: string) => `Show me the rules ${name} should follow`,
    searchQ: (name: string) => `Show me the documents ${name}'s search should find`,
    docsHint: "Choose the folder with the source files.",
    rulesHint: "Choose the folder with your policy or rule files.",
    searchHint: "Choose the folder with the pages your search system should retrieve from.",
    searchContextRequired: "Search Quality needs the retrieved-context column from your system. Without it, PressF would only measure its own search, so this check cannot start.",
    pasteDocs: "Paste folder path",
    chooseFolder: "Choose folder",
    kbFolder: "Folder with documents",
    kbChunks: "Exported chunks (JSONL)",
    chunksHint: "One JSON object per line with a text field — the universal export from any vector store.",
    pasteChunks: "Paste chunks file path",
    chunksPath: "/path/to/chunks.jsonl",
    labelOffer: "I found human decisions in this file. Import them too?",
    questionColumn: "Which column is the question?",
    answerColumn: "Which column is the answer?",
    ready: "Ready.",
    start: "Start",
    connectKey: "Connect key",
    estimateFallback: "Connect a key to estimate time and cost.",
    fileShape: "question | answer",
    sampleQuestion: "How do I cancel?",
    sampleAnswer: "You can cancel from billing.",
    answersPath: "/path/to/answers.csv",
    docsPath: "/path/to/docs",
    readyLine: (count: number, cost: string | null) => `Checking ${count} answers: about a few minutes${cost ? ` and from ${cost}` : "."}`
  },
  scan: {
    title: "Checking answers",
    done: "All checked.",
    cancel: "Cancel check",
    viewResults: "View results",
    cancelled: "Check cancelled.",
    failed: "Check stopped with an error.",
    starting: "Starting judge check…",
    suspicious: "flagged",
    checked: "checked",
    progress: (checked: number, total: number, suspicious: number) => `${checked} of ${total} checked · ${suspicious} flagged`
  },
  hub: {
    title: "Flagged answers",
    primary: "Review flagged",
    fine: "Also review the ones that look fine",
    open: "Open",
    none: "Nothing flagged.",
    checked: (count: number) => `${count} answers checked`,
    compare: "Compare versions",
    filters: {
      category: "Category",
      confidence: "Confidence",
      all: "All",
      high: "≥ 0.90",
      medium: "0.70–0.89",
      low: "< 0.70"
    },
    looksFine: "Looks fine",
    meta: {
      model: "Judge model",
      lastRun: "Last run",
      cost: "Run cost",
      escalations: "Escalations",
      flaggedShare: "Flagged",
      passShare: "Pass",
      meanConfidence: "Mean confidence",
      faithfulness: "Good answers"
    },
    table: {
      question: "Question",
      category: "Category",
      confidence: "Confidence",
      status: "Status",
      pending: "Pending",
      reviewed: "Reviewed"
    }
  },
  card: {
    answered: (name: string) => `${name} answered:`,
    docsSay: "Your documents say:",
    rulesSay: "Your rules say:",
    searchFound: "Search found:",
    noDoc: "Your documents don't answer this question.",
    question: "Is the answer correct?",
    yes: "Yes",
    no: "No",
    skip: "skip",
    skipNote: "Why skip this one?",
    undo: "Undo",
    details: "Details",
    rawCaption: "Shown in the language of your data.",
    coachTitle: "You are the teacher",
    coachBody: "The judge proposes a verdict from the document evidence. Confirm or correct it with the same shortcuts shown on the buttons.",
    coachDone: "Start reviewing",
    coachHelp: "Review help",
    left: (n: number) => `${n} left`,
    blind: "Hide judge view",
    revealJudge: "Reveal judge view",
    judgeLabel: "Judge's take",
    judgePass: "Looks correct",
    judgeFail: "Looks wrong",
    judgeConfidence: (c: number) => `confidence ${(Number(c) || 0).toFixed(2)}`
  },
  compare: {
    leftAnswer: "Left answer",
    rightAnswer: "Right answer",
    question: "Which version is better?",
    left: "Left",
    right: "Right",
    tie: "Tie"
  },
  compareResult: {
    title: "Release decision",
    winRate: (rate: string, lo: string, hi: string, n: number) => `New version wins ${rate} of ${n} decided pairs (95% CI ${lo}–${hi}).`,
    pValue: (p: string) => `Sign test p=${p}; ties are excluded.`,
    leftBias: (share: string) => `Left-side picks: ${share}.`,
    ship: "New version is better with 95% confidence — safe to ship.",
    hold: "This sample does not establish that the new version is better. Label more pairs.",
    worse: "The new version is worse with 95% confidence — do not ship it.",
    empty: "No decided pairs yet — compare the versions before making a release decision.",
    judgeAgreement: (share: string, n: number) => `Judge agrees with your pair choices on ${share} of ${n} pairs.`
  },
  finish: {
    done: "Done!",
    save: "Save report",
    again: (name: string) => `Check again after you fix ${name}`,
    saved: "Report saved.",
    showInFinder: "Show in Finder",
    disagreements: "View disagreements",
    trust: "Checker trust",
    improveJudge: "Improve the judge",
    calibrationTitle: "Suggested guideline update",
    calibrationBody: "Review this proposal before adding it to GUIDELINES.md. It will be used on the next judge check.",
    calibrationAccept: "Accept update",
    calibrationReject: "Reject",
    calibrationApplied: "Guidelines updated. Re-check answers with the improved judge?",
    calibrationRecheck: "Re-check now",
    realErrors: "real errors",
    falseAlarms: "false alarms",
    summary: (done: number, realErrors: number, falseAlarms: number) => `You checked ${done} answers — ${realErrors} real errors, ${falseAlarms} false alarms.`,
    pairwiseSummary: (better: number, worse: number, ties: number) => `New version: better on ${better}, worse on ${worse}, tie on ${ties}.`
  },
  disagreements: {
    title: "Judge disagreements",
    none: "No disagreements were exported.",
    judge: "Judge recommendation",
    human: "Human decision",
    note: "Review note"
  },
  judge: {
    title: "Choose a judge",
    body: "Use the provider that can access your evaluation data. You can change the model later in lazy.yaml.",
    provider: "Judge provider",
    model: "Judge model",
    modelOptional: "Use provider default",
    baseUrl: "Compatible API base URL",
    keyHint: (provider: LlmProvider) => provider === "openai" ? "PressF will use OPENAI_API_KEY." : provider === "openai_compatible" ? "PressF will use OPENAI_COMPAT_API_KEY." : "PressF will use ANTHROPIC_API_KEY."
  },
  key: {
    title: (provider: LlmProvider) => `Connect your ${provider === "openai" ? "OpenAI" : provider === "openai_compatible" ? "compatible API" : "Anthropic"} key.`,
    body: (provider: LlmProvider) => `Paste ${provider === "openai" ? "OPENAI_API_KEY" : provider === "openai_compatible" ? "OPENAI_COMPAT_API_KEY" : "ANTHROPIC_API_KEY"}. It stays only on this Mac.`,
    save: "Save key",
    placeholder: "sk-ant-..."
  },
  dev: {
    title: "Settings",
    body: "Configure the LLM judge and inspect the raw project files this app reads and writes.",
    judgeHeading: "LLM judge",
    provider: "Provider",
    providerAnthropic: "Anthropic (Claude)",
    providerOpenai: "OpenAI",
    providerCompatible: "OpenAI-compatible (Ollama, vLLM, Together…)",
    judgeModel: "Judge model",
    baseUrl: "Base URL",
    baseUrlPlaceholder: "http://localhost:11434/v1",
    budget: "Budget cap (USD)",
    escalation: "Escalation model",
    escalationHint: "Leave empty to disable escalation for this provider.",
    escalationThreshold: "Escalation threshold",
    keyHint: "Key is read from the environment: ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENAI_COMPAT_API_KEY.",
    save: "Save settings",
    saved: "Saved. New settings apply on the next judge run.",
    reviewerHeading: "Reviewer",
    reviewerName: "Reviewer name",
    reviewerHint: "Written into every decision as the annotator. With several reviewers, the report can measure agreement between people.",
    reviewerSave: "Save name",
    reviewerSaved: "Reviewer name saved.",
    botHeading: "Bot connector",
    botKind: "Connection type",
    botCommand: "Command",
    botUrl: "URL",
    botMethod: "HTTP method",
    botHeaders: "Headers (JSON)",
    botBody: "Request body",
    botAnswerPath: "Answer path",
    botTimeout: "Timeout (seconds)",
    botSave: "Save bot connector",
    botSaved: "Bot connector saved.",
    retrieverHeading: "Knowledge base",
    retriever: "Retriever",
    retrieverKind: "Storage",
    retrieverTopK: "Chunks per search (top_k)",
    retrieverSave: "Save knowledge base",
    retrieverSaved: "Knowledge base saved. It is used on the next judge run.",
    retrieverHint: "Point the judge at where your knowledge base actually lives. API keys and field names stay in lazy.yaml.",
    noProject: "Open a project to configure its judge.",
    files: "Raw files",
    command: "Terminal equivalent"
  },
  developerFiles: {
    examples: "examples.jsonl",
    verdicts: "verdicts.jsonl",
    annotations: "annotations.jsonl",
    exportCommand: (root: string) => `lazy export ${root}`
  },
  categories: {
    contradicts: {
      title: "Hallucination - contradicts docs",
      cardWord: "contradicted",
      detail: "The answer conflicts with retrieved document evidence."
    },
    made_up: {
      title: "Hallucination - unanswerable",
      cardWord: "not found",
      detail: "The answer contains unsupported information."
    },
    bad_refusal: {
      title: "False refusal",
      cardWord: "refused",
      detail: "The model refused despite available document evidence."
    },
    incomplete: {
      title: "Partial answer",
      cardWord: "incomplete",
      detail: "The answer is partly supported but misses required information."
    },
    policy_break: {
      title: "Policy violation",
      cardWord: "violates policy",
      detail: "The answer violates an applicable rule."
    },
    search_partial: {
      title: "Partial retrieval",
      cardWord: "partial context",
      detail: "Retrieved context contains some evidence but not enough to answer fully."
    },
    search_missing: {
      title: "Missing retrieval",
      cardWord: "missing context",
      detail: "Retrieved context does not answer the question."
    },
    uncertain: {
      title: "Low confidence",
      cardWord: "unclear",
      detail: "The LLM judge confidence is below the review threshold."
    },
    looks_fine: {
      title: "Correct",
      cardWord: "correct",
      detail: "The verdict is supported by the available evidence."
    }
  } satisfies Record<FindingCategory, { title: string; cardWord: string; detail: string }>,
  categoryMarks: {
    contradicts: { mark: "HC", label: "hallucination contradicts docs" },
    made_up: { mark: "HU", label: "hallucination unanswerable" },
    bad_refusal: { mark: "FR", label: "false refusal" },
    incomplete: { mark: "PA", label: "partial answer" },
    policy_break: { mark: "PV", label: "policy violation" },
    search_partial: { mark: "PR", label: "partial retrieval" },
    search_missing: { mark: "MR", label: "missing retrieval" },
    uncertain: { mark: "LC", label: "low confidence" },
    looks_fine: { mark: "OK", label: "correct" }
  } satisfies Record<FindingCategory, { mark: string; label: string }>,
  trustCaption: {
    unavailable: "Agreement is unavailable until at least one p/f annotation is recorded.",
    high: "The LLM judge is aligned on this sample; continue spot checks on high-impact answers.",
    medium: "The judge is useful for prioritization, but human review should stay in the loop.",
    low: "Treat judge verdicts as triage only until agreement improves."
  }
} as const;
