"""匯出成 AGENTS.md（跨 agent 通用標準）。

兩種形態：
  index（預設）— AGENTS.md 只放 MUST 規則全文 + 其餘規則的索引，
                 細節留在 design-dna/<gene>.md。這才是 LLM wiki 的用法：
                 主檔省 context，agent 需要細節時才去讀該頁。
  full        — 全部攤平在單一 AGENTS.md，適合不支援多檔參照的工具。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models import Gene, split_sections
from ..resolve import ResolvedProfile
from ..taxonomy import PRIORITY_WORD, category_label

WIKI_DIR = "design-dna"

HEADING_RE = re.compile(r"^(#{1,5})(\s+)", re.M)
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]*))?\]\]")
FENCE_RE = re.compile(r"^```", re.M)


def _demote(body: str, levels: int) -> str:
    """把 body 裡的標題降階，避免蓋過外層的基因標題。

    只處理程式碼區塊「之外」的行 —— CSS 註解與 shell 提示字元裡的 # 不能動。
    """
    if levels <= 0:
        return body
    out, in_fence = [], False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            line = HEADING_RE.sub(
                lambda m: "#" * min(6, len(m.group(1)) + levels) + m.group(2),
                line)
        out.append(line)
    return "\n".join(out)


def _linkify(body: str, prefix: str = "") -> str:
    """[[gene-id]] → [gene-id](prefix/gene-id.md)，人與 agent 都能跟著走。"""
    def sub(m: re.Match) -> str:
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        return "[" + label + "](" + prefix + target + ".md)"
    return WIKILINK_RE.sub(sub, body)


def _rule_text(gene: Gene) -> str:
    sections = split_sections(gene.body)
    for key in ("Rule", "規則", ""):
        if sections.get(key):
            return sections[key].strip()
    return gene.body.strip()


def _one_line(text: str, limit: int = 160) -> str:
    """壓成一行摘要，可安全放進 Markdown 表格。"""
    # 摘要裡塞程式碼片段沒有意義，先整段丟掉
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    flat = " ".join(text.split()).replace("|", r"\|")
    return flat if len(flat) <= limit else flat[:limit - 1] + "…"


def _gene_heading(gene: Gene) -> str:
    return ("### " + gene.title + "  `" + PRIORITY_WORD.get(gene.priority, "SHOULD")
            + "`")


def _gene_full(gene: Gene, link_target: bool = True) -> str:
    out = [_gene_heading(gene), ""]
    # 基因標題是 h3，body 的 h2 必須降到 h4 才不會蓋過它
    out.append(_linkify(_demote(gene.body.strip(), 2), WIKI_DIR + "/"))
    meta = ["id: `" + gene.id + "`"]
    if gene.inherited_from:
        meta.append("繼承自 `" + gene.inherited_from + "`")
    if gene.confidence < 0.6:
        meta.append("信心度 " + str(round(gene.confidence, 2)) + "（偏推測，可質疑）")
    if link_target:
        meta.append("詳見 `" + WIKI_DIR + "/" + gene.id + ".md`")
    out += ["", "<sub>" + " · ".join(meta) + "</sub>", ""]
    return "\n".join(out)


HEADER = """# AGENTS.md — {name} 的設計 DNA

> 這份檔案由 design-dna 從 `{profile}` profile 自動產生。
> **不要手動編輯**，改了下次匯出會被覆蓋。要改規則請改
> design-dna 工作區裡的 `dna/profiles/{profile}/genes/`，再重新匯出。

## 這份文件是什麼

這是這位使用者在設計網頁時的**個人風格與習慣**。當你被要求設計、實作或修改任何
使用者介面時，先讀完這裡的規則，再動手。

規則強度：
- `MUST` — 一定要照做。違反前必須先問過使用者。
- `SHOULD` — 預設照做。有充分理由才能偏離，並在回覆中說明。
- `MAY` — 使用者的偏好，同等條件下優先選這個。

