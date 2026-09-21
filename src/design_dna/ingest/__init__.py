"""Ingest 層：把一份參考資料變成一筆 Source + 一包確定性事實。

支援四種來源，可混合（一個資料夾裡同時有 code / 圖 / 文件也沒問題）：
    code      前端原始碼（.css .scss .html .jsx .tsx .vue .svelte …）
    image     設計稿與截圖
    document  .md .txt .docx .pdf
    web       線上網址

這一層完全不呼叫 LLM。產出的 facts 之後才交給 analyze 模組組成任務包。

可追溯性：預設把「實際被分析的檔案」複製進 sources/<id>/raw/ 並記下 sha256。
原路徑只在當初那台機器上有意義，raw/ 才是跟著 repo 走、換機器也查得到的證據原件。
網址來源則保存抓下來的 HTML 與 CSS 快照 —— 網站會改版，快照是唯一能回頭驗證的東西。
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Source, slugify
from ..store import DEFAULT_PROFILE, Workspace
from .code import CODE_EXTS, IGNORE_DIRS, analyze_code, collect_files
from .document import DOC_EXTS, analyze_documents
from .image import IMAGE_EXTS, analyze_images
from .web import fetch_site

MAX_COPY_BYTES = 20_000_000      # 單一來源最多複製 20MB 原始檔

# detect_stack 會讀的設定檔。技術棧的證據就在這些檔裡，所以也要留底
STACK_CONFIG_PATTERNS = (
    "package.json", "tailwind.config.*", "next.config.*", "vite.config.*",
    "svelte.config.*", "astro.config.*", "nuxt.config.*", "tsconfig.json",
)


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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _stack_configs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    for pattern in STACK_CONFIG_PATTERNS:
        found.extend(p for p in root.glob(pattern) if p.is_file())
    return found


def _copy_raw(files: list[Path], base: Path, dest: Path
              ) -> tuple[list[str], dict[str, str], list[str]]:
    """複製參考檔到 raw/。回傳 (相對路徑, sha256 對照, 因超出預算而略過的檔)。"""
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    checksums: dict[str, str] = {}
    skipped: list[str] = []
    budget = MAX_COPY_BYTES
    seen: set[str] = set()
    for f in files:
        try:
            rel = f.relative_to(base) if base.is_dir() else Path(f.name)
        except ValueError:
            rel = Path(f.name)
        key = rel.as_posix()
        if key in seen:
            continue
        seen.add(key)
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > budget:
            skipped.append(key)
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(f, target)
        except OSError:
            skipped.append(key)
            continue
        budget -= size
        copied.append(key)
        checksums[key] = sha256_file(target)
    return copied, checksums, skipped


def _write_snapshot(docs: list[tuple[str, str]], dest: Path
                    ) -> tuple[list[str], dict[str, str]]:
    """把網址抓到的 HTML / CSS 存成快照檔。"""
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    checksums: dict[str, str] = {}
    css_n = 0
    for name, text in docs:
        if "<style#" in name:
            continue                       # 內嵌 style 已經在 index.html 裡了
        if not copied:
            rel = "index.html"
        else:
            css_n += 1
            base = Path(urlparse(name).path).name or "style.css"
            if not base.endswith(".css"):
                base += ".css"
            rel = "css/" + str(css_n).zfill(2) + "-" + slugify(base[:-4])[:40] + ".css"
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # write_bytes 而非 write_text：Windows 的文字模式會把 \n 改成 \r\n，
        # 快照就不是對方伺服器回傳的原樣了
        target.write_bytes(text.encode("utf-8"))
        copied.append(rel)
        checksums[rel] = sha256_file(target)
    return copied, checksums


def ingest(ws: Workspace, target: str, profile: str = DEFAULT_PROFILE,
           note: str = "", keep_raw: bool = True) -> Source:
    """把 target（路徑或網址）登錄成一筆 Source 並抽取事實。"""
    if is_url(target):
        return _ingest_url(ws, target, profile, note, keep_raw)
    return _ingest_path(ws, Path(target), profile, note, keep_raw)


def _ingest_url(ws: Workspace, url: str, profile: str, note: str,
                keep_raw: bool) -> Source:
    site = fetch_site(url)
    host = urlparse(site.get("url") or url).netloc or url
    src = Source(
        id=new_source_id(host),
        kind="web",
        origin=site.get("url") or url,
        profile=slugify(profile),
        note=note,
    )
    if site.get("ok"):
        docs = site.pop("docs")
        facts = analyze_code(None, extra_texts=docs)
        facts["site"] = site
        if keep_raw:
            src.files, src.checksums = _write_snapshot(
                docs, ws.source_dir(src.id) / "raw")
            facts["site"]["snapshot_taken"] = datetime.now().isoformat(
                timespec="seconds")
    else:
        facts = site
    src.facts = {"web": facts}
    ws.save_source(src)
    return src


def _ingest_path(ws: Workspace, path: Path, profile: str, note: str,
                 keep_raw: bool) -> Source:
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

    src = Source(
        id=new_source_id(path.name),
        kind=kind,
        origin=str(path),
        profile=slugify(profile),
        note=note,
    )

    if keep_raw:
        if path.is_file():
            to_copy = [path]
            base = path.parent
        else:
            # 只留「真的被分析過」的檔：與 analyze_code / analyze_* 用同一套挑選規則，
            # 證據才對得上；node_modules 之類的雜物本來就被排除
            to_copy = (collect_files(path) + _stack_configs(path)
                       + buckets["image"][:24] + buckets["document"][:12])
            base = path
        src.files, src.checksums, skipped = _copy_raw(
            to_copy, base, ws.source_dir(src.id) / "raw")
        if skipped:
            facts["raw_skipped"] = {
                "reason": "超過單一來源 " + str(MAX_COPY_BYTES // 1_000_000)
                          + "MB 的留底上限",
                "files": skipped[:50],
            }

    src.facts = facts
    ws.save_source(src)
    return src


def verify_source(ws: Workspace, source: Source) -> list[str]:
    """檢查留底原件是否還在、內容是否跟當初一致。回傳問題清單。"""
    problems: list[str] = []
    raw = ws.source_dir(source.id) / "raw"
    for rel in source.files:
        p = raw / rel
        if not p.exists():
            problems.append("遺失 " + rel)
            continue
        expected = source.checksums.get(rel)
        if expected and sha256_file(p) != expected:
            problems.append("內容已變動 " + rel)
    return problems


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

    if source.files:
        label = "網頁快照" if source.kind == "web" else "留底原件"
        lines.append(label + " " + str(len(source.files)) + " 個（含 sha256）")
    else:
        lines.append("沒有留底原件 —— 換機器後無法回頭驗證這份證據")
    skipped = (source.facts.get("raw_skipped") or {}).get("files") or []
    if skipped:
        lines.append("超過留底上限而略過 " + str(len(skipped)) + " 個檔")
    return lines


__all__ = ["ingest", "summarize", "verify_source", "is_url", "collect_files"]
