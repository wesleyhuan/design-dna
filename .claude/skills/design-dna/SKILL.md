---
name: design-dna
description: 分析使用者提供的設計參考資料（前端原始碼、設計稿圖片、規範文件、網址），把設計習慣與風格整理成 design-dna 知識庫的「基因」提案。當使用者說「分析我的設計風格」、「幫我建立設計 DNA」、「讀取 dna/inbox 的任務包」，或要求把某個專案 / 網站 / 設計稿的風格記錄下來時使用。
---

# Design DNA 分析

把「這個人設計網頁的習慣」變成一條條可執行的規則，存進可攜式的 wiki 知識庫。

## 這個系統怎麼運作

```
參考資料 ──ingest──▶ 確定性事實 ──analyze──▶ 任務包 ──你──▶ 提案 ──使用者確認──▶ 基因庫 ──export──▶ AGENTS.md
   (使用者給)         (程式算的，不燒 token)              (你做的詮釋)      (人把關)        (dna/)          (可移植)
```

**你的位置在「任務包 → 提案」這一段。** 前面的抽取是程式做的，後面的採納是使用者做的。
不要跳過任何一段自己腦補。

## 標準流程

### 1. 使用者給了新的參考資料

```bash
python dna.py ingest <路徑或網址> --profile <profile> --note "這是什麼"
```

支援資料夾、單一檔案（`.css .html .tsx .md .docx .pdf`）、圖片、網址。
程式會抽出色票、字級、間距、圓角、陰影、轉場、斷點、CSS 變數、命名慣例、技術棧。

### 2. 產生任務包

```bash
python dna.py analyze --profile <profile>
```

輸出 `dna/inbox/<id>.task.md`。

### 3. 你讀任務包並產出提案 ← 這是你的工作

讀 `dna/inbox/<id>.task.md`，照它裡面的規格，寫出 `dna/inbox/<id>.proposal.json`。

任務包裡若列了「需要你親自查看的檔案」（PDF、圖片），**一定要用 Read 工具逐一打開來看**。
程式抽不出「這張設計稿的氣質」，那是你的價值所在。

### 4. 交還給使用者確認

寫完提案後，告訴使用者：

```bash
python dna.py review <proposal_id>
```

或叫他們去 Web UI（`python dna.py web`）的「AI 提案」分頁勾選。
**不要自己執行 review --yes 幫使用者決定。** 這個系統的整個重點就是規則要經過本人點頭。

## 寫基因的品質標準

一條基因要能通過這個測試：**下一個 agent 只讀這條規則，能不能做出更像這位使用者的東西？**

| 不合格 | 合格 |
| --- | --- |
| 「使用藍色系」 | 「主色 `#2563EB`，只用於主要 CTA 與連結；hover 換 `#1D4ED8`」 |
| 「注意間距一致性」 | 「margin/padding/gap 只能取 4, 8, 16, 24, 32, 48px」 |
| 「排版要有層次」 | 「字級只用 14/16/24/32/48px 五階，字級越大行高越緊」 |

其他規則：

- `body` 用 `## Rule` / `## Rationale` / `## Do` / `## Avoid` 四段，Do 與 Avoid 各給實際程式碼。
- `evidence` 一定要填：`source` 是任務包列出的來源 id，`locator` 是 `raw/` 底下的檔案路徑
  （可加選擇器），`detail` 寫看到什麼數據。這條鏈要能讓人打開原件找到那一行。
- `confidence` 誠實給。跨多檔一致的給 0.8 以上；只出現一兩次的給 0.4 以下，並在 Rationale 說明這是推測。
- 用 `[[其他基因id]]` 互相連結。這些連結會構成 wiki 關聯圖，也會變成匯出時的可點連結。
- `priority` 只有真正不能違反的才給 `must`。整份都是 must 等於都不是 must。
- 寧可少而準。11 條紮實的規則勝過 30 條廢話。

## 常見判斷

**事實互相矛盾時**（例如出現兩套字級尺標）：不要硬掰一致性。誠實寫成一條 `antipattern`
（「專案裡混了兩套尺標，這是要修掉的」），或降低 confidence 並在 Rationale 說明。

**出現次數很少的值**：多半是第三方樣式殘留或一次性的例外，不要當成使用者的風格。
真的重要就寫進 Rationale 當作例外說明（例如「按鈕的 12px 是唯一允許的例外」）。

**已經有同 id 的基因**：任務包會列出現有基因。要更新就沿用同一個 id（會覆蓋），
不要造 `core-color-palette-v2` 這種東西。

**使用者只給了圖片**：先用 Read 看圖，描述你看到的版面結構、留白密度、對比強度、
字級層次、圓角與陰影的重量感，再對照程式抽出的色票資料，寫成基因。

## profile 的分層

`base` 放跨專案都成立的習慣（無障礙要求、命名慣例、技術棧偏好）。
`personal` / `client-xxx` 繼承 base，放該情境專屬的東西（品牌色、特定元件規格）。

判斷原則：**這條規則換一個客戶還成立嗎？** 成立就放 base，不成立就放子 profile。

## 其他指令

```bash
python dna.py profile list                # 有哪些風格檔
python dna.py gene list --profile <p>     # 某個 profile 的所有規則
python dna.py gene show <id> --profile <p>
python dna.py graph --profile <p>         # wiki 連結圖
python dna.py doctor                      # 檢查斷連結、缺證據、空內容
python dna.py export --profile <p>        # 產生 build/<p>/AGENTS.md
python dna.py web                         # 本地 UI
```

## 不要做的事

- 不要直接手寫 `dna/profiles/*/genes/*.md` 繞過提案流程 —— 除非使用者明確要求編輯某條既有規則。
- 不要幫使用者決定要採納哪些提案。
- 不要把 `build/` 底下的檔案當成資料來源改，那是產物，下次匯出會被蓋掉。
- 不要在沒有證據的情況下生成基因。抽不出東西就說抽不出來，並問使用者要不要多給一份參考。
