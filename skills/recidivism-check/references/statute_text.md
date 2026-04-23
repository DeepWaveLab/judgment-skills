# 刑法 §47 - Statute Text and Interpretation

## Statutory text (中華民國刑法)

> **第 47 條** 受徒刑之執行完畢，或一部之執行而赦免後，五年以內故意再犯有期徒刑以上之罪者，為累犯，加重本刑至二分之一。
>
> 第九十八條第二項關於因強制工作而免其刑之執行者，於受強制工作處分之執行完畢或一部之執行而免除後，五年以內故意再犯有期徒刑以上之罪者，以累犯論。

## Plain-English elements

For a defendant to be a 累犯 ("recidivist") the court must find all of:

1. **Prior custodial sentence fully served or pardoned**. The earlier 徒刑 (imprisonment) was executed to completion, or a portion was executed and the remainder pardoned (赦免). Mere probation / fine does not qualify.
2. **Within 5 years**. The new offense was committed within 5 years after the prior sentence's execution ended (or pardon took effect).
3. **New crime is intentional (故意) and punishable by 有期徒刑 or above**. Negligent crimes do not trigger §47.

If all three are met, the court **must** add up to 1/2 to the statutory penalty (加重本刑至二分之一).

## What this skill approximates

This skill operates over text and structured extractions; it **cannot** verify element (1) with certainty (whether the prior sentence was fully served). It therefore implements a practical proxy:

- Approximates "execution completed" with `finalized_date` (判決確定日) plus a presumption that a short prior sentence has been served by the time the new offense occurs.
- Approximates the 5-year window by comparing `finalized_date` to the current `offense_date`.
- Approximates "custodial" by `sentence_months >= 1` OR the word `拘役` appearing in the record (in practice, most real 累犯 authorities now treat 拘役 as qualifying for §47 purposes as well, though doctrine is not uniform).

For every positive finding the skill emits a `caveat` reminding the reviewer that they must manually confirm element (1) from the prior judgment's execution record.

## ROC-date to Gregorian conversion

Taiwan judgment dates are often given in 民國 (ROC) years: `ROC_year + 1911 = Gregorian_year`. Example: `107年7月10日` -> `2018-07-10`. The `extract_priors_from_text` helper performs this conversion.

## 5-year window math

The skill uses calendar-aware date subtraction via `datetime.date`. 5 years = 1826 days (accounts for 1 leap year in an arbitrary 5-year span). Window is **inclusive** on both endpoints: if the prior's `finalized_date` is exactly 5 years before `offense_date` it still counts.

## 刑法 §185-3 III - 10-year carve-out

The statute for drunk driving / dangerous driving has an **explicit** 10-year recidivism enhancement that is broader than §47's general 5-year window:

> 曾犯本條或陸海空軍刑法第54條之罪，經有罪判決確定或經緩起訴處分確定，於十年內再犯第1項之罪因而致人於死者，處無期刑或5年以上有期徒刑…

When the current case is classified as 公共危險 / 不能安全駕駛 / 酒駕, this skill uses a **10-year window (3653 days)** instead of the default 5 years. The matched prior's `window` field records which window was applied ("5年內" / "10年內").

This is a defensible default for 公共危險 judgments; however the full §185-3 III text targets specific outcomes (致人於死 / 致重傷). Reviewers should confirm whether the enhancement actually applies to the sentencing posture of the case.

## Edge cases deliberately left to human review

- Prior was 緩刑 (suspended sentence) later revoked.
- Prior was 易科罰金 (commutation to fine) - doctrinally does NOT count as "executed".
- Multiple priors; §47 only needs one qualifying prior.
- Juvenile records (少年事件處理法).
- Military convictions under 陸海空軍刑法.

All of these surface via the `caveat` field and should be reviewed with `review-todo-generator` prioritisation.
