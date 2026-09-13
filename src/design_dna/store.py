"""儲存層：把 dna/ 目錄當成資料庫來讀寫。

刻意不用 SQLite —— 純文字才能 git diff、才能整包丟給任何 agent 讀。
Workspace 是唯一的入口，所有路徑計算都收斂在這裡。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 相依缺失時給人話訊息
    raise SystemExit("缺少相依套件 PyYAML。請執行： pip install pyyaml") from exc

from .models import Gene, Profile, Source, slugify, today

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
BASE_PROFILE = "base"


# --------------------------------------------------------------------------
# frontmatter 讀寫
# --------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """回傳 (frontmatter dict, body)。沒有 frontmatter 就回傳空 dict。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text.strip()
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, m.group(2).strip()


def dump_frontmatter(data: dict[str, Any], body: str) -> str:
    head = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()
    return "---\n" + head + "\n---\n\n" + body.strip() + "\n"


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                       default_flow_style=False),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Workspace
# --------------------------------------------------------------------------

class Workspace:
    """一個 design DNA 工作區（root 底下有 dna/ 與 build/）。"""

    def __init__(self, root: Path | str = "."):
        self.root = Path(root).resolve()
        self.dna = self.root / "dna"
        self.build = self.root / "build"

    # -- 探測 ------------------------------------------------------------
    @classmethod
    def discover(cls, start: Path | str = ".") -> "Workspace":
        """從 start 往上找含有 dna/profiles 的目錄；找不到就用 start 本身。"""
        cur = Path(start).resolve()
        for candidate in [cur, *cur.parents]:
            if (candidate / "dna" / "profiles").is_dir():
                return cls(candidate)
        return cls(cur)

    @property
    def exists(self) -> bool:
        return (self.dna / "profiles").is_dir()

    def init(self) -> None:
        for sub in ("profiles", "sources", "inbox"):
            (self.dna / sub).mkdir(parents=True, exist_ok=True)
        self.build.mkdir(parents=True, exist_ok=True)
        if not (self.profile_dir(BASE_PROFILE) / "profile.yaml").exists():
            self.create_profile(
                BASE_PROFILE,
                name="共用基底",
                description="所有 profile 預設繼承的通用規則。放跨專案都成立的習慣。",
            )

    # -- 路徑 ------------------------------------------------------------
    def profile_dir(self, profile: str) -> Path:
        return self.dna / "profiles" / slugify(profile)

    def genes_dir(self, profile: str) -> Path:
        return self.profile_dir(profile) / "genes"

    def gene_path(self, profile: str, gene_id: str) -> Path:
        return self.genes_dir(profile) / (slugify(gene_id) + ".md")

    def source_dir(self, source_id: str) -> Path:
        return self.dna / "sources" / source_id

    @property
    def inbox_dir(self) -> Path:
        return self.dna / "inbox"

    # -- Profile ---------------------------------------------------------
    def list_profiles(self) -> list[Profile]:
        base = self.dna / "profiles"
        if not base.is_dir():
            return []
        out = []
        for d in sorted(base.iterdir()):
            if d.is_dir():
                p = self.get_profile(d.name)
                if p:
                    out.append(p)
        return out

    def get_profile(self, profile: str) -> Profile | None:
        pid = slugify(profile)
        path = self.profile_dir(pid) / "profile.yaml"
        if not path.exists():
            if self.profile_dir(pid).is_dir():
                return Profile(id=pid)
            return None
        data = read_yaml(path)
        data.setdefault("id", pid)
        return Profile.from_dict(data)

    def save_profile(self, profile: Profile) -> Profile:
        profile.updated = today()
        self.genes_dir(profile.id).mkdir(parents=True, exist_ok=True)
        write_yaml(self.profile_dir(profile.id) / "profile.yaml",
                   profile.to_dict())
        return profile

    def create_profile(self, profile_id: str, name: str = "",
                       description: str = "",
                       extends: Iterable[str] | None = None) -> Profile:
        pid = slugify(profile_id)
        if extends is None:
            extends = [] if pid == BASE_PROFILE else [BASE_PROFILE]
        prof = Profile(id=pid, name=name or pid, description=description,
                       extends=list(extends))
        return self.save_profile(prof)

    def delete_profile(self, profile: str) -> bool:
        d = self.profile_dir(profile)
        if not d.is_dir():
            return False
        shutil.rmtree(d)
        return True

    # -- Gene ------------------------------------------------------------
    def list_genes(self, profile: str) -> list[Gene]:
        d = self.genes_dir(profile)
        if not d.is_dir():
            return []
        genes = []
        for f in sorted(d.glob("*.md")):
            g = self._load_gene(f, slugify(profile))
            if g:
                genes.append(g)
        return genes

    def _load_gene(self, path: Path, profile: str) -> Gene | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        data, body = parse_frontmatter(raw)
        data.setdefault("id", path.stem)
        data.setdefault("title", path.stem)
        data["body"] = body
        gene = Gene.from_dict(data)
        gene.profile = profile
        return gene

    def get_gene(self, profile: str, gene_id: str) -> Gene | None:
        path = self.gene_path(profile, gene_id)
        if not path.exists():
            return None
        return self._load_gene(path, slugify(profile))

    def save_gene(self, profile: str, gene: Gene) -> Gene:
        gene.profile = slugify(profile)
        gene.updated = today()
        path = self.gene_path(profile, gene.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_frontmatter(gene.frontmatter(), gene.body),
                        encoding="utf-8")
        return gene

    def delete_gene(self, profile: str, gene_id: str) -> bool:
        path = self.gene_path(profile, gene_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    # -- Source ----------------------------------------------------------
    def list_sources(self) -> list[Source]:
        d = self.dna / "sources"
        if not d.is_dir():
            return []
        out = []
        for sub in sorted(d.iterdir(), reverse=True):
            data = read_yaml(sub / "source.yaml")
            if data:
                out.append(Source.from_dict(data))
        return out

    def get_source(self, source_id: str) -> Source | None:
        data = read_yaml(self.source_dir(source_id) / "source.yaml")
        return Source.from_dict(data) if data else None

    def save_source(self, source: Source) -> Source:
        write_yaml(self.source_dir(source.id) / "source.yaml", source.to_dict())
        return source

    def genes_citing(self, source_id: str) -> list[tuple[str, str]]:
        """哪些基因拿這份來源當證據。回傳 (profile, gene_id)。刪來源前必查。"""
        hits: list[tuple[str, str]] = []
        for prof in self.list_profiles():
            for gene in self.list_genes(prof.id):
                if any(e.source == source_id for e in gene.evidence):
                    hits.append((prof.id, gene.id))
        return hits

    def delete_source(self, source_id: str) -> bool:
        d = self.source_dir(source_id)
        if not d.is_dir():
            return False
        shutil.rmtree(d)
        return True

    # -- Inbox（AI 提案） -------------------------------------------------
    def list_proposals(self) -> list[dict[str, Any]]:
        if not self.inbox_dir.is_dir():
            return []
        out = []
        for f in sorted(self.inbox_dir.glob("*.proposal.json"), reverse=True):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        f = self.inbox_dir / (proposal_id + ".proposal.json")
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        pid = proposal.get("id") or "proposal"
        f = self.inbox_dir / (pid + ".proposal.json")
        f.write_text(json.dumps(proposal, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return proposal

    def delete_proposal(self, proposal_id: str) -> bool:
        removed = False
        for suffix in (".proposal.json", ".task.md"):
            f = self.inbox_dir / (proposal_id + suffix)
            if f.exists():
                f.unlink()
                removed = True
        return removed
