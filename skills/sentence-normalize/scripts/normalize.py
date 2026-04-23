#!/usr/bin/env python3
"""sentence-normalize — convert Taiwan judgment numeric expressions.

Pure-stdlib. Exports `normalize_sentence`, `normalize_money`,
`normalize_roc_date`, and a CLI that scans a text file and prints all matches.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Optional

# --- Numeral tables -------------------------------------------------------
DIGIT_MAP: dict[str, int] = {
    # 大寫
    "零": 0, "壹": 1, "貳": 2, "參": 3, "叄": 3, "肆": 4,
    "伍": 5, "陸": 6, "柒": 7, "捌": 8, "玖": 9,
    # 小寫 (traditional)
    "〇": 0, "○": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

UNIT_MAP: dict[str, int] = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "萬": 10000,
    "億": 100_000_000,
}

DIGIT_CHARS = "".join(DIGIT_MAP.keys())
UNIT_CHARS = "".join(UNIT_MAP.keys())
CN_NUM_CHAR = f"[{DIGIT_CHARS}{UNIT_CHARS}]"
CN_NUM_RUN = CN_NUM_CHAR + "+"

NUM_RE = re.compile(rf"(?:\d+|{CN_NUM_RUN})")


def _cn_to_int(s: str) -> int:
    """Convert a Chinese numeral string (大寫 or 小寫) to int.

    Supports chains like 貳萬伍仟, 一千二百, 參拾陸, and bare digits (一二三
    rendered as "123" is NOT supported — bare sequences are interpreted as
    composed, not concatenated).
    """
    s = s.strip()
    if not s:
        raise ValueError("empty numeral")
    if s.isdigit():
        return int(s)

    # Split on 億 and 萬 first, recurse on the smaller pieces.
    for big_unit, big_val in (("億", 100_000_000), ("萬", 10_000)):
        if big_unit in s:
            left, _, right = s.partition(big_unit)
            left_val = _cn_to_int(left) if left else 1
            right_val = _cn_to_int(right) if right else 0
            return left_val * big_val + right_val

    # Now s only contains digits in [0-9] and units 十百千/拾佰仟.
    total = 0
    current = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in DIGIT_MAP:
            current = DIGIT_MAP[ch]
        elif ch in UNIT_MAP:
            unit = UNIT_MAP[ch]
            if current == 0:
                # e.g. "十五" meaning 15
                current = 1
            total += current * unit
            current = 0
        elif ch.isdigit():
            current = int(ch)
        else:
            raise ValueError(f"bad numeral char: {ch!r} in {s!r}")
        i += 1
    total += current
    return total


def _parse_num(raw: str) -> int:
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    return _cn_to_int(raw)


# --- Sentence -------------------------------------------------------------
SENTENCE_KEYWORDS = r"(?:有期徒刑|拘役)"

# Very tolerant matcher; downstream `normalize_sentence` parses the groups.
SENTENCE_RE = re.compile(
    rf"(無期徒刑|死刑|{SENTENCE_KEYWORDS}\s*"
    rf"(?:\d+|{CN_NUM_RUN})\s*(?:年|月|個月|日|天)"
    rf"(?:\s*(?:\d+|{CN_NUM_RUN})\s*(?:月|個月|日|天))?"
    rf")"
)

YEARS_RE = re.compile(rf"(\d+|{CN_NUM_RUN})\s*年")
MONTHS_RE = re.compile(rf"(\d+|{CN_NUM_RUN})\s*(?:個月|月)")
DAYS_RE = re.compile(rf"(\d+|{CN_NUM_RUN})\s*(?:日|天)")


def normalize_sentence(s: str) -> Optional[dict]:
    """Parse a sentence expression; return canonical dict or None."""
    s = s.strip()
    if not s:
        return None
    if "無期徒刑" in s:
        return {"life": True}
    if "死刑" in s:
        return {"death": True}

    is_detention = "拘役" in s  # 拘役 is always in days under R.O.C. law.
    # Strip leading keyword if present.
    body = re.sub(r"^(?:有期徒刑|拘役)\s*", "", s)

    years = months = days = 0
    found = False

    ym = YEARS_RE.search(body)
    if ym:
        years = _parse_num(ym.group(1))
        body = body[ym.end():]
        found = True
    mm = MONTHS_RE.search(body)
    if mm:
        months = _parse_num(mm.group(1))
        body = body[mm.end():]
        found = True
    dm = DAYS_RE.search(body)
    if dm:
        days = _parse_num(dm.group(1))
        found = True

    if not found:
        return None
    if is_detention or (days and not years and not months):
        return {"days": days or (years * 365 + months * 30)}
    return {"months": years * 12 + months + (days // 30 if days else 0)}


# --- Money ----------------------------------------------------------------
# Note: we deliberately use `[ \t]*` (horizontal whitespace only, no newline)
# between the numeric body and the 元 suffix so that page-column-number
# prefixes like `\n29 ` don't get pulled in as if they were the amount.
MONEY_RE = re.compile(
    rf"(?:新臺幣|新台幣|NT\$?)?[ \t]*"
    rf"((?:\d+|{CN_NUM_RUN})"
    rf"(?:[ \t]*(?:百萬|千萬|萬|億))?)[ \t]*元"
)


def normalize_money(s: str) -> Optional[int]:
    """Parse a monetary expression like `新臺幣貳萬元` → 20000."""
    s = s.strip()
    m = MONEY_RE.search(s)
    if not m:
        return None
    body = m.group(1).strip()
    # Split optional multiplier suffix.
    for suffix, mul in (("百萬", 1_000_000), ("千萬", 10_000_000),
                        ("億", 100_000_000), ("萬", 10_000)):
        if body.endswith(suffix):
            num_part = body[: -len(suffix)].strip()
            if not num_part:
                return mul
            return _parse_num(num_part) * mul
    return _parse_num(body)


# --- ROC date -------------------------------------------------------------
ROC_DATE_RE = re.compile(
    rf"(?:中華民國\s*)?"
    rf"(\d+|{CN_NUM_RUN})\s*年\s*"
    rf"(\d+|{CN_NUM_RUN})\s*月\s*"
    rf"(\d+|{CN_NUM_RUN})\s*日"
)


def normalize_roc_date(s: str) -> Optional[str]:
    """Parse `中華民國 115 年 4 月 21 日` → `2026-04-21`."""
    m = ROC_DATE_RE.search(s)
    if not m:
        return None
    y = _parse_num(m.group(1)) + 1911
    mo = _parse_num(m.group(2))
    d = _parse_num(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


# --- Scanner --------------------------------------------------------------
def scan(text: str) -> list[dict]:
    """Find every sentence / money / date in `text` and normalize it."""
    matches: list[dict] = []

    for m in SENTENCE_RE.finditer(text):
        raw = m.group(0)
        val = normalize_sentence(raw)
        if val is not None:
            matches.append({"kind": "sentence", "span": [m.start(), m.end()],
                            "raw": raw, "value": val})

    for m in MONEY_RE.finditer(text):
        raw = m.group(0)
        val = normalize_money(raw)
        if val is not None:
            matches.append({"kind": "money", "span": [m.start(), m.end()],
                            "raw": raw, "value": val})

    for m in ROC_DATE_RE.finditer(text):
        raw = m.group(0)
        val = normalize_roc_date(raw)
        if val is not None:
            matches.append({"kind": "date", "span": [m.start(), m.end()],
                            "raw": raw, "value": val})

    matches.sort(key=lambda x: x["span"][0])
    return matches


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 2 or argv[1] == "-":
        text = sys.stdin.read()
    else:
        with open(argv[1], "r", encoding="utf-8") as fh:
            text = fh.read()
    out = scan(text)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
