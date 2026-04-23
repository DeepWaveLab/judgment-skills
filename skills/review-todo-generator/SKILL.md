---
name: review-todo-generator
description: Use this skill when Claude needs to turn a contradiction-check diff (and optional confidence scores) into a prioritised, case-tagged human-review TODO list for Taiwan judgment QA workflows. Trigger whenever the user asks for review assignments, 每日覆核, QA triage, spot-checks, sampling, or wants to route critical-field mismatches (量刑, 累犯, 沒收, 緩刑, 易科罰金) to a human reviewer. Keywords - todo, review, triage, priority P0 P1 P2, 人工覆核, 待辦, sampling spot check, 抽樣.
version: 1.0.0
license: Proprietary
---

# review-todo-generator

## Overview

Consume a `contradiction-check` diff and produce a prioritized, case-tagged TODO list for human reviewers. The TODO list embeds the priority tier, the disputed field, a short rationale, and the originating case id so that reviewers can load the exact paragraph via `cite-tracer` downstream.

Deterministic (Python 3.11 stdlib only). If `sample_rate > 0`, a seeded RNG also flags a fraction of `agree` fields for random spot-check.

## Inputs / Outputs

**Input**:

```python
diff = {
  "diffs": [{"field": "主文刑期月數", "rule_value": 3, "llm_value": 4,
             "similarity": 0.0, "flag": "mismatch"}, ...],
  "summary": {...}
}
case_id = "115交簡478"
sample_rate = 0.1   # optional, default 0.0
confidence = {"主文刑期月數": 0.92, ...}  # optional field -> [0..1]
```

**Output** (JSON):

```json
{
  "todos": [
    {"id": "todo-001", "priority": "P0", "field": "主文刑期月數",
     "reason": "rule=3 llm=4, critical sentencing field",
     "case_id": "115交簡478"}
  ],
  "summary": {"total": 3, "P0": 1, "P1": 1, "P2": 1, "sampled": 0}
}
```

## Quick Start

CLI:

```bash
python3 skills/review-todo-generator/scripts/generate.py diff.json --case-id 115交簡478
python3 skills/review-todo-generator/scripts/generate.py diff.json --case-id CASE --sample-rate 0.2
python3 skills/review-todo-generator/scripts/generate.py   # self-test
```

Python API:

```python
from scripts.generate import generate_todos
todos = generate_todos(diff_dict, case_id="115交簡478", sample_rate=0.1)
```

## Rules

Priority assignment (see `references/priority_rules.md`):

- **P0** - `mismatch` or `only_rule`/`only_llm` on critical sentencing fields: `主文刑期月數`, `罰金金額`, `累犯`, `沒收`, `緩刑`, `易科罰金折算`.
- **P1** - `low_similarity` on key identity / quantity fields: `被告姓名`, `案號`, `毒品種類`, `毒品數量`, `交易金額`, `犯罪日期`.
- **P2** - everything else (non-critical `mismatch`, `low_similarity`, or `agree` that was sampled).

Sampling:
- If `sample_rate > 0`, each `agree` diff is included with probability `sample_rate` under a deterministic seed derived from `case_id` (reproducible across reruns).
- Sampled rows get priority `P2` and reason `spot-check sampling`.

TODO IDs are `todo-NNN` in emission order, zero-padded to 3 digits.

## Evaluation

- Running `python3 skills/review-todo-generator/scripts/generate.py` with no args exercises a built-in diff and prints a todo list that includes at least one `P0` (量刑 mismatch) and one `P1` (identity low_similarity).
- `evals/smoke.txt` contains the captured output.

## References

- `references/priority_rules.md` - full tier table + the canonical critical-field list.
