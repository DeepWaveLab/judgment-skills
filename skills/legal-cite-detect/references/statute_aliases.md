# Statute Aliases

Short-form statute names the detector accepts, and the canonical form it emits.

| Short / alias | Canonical `statute` field |
|---------------|---------------------------|
| 刑法 | 中華民國刑法 |
| 中華民國刑法 | 中華民國刑法 |
| 刑訴 | 刑事訴訟法 |
| 刑事訴訟法 | 刑事訴訟法 |
| 刑法施行法 | 刑法施行法 |
| 毒危條例 | 毒品危害防制條例 |
| 毒品危害防制條例 | 毒品危害防制條例 |
| 陸海空軍刑法 | 陸海空軍刑法 |
| 道路交通管理處罰條例 | 道路交通管理處罰條例 |
| 道交條例 | 道路交通管理處罰條例 |
| 槍砲彈藥刀械管制條例 | 槍砲彈藥刀械管制條例 |
| 組織犯罪防制條例 | 組織犯罪防制條例 |

## Matching strategy

1. Longest alias wins (`中華民國刑法` before `刑法`).
2. `刑法` alone is mapped to `中華民國刑法`; `刑法施行法` stays distinct because its alias is longer.
3. `刑訴` must be followed by `法` or `第N條` to avoid false positives on prose like 「刑訴程序」.

## Extending the table

Add a new row above and extend the regex alternation in `scripts/detect.py`. Order matters - the regex alternates are tried left-to-right, so put longer / more specific names first.
