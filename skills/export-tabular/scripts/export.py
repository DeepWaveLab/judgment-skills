#!/usr/bin/env python3
"""export-tabular: dump records to xlsx (with CSV fallback) or pretty JSON.

CLI:
    python3 export.py records.json --format xlsx --out out.xlsx
    python3 export.py records.json --format json --out out.json
    python3 export.py records.json --format xlsx --out out.xlsx --columns f1,f2,f3
    python3 export.py                                              # self-test

Library:
    from export import export
    export(records, "/tmp/out.xlsx", fmt="xlsx", columns=["case_id", "被告"])
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any


def _resolve_columns(records: list[dict], columns: list[str] | None) -> list[str]:
    if columns is not None:
        return list(columns)
    seen: list[str] = []
    seen_set: set[str] = set()
    for r in records:
        for k in r.keys():
            if k not in seen_set:
                seen.append(k)
                seen_set.add(k)
    return seen


def _coerce_cell(v: Any, warnings: list[str]) -> Any:
    """Return a value suitable for xlsx / CSV cell."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    # fallback
    warnings.append(f"coerced {type(v).__name__} to str")
    return str(v)


def _write_xlsx(records: list[dict], path: str, columns: list[str]) -> None:
    from openpyxl import Workbook  # lazy import
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "records"
    bold = Font(bold=True)

    # header
    for col_idx, key in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=key)
        cell.font = bold

    warnings: list[str] = []
    for row_idx, r in enumerate(records, start=2):
        for col_idx, key in enumerate(columns, start=1):
            ws.cell(row=row_idx, column=col_idx, value=_coerce_cell(r.get(key), warnings))

    # auto-width
    for col_idx, key in enumerate(columns, start=1):
        max_len = len(str(key))
        for r in records:
            v = r.get(key)
            if v is None:
                continue
            ln = len(str(v))
            if ln > max_len:
                max_len = ln
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 60)

    wb.save(path)
    for w in set(warnings):
        print(f"WARNING: {w}", file=sys.stderr)


def _write_csv(records: list[dict], path: str, columns: list[str]) -> None:
    warnings: list[str] = []
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, dialect="excel")
        writer.writerow(columns)
        for r in records:
            writer.writerow([_coerce_cell(r.get(k), warnings) for k in columns])
    for w in set(warnings):
        print(f"WARNING: {w}", file=sys.stderr)


def _write_json(records: list[dict], path: str, columns: list[str]) -> None:
    # Filter records to columns (preserve null for missing keys)
    filtered = [{k: r.get(k, None) for k in columns} for r in records]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(filtered, fh, ensure_ascii=False, indent=2)


def export(records: list[dict], path: str, fmt: str = "xlsx",
           columns: list[str] | None = None) -> None:
    """Export records to path in the given format.

    fmt: "xlsx" or "json".
    If fmt == "xlsx" and openpyxl is unavailable, writes CSV to <path>.csv and warns.
    """
    if not isinstance(records, list):
        raise TypeError("records must be a list[dict]")
    cols = _resolve_columns(records, columns)

    fmt = fmt.lower()
    if fmt == "json":
        _write_json(records, path, cols)
        return

    if fmt == "xlsx":
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            # fallback to CSV
            base, ext = os.path.splitext(path)
            csv_path = base + ".csv"
            _write_csv(records, csv_path, cols)
            print(f"WARNING: openpyxl not found; wrote CSV to {csv_path}", file=sys.stderr)
            return
        _write_xlsx(records, path, cols)
        return

    raise ValueError(f"unsupported fmt: {fmt!r} (expected 'xlsx' or 'json')")


def _self_test() -> str:
    records = [
        {"case_id": "115交簡478", "被告": "何建睿", "主文刑期月數": 3, "罰金金額": 20000},
        {"case_id": "112毒字第1號", "被告": "王小明", "毒品種類": "海洛因", "毒品重量": 3.2},
    ]
    out = "/tmp/export_test.json"
    export(records, out, fmt="json")
    return out


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        path = _self_test()
        print(path)
        return 0

    parser = argparse.ArgumentParser(description="Export records to xlsx or JSON.")
    parser.add_argument("input", help="path to records JSON (list[dict])")
    parser.add_argument("--format", choices=["xlsx", "json"], default="xlsx")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument("--columns", help="comma-separated column list (also filters)")
    args = parser.parse_args(argv[1:])

    with open(args.input, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    if not isinstance(records, list):
        print("ERROR: input JSON must be a list of dicts", file=sys.stderr)
        return 2

    columns = args.columns.split(",") if args.columns else None
    export(records, args.out, fmt=args.format, columns=columns)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
