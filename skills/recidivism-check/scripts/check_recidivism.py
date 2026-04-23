#!/usr/bin/env python3
"""recidivism-check: apply a simplified 刑法§47 to decide 累犯 status.

CLI:
    python3 check_recidivism.py samples/judgment_sample_001.txt
    python3 check_recidivism.py samples/judgment_sample_001.txt --current-date 2026-03-17
    python3 check_recidivism.py                                    # self-test

Library:
    from check_recidivism import check_recidivism, extract_priors_from_text
    priors = extract_priors_from_text(text)
    result = check_recidivism(priors, current_case={"offense_date": "2026-03-17"})
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

FIVE_YEARS_DAYS = 1826  # 5 * 365 + 1 leap day (刑法§47 general rule)
TEN_YEARS_DAYS = 3653   # 10 * 365 + 3 leap days (刑法§185-3 III special enhancement)

CAVEAT = (
    "刑法§47 還要求前案刑罰已執行完畢或赦免；本技能無法僅從文字確認，請人工再覆核。"
)

# Crime categories that trigger §185-3 III's 10-year window instead of §47's 5-year window.
TEN_YEAR_WINDOW_CRIMES = ("公共危險", "不能安全駕駛", "酒駕")

# Regex for a ROC-formatted case number, e.g. 107年度湖交簡字第433號
_CASE_NO_RE = re.compile(
    r"(?P<year>\d{2,3})\s*年(?:度)?\s*(?P<court>[\u4e00-\u9fff]{1,8})字第\s*(?P<num>\d+)\s*號"
)

# ROC-formatted date, e.g. 107年7月10日 or 民國107年7月10日
_ROC_DATE_RE = re.compile(
    r"(?:民國\s*)?(?P<y>\d{2,3})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
)

# Sentence phrases: 有期徒刑2月 or 有期徒刑1年6月 or 拘役N日
_SENTENCE_YEARS_MONTHS_RE = re.compile(
    r"有期徒刑\s*(?:(?P<y>\d+)\s*年)?\s*(?:(?P<m>\d+)\s*月)?"
)
_DETENTION_RE = re.compile(r"拘役\s*(?P<d>\d+)?\s*日?")


def _roc_to_iso(y: int, m: int, d: int) -> str | None:
    """Convert ROC-year y/m/d to ISO YYYY-MM-DD string; return None if invalid."""
    try:
        return date(y + 1911, m, d).isoformat()
    except (ValueError, OverflowError):
        return None


def _parse_iso(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def extract_priors_from_text(text: str) -> list[dict]:
    """Regex-scan for prior-case references. Returns a list of dicts with fields:
        case_no, finalized_date (ISO str or None), sentence_months (int or None), crime_type (str or None).

    Filters:
      * ROC year must be 1..150 (plausible range).
      * Skip 偵 / 他 / 相 / 核 filing-style case numbers (prosecutorial stage, not a conviction).
      * Skip the current case's own case number if it appears at the top of the judgment.
    """
    priors: list[dict] = []
    seen_case_nos: set[str] = set()
    # flatten whitespace/newlines lightly for context windows
    flat = re.sub(r"\s+", "", text)

    # Detect the current case's own header case number (typically first match near the top)
    own_case_no: str | None = None
    head = flat[:200]
    head_m = _CASE_NO_RE.search(head)
    if head_m:
        own_case_no = f"{head_m.group('year')}年度{head_m.group('court')}字第{head_m.group('num')}號"

    for m in _CASE_NO_RE.finditer(flat):
        year_int = int(m.group("year"))
        court = m.group("court")
        if year_int < 1 or year_int > 150:
            continue
        # Skip prosecutorial / non-conviction filings
        if any(kw in court for kw in ("偵", "他", "相", "核", "選偵", "軍他")):
            continue
        case_no = f"{year_int}年度{court}字第{m.group('num')}號"
        if own_case_no and case_no == own_case_no:
            continue
        if case_no in seen_case_nos:
            continue
        seen_case_nos.add(case_no)
        # context window: 60 chars before + 60 chars after
        start = max(0, m.start() - 80)
        end = min(len(flat), m.end() + 80)
        ctx = flat[start:end]

        # Finalized date: find last ROC date BEFORE the case no (typical phrasing
        # "於107年7月10日以107年度湖交簡字第433號判決判處")
        finalized = None
        pre = flat[start:m.start()]
        dates_before = list(_ROC_DATE_RE.finditer(pre))
        if dates_before:
            last = dates_before[-1]
            finalized = _roc_to_iso(int(last.group("y")), int(last.group("m")), int(last.group("d")))
        if finalized is None:
            # fallback: any ROC date in context
            any_date = _ROC_DATE_RE.search(ctx)
            if any_date:
                finalized = _roc_to_iso(int(any_date.group("y")), int(any_date.group("m")), int(any_date.group("d")))

        # Sentence months - look AFTER the case no for "有期徒刑..." or "拘役..."
        post = flat[m.end():end]
        sentence_months = None
        sm = _SENTENCE_YEARS_MONTHS_RE.search(post)
        if sm and (sm.group("y") or sm.group("m")):
            yrs = int(sm.group("y") or 0)
            mos = int(sm.group("m") or 0)
            total = yrs * 12 + mos
            if total > 0:
                sentence_months = total
        if sentence_months is None and _DETENTION_RE.search(post):
            # 拘役 - treat as 0 months but custodial (caller uses crime_type for detection)
            sentence_months = 0

        # Crime type - heuristics: look for 公共危險 / 毒品 / 竊盜 / 詐欺 / 傷害 / 不能安全駕駛
        crime_type = None
        for keyword in ("公共危險", "毒品", "竊盜", "詐欺", "傷害", "不能安全駕駛", "違反毒品危害防制條例"):
            if keyword in ctx:
                crime_type = keyword
                break

        priors.append({
            "case_no": case_no,
            "finalized_date": finalized,
            "sentence_months": sentence_months,
            "crime_type": crime_type,
        })
    return priors


def _extract_offense_date(text: str) -> str | None:
    """Try to extract the current offense date from judgment text.

    Heuristic:
      1. Scan every '犯罪事實' heading; prefer the first whose following 400-char
         window contains a '於民國YYY年M月D日' phrase (that is the offense statement).
      2. Fall back to any '於民國...' phrase in the whole text.
      3. Fall back to the first '民國...' date after the last 犯罪事實.
    """
    flat = re.sub(r"\s+", "", text)
    yu_pat = re.compile(r"於\s*民國?\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")

    # Try every 犯罪事實 position and pick the first that contains '於民國...'
    for m in re.finditer(r"犯罪事實", flat):
        ctx = flat[m.end(): m.end() + 400]
        d = yu_pat.search(ctx)
        if d:
            return _roc_to_iso(int(d.group(1)), int(d.group(2)), int(d.group(3)))

    # Fallback 1: any 於民國 phrase anywhere
    d = yu_pat.search(flat)
    if d:
        return _roc_to_iso(int(d.group(1)), int(d.group(2)), int(d.group(3)))

    # Fallback 2: first 民國 date after last 犯罪事實
    positions = [m.end() for m in re.finditer(r"犯罪事實", flat)]
    if positions:
        ctx = flat[positions[-1]:positions[-1] + 600]
        d = re.search(r"民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", ctx)
        if d:
            return _roc_to_iso(int(d.group(1)), int(d.group(2)), int(d.group(3)))

    # Last resort
    d = _ROC_DATE_RE.search(flat)
    if d:
        return _roc_to_iso(int(d.group("y")), int(d.group("m")), int(d.group("d")))
    return None


def _is_custodial(prior: dict) -> bool:
    sm = prior.get("sentence_months")
    if isinstance(sm, (int, float)) and sm >= 1:
        return True
    ct = prior.get("crime_type") or ""
    # 拘役 detection already records sentence_months == 0 as custodial-ish when crime_type hints
    # but to stay conservative we require the literal 拘役 marker in crime_type OR a known 公共危險/毒品 hit with sm==0
    if "拘役" in ct:
        return True
    # If sentence_months == 0 (set by 拘役 branch), also custodial
    if sm == 0:
        return True
    return False


def _window_days_for(current_case: dict) -> tuple[int, str]:
    """Return (window_days, window_label) based on the current case's crime type.

    公共危險 / 不能安全駕駛 → 10 years per 刑法§185-3 III.
    Everything else → 5 years per 刑法§47.
    """
    ct = (current_case.get("crime_type") or "")
    for kw in TEN_YEAR_WINDOW_CRIMES:
        if kw in ct:
            return TEN_YEARS_DAYS, "10年內"
    return FIVE_YEARS_DAYS, "5年內"


def check_recidivism(prior_records: list[dict], current_case: dict) -> dict:
    """Apply simplified 刑法§47 (with 刑法§185-3 III carve-out).

    Returns the recidivism result dict.
    """
    offense_iso = current_case.get("offense_date")
    offense = _parse_iso(offense_iso) if offense_iso else None
    if offense is None:
        return {
            "is_recidivist": False,
            "matched_priors": [],
            "rationale": "無法判定：當前案件缺少 offense_date。",
            "caveat": CAVEAT,
        }

    window_days, window_label = _window_days_for(current_case)

    matched: list[dict] = []
    for p in prior_records:
        fd_iso = p.get("finalized_date")
        fd = _parse_iso(fd_iso) if fd_iso else None
        if fd is None:
            continue
        delta = (offense - fd).days
        within = 0 <= delta <= window_days
        custodial = _is_custodial(p)
        if within and custodial:
            matched.append({
                "case_no": p.get("case_no"),
                "finalized_date": fd_iso,
                "days_to_offense": delta,
                "within_window": True,
                "window": window_label,
                "custodial": True,
            })

    if matched:
        m = matched[0]
        rationale = (
            f"{m['case_no']} 判決確定 {m['finalized_date']}, "
            f"本案犯罪日 {offense.isoformat()}, {window_label}。"
        )
        return {
            "is_recidivist": True,
            "matched_priors": matched,
            "rationale": rationale,
            "caveat": CAVEAT,
        }

    return {
        "is_recidivist": False,
        "matched_priors": [],
        "rationale": f"本案犯罪日 {offense.isoformat()}，無符合 §47 之前案（{window_label}）。",
        "caveat": CAVEAT,
    }


def _find_sample() -> str | None:
    """Locate samples/judgment_sample_001.txt relative to repo root."""
    here = os.path.abspath(os.path.dirname(__file__))
    # repo root is 3 levels up: scripts -> skill -> skills -> repo
    candidates = [
        os.path.join(here, "..", "..", "..", "samples", "judgment_sample_001.txt"),
        os.path.join(os.getcwd(), "samples", "judgment_sample_001.txt"),
    ]
    for c in candidates:
        c = os.path.abspath(c)
        if os.path.exists(c):
            return c
    return None


def _detect_crime_type(text: str) -> str | None:
    for kw in ("公共危險", "不能安全駕駛", "違反毒品危害防制條例", "毒品", "竊盜", "詐欺", "傷害"):
        if kw in text:
            return kw
    return None


def _self_test() -> dict:
    sample = _find_sample()
    if sample is None:
        # Fallback: synthetic example
        return check_recidivism(
            prior_records=[{
                "case_no": "107年度湖交簡字第433號",
                "finalized_date": "2018-07-10",
                "sentence_months": 2,
                "crime_type": "公共危險",
            }],
            current_case={"offense_date": "2026-03-17", "crime_type": "公共危險"},
        )
    with open(sample, "r", encoding="utf-8") as fh:
        text = fh.read()
    priors = extract_priors_from_text(text)
    offense = _extract_offense_date(text)
    crime = _detect_crime_type(text)
    result = check_recidivism(priors, current_case={"offense_date": offense, "crime_type": crime})
    # Attach extraction detail to help humans debug
    result["_extracted_priors"] = priors
    result["_detected_offense_date"] = offense
    result["_detected_crime_type"] = crime
    return result


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        result = _self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Check 累犯 per simplified 刑法§47.")
    parser.add_argument("text_path", help="path to judgment text file")
    parser.add_argument("--current-date", help="ISO YYYY-MM-DD override for the 犯罪日")
    args = parser.parse_args(argv[1:])

    with open(args.text_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    priors = extract_priors_from_text(text)
    offense = args.current_date or _extract_offense_date(text)
    crime = _detect_crime_type(text)
    result = check_recidivism(priors, current_case={"offense_date": offense, "crime_type": crime})
    result["_extracted_priors"] = priors
    result["_detected_offense_date"] = offense
    result["_detected_crime_type"] = crime
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
