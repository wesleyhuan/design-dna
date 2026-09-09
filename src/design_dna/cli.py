"""design-dna 命令列介面。

    python -m design_dna <command>

主要流程：
    init → ingest → analyze → (agent 產生提案) → review → export
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, analyze as analyze_mod, exporters
from .ingest import ingest as do_ingest, summarize
from .models import Gene, split_sections
from .resolve import inheritance_chain, link_graph, resolve
from .store import BASE_PROFILE, Workspace
from .taxonomy import (CATEGORIES, PRIORITY_LABEL, PRIORITY_WORD,
                       STATUS_LABEL, category_label)


# ---------------------------------------------------------------------------
# 輸出小工具
# ---------------------------------------------------------------------------

def _setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def info(msg: str = "") -> None:
    print(msg)


def ok(msg: str) -> None:
    print("[OK] " + msg)


def warn(msg: str) -> None:
    print("[!] " + msg)


def fail(msg: str) -> int:
    print("[X] " + msg, file=sys.stderr)
    return 1


def table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        info("（無資料）")
        return
    widths = [_width(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], _width(str(cell)))
    info("  ".join(_pad(h, widths[i]) for i, h in enumerate(headers)))
    info("  ".join("-" * w for w in widths))
    for r in rows:
        info("  ".join(_pad(str(c), widths[i]) for i, c in enumerate(r)))


def _width(text: str) -> int:
    """中日韓字元佔兩格，讓表格在終端機對得齊。"""
    return sum(2 if ord(ch) > 0x1100 and _wide(ch) else 1 for ch in text)


def _wide(ch: str) -> bool:
    o = ord(ch)
    return (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0xA4CF
            or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF
            or 0xFE30 <= o <= 0xFE6F or 0xFF00 <= o <= 0xFF60
            or 0xFFE0 <= o <= 0xFFE6)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def get_ws(args: argparse.Namespace) -> Workspace:
    root = getattr(args, "root", None)
    return Workspace(root) if root else Workspace.discover(".")


# ---------------------------------------------------------------------------
# 指令
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    ws = Workspace(args.root or ".")
    existed = ws.exists
    ws.init()
    ok(("工作區已存在，補齊缺少的目錄：" if existed else "已建立工作區：")
       + str(ws.root))
    info("  dna/profiles/   風格檔（每個 profile 一個資料夾）")
    info("  dna/sources/    參考資料與抽取出的事實")
    info("  dna/inbox/      待確認的 AI 提案")
    info("  build/          匯出的 AGENTS.md")
    info("")
    info("下一步： python -m design_dna profile new personal")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    if args.action == "list":
        rows = []
        for p in ws.list_profiles():
            r = resolve(ws, p.id)
            rows.append([p.id, p.name,
                         " → ".join(p.extends) or "-",
                         str(len(r.genes)),
                         str(len(r.confirmed()))])
        table(rows, ["id", "名稱", "繼承", "規則數", "已確認"])
        return 0

    if args.action == "new":
        if not args.name:
            return fail("請給 profile 名稱： profile new <id>")
        extends = args.extends.split(",") if args.extends else None
        p = ws.create_profile(args.name, name=args.title or args.name,
                              description=args.description or "",
                              extends=extends)
        ok("已建立 profile `" + p.id + "`，繼承 "
           + (", ".join(p.extends) or "（無）"))
        return 0

    if args.action == "show":
        r = resolve(ws, args.name or BASE_PROFILE)
        info("profile : " + r.profile_id)
        info("名稱    : " + r.name)
        info("繼承鏈  : " + " → ".join(r.chain))
        if r.description:
            info("說明    : " + r.description)
        info("")
        rows = [[g.id, category_label(g.category),
                 PRIORITY_WORD.get(g.priority, ""),
                 STATUS_LABEL.get(g.status, g.status),
                 g.inherited_from or "-"] for g in r.genes]
        table(rows, ["id", "分類", "強度", "狀態", "繼承自"])
        return 0

    if args.action == "rm":
        if not args.name:
            return fail("請給要刪除的 profile id")
        if ws.delete_profile(args.name):
            ok("已刪除 profile `" + args.name + "`")
            return 0
        return fail("找不到 profile：" + args.name)

    return fail("未知的動作：" + str(args.action))


def cmd_ingest(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    if not ws.exists:
        return fail("這裡不是 design-dna 工作區。先執行： python -m design_dna init")
    keep_raw = None
    if args.keep_raw:
        keep_raw = True
    elif args.no_raw:
        keep_raw = False

    try:
        src = do_ingest(ws, args.target, profile=args.profile,
                        note=args.note or "", keep_raw=keep_raw)
    except FileNotFoundError as exc:
        return fail(str(exc))

    ok("已登錄來源 `" + src.id + "`（" + src.kind + "）")
    for line in summarize(src):
        info("  · " + line)
    if src.files:
        info("  · 已保存原始檔 " + str(len(src.files)) + " 個到 dna/sources/"
             + src.id + "/raw/")
    if src.kind == "web" and not (src.facts.get("web") or {}).get("scanned_files"):
        warn("網頁抓取沒拿到內容，請確認網址或改用本地檔案。")
    info("")
    info("下一步： python -m design_dna analyze --profile " + args.profile)
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    if args.remove:
        if ws.delete_source(args.remove):
            ok("已刪除來源 " + args.remove)
            return 0
        return fail("找不到來源：" + args.remove)
    rows = [[s.id, s.kind, s.profile, s.added,
             (s.origin[:52] + "…") if len(s.origin) > 53 else s.origin]
            for s in ws.list_sources()]
    table(rows, ["id", "類型", "profile", "加入日", "出處"])
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    sources = args.source or [s.id for s in ws.list_sources()
                              if not args.profile or s.profile == args.profile]
    if not sources:
        return fail("沒有可分析的來源。先執行 ingest。")

    try:
        task = analyze_mod.build_task(ws, sources, profile=args.profile,
                                      count=args.count,
                                      count_max=args.count + 8)
    except ValueError as exc:
        return fail(str(exc))

    ok("已產生分析任務包：" + task["task_path"])

    if args.api:
        if not analyze_mod.api_available():
            return fail("沒有 ANTHROPIC_API_KEY，無法使用 --api。"
                        "改用預設的 agent 模式即可。")
        info("呼叫 Anthropic API 中…")
        try:
            proposal = analyze_mod.run_with_api(ws, Path(task["task_path"]),
                                                model=args.model)
        except Exception as exc:                     # noqa: BLE001
            return fail("API 呼叫失敗：" + str(exc))
        ok("已產生提案 `" + proposal["id"] + "`，共 "
           + str(len(proposal["genes"])) + " 條基因")
        info("下一步： python -m design_dna review " + proposal["id"])
        return 0

    info("")
    info("接下來把這句話貼給你的 coding agent（Claude Code / Codex / Cursor）：")
    info("")
    info('    請讀取 "' + task["task_path"] + '" 並照裡面的指示完成分析。')
    info("")
    if task["manual_files"]:
        info("（任務包中有 " + str(len(task["manual_files"]))
             + " 個檔案需要 agent 親自打開查看，已列在任務包裡。）")
    info("agent 完成後執行： python -m design_dna review "
         + task["proposal_id"])
    return 0


def cmd_proposals(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    rows = []
    for p in ws.list_proposals():
        pending = sum(1 for g in p.get("genes", [])
                      if g.get("decision") == "pending")
        rows.append([p.get("id", ""), p.get("profile", ""),
                     p.get("status", ""), str(len(p.get("genes", []))),
                     str(pending)])
    table(rows, ["提案 id", "profile", "狀態", "基因數", "待決"])
    if not rows:
        info("")
        info("還沒有提案。流程： ingest → analyze → 交給 agent → review")
    return 0


def _print_gene_preview(item: dict, idx: int, total: int) -> None:
    info("")
    info("=" * 68)
    info("[" + str(idx) + "/" + str(total) + "] " + item.get("title", "")
         + "   " + PRIORITY_WORD.get(item.get("priority", "should"), "")
         + "   信心 " + str(item.get("confidence", "-")))
    info("id: " + item.get("id", "") + "   分類: "
         + category_label(item.get("category", "")))
    ev = item.get("evidence") or []
    if ev:
        for e in ev[:3]:
            detail = e.get("detail") if isinstance(e, dict) else str(e)
            if detail:
                info("證據: " + detail)
    info("-" * 68)
    sections = split_sections(item.get("body", ""))
    for name, text in sections.items():
        if name:
            info("## " + name)
        info(text)
        info("")


def cmd_review(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    pid = args.proposal_id
    if not pid:
        proposals = ws.list_proposals()
        pending = [p for p in proposals if p.get("status") != "applied"]
        if not pending:
            return fail("沒有待審的提案。")
        pid = pending[0]["id"]
        info("審核最新提案：" + pid)

    try:
        proposal = analyze_mod.load_proposal(ws, pid)
    except FileNotFoundError as exc:
        return fail(str(exc))

    genes = proposal["genes"]
    if not genes:
        return fail("這份提案沒有任何基因。")

    if args.yes:
        result = analyze_mod.apply_proposal(ws, pid,
                                            accept=[g["id"] for g in genes],
                                            profile=args.profile)
        ok("已全部採納 " + str(len(result["written"])) + " 條到 `"
           + result["profile"] + "`")
        return 0

    accepted: list[str] = []
    info("逐條確認。y=採納  n=略過  a=全部採納  q=中止")
    for i, item in enumerate(genes, 1):
        _print_gene_preview(item, i, len(genes))
        while True:
            try:
                choice = input("採納這一條？ [y/n/a/q] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                info("")
                return fail("已中止，沒有寫入任何東西。")
            if choice in ("y", "n", "a", "q", ""):
                break
        if choice == "q":
            return fail("已中止，沒有寫入任何東西。")
        if choice == "a":
            accepted = [g["id"] for g in genes]
            break
        if choice in ("y", ""):
            accepted.append(item["id"])

    result = analyze_mod.apply_proposal(ws, pid, accept=accepted,
                                        profile=args.profile)
    ok("寫入 " + str(len(result["written"])) + " 條到 profile `"
       + result["profile"] + "`，略過 " + str(len(result["skipped"])) + " 條")
    if result["written"]:
        info("下一步： python -m design_dna export --profile "
             + result["profile"])
    return 0


def cmd_gene(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    profile = args.profile

    if args.action == "list":
        r = resolve(ws, profile, include_deprecated=True)
        rows = [[g.id, category_label(g.category),
                 PRIORITY_LABEL.get(g.priority, g.priority),
                 STATUS_LABEL.get(g.status, g.status),
                 str(round(g.confidence, 2)),
                 g.inherited_from or "本層"] for g in r.genes]
        table(rows, ["id", "分類", "強度", "狀態", "信心", "來自"])
        return 0

    if args.action == "show":
        if not args.gene_id:
            return fail("請給 gene id")
        r = resolve(ws, profile, include_deprecated=True)
        match = next((g for g in r.genes if g.id == args.gene_id), None)
        if not match:
            return fail("找不到基因：" + args.gene_id)
        info("# " + match.title)
        info("分類 " + category_label(match.category)
             + " / 強度 " + PRIORITY_WORD.get(match.priority, "")
             + " / 狀態 " + STATUS_LABEL.get(match.status, "")
             + " / 信心 " + str(round(match.confidence, 2)))
        if match.links():
            info("相關 " + ", ".join(match.links()))
        info("")
        info(match.body)
        return 0

    if args.action == "rm":
        if not args.gene_id:
            return fail("請給 gene id")
        if ws.delete_gene(profile, args.gene_id):
            ok("已刪除 " + args.gene_id)
            return 0
        return fail("在 profile `" + profile + "` 找不到 " + args.gene_id)

    if args.action == "status":
        if not args.gene_id or not args.value:
            return fail("用法： gene status <id> --value confirmed")
        g = ws.get_gene(profile, args.gene_id)
        if not g:
            return fail("找不到基因：" + args.gene_id)
        g.status = args.value
        ws.save_gene(profile, g)
        ok(args.gene_id + " 狀態改為 " + g.status)
        return 0

    return fail("未知的動作：" + str(args.action))


def cmd_export(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    profile = args.profile
    if ws.get_profile(profile) is None:
        return fail("找不到 profile：" + profile)

    r = resolve(ws, profile)
    out = Path(args.out) if args.out else (ws.build / profile)
    try:
        result = exporters.export(r, out, target=args.target, mode=args.mode,
                                  include_proposed=args.include_proposed)
    except ValueError as exc:
        return fail(str(exc))

    confirmed = len(r.confirmed())
    ok("已匯出 " + str(confirmed) + " 條規則到 " + result["main"])
    if result["count"] > 1:
        info("  另有 " + str(result["count"] - 1) + " 個 wiki 頁在 "
             + str(out / "design-dna") + "/")
    info("")
    info("移植方式：把整個 " + str(out) + " 目錄複製到目標專案根目錄即可，")
    info("任何讀 AGENTS.md 的 agent 都會自動吃到這份設計 DNA。")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    problems = 0
    for prof in ws.list_profiles():
        r = resolve(ws, prof.id, include_deprecated=True)
        graph = link_graph(r)
        issues: list[str] = []
        if graph["dangling"]:
            issues.append("斷掉的 wiki 連結：" + ", ".join(graph["dangling"]))
        no_ev = [g.id for g in r.genes
                 if g.status == "confirmed" and not g.evidence]
        if no_ev:
            issues.append("已確認但沒有證據：" + ", ".join(no_ev))
        low = [g.id for g in r.genes
               if g.status == "confirmed" and g.confidence < 0.4]
        if low:
            issues.append("信心度偏低卻已確認：" + ", ".join(low))
        empty = [g.id for g in r.genes if not g.body.strip()]
        if empty:
            issues.append("內容是空的：" + ", ".join(empty))
        # 只有 confirmed 會被匯出，所以 confirmed → 非 confirmed 的連結
        # 在匯出的 bundle 裡會變成死連結
        exported = {g.id for g in r.genes if g.status == "confirmed"}
        broken = sorted({
            g.id + " → " + t
            for g in r.genes if g.status == "confirmed"
            for t in g.links()
            if t not in exported and any(x.id == t for x in r.genes)
        })
        if broken:
            issues.append("已確認的規則連到未確認/已淘汰的規則"
                          "（匯出後會是死連結）：" + ", ".join(broken))
        if len(inheritance_chain(ws, prof.id)) == 0:
            issues.append("繼承鏈解析失敗（可能有循環繼承）")

        info("profile `" + prof.id + "` — " + str(len(r.genes)) + " 條規則")
        for msg in issues:
            warn("  " + msg)
            problems += 1
        if not issues:
            info("  沒有問題")
    info("")
    if problems:
        warn("共 " + str(problems) + " 個問題。")
    else:
        ok("全部健康。")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .web.server import serve
    ws = get_ws(args)
    if not ws.exists:
        return fail("這裡不是 design-dna 工作區。先執行： python -m design_dna init")
    serve(ws, host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    ws = get_ws(args)
    r = resolve(ws, args.profile)
    g = link_graph(r)
    if args.json:
        print(json.dumps(g, ensure_ascii=False, indent=2))
        return 0
    info("節點 " + str(len(g["nodes"])) + " 個、連結 "
         + str(len(g["edges"])) + " 條")
    for e in g["edges"]:
        info("  " + e["source"] + "  <->  " + e["target"])
    if g["dangling"]:
        warn("指向不存在的基因： " + ", ".join(g["dangling"]))
    return 0


# ---------------------------------------------------------------------------
# 參數表
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="design_dna",
        description="把你的網頁設計習慣與風格，記錄成可攜式的 AI 知識庫。",
    )
    p.add_argument("--version", action="version", version="design-dna " + __version__)
    p.add_argument("--root", help="工作區根目錄（預設自動往上找）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="建立工作區")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("profile", help="管理風格檔")
    sp.add_argument("action", choices=["list", "new", "show", "rm"])
    sp.add_argument("name", nargs="?")
    sp.add_argument("--title", help="顯示名稱")
    sp.add_argument("--description", help="這個 profile 的說明")
    sp.add_argument("--extends", help="繼承哪些 profile（逗號分隔）")
    sp.set_defaults(func=cmd_profile)

    sp = sub.add_parser("ingest", help="登錄一份參考資料（路徑或網址）")
    sp.add_argument("target", help="檔案 / 資料夾 / 網址")
    sp.add_argument("--profile", default=BASE_PROFILE)
    sp.add_argument("--note", help="這份資料是什麼")
    sp.add_argument("--keep-raw", action="store_true", help="強制保留原始檔副本")
    sp.add_argument("--no-raw", action="store_true", help="不要保留原始檔副本")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("sources", help="列出已登錄的參考資料")
    sp.add_argument("--remove", help="刪除指定來源 id")
    sp.set_defaults(func=cmd_sources)

    sp = sub.add_parser("analyze", help="產生給 AI 的分析任務包")
    sp.add_argument("--profile", default=BASE_PROFILE)
    sp.add_argument("--source", action="append", help="只分析指定來源（可重複）")
    sp.add_argument("--count", type=int, default=8, help="期望產出的基因數下限")
    sp.add_argument("--api", action="store_true",
                    help="直接呼叫 Anthropic API（需 ANTHROPIC_API_KEY）")
    sp.add_argument("--model", default=analyze_mod.DEFAULT_MODEL)
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("proposals", help="列出 AI 提案")
    sp.set_defaults(func=cmd_proposals)

    sp = sub.add_parser("review", help="逐條確認提案並寫入 profile")
    sp.add_argument("proposal_id", nargs="?")
    sp.add_argument("--profile", help="寫到哪個 profile（預設用提案裡的）")
    sp.add_argument("--yes", action="store_true", help="全部採納，不逐條問")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("gene", help="檢視與編輯單條規則")
    sp.add_argument("action", choices=["list", "show", "rm", "status"])
    sp.add_argument("gene_id", nargs="?")
    sp.add_argument("--profile", default=BASE_PROFILE)
    sp.add_argument("--value", help="status 動作要設定的新狀態")
    sp.set_defaults(func=cmd_gene)

    sp = sub.add_parser("export", help="匯出成 AGENTS.md")
    sp.add_argument("--profile", default=BASE_PROFILE)
    sp.add_argument("--target", default=exporters.DEFAULT_EXPORTER,
                    choices=exporters.available())
    sp.add_argument("--mode", default="index", choices=["index", "full"],
                    help="index=主檔放 MUST + 索引；full=全部攤平")
    sp.add_argument("--out", help="輸出目錄（預設 build/<profile>）")
    sp.add_argument("--include-proposed", action="store_true",
                    help="連未確認的規則也匯出")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("graph", help="顯示 wiki 連結圖")
    sp.add_argument("--profile", default=BASE_PROFILE)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("doctor", help="檢查知識庫健康度")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("web", help="啟動本地 Web UI")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--no-browser", action="store_true")
    sp.set_defaults(func=cmd_web)

    return p


def main(argv: list[str] | None = None) -> int:
    _setup_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        info("")
        return 130
