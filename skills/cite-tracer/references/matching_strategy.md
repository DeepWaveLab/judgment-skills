# Matching Strategy

## Pipeline

For each `(field_name, field_value)` in the input:

1. **Stringify** the value into one or more candidate surface forms.
2. **Flatten** `segmented.sections[].paragraphs[]` into document-order
   `(paragraph_id, text)` pairs.
3. **Score** each paragraph:
   - If any surface is a substring of the paragraph (after whitespace
     normalization), score = **1.0**.
   - Else compute `difflib.SequenceMatcher(None, surface, paragraph).ratio()`
     and a sliding-window ratio (to prevent short-surface-vs-long-paragraph
     collapse), take the max.
4. **Keep** paragraphs whose score ≥ **0.6** (cutoff).
5. **Rank** descending, return the top 3 IDs and the best score.

## Surface forms per type

### `str`

The value is used as-is. If it looks like an ISO date
(`YYYY-MM-DD`), additional ROC-calendar surfaces are generated:

| Value          | Added surfaces                                     |
|----------------|-----------------------------------------------------|
| `2026-04-21`   | `中華民國 115 年 4 月 21 日`, `中華民國115年4月21日`, `115 年 4 月 21 日`, `115年4月21日` |

### `int`

| Range              | Added surfaces                                  |
|--------------------|-------------------------------------------------|
| any                | `str(value)`                                    |
| `1 <= v < 100`     | 小寫 CN (`三`), 大寫 CN (`參`), each + `月`, plus `v月` / `v 月` (sentence months) |
| `v >= 1000`        | `{v:,}元`, `{v}元`                               |
| `v % 10000 == 0`   | `{v/10000}萬元`, 大寫 CN of `v/10000` + `萬元`    |

Example: `20000` → `["20000", "20000元", "20,000元", "2萬元", "貳萬元"]`.

Example: `3` → `["3", "三", "參", "三月", "參月", "3月", "3 月"]`.

### `bool`

Just `str(value)`; rarely traced — `True/False` fields should usually be
carried with their underlying evidence field instead.

### `float`

`str(value)` and `f"{value:.2f}"`.

### `list`

Union of surfaces per element.

## Whitespace normalization

Before substring / fuzzy match both sides are passed through
`re.sub(r"\s+", "", s)` so that `有期徒刑 參月` (PDF line-wrapped) matches
`有期徒刑參月` and vice versa.

## Sliding-window fuzzy

When the paragraph is much longer than the surface form, the raw
`SequenceMatcher` ratio under-reports because it's averaging across the
whole paragraph. We additionally slide a window of length `|surface|` across
the paragraph with step `|surface|/2` and take the maximum window ratio.
This restores the expected behavior for short-needle matches while still
keeping things deterministic and stdlib-only.

## Cutoff

0.6 is the standard default used in `difflib.get_close_matches`. Higher
precision (0.75) rejected correct Chinese matches in dev because single-
character substitutions tank the ratio.
</content>
</invoke>