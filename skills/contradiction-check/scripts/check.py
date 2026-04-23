#!/usr/bin/env python3
"""contradiction-check: diff two flat field dicts (rule vs LLM).

CLI:
    python3 check.py rule.json llm.json
    python3 check.py                # self-test with built-in example

Library:
    from check import compare
    diff = compare(rule_dict, llm_dict)
"""
from __future__ import annotations

import json
import sys
from typing import Any

_PUNCT = set("，。、；：「」『』（）()[]{}.,;:!?\\-_/\\\t\n ")
_LOW_SIM_THRESHOLD = 0.8


def _is_missing(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _tokenize_string(s: str) -> set[str]:
    s = s.strip().lower()
    # strip punctuation
    cleaned = "".join(ch for ch in s if ch not in _PUNCT)
    if not cleaned:
        return set()
    # If contains ASCII word chars, split on whitespace/punct boundaries
    has_ascii = any(ch.isascii() and ch.isalnum() for ch in cleaned)
    if has_ascii:
        import re
        tokens = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", cleaned)
        return set(tokens) if tokens else {cleaned}
    # Fallback: each CJK grapheme is a token
    return set(cleaned)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _similarity(rule: Any, llm: Any) -> float:
    """Return similarity in [0.0, 1.0] given both sides are non-missing."""
    # both lists
    if isinstance(rule, list) and isinstance(llm, list):
        a = frozenset(str(x) for x in rule)
        b = frozenset(str(x) for x in llm)
        return _jaccard(set(a), set(b))
    # both strings
    if isinstance(rule, str) and isinstance(llm, str):
        return _jaccard(_tokenize_string(rule), _tokenize_string(llm))
    # matched scalar type (excluding bool edge: bool is subclass of int — treat equal as 1.0)
    if type(rule) is type(llm) and isinstance(rule, (int, float, bool)):
        return 1.0 if rule == llm else 0.0
    # mixed types — cast to string then Jaccard
    return _jaccard(_tokenize_string(str(rule)), _tokenize_string(str(llm)))


def _flag(rule_missing: bool, llm_missing: bool, rule: Any, llm: Any, sim: float) -> str:
    if rule_missing and not llm_missing:
        return "only_llm"
    if llm_missing and not rule_missing:
        return "only_rule"
    # both present
    if isinstance(rule, str) and isinstance(llm, str):
        if sim >= 1.0:
            return "agree"
        if sim <= 0.0:
            return "mismatch"
        return "low_similarity"
    if isinstance(rule, list) and isinstance(llm, list):
        if sim >= 1.0:
            return "agree"
        if sim <= 0.0:
            return "mismatch"
        return "low_similarity"
    # scalar / mixed
    if sim >= 1.0:
        return "agree"
    if sim <= 0.0:
        return "mismatch"
    return "low_similarity"


def compare(rule: dict, llm: dict) -> dict:
    """Compare two flat field dicts. Returns {'diffs': [...], 'summary': {...}}."""
    if not isinstance(rule, dict) or not isinstance(llm, dict):
        raise TypeError("compare() expects two dicts")

    keys = list(rule.keys()) + [k for k in llm.keys() if k not in rule]
    diffs: list[dict] = []

    for k in keys:
        rv = rule.get(k)
        lv = llm.get(k)
        rm = _is_missing(rv)
        lm = _is_missing(lv)
        if rm and lm:
            continue  # skip case A
        if rm or lm:
            sim = 0.0
        else:
            sim = _similarity(rv, lv)
        flag = _flag(rm, lm, rv, lv, sim)
        diffs.append({
            "field": k,
            "rule_value": rv,
            "llm_value": lv,
            "similarity": round(sim, 2),
            "flag": flag,
        })

    total = len(diffs)
    mismatches = sum(1 for d in diffs if d["flag"] in ("mismatch", "only_rule", "only_llm"))
    if total == 0:
        jaccard_avg = 1.0
    else:
        jaccard_avg = round(sum(d["similarity"] for d in diffs) / total, 2)

    return {
        "diffs": diffs,
        "summary": {
            "total": total,
            "mismatches": mismatches,
            "jaccard_avg": jaccard_avg,
        },
    }


def _self_test() -> dict:
    rule = {
        "主文刑期月數": 3,
        "被告姓名": "何建睿",
        "犯罪日期": "2026-03-17",
        "扣案物": ["安非他命", "電子秤"],
        "累犯": True,
        "罰金金額": 20000,
    }
    llm = {
        "主文刑期月數": 4,
        "被告姓名": "何建叡",
        "犯罪日期": "2026-03-17",
        "扣案物": ["安非他命"],
        "累犯": True,
        "沒收物": "電子秤",
    }
    return compare(rule, llm)


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        result = _self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if len(argv) != 3:
        print("usage: check.py <rule.json> <llm.json>", file=sys.stderr)
        return 2
    with open(argv[1], "r", encoding="utf-8") as fh:
        rule = json.load(fh)
    with open(argv[2], "r", encoding="utf-8") as fh:
        llm = json.load(fh)
    result = compare(rule, llm)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
