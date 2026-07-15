"""Final report: numbers, agent×person matrix, disagreements, skips, cost."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import Project
from ..llm.prompts import truncate_tool_result


def write_report(project: Project) -> Path:
    verdicts = project.load_verdicts()
    annotations = project.effective_annotations()
    examples = {ex.id: ex for ex in project.load_examples()}

    counts = {"p": 0, "f": 0, "s": 0}
    matrix = {("p", "p"): 0, ("p", "f"): 0, ("f", "p"): 0, ("f", "f"): 0}
    disagreements: list[str] = []
    skips: list[str] = []
    elapsed: list[int] = []

    for eid, ann in annotations.items():
        counts[ann.label] += 1
        if ann.elapsed_ms:
            elapsed.append(ann.elapsed_ms)
        ex = examples.get(eid)
        v = verdicts.get(eid)
        q = (ex.question[:100] if ex else eid)
        if ann.label == "s":
            skips.append(f"- `{eid}` — {q} — note: {ann.note or '—'}")
            continue
        if v is not None:
            matrix[(v.recommendation, ann.label)] = matrix.get((v.recommendation, ann.label), 0) + 1
            if v.recommendation != ann.label:
                disagreements.append(
                    f"- `{eid}` — {q}\n  agent: **{v.recommendation}** ({v.category}, confidence {v.confidence:.2f}) → human: **{ann.label}**"
                    + (f" — note: {ann.note}" if ann.note else "")
                )

    agreed = matrix[("p", "p")] + matrix[("f", "f")]
    judged = sum(matrix.values())
    agreement = f"{agreed / judged:.1%}" if judged else "—"

    #confidence interval of agreement (Wilson, 95%) - «84% ± 3%, n=...» instead of the bare fraction
    from ..stats import flag_precision_recall, per_category_agreement, wilson_interval

    if judged:
        lo, hi = wilson_interval(agreed, judged)
        half = (hi - lo) / 2 * 100
        agreement_ci = f"**{agreement}** ± {half:.0f}% (95% CI, n={judged})"
    else:
        agreement_ci = "—"

    #judge's accuracy on class «problem» (f) against a human reference
    pf_pairs = [
        (verdicts[eid].recommendation, ann.label)
        for eid, ann in annotations.items()
        if ann.label in ("p", "f") and eid in verdicts and verdicts[eid].recommendation in ("p", "f")
    ]
    prf = flag_precision_recall(pf_pairs)
    cat_rows = [
        f"| {cat} | {total} | {frac:.0%} |"
        for cat, (total, frac) in sorted(
            per_category_agreement(
                [(verdicts[eid].category, verdicts[eid].recommendation, ann.label)
                 for eid, ann in annotations.items() if eid in verdicts]
            ).items(),
            key=lambda kv: kv[1][0], reverse=True,
        )
    ] or ["| — | 0 | — |"]
    total_cost = sum(v.cost_usd for v in verdicts.values())
    avg_sec = f"{(sum(elapsed) / len(elapsed) / 1000):.1f} c" if elapsed else "—"
    cfg = project.load_config()

    #agreement on confidence buckets - the basis for future auto-tagging of confident
    buckets = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
    bucket_rows = []
    for lo, hi in buckets:
        b_agreed = b_total = 0
        for eid, ann in annotations.items():
            v = verdicts.get(eid)
            if v is None or ann.label not in ("p", "f") or not (lo <= v.confidence < hi):
                continue
            b_total += 1
            b_agreed += int(v.recommendation == ann.label)
        pct = f"{b_agreed / b_total:.0%}" if b_total else "—"
        bucket_rows.append(f"| {lo:.1f}–{min(hi, 1.0):.1f} | {b_total} | {pct} |")

    from ..stats import inter_annotator_kappa

    kappa_pairs = inter_annotator_kappa(project.effective_annotations_by_annotator())
    kappa_rows = [
        f"- {a or '(no name)'} × {b or '(no name)'}: **κ={k:.2f}** (general:{n})"
        for a, b, n, k in kappa_pairs
    ]

    from ..review import selfcheck_agreement

    sc = selfcheck_agreement(project)
    sc_line = (
        f"- Self-check (agreement with yourself): **{sc[0] / sc[1]:.1%}** ({sc[0]}from{sc[1]})"
        if sc
        else "- Self-check was not carried out (lazy review --self-check)"
    )

    policy_counts: dict[str, int] = {}
    if cfg.task == "policy_compliance":
        for ann in annotations.values():
            v = verdicts.get(ann.example_id)
            if ann.label == "f" and v and v.claims and v.claims[0].evidence:
                key = v.claims[0].evidence[0].text[:120]
                policy_counts[key] = policy_counts.get(key, 0) + 1
    policy_rows = [
        f"- {rule}: {count}"
        for rule, count in sorted(policy_counts.items(), key=lambda item: item[1], reverse=True)
    ] or ["No confirmed violations."]

    search_counts: dict[str, int] = {}
    if cfg.task == "retrieval_quality":
        for ann in annotations.values():
            v = verdicts.get(ann.example_id)
            if ann.label == "f" and v:
                search_counts[v.category] = search_counts.get(v.category, 0) + 1
    search_rows = [
        f"- {category}: {count}"
        for category, count in sorted(search_counts.items(), key=lambda item: item[1], reverse=True)
    ] or ["No confirmed search issues."]

    pairwise = None
    if cfg.task == "pairwise_compare":
        from ..stats import pairwise_summary

        pairwise = pairwise_summary(project.effective_pairwise_annotations().values())

    trajectory_lines: list[str] = []
    if cfg.task == "agent_trajectory":
        categories = [
            "trajectory_ok", "trajectory_inefficient", "trajectory_unfaithful",
            "trajectory_unsafe", "trajectory_wrong_answer",
        ]
        category_counts = {category: sum(v.category == category for v in verdicts.values()) for category in categories}
        total_verdicts = len(verdicts)
        issue_counts: dict[str, int] = {}
        failures: list[str] = []
        lengths = [len(ex.trajectory or []) for ex in examples.values() if ex.trajectory]
        for eid, verdict in verdicts.items():
            ex = examples.get(eid)
            added_failure = False
            for finding in verdict.step_issues or []:
                if finding.issue_kind:
                    issue_counts[finding.issue_kind] = issue_counts.get(finding.issue_kind, 0) + 1
                if not finding.ok and ex:
                    step = next((s for s in ex.trajectory or [] if s.index == finding.step_index), None)
                    tool = step.tool.name if step and step.tool else "—"
                    excerpt = ""
                    if step and step.tool:
                        excerpt = f"args={truncate_tool_result(str(step.tool.arguments), 240)} result={truncate_tool_result(step.tool.result, 240)}"
                    elif step:
                        excerpt = truncate_tool_result(step.content, 240)
                    failures.append(f"- `{eid}` — **{verdict.category}** — step {finding.step_index}, tool {tool}, "
                                    f"{finding.issue_kind or 'other'}: {finding.issue or '—'}\n  {excerpt}")
                    added_failure = True
            if verdict.category != "trajectory_ok" and not added_failure:
                failures.append(f"- `{eid}` — **{verdict.category}** — step —, tool —: {verdict.reasoning}")
        category_rows = [f"| {cat} | {category_counts[cat]} | {(category_counts[cat] / total_verdicts if total_verdicts else 0):.0%} |" for cat in categories]
        issue_rows = [f"- {kind}: {count}" for kind, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))] or ["No step issues."]
        average = f"{sum(lengths) / len(lengths):.1f}" if lengths else "—"
        trajectory_lines = [
            "## Trajectory analysis", "", "### Category breakdown", "",
            "| category | count | percentage |", "|---|---:|---:|", *category_rows,
            "", "### Issue kinds", "", *issue_rows,
            "", f"### Average trajectory length\n\n{average} steps", "",
            "### Failed examples", "", *(failures or ["No failed trajectory findings."]), "",
        ]

    lines = [
        f"# Report: {cfg.project}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Results",
        f"- Total examples: {len(examples)}",
        f"- Reviewed: {len(annotations)} (p: {counts['p']}, f: {counts['f']}, s: {counts['s']})",
        f"- Human/judge agreement: {agreement_ci} ({agreed} of {judged})",
        f"- Judge precision on flags (class f): {prf['precision']:.0%}, "
        f"recall {prf['recall']:.0%}, F1 {prf['f1']:.0%}",
        sc_line,
        f"- Fact check cost: ${total_cost:.4f}",
        f"- Average time per example: {avg_sec}",
        "",
        "## Judge × human matrix",
        "",
        "| judge \\ human | p | f |",
        "|---|---|---|",
        f"| **p** | {matrix[('p', 'p')]} | {matrix[('p', 'f')]} |",
        f"| **f** | {matrix[('f', 'p')]} | {matrix[('f', 'f')]} |",
        "",
        "## Agreement by confidence bucket",
        "",
        "| confidence | examples | agreement |",
        "|---|---|---|",
        *bucket_rows,
        "",
        "## Judge accuracy by category",
        "",
        "| judge category | reviewed | human agreement |",
        "|---|---|---|",
        *cat_rows,
        "",
        *(["## Agreement between markers (Cohen's kappa)", "", *kappa_rows, ""]
          if kappa_rows else []),
        f"## Disagreements ({len(disagreements)}) — calibration material",
        "",
        *(disagreements or ["No."]),
        "",
        f"## Skips ({len(skips)}) — signals about holes in guidelines",
        "",
        *(skips or ["No."]),
        "",
    ]
    if cfg.task == "policy_compliance":
        lines += [
            "## Violations according to the rules",
            "",
            *policy_rows,
            "",
        ]
    if cfg.task == "retrieval_quality":
        lines += [
            "## Search problems",
            "",
            *search_rows,
            "",
        ]
    if cfg.task == "pairwise_compare":
        assert pairwise is not None
        rate = f"{pairwise.b_win_rate:.1%}" if pairwise.b_win_rate is not None else "—"
        p_value = f"{pairwise.p_value:.4f}" if pairwise.p_value is not None else "—"
        left_bias = f"{pairwise.left_pick_rate:.1%}" if pairwise.left_pick_rate is not None else "—"
        lines += [
            "## Version comparison",
            "",
            f"- A wins: {pairwise.a_wins}",
            f"- B wins: {pairwise.b_wins}",
            f"- Ties: {pairwise.ties}",
            f"- Decided pairs: {pairwise.decided}",
            f"- B win rate: **{rate}** (95% CI {pairwise.ci_low:.1%}–{pairwise.ci_high:.1%})",
            f"- Sign test: p={p_value} (ties excluded)",
            f"- Left-side selections: {left_bias} (positional-bias check)",
            f"- Conclusion: **{pairwise.decision}**",
            "",
        ]
    if trajectory_lines:
        lines += trajectory_lines
    project.out_dir.mkdir(parents=True, exist_ok=True)
    path = project.out_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
