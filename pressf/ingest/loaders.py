"""Loading raw materials: CSV / TSV / JSONL / Excel → list of dict strings."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_rows(path: Path | str) -> list[dict[str, Any]]:
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"File not found:{path}")
    suffix = path.suffix.lower()
    if suffix in (".jsonl", ".ndjson"):
        return _load_jsonl(path)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        raise ValueError(f"{path}: expected JSON-array of objects")
    if suffix in (".csv", ".tsv"):
        return _load_csv(path, delimiter="\t" if suffix == ".tsv" else ",")
    if suffix in (".xlsx", ".xls"):
        return _load_excel(path)
    raise ValueError(f"Unknown format:{suffix}. Supported: jsonl, json, csv, tsv, xlsx")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                rows.append({"_parse_error": f"line{i}: {e}"})
    return rows


def _load_csv(path: Path, delimiter: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _load_excel(path: Path) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except ImportError as e:
        raise RuntimeError(
            "For Excel you need openpyxl: pip install 'pressf[xlsx]'"
        ) from e
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(next(rows_iter, []) or [])]
    return [dict(zip(header, row)) for row in rows_iter]
