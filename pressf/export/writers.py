"""Goldset export: JSONL (always self-described) and CSV."""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import __version__
from ..config import Project
from ..io import write_jsonl_atomic


def _build_records(project: Project) -> list[dict[str, Any]]:
    verdicts = project.load_verdicts()
    annotations = project.effective_annotations()
    records: list[dict[str, Any]] = []
    for ex in project.load_examples():
        ann = annotations.get(ex.id)
        if ann is None:
            continue  #unmarked ones do not go into the gold set
        v = verdicts.get(ex.id)
        records.append(
            {
                "id": ex.id,
                "question": ex.question,
                "answer": ex.answer,
                "label": ann.label,
                "note": ann.note,
                "agent_recommendation": v.recommendation if v else None,
                "agent_category": v.category if v else None,
                "agent_confidence": v.confidence if v else None,
                "agent_reasoning": v.reasoning if v else None,
                "agreed_with_agent": ann.agreed_with_agent,
                "claims": [c.model_dump() for c in v.claims] if v else [],
                "annotated_at": ann.ts.isoformat(),
            }
        )
    return records


def _meta(project: Project, records: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = project.load_config()
    guidelines = project.load_guidelines()
    labels = [r["label"] for r in records]
    return {
        "_meta": {
            "tool": f"pressf {__version__}",
            "project": cfg.project,
            "task": cfg.task,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "guidelines_sha256": hashlib.sha256(guidelines.encode()).hexdigest()[:16],
            "judge_model": cfg.llm.judge_model,
            "escalation_model": cfg.llm.escalation_model,
            "counts": {label: labels.count(label) for label in ("p", "f", "s")},
            "total": len(records),
        }
    }


def export_goldset(project: Project, formats: list[str] | None = None) -> list[Path]:
    cfg = project.load_config()
    formats = formats or cfg.export.formats
    records = _build_records(project)
    project.out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "jsonl" in formats or not formats:
        path = project.out_dir / "goldset.jsonl"
        write_jsonl_atomic(path, [_meta(project, records), *records])
        written.append(path)

    if "csv" in formats:
        path = project.out_dir / "goldset.csv"
        cols = [
            "id", "question", "answer", "label", "note",
            "agent_recommendation", "agent_category", "agent_confidence",
            "agreed_with_agent", "annotated_at",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        written.append(path)

    if "hf" in formats:
        try:
            from datasets import Dataset
        except ImportError as e:
            raise RuntimeError("Need datasets: pip install 'pressf[hf]'") from e
        path = project.out_dir / "goldset_hf"
        Dataset.from_list(records).save_to_disk(str(path))
        written.append(path)

    return written


def _norm_q(q: str) -> str:
    return " ".join(q.strip().lower().split())


def export_pairs(project: Project) -> Path:
    """Preparations DPO-pairs (honestly - see PLAN.md §1.1 case 3): rejected - our f-response;
    chosen is filled with the p-answer to the same question if it is in the dataset, otherwise null —
    is reached by the user (standards, generation)."""
    cfg = project.load_config()
    if cfg.task == "pairwise_compare":
        choices = project.effective_pairwise_annotations()
        examples = {ex.id: ex for ex in project.load_examples()}
        pairs = []
        for eid, ann in choices.items():
            ex = examples.get(eid)
            if ex is None or not ex.answer_b:
                continue
            if ann.winner == "a":
                chosen, rejected = ex.answer, ex.answer_b
            elif ann.winner == "b":
                chosen, rejected = ex.answer_b, ex.answer
            else:
                chosen = rejected = None
            pairs.append(
                {
                    "question": ex.question,
                    "answer_a": ex.answer,
                    "answer_b": ex.answer_b,
                    "winner": ann.winner,
                    "shown_left": ann.shown_left,
                    "chosen": chosen,
                    "rejected": rejected,
                    "example_id": ex.id,
                    "note": ann.note,
                    "annotated_at": ann.ts.isoformat(),
                }
            )
        project.out_dir.mkdir(parents=True, exist_ok=True)
        path = project.out_dir / "pairs.jsonl"
        write_jsonl_atomic(path, pairs)
        return path

    records = _build_records(project)
    good_by_q: dict[str, str] = {}
    for r in records:
        if r["label"] == "p":
            good_by_q.setdefault(_norm_q(r["question"]), r["answer"])
    pairs = [
        {
            "question": r["question"],
            "rejected": r["answer"],
            "chosen": good_by_q.get(_norm_q(r["question"])),
            "example_id": r["id"],
            "agent_category": r["agent_category"],
        }
        for r in records
        if r["label"] == "f"
    ]
    project.out_dir.mkdir(parents=True, exist_ok=True)
    path = project.out_dir / "pairs.jsonl"
    write_jsonl_atomic(path, pairs)
    return path


def disagreement_records(project: Project) -> list[dict[str, Any]]:
    """Human/agent disagreements without writing to disk (for calibration and preview)."""
    return [
        r for r in _build_records(project)
        if r["agreed_with_agent"] is False
    ]


def export_disagreements(project: Project) -> Path:
    """Human/agent disagreements are calibration material."""
    records = disagreement_records(project)
    project.out_dir.mkdir(parents=True, exist_ok=True)
    path = project.out_dir / "disagreements.jsonl"
    write_jsonl_atomic(path, records)
    return path
