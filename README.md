# 判決書文本探勘技能庫（judgment-skills）

> **Judgment Skills** — 供司法官學院「毒品判決書文本探勘系統」使用的 10 項 Claude Agent Skills，採 Anthropic Agent Skills 規格（[agentskills.io/specification](https://agentskills.io/specification)）。
>
> 每個技能皆為獨立資料夾（`SKILL.md` + `scripts/` + `references/` + `evals/`），可單獨載入、單獨測試，並以白名單方式匯入系統沙箱；整體符合 RFP 最低 10 項技能之要求（對應 RFP 第 IX 項「技能庫安全管控」與第 VI 項「品管流程」）。

---

## 一、專案總覽

- **目標**：把判決書從 PDF → 結構化 JSON/xlsx 的每一步驟，拆解為可稽核、可替換、可白名單的原子技能。
- **資料流**：

  ```
  PDF ─► pdf_to_text ─► doc-segmenter ─► { drug-sales-extract, legal-cite-detect }
                                     └──► pii-deid
                                     └──► sentence-normalize
         抽取結果 ─► cite-tracer（溯源）
                 ─► contradiction-check（規則 vs LLM）
                 ─► review-todo-generator（人工覆核排程）
                 ─► recidivism-check（累犯判定）
                 ─► export-tabular（xlsx / JSON 匯出）
  ```

- **開發規範**：SKILL.md 一律英文；本 README 與 `docs/` 繁體中文。

---

## 二、10 項技能一覽

| # | 資料夾                   | 版本     | 中文名稱                  | 角色            |
|---|--------------------------|----------|---------------------------|-----------------|
| 1 | `doc-segmenter`          | v0.1.0   | 判決書段落切分            | 前處理          |
| 2 | `drug-sales-extract`     | v0.1.0   | 毒品販賣欄位抽取          | 抽取            |
| 3 | `legal-cite-detect`      | v0.1.0   | 法條引用偵測              | 抽取            |
| 4 | `pii-deid`               | v0.1.0   | 個資去識別化              | 資安            |
| 5 | `sentence-normalize`     | v0.1.0   | 量刑規則正規化            | 正規化          |
| 6 | `cite-tracer`            | v0.1.0   | 段落引用追溯              | 稽核            |
| 7 | `contradiction-check`    | v0.1.0   | 矛盾檢核（規則 vs LLM）  | 品管            |
| 8 | `review-todo-generator`  | v0.1.0   | 人工覆核待辦產生          | 品管排程        |
| 9 | `export-tabular`         | v0.1.0   | xlsx / JSON 匯出          | 匯出            |
| 10| `recidivism-check`       | v0.1.0   | 累犯認定規則（刑法§47）   | 規則引擎        |

> 各技能的完整輸入／輸出、規則細節、參考資料，請見該資料夾的 `SKILL.md` 與 `references/*.md`。

---

## 三、目錄結構

```
judgment-skills/
├── README.md                       ← 本檔（繁體中文）
├── CHANGELOG.md
├── docs/
│   ├── PLAN.md                     ← 設計與範圍計畫
│   └── EVALUATION.md               ← 十項技能驗證報告
├── samples/
│   ├── judgment_sample_001.pdf     ← 範例判決
│   └── judgment_sample_001.txt     ← 預先擷取的文字
├── scripts/
│   └── pdf_to_text.py              ← 共用 PDF → 文字工具
├── evals/
│   ├── run_all.py                  ← 端到端驗證腳本
│   └── output/report.json          ← （執行後產生）
└── skills/
    ├── doc-segmenter/
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

每個技能資料夾固定為：

```
skills/<name>/
├── SKILL.md         ← 英文主文件（Anthropic Skills 規格）
├── scripts/         ← 可執行之 Python 3.11 stdlib 腳本
├── references/      ← 詳細規則、欄位字典、別名表
└── evals/smoke.txt  ← 單技能煙霧測試輸出
```

---

## 四、快速開始

### 1. 環境需求

- Python 3.11+
- 選用套件：`pdfplumber`（較佳 PDF 解析）、`pypdf`、`openpyxl`（xlsx 匯出）
- **不需要**任何外部網路、不連結第三方市集（對應 RFP 第 IX 項）

### 2. 執行端到端驗證

```bash
cd judgment-skills
python3 evals/run_all.py
```

預期輸出：

```
Skill                      Status  Detail
--------------------------------------------------------------------------------
doc-segmenter              PASS    7 sections
drug-sales-extract         PASS    defendant=何建睿, is_drug=False
legal-cite-detect          PASS    14 citations, 6/6 expected
pii-deid                   PASS    7 codes
sentence-normalize         PASS    20 matches, 3-month=True, 20000=True
cite-tracer                PASS    8 fields traced
contradiction-check        PASS    total=7, mismatches=3
review-todo-generator      PASS    5 todos, P0=3
export-tabular             PASS    wrote /tmp/export_test.json
recidivism-check           PASS    is_recidivist=True, priors=1

10/10 skills passed.
```

### 3. 單獨執行某一項技能

```bash
# 段落切分
python3 skills/doc-segmenter/scripts/segment.py samples/judgment_sample_001.txt | head -40

# 法條偵測
python3 skills/legal-cite-detect/scripts/detect.py samples/judgment_sample_001.txt

# 累犯判定（自動從文字推測犯罪日與前案）
python3 skills/recidivism-check/scripts/check_recidivism.py samples/judgment_sample_001.txt
```

---

## 五、資安與合規（對應 RFP 第 IX 項）

- **白名單匯入**：僅載入 `skills/` 目錄下已審查之技能；**不**連結 Awesome-Claude-Agents 等公開市集。
- **原始碼檢視**：所有技能皆為純 Python 3.11 stdlib 腳本（外加 `pdfplumber` / `pypdf` / `openpyxl`），可逐行人工審查。
- **SHA-256 雜湊校驗**：每次上線前對 `skills/<name>/` 產生 SHA-256，登錄於 `CHANGELOG.md`（後續 CI 工作項）。
- **沙箱隔離測試**：`evals/run_all.py` 皆在獨立子程序中執行，不開放網路。
- **個資保護**：`pii-deid` 作為匯出前的強制步驟；`export-tabular` 建議串接於 `pii-deid` 之後。

---

## 六、品管流程（對應 RFP 第 VI 項）

| RFP 要求           | 對應技能                                 |
|--------------------|------------------------------------------|
| 矛盾檢核           | `contradiction-check`                    |
| 人工覆核待辦產生   | `review-todo-generator`                  |
| 欄位來源溯源       | `cite-tracer`                            |
| 錯誤回報           | 由 `review-todo-generator` 的 `todos` 接續（後續 `error-report` 技能可追加） |
| 版本管理           | 每技能 `SKILL.md` 內 `version:` 欄位 + `CHANGELOG.md` |

---

## 七、開發流程（Git Flow）

```
main
 └── feature/scaffold          ← 骨架 + 三個批次技能（目前工作分支）
      ├── Batch A: doc-segmenter, drug-sales-extract, legal-cite-detect
      ├── Batch B: pii-deid, sentence-normalize, cite-tracer
      └── Batch C: contradiction-check, review-todo-generator, export-tabular, recidivism-check
```

新增技能：

1. 從 `main` 建立 `feature/<skill-name>`。
2. 新增 `skills/<skill-name>/SKILL.md`、`scripts/`、`references/`。
3. 更新 `evals/run_all.py` 加入該技能的驗證項。
4. 確認 `python3 evals/run_all.py` 全綠後開 PR。
5. 於 `CHANGELOG.md` 記載版本與 SHA-256。

---

## 八、授權

Proprietary — 僅供司法官學院「毒品判決書文本探勘系統」案內部使用。

---

## 九、參考資料

- Anthropic Agent Skills Specification — <https://agentskills.io/specification>
- The Complete Guide to Building Skills for Claude — <https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf>
- 專案原型 UI — `ui-prototype-adjust/ui-prototype-司法官判決系統/skills.html`
- 設計與範圍 — `docs/PLAN.md`
- 驗證報告 — `docs/EVALUATION.md`
