"""匯出器登錄表。

  agents — AGENTS.md（跨 agent 通用標準，Codex / Cursor / Copilot /
           Gemini CLI / Windsurf 等原生讀取）
  claude — agents 再加一份匯入 AGENTS.md 的 CLAUDE.md。Claude Code 只讀 CLAUDE.md。

要多加一種格式，只要寫一個模組提供 render() 與 export()，然後登錄到 EXPORTERS 就好。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..resolve import ResolvedProfile
from . import agents_md, claude_md

EXPORTERS: dict[str, Any] = {
    "agents": agents_md,
    "claude": claude_md,
}

DEFAULT_EXPORTER = "agents"


def available() -> list[str]:
    return sorted(EXPORTERS)


def export(resolved: ResolvedProfile, out_dir: Path,
           target: str = DEFAULT_EXPORTER, mode: str = "index",
           include_proposed: bool = False) -> dict[str, Any]:
    mod = EXPORTERS.get(target)
    if mod is None:
        raise ValueError("未知的匯出目標：" + target
                         + "（可用： " + ", ".join(available()) + "）")
    return mod.export(resolved, out_dir, mode=mode,
                      include_proposed=include_proposed)


def render(resolved: ResolvedProfile, target: str = DEFAULT_EXPORTER,
           mode: str = "index", include_proposed: bool = False) -> str:
    mod = EXPORTERS.get(target)
    if mod is None:
        raise ValueError("未知的匯出目標：" + target)
    return mod.render(resolved, mode=mode, include_proposed=include_proposed)
