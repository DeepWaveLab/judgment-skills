---
name: sentence-normalize
description: Use this skill to normalize Chinese-formatted Taiwan judgment numeric expressions into machine-comparable values. Trigger whenever the user wants to convert sentence lengths (有期徒刑, 拘役, 無期徒刑) into months or days, convert monetary amounts in 新臺幣 into an integer number of TWD, or convert Republic-of-China dates (中華民國 115 年 4 月 21 日) into ISO 8601 Gregorian dates. Handles traditional 大寫 numerals (零壹貳參肆伍陸柒捌玖拾佰仟萬億), traditional-simplified 一二三四五六七八九十百千萬, and Arabic digits interchangeably. Keywords - 量刑正規化, 刑期月數, 大寫數字, 罰金, ROC 日期, normalize sentence, chinese numeral.
version: 0.1.0
license: Proprietary
---

# sentence-normalize

## Overview

Taiwan judgments mix three numeric conventions: Arabic digits (`7 年 6 月`),
traditional Chinese numerals (`七年六月`), and 大寫 accounting numerals
(`柒年陸月`, `貳萬元`). Monetary amounts additionally use the shorthand
multipliers `萬` (10,000) and `億` (100,000,000). Dates are written in ROC
calendar years (民國 115 年 = 2026 A.D.).

This skill converts all three into canonical machine values so downstream
extractors can compare, sort, and aggregate.

## Inputs / Outputs

Three pure functions plus a CLI.

```python
from skills.sentence_normalize.scripts.normalize import (
    normalize_sentence, normalize_money, normalize_roc_date,
)

normalize_sentence("有期徒刑參月")          # -> {"months": 3}
normalize_sentence("柒年陸月")              # -> {"months": 90}
normalize_sentence("有期徒刑 7 年 6 個月")  # -> {"months": 90}
normalize_sentence("拘役伍拾日")            # -> {"days": 50}
normalize_sentence("無期徒刑")              # -> {"life": True}

normalize_money("新臺幣貳萬元")             # -> 20000
normalize_money("罰金 3 百萬元")            # -> 3000000

normalize_roc_date("中華民國 115 年 4 月 21 日")  # -> "2026-04-21"
```

CLI: read any file (text) and emit a JSON list of matched expressions with
their normalized forms.

```bash
python3 skills/sentence-normalize/scripts/normalize.py samples/judgment_sample_001.txt
```

Output:

```json
[
  {"kind": "sentence", "span": [r, c], "raw": "有期徒刑參月", "value": {"months": 3}},
  {"kind": "money",    "span": [r, c], "raw": "新臺幣貳萬元",  "value": 20000},
  {"kind": "date",     "span": [r, c], "raw": "中華民國 115 年 4 月 21 日", "value": "2026-04-21"}
]
```

## Rules

### Chinese numerals

`大寫` and `小寫` traditional numerals are interchangeable. See
`references/numeral_tables.md`. The parser recognises the unit chain
`十 / 百 / 千 / 萬 / 億` and composes values correctly for inputs like
`貳萬伍仟`, `三百`, `一千二百萬`.

### Sentence

- Keywords: `有期徒刑`, `拘役`, `無期徒刑`, `死刑`.
- Units: `年`, `月`, `個月`, `日`, `天`.
- Composition: `<Y>年<M>月` or `<Y>年` or `<M>月` or `<D>日`.
- `無期徒刑` → `{"life": True}`; `死刑` → `{"death": True}`.
- Result shape: `{"months": int}` for 有期徒刑; `{"days": int}` for 拘役.

### Money

- Optional prefix `新臺幣` / `新台幣` / `NT\$?`.
- Integer in Chinese or Arabic numerals.
- Optional shorthand tail `萬` (×10,000), `億` (×100,000,000), `百萬`
  (×1,000,000), `千萬` (×10,000,000).
- Required suffix `元`.

### ROC date

`(中華民國)?\s*<Y>\s*年\s*<M>\s*月\s*<D>\s*日` where Y/M/D may be Arabic or
Chinese numerals. Gregorian year = `Y + 1911`. Output is ISO 8601
(`YYYY-MM-DD`).

## Evaluation

Against `samples/judgment_sample_001.txt` the skill should extract (at
least): `有期徒刑參月` → 3, `新臺幣貳萬元` → 20000, `中華民國 115 年 4 月
21 日` → `2026-04-21`, `中華民國 115 年 3 月 29 日` → `2026-03-29`,
`有期徒刑2月` → 2, and `壹仟元` → 1000.

Smoke output is captured in `evals/smoke.txt`.

## References

- `references/numeral_tables.md` - full lookup tables and composition rules.
</content>
</invoke>