#!/usr/bin/env python
"""跨 OS 煙霧測試：把整條 pipeline 在暫存工作區跑一遍。

    python scripts/smoke.py

CI 在 Windows / macOS / Linux 上各跑一次。這不是單元測試，是「整條流程在這台
機器上走得完嗎」的檢查，重點放在換 OS 才會壞的事：
  · 中文與保留字檔名建不建得出來
  · 檔案編碼與換行
  · repo 內建證據原件的 sha256 在 clone 之後還對不對（doctor 會查）

所有寫入都在暫存目錄，不會碰到 repo 的 dna/。
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DNA_PY = ROOT / "dna.py"


def tiny_png() -> bytes:
    """2x2 的 PNG：兩個主色藍、兩個深墨色。

    自己組 PNG 而不是內嵌 base64，是因為這支腳本在沒裝 pillow 的環境也要能跑，
    而寫死的 base64 一旦貼錯就會變成「圖片讀不出來」這種假失敗。
    """
    blue, ink = (0x25, 0x63, 0xEB), (0x0F, 0x17, 0x2A)
    raw = b""
    for row in ((blue, ink), (ink, blue)):
        raw += b"\x00" + bytes(v for px in row for v in px)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print("  [ok] " + label)
    else:
        print("  [FAIL] " + label + ((" — " + detail) if detail else ""))
        failures.append(label)


def run(*args: str, cwd: Path | None = None,
        expect: int = 0) -> subprocess.CompletedProcess:
    """跑一次 CLI。expect 是預期的 exit code。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, str(DNA_PY), *args],
        cwd=str(cwd or ROOT), env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    label = "dna.py " + " ".join(args[:3])
    if proc.returncode != expect:
        print("  [FAIL] " + label + " — exit " + str(proc.returncode)
              + "，預期 " + str(expect))
        print("    stdout: " + (proc.stdout or "").strip()[:2000])
        print("    stderr: " + (proc.stderr or "").strip()[:2000])
        failures.append(label)
    else:
        print("  [ok] " + label + " (exit " + str(proc.returncode) + ")")
    return proc


def make_fixtures(base: Path) -> Path:
    """造一份假的前端專案，數值刻意一致，讓抽取結果可預期。"""
    site = base / "fixture-site"
    (site / "styles").mkdir(parents=True)
    (site / "styles" / "tokens.css").write_text(
        ":root{\n--color-primary:#2563EB;\n--color-ink:#0F172A;\n"
        "--space-2:8px;\n--space-4:16px;\n--radius:8px;\n}\n",
        encoding="utf-8")
    (site / "styles" / "components.css").write_text(
        ".btn{background:#2563EB;padding:8px 16px;border-radius:8px;"
        "font-size:16px;transition:all .2s ease}\n"
        ".card{padding:24px;font-size:14px;box-shadow:0 1px 2px rgba(0,0,0,.06)}\n"
        "@media (min-width:768px){.card{padding:32px}}\n",
        encoding="utf-8")
    (site / "Hero.tsx").write_text(
        'export const Hero = () => <section className="hero card">'
        '<h1 style={{fontSize: "48px"}}>標題</h1></section>;\n',
        encoding="utf-8")
    (site / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0",
                                     "tailwindcss": "^3.4.0"}}),
        encoding="utf-8")
    (base / "spec.md").write_text(
        "# 設計規範\n\n間距一律 8 的倍數。主色 #2563EB。\n", encoding="utf-8")
    (base / "mock.png").write_bytes(tiny_png())
    return site


