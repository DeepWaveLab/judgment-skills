# Chinese Numeral Tables — Taiwan Judgments

## Digits

| 大寫 (formal) | 小寫 (traditional) | Arabic |
|---------------|--------------------|--------|
| 零            | 〇 / ○ / 零        | 0      |
| 壹            | 一                 | 1      |
| 貳            | 二 (or 兩)         | 2      |
| 參 / 叄       | 三                 | 3      |
| 肆            | 四                 | 4      |
| 伍            | 五                 | 5      |
| 陸            | 六                 | 6      |
| 柒            | 七                 | 7      |
| 捌            | 八                 | 8      |
| 玖            | 九                 | 9      |

## Units

| 大寫 | 小寫 | Value |
|------|------|-------|
| 拾   | 十   | 10    |
| 佰   | 百   | 100   |
| 仟   | 千   | 1,000 |
| 萬   | 萬   | 10,000 |
| 億   | 億   | 100,000,000 |

> Accounting 大寫 is commonly used in formal financial expressions in
> judgments, e.g. penalty amounts (新臺幣貳萬元). Judges mix 大寫 and 小寫
> freely: `柒年陸月` (sentence) alongside `30 萬元以下罰金` (statute).

## Composition rules

Numerals compose with units into an additive structure:

- `參拾陸` = 3 × 10 + 6 = 36
- `貳萬伍仟` = 2 × 10000 + 5 × 1000 = 25000
- `一千二百萬` = (1 × 1000 + 2 × 100) × 10000 = 12,000,000
- `一億二千三百四十五萬` = 1 × 10^8 + (1 × 1000 + 2 × 100 + 3 × 10 + 4) × 10000 + 5 = 123,450,005 (not normally seen)

### Special cases

- Leading unit with no digit: `十五` = 15 (implicit `一` before `十`).
- Masked values: published judgments sometimes mask personal phone numbers
  with `○` (full-width circle), which behaves as 0 for parsing but is
  normally redacted upstream by `pii-deid` before normalization runs.

## Sentence-length conventions

| Law-book phrase     | Canonical form                |
|---------------------|-------------------------------|
| 有期徒刑 X 年 Y 月    | `{"months": 12X + Y}`         |
| 有期徒刑 Y 月        | `{"months": Y}`               |
| 拘役 N 日            | `{"days": N}`                 |
| 無期徒刑             | `{"life": true}`              |
| 死刑                 | `{"death": true}`             |

Under Taiwan criminal law 拘役 (short-term detention) is measured in days
(1 to 120 days max), whereas 有期徒刑 (fixed-term imprisonment) is measured
in months/years — the normalizer follows that convention.

## Monetary conventions

`新臺幣` / `新台幣` / `NT$` prefixes are all accepted. The 萬 / 百萬 / 千萬
/ 億 suffixes multiply the leading numeral. Examples:

| Raw                | Normalized    |
|--------------------|---------------|
| 新臺幣壹仟元        | 1000          |
| 新臺幣貳萬元        | 20000         |
| 30 萬元            | 300000        |
| 3 百萬元           | 3000000       |
| 新臺幣一億元        | 100000000     |

## ROC → Gregorian

`民國 Y 年` = `(Y + 1911)` A.D. The sample judgment's `中華民國 115 年 4 月
21 日` becomes `2026-04-21`.
</content>
</invoke>