---
name: cite-tracer
description: Use this skill to attach paragraph-level citations to extracted judgment fields so every value can be traced back to the exact paragraph it came from. Trigger whenever the user wants source attribution for structured extractions, an audit trail, evidence for a QA reviewer, or wants to verify that a downstream extractor's output is grounded in the input document. Input is a set of extracted fields plus the segmented judgment JSON from doc-segmenter; output is a field_trace list with source_paragraph_ids and a match_score per field. Keywords - 段落引用追溯, source attribution, citation, provenance, audit, evidence trace.
version: 0.1.0
license: Proprietary
---

# cite-tracer

## Overview

Downstream extractors (drug-sales-extract, legal-cite-detect, pii-deid, etc.)
produce structured fields that a human reviewer must be able to verify. This
skill closes the loop: for each extracted `field → value` it finds the
paragraph(s) in the segmented judgment that most likely support it, attaches
their paragraph IDs, and emits a confidence score.

The matcher runs in two tiers:

1. **Substring** — normalize both sides and check for direct containment.
2. **Fuzzy** — `difflib.SequenceMatcher` ratio, cutoff 0.6.

Numeric fields (sentence months, amounts in TWD) are stringified into the
multiple Chinese surface forms a judgment might use before matching, so a
field value of `3` will match `參月`, `3 月`, `三月`, etc.

## Inputs / Outputs

```json
// Input
{
  "fields": {
    "被告": "何建睿",
    "主文刑期月數": 3,
    "罰金金額": 20000,
    "判決日期": "2026-04-21"
  },
  "segmented": {
    "sections": [
      {"id": "sec-01", "label": "主文",
       "paragraphs": [{"id": "p-001", "text": "何建睿 ... 處有期徒刑參月 ..."}]}
    ]
  }
}

// Output
{
  "field_trace": [
    {"field": "被告", "value": "何建睿",
     "source_paragraph_ids": ["p-001"], "match_score": 1.0},
    {"field": "主文刑期月數", "value": 3,
     "source_paragraph_ids": ["p-001"], "match_score": 1.0}
  ]
}
```

Up to 3 paragraph IDs are returned per field (ranked by score).

## Quick Start

Self-test (no args) — uses `samples/judgment_sample_001.txt` split into fake
paragraphs:

```bash
python3 skills/cite-tracer/scripts/trace.py
```

With an input JSON file:

```bash
python3 skills/cite-tracer/scripts/trace.py input.json > output.json
```

Programmatic:

```python
from skills.cite_tracer.scripts.trace import trace
result = trace(fields, segmented)
```

## Rules

1. Flatten `segmented.sections[].paragraphs[]` into a list of
   `(paragraph_id, text)` pairs, preserving document order.
2. For each `(field, value)`:
   1. Stringify `value` into one or more candidate surface forms (see
      `references/matching_strategy.md`).
   2. If any surface form is a substring of any paragraph, that paragraph
      scores 1.0 and is ranked first.
   3. Otherwise compute `SequenceMatcher(None, surface, paragraph).ratio()`
      per paragraph and keep those ≥ 0.6.
3. Return the top 3 paragraphs by score. If none match, return an empty list
   with score 0.0 (the field still appears in `field_trace`).

## Evaluation

Against `samples/judgment_sample_001.txt` (split into paragraphs for the
self-test) the skill should:

- Trace `被告 = 何建睿` to the 主文 paragraph (score 1.0).
- Trace `主文刑期月數 = 3` to the 主文 paragraph that contains `參月` (score
  1.0 via the `參月` surface form).
- Trace `罰金金額 = 20000` to the 主文 paragraph that contains `貳萬元`
  (score 1.0).
- Trace `判決日期 = 2026-04-21` to the signature paragraph that contains
  `中華民國 115 年 4 月 21 日` (score 1.0).

Smoke output is captured in `evals/smoke.txt`.

## References

- `references/matching_strategy.md` - full surface-form table for numeric
  fields and the substring-before-fuzzy decision tree.
</content>
</invoke>