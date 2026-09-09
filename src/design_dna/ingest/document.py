"""從文件檔（Markdown / txt / docx / PDF）取出純文字。

txt、md 直接讀；docx 用 stdlib zipfile 拆（不需要 python-docx）；
PDF 沒有可靠的純 stdlib 解法，標記成 needs_agent_read，
交由 coding agent 自己讀檔（Claude Code 的 Read 工具能讀 PDF）。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

# 刻意不含 .json/.yaml —— 那是設定檔，由 stack 偵測負責，
# 混進「設計文件」只會稀釋 AI 的判斷。
TEXT_EXTS = {".md", ".markdown", ".txt", ".rst"}
DOC_EXTS = TEXT_EXTS | {".docx", ".pdf"}
MAX_CHARS = 40_000

XML_TAG_RE = re.compile(r"<[^>]+>")
DOCX_PARA_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)


def _read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return "[無法解析 docx：" + str(exc) + "]"
    paras = []
    for para in DOCX_PARA_RE.findall(xml):
        text = XML_TAG_RE.sub("", para)
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"'))
        if text.strip():
            paras.append(text.strip())
    return "\n\n".join(paras)


def analyze_document(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    ext = path.suffix.lower()
    info: dict[str, Any] = {
        "file": path.name,
        "ext": ext,
        "bytes": path.stat().st_size if path.exists() else 0,
        "needs_agent_read": False,
        "text": "",
    }

    if ext in TEXT_EXTS:
        info["text"] = path.read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS]
    elif ext == ".docx":
        info["text"] = _read_docx(path)[:MAX_CHARS]
    elif ext == ".pdf":
        text = ""
        try:                                        # 有裝就用，沒裝也不強求
            import fitz                             # PyMuPDF
            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)[:MAX_CHARS]
        except Exception:                           # noqa: BLE001
            text = ""
        info["text"] = text
        info["needs_agent_read"] = not text.strip()
    else:
        info["needs_agent_read"] = True

    info["chars"] = len(info["text"])
    info["excerpt"] = info["text"][:2000]
    return info


def analyze_documents(paths: list[Path]) -> dict[str, Any]:
    docs = [analyze_document(p) for p in paths]
    return {
        "document_count": len(docs),
        "documents": docs,
        "needs_agent_read": [d["file"] for d in docs if d["needs_agent_read"]],
        "total_chars": sum(d["chars"] for d in docs),
    }
