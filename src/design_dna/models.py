"""資料模型。

刻意用 stdlib dataclass 而非 pydantic —— 這個專案的賣點是「複製走就能用」，
相依越少越好。所有模型都能來回轉成 dict/YAML。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

from .taxonomy import CATEGORY_KEYS, PRIORITIES, STATUSES

WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def split_sections(body: str) -> dict[str, str]:
    """把 gene body 依 `## 標題` 切成區塊。標題名稱不限，解析是通用的。

    `## Rule` 之前的文字會放在 key ""（前言）。
    """
    matches = list(SECTION_RE.finditer(body))
    if not matches:
        return {"": body.strip()} if body.strip() else {}
    out: dict[str, str] = {}
    preamble = body[: matches[0].start()].strip()
    if preamble:
        out[""] = preamble
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[m.group(1)] = body[m.end():end].strip()
    return out


def slugify(text: str) -> str:
    """把任意標題轉成安全的檔名 slug（保留 CJK，不粗暴丟掉中文）。"""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = text.replace(chr(92), "-")
    text = re.sub(r"[\s_/]+", "-", text)
    text = re.sub(r"[^\w\-一-鿿]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled"


def today() -> str:
    return date.today().isoformat()


@dataclass
class Evidence:
    """一條基因的證據出處。沒有證據的基因只是猜測。"""

    source: str = ""          # source id，對應 dna/sources/<id>/
    detail: str = ""          # 人話說明，例如「12 個 CSS 檔中出現 47 次」
    locator: str = ""         # 檔案路徑 / 選擇器 / 頁面區塊

    @classmethod
    def from_any(cls, raw: Any) -> "Evidence":
        if isinstance(raw, Evidence):
            return raw
        if isinstance(raw, str):
            return cls(detail=raw)
        if isinstance(raw, dict):
            return cls(
                source=str(raw.get("source", "")),
                detail=str(raw.get("detail", "")),
                locator=str(raw.get("locator", "")),
            )
        return cls(detail=str(raw))

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class Gene:
    """一顆設計基因 = 一個 wiki 節點 = 一個 .md 檔。"""

    id: str
    title: str
    category: str = "identity"
    priority: str = "should"
    status: str = "proposed"
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    updated: str = field(default_factory=today)
    body: str = ""
    # 執行期填入，不寫回檔案
    profile: str = ""
    inherited_from: str = ""

    def __post_init__(self) -> None:
        if self.category not in CATEGORY_KEYS:
            self.category = "identity"
        if self.priority not in PRIORITIES:
            self.priority = "should"
        if self.status not in STATUSES:
            self.status = "proposed"
        try:
            self.confidence = max(0.0, min(1.0, float(self.confidence)))
        except (TypeError, ValueError):
            self.confidence = 0.5
        self.evidence = [Evidence.from_any(e) for e in self.evidence]
        self.id = slugify(self.id or self.title)

    # -- wiki 連結 -------------------------------------------------------
    def links(self) -> list[str]:
        """body 內的 [[wikilink]] 加上 frontmatter 的 related，去重後回傳。"""
        found = [slugify(m) for m in WIKILINK_RE.findall(self.body)]
        out: list[str] = []
        for item in list(self.related) + found:
            s = slugify(item)
            if s and s != self.id and s not in out:
                out.append(s)
        return out

    # -- 序列化 ----------------------------------------------------------
    def frontmatter(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "updated": self.updated,
        }
        if self.tags:
            data["tags"] = self.tags
        if self.related:
            data["related"] = self.related
        if self.evidence:
            data["evidence"] = [e.to_dict() for e in self.evidence]
        return data

    def to_dict(self) -> dict[str, Any]:
        data = self.frontmatter()
        data["body"] = self.body
        data["profile"] = self.profile
        data["inherited_from"] = self.inherited_from
        data["links"] = self.links()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Gene":
        known = {
            "id", "title", "category", "priority", "status", "confidence",
            "tags", "evidence", "related", "updated", "body",
        }
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("id", data.get("title", "untitled"))
        kwargs.setdefault("title", kwargs["id"])
        for list_key in ("tags", "related"):
            val = kwargs.get(list_key)
            if isinstance(val, str):
                kwargs[list_key] = [v.strip() for v in val.split(",") if v.strip()]
            elif val is None:
                kwargs[list_key] = []
        ev = kwargs.get("evidence") or []
        if not isinstance(ev, list):
            ev = [ev]
        kwargs["evidence"] = ev
        kwargs["body"] = kwargs.get("body") or ""
        return cls(**kwargs)


@dataclass
class Profile:
    """一組風格檔，例如 personal / client-acme。可繼承其他 profile。"""

    id: str
    name: str = ""
    description: str = ""
    extends: list[str] = field(default_factory=list)
    created: str = field(default_factory=today)
    updated: str = field(default_factory=today)

    def __post_init__(self) -> None:
        self.id = slugify(self.id)
        self.name = self.name or self.id
        if isinstance(self.extends, str):
            self.extends = [self.extends]
        self.extends = [slugify(e) for e in self.extends if e]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "extends": self.extends,
            "created": self.created,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            id=data.get("id", "untitled"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            extends=data.get("extends") or [],
            created=data.get("created") or today(),
            updated=data.get("updated") or today(),
        )


@dataclass
class Source:
    """一份參考資料的登錄紀錄（原始檔留在 sources/<id>/raw/）。"""

    id: str
    kind: str = "unknown"        # code | image | document | web
    origin: str = ""             # 原始路徑或 URL
    profile: str = ""
    added: str = field(default_factory=today)
    note: str = ""
    files: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)   # 確定性抽取結果

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Source":
        return cls(
            id=data.get("id", "unknown"),
            kind=data.get("kind", "unknown"),
            origin=data.get("origin", ""),
            profile=data.get("profile", ""),
            added=data.get("added") or today(),
            note=data.get("note", ""),
            files=list(data.get("files") or []),
            facts=dict(data.get("facts") or {}),
        )
