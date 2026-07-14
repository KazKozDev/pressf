# Annotation Guidelines: fluxus-demo

## Task
Factual faithfulness of bot answers about the Fluxus API against the documentation.

## Labels
- **p (positive)** — the answer is factually correct and supported by the knowledge base.
  Refusing to answer when the answer is genuinely absent from the knowledge base is also **p**.
- **f (negative)** — the answer contradicts the knowledge base, is fabricated (the answer is not in the knowledge base but the model answered anyway),
  is only partially correct, or the model refused to answer despite the answer being in the knowledge base.
- **s (skip)** — cannot decide. Always include a note: each note is a signal
  that this guidelines file needs clarification.

## Edge Cases
<!-- add as you annotate; notes on skips are candidates to go here -->
- Answer is correct but incomplete: p if what is stated is correct and sufficient for the question; f if the omission distorts the meaning.
- Minor wording inaccuracies without factual distortion: p.
