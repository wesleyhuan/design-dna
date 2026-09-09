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
python dna.py init                                    # 建立工作區
python dna.py profile new personal --title "我的風格"   # 建一個風格檔
python dna.py ingest D:\projects\my-old-site --profile personal --note "去年做的官網"
python dna.py analyze --profile personal              # 產生 AI 分析任務包
```

最後一步會印出一句話，把它貼給你的 coding agent：

```
請讀取 "D:\...\dna\inbox\20260908-005048-personal.task.md" 並照裡面的指示完成分析。
```

agent 會讀完抽取出來的事實、打開需要親自看的圖與 PDF，然後寫回一份提案。接著：

```bash
python dna.py review 20260908-005048-personal   # 逐條確認（y/n/a/q）
python dna.py export --profile personal         # 產生 build/personal/AGENTS.md
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
├─ sources/                    參考資料與抽出的事實
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

`AGENTS.md` 是跨 agent 的通用標準，Codex、Cursor、Copilot、Gemini CLI、Claude Code 都讀得懂。
要加 `CLAUDE.md` 或 Cursor rules 格式，在 `src/design_dna/exporters/` 加一個模組即可。

## 指令一覽

```bash
python dna.py init                          建立工作區
python dna.py profile list|new|show|rm      管理風格檔
python dna.py ingest <路徑或網址>            登錄參考資料
python dna.py sources                       列出參考資料
python dna.py analyze --profile <p>         產生 AI 分析任務包
python dna.py proposals                     列出 AI 提案
python dna.py review [proposal_id]          逐條確認並寫入
python dna.py gene list|show|rm|status      檢視與編輯單條規則
python dna.py graph --profile <p>           wiki 連結圖
python dna.py doctor                        檢查斷連結、缺證據、空內容
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
可以拿來看基因該怎麼寫。不需要的話直接刪：

```bash
python dna.py profile rm demo
```

`docs/example-proposal.json` 是提案 JSON 的格式範例。
