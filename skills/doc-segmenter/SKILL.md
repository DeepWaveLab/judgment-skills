---
name: doc-segmenter
description: Use this skill when Claude needs to split a Taiwan criminal judgment (判決書) into its canonical sections (主文, 事實, 犯罪事實, 證據, 理由, 論罪科刑, 據上論斷, 附錄法條) and assign stable paragraph IDs. Trigger whenever the user uploads a judgment PDF or text and asks to segment, structure, chunk, or tag paragraphs, or whenever a downstream extractor needs paragraph-addressable input. Keywords - 段落切分, 分段, segment judgment, paragraph id, section detection, 主文, 犯罪事實, 理由, 據上論斷.
version: 1.6.2
license: Proprietary
---

# doc-segmenter

## Overview

Split a Taiwan criminal judgment into canonical sections and emit paragraph-level JSON with globally unique, zero-padded, deterministic IDs. The segmenter is the first stage of the judgment-mining pipeline; every downstream extractor (drug-sales-extract, legal-cite-detect, cite-tracer) consumes its output to address evidence by paragraph ID.

Segmentation is rule-based (regex over well-known headings) so it runs offline and produces identical output across reruns.

## Inputs / Outputs

**Input** - raw judgment text (preferred) or a PDF path. When given a PDF the skill invokes the shared helper `scripts/pdf_to_text.py` from the repo root.

**Output** (JSON, UTF-8):

```json
{
  "sections": [
    {
      "id": "sec-01",
      "label": "主文",
      "paragraphs": [
        {"id": "p-001", "text": "..."}
      ]
    }
  ]
}
```

- `sections[].id` is `sec-NN` zero-padded to 2 digits, in document order.
- `sections[].label` is the canonical label from `references/section_taxonomy.md`.
- `paragraphs[].id` is `p-NNN` zero-padded to 3 digits, globally unique across the whole document and stable across reruns for the same input.

## Quick Start

From the repo root (`judgment-skills/`):

```bash
python3 skills/doc-segmenter/scripts/segment.py samples/judgment_sample_001.txt | head -40
python3 skills/doc-segmenter/scripts/segment.py samples/judgment_sample_001.pdf | head -40
```

Or import programmatically:

```python
from skills.doc-segmenter.scripts.segment import segment
result = segment(open("samples/judgment_sample_001.txt").read())
```

## Rules

1. Input text is first normalized: per-line leading page markers (e.g. `01`, `02`) and `第[一二三四]頁` page footers are stripped.
2. Section boundaries are detected by regex over full-width / half-width variants of the anchors: `主文`, `事實(及理由)?`, `犯罪事實`, `證據(及所犯法條)?`, `理由`, `論罪科刑`, `據上論斷`, `附錄.*法條`. See `references/section_taxonomy.md`.
3. If no section anchors are found, the whole document is returned under label `未分段`.
4. Paragraphs are split on blank lines and on Chinese ordinal bullets (`一、`, `二、`, `三、`, ...).
5. IDs are assigned in a single pass; rerunning on unchanged text yields identical IDs.

## Evaluation

Against `samples/judgment_sample_001.txt` (the bundled drunk-driving simplified verdict) the segmenter should:

- Return at least 5 distinct sections (主文, 事實及理由, 犯罪事實, 證據及所犯法條, 附錄法條).
- Emit non-empty `paragraphs` for each section.
- Produce the same JSON bytes across two consecutive runs.

## References

- `references/section_taxonomy.md` - canonical section set with aliases + regex patterns.
- Upstream RFP: Taiwan Judicial Academy drug-judgment mining spec, section IX.
