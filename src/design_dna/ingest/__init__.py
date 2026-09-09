"""Ingest 層：把一份參考資料變成一筆 Source + 一包確定性事實。

支援四種來源，可混合（一個資料夾裡同時有 code / 圖 / 文件也沒問題）：
    code      前端原始碼（.css .scss .html .jsx .tsx .vue .svelte …）
    image     設計稿與截圖
    document  .md .txt .docx .pdf
    web       線上網址

這一層完全不呼叫 LLM。產出的 facts 之後才交給 analyze 模組組成任務包。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Source, slugify
from ..store import Workspace
from .code import CODE_EXTS, IGNORE_DIRS, analyze_code, collect_files
from .document import DOC_EXTS, analyze_documents
from .image import IMAGE_EXTS, analyze_images
from .web import analyze_url

MAX_COPY_BYTES = 20_000_000      # 單一來源最多複製 20MB 原始檔


def is_url(target: str) -> bool:
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https"):
        return True
    # 沒寫 scheme 但長得像網域，且本地不存在同名檔案
    return ("." in target and "/" not in target.split(".")[0]
            and not Path(target).exists()
            and bool(parsed.path) and " " not in target)


def new_source_id(label: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return stamp + "-" + (slugify(label)[:32] or "source")


def _classify(paths: list[Path]) -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = {"code": [], "image": [], "document": []}
    for p in paths:
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            buckets["image"].append(p)
        elif ext in CODE_EXTS:
            buckets["code"].append(p)
        elif ext in DOC_EXTS:
            buckets["document"].append(p)
    return buckets


def _walk(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in IGNORE_DIRS for part in p.parts):
            out.append(p)
    return out


def _copy_raw(files: list[Path], base: Path, dest: Path) -> list[str]:
    """複製參考檔到 sources/<id>/raw/，回傳相對路徑清單（超過預算就停）。"""
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    budget = MAX_COPY_BYTES
    for f in files:
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > budget:
            continue
        try:
            rel = f.relative_to(base) if base.is_dir() else Path(f.name)
        except ValueError:
            rel = Path(f.name)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(f, target)
        except OSError:
            continue
        budget -= size
        copied.append(rel.as_posix())
    return copied


def ingest(ws: Workspace, target: str, profile: str = "base",
           note: str = "", keep_raw: bool | None = None) -> Source:
    """把 target（路徑或網址）登錄成一筆 Source 並抽取事實。"""
    if is_url(target):
        return _ingest_url(ws, target, profile, note)
    return _ingest_path(ws, Path(target), profile, note, keep_raw)


def _ingest_url(ws: Workspace, url: str, profile: str, note: str) -> Source:
    facts = analyze_url(url)
    host = urlparse(url if "//" in url else "https://" + url).netloc or url
    src = Source(
        id=new_source_id(host),
        kind="web",
        origin=url,
        profile=slugify(profile),
        note=note,
        files=[],
        facts={"web": facts},
    )
    ws.save_source(src)
    return src


def _ingest_path(ws: Workspace, path: Path, profile: str, note: str,
                 keep_raw: bool | None) -> Source:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError("找不到來源：" + str(path))

    all_files = _walk(path)
    buckets = _classify(all_files)

    facts: dict[str, Any] = {}
    if buckets["code"] or path.is_dir():
        facts["code"] = analyze_code(path)
    if buckets["image"]:
        facts["images"] = analyze_images(buckets["image"][:24])
    if buckets["document"]:
        facts["documents"] = analyze_documents(buckets["document"][:12])

    kinds = [k for k, v in buckets.items() if v]
    kind = kinds[0] if len(kinds) == 1 else ("mixed" if kinds else "unknown")

    # 預設：圖與文件會留底（那是使用者的參考素材本體），
    # 整包原始碼專案不留底（太大，且原路徑仍在）。
    if keep_raw is None:
        keep_raw = bool(buckets["image"] or buckets["document"])

    src = Source(
        id=new_source_id(path.name),
        kind=kind,
        origin=str(path),
        profile=slugify(profile),
        note=note,
        files=[],
        facts=facts,
    )

    if keep_raw:
        to_copy = buckets["image"] + buckets["document"]
        if path.is_file():
            to_copy = [path]
        src.files = _copy_raw(to_copy, path if path.is_dir() else path.parent,
                              ws.source_dir(src.id) / "raw")

    ws.save_source(src)
    return src


def summarize(source: Source, limit: int = 6) -> list[str]:
    """給 CLI / UI 用的一行行摘要。"""
    lines: list[str] = []
    code = source.facts.get("code") or {}
    web = (source.facts.get("web") or {})
    stats = code or web

    if stats:
        if stats.get("scanned_files"):
            lines.append("掃描檔案 " + str(stats["scanned_files"]) + " 個")
        colors = stats.get("colors") or []
        if colors:
            lines.append("主要色彩 " + ", ".join(
                c["value"] for c in colors[:limit]))
        fams = stats.get("font_families") or []
        if fams:
            lines.append("字族 " + " / ".join(f["value"][:48] for f in fams[:2]))
        sizes = stats.get("font_sizes") or []
        if sizes:
            lines.append("字級 " + ", ".join(s["value"] for s in sizes[:limit]))
        space = stats.get("spacing_values") or []
        if space:
            lines.append("間距 " + ", ".join(s["value"] for s in space[:limit]))
        bps = stats.get("breakpoints") or []
        if bps:
            lines.append("斷點 " + ", ".join(b["value"] for b in bps[:4]))
        naming = (stats.get("naming") or {}).get("dominant")
        if naming:
            lines.append("命名慣例 " + naming)
        stack = (stats.get("stack") or {}).get("detected") or []
        if stack:
            lines.append("技術棧 " + ", ".join(stack))

    imgs = source.facts.get("images") or {}
    if imgs.get("image_count"):
        lines.append("圖片 " + str(imgs["image_count"]) + " 張，整體偏 "
                     + (imgs.get("dominant_mode") or "未知"))

    docs = source.facts.get("documents") or {}
    if docs.get("document_count"):
        lines.append("文件 " + str(docs["document_count"]) + " 份，共 "
                     + str(docs.get("total_chars", 0)) + " 字")
        if docs.get("needs_agent_read"):
            lines.append("需要 agent 自行讀取： "
                         + ", ".join(docs["needs_agent_read"]))
    return lines


__all__ = ["ingest", "summarize", "is_url", "collect_files"]
