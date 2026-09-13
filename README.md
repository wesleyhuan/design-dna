# Design DNA 🧬

把你設計網頁的習慣與風格，記錄成一份**可攜式的 AI 知識庫**。
丟給任何 coding agent，它做出來的東西就會像你做的。

```
參考資料 ──▶ 確定性抽取 ──▶ AI 詮釋 ──▶ 你逐條確認 ──▶ wiki 知識庫 ──▶ AGENTS.md
 你之前的      色票/字級/間距      變成可執行      規則要經過        純文字，        任何 agent
 設計與程式    /斷點/命名慣例      的規則         本人點頭          可 git 管理      都讀得懂
```

## 為什麼不是一份提示詞就好

一份幾千字的提示詞，agent 每次都要整份讀進 context，而且改一條就要重寫整份。

這裡用的是 **LLM wiki** 的做法：每條規則是一個獨立的 Markdown 頁面，
彼此用 `[[wikilink]]` 相連。匯出的 `AGENTS.md` 只放硬性規則全文 + 其餘規則的一句話索引，
agent 需要細節時才去讀那一頁。省 context，也讓每條規則可以單獨修改、單獨追溯證據。

## 安裝

只需要 Python 3.10+ 與 `pyyaml`：

```bash
pip install pyyaml
```

想要圖片取色與網址抓取（建議）：

```bash
pip install pillow requests
```

PDF 文字抽取（可選，沒裝的話會交給 coding agent 自己讀）：

```bash
pip install pymupdf
```

不需要 `pip install` 這個專案本身 —— 直接 `python dna.py` 就能跑。

## 快速開始

```bash
python dna.py init                                    # 建立工作區（含 base 與 personal）
python dna.py ingest D:\projects\my-old-site --note "去年做的官網"
python dna.py analyze                                 # 產生 AI 分析任務包
```

`--profile` 沒寫時一律是 `personal`。要寫進共用基底必須明講 `--profile base`，
這樣忘了加參數時資料不會污染所有 profile 都會繼承的那一層。

最後一步會印出一句話，把它貼給你的 coding agent：

```
請讀取 "D:\...\dna\inbox\20260908-005048-personal.task.md" 並照裡面的指示完成分析。
```

agent 會讀完抽取出來的事實、打開需要親自看的圖與 PDF，然後寫回一份提案。接著：

```bash
python dna.py review 20260908-005048-personal   # 逐條確認（y/n/a/q）
python dna.py export                            # 產生 build/personal/AGENTS.md
python dna.py export --target claude            # 用 Claude Code 的話改用這個
```

把 `build/personal/` 整個資料夾複製到任何專案根目錄，就完成移植了。

### 或者用 Web UI

```bash
python dna.py web
```

瀏覽器會開 `http://127.0.0.1:8765`，可以瀏覽與編輯規則、看色票、加參考資料、
勾選提案、預覽匯出結果。

## 支援的參考資料

| 類型 | 例子 | 程式會抽出什麼 |
| --- | --- | --- |
| 前端原始碼 | 資料夾、`.css` `.scss` `.html` `.jsx` `.tsx` `.vue` | 色票出現次數、字級分佈、間距值域、圓角、陰影、轉場曲線、斷點、CSS 變數、class 命名慣例、技術棧 |
| 設計稿 / 截圖 | `.png` `.jpg` `.webp` | 量化主色票、各色佔比、整體明暗、版面比例 |
| 文件 | `.md` `.txt` `.docx` `.pdf` | 全文（PDF 沒裝 pymupdf 時交給 agent 讀） |
| 線上網址 | `https://example.com` | 抓 HTML 與外部 CSS，同前端原始碼分析 |

**這一層完全不呼叫 LLM。** 能量測的東西用程式算，AI 只負責詮釋，
所以就算你沒有 API key 也能用，而且 AI 拿到的是硬數據而不是含糊的印象。

## 可追溯性

每條規則的 `evidence` 都指向一份來源。為了讓這條鏈在任何一台機器上都查得回去：

- **原件留底**：ingest 預設把實際被分析的檔案複製到 `dna/sources/<id>/raw/`，
  並在 `source.yaml` 記下每個檔的 sha256。原路徑只在當初那台電腦有意義，`raw/` 才會跟著 repo 走。
- **網頁快照**：網址來源會存下當時抓到的 HTML 與 CSS。網站會改版，快照是唯一能回頭驗證的東西。
- **刪除保護**：有規則拿某份來源當證據時，直接刪會被擋下（CLI 需加 `--force`，Web UI 會再確認一次）。
- **健康檢查**：`python dna.py doctor` 會回報指向不存在來源的證據、遺失的原件、以及內容被改過的原件。

代價是 repo 會隨著參考資料變大，這是刻意的取捨。

> ⚠️ **原件會被 commit 並 push。** 如果 repo 是公開的，你 ingest 的客戶設計稿、
> 未公開的原始碼、內部規範文件都會跟著公開。機密素材請把 repo 設為 private，
> 或登錄時加 `--no-raw`（Web UI 勾「不留底原件」）—— 規則照樣產生，只是那份證據換機器後無法驗證。

## 知識庫長什麼樣

