---
name: export-tabular
description: Use this skill when Claude needs to export a list of field-record dicts (one per Taiwan judgment) to xlsx or pretty JSON, with optional column ordering/filtering. Trigger whenever the user asks to dump results, write a spreadsheet, produce xlsx/csv/json, deliverable output, 匯出, 表格, or end-of-pipeline download. Falls back to CSV if openpyxl is missing. Keywords - export, xlsx, excel, csv, json dump, tabular, 匯出, 表格, 下載, deliver results.
version: 0.1.0
license: Proprietary
---

# export-tabular

## Overview

Write a list of flat record dicts (one dict per judgment or per field-set) to xlsx or JSON. This is the final stage of the judgment-mining pipeline: the UI, downstream analytics, or the customer deliverable reads from this file.

Designed to never hard-fail on a missing optional dependency:
- If `openpyxl` is available (it is, per the repo baseline), xlsx is produced.
- If not, the script writes CSV with a `.csv` suffix and prints a warning to stderr; the caller can still ship the file.

## Inputs / Outputs

**Input** - a `list[dict]`; dicts may have heterogeneous keys. Missing values become empty cells.

```python
records = [
  {"case_id": "115交簡478", "被告": "何建睿", "主文刑期月數": 3, "罰金金額": 20000},
  {"case_id": "112毒字第1號", "被告": "王小明", "毒品種類": "海洛因", "毒品重量": 3.2}
]
```

**Output** - a single file at `--out`:
- `xlsx` -> binary Excel workbook (UTF-8 cell values, sheet `records`).
- `json` -> UTF-8 JSON array with `ensure_ascii=False`, 2-space indent.

## Quick Start

CLI:

```bash
python3 skills/export-tabular/scripts/export.py records.json --format xlsx --out out.xlsx
python3 skills/export-tabular/scripts/export.py records.json --format json --out out.json
python3 skills/export-tabular/scripts/export.py records.json --format xlsx --out out.xlsx \
    --columns case_id,被告,主文刑期月數
python3 skills/export-tabular/scripts/export.py     # self-test: writes /tmp/export_test.json
```

Python API:

```python
from scripts.export import export
export(records, "/tmp/out.xlsx", fmt="xlsx", columns=["case_id", "被告"])
```

## Rules

1. Column order:
   - If `columns` is provided, use it exactly (as both the filter and the order). Keys not in any record are still emitted as empty columns.
   - Otherwise, union all keys in first-seen order across records.
2. Missing keys in a record render as `""` in xlsx/CSV and as `null` in JSON (explicitly).
3. Non-JSON-serialisable values are coerced via `str()` with a warning to stderr.
4. xlsx encoding is UTF-8; openpyxl handles BOM / Excel encoding transparently.
5. If `openpyxl` is not importable and `fmt == "xlsx"`:
   - Swap the output path suffix to `.csv`.
   - Print `WARNING: openpyxl not found; wrote CSV to <path>` to stderr.
   - Write RFC 4180 CSV with UTF-8 BOM so Excel-on-Windows renders Chinese correctly.

## Evaluation

- Running `python3 skills/export-tabular/scripts/export.py` with no args exports 2 dummy records to `/tmp/export_test.json` and prints the path on stdout.
- `evals/smoke.txt` contains the captured stdout.
- Round-trip: re-reading the JSON output must yield a list equal to the original records.

## References

- `references/export_formats.md` - full schema, column rules, Excel encoding notes, round-trip guarantees.
