# Similarity Rules - contradiction-check

This document fixes the exact similarity formula applied to each value pair so that diff output is deterministic and reproducible across reruns.

## 1. Value type classification

Before computing similarity we classify each `(rule_value, llm_value)` pair:

| Case | Rule side | LLM side | Behaviour |
|------|-----------|----------|-----------|
| A | None / missing | None / missing | Skip (not emitted) |
| B | non-null | None / missing | Emit `only_rule`, similarity 0.0 |
| C | None / missing | non-null | Emit `only_llm`, similarity 0.0 |
| D | str | str | Token-set Jaccard (section 2) |
| E | list | list | Set Jaccard (section 3) |
| F | bool / int / float | same type | Exact equality, similarity 1.0 or 0.0 |
| G | mixed types | mixed types | Cast both to `str` then apply D |

## 2. String token-set Jaccard

1. Lowercase ASCII letters (Chinese is untouched; Jaccard still works because Chinese tokens are graphemes).
2. Strip punctuation: `，。、；：「」『』（）()[]{}.,;:!?\-_/\\` and whitespace.
3. Tokenize:
   - If the string contains any ASCII word characters, split on whitespace/punct.
   - Otherwise, take each character as a token (CJK-friendly).
4. Jaccard = `|A ∩ B| / |A ∪ B|`. Both empty -> 1.0 (treated as agree).

**Flag thresholds**:

- similarity == 1.0 -> `agree`
- 0.8 <= similarity < 1.0 -> `low_similarity` (boundary case: 0.8 is considered low)
- 0 < similarity < 0.8 -> `low_similarity`
- similarity == 0.0 -> `mismatch`

Note: the plan specifies `< 0.8` triggers `low_similarity`. We preserve that: only equality with 1.0 is `agree`, anything strictly below 0.8 down to 0 exclusive is `low_similarity`, and exactly 0.0 is a hard `mismatch`.

## 3. List set Jaccard

1. Convert each list to a `frozenset` of stringified elements.
2. Jaccard = `|A ∩ B| / |A ∪ B|`. Both empty -> 1.0.
3. Flag thresholds identical to section 2.

## 4. Scalar equality

For `int`, `float`, `bool`, and `None`-free scalars of identical Python type:

- `similarity = 1.0` if `rule == llm` else `0.0`.
- Flag `agree` on 1.0, `mismatch` on 0.0.

Float tolerance is **not** applied - callers must pre-round if needed. This keeps the rule engine fully deterministic.

## 5. Mixed types (case G)

If types differ (e.g. rule emits `3` and LLM emits `"3"`), cast both sides via `str()` then apply the string Jaccard. This prevents trivial type drift from looking like a mismatch while still flagging a true semantic difference.

## 6. Summary statistics

- `summary.total` = number of emitted diff rows.
- `summary.mismatches` = count where `flag in {"mismatch", "only_rule", "only_llm"}`.
- `summary.jaccard_avg` = arithmetic mean of `similarity` over all emitted rows, rounded to 2 decimals. If `total == 0`, returns 1.0 (no disagreement).

## 7. Rounding

All emitted `similarity` values are rounded to 2 decimals to avoid noise in downstream consumers.