{wiki_note}
"""

WIKI_NOTE_INDEX = """規則採漸進揭露：下面 `MUST` 規則寫在這裡，其餘規則只列標題與一句話摘要。
需要細節（理由、正例、反例、程式碼片段）時，去讀 `{wiki}/<id>.md`。
每頁裡的 `[[其他-id]]` 是 wiki 連結，指向同目錄下的另一頁。"""

WIKI_NOTE_FULL = """所有規則都完整寫在這一份檔案裡。"""


def render(resolved: ResolvedProfile, mode: str = "index",
           include_proposed: bool = False) -> str:
    genes = [g for g in resolved.genes
             if include_proposed or g.status == "confirmed"]

    parts = [HEADER.format(
        name=resolved.name or resolved.profile_id,
        profile=resolved.profile_id,
        wiki_note=(WIKI_NOTE_INDEX.format(wiki=WIKI_DIR) if mode == "index"
                   else WIKI_NOTE_FULL),
    )]

    if resolved.description:
        parts.append("## 這位使用者\n\n" + resolved.description.strip() + "\n")

    if not genes:
        parts.append("## （尚無已確認的規則）\n\n"
                     "這個 profile 還沒有任何 confirmed 的基因。"
                     "請先 ingest 參考資料並確認提案。\n")
        return "\n".join(parts)

    musts = [g for g in genes if g.priority == "must"]
    rest = [g for g in genes if g.priority != "must"]

    if mode == "full":
        by_cat: dict[str, list[Gene]] = {}
        for g in genes:
            by_cat.setdefault(g.category, []).append(g)
        for cat, items in by_cat.items():
            parts.append("## " + category_label(cat) + "\n")
            parts += [_gene_full(g, link_target=False) for g in items]
    else:
        if musts:
            parts.append("## 硬性規則（MUST）\n")
            parts += [_gene_full(g) for g in musts]
        if rest:
            parts.append("## 其他規則索引\n")
            parts.append("| 規則 | 強度 | 分類 | 一句話 | 細節 |")
            parts.append("| --- | --- | --- | --- | --- |")
            for g in rest:
                parts.append(
                    "| " + g.title
                    + " | `" + PRIORITY_WORD.get(g.priority, "SHOULD") + "`"
                    + " | " + category_label(g.category)
                    + " | " + _one_line(_rule_text(g), 90)
                    + " | [`" + g.id + ".md`](" + WIKI_DIR + "/" + g.id + ".md) |"
                )
            parts.append("")

    parts.append("## 使用方式\n")
    parts.append(
        "1. 開始任何 UI 工作前，先讀完上面的 `MUST` 規則。\n"
        "2. 遇到具體決策（選色、字級、間距、元件寫法）時，"
        "去索引找對應規則並讀該頁。\n"
        "3. 規則沒涵蓋到的，依照最接近的規則精神推論，並在回覆中說明你的推論。\n"
        "4. 若使用者的要求與規則衝突，以使用者當下的要求為準，"
        "但要主動指出衝突到哪一條。\n"
    )

    chain = " → ".join(resolved.chain) if resolved.chain else resolved.profile_id
    parts.append("---\n")
    parts.append("<sub>profile: `" + resolved.profile_id + "` · 繼承鏈: "
                 + chain + " · 規則數: " + str(len(genes))
                 + " · 由 design-dna 產生</sub>\n")
    return "\n".join(parts)


def render_wiki_page(gene: Gene) -> str:
    """單一基因頁（給 design-dna/<id>.md）。"""
    head = ["# " + gene.title, ""]
    meta = [
        "- **強度**：`" + PRIORITY_WORD.get(gene.priority, "SHOULD") + "`",
        "- **分類**：" + category_label(gene.category),
        "- **信心度**：" + str(round(gene.confidence, 2)),
    ]
    if gene.tags:
        meta.append("- **標籤**：" + ", ".join(gene.tags))
    if gene.inherited_from:
        meta.append("- **繼承自**：`" + gene.inherited_from + "`")
    if gene.evidence:
        meta.append("- **證據**：")
        for e in gene.evidence:
            where = " / ".join(filter(None, [e.source, e.locator]))
            meta.append("  - " + (e.detail or "（未說明）")
                        + ("（`" + where + "`）" if where else ""))
    links = gene.links()
    if links:
        meta.append("- **相關**：" + ", ".join(
            "[" + t + "](" + t + ".md)" for t in links))

    # 這裡是 wiki 目錄內部，連結不需要前綴
    body = _linkify(gene.body.strip())
    return "\n".join(head + meta + ["", "---", "", body, ""])


def export(resolved: ResolvedProfile, out_dir: Path, mode: str = "index",
           include_proposed: bool = False) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    text = render(resolved, mode=mode, include_proposed=include_proposed)
    main = out_dir / "AGENTS.md"
    main.write_text(text, encoding="utf-8")
    written = [str(main)]

    if mode == "index":
        wiki = out_dir / WIKI_DIR
        wiki.mkdir(parents=True, exist_ok=True)
        for old in wiki.glob("*.md"):
            old.unlink()
        for g in resolved.genes:
            if not include_proposed and g.status != "confirmed":
                continue
            page = wiki / (g.id + ".md")
            page.write_text(render_wiki_page(g), encoding="utf-8")
            written.append(str(page))

    return {"files": written, "count": len(written), "main": str(main)}