def write_proposal(path: Path, proposal_id: str, source_id: str) -> None:
    """模擬 agent 產出的提案。

    三條基因刻意測三種檔名：一般 ASCII、中文、Windows 保留裝置名。
    """
    def gene(gid: str, title: str, body: str, **kw) -> dict:
        return {
            "id": gid, "title": title, "category": kw.get("category", "color"),
            "priority": kw.get("priority", "should"), "confidence": 0.8,
            "tags": ["煙霧測試"], "related": kw.get("related", []),
            "evidence": [{"source": source_id,
                          "detail": "fixture 裡穩定出現",
                          "locator": "styles/tokens.css"}],
            "body": body, "decision": "accept",
        }

    proposal = {
        "id": proposal_id,
        "profile": "personal",
        "sources": [source_id],
        "genes": [
            gene("core-color-palette", "核心色票",
                 "## Rule\n主色 `#2563EB`。\n\n## Rationale\n單一強調色。\n"
                 "\n## Do\n```css\n.btn{background:#2563EB}\n```\n"
                 "\n## Avoid\n```css\n.btn{background:#3B82F6}\n```\n"
                 "間距見 [[間距節奏]]。",
                 priority="must", related=["間距節奏"]),
            gene("間距節奏", "8px 間距尺標",
                 "## Rule\n只取 8 的倍數。\n\n## Rationale\n垂直節奏自動對齊。\n"
                 "\n## Do\n```css\n.stack{gap:16px}\n```\n"
                 "\n## Avoid\n```css\n.stack{gap:18px}\n```\n",
                 category="spacing"),
            # con 是 Windows 保留裝置名，slugify 應該轉成 con-x
            gene("con", "容器寬度", "## Rule\n內容最大寬 1200px。\n",
                 category="layout"),
        ],
    }
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def main() -> int:
    print("design-dna 煙霧測試")
    print("  python   : " + sys.version.split()[0])
    print("  platform : " + sys.platform)
    print("  repo     : " + str(ROOT))

    sys.path.insert(0, str(ROOT / "src"))
    from design_dna.models import slugify            # noqa: E402

    print("\n[1] slugify 跨 OS 檔名規則")
    check("Windows 保留字加後綴", slugify("CON") == "con-x", slugify("CON"))
    check("保留字判斷不誤殺", slugify("console") == "console")
    check("CJK 保留", slugify("間距節奏") == "間距節奏")
    check("slugify 可重複套用", slugify(slugify("NUL")) == slugify("NUL"))

    print("\n[2] repo 自身的知識庫（驗 .gitattributes 與證據 sha256）")
    run("doctor")
    out = Path(tempfile.mkdtemp(prefix="dna-build-"))
    run("export", "--profile", "demo", "--out", str(out))
    check("demo 匯出有 AGENTS.md", (out / "AGENTS.md").is_file())
    shutil.rmtree(out, ignore_errors=True)

    work = Path(tempfile.mkdtemp(prefix="dna-smoke-"))
    try:
        print("\n[3] 建立工作區")
        run("--root", str(work), "init")
        check("base profile 建好", (work / "dna" / "profiles" / "base"
                                    / "profile.yaml").is_file())
        check("預設 profile personal 建好",
              (work / "dna" / "profiles" / "personal" / "profile.yaml").is_file())

        print("\n[4] ingest（程式碼 / 文件 / 圖片）")
        site = make_fixtures(work / "fixtures")
        run("--root", str(work), "ingest", str(site), "--note", "假前端專案")
        run("--root", str(work), "ingest",
            str(work / "fixtures" / "spec.md"), "--note", "規範文件")
        run("--root", str(work), "ingest",
            str(work / "fixtures" / "mock.png"), "--note", "設計稿")

        sources = sorted((work / "dna" / "sources").iterdir())
        check("登錄了 3 份來源", len(sources) == 3, str(len(sources)))
        code_src = next((d for d in sources
                         if (d / "source.yaml").read_text(encoding="utf-8")
                         .find("kind: code") >= 0), None)
        check("程式碼來源存在", code_src is not None)
        if code_src is None:
            return 1
        facts = (code_src / "source.yaml").read_text(encoding="utf-8")
        check("抽到主色 #2563EB", "2563EB" in facts.upper())
        check("抽到技術棧 tailwind", "tailwind" in facts.lower())
        check("留底原件在 raw/", (code_src / "raw").is_dir()
              and any((code_src / "raw").rglob("*.css")))

        # 選用相依在不在，結果應該不同，但兩種都不能讓流程壞掉
        image_src = next((d for d in sources
                          if "kind: image" in (d / "source.yaml")
                          .read_text(encoding="utf-8")), None)
        check("圖片來源存在", image_src is not None)
        if image_src is not None:
            img_facts = (image_src / "source.yaml").read_text(encoding="utf-8")
            try:
                import PIL                          # noqa: F401
                check("有 pillow：圖片抽到色票", "hex:" in img_facts)
            except ImportError:
                check("沒 pillow：圖片來源優雅降級",
                      "available: false" in img_facts.lower()
                      and "pillow" in img_facts.lower())

        print("\n[5] 打錯 profile 名稱要擋下")
        run("--root", str(work), "ingest", str(site),
            "--profile", "persnal", expect=1)

        print("\n[6] analyze → 提案 → review")
        proc = run("--root", str(work), "analyze", "--profile", "personal")
        tasks = list((work / "dna" / "inbox").glob("*.task.md"))
        check("產生了任務包", len(tasks) == 1, str(len(tasks)))
        if not tasks:
            return 1
        task_text = tasks[0].read_text(encoding="utf-8")
        check("任務包列出留底原件", "raw/" in task_text or "原件" in task_text)
        check("任務包提到 proposal 路徑", ".proposal.json" in task_text)
        check("analyze 印出貼給 agent 的指示", "task.md" in proc.stdout)

        proposal_id = tasks[0].name[: -len(".task.md")]
        write_proposal(work / "dna" / "inbox" / (proposal_id + ".proposal.json"),
                       proposal_id, code_src.name)
        run("--root", str(work), "proposals")
        run("--root", str(work), "review", proposal_id, "--yes")

        genes = work / "dna" / "profiles" / "personal" / "genes"
        check("ASCII 檔名寫入", (genes / "core-color-palette.md").is_file())
        check("中文檔名寫入", (genes / "間距節奏.md").is_file())
        check("保留字檔名改寫成 con-x.md", (genes / "con-x.md").is_file())

        print("\n[7] 檢視指令")
        run("--root", str(work), "profile", "list")
        run("--root", str(work), "gene", "list")
        run("--root", str(work), "gene", "show", "間距節奏")
        run("--root", str(work), "graph", "--json")
        run("--root", str(work), "doctor")

        print("\n[8] 匯出兩種目標")
        run("--root", str(work), "export", "--profile", "personal")
        build = work / "build" / "personal"
        check("AGENTS.md 產生", (build / "AGENTS.md").is_file())
        pages = sorted((build / "design-dna").glob("*.md"))
        check("3 個 wiki 頁", len(pages) == 3, str(len(pages)))
        check("保留字 wiki 頁是 con-x.md",
              (build / "design-dna" / "con-x.md").is_file())
        agents_text = (build / "AGENTS.md").read_text(encoding="utf-8")
        check("MUST 規則寫進主檔", "2563EB" in agents_text.upper())
        page = (build / "design-dna" / "core-color-palette.md").read_text(
            encoding="utf-8")
        check("wikilink 轉成相對連結", "(間距節奏.md)" in page)

        run("--root", str(work), "export", "--profile", "personal",
            "--target", "claude")
        check("CLAUDE.md 產生", (build / "CLAUDE.md").is_file())
        check("CLAUDE.md 匯入 AGENTS.md",
              "@AGENTS.md" in (build / "CLAUDE.md").read_text(encoding="utf-8"))

        run("--root", str(work), "export", "--profile", "personal",
            "--mode", "full", "--out", str(work / "build" / "flat"))
        flat = (work / "build" / "flat" / "AGENTS.md").read_text(encoding="utf-8")
        check("full 模式把規則攤平", "1200px" in flat)
        check("full 模式不留 wiki 目錄",
              not (work / "build" / "flat" / "design-dna").exists())

        print("\n[9] 模組進入點")
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(ROOT / "src"))
        proc = subprocess.run([sys.executable, "-m", "design_dna", "--version"],
                              cwd=str(ROOT), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        check("python -m design_dna --version", proc.returncode == 0,
              (proc.stderr or "").strip()[:200])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\n" + "-" * 48)
    if failures:
        print("[X] " + str(len(failures)) + " / " + str(checks) + " 項失敗：")
        for f in failures:
            print("  · " + f)
        return 1
    print("[OK] " + str(checks) + " 項檢查全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
