#!/usr/bin/env python3
"""drug-sales-extract - rule-based extractor for Taiwan drug-sales judgments.

CLI:
    python3 skills/drug-sales-extract/scripts/extract.py <text-or-pdf>

Library:
    from extract import extract
    record = extract(text)                      # raw text
    record = extract(segmented_dict)            # output of doc-segmenter

The production pipeline uses an LLM over the segmented judgment; this rule-based
implementation is the offline fallback and smoke test. It deliberately returns a
well-typed record with null defaults on non-drug cases.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Chinese numeral parser (covers 零〇一二三四五六七八九十百千 + 大寫變體).
# ---------------------------------------------------------------------------
_CN_DIGIT = {
    "零": 0, "〇": 0, "0": 0,
    "一": 1, "壹": 1, "二": 2, "貳": 2, "兩": 2,
    "三": 3, "參": 3, "叁": 3, "四": 4, "肆": 4,
    "五": 5, "伍": 5, "六": 6, "陸": 6,
    "七": 7, "柒": 7, "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}
_CN_UNIT = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000, "萬": 10000, "億": 100_000_000}


def _chinese_to_int(s: str) -> Optional[int]:
    """Parse a Chinese numeral string (possibly mixed with Arabic digits) to int.

    Returns None if the string cannot be fully parsed.
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    # Pure Arabic fast path (commas allowed).
    if re.fullmatch(r"[\d,]+", s):
        return int(s.replace(",", ""))

    total = 0
    current = 0
    section = 0  # accumulates within a 萬/億 group
    for ch in s:
        if ch in _CN_DIGIT:
            current = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            if unit >= 10000:
                section = (section + (current or 1)) * unit
                total += section
                section = 0
                current = 0
            else:
                if current == 0:
                    current = 1
                section += current * unit
                current = 0
        elif ch.isdigit():
            current = current * 10 + int(ch)
        else:
            return None
    return total + section + current


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_text(source: Union[str, Dict, Path]) -> str:
    """Accept raw text, segmented JSON, or a path; return a single text blob."""
    if isinstance(source, dict) and "sections" in source:
        parts: List[str] = []
        for sec in source["sections"]:
            parts.append(sec.get("label", ""))
            for p in sec.get("paragraphs", []):
                parts.append(p.get("text", ""))
        return "\n".join(parts)
    if isinstance(source, Path):
        return _load_path(source)
    if isinstance(source, str):
        p = Path(source)
        if len(source) < 500 and p.exists():
            return _load_path(p)
        return source
    raise TypeError(f"unsupported input type: {type(source)!r}")


