---
name: drug-sales-extract
description: Use this skill when Claude needs to extract the ~28 structured fields that describe a Taiwan drug-sales (販賣毒品) criminal judgment - defendant name, drug class and type, transaction counts and amounts, buyer, seized weight, indicted statutes, sentence months, fines, recidivism flag, confession, probation, forfeiture, and so on. Trigger whenever the user uploads a drug-case judgment (毒品危害防制條例) and asks to extract fields, populate a spreadsheet row, or feed a DB. The extractor is null-safe - on a non-drug case (e.g. drunk driving) it returns every field with sensible null defaults plus `is_drug_sales_case: false`. Keywords - 毒品販賣, 欄位抽取, 販賣, 級別, 交易金額, drug sales extraction, 28 fields.
version: 0.1.0
license: Proprietary
---

# drug-sales-extract

## Overview

Extract ~28 structured fields from a Taiwan drug-sales (販賣毒品) judgment. Two execution modes:

1. **LLM-first (production)** - Claude reads the segmented judgment and fills the schema under the rules in `references/field_dictionary.md`.
2. **Rule-based (offline fallback / smoke test)** - the bundled `scripts/extract.py` runs deterministic regex/keyword rules so the skill is testable without an LLM.

The skill is designed to be cheap to call on any judgment: non-drug cases return a well-typed record with null-safe defaults and `is_drug_sales_case: false` so the caller can skip or route it.

## Inputs / Outputs

**Input** - one of:

- The raw judgment text.
- The segmented JSON produced by `doc-segmenter`.
- A path to a `.txt` or `.pdf`.

**Output** - a single JSON record. Every field is present even if null. See `references/field_dictionary.md` for the authoritative list with types and extraction rules.

Top-level shape (abridged):

```json
{
  "is_drug_sales_case": false,
  "case_no": "115年度交簡字第478號",
  "court": "臺灣臺北地方法院",
  "defendant": "何建睿",
  "drug_schedule": null,
  "drug_type": null,
  "transaction_count": null,
  "transaction_amount_twd": null,
  "buyer": null,
  "seized_weight_g": null,
  "indicted_statutes": ["刑法第185-3條第1項第1款"],
  "sentence_months": 3,
  "fine_twd": 20000,
  "recidivism": false,
  "confessed": true,
  "probation": false,
  "forfeiture": null,
  "..." : "..."
}
```

## Quick Start

From the repo root (`judgment-skills/`):

```bash
python3 skills/drug-sales-extract/scripts/extract.py samples/judgment_sample_001.txt | head -40
```

Programmatic:

```python
from extract import extract
record = extract(open("samples/judgment_sample_001.txt").read())
```

## Fields / Rules

Full schema lives in `references/field_dictionary.md`. Highlights:

| Field | Type | Rule |
|-------|------|------|
| `is_drug_sales_case` | bool | True when 毒品危害防制條例 is cited **and** 販賣/轉讓/販售 appears. |
| `drug_schedule` | "一"-"四" \| null | Detected from 第一級/第二級/第三級/第四級毒品. |
| `drug_type` | str \| null | 海洛因 / 甲基安非他命 / MDMA / 大麻 / 愷他命 ... |
| `transaction_count` | int \| null | Count of 交易次數. |
| `transaction_amount_twd` | int \| null | Parsed from 新臺幣... 元, incl. Chinese numerals. |
| `sentence_months` | int \| null | 有期徒刑X月 / X年X月 - returns total months. |
| `fine_twd` | int \| null | Parsed 併科罰金 amount. |
| `recidivism` | bool | True on 累犯 keyword. |
| `confessed` | bool | True on 坦承/自白/認罪 keywords. |
| `probation` | bool | True on 緩刑 keyword (and no 撤銷緩刑). |

The rule-based extractor uses a compact Chinese numeral parser (`_chinese_to_int`) covering 一二三四五六七八九十百千 plus 零/〇/貳/參/肆/伍/陸/柒/捌/玖/拾/佰/仟, sufficient for sentence and fine amounts.

## Evaluation

Smoke test against the bundled drunk-driving sample (`samples/judgment_sample_001.txt`) must:

- Return `is_drug_sales_case: false`.
- Still populate `case_no`, `court`, `defendant`, `sentence_months` (=3), `fine_twd` (=20000), `confessed` (=true), `recidivism` (=false).
- Return `null` (not crash) for every drug-specific field.

For a real drug-sales judgment the LLM pipeline is the primary path; the rule-based extractor is a regression check.

## References

- `references/field_dictionary.md` - full 28-field schema with type, example, and source rule.
