#!/usr/bin/env python3
"""review-todo-generator: prioritize a contradiction-check diff into a human-review TODO list.

CLI:
    python3 generate.py diff.json --case-id 115交簡478 [--sample-rate 0.1]
    python3 generate.py                                  # self-test

Library:
    from generate import generate_todos
    todos = generate_todos(diff_dict, case_id="CASE", sample_rate=0.1)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys

# Critical field buckets
P0_FIELDS = {
    "主文刑期月數",
    "罰金金額",
    "累犯",
    "沒收",
    "沒收物",
    "沒收金額",
    "緩刑",
    "緩刑期間",
    "易科罰金折算",
}

P1_FIELDS = {
    "被告姓名",
    "案號",
    "毒品種類",
    "毒品數量",
    "毒品重量",
    "交易金額",
    "犯罪日期",
    "前案號",
}

_MAX_REASON = 200


def _truncate(s: str, n: int = _MAX_REASON) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_value(v) -> str:
    if v is None:
        return "MISSING"
    return json.dumps(v, ensure_ascii=False)


def _priority_for(row: dict) -> str:
    field = row.get("field", "")
    flag = row.get("flag", "")
    if flag in ("mismatch", "only_rule", "only_llm") and field in P0_FIELDS:
        return "P0"
    if flag == "low_similarity" and field in P1_FIELDS:
        return "P1"
    return "P2"


def _reason_for(row: dict, priority: str) -> str:
    field = row.get("field", "")
    flag = row.get("flag", "")
    rv = _fmt_value(row.get("rule_value"))
    lv = _fmt_value(row.get("llm_value"))
    sim = row.get("similarity", 0.0)
    if priority == "P0":
        if flag == "only_rule":
            return _truncate(f"rule={rv} llm=MISSING, critical sentencing field")
        if flag == "only_llm":
            return _truncate(f"rule=MISSING llm={lv}, critical sentencing field")
        return _truncate(f"rule={rv} llm={lv}, critical sentencing field")
    if priority == "P1":
        return _truncate(
            f"rule={rv} llm={lv} similarity={sim}, key identity/quantity field"
        )
    # P2 non-sampled
    return _truncate(f"field='{field}' flag={flag} similarity={sim}")


def _seeded_rng(case_id: str) -> random.Random:
    h = hashlib.sha1(case_id.encode("utf-8")).digest()
    seed = int.from_bytes(h[:8], "big", signed=False)
    return random.Random(seed)


def generate_todos(diff: dict, case_id: str, sample_rate: float = 0.0) -> dict:
    if not isinstance(diff, dict) or "diffs" not in diff:
        raise TypeError("generate_todos() expects a contradiction-check diff dict")
    rows = diff.get("diffs", [])
    todos: list[dict] = []
    rng = _seeded_rng(case_id) if sample_rate > 0 else None
    sampled = 0

    for row in rows:
        flag = row.get("flag", "")
        if flag == "agree":
            # sampling path
            if rng is not None and rng.random() < sample_rate:
                todos.append({
                    "priority": "P2",
                    "field": row.get("field", ""),
                    "reason": "spot-check sampling",
                    "case_id": case_id,
                    "_sampled": True,
                })
                sampled += 1
            continue
        priority = _priority_for(row)
        todos.append({
            "priority": priority,
            "field": row.get("field", ""),
            "reason": _reason_for(row, priority),
            "case_id": case_id,
            "_sampled": False,
        })

    # Sort: P0 first, then P1, then P2; preserve stable order within each tier.
    tier_order = {"P0": 0, "P1": 1, "P2": 2}
    todos.sort(key=lambda t: tier_order.get(t["priority"], 9))

    # assign IDs and drop internal flag
    out: list[dict] = []
    for i, t in enumerate(todos, start=1):
        out.append({
            "id": f"todo-{i:03d}",
            "priority": t["priority"],
            "field": t["field"],
            "reason": t["reason"],
            "case_id": t["case_id"],
        })

    summary = {
        "total": len(out),
        "P0": sum(1 for t in out if t["priority"] == "P0"),
        "P1": sum(1 for t in out if t["priority"] == "P1"),
        "P2": sum(1 for t in out if t["priority"] == "P2"),
        "sampled": sampled,
    }
    return {"todos": out, "summary": summary}


def _self_test() -> dict:
    diff = {
        "diffs": [
            {"field": "主文刑期月數", "rule_value": 3, "llm_value": 4,
             "similarity": 0.0, "flag": "mismatch"},
            {"field": "被告姓名", "rule_value": "何建睿", "llm_value": "何建叡",
             "similarity": 0.5, "flag": "low_similarity"},
            {"field": "犯罪日期", "rule_value": "2026-03-17", "llm_value": "2026-03-17",
             "similarity": 1.0, "flag": "agree"},
            {"field": "扣案物", "rule_value": ["安非他命", "電子秤"],
             "llm_value": ["安非他命"], "similarity": 0.5, "flag": "low_similarity"},
            {"field": "累犯", "rule_value": True, "llm_value": False,
             "similarity": 0.0, "flag": "mismatch"},
            {"field": "沒收金額", "rule_value": 5000, "llm_value": None,
             "similarity": 0.0, "flag": "only_rule"},
        ],
        "summary": {"total": 6, "mismatches": 3, "jaccard_avg": 0.5},
    }
    return generate_todos(diff, case_id="115交簡478", sample_rate=0.5)


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        result = _self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Generate review TODOs from a contradiction-check diff.")
    parser.add_argument("diff_path", help="path to diff JSON")
    parser.add_argument("--case-id", required=True, help="case identifier")
    parser.add_argument("--sample-rate", type=float, default=0.0,
                        help="probability of sampling each 'agree' row (0..1)")
    args = parser.parse_args(argv[1:])

    with open(args.diff_path, "r", encoding="utf-8") as fh:
        diff = json.load(fh)
    result = generate_todos(diff, case_id=args.case_id, sample_rate=args.sample_rate)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
