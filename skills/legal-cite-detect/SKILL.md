---
name: legal-cite-detect
description: Use this skill when Claude needs to detect every citation to a Taiwan statute inside a judgment (or any Chinese legal document). Outputs a list of structured citations with statute short name, article number, paragraph, item, the raw span, and its character offset. Handles both Arabic numerals ("第185條之3") and common Chinese numerals ("第壹佰捌拾伍條之參"). Covered statutes include 中華民國刑法, 刑事訴訟法, 刑法施行法, 毒品危害防制條例, plus aliases (刑法, 刑訴, 毒危條例). Trigger whenever the user asks to list cited laws, count citations, map 法條, or build a citation index. Keywords - 法條, 引用, citation, 刑法, 刑訴, 毒危條例, 毒品危害防制條例.
version: 0.1.0
license: Proprietary
---

# legal-cite-detect

## Overview

Scan Chinese legal text and return every statutory citation with a machine-readable structure. The detector normalizes aliases (刑法 -> 中華民國刑法, 刑訴 -> 刑事訴訟法, 毒危條例 -> 毒品危害防制條例), converts Chinese numerals to Arabic for the `article`/`paragraph`/`item` fields, and reports the raw span plus its character offset so downstream skills (cite-tracer) can link paragraphs to citations.

## Inputs / Outputs

**Input** - raw text.

**Output** - list of citation dicts:

```json
[
  {
    "statute": "中華民國刑法",
    "article": "185-3",
    "paragraph": "1",
    "item": "1",
    "raw": "刑法第185條之3第1項第1款",
    "offset": 123
  }
]
```

- `statute` is the canonical full name (see `references/statute_aliases.md`).
- `article` is the Arabic article number; subsection modifier is rendered with `-` (e.g. 185-3, 1-1).
- `paragraph` / `item` are Arabic strings or null.
- `raw` is the exact matched span; `offset` is its starting character index in the input.
- Duplicate raw/offset pairs are suppressed.

## Quick Start

From the repo root (`judgment-skills/`):

```bash
python3 skills/legal-cite-detect/scripts/detect.py samples/judgment_sample_001.txt | head -40
```

Programmatic:

```python
from detect import detect
citations = detect(open("samples/judgment_sample_001.txt").read())
```

## Rules

- Statute short names and full names are both matched, then mapped via the alias table.
- Article numbers: Arabic digits OR Chinese numerals on `[一二三四五六七八九十百千零〇壹貳參肆伍陸柒捌玖拾佰仟]`.
- Sub-article (`之N`) supported; rendered as `<article>-<N>`.
- Paragraph (`第N項`) and item (`第N款`) optional.
- Ranges ("第449條第1項前段、第3項") are split into separate citations for each 項 mentioned.

## Evaluation

Against `samples/judgment_sample_001.txt` the detector should pick up at least:

- 刑法 第185條之3 第1項 第1款 (multiple times in 主文, 理由, 附錄)
- 刑事訴訟法 第449條 第1項 + 第3項
- 刑事訴訟法 第454條 第2項
- 刑事訴訟法 第451條 第1項
- 刑法 第41條 第1項 前段
- 刑法 第42條 第3項 前段
- 刑法施行法 第1條之1 第1項
- 陸海空軍刑法 第54條 (mentioned in the appended statute text)

## References

- `references/statute_aliases.md` - statute short-name to canonical name map.
