"""分析層：把確定性事實 → AI 提案 → 使用者確認 → 寫進 wiki。

兩條路都支援：
  agent 模式（預設，零成本）：產生一份任務包 dna/inbox/<id>.task.md，
      交給 Claude Code 之類的 coding agent 讀，agent 寫回 <id>.proposal.json。
  api 模式（可選）：偵測到 ANTHROPIC_API_KEY 就直接打 Messages API 產生提案。

不管走哪條，最後都必須經過使用者逐條確認才會寫入 profile。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Gene, slugify, today
from .resolve import resolve
from .store import DEFAULT_PROFILE, Workspace
from .taxonomy import CATEGORIES, PRIORITIES

DEFAULT_MODEL = "claude-opus-5"
API_URL = "https://api.anthropic.com/v1/messages"


# ---------------------------------------------------------------------------
# 任務包
# ---------------------------------------------------------------------------

def _taxonomy_block() -> str:
    rows = ["| category | 說明 |", "| --- | --- |"]
    rows += ["| `" + c.key + "` | " + c.label + " —— " + c.hint + " |"
             for c in CATEGORIES]
    return "\n".join(rows)


def _existing_block(ws: Workspace, profile: str) -> str:
    resolved = resolve(ws, profile, include_deprecated=True)
    if not resolved.genes:
        return "（這個 profile 目前還沒有任何基因，全部都是新的。）"
    rows = ["| id | 分類 | 標題 | 狀態 |", "| --- | --- | --- | --- |"]
    for g in resolved.genes:
        rows.append("| `" + g.id + "` | " + g.category + " | " + g.title
                    + " | " + g.status + " |")
    return "\n".join(rows)


def _facts_block(ws: Workspace, source_ids: list[str]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    manual: list[str] = []
    for sid in source_ids:
        src = ws.get_source(sid)
        if not src:
            continue
        raw_rel = "dna/sources/" + src.id + "/raw/"
        raw_list = ("- 留底原件（evidence.locator 請填這些路徑之一）：\n"
                    + "".join("  - `" + f + "`\n" for f in src.files[:60])
                    if src.files else "- 留底原件：無（這份證據換機器後無法驗證）\n")
        chunks.append("### 來源 `" + src.id + "`（" + src.kind + "）\n\n"
                      + "- 出處：" + (src.origin or "-") + "\n"
                      + "- 原件目錄：`" + raw_rel + "`\n"
                      + raw_list
                      + ("- 備註：" + src.note + "\n" if src.note else "")
                      + "\n```json\n"
                      + json.dumps(src.facts, ensure_ascii=False, indent=2)
                      + "\n```\n")
        raw_dir = ws.source_dir(src.id) / "raw"
        for rel in src.files:
            p = raw_dir / rel
            if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".webp",
                                    ".gif", ".bmp", ".tiff"}:
                manual.append(str(p))
        docs = (src.facts.get("documents") or {}).get("needs_agent_read") or []
        for name in docs:
            manual.append(str(raw_dir / name))
    return "\n".join(chunks), sorted(set(manual))


TASK_TEMPLATE = """# Design DNA 分析任務：{profile}

你是設計風格分析師。下面是從使用者提供的參考資料中，用程式**確定性抽取**出來的事實
（色票出現次數、字級分佈、間距、斷點、命名慣例、技術棧等）。

你的工作是把這些原始事實**詮釋成可執行的設計規則**，寫成一份提案 JSON。

## 你必須做的事

1. 讀完下面所有事實區塊。
2. 若「需要親自查看的檔案」有列出項目，用你的檔案讀取工具逐一打開來看
   （PDF 讀內容、圖片看畫面），把觀察到的風格也納入判斷。
3. 產出 {count} ~ {count_max} 條基因，寫進檔案：
   `{proposal_path}`
4. 完成後告訴使用者執行 `python -m design_dna review {proposal_id}` 逐條確認。

## 分類法（category 只能用這些）

