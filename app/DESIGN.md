# PressF Desktop Design System

## Visual Thesis

PressF uses Apple-style Liquid Glass as a professional evaluation workstation: translucent frosted materials over module-tinted depth, crisp review tables, clear verdict language, and restrained motion.

The product is not a decorative demo. Glass is used for hierarchy and focus; dense evaluation surfaces stay legible.

## Module Hues

Module color is chrome only. It tints the active rail item, primary action, focus rings, ambient light, and the Check lens. Outcome state always uses semantic colors.

| Module | Task | Hue | RGB |
|---|---|---:|---:|
| Truth Check | `rag_faithfulness` | `#2ee58f` | `46, 229, 143` |
| Policy Check | `policy_compliance` | `#4aa8ff` | `74, 168, 255` |
| Search Quality | `retrieval_quality` | `#f7b64a` | `247, 182, 74` |
| Compare Versions | `pairwise_compare` | `#b18bff` | `177, 139, 255` |

## Semantic Colors

| Role | Token | Value |
|---|---|---:|
| Success | `--success` | `#34d17f` |
| Error | `--error` | `#ff5d63` |
| Warning | `--warning` | `#f3b545` |
| Neutral | `--neutral` | `#8290a0` |

Semantic colors mark review outcomes, warnings, and confidence state. Module hues never encode pass/fail.

## Liquid Glass Materials

| Token | Use |
|---|---|
| `--bg-0`, `--bg-1` | dark and light ambient backdrops |
| `--glass-1` | low elevation frosted panels |
| `--glass-2` | default controls and medium elevation panels |
| `--glass-3` | strong controls, headers, and active layers |
| `--glass-edge` | hairline specular edge |
| `--glass-edge-strong` | prominent top edge or active boundary |
| `--glass-inner` | subtle internal highlight |
| `--blur`, `--blur-strong` | saturated glass blur strengths |
| `--glow-1`, `--glow-2` | shadow plus specular inset highlight |

The backdrop uses soft module-tinted radial light sources so glass surfaces feel refractive without hiding text. Tables and quotes use glass panels but preserve high contrast.

## Radii

| Token | Value | Use |
|---|---:|---|
| `--radius-sm` | `12px` | inputs, compact controls |
| `--radius-md` | `18px` | rail items, rows, small panels |
| `--radius-lg` | `26px` | major panels |
| `--radius-xl` | `34px` | hero lens and large work surfaces |

## Typography

| Role | Family | Weight |
|---|---|---:|
| Display headings and key numbers | SF Pro Display fallback stack | 720-760 |
| UI labels and body copy | SF Pro Text fallback stack | 400-680 |
| Quotes, ids, file paths, numeric data | SF Mono fallback stack | 400-650 |

No serif fonts are used. Terminology is professional and evaluation-oriented: LLM judge, verdict, confidence, goldset, evaluation, retrieval, context, annotation, escalation, agreement, DPO pairs.

## Motion

| Pattern | Duration | Use |
|---|---:|---|
| Button lift | `180ms` | interactive affordance |
| Panel/card settle | `180ms` | workspace transitions |
| Scan ring pulse | `1600ms` loop | active checking state |
| Check lens breathe | `1600ms` hover loop | primary action feedback |

`prefers-reduced-motion: reduce` disables transitions and animations.

## Iconography

Icons come from `lucide-react` with rounded 2px strokes. Verdict categories use compact professional labels:

`HC`, `HU`, `FR`, `PA`, `PV`, `PR`, `MR`, `LC`, `OK`.

## Screen Rules

- Home: one Liquid Glass Check lens, one primary action, module context visible in the rail.
- Setup: one operational question per screen, one input target, no marketing copy.
- Scan: live progress with glass lens and streaming findings.
- Results hub: reads as an evaluation report with metadata, stats, and flagged rows.
- Review card: one example, evidence panes, decision controls, undo always visible.
- Pairwise review: answers are anonymized as Left/Right, with Left/Right/Tie controls.
- Finish: export/report actions and evaluation summary. No celebratory effects.
