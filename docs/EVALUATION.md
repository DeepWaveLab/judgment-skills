# Evaluation Report

**Test fixture:** `samples/judgment_sample_001.pdf` (臺灣臺北地方法院 115 年度交簡字第 478 號 刑事簡易判決 — 公共危險 / 酒駕案)

**Runner:** `python3 evals/run_all.py` (from repo root)
**Reproducible:** see `evals/output/report.json` for machine-readable results

## Summary

| # | Skill                  | Status | Signal                                                                 |
|---|------------------------|--------|------------------------------------------------------------------------|
| 1 | doc-segmenter          | ✅ PASS | 7 sections detected, `主文` present                                   |
| 2 | drug-sales-extract     | ✅ PASS | `defendant=何建睿`, `sentence_months=3`, `fine_twd=20000`, `is_drug_sales_case=false` |
| 3 | legal-cite-detect      | ✅ PASS | 14 citations, all 6 expected articles found (刑法 §185-3/§41/§42, 刑訴 §449/§454, 刑法施行法 §1-1) |
| 4 | pii-deid               | ✅ PASS | 7 PII codes assigned (1 defendant, 4 officials, 1 plate, 1 address)   |
| 5 | sentence-normalize     | ✅ PASS | 20 matches incl. `有期徒刑參月→3 months` and `新臺幣貳萬元→20000`      |
| 6 | cite-tracer            | ✅ PASS | 8 fields traced with paragraph IDs (self-test)                         |
| 7 | contradiction-check    | ✅ PASS | 7-field diff with 3 mismatches (self-test)                             |
| 8 | review-todo-generator  | ✅ PASS | 5 todos emitted including 3 × P0 (self-test)                           |
| 9 | export-tabular         | ✅ PASS | wrote `/tmp/export_test.json` round-trip OK                            |
| 10| recidivism-check       | ✅ PASS | detected `107 年度湖交簡字第 433 號` prior → `is_recidivist=true`      |

**Result: 10 / 10 skills passed.**

## Methodology

- **Input surface:** all skills accept the shared pre-extracted `samples/judgment_sample_001.txt` (produced by `scripts/pdf_to_text.py`).
- **Stdlib-only runtime:** scripts run on Python 3.11 stdlib; `pdfplumber` / `pypdf` / `openpyxl` are optional.
- **Determinism:** section IDs, paragraph IDs, and PII codes are stable across reruns (spot-checked `doc-segmenter` double-run, identical output).
- **Self-tests:** skills that require paired inputs (`cite-tracer`, `contradiction-check`, `review-todo-generator`, `export-tabular`) ship with a built-in self-test that runs when invoked without arguments.

## Limitations & Known Gaps

1. **Sample is not a drug-sales case.** `drug-sales-extract` returns the full 28-field schema with `is_drug_sales_case=false` and nulls for drug-specific fields (交易次數 / 毒品重量 / 買方代號 …). Full coverage of drug-field rules requires drug-sales fixtures — scheduled for v0.2.
2. **§47 caveat.** `recidivism-check` cannot confirm "前案刑罰已執行完畢" from text alone; the caveat is surfaced in the output.
3. **Rule-based extraction is a fallback.** Production pipelines are expected to chain these skills with an LLM-based extractor. The rule fallback guarantees offline smoke testing and CI gating.
4. **Citation offsets** in `legal-cite-detect` refer to normalized text (page markers stripped). Downstream skills that need raw-text offsets must share the same normalization step.

## How to re-run

```bash
cd judgment-skills
python3 evals/run_all.py        # table + JSON report
cat evals/output/report.json    # machine-readable
```

Each skill can also be exercised in isolation:
```bash
python3 skills/doc-segmenter/scripts/segment.py samples/judgment_sample_001.txt | head -40
python3 skills/legal-cite-detect/scripts/detect.py samples/judgment_sample_001.txt
python3 skills/recidivism-check/scripts/check_recidivism.py samples/judgment_sample_001.txt
```

## Acceptance criteria (RFP §VI & §IX)

- [x] ≥ 10 skills under `skills/` — **10 delivered**
- [x] Each skill self-contained (SKILL.md + scripts + references)
- [x] Sandbox-safe: stdlib-only execution, no network, no third-party marketplaces
- [x] End-to-end verification against a real judgment PDF
- [x] Contradiction + review-todo pipeline demonstrates §VI "矛盾檢核 / 人工覆核待辦產生"
- [x] Cite-tracer provides the auditability guarantee in §VI
- [x] PII de-identification before any export (§IX 資安合規)
