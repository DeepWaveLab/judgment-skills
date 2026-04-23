#!/usr/bin/env python3
"""cite-tracer — attach paragraph IDs to extracted fields.

CLI:
    python3 skills/cite-tracer/scripts/trace.py input.json > output.json
    python3 skills/cite-tracer/scripts/trace.py            # self-test

Importable:
    from skills.cite_tracer.scripts.trace import trace
    trace(fields: dict, segmented: dict) -> dict
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

FUZZY_CUTOFF = 0.6
MAX_MATCHES = 3

# --- Chinese numeral rendering (for numeric field surface forms) ----------
_SMALL_CN = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
_SMALL_FORMAL = ["零", "壹", "貳", "參", "肆", "伍", "陸", "柒", "捌", "玖"]


def _int_to_small_cn(n: int, digits: list[str]) -> str:
    """Render integers 1..99 into '十'/'拾' form using the given digit list."""
    ten = "十" if digits is _SMALL_CN else "拾"
    if n < 10:
        return digits[n]
    if n < 20:
        return ten if n == 10 else ten + digits[n - 10]
    tens, ones = divmod(n, 10)
    out = digits[tens] + ten
    if ones:
        out += digits[ones]
    return out


def _stringify(value: Any) -> list[str]:
    """Turn a field value into candidate surface forms for matching."""
    if value is None:
        return []
    if isinstance(value, bool):
        return [str(value)]
    if isinstance(value, int):
        surfaces = [str(value)]
        if 0 < value < 100:
            surfaces.append(_int_to_small_cn(value, _SMALL_CN))
            surfaces.append(_int_to_small_cn(value, _SMALL_FORMAL))
            surfaces.append(surfaces[-1] + "月")
            surfaces.append(surfaces[-2] + "月")
            surfaces.append(f"{value}月")
            surfaces.append(f"{value} 月")
        # Money-ish surfaces.
        if value >= 1000:
            if value % 10000 == 0:
                wan = value // 10000
                surfaces.append(f"{wan}萬元")
                if 0 < wan < 100:
                    surfaces.append(_int_to_small_cn(wan, _SMALL_FORMAL) + "萬元")
            surfaces.append(f"{value:,}元")
            surfaces.append(f"{value}元")
        return [s for s in surfaces if s]
    if isinstance(value, float):
        return [str(value), f"{value:.2f}"]
    if isinstance(value, str):
        surfaces = [value]
        # ISO date → ROC surface forms.
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            roc_y = y - 1911
            surfaces.append(f"中華民國 {roc_y} 年 {mo} 月 {d} 日")
            surfaces.append(f"中華民國{roc_y}年{mo}月{d}日")
            surfaces.append(f"{roc_y} 年 {mo} 月 {d} 日")
            surfaces.append(f"{roc_y}年{mo}月{d}日")
        return surfaces
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            out.extend(_stringify(v))
        return out
    return [str(value)]


def _normalize(s: str) -> str:
    """Minimal whitespace normalization for matching."""
    return re.sub(r"\s+", "", s)


def _iter_paragraphs(segmented: dict) -> list[tuple[str, str]]:
    """Flatten segmented JSON into [(paragraph_id, text), ...]."""
    out: list[tuple[str, str]] = []
    for section in segmented.get("sections", []):
        for para in section.get("paragraphs", []):
            pid = para.get("id")
            text = para.get("text", "")
            if pid:
                out.append((pid, text))
    return out


def _score_paragraph(surfaces: Iterable[str], para_text: str) -> float:
    para_norm = _normalize(para_text)
    best = 0.0
    for surface in surfaces:
        if not surface:
            continue
        s_norm = _normalize(surface)
        if not s_norm:
            continue
        if s_norm in para_norm:
            return 1.0
        ratio = SequenceMatcher(None, s_norm, para_norm).ratio()
        # Substring-in-surface fallback: a short surface hidden inside a much
        # larger paragraph legitimately gets a low raw ratio; boost by taking
        # the ratio of surface against a sliding window of comparable length.
        if len(para_norm) > 2 * len(s_norm):
            window_ratio = 0.0
            step = max(1, len(s_norm) // 2)
            for i in range(0, len(para_norm) - len(s_norm) + 1, step):
                window = para_norm[i:i + len(s_norm)]
                r = SequenceMatcher(None, s_norm, window).ratio()
                if r > window_ratio:
                    window_ratio = r
            ratio = max(ratio, window_ratio)
        if ratio > best:
            best = ratio
    return best


def trace(fields: dict, segmented: dict) -> dict:
    """Attach source paragraph IDs to each extracted field."""
    paragraphs = _iter_paragraphs(segmented)
    field_trace: list[dict] = []

    for field_name, value in fields.items():
        surfaces = _stringify(value)
        scored: list[tuple[float, str]] = []
        for pid, text in paragraphs:
            score = _score_paragraph(surfaces, text)
            if score >= FUZZY_CUTOFF:
                scored.append((score, pid))
        scored.sort(key=lambda x: (-x[0], x[1]))
        top = scored[:MAX_MATCHES]

        if top:
            field_trace.append({
                "field": field_name,
                "value": value,
                "source_paragraph_ids": [pid for _, pid in top],
                "match_score": round(top[0][0], 4),
            })
        else:
            field_trace.append({
                "field": field_name,
                "value": value,
                "source_paragraph_ids": [],
                "match_score": 0.0,
            })

    return {"field_trace": field_trace}


# --- Self-test -----------------------------------------------------------
def _fake_segment(text: str) -> dict:
    """Split a text into pseudo-paragraphs for the self-test harness."""
    # Strip page markers and column numbers like the segmenter would.
    cleaned: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\d{1,2}\s*", "", line)
        if line.strip() == "" or line.startswith("第") and line.endswith("頁"):
            continue
        cleaned.append(line)
    joined = "\n".join(cleaned)

    # Split on Chinese ordinal bullets and headings.
    parts = re.split(r"(?=主\s*文|事實及理由|犯罪事實|證據|據上論斷|附錄|一、|二、|三、|四、)",
                     joined)
    parts = [p.strip() for p in parts if p.strip()]

    paragraphs = [{"id": f"p-{i+1:03d}", "text": p} for i, p in enumerate(parts)]
    return {"sections": [{"id": "sec-01", "label": "全文",
                          "paragraphs": paragraphs}]}


def _run_self_test() -> int:
    sample_path = (Path(__file__).resolve().parents[3]
                   / "samples" / "judgment_sample_001.txt")
    if not sample_path.exists():
        print(f"sample not found: {sample_path}", file=sys.stderr)
        return 2

    text = sample_path.read_text(encoding="utf-8")
    segmented = _fake_segment(text)
    fields = {
        "被告": "何建睿",
        "檢察官": "林彥均",
        "法官": "曾名阜",
        "主文刑期月數": 3,
        "罰金金額": 20000,
        "判決日期": "2026-04-21",
        "酒精濃度": "0.46毫克",
        "前案字號": "107年度湖交簡字第433號",
    }

    result = trace(fields, segmented)
    result["_self_test"] = {
        "paragraph_count": len(segmented["sections"][0]["paragraphs"]),
        "sample_path": str(sample_path.name),
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 2:
        return _run_self_test()

    path = argv[1]
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    fields = payload.get("fields", {})
    segmented = payload.get("segmented", {})
    result = trace(fields, segmented)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
