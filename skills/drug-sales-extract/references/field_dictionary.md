# Drug-Sales Field Dictionary (v2.1.0)

Authoritative schema for the drug-sales extractor. Every field MUST be present in the output record, even if null. Types shown use Python annotations.

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class DrugSalesRecord:
    # --- routing -----------------------------------------------------------
    is_drug_sales_case: bool                  # true when 毒危條例 cited + 販賣/轉讓/販售 keyword present

    # --- case metadata -----------------------------------------------------
    case_no: Optional[str]                    # e.g. "115年度交簡字第478號"
    court: Optional[str]                      # e.g. "臺灣臺北地方法院"
    judgment_date: Optional[str]              # ROC date string, raw ("中華民國 115 年 4 月 21 日")
    judge: Optional[str]                      # 法官
    prosecutor: Optional[str]                 # 檢察官

    # --- parties -----------------------------------------------------------
    defendant: Optional[str]                  # 被告 primary name
    co_defendants: List[str]                  # additional 共同被告, [] if none

    # --- drug descriptors --------------------------------------------------
    drug_schedule: Optional[str]              # "一" / "二" / "三" / "四" (毒品級別)
    drug_type: Optional[str]                  # 海洛因 / 甲基安非他命 / MDMA / 大麻 / 愷他命 ...
    seized_weight_g: Optional[float]          # grams, parsed from "扣案...X公克"
    purity_percent: Optional[float]           # 純度 (if reported)

    # --- transaction -------------------------------------------------------
    transaction_count: Optional[int]          # 次數
    transaction_amount_twd: Optional[int]     # total 新臺幣 for all transactions
    unit_price_twd: Optional[int]             # per-transaction price if stated
    buyer: Optional[str]                      # 交易對象 (可化名)
    transaction_location: Optional[str]       # 交易地點

    # --- charges and sentencing -------------------------------------------
    indicted_statutes: List[str]              # e.g. ["毒品危害防制條例第4條第1項"]
    charge_label: Optional[str]               # 販賣第一級毒品 / 轉讓 / 施用 ...
    sentence_months: Optional[int]            # primary term in months (年*12 + 月)
    sentence_text: Optional[str]              # raw 主文刑期 string
    fine_twd: Optional[int]                   # 併科罰金 in TWD
    commute_rate_twd: Optional[int]           # 易科罰金 折算標準 (元/日)

    # --- aggravators / mitigators -----------------------------------------
    recidivism: bool                          # 累犯 (刑法§47)
    confessed: bool                           # 坦承 / 自白 / 認罪
    probation: bool                           # 緩刑 granted (and not 撤銷)
    forfeiture: Optional[str]                 # 沒收 raw description
    prior_cases: List[str]                    # prior case numbers referenced
```

## Field-by-field rules (rule-based extractor)

| # | Field | Source rule |
|---|-------|-------------|
| 1 | is_drug_sales_case | `毒品危害防制條例` AND (`販賣`|`轉讓`|`販售`) both present in text |
| 2 | case_no | regex `\d{2,3}年度[^\s，。]*字第\d+號` - first match |
| 3 | court | regex `(臺灣|福建)[^\s。，]*法院` - first match |
| 4 | judgment_date | raw ROC date line `中華民國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日` - first match |
| 5 | judge | line starting with `法 *官` |
| 6 | prosecutor | line containing `檢察官` + name |
| 7 | defendant | `被 *告\s+(\S+)` - first match |
| 8 | co_defendants | subsequent `被 *告` matches, deduped |
| 9 | drug_schedule | `第([一二三四])級毒品` |
| 10 | drug_type | dictionary hit among {海洛因, 甲基安非他命, 安非他命, 搖頭丸, MDMA, 大麻, 愷他命, K他命, 咖啡包} |
| 11 | seized_weight_g | `扣案.*?(\d+(?:\.\d+)?)\s*(公克\|克\|公斤)` - normalized to grams |
| 12 | purity_percent | `純度.*?(\d+(?:\.\d+)?)\s*%` |
| 13 | transaction_count | count of `交易|販賣|出售` occurrences near 次 |
| 14 | transaction_amount_twd | sum of `新臺幣X元` amounts in 主文 / 事實 |
| 15 | unit_price_twd | `每次\|每筆` + amount |
| 16 | buyer | `販賣.*?予\|售予\|交付.*?予` + following name token |
| 17 | transaction_location | `於.*?(?=販賣\|交易)` heuristic |
| 18 | indicted_statutes | aggregated from legal-cite-detect style regex |
| 19 | charge_label | span matching `販賣第[一二三四]級毒品\|轉讓第[一二三四]級毒品\|施用第[一二三四]級毒品` |
| 20 | sentence_months | parse `有期徒刑(X年)?(X月)?` incl. Chinese numerals, return total months |
| 21 | sentence_text | raw primary 刑期 sentence span |
| 22 | fine_twd | `併科罰金.*?新臺幣(\d+或中文)元` |
| 23 | commute_rate_twd | `以新臺幣(\d+或中文)元折算壹?一?日` |
| 24 | recidivism | `累犯` token present |
| 25 | confessed | `坦承|自白|認罪` present |
| 26 | probation | `緩刑` present AND `撤銷緩刑` absent |
| 27 | forfeiture | span starting with `沒收` up to `。` |
| 28 | prior_cases | all prior `\d+年度[^\s，。]*字第\d+號判決` referenced |

## Non-drug cases

When `is_drug_sales_case` is false every drug-specific field is null / empty list. Case metadata, sentence, fine, recidivism, and confession fields are still populated when parsable - this keeps the record useful for non-drug pipelines that reuse the same schema.

## LLM path

In production Claude reads the segmented judgment plus this dictionary and fills the schema. The rule-based path in `scripts/extract.py` is the offline fallback and the smoke test that catches regressions in field coverage and parser bugs.