{taxonomy}

其他欄位限制：
- `priority`：`must`（一定要遵守）/ `should`（建議）/ `may`（可選）
- `confidence`：0~1。證據越硬（出現次數多、跨多檔一致）越高；純推測給 0.4 以下。

## 這個 profile 已有的基因（不要重複造，該更新就沿用同一個 id）

{existing}

## 需要你親自查看的檔案

{manual}

## 抽取到的事實

{facts}

## 輸出格式

寫一個 JSON 檔到 `{proposal_path}`，結構如下：

```json
{{
  "id": "{proposal_id}",
  "profile": "{profile}",
  "sources": {sources_json},
  "created": "{created}",
  "status": "pending",
  "genes": [
    {{
      "id": "core-color-palette",
      "title": "核心色票",
      "category": "color",
      "priority": "must",
      "confidence": 0.9,
      "tags": ["色彩"],
      "related": ["semantic-color-roles"],
      "evidence": [
        {{"source": "{first_source}", "locator": "styles/tokens.css",
          "detail": "#2563EB 在 14 個檔案出現 47 次，定義在 --color-primary"}}
      ],
      "body": "## Rule\\n...\\n\\n## Rationale\\n...\\n\\n## Do\\n...\\n\\n## Avoid\\n...",
      "decision": "pending"
    }}
  ]
}}
```

### body 的寫法要求（這是最重要的部分）

- 用 `## Rule` / `## Rationale` / `## Do` / `## Avoid` 四段。
- **Rule 要具體到可以直接照做**：寫「主色 `#2563EB`，只用於主要 CTA 與連結」，
  不要寫「使用藍色系」。數值、色碼、單位都要寫死。
- **Rationale 說明為什麼**，包含你從資料看到的證據。
- **Do / Avoid 各給至少一個程式碼片段或具體例子。**
- 想連到別的基因就用 `[[gene-id]]`，這是 wiki 連結，會建立關聯圖。
- 全部用繁體中文書寫（程式碼與色碼除外）。

### 證據要能追溯

- `evidence.source` 必須是上面列出的來源 id，不能自己編。
- `evidence.locator` 填留底原件的相對路徑（可加選擇器，例如 `styles/components.css .card`），
  讓人之後能打開那個檔、找到那一行，驗證這條規則不是你想像出來的。
- 需要確認時，直接去原件目錄讀檔，不要只憑事實區塊的統計數字下結論。

### 特別注意

- 出現次數少、看起來像意外或第三方樣式殘留的值，不要當成使用者的風格。
- 如果事實彼此矛盾（例如同時有兩套字級尺標），誠實寫成一條 `antipattern`
  或降低 confidence 並在 Rationale 說明，不要硬掰一致性。
