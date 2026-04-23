# PII Pattern Reference — Taiwan Judgments

This document enumerates every regex used by `scripts/deid.py`, the reasoning
behind it, and an example drawn from real Taiwan criminal judgments.

## 1. Role-tagged Chinese names

Chinese personal names in judgments almost always appear right after a role
label. We anchor on the role, then grab the 2-4 Han-character name that
follows.

```
(role)\s*(Name)
```

where `Name = [Surname][GivenName]{1,3}`. The surname class is an explicit
百家姓-derived whitelist (roughly 500 Taiwan-common Han characters); the
given-name class is `[\u4e00-\u9fff]` minus a stop-set of verbs /
prepositions / conjunctions / place suffixes that reliably terminate a
name (`的了於在是有…`). This surname-anchored, stop-char-bounded approach
is much more precise than matching any 2-4 Han run after a role tag, which
greedily swallows verb phrases like `因公共危` (`被告因公共危險…`).

Several single-character "surnames" that also function as common function
words are explicitly removed from the whitelist to prevent false positives:
`於 (prep.) 臺 (place prefix) 都 和 方 中 時 先 單 達 全 本 南`.

`聲請人` is deliberately **not** in the role set because in Taiwan practice
the `聲請人` of a criminal-summary case is an institution (the prosecutor's
office), not a named individual — the prosecutor's personal name appears
later, tagged with `檢察官`.

| Role pattern (regex) | Code family | Example matched string | Example replacement |
|----------------------|-------------|------------------------|---------------------|
| `被\s*告\s*人?` | `D` | `被告 何建睿` | `被告 D-001` |
| `被\s*害\s*人` | `V` | `被害人 王小明` | `被害人 V-001` |
| `證\s*人` | `W` | `證人 陳大華` | `證人 W-001` |
| `檢\s*察\s*官` | `O` | `檢察官 林彥均` | `檢察官 O-001` |
| `法\s*官` | `O` | `法官 曾名阜` | `法官 O-002` |
| `書\s*記\s*官` | `O` | `書記官 李璁潁` | `書記官 O-003` |
| `辯\s*護\s*人` | `O` | `辯護人 張某某` | `辯護人 O-NNN` |
| `告\s*訴\s*人` | `V` | `告訴人 李某` | `告訴人 V-NNN` |

### Institution guard

To avoid eating "地方法院", "地方檢察署", "分局", "派出所" etc, the name
regex is followed by:

```
(?!地方|法院|檢察|分局|警察|派出|派遣|刑事|民事|交通|市政|縣政|簡易|
   公司|銀行|商店|事件|案件|部分|法庭|法條|庭長|庭員|轄區|警局|政府|
   醫院|機關|審判|偵查|告訴|上訴|辯護|車牌)
```

### Replay pass

After the role-tagged pass, any bare subsequent mention of an already-coded
name (e.g. the defendant's name later in the narrative without the 被告
prefix) is replaced with the same code via a simple `str.replace`, sorted by
longest-first to prevent prefix overlap.

## 2. ROC national ID number

Taiwan national ID format: one uppercase letter (area code) + `1` (male) or
`2` (female) + 8 digits.

```
(?<![A-Z])[A-Z][12]\d{8}(?!\d)
```

Example: `A123456789` → `ID-001`.

## 3. Vehicle plates

Taiwan plates always end with 3-4 digits or 3-4 uppercase alphanumerics.
To avoid colliding with our own placeholder codes like `ADDR-001` or
`PL-001` (which would otherwise recursively match the `[A-Z]{2,4}-\d{3,4}`
arm), we restrict the regex to the digits-first arm:

```
(?<![A-Za-z0-9])\d{3,4}-[A-Z0-9]{3,4}(?![A-Za-z0-9])
```

| Example | Replacement |
|---------|-------------|
| `1234-AB` | `PL-001` |
| `000-0000` (masked in judgment) | `PL-001` |
| `123-4567` | `PL-001` |

Note: the sample judgment uses `車牌號碼000-0000號` — the masked digits match
the `\d{3,4}-[A-Z0-9]{3,4}` arm. The letters-first plate variant
(`ABC-1234`) is rare in redacted published judgments; if you need it, drop
it back in and switch your placeholder prefix to something numeric to avoid
the recursion collision.

## 4. Phone numbers

```
(?:09\d{2}[- ]?\d{3}[- ]?\d{3}|0\d{1,2}[- ]?\d{6,8})
```

Covers mobile (`0912-345-678`, `0912345678`) and landline (`02-12345678`,
`037-123456`).

## 5. Street address

Taiwan addresses start at a specific city/county name (`臺北市`, `新北市`,
…), then optionally chain through `區/鄉/鎮/市`, `村/里`, `路/街/大道`,
`段`, `巷`, `弄`, `號`, `樓`. The final required component is `號` (門牌號)
— we only redact to a resolution that could identify a building.

Anchoring on the exact city-name list (rather than "any Han run ending in
市") avoids swallowing verb prefixes like `行經臺北市` into
`行經臺北市`.

```
(?:臺北|台北|新北|桃園|臺中|台中|臺南|台南|高雄|基隆|新竹|嘉義|
   苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|臺東|台東|澎湖|金門|連江)
(?:縣|市)
(?:WS [\u4e00-\u9fff○]{1,6}(?:區|鄉|鎮|市))?
(?:WS [\u4e00-\u9fff○]{1,8}(?:村|里))?
(?:WS [\u4e00-\u9fff○\d]{1,10}(?:路|街|大道))
(?:WS [\u4e00-\u9fff○\d一二三四五六七八九十]{1,4}段)?
(?:WS \d+巷)?
(?:WS \d+弄)?
(?:WS \d+(?:之\d+)?號)
(?:WS \d+樓)?
```

`WS` = `\s*(?:\n\s*\d{1,2}\s*)?` — tolerates line breaks and the page-
column digit re-prefix that shows up when a judgment PDF is extracted to
text (e.g. `行經臺北市○○區○○○路\n15 00巷00號`).

`○` (full-width circle) is explicitly whitelisted inside Han runs because
the publisher pre-masks some address components that way.

Example from the sample: `臺北市○○區○○○路\n15 00巷00號` → `ADDR-001`.

## 6. Ordering

1. Role-tagged names.
2. Replay known names (bare mentions).
3. Addresses (before plates, because address ends in digits that could
   pattern-collide with a plate's leading digits).
4. ROC national ID.
5. Plates.
6. Phones.
</content>
</invoke>