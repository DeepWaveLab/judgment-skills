# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/).

## [0.1.0] - 2026-04-23

### Added
- Initial 10 core skills (see `skills/`):
  - `doc-segmenter`, `drug-sales-extract`, `legal-cite-detect`
  - `pii-deid`, `sentence-normalize`, `cite-tracer`
  - `contradiction-check`, `review-todo-generator`, `export-tabular`, `recidivism-check`
- Shared PDF text extractor `scripts/pdf_to_text.py`
- End-to-end evaluation runner `evals/run_all.py`
- Sample judgment PDF under `samples/`
- Traditional Chinese README; English SKILL.md per skill