- 寧可少而準。每一條都要能回答「這條規則能讓下一個 agent 做出更像我的設計嗎？」
"""


def build_task(ws: Workspace, source_ids: list[str], profile: str = DEFAULT_PROFILE,
               count: int = 8, count_max: int = 16) -> dict[str, Any]:
    """產生任務包，回傳 {proposal_id, task_path, proposal_path}。"""
    proposal_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slugify(profile)
    facts, manual = _facts_block(ws, source_ids)
    if not facts:
        raise ValueError("沒有可用的來源。請先執行 ingest。")

    proposal_path = ws.inbox_dir / (proposal_id + ".proposal.json")
    manual_block = ("\n".join("- `" + m + "`" for m in manual)
                    if manual else "（無，事實區塊已足夠。）")

    text = TASK_TEMPLATE.format(
        profile=profile,
        count=count,
        count_max=count_max,
        taxonomy=_taxonomy_block(),
        existing=_existing_block(ws, profile),
        manual=manual_block,
        facts=facts,
        proposal_path=proposal_path.as_posix(),
        proposal_id=proposal_id,
        sources_json=json.dumps(source_ids, ensure_ascii=False),
        created=today(),
        first_source=source_ids[0] if source_ids else "",
    )

    ws.inbox_dir.mkdir(parents=True, exist_ok=True)
    task_path = ws.inbox_dir / (proposal_id + ".task.md")
    task_path.write_text(text, encoding="utf-8")
    return {
        "proposal_id": proposal_id,
        "task_path": str(task_path),
        "proposal_path": str(proposal_path),
        "manual_files": manual,
    }


# ---------------------------------------------------------------------------
# 可選：直接呼叫 Anthropic API
# ---------------------------------------------------------------------------

def api_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


def _extract_json(text: str) -> dict[str, Any]:
    m = JSON_BLOCK_RE.search(text)
    raw = m.group(1) if m else text
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型回應中找不到 JSON。")
    return json.loads(raw[start:end + 1])


def run_with_api(ws: Workspace, task_path: Path, model: str = DEFAULT_MODEL,
                 max_tokens: int = 8000) -> dict[str, Any]:
    """走 API 模式。需要 ANTHROPIC_API_KEY 與 requests。"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("沒有設定 ANTHROPIC_API_KEY，無法使用 API 模式。")
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("API 模式需要 requests：pip install requests") from exc

    prompt = Path(task_path).read_text(encoding="utf-8")
    prompt += ("\n\n---\n\n注意：你現在沒有檔案寫入工具。"
               "請直接把提案 JSON 輸出在回應中，包在 ```json 區塊裡即可。")

    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    resp.raise_for_status()
    payload = resp.json()
    text = "".join(b.get("text", "") for b in payload.get("content", []))
    proposal = _extract_json(text)
    return ws.save_proposal(normalize_proposal(proposal))


# ---------------------------------------------------------------------------
# 提案正規化與套用
# ---------------------------------------------------------------------------

def normalize_proposal(raw: dict[str, Any]) -> dict[str, Any]:
    genes = []
    for item in raw.get("genes") or []:
        if not isinstance(item, dict):
            continue
        g = dict(item)
        g["id"] = slugify(g.get("id") or g.get("title") or "untitled")
        g.setdefault("title", g["id"])
        if g.get("priority") not in PRIORITIES:
            g["priority"] = "should"
        g["decision"] = g.get("decision") or "pending"
        g["body"] = g.get("body") or ""
        genes.append(g)
    return {
        "id": raw.get("id") or datetime.now().strftime("%Y%m%d-%H%M%S"),
        "profile": slugify(raw.get("profile") or "base"),
        "sources": list(raw.get("sources") or []),
        "created": raw.get("created") or today(),
        "status": raw.get("status") or "pending",
        "genes": genes,
    }


def load_proposal(ws: Workspace, proposal_id: str) -> dict[str, Any]:
    data = ws.get_proposal(proposal_id)
    if data is None:
        raise FileNotFoundError("找不到提案：" + proposal_id)
    return normalize_proposal(data)


def apply_proposal(ws: Workspace, proposal_id: str,
                   accept: list[str] | None = None,
                   profile: str | None = None) -> dict[str, Any]:
    """把提案中被接受的基因寫進 profile（狀態設為 confirmed）。"""
    proposal = load_proposal(ws, proposal_id)
    target = slugify(profile or proposal["profile"])
    if ws.get_profile(target) is None:
        ws.create_profile(target)

    written, skipped = [], []
    for item in proposal["genes"]:
        gid = item["id"]
        decided = item.get("decision")
        wanted = (gid in accept) if accept is not None else (decided == "accept")
        if not wanted:
            skipped.append(gid)
            item["decision"] = "reject" if decided != "pending" else "pending"
            continue
        gene = Gene.from_dict({**item, "status": "confirmed"})
        ws.save_gene(target, gene)
        item["decision"] = "accept"
        written.append(gid)

    proposal["status"] = "applied" if written else proposal["status"]
    proposal["applied_at"] = today()
    ws.save_proposal(proposal)
    return {"profile": target, "written": written, "skipped": skipped}
