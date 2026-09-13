"""匯出成 AGENTS.md + CLAUDE.md（給 Claude Code 用）。

Claude Code 不會自動讀 AGENTS.md，只讀 CLAUDE.md。與其維護兩份內容，
這裡照常產生 AGENTS.md 與 wiki 頁，再多寫一份只有匯入指令的 CLAUDE.md。
內容的單一來源仍是 AGENTS.md，其他 agent 照樣讀得到，這個目標是 agents 的超集。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..resolve import ResolvedProfile
from . import agents_md

# 說明文字裡刻意不寫 @ 開頭的路徑，Claude Code 會把它當成另一個匯入
SHIM = """# CLAUDE.md

> 由 design-dna 產生。Claude Code 不會自動讀 AGENTS.md，下面這行把它匯入。
> 目標專案如果已經有自己的 CLAUDE.md，不要整個覆蓋，把下面這行加進去即可。

@AGENTS.md
"""


def render(resolved: ResolvedProfile, mode: str = "index",
           include_proposed: bool = False) -> str:
    return ("<!-- ===== CLAUDE.md ===== -->\n\n" + SHIM
            + "\n<!-- ===== AGENTS.md ===== -->\n\n"
            + agents_md.render(resolved, mode=mode,
                               include_proposed=include_proposed))


def export(resolved: ResolvedProfile, out_dir: Path, mode: str = "index",
           include_proposed: bool = False) -> dict[str, Any]:
    result = agents_md.export(resolved, out_dir, mode=mode,
                              include_proposed=include_proposed)
    shim = Path(out_dir) / "CLAUDE.md"
    shim.write_text(SHIM, encoding="utf-8")
    files = [str(shim)] + result["files"]
    return {**result, "files": files, "count": len(files)}
