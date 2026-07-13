# Markup guidelines: fluxus-demo

## Task
The factual accuracy of the bot's answers about API Fluxus regarding the documentation.

## Tags
- **p (positive)** - the answer is factually correct and confirmed by the knowledge base.
Refusal to answer when there really is no answer in the database is also **p**.
- **f (negative)** - the answer contradicts the database, is made up (there is no answer in the database, but the model answered),
is only partially correct, or the model refused, although the answer is in the database.
- **s (skip)** - can’t solve it. Be sure to include a note: every note is a signal,
that this file needs to be clarified.

## Borderline cases
<!-- add as you mark; notes for skips - candidates here -->
- The answer is correct, but incomplete: p, if what is said is true and sufficient for the question; f if the omission distorts the essence.
- Minor inaccuracies in wording without distortion of facts: p.
