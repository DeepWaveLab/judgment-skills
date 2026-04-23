# Export Formats - export-tabular

This document pins down how records map to xlsx / CSV / JSON columns, plus encoding notes for Excel on Windows.

## Input contract

`records: list[dict]` where each dict is a flat mapping of string keys to JSON-serialisable values (`str`, `int`, `float`, `bool`, `None`, or `list`/`dict` - see coercion rules below).

## Column resolution

1. If caller passes `columns=["a", "b", "c"]`:
   - Output columns are exactly `a`, `b`, `c` in that order.
   - Keys present in the records but **not** in `columns` are dropped (filter behaviour).
   - Keys in `columns` but not in any record still appear as a column with blank cells.
2. If `columns` is `None`:
   - Columns = union of all keys in first-seen order across `records`.
   - This preserves the order in which extractors typically emit fields.

## Cell rendering

| Value type | xlsx / CSV cell | JSON cell |
|------------|-----------------|-----------|
| `str` | UTF-8 string | string |
| `int` / `float` | numeric | numeric |
| `bool` | `TRUE` / `FALSE` | `true` / `false` |
| `None` / missing key | empty string `""` | `null` |
| `list` / `dict` | `json.dumps(ensure_ascii=False)` | nested as-is |
| anything else | `str(value)` + stderr warning | `str(value)` + warning |

## xlsx details (openpyxl present)

- Sheet name: `records`.
- Header row: bold (using openpyxl's default style).
- Columns are auto-sized to `min(max_cell_len + 2, 60)` for readability.
- File is written via `Workbook.save(path)`; openpyxl handles UTF-8 natively.

## CSV fallback (openpyxl missing)

- Output suffix is forcibly rewritten to `.csv`.
- Encoding: `utf-8-sig` (UTF-8 with BOM) so Excel-on-Windows opens Chinese correctly.
- Dialect: `csv.excel` (comma-separated, `\r\n` newlines, quote on need).
- A warning is printed to stderr: `WARNING: openpyxl not found; wrote CSV to <path>`.

## JSON details

- `json.dump(records, fh, ensure_ascii=False, indent=2)`.
- Nested `list` / `dict` are preserved (not stringified).
- File encoding: UTF-8 (no BOM).

## Round-trip guarantees

- JSON output: perfect round-trip - reading the output with `json.load` yields a list equal to the filtered input (same values, with only the `columns`-filtered subset and `None` preserved).
- xlsx output: lossy only for `list` / `dict` cells (they become strings) and `bool` (rendered as `TRUE/FALSE`). String/number round-trip is exact.

## Size expectations

openpyxl handles up to ~1M rows reasonably; for judgment pipelines we expect < 50k rows per export. No streaming writer is used.

## Related skills

- `contradiction-check` and `review-todo-generator` emit diff / todo JSON; both are valid `records` inputs (with a pre-flatten step on the caller's side if desired).
