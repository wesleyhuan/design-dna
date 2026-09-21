# AGENTS.md — design-dna 專案本身

> 這份是**給開發這個工具的 agent 看的**。
> 使用者的設計風格規則不在這裡，在 `build/<profile>/AGENTS.md`（由 `dna/` 匯出）。

## 這是什麼

一個把「個人網頁設計習慣」記錄成可攜式 AI 知識庫的工具。核心概念是 LLM wiki：
每條規則是一個帶 frontmatter 的 Markdown 檔（一顆「基因」），彼此用 `[[wikilink]]` 相連，
整個 `dna/` 目錄是純文字，複製到任何專案、餵給任何 coding agent 都能用。

## 執行

```bash
python dna.py <command>          # 零安裝，直接跑
python -m design_dna <command>   # pip install -e . 之後等效
```

沒有測試框架。改動後至少跑一次：

```bash
python dna.py doctor
python dna.py export --profile demo
```

## 相依

**硬相依只有 `pyyaml`。** 這是刻意的 —— 工具的賣點是移植性，多一個相依就多一分裝不起來的機會。

選用相依（缺了要能優雅降級，不能爆炸）：

| 套件 | 用途 | 缺了會怎樣 |
| --- | --- | --- |
| `pillow` | 圖片取色 | 圖片來源回傳 `available: false` 並附說明 |
| `requests` | 抓網址 | 網址來源回傳抓取失敗 |
| `pymupdf` | PDF 文字 | 標記 `needs_agent_read`，交給 agent 用 Read 工具讀 |

**Web UI 一律用 stdlib `http.server`。** 不要引入 FastAPI / Flask / 任何前端建置工具。
前端是 vanilla JS，沒有 npm，沒有打包步驟。

## 架構

```
src/design_dna/
  taxonomy.py      基因分類法（14 個 category、強度、狀態）。schema 的單一來源。
  models.py        Gene / Profile / Source dataclass、slugify、wikilink 解析
  store.py         Workspace —— dna/ 目錄的讀寫，所有路徑計算收斂在這裡
  resolve.py       profile 繼承解析（子覆蓋父）、wiki 連結圖
  ingest/          確定性抽取，完全不呼叫 LLM
    code.py          CSS/HTML/JSX：色票、字級、間距、圓角、陰影、斷點、命名、技術棧
    image.py         PIL 量化取主色、明暗判斷
    web.py           抓 HTML + 外部 CSS，轉交 code.py
    document.py      md/txt 直讀、docx 用 zipfile 拆、pdf 交給 agent
  analyze.py       任務包產生、提案正規化、套用到 profile；可選的 Anthropic API 路徑
  exporters/       匯出器（index / full 兩種形態）
    agents_md.py     AGENTS.md + design-dna/ wiki 頁
    claude_md.py     agents_md 的超集，多一份 `@AGENTS.md` 匯入的 CLAUDE.md
  cli.py           argparse 介面
  web/server.py    stdlib HTTP 伺服器 + JSON API
  web/static/      單頁 UI
```

資料在 `dna/`（profiles / sources / inbox），產物在 `build/`。

## 改這個專案時要守的事

- **`dna/` 是使用者的資料。** 不要為了測試往裡面寫東西，測試用 scratchpad 或 `demo` profile。
- **加新的 category** 只改 `taxonomy.py`，其他地方都是從那裡讀的。
- **加新的匯出格式**（Cursor rules 等）：在 `exporters/` 加一個模組，
  提供 `render(resolved, mode, include_proposed)` 與 `export(resolved, out_dir, ...)`，
  登錄到 `exporters/__init__.py` 的 `EXPORTERS`。CLI 的 `--target` 會自動出現新選項；
  Web UI 的目標選單是寫死在 `index.html` 的，要記得一起加。
- **不要宣稱某個 agent 會讀 AGENTS.md，除非查證過。** Claude Code 就不讀（只讀 CLAUDE.md），
  README 曾經寫錯。
- **抽取器要保持確定性。** `ingest/` 底下不准出現 LLM 呼叫。詮釋是 `analyze.py` 之後的事。
- **提案一定要經過使用者確認才寫入 profile。** 不要加「自動採納」的預設行為。

## Windows 注意事項

開發環境是 Windows + Git Bash。

- 終端輸出中文需要 `PYTHONIOENCODING=utf-8`，CLI 已在 `_setup_stdout()` 處理。
- **不要用 bash heredoc 寫 Python 原始碼**：這個環境的 heredoc 會吃掉反斜線
  （`\\` 變成 `\`），正則表示式會被靜默改壞。用檔案編輯工具寫。
- Python 看不到 Git Bash 的 `/tmp`。臨時檔用真實路徑。

## 已知的取捨

- `slugify` 保留 CJK，所以中文標題會產生中文檔名。這是刻意的（可讀性 > 純 ASCII）。
- `slugify` 會把 Windows 保留裝置名（`con` `nul` `aux` `prn` `com0-9` `lpt0-9`）加上 `-x` 後綴，
  否則在 mac/Linux 建的 repo clone 到 Windows 會建不出檔案。`dna/sources/*/raw/` 的原件保留原檔名，
  不經過 slugify，所以這一層沒有防護。
- **可追溯性優先於 repo 大小**（使用者的明確決定）。ingest 預設把實際被分析的檔案
  複製進 `dna/sources/<id>/raw/` 並記錄 sha256；網址來源存 HTML/CSS 快照。
  原路徑只在當初那台機器有意義，`raw/` 才是跟著 repo 走的證據。不要把預設改回不留底。
- `.gitattributes` 對 `dna/sources/*/raw/**` 設 `-text`。證據原件必須逐位元組保留，
  否則 Windows clone 時被轉成 CRLF，sha256 會對不上。寫快照要用 `write_bytes`，理由相同。
- 有基因引用的來源不能直接刪（CLI 要 `--force`、API 回 409）。`doctor` 會檢查
  證據是否指向存在的來源、原件是否遺失或被改過。
- Web UI 只綁 `127.0.0.1`，且寫入請求檢查 Host 與 Origin。這個服務能讀寫本機檔案，
  不要為了方便把綁定位址開放出去。
