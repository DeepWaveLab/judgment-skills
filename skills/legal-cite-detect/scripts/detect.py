#!/usr/bin/env python3
"""legal-cite-detect - detect Taiwan statute citations in Chinese text.

CLI:
    python3 skills/legal-cite-detect/scripts/detect.py <text-or-pdf>

Library:
    from detect import detect
    citations = detect(raw_text)           # -> list[dict]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Alias table - order matters, longest/most-specific names first so the regex
# alternation does not shadow compound names.
# ---------------------------------------------------------------------------
STATUTE_ALIASES: List[tuple[str, str]] = [
    ("中華民國刑法", "中華民國刑法"),
    ("刑法施行法", "刑法施行法"),
    ("刑事訴訟法", "刑事訴訟法"),
    ("毒品危害防制條例", "毒品危害防制條例"),
    ("毒危條例", "毒品危害防制條例"),
    ("道路交通管理處罰條例", "道路交通管理處罰條例"),
    ("道交條例", "道路交通管理處罰條例"),
    ("槍砲彈藥刀械管制條例", "槍砲彈藥刀械管制條例"),
    ("組織犯罪防制條例", "組織犯罪防制條例"),
    ("陸海空軍刑法", "陸海空軍刑法"),
    ("刑法", "中華民國刑法"),
    ("刑訴", "刑事訴訟法"),
]


# ---------------------------------------------------------------------------
# Chinese numeral handling (article/paragraph/item values).
# ---------------------------------------------------------------------------
_CN_DIGIT = {
    "零": 0, "〇": 0, "0": 0,
    "一": 1, "壹": 1, "二": 2, "貳": 2, "兩": 2,
    "三": 3, "參": 3, "叁": 3, "四": 4, "肆": 4,
    "五": 5, "伍": 5, "六": 6, "陸": 6,
    "七": 7, "柒": 7, "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}
_CN_UNIT = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}


def _chinese_to_int(s: str) -> Optional[int]:
    s = s.strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    total = 0
    current = 0
    for ch in s:
        if ch in _CN_DIGIT:
            current = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
        elif ch.isdigit():
            current = current * 10 + int(ch)
        else:
            return None
    return total + current


NUM = r"[0-9一二三四五六七八九十百千零〇壹貳參肆伍陸柒捌玖拾佰仟兩]+"

# Tail component: "第N項", "第N款", optionally followed by 前段/後段/本文/但書.
# `\s*` is allowed inside the modifier to tolerate PDF line-wraps like `前\n段`.
TAIL_COMPONENT = rf"\s*第\s*{NUM}\s*(?:項|款)(?:\s*(?:前\s*段|後\s*段|本\s*文|但\s*書))?"
# Full tail: one or more tail components, optionally separated by 、 or ,.
TAIL = rf"(?:{TAIL_COMPONENT}(?:\s*[、,]?{TAIL_COMPONENT})*)?"

STATUTE_GROUP = "|".join(re.escape(k) for k, _ in STATUTE_ALIASES)

# Full citation: statute + 第N條(之N)? + tail.
CITATION_RE = re.compile(
    rf"(?P<statute>{STATUTE_GROUP})\s*第\s*(?P<article>{NUM})\s*條"
    rf"(?:\s*之\s*(?P<sub>{NUM}))?"
    rf"(?P<tail>{TAIL})"
)

# Carry-over citation: a bare 第N條 that inherits the most recent statute.
CARRY_ARTICLE_RE = re.compile(
    rf"第\s*(?P<article>{NUM})\s*條"
    rf"(?:\s*之\s*(?P<sub>{NUM}))?"
    rf"(?P<tail>{TAIL})"
)

TAIL_PARA_ITEM_RE = re.compile(rf"第\s*({NUM})\s*(項|款)")


def _canonical(short: str) -> str:
    for k, v in STATUTE_ALIASES:
        if k == short:
            return v
    return short


def _format_article(article_raw: str, sub_raw: Optional[str]) -> Optional[str]:
    art = _chinese_to_int(article_raw)
    if art is None:
        return None
    if sub_raw:
        sub = _chinese_to_int(sub_raw)
        if sub is not None:
            return f"{art}-{sub}"
    return str(art)


def _expand_tail(tail: str) -> List[tuple[Optional[str], Optional[str]]]:
    """Return list of (paragraph, item) pairs from a citation tail.

    The tail may contain multiple 項/款 references separated by 、. If no
    項 is present we return [(None, None)] so the caller still emits one row.
    """
    pairs: List[tuple[Optional[str], Optional[str]]] = []
    current_para: Optional[str] = None
    current_item: Optional[str] = None
    saw_any = False
    for m in TAIL_PARA_ITEM_RE.finditer(tail):
        value_raw, kind = m.group(1), m.group(2)
        value = _chinese_to_int(value_raw)
        value_s = str(value) if value is not None else None
        if kind == "項":
            if saw_any:
                pairs.append((current_para, current_item))
            current_para = value_s
            current_item = None
            saw_any = True
        else:  # 款
            current_item = value_s
            saw_any = True
    if saw_any:
        pairs.append((current_para, current_item))
    else:
        pairs.append((None, None))
    return pairs


CARRY_GAP_RE = re.compile(r"^[\s、，及]*$")


def _emit(results: List[Dict], seen: set, row: Dict) -> None:
    key = (row["statute"], row["article"], row["paragraph"], row["item"], row["offset"])
    if key in seen:
        return
    seen.add(key)
    results.append(row)


_PAGE_FOOTER = re.compile(r"^\s*第[一二三四五六七八九十百零]+頁\s*$", re.MULTILINE)
_LINE_PAGE_NUM = re.compile(r"(?:\n|\A)\s*\d{1,3}\s+")


def _normalize_for_detect(text: str) -> str:
    """Strip page footers and leading per-line page-number markers.

    The detector still reports `offset` in the normalized text. Callers that
    need offsets in the original source should feed the same normalized text
    to all consumers.
    """
    text = _PAGE_FOOTER.sub("", text)
    # Remove `\n<digits> ` style markers pdfplumber leaves at the start of
    # every line (e.g. "\n01 "), but keep the newline so paragraph breaks
    # survive.
    text = re.sub(r"\n\s*\d{1,3}\s+", "\n", text)
    return text


def detect(text: str) -> List[Dict]:
    """Detect statutory citations and return a list of citation dicts.

    Supports carry-over citations (a bare `第N條` that inherits the previous
    statute) and multi-項 tails like `第1項前段、第3項`.
    """
    text = _normalize_for_detect(text)
    results: List[Dict] = []
    seen: set = set()

    # Collect primary matches and the spans they consume.
    primary: List[tuple[int, int, str]] = []  # (start, end, canonical_statute)
    for m in CITATION_RE.finditer(text):
        statute = _canonical(m.group("statute"))
        article = _format_article(m.group("article"), m.group("sub"))
        if article is None:
            continue
        tail = m.group("tail") or ""
        raw = m.group(0)
        for paragraph, item in _expand_tail(tail):
            _emit(
                results,
                seen,
                {
                    "statute": statute,
                    "article": article,
                    "paragraph": paragraph,
                    "item": item,
                    "raw": raw,
                    "offset": m.start(),
                },
            )
        primary.append((m.start(), m.end(), statute))

    # Carry-over pass. Walk carry-style matches and, for each one that does not
    # overlap a primary match, check if the gap back to any preceding citation
    # (primary or carry) is clean - only whitespace, 、, ，, or 及. If so, reuse
    # that citation's statute.
    cursor_spans: List[tuple[int, int, str]] = list(primary)
    for m in CARRY_ARTICLE_RE.finditer(text):
        if any(m.start() >= s and m.start() < e for s, e, _ in primary):
            continue
        # Find nearest preceding span.
        carrier: Optional[str] = None
        nearest_end = -1
        for s, e, canonical in cursor_spans:
            if e <= m.start() and e > nearest_end:
                gap = text[e : m.start()]
                if CARRY_GAP_RE.match(gap):
                    carrier = canonical
                    nearest_end = e
        if not carrier:
            continue
        article = _format_article(m.group("article"), m.group("sub"))
        if article is None:
            continue
        tail = m.group("tail") or ""
        for paragraph, item in _expand_tail(tail):
            _emit(
                results,
                seen,
                {
                    "statute": carrier,
                    "article": article,
                    "paragraph": paragraph,
                    "item": item,
                    "raw": m.group(0),
                    "offset": m.start(),
                },
            )
        cursor_spans.append((m.start(), m.end(), carrier))

    results.sort(key=lambda r: r["offset"])
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_input(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        sys.path.insert(0, str(scripts_dir))
        from pdf_to_text import pdf_to_text  # type: ignore

        return pdf_to_text(path)
    return path.read_text(encoding="utf-8")


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: detect.py <text-or-pdf>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1
    text = _load_input(path)
    citations = detect(text)
    print(json.dumps(citations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
