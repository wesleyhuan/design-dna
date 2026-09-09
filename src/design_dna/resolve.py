"""Profile 繼承解析與 wiki 連結圖。

一個 profile 可以 extends 多個父 profile。解析規則：
  * 依 MRO 由遠而近展開（父在前、子在後）
  * 同 id 的基因，子覆蓋父，並記錄 overrides 來源
  * deprecated 的基因不進入匯出，但仍留在庫裡
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Gene
from .store import Workspace
from .taxonomy import category_order


@dataclass
class ResolvedProfile:
    profile_id: str
    name: str
    description: str
    chain: list[str] = field(default_factory=list)          # 由遠而近
    genes: list[Gene] = field(default_factory=list)         # 已解析、已排序
    overridden: dict[str, str] = field(default_factory=dict)  # gene_id -> 被誰蓋掉

    def by_category(self) -> dict[str, list[Gene]]:
        out: dict[str, list[Gene]] = {}
        for g in self.genes:
            out.setdefault(g.category, []).append(g)
        return out

    def confirmed(self) -> list[Gene]:
        return [g for g in self.genes if g.status == "confirmed"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "description": self.description,
            "chain": self.chain,
            "genes": [g.to_dict() for g in self.genes],
            "overridden": self.overridden,
        }


def inheritance_chain(ws: Workspace, profile_id: str,
                      _seen: set[str] | None = None) -> list[str]:
    """深度優先展開繼承鏈，回傳由遠而近的 profile id（含自己，結尾）。"""
    seen = _seen if _seen is not None else set()
    if profile_id in seen:
        return []          # 迴圈保護
    seen.add(profile_id)

    prof = ws.get_profile(profile_id)
    if prof is None:
        return []

    chain: list[str] = []
    for parent in prof.extends:
        for pid in inheritance_chain(ws, parent, seen):
            if pid not in chain:
                chain.append(pid)
    chain.append(profile_id)
    return chain


PRIORITY_RANK = {"must": 0, "should": 1, "may": 2}


def resolve(ws: Workspace, profile_id: str,
            include_deprecated: bool = False) -> ResolvedProfile:
    prof = ws.get_profile(profile_id)
    chain = inheritance_chain(ws, profile_id)

    merged: dict[str, Gene] = {}
    overridden: dict[str, str] = {}
    for pid in chain:                      # 由遠而近，後者覆蓋前者
        for gene in ws.list_genes(pid):
            if gene.id in merged:
                overridden[gene.id] = merged[gene.id].profile
            gene.inherited_from = pid if pid != profile_id else ""
            merged[gene.id] = gene

    genes = list(merged.values())
    if not include_deprecated:
        genes = [g for g in genes if g.status != "deprecated"]

    genes.sort(key=lambda g: (
        category_order(g.category),
        PRIORITY_RANK.get(g.priority, 9),
        -g.confidence,
        g.title,
    ))

    return ResolvedProfile(
        profile_id=profile_id,
        name=prof.name if prof else profile_id,
        description=prof.description if prof else "",
        chain=chain,
        genes=genes,
        overridden=overridden,
    )


def link_graph(resolved: ResolvedProfile) -> dict[str, Any]:
    """給 Web UI 畫 wiki 關聯圖用的 node/edge 結構。"""
    ids = {g.id for g in resolved.genes}
    nodes = [
        {
            "id": g.id,
            "title": g.title,
            "category": g.category,
            "status": g.status,
            "priority": g.priority,
            "inherited": bool(g.inherited_from),
        }
        for g in resolved.genes
    ]
    edges = []
    seen: set[tuple[str, str]] = set()
    for g in resolved.genes:
        for target in g.links():
            key = tuple(sorted((g.id, target)))
            if target in ids and key not in seen:
                seen.add(key)
                edges.append({"source": g.id, "target": target})
    dangling = sorted({
        t for g in resolved.genes for t in g.links() if t not in ids
    })
    return {"nodes": nodes, "edges": edges, "dangling": dangling}
