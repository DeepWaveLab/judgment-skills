# Judgment Skills — Implementation Plan

> 中文：判決書文本探勘技能庫（10 個核心 Skill）實作計畫
> 對應 RFP：司法官學院「毒品判決書文本探勘系統」技能庫（第 IX 項）與品管流程（第 VI 項）
> UI 對照：`ui-prototype-adjust/ui-prototype-司法官判決系統/skills.html`

## 1. Purpose / 目的

Build a **production-ready skill library** that can be mounted into a Claude-powered judgment-mining pipeline. Each skill is a self-contained folder following Anthropic's Agent Skills spec (`SKILL.md` + optional `scripts/` + `references/`), is individually testable, and collectively satisfies the RFP's minimum "10 skill" requirement.

建立可直接裝載於判決書探勘管線的技能庫。每個技能為自含資料夾（SKILL.md + scripts + references），可單獨呼叫，整體滿足 RFP 10 項技能最低要求。

## 2. The 10 Skills

| # | Skill (folder)              | 中文名稱                 | 角色 | 主要輸入 → 輸出 |
|---|-----------------------------|--------------------------|------|-----------------|
| 1 | `doc-segmenter`             | 判決書段落切分           | Pre-processor | 判決書純文字 → 分段 JSON（主文／犯罪事實／證據／論罪科刑／據上論斷） |
| 2 | `drug-sales-extract`        | 毒品販賣欄位抽取         | Extractor | 分段 JSON → 28 欄結構化資料 |
| 3 | `legal-cite-detect`         | 法條引用偵測             | Extractor | 判決書純文字 → 法律條文清單（毒危條例／刑法／刑訴） |
| 4 | `pii-deid`                  | 個資去識別化             | Privacy | 判決書純文字 → 代號化文字 + 對應表 |
| 5 | `sentence-normalize`        | 量刑規則正規化           | Normalizer | 中文刑期字串 → 月數整數 |
| 6 | `cite-tracer`               | 段落引用追溯             | Audit | 欄位 + 分段 → 來源段落 ID 匹配 |
| 7 | `contradiction-check`       | 矛盾檢核（規則 vs LLM）  | QA | 規則輸出 + LLM 輸出 → 差異清單 |
| 8 | `review-todo-generator`     | 人工覆核待辦產生         | QA routing | 矛盾清單 + 信心分數 → 每日待辦 JSON |
| 9 | `export-tabular`            | xlsx / JSON 匯出         | Export | 結構化資料 → .xlsx / .json |
| 10| `recidivism-check`          | 累犯認定規則（刑法§47）  | Rule engine | 前案 + 本案 → 累犯判定 |

**Not included in the core 10** (will be scaffolded as optional / sandbox in future iterations): error-report, bm25-search, vector-rag, golden-eval, use-charge-extract, co-defendant-extract, timeline-reconstruct.

## 3. Folder Layout

```
judgment-skills/
├── README.md                  # 繁體中文總覽
├── CHANGELOG.md
├── docs/
│   ├── PLAN.md               # 本檔
│   └── EVALUATION.md         # 十項技能驗證結果
├── samples/
│   └── judgment_sample_001.pdf
├── scripts/
│   └── pdf_to_text.py        # 共用工具
├── evals/
│   └── run_all.py            # 端到端驗證腳本
└── skills/
    ├── doc-segmenter/
    │   ├── SKILL.md
    │   ├── scripts/segment.py
    │   └── references/field_dictionary.md
    ├── drug-sales-extract/
    ├── legal-cite-detect/
    ├── pii-deid/
    ├── sentence-normalize/
    ├── cite-tracer/
    ├── contradiction-check/
    ├── review-todo-generator/
    ├── export-tabular/
    └── recidivism-check/
```

## 4. SKILL.md Contract

Each `SKILL.md` follows the [Agent Skills spec](https://agentskills.io/specification):

```yaml
---
name: <kebab-case-name>
description: When Claude should invoke this skill (≤ 1024 chars, English).
version: <semver>
license: Proprietary
---
```

Body (English) MUST cover:
1. **Overview** — one paragraph, what & when.
2. **Inputs / Outputs** — typed schema (JSON / dataclass).
3. **Quick Start** — runnable snippet.
4. **Reference** — pointer to `references/` for long specs.
5. **Evaluation** — how to test (link to `evals/`).

## 5. Development Workflow

1. **git flow** — one feature branch per batch, squash-merge into `main`.
   - `feature/batch-a-extract` (doc-segmenter, drug-sales-extract, legal-cite-detect)
   - `feature/batch-b-normalize` (pii-deid, sentence-normalize, cite-tracer)
   - `feature/batch-c-qa-export` (contradiction-check, review-todo-generator, export-tabular, recidivism-check)
2. **Verification** — each batch closes with a run of `evals/run_all.py` on `samples/judgment_sample_001.pdf`.
3. **Review** — every SKILL.md peer-reviewable: name ≤ 64 chars, description clear, quick-start reproducible.
4. **Docs** — README 繁體中文；SKILL.md 一律英文。

## 6. Evaluation Strategy

For the attached sample (公共危險 / 酒駕簡易判決)：

| Skill | Success signal |
|-------|----------------|
| doc-segmenter | 5 known sections detected, each with ≥1 paragraph |
| drug-sales-extract | Returns structured record with null-safe defaults (this sample isn't drug-sales) |
| legal-cite-detect | Detects 刑法 §185-3, 刑訴 §449, §454, 刑法 §41, §42, 刑法施行法 §1-1 |
| pii-deid | Replaces 何建睿 / 林彥均 / 曾名阜 / 李璁穎 / 林宜薘 / 車牌 / 地址 |
| sentence-normalize | "有期徒刑參月" → 3 months; "貳萬元" → 20000 |
| cite-tracer | Every extracted field references a paragraph id |
| contradiction-check | Given fabricated LLM vs rule outputs, emits diff list |
| review-todo-generator | Produces a non-empty todo list from the diff |
| export-tabular | Writes xlsx + json; round-trip integrity |
| recidivism-check | Detects the 107 年度湖交簡字第 433 號 prior case reference |

## 7. Deliverables

- 10 skill folders under `skills/`
- `evals/REPORT.md` with pass/fail per skill
- `README.md` 繁體中文總覽（install / run / skill index）
- Git history following the batch structure above
