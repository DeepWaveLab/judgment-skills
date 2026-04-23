---
name: contradiction-check
description: Use this skill when Claude needs to compare two structured field dictionaries (typically a rule-engine extraction versus an LLM extraction, or LLM-vs-LLM re-extraction) for a Taiwan judgment and emit a per-field diff with similarity scores and mismatch flags. Trigger whenever the user asks to cross-check, reconcile, compare two JSON extraction outputs, find contradictions, audit the extractor, or produce a QA diff for 判決書 pipelines. Keywords - contradiction, mismatch, diff, rule vs LLM, QA compare, similarity, Jaccard, 矛盾檢核, 交叉比對.
version: 1.4.0
license: Proprietary
---

# contradiction-check

## Overview

Compare two flat field dictionaries field-by-field and produce a structured diff suitable for downstream human-review routing. Typical use is the QA gate between a deterministic rule-engine extractor and a probabilistic LLM extractor: any disagreement either flags a rule-engine bug or an LLM hallucination and must be triaged.

This skill is deterministic, offline, and has no external dependencies (Python 3.11 stdlib only).

## Inputs / Outputs

**Input** - two `dict` objects with the same key space (union is compared; missing keys on either side are flagged).

```python
rule = {"主文刑期月數": 3, "被告姓名": "何建睿", "犯罪日期": "2026-03-17"}
llm  = {"主文刑期月數": 4, "被告姓名": "何建叡", "犯罪日期": "2026-03-17"}
```

**Output** (JSON):

```json
{
  "diffs": [
    {"field": "主文刑期月數", "rule_value": 3, "llm_value": 4, "similarity": 0.0, "flag": "mismatch"},
    {"field": "被告姓名", "rule_value": "何建睿", "llm_value": "何建叡", "similarity": 0.66, "flag": "low_similarity"},
    {"field": "犯罪日期", "rule_value": "2026-03-17", "llm_value": "2026-03-17", "similarity": 1.0, "flag": "agree"}
  ],
  "summary": {"total": 3, "mismatches": 1, "jaccard_avg": 0.55}
}
```

Flag values:
- `agree` - equal after normalization, similarity == 1.0.
- `low_similarity` - both sides present strings, Jaccard similarity < 0.8.
- `mismatch` - scalars differ OR string similarity 0.
- `only_rule` - key only present (non-null) in rule dict.
- `only_llm` - key only present (non-null) in llm dict.

## Quick Start

CLI (two JSON file paths):

```bash
python3 skills/contradiction-check/scripts/check.py rule.json llm.json
```

Self-test (built-in example):

```bash
python3 skills/contradiction-check/scripts/check.py
```

Python API:

```python
from scripts.check import compare
diff = compare(rule_dict, llm_dict)
```

## Rules

1. Iterate the union of keys from both dicts.
2. If both values are `None` / missing - skip (do not emit a diff row).
3. If only one side has a non-null value - emit `only_rule` / `only_llm` with similarity 0.0.
4. If both are strings - compute token-set Jaccard on whitespace+punctuation-stripped tokens. Flag `agree` if 1.0, `low_similarity` if < 0.8, else `mismatch`.
5. If both are scalars (number / bool / date-ish) - exact equality after string-casting. Similarity is 1.0 or 0.0.
6. If both are lists - treat as sets, compute Jaccard; thresholds same as strings.
7. `summary.jaccard_avg` is the mean similarity across all emitted diffs (rounded to 2 decimals).

See `references/similarity_rules.md` for the exact formulas.

## Evaluation

- Running `python3 skills/contradiction-check/scripts/check.py` with no args should print a diff JSON for the built-in example that contains at least one `mismatch` and one `agree` row.
- `evals/smoke.txt` contains the captured output.

## References

- `references/similarity_rules.md` - per-type similarity formulas and edge cases.