def _load_path(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        sys.path.insert(0, str(scripts_dir))
        from pdf_to_text import pdf_to_text  # type: ignore

        return pdf_to_text(path)
    return path.read_text(encoding="utf-8")


def _first(pattern: str, text: str, flags: int = 0, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    try:
        return m.group(group).strip()
    except IndexError:
        return m.group(0).strip()


def _parse_sentence_months(text: str) -> Optional[int]:
    """Return total months from the first 有期徒刑 span."""
    m = re.search(r"有期徒刑([0-9一二三四五六七八九十百千壹貳參肆伍陸柒捌玖拾佰仟兩]+)(?:年)?", text)
    if not m:
        return None
    span_start = m.start()
    snippet = text[span_start : span_start + 40]
    years = 0
    months = 0
    ym = re.search(r"([0-9一二三四五六七八九十百千壹貳參肆伍陸柒捌玖拾佰仟兩]+)\s*年", snippet)
    mm = re.search(r"([0-9一二三四五六七八九十百千壹貳參肆伍陸柒捌玖拾佰仟兩]+)\s*月", snippet)
    if ym:
        y = _chinese_to_int(ym.group(1))
        if y is not None:
            years = y
    if mm:
        mo = _chinese_to_int(mm.group(1))
        if mo is not None:
            months = mo
    total = years * 12 + months
    return total or None


def _parse_fine(text: str) -> Optional[int]:
    m = re.search(
        r"併科罰金\s*新臺幣?\s*([0-9,一二三四五六七八九十百千萬億壹貳參肆伍陸柒捌玖拾佰仟兩]+)\s*元",
        text,
    )
    if not m:
        return None
    return _chinese_to_int(m.group(1))


def _parse_commute_rate(text: str) -> Optional[int]:
    m = re.search(
        r"新臺幣?\s*([0-9,一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟兩]+)\s*元\s*折算[壹一]?日",
        text,
    )
    if not m:
        return None
    return _chinese_to_int(m.group(1))


def _parse_seized_weight_g(text: str) -> Optional[float]:
    m = re.search(r"扣案[^。]{0,40}?(\d+(?:\.\d+)?)\s*(公斤|公克|克)", text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "公斤":
        value *= 1000
    return value


def _detect_drug(text: str) -> tuple[Optional[str], Optional[str]]:
    schedule = None
    m = re.search(r"第([一二三四])級毒品", text)
    if m:
        schedule = m.group(1)
    drug_names = [
        "海洛因",
        "甲基安非他命",
        "安非他命",
        "MDMA",
        "搖頭丸",
        "大麻",
        "愷他命",
        "K他命",
        "K他命",
        "咖啡包",
    ]
    drug_type = next((name for name in drug_names if name in text), None)
    return schedule, drug_type


def _detect_statutes(text: str) -> List[str]:
    """Light statute listing for the record. Full detection lives in legal-cite-detect."""
    out: List[str] = []
    seen = set()
    for m in re.finditer(
        r"(刑法施行法|刑事訴訟法|毒品危害防制條例|刑法)第(\d+(?:-\d+)?|[0-9一二三四五六七八九十百千壹貳參肆伍陸柒捌玖拾佰仟]+(?:之[0-9一二三四五六七八九十壹貳參肆伍陸柒捌玖拾]+)?)條(?:第(\d+|[一二三四五六七八九十])項)?(?:第(\d+|[一二三四五六七八九十])款)?",
        text,
    ):
        raw = m.group(0)
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def _detect_prior_cases(text: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for m in re.finditer(r"\d{2,3}年度[\u4e00-\u9fff]+字第\d+號", text):
        val = m.group(0)
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _extract_defendants(text: str) -> tuple[Optional[str], List[str]]:
    names: List[str] = []
    for m in re.finditer(r"被\s*告\s+([\u4e00-\u9fff]{2,4})", text):
        name = m.group(1)
        if name not in names:
            names.append(name)
    if not names:
        return None, []
    return names[0], names[1:]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract(source: Union[str, Dict, Path]) -> Dict[str, Any]:
    text = _coerce_text(source)

    defendant, co_defendants = _extract_defendants(text)
    schedule, drug_type = _detect_drug(text)

    is_drug = ("毒品危害防制條例" in text) and any(
        kw in text for kw in ("販賣", "轉讓", "販售")
    )

    # transaction_count: count explicit 次 mentions near 販賣/交易.
    tx_count: Optional[int] = None
    if is_drug:
        matches = re.findall(r"(?:販賣|交易|出售)[^。]{0,20}?(\d+|[一二三四五六七八九十])\s*次", text)
        if matches:
            total = 0
            for m in matches:
                v = _chinese_to_int(m)
                if v is not None:
                    total += v
            tx_count = total or None

    sentence_text = _first(r"(有期徒刑[^\s，。]+)", text)
    sentence_months = _parse_sentence_months(text)
    fine = _parse_fine(text)
    commute = _parse_commute_rate(text)

    record: Dict[str, Any] = {
        "is_drug_sales_case": is_drug,
        # case metadata
        "case_no": _first(r"(\d{2,3}年度[\u4e00-\u9fff]*字第\d+號)", text),
        "court": _first(r"((?:臺灣|福建)[\u4e00-\u9fff]*?法院)", text),
        "judgment_date": _first(r"(中\s*華\s*民\s*國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日)", text),
        "judge": _first(r"法\s*官\s+([\u4e00-\u9fff]{2,4})", text),
        "prosecutor": _first(r"檢\s*察\s*官\s+([\u4e00-\u9fff]{2,4})", text),
        # parties
        "defendant": defendant,
        "co_defendants": co_defendants,
        # drug descriptors
        "drug_schedule": schedule,
        "drug_type": drug_type,
        "seized_weight_g": _parse_seized_weight_g(text),
        "purity_percent": None,
        # transaction
        "transaction_count": tx_count,
        "transaction_amount_twd": None,
        "unit_price_twd": None,
        "buyer": None,
        "transaction_location": None,
        # charges and sentencing
        "indicted_statutes": _detect_statutes(text),
        "charge_label": _first(r"(販賣第[一二三四]級毒品|轉讓第[一二三四]級毒品|施用第[一二三四]級毒品)", text),
        "sentence_months": sentence_months,
        "sentence_text": sentence_text,
        "fine_twd": fine,
        "commute_rate_twd": commute,
        # aggravators / mitigators
        "recidivism": "累犯" in text,
        "confessed": any(kw in text for kw in ("坦承", "自白", "認罪")),
        "probation": ("緩刑" in text) and ("撤銷緩刑" not in text),
        "forfeiture": _first(r"(沒收[^。]+。)", text),
        "prior_cases": _detect_prior_cases(text),
    }

    # For non-drug cases, null out drug-specific numerics defensively.
    if not is_drug:
        for drug_field in (
            "drug_schedule",
            "drug_type",
            "seized_weight_g",
            "purity_percent",
            "transaction_count",
            "transaction_amount_twd",
            "unit_price_twd",
            "buyer",
            "transaction_location",
            "charge_label",
        ):
            record[drug_field] = None

    return record


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: extract.py <text-or-pdf>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1
    record = extract(path)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
