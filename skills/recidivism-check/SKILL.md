---
name: recidivism-check
description: Use this skill when Claude needs to determine whether a Taiwan criminal defendant is a 累犯 per 刑法§47 based on prior judgment records and the current offense date. Also exposes a helper to extract candidate prior-case references (e.g. "107年度湖交簡字第433號") from raw judgment text. Trigger whenever the user asks about 累犯, prior convictions within 5 years, recidivism, §47, 前案, 前科, 是否構成累犯. Keywords - 累犯, 刑法47, recidivism, prior record, 前案, 五年內再犯.
version: 0.1.0
license: Proprietary
---

# recidivism-check

## Overview

Apply a simplified version of 刑法第47條 to decide if a defendant is a recidivist (累犯). The rule: if any prior record was finalized within 5 years of the current offense date AND the prior was custodial (imprisonment or 拘役), the case is flagged `is_recidivist = true`. A caveat is always attached reminding reviewers that the real statute also requires the prior sentence to have been fully served - a fact our skill cannot verify from text alone.

Includes a regex-based extractor for prior-case references in Chinese judgment text.

## Inputs / Outputs

**Input** (programmatic):

```json
{
  "prior_records": [
    {"case_no": "107湖交簡字第433號", "sentence_months": 2,
     "finalized_date": "2018-07-10", "crime_type": "公共危險"}
  ],
  "current_case": {"offense_date": "2026-03-17", "crime_type": "公共危險"}
}
```

**Output**:

```json
{
  "is_recidivist": true,
  "matched_priors": [
    {"case_no": "107湖交簡字第433號", "finalized_date": "2018-07-10",
     "days_to_offense": 2807, "within_5y": true, "custodial": true}
  ],
  "rationale": "107湖交簡字第433號 判決確定 2018-07-10, 本案犯罪日 2026-03-17, 5年內。",
  "caveat": "刑法§47 還要求前案刑罰已執行完畢或赦免；本技能無法僅從文字確認，請人工再覆核。"
}
```

## Quick Start

CLI (auto-extract priors from raw judgment text):

```bash
python3 skills/recidivism-check/scripts/check_recidivism.py samples/judgment_sample_001.txt
python3 skills/recidivism-check/scripts/check_recidivism.py samples/judgment_sample_001.txt \
    --current-date 2026-03-17
```

Self-test: run with no args - uses `samples/judgment_sample_001.txt` if present.

Python API:

```python
from scripts.check_recidivism import check_recidivism, extract_priors_from_text
priors = extract_priors_from_text(text)
result = check_recidivism(priors, current_case={"offense_date": "2026-03-17",
                                                "crime_type": "公共危險"})
```

## Rules

Per simplified 刑法§47 (see `references/statute_text.md`):

1. A prior record counts if its `finalized_date` is within a qualifying window before the current `offense_date`:
   - Default window: **5 years** (1826 days) per 刑法§47.
   - **刑法§185-3 III carve-out**: if `current_case.crime_type` contains `公共危險` / `不能安全駕駛` / `酒駕`, the window widens to **10 years** (3653 days) - this mirrors §185-3 III's explicit recidivism enhancement ("曾犯本條...於十年內再犯第1項之罪").
2. A prior is **custodial** if `sentence_months >= 1` OR the crime_type / sentence text contains `拘役`.
3. If any prior satisfies both (1) and (2), `is_recidivist = true`.
4. The output always carries a `caveat` reminding that 刑法§47 also requires the prior sentence to have been fully served or pardoned - a fact we cannot verify from text.

`extract_priors_from_text(text)` regex-scans for:
- `\d{2,3}\s*年度?\s*\w{1,6}字第\s*\d+\s*號` (e.g. `107年度湖交簡字第433號`).
- Nearby dates in the forms `民國?\s*\d{2,3}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日` or `YYYY-MM-DD`.
- Nearby sentence phrases like `有期徒刑\s*\d+\s*(年|月)` or `拘役`.
The helper returns a list of `{"case_no", "finalized_date", "sentence_months", "crime_type"}` dicts (fields may be `None` if not detected).

## Evaluation

Against `samples/judgment_sample_001.txt`:
- `extract_priors_from_text` detects `107年度湖交簡字第433號` with `finalized_date = 2018-07-10` and `sentence_months = 2`.
- `check_recidivism` returns `is_recidivist = true` with that prior in `matched_priors`.
- Captured output in `evals/smoke.txt`.

## References

- `references/statute_text.md` - the text of 刑法§47 + interpretation notes and ROC-date conversion guidance.
