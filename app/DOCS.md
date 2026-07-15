# About PressF

*An evaluation workbench for RAG systems and LLM assistants.*

This is the same content shown in the app's **Help** screen, kept here so it lives outside
the app too.

## What it is

An LLM judge fact-checks every answer against your own documents and drafts a verdict with
verbatim quotes. You confirm or overrule each one with a single keypress. The output is a
human-verified goldset and a measured level of trust in the judge itself.

## Who it's for

Teams shipping anything that answers from documents — support bots, RAG apps,
knowledge-base assistants, and AI agents. Anyone who needs evidence, not a hunch, that
their system tells the truth, follows the rules, retrieves the right context, or actually
improved after a change.

## The key idea

Manual evaluation is accurate but slow; automatic evaluation is fast but unproven. PressF
splits the work: the judge does the tedious part — breaking each answer into claims,
searching the docs, and quoting evidence — while you do only the fast part, yes or no. You
get goldset-quality labels at a fraction of the cost, plus a number that tells you how far
the judge can be trusted on its own.

## Five kinds of evaluation

- **Truth Check** — Does the answer contradict or invent facts against your documents?
- **Policy Check** — Does the answer break a rule your system must never break?
- **Search Quality** — Did retrieval return enough context to answer at all?
- **Compare Versions** — Is the new version better than the old one on the same questions?
- **Agent Trajectory** — Did the agent take a sound path to the answer, or fabricate tool results, loop, or act unsafely?

## How trust is earned

First you label answers with the judge's help. The report then shows how often you and the
judge agreed. High agreement means the judge can triage routine cases on its own; low
agreement means tighter guidelines or a stronger model. A human always stays in the loop
for doubtful and high-impact answers.

## No lock-in

PressF is a graphical layer over the `pressf` command-line tool. Every project is plain
files — examples, verdicts, and annotations as JSONL — that the terminal reads and writes
too. Open Settings to inspect them or copy the equivalent CLI command.

## Author & contact

Built by KazKozDev. Questions, ideas, or bug reports are welcome.

- GitHub: <https://github.com/KazKozDev>
- Email: <kazkozdev@gmail.com>
- LinkedIn: <https://www.linkedin.com/in/kazkozdev>
