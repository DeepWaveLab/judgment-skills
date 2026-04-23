---
name: pii-deid
description: Use this skill to de-identify Taiwan criminal judgments (判決書) by replacing personally identifiable information with stable placeholder codes. Trigger whenever the user asks to redact, anonymize, mask, 去識別化, 代號化, remove names, strip personal data from a judgment, or prepare judgment text for sharing, publication, or LLM prompting. Handles 被告 / 被害人 / 證人 / 檢察官 / 法官 / 書記官 Chinese names, ROC national ID numbers, Taiwan vehicle plates, phone numbers, and street addresses down to 巷弄門牌號. Returns both redacted text and a mapping from placeholder code back to the original string so the transformation is reversible.
version: 0.1.0
license: Proprietary
---

# pii-deid

## Overview

Taiwan court judgments routinely contain the full names of defendants, victims, witnesses, prosecutors, judges, and clerks, plus ROC national-ID numbers, vehicle plates, phone numbers, and precise street addresses. Before a judgment can be shared with third parties, indexed for search, or passed to an external LLM, this PII must be replaced with stable codes. `pii-deid` performs that substitution using deterministic Taiwan-specific regex rules and returns both the redacted text and a reversible `{code: original}` mapping.

The skill is deterministic, stdlib-only, and ID assignment is stable: running twice on the same input yields identical codes.

## Inputs / Outputs

**Input**: raw judgment text (UTF-8 string).

**Output** (JSON):

```json
{
  "redacted": "被告 D-001 ... 車牌號碼 PL-001 ... 地址 ADDR-001 ...",
  "map": {
    "D-001": "何建睿",
    "O-001": "林彥均",
    "O-002": "曾名阜",
    "O-003": "李璁潁",
    "O-004": "林宜蓁",
    "PL-001": "000-0000",
    "ADDR-001": "臺北市○○區○○○路00巷00號"
  }
}
```

Code families:

| Prefix | Meaning |
|--------|---------|
| `D-NNN` | 被告 / 被告人 (defendant) |
| `V-NNN` | 被害人 (victim) |
| `W-NNN` | 證人 (witness) |
| `O-NNN` | 檢察官 / 法官 / 書記官 (official) |
| `PL-NNN` | 車牌號碼 (plate) |
| `ID-NNN` | ROC 身分證字號 (national ID) |
| `PH-NNN` | 電話 (phone) |
| `ADDR-NNN` | 地址 (address down to 門牌號) |

## Quick Start

From the repo root (`judgment-skills/`):

```bash
python3 skills/pii-deid/scripts/deid.py "$(cat samples/judgment_sample_001.txt)" | head -40
```

Programmatic:

```python
from skills.pii_deid.scripts.deid import deidentify
out = deidentify(open("samples/judgment_sample_001.txt").read())
print(out["redacted"])
print(out["map"])
```

## Rules

1. **Role-tagged name rules run first** so defendants get `D-`, officials get `O-`, etc. Patterns: `被告\s*<Name>`, `被害人\s*<Name>`, `證人\s*<Name>`, `檢察官\s*<Name>`, `法官\s*<Name>`, `書記官\s*<Name>`, `聲請人\s*<Name>`.
2. A Chinese name is 2-4 Han characters (`[\u4e00-\u9fff]{2,4}`) not followed by common noun continuations (地方, 法院, 檢察署, 分局, 警察, 派出, 派遣, 刑事, 民事, 交通, 市政, 縣政, 簡易, 公司, 銀行, 商店, 事件, 案件, 部分, 法庭, 庭, 法條).
3. **Structured PII rules**: ROC ID `[A-Z][12]\d{8}`, plate `\d{3,4}-[A-Z0-9]{3,4}` (also the masked form `\d{3}-\d{4}` and bracketed 車牌號碼 values), phone `09\d{2}-?\d{3}-?\d{3}` and `0\d{1,2}-?\d{6,8}`.
4. **Address rule** matches a Taiwan address starting from 縣/市, through 區/鄉/鎮, 路/街/大道, 段, 巷, 弄, 號 (masked `○` characters are allowed inside the run). The entire string is replaced with `ADDR-NNN`.
5. **Stable IDs**: codes are assigned in first-appearance order per prefix; the same original string always maps to the same code within a single invocation.
6. The redactor never replaces a name more than once in the map — if "何建睿" appears 12 times, all 12 become `D-001`.
7. Officials already covered by role-tag rules (`檢察官 林彥均`) are not also matched by structured rules. Structured rules run only on residual text.

## Evaluation

Against `samples/judgment_sample_001.txt` the skill should:

- Replace `何建睿` (defendant) with `D-001`.
- Replace `林彥均` (prosecutor) with an `O-NNN` code.
- Replace `曾名阜` (judge) with an `O-NNN` code.
- Replace `李璁潁` / `林宜蓁` (clerks) with `O-NNN` codes.
- Replace the `000-0000` plate placeholder with `PL-001`.
- Replace the `臺北市○○區○○○路00巷00號` address with `ADDR-001`.
- Produce a `map` whose keys are all unique and whose values round-trip the original.

Smoke output is captured in `evals/smoke.txt`.

## References

- `references/pii_patterns.md` - every regex with annotated examples drawn from real Taiwan judgments.
</content>
</invoke>