```
dna/
├─ profiles/
│  ├─ base/                    共用基底（跨專案都成立的習慣）
│  │  ├─ profile.yaml
│  │  └─ genes/
│  │     ├─ reduced-motion.md
│  │     └─ semantic-html-first.md
│  └─ personal/                繼承 base
│     ├─ profile.yaml
│     └─ genes/
│        ├─ core-color-palette.md
│        └─ type-scale.md
├─ sources/
│  └─ 20260913-144030-sample-site/
│     ├─ source.yaml           抽出的事實 + 原件 sha256
│     └─ raw/                  證據原件（跟著 repo 版控）
└─ inbox/                      待確認的 AI 提案
```

每個基因檔：

```markdown
---
id: spacing-rhythm
title: 8px 間距尺標
category: spacing
priority: must
status: confirmed
confidence: 0.85
tags: [間距, token]
related: [type-scale, design-token-first]
evidence:
  - source: 20260908-005028-my-old-site
    detail: 間距值集中在 8/16/24/32/48px，唯一例外是按鈕的 12px
updated: 2026-09-08
---

## Rule
所有 margin / padding / gap 只能取 `4, 8, 16, 24, 32, 48` px。

## Rationale
限制值域讓垂直節奏自動對齊，不同人（或不同 agent）寫出來的間距不會各憑感覺。

## Do
```css
.stack { display: flex; flex-direction: column; gap: 16px; }
```

## Avoid
```css
.card { padding: 20px; margin-bottom: 18px; }
```
```

純文字、可 `git diff`、可手改。**這就是資料庫本體**，工具只是在上面加操作介面。

## 多 Profile

```bash
python dna.py profile new client-acme --title "ACME 客戶" --extends base
```

判斷原則：**這條規則換一個客戶還成立嗎？** 成立就放 `base`，不成立就放子 profile。
子 profile 出現同 id 的基因會覆蓋父層的版本，匯出時自動合併。

## 匯出

```bash
python dna.py export --profile personal              # index 模式（預設）
python dna.py export --profile personal --mode full  # 全部攤平成單一檔
```

`index` 模式產生：

```
build/personal/
├─ AGENTS.md               MUST 規則全文 + 其餘規則的索引表
└─ design-dna/
   ├─ core-color-palette.md
   ├─ type-scale.md
   └─ ...                  每條規則一頁，[[連結]] 已轉成可點的相對連結
```

### 匯出目標

| `--target` | 產出 | 誰會自動讀 |
| --- | --- | --- |
| `agents`（預設） | `AGENTS.md` + `design-dna/` | Codex、Cursor、GitHub Copilot、Gemini CLI、Windsurf 等 |
| `claude` | 上面全部 + 只有一行 `@AGENTS.md` 的 `CLAUDE.md` | 上面全部 + **Claude Code** |

**Claude Code 不讀 `AGENTS.md`**，只讀 `CLAUDE.md`，所以要給它用請加 `--target claude`。
`CLAUDE.md` 只是匯入指令，規則內容仍只有 `AGENTS.md` 一份，不會兩邊不同步。
目標專案已經有自己的 `CLAUDE.md` 時不要覆蓋，把 `@AGENTS.md` 這一行加進去即可。

沒有檔案系統的平台（ChatGPT、Claude.ai Projects、v0 這類）跟不了 `index` 模式的相對連結，
改用 `--mode full` 產生單一檔再貼上或上傳。

要加 Cursor rules 等其他格式，在 `src/design_dna/exporters/` 加一個模組即可。

## 指令一覽

```bash
python dna.py init                          建立工作區
python dna.py profile list|new|show|rm      管理風格檔
python dna.py ingest <路徑或網址>            登錄參考資料
python dna.py sources [--remove <id>]       列出 / 刪除參考資料
python dna.py analyze --profile <p>         產生 AI 分析任務包
python dna.py proposals                     列出 AI 提案
python dna.py review [proposal_id]          逐條確認並寫入
python dna.py gene list|show|rm|status      檢視與編輯單條規則
python dna.py graph --profile <p>           wiki 連結圖
python dna.py doctor                        檢查斷連結、斷證據鏈、原件完整性
python dna.py export --profile <p>          匯出 AGENTS.md
python dna.py web                           本地 Web UI
```

## AI 分析的兩種模式

**agent 模式（預設，零成本）** — `analyze` 產生任務包，交給你已經在用的 coding agent
（Claude Code / Codex / Cursor）完成。專案內附 `.claude/skills/design-dna/SKILL.md`，
Claude Code 會自動知道該怎麼做。

**API 模式（可選）** — 設好 `ANTHROPIC_API_KEY` 後加 `--api`，直接呼叫 Anthropic API：

```bash
python dna.py analyze --profile personal --api
```

兩種模式產出的提案格式相同，都必須經過 `review` 才會寫入。

## 附的範例

`dna/profiles/demo/` 是一個跑完整條流程產出的範例 profile（11 條規則，含 wiki 連結），
證據指向 `dna/sources/20260913-144030-sample-site/`，原件就在 `raw/` 裡，可以實際對照
規則是從哪幾行 CSS 推出來的。不需要的話直接刪（先刪 profile，來源就不再被引用）：

```bash
python dna.py profile rm demo
```

```bash
python dna.py sources --remove 20260913-144030-sample-site
```

`docs/example-proposal.json` 是提案 JSON 的格式範例。
