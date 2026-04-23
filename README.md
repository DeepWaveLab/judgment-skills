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

## 四、安裝

本技能庫可用於 **(A) 本機開發／CI**、**(B) Claude Code 外掛市集**、**(C) Claude.ai 介面**、**(D) Claude API** 四種情境。實際部署至司法官學院內網時，建議走 (A) + 內網鏡像；(B)-(D) 僅供開發者本機測試。

### 情境 A：本機 / 內網開發（建議做法）

1. **取得原始碼**

   ```bash
   # 公開鏡像（開發用）
   git clone https://github.com/DeepWaveLab/judgment-skills.git
   cd judgment-skills

   # 或將整個資料夾（含 .git）以加密隨身碟方式送入內網鏡像
   ```

2. **建立虛擬環境並安裝相依套件**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -U pip
   pip install pdfplumber pypdf openpyxl
   ```

   > 核心技能只需 Python 3.11 stdlib；上述三個套件用於 PDF 解析與 xlsx 匯出。若內網無 PyPI，請以 `pip download` 於外網抓 wheel，再離線 `pip install --no-index --find-links ./wheels` 安裝。

3. **驗證安裝**

   ```bash
   python3 evals/run_all.py
   # 預期：10/10 skills passed.
   ```

### 情境 B：安裝至 Claude Code（Plugin 市集模式）

Claude Code 可將整個 repo 註冊為本地 plugin 市集，再選擇技能安裝：

```bash
# 於 Claude Code 互動介面中輸入：
/plugin marketplace add /path/to/judgment-skills
/plugin install judgment-skills@local        # 若已附 .claude-plugin/ 設定
```

若尚未附上 `.claude-plugin/marketplace.json`（v0.1.0 目前未附），可直接把想用的單一技能資料夾複製至 Claude Code 技能目錄：

```bash
# macOS / Linux
mkdir -p ~/.claude/skills
cp -R skills/doc-segmenter ~/.claude/skills/
cp -R skills/pii-deid      ~/.claude/skills/
# …重複複製所需技能
```

Claude Code 啟動後輸入 `/skills` 應可看到已匯入之技能；對話中提到 `doc-segmenter`、`pii-deid` 等名稱即會被呼叫。

### 情境 C：上傳至 Claude.ai（付費方案）

Claude.ai Pro / Team / Enterprise 支援使用者自備 Skill：

1. 於 repo 根目錄為每個技能打包：

   ```bash
   cd skills/doc-segmenter
   zip -r ../../dist/doc-segmenter.zip . -x "evals/*" "*.pyc"
   ```

2. 進入 Claude.ai → **設定 → Capabilities → Skills → Upload skill** → 上傳 `doc-segmenter.zip`。
3. 其他 9 個技能重複相同流程。

> 注意：上傳即代表資料會離開內網環境，司法官學院正式環境**不**建議走此路徑，只作為功能展示／demo 之用。

### 情境 D：透過 Claude API 使用

Claude API 的 Skills 支援讓程式化流程直接載入技能資料夾：

```python
import anthropic, pathlib

client = anthropic.Anthropic()

skill_dir = pathlib.Path("skills/doc-segmenter")
skill = client.skills.create(
    name="doc-segmenter",
    files=[str(p) for p in skill_dir.rglob("*") if p.is_file()],
)

msg = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    skills=[skill.id],
    messages=[{"role": "user", "content": "幫我用 doc-segmenter 切這份判決。"}],
)
print(msg.content)
```

API 使用說明詳見 Anthropic 官方文件：<https://docs.claude.com/en/api/skills-guide>

### 解除安裝 / 移除

- 情境 A：刪除 clone 下來的資料夾即可。
- 情境 B：`rm -rf ~/.claude/skills/<skill-name>`，或在 Claude Code 執行 `/plugin uninstall judgment-skills@local`。
- 情境 C：Claude.ai → Skills → 點該技能右側的 **Remove**。
- 情境 D：`client.skills.delete(skill.id)`。

---

## 五、快速開始

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

## 六、資安與合規（對應 RFP 第 IX 項）

- **白名單匯入**：僅載入 `skills/` 目錄下已審查之技能；**不**連結 Awesome-Claude-Agents 等公開市集。
- **原始碼檢視**：所有技能皆為純 Python 3.11 stdlib 腳本（外加 `pdfplumber` / `pypdf` / `openpyxl`），可逐行人工審查。
- **SHA-256 雜湊校驗**：每次上線前對 `skills/<name>/` 產生 SHA-256，登錄於 `CHANGELOG.md`（後續 CI 工作項）。
- **沙箱隔離測試**：`evals/run_all.py` 皆在獨立子程序中執行，不開放網路。
- **個資保護**：`pii-deid` 作為匯出前的強制步驟；`export-tabular` 建議串接於 `pii-deid` 之後。

---

## 七、品管流程（對應 RFP 第 VI 項）

| RFP 要求           | 對應技能                                 |
|--------------------|------------------------------------------|
| 矛盾檢核           | `contradiction-check`                    |
| 人工覆核待辦產生   | `review-todo-generator`                  |
| 欄位來源溯源       | `cite-tracer`                            |
| 錯誤回報           | 由 `review-todo-generator` 的 `todos` 接續（後續 `error-report` 技能可追加） |
| 版本管理           | 每技能 `SKILL.md` 內 `version:` 欄位 + `CHANGELOG.md` |

---

## 八、開發流程（Git Flow）

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

## 九、授權

Proprietary — 僅供司法官學院「毒品判決書文本探勘系統」案內部使用。

---

## 十、參考資料

- Anthropic Agent Skills Specification — <https://agentskills.io/specification>
- The Complete Guide to Building Skills for Claude — <https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf>
- 專案原型 UI — `ui-prototype-adjust/ui-prototype-司法官判決系統/skills.html`
- 設計與範圍 — `docs/PLAN.md`
- 驗證報告 — `docs/EVALUATION.md`
