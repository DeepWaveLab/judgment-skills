#!/usr/bin/env python3
"""End-to-end smoke runner for all 10 judgment-skills.

Runs from repo root:
    cd judgment-skills && python3 evals/run_all.py

Produces evals/output/report.json and prints a concise pass/fail table.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SAMPLE_TXT = REPO / "samples" / "judgment_sample_001.txt"
OUT_DIR = REPO / "evals" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    return p.returncode, p.stdout, p.stderr


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def check(name: str, predicate: bool, detail: str = "") -> dict:
    status = "PASS" if predicate else "FAIL"
    return {"skill": name, "status": status, "detail": detail}


def as_json(stdout: str) -> Any:
    # Scripts print JSON as the last block; some also prefix with log lines.
    # Strategy: find first '{' or '[' and parse from there.
    for i, ch in enumerate(stdout):
        if ch in "{[":
            try:
                return json.loads(stdout[i:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON in stdout: {stdout[:120]}")


def main() -> int:
    results: list[dict] = []

    # 1) doc-segmenter
    rc, out, err = run(["python3", "skills/doc-segmenter/scripts/segment.py", str(SAMPLE_TXT)])
    data = as_json(out) if rc == 0 else None
    sections = data["sections"] if data else []
    ok = rc == 0 and len(sections) >= 5 and any(s["label"] == "主文" for s in sections)
    results.append(check("doc-segmenter", ok, f"{len(sections)} sections"))

    # 2) drug-sales-extract
    rc, out, _ = run(["python3", "skills/drug-sales-extract/scripts/extract.py", str(SAMPLE_TXT)])
    rec = as_json(out) if rc == 0 else {}
    ok = rc == 0 and rec.get("defendant") == "何建睿" and rec.get("sentence_months") == 3 and rec.get("fine_twd") == 20000 and rec.get("is_drug_sales_case") is False
    results.append(check("drug-sales-extract", ok, f"defendant={rec.get('defendant')}, is_drug={rec.get('is_drug_sales_case')}"))

    # 3) legal-cite-detect
    rc, out, _ = run(["python3", "skills/legal-cite-detect/scripts/detect.py", str(SAMPLE_TXT)])
    cites = as_json(out) if rc == 0 else []
    articles = {(c.get("statute"), c.get("article")) for c in cites}
    expected = {("中華民國刑法", "185-3"), ("中華民國刑法", "41"), ("中華民國刑法", "42"),
                ("刑事訴訟法", "449"), ("刑事訴訟法", "454"), ("刑法施行法", "1-1")}
    ok = rc == 0 and expected.issubset(articles)
    results.append(check("legal-cite-detect", ok, f"{len(cites)} citations, {len(articles & expected)}/{len(expected)} expected"))

    # 4) pii-deid
    rc, out, _ = run(["python3", "skills/pii-deid/scripts/deid.py", str(SAMPLE_TXT)])
    deid = as_json(out) if rc == 0 else {}
    code_map = deid.get("map", {})
    ok = rc == 0 and "何建睿" in code_map.values() and any(v == "林彥均" for v in code_map.values())
    results.append(check("pii-deid", ok, f"{len(code_map)} codes"))

    # 5) sentence-normalize
    rc, out, _ = run(["python3", "skills/sentence-normalize/scripts/normalize.py", str(SAMPLE_TXT)])
    norms = as_json(out) if rc == 0 else []
    found = {(m.get("kind"), json.dumps(m.get("value"), ensure_ascii=False)) for m in norms}
    has_3_months = any(m.get("kind") == "sentence" and m.get("value") == {"months": 3} for m in norms)
    has_20000 = any(m.get("kind") == "money" and m.get("value") == 20000 for m in norms)
    ok = rc == 0 and has_3_months and has_20000
    results.append(check("sentence-normalize", ok, f"{len(norms)} matches, 3-month={has_3_months}, 20000={has_20000}"))

    # 6) cite-tracer (self-test, no args)
    rc, out, _ = run(["python3", "skills/cite-tracer/scripts/trace.py"])
    trace = as_json(out) if rc == 0 else {}
    field_trace = trace.get("field_trace", [])
    ok = rc == 0 and len(field_trace) >= 3 and all(ft.get("source_paragraph_ids") for ft in field_trace)
    results.append(check("cite-tracer", ok, f"{len(field_trace)} fields traced"))

    # 7) contradiction-check (self-test)
    rc, out, _ = run(["python3", "skills/contradiction-check/scripts/check.py"])
    diff = as_json(out) if rc == 0 else {}
    ok = rc == 0 and diff.get("summary", {}).get("total", 0) > 0 and diff.get("diffs")
    results.append(check("contradiction-check", ok, f"total={diff.get('summary', {}).get('total')}, mismatches={diff.get('summary', {}).get('mismatches')}"))

    # 8) review-todo-generator (self-test)
    rc, out, _ = run(["python3", "skills/review-todo-generator/scripts/generate.py"])
    todo = as_json(out) if rc == 0 else {}
    todos = todo.get("todos", [])
    ok = rc == 0 and len(todos) >= 1 and any(t.get("priority") == "P0" for t in todos)
    results.append(check("review-todo-generator", ok, f"{len(todos)} todos, P0={sum(1 for t in todos if t.get('priority') == 'P0')}"))

    # 9) export-tabular (self-test writes to /tmp)
    rc, out, _ = run(["python3", "skills/export-tabular/scripts/export.py"])
    target = out.strip().splitlines()[-1].strip() if out.strip() else ""
    exists = Path(target).exists() if target else False
    ok = rc == 0 and exists
    results.append(check("export-tabular", ok, f"wrote {target}"))

    # 10) recidivism-check on sample text
    rc, out, _ = run(["python3", "skills/recidivism-check/scripts/check_recidivism.py", str(SAMPLE_TXT)])
    rec = as_json(out) if rc == 0 else {}
    ok = rc == 0 and rec.get("is_recidivist") is True and any("433" in (p.get("case_no") or "") for p in rec.get("matched_priors", []))
    results.append(check("recidivism-check", ok, f"is_recidivist={rec.get('is_recidivist')}, priors={len(rec.get('matched_priors', []))}"))

    # Summary table
    print(f"{'Skill':<26} {'Status':<6}  Detail")
    print("-" * 80)
    for r in results:
        print(f"{r['skill']:<26} {r['status']:<6}  {r['detail']}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{passed}/{len(results)} skills passed.")

    out_path = OUT_DIR / "report.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report written: {out_path}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
