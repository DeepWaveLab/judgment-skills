# Priority Rules - review-todo-generator

This document defines the exact priority tier each diff row maps to. Tiering is driven by two inputs: the diff `flag` and the `field` name.

## Tier definitions

| Tier | Meaning | Target SLA |
|------|---------|------------|
| P0 | Blocker. A human MUST reconcile before the judgment can be published. | Same-day |
| P1 | High-confidence investigation. Likely extractor error on an identity / quantity field. | Next business day |
| P2 | Nice-to-have review. Includes sampled `agree` rows for quality assurance. | Weekly batch |

## Critical sentencing fields (P0 triggers)

A `mismatch`, `only_rule`, or `only_llm` flag on any of these fields is P0:

- `主文刑期月數` - imprisonment months
- `罰金金額` - fine amount
- `累犯` - recidivism boolean
- `沒收` / `沒收物` / `沒收金額` - confiscation
- `緩刑` / `緩刑期間` - probation
- `易科罰金折算` - commutation rate

Rationale: any error here directly changes the defendant's punishment and is not caught by downstream sanity checks.

## Key identity & quantity fields (P1 triggers)

A `low_similarity` flag on any of these fields is P1:

- `被告姓名` - defendant name
- `案號` - case number
- `毒品種類` - drug type
- `毒品數量` / `毒品重量` - drug quantity
- `交易金額` - transaction amount
- `犯罪日期` - offense date
- `前案號` - prior case number (used by recidivism-check)

Rationale: identity/quantity drift often points to OCR or extractor issues worth human confirmation, but does not by itself change sentencing.

## P2

Everything else. This includes:

- `mismatch` on non-critical fields.
- `low_similarity` on non-key fields.
- Randomly sampled `agree` rows when `sample_rate > 0`.

## Sampling semantics

When `sample_rate > 0`:

1. Deterministic seed: `seed = hash(case_id)` (Python `hash()` is per-process; we use a stable SHA-1 over `case_id` bytes to ensure reproducibility across runs).
2. For each `agree` diff, emit a P2 todo with probability `sample_rate`.
3. Emitted sampled rows carry `reason = "spot-check sampling"`.

## Reason string format

- P0 mismatch: `"rule=<rv> llm=<lv>, critical sentencing field"`.
- P0 only_rule: `"rule=<rv> llm=MISSING, critical sentencing field"`.
- P0 only_llm: `"rule=MISSING llm=<lv>, critical sentencing field"`.
- P1 low_similarity: `"rule='<rv>' llm='<lv>' similarity=<s>, key identity/quantity field"`.
- P2 other: short description mirroring flag + similarity.
- P2 sampled: `"spot-check sampling"`.

Reason strings are truncated to 200 chars to keep downstream UIs tidy.
