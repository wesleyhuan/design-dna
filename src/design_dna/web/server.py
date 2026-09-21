"""本地 Web UI 伺服器。

刻意只用 stdlib 的 http.server：整包複製到別台機器，
不裝任何東西就能 `python dna.py web` 起來。

安全性：只綁 127.0.0.1，且所有會寫入的請求都檢查 Host 與 Origin，
避免瀏覽器上某個網頁偷偷對你的本機服務下指令（DNS rebinding / CSRF）。
"""

from __future__ import annotations

import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__, analyze as analyze_mod, exporters
from ..ingest import ingest as do_ingest, summarize, verify_source
from ..models import Gene, slugify
from ..resolve import link_graph, resolve
from ..store import BASE_PROFILE, DEFAULT_PROFILE, Workspace
from ..taxonomy import (CATEGORIES, PRIORITIES, PRIORITY_LABEL, STATUSES,
                        STATUS_LABEL)

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# 路由表
# ---------------------------------------------------------------------------

Route = tuple[str, re.Pattern, Callable]
ROUTES: list[Route] = []


def route(method: str, pattern: str) -> Callable:
    def deco(fn: Callable) -> Callable:
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


@route("GET", "/api/state")
def api_state(ws: Workspace, m, query, body) -> dict[str, Any]:
    profiles = []
    for p in ws.list_profiles():
        r = resolve(ws, p.id)
        profiles.append({
            **p.to_dict(),
            "gene_count": len(r.genes),
            "confirmed_count": len(r.confirmed()),
        })
    proposals = ws.list_proposals()
    return {
        "version": __version__,
        "root": str(ws.root),
        "profiles": profiles,
        "categories": [{"key": c.key, "label": c.label, "hint": c.hint}
                       for c in CATEGORIES],
        "priorities": [{"key": k, "label": PRIORITY_LABEL[k]} for k in PRIORITIES],
        "statuses": [{"key": k, "label": STATUS_LABEL[k]} for k in STATUSES],
        "source_count": len(ws.list_sources()),
        "pending_proposals": sum(1 for p in proposals
                                 if p.get("status") != "applied"),
        "api_mode": analyze_mod.api_available(),
        "export_targets": exporters.available(),
    }


@route("POST", "/api/profiles")
def api_profile_create(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = slugify(body.get("id") or body.get("name") or "")
    if not pid:
        raise ApiError("profile id 不能是空的")
    if ws.get_profile(pid) is not None:
        raise ApiError("profile `" + pid + "` 已經存在")
    extends = body.get("extends")
    if isinstance(extends, str):
        extends = [e.strip() for e in extends.split(",") if e.strip()]
    p = ws.create_profile(pid, name=body.get("name") or pid,
                          description=body.get("description") or "",
                          extends=extends)
    return p.to_dict()


@route("DELETE", r"/api/profiles/([^/]+)")
def api_profile_delete(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = unquote(m.group(1))
    if pid == BASE_PROFILE:
        raise ApiError("base profile 不能刪除")
    if not ws.delete_profile(pid):
        raise ApiError("找不到 profile：" + pid, 404)
    return {"deleted": pid}


@route("GET", r"/api/profiles/([^/]+)")
def api_profile_get(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = unquote(m.group(1))
    if ws.get_profile(pid) is None:
        raise ApiError("找不到 profile：" + pid, 404)
    r = resolve(ws, pid, include_deprecated=True)
    data = r.to_dict()
    data["graph"] = link_graph(r)
    return data


@route("PUT", r"/api/profiles/([^/]+)/genes/([^/]+)")
def api_gene_save(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid, gid = unquote(m.group(1)), unquote(m.group(2))
    if ws.get_profile(pid) is None:
        raise ApiError("找不到 profile：" + pid, 404)
    payload = dict(body)
    payload["id"] = gid
    gene = Gene.from_dict(payload)
    saved = ws.save_gene(pid, gene)
    return saved.to_dict()


@route("POST", r"/api/profiles/([^/]+)/genes")
def api_gene_create(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = unquote(m.group(1))
    if ws.get_profile(pid) is None:
        raise ApiError("找不到 profile：" + pid, 404)
    gid = slugify(body.get("id") or body.get("title") or "")
    if not gid:
        raise ApiError("規則需要一個標題")
    if ws.get_gene(pid, gid) is not None:
        raise ApiError("這個 profile 已經有 `" + gid + "` 了")
    payload = dict(body)
    payload["id"] = gid
    gene = Gene.from_dict(payload)
    return ws.save_gene(pid, gene).to_dict()


@route("DELETE", r"/api/profiles/([^/]+)/genes/([^/]+)")
def api_gene_delete(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid, gid = unquote(m.group(1)), unquote(m.group(2))
    if not ws.delete_gene(pid, gid):
        raise ApiError("這條規則不在 `" + pid + "` 本層（可能是繼承來的）", 404)
    return {"deleted": gid}


@route("GET", "/api/sources")
def api_sources(ws: Workspace, m, query, body) -> dict[str, Any]:
    items = []
    for s in ws.list_sources():
        items.append({
            **s.to_dict(),
            "summary": summarize(s),
            "cited_by": [p + "/" + g for p, g in ws.genes_citing(s.id)],
            "integrity": verify_source(ws, s),
        })
    return {"sources": items}


@route("DELETE", r"/api/sources/([^/]+)")
def api_source_delete(ws: Workspace, m, query, body) -> dict[str, Any]:
    sid = unquote(m.group(1))
    if ws.get_source(sid) is None:
        raise ApiError("找不到來源：" + sid, 404)
    citing = ws.genes_citing(sid)
    force = (query.get("force") or ["0"])[0] == "1"
    if citing and not force:
        raise ApiError("這份來源是 " + str(len(citing)) + " 條規則的證據（"
                       + ", ".join(p + "/" + g for p, g in citing)
                       + "），刪掉後它們就追不回出處。", 409)
    ws.delete_source(sid)
    return {"deleted": sid, "orphaned": [p + "/" + g for p, g in citing]}


@route("POST", "/api/ingest")
def api_ingest(ws: Workspace, m, query, body) -> dict[str, Any]:
    target = (body.get("target") or "").strip()
    if not target:
        raise ApiError("請給一個檔案路徑、資料夾或網址")
    try:
        src = do_ingest(ws, target,
                        profile=body.get("profile") or DEFAULT_PROFILE,
                        note=body.get("note") or "",
                        keep_raw=body.get("keep_raw", True) is not False)
    except FileNotFoundError as exc:
        raise ApiError(str(exc), 404) from exc
    except Exception as exc:                        # noqa: BLE001
        raise ApiError("登錄失敗：" + str(exc)) from exc
    return {**src.to_dict(), "summary": summarize(src)}


@route("POST", "/api/analyze")
def api_analyze(ws: Workspace, m, query, body) -> dict[str, Any]:
    profile = body.get("profile") or DEFAULT_PROFILE
    sources = body.get("sources") or [s.id for s in ws.list_sources()
                                      if s.profile == profile]
    if not sources:
        raise ApiError("這個 profile 底下沒有參考資料，先去「參考資料」加一份。")
    try:
        task = analyze_mod.build_task(ws, sources, profile=profile,
                                      count=int(body.get("count") or 8))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc

    if body.get("use_api"):
        if not analyze_mod.api_available():
            raise ApiError("沒有設定 ANTHROPIC_API_KEY，無法使用 API 模式。")
        try:
            proposal = analyze_mod.run_with_api(ws, Path(task["task_path"]))
        except Exception as exc:                    # noqa: BLE001
            raise ApiError("API 呼叫失敗：" + str(exc)) from exc
        return {**task, "proposal": proposal, "mode": "api"}
    return {**task, "mode": "agent"}


@route("GET", "/api/proposals")
def api_proposals(ws: Workspace, m, query, body) -> dict[str, Any]:
    return {"proposals": [analyze_mod.normalize_proposal(p)
                          for p in ws.list_proposals()]}


@route("GET", r"/api/proposals/([^/]+)")
def api_proposal_get(ws: Workspace, m, query, body) -> dict[str, Any]:
    try:
        return analyze_mod.load_proposal(ws, unquote(m.group(1)))
    except FileNotFoundError as exc:
        raise ApiError(str(exc), 404) from exc


@route("POST", r"/api/proposals/([^/]+)/apply")
def api_proposal_apply(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = unquote(m.group(1))
    accept = body.get("accept")
    if accept is not None and not isinstance(accept, list):
        raise ApiError("accept 必須是 id 陣列")
    try:
        return analyze_mod.apply_proposal(ws, pid, accept=accept,
                                          profile=body.get("profile"))
    except FileNotFoundError as exc:
        raise ApiError(str(exc), 404) from exc


@route("DELETE", r"/api/proposals/([^/]+)")
def api_proposal_delete(ws: Workspace, m, query, body) -> dict[str, Any]:
    pid = unquote(m.group(1))
    if not ws.delete_proposal(pid):
        raise ApiError("找不到提案：" + pid, 404)
    return {"deleted": pid}


@route("GET", "/api/export")
def api_export_preview(ws: Workspace, m, query, body) -> dict[str, Any]:
    profile = (query.get("profile") or [DEFAULT_PROFILE])[0]
    mode = (query.get("mode") or ["index"])[0]
    target = (query.get("target") or [exporters.DEFAULT_EXPORTER])[0]
    if ws.get_profile(profile) is None:
        raise ApiError("找不到 profile：" + profile, 404)
    r = resolve(ws, profile)
    return {
        "profile": profile,
        "mode": mode,
        "text": exporters.render(r, target=target, mode=mode),
        "confirmed": len(r.confirmed()),
        "total": len(r.genes),
        "out_dir": str(ws.build / profile),
    }


@route("POST", "/api/export")
def api_export_write(ws: Workspace, m, query, body) -> dict[str, Any]:
    profile = body.get("profile") or DEFAULT_PROFILE
    if ws.get_profile(profile) is None:
        raise ApiError("找不到 profile：" + profile, 404)
    r = resolve(ws, profile)
    out = Path(body["out"]) if body.get("out") else (ws.build / profile)
    result = exporters.export(r, out, target=body.get("target")
                              or exporters.DEFAULT_EXPORTER,
                              mode=body.get("mode") or "index",
                              include_proposed=bool(body.get("include_proposed")))
    return {**result, "out_dir": str(out)}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    workspace: Workspace = None            # 由 serve() 注入
    server_version = "design-dna/" + __version__
    protocol_version = "HTTP/1.1"

    # -- 安全檢查 --------------------------------------------------------
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ALLOWED_HOSTS

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            # 沒有 Origin 的同源請求（例如 curl）放行，但要求標記
            return self.headers.get("X-Design-DNA") == "1"
        host = urlparse(origin).hostname
        return host in {"127.0.0.1", "localhost", "::1"}

    # -- 回應 ------------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, data: Any, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    # -- 分派 ------------------------------------------------------------
    def _handle(self, method: str) -> None:
        # 一定要先把 body 讀完再做任何提早回傳的檢查：
        # 沒讀走的位元組會留在 socket 裡，被當成下一個請求的請求列解析。
        raw = b""
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            raw = self.rfile.read(length)

        if not self._host_ok():
            self._error("只接受來自本機的請求", 403)
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/"):
            if method != "GET" and not self._origin_ok():
                self._error("跨來源的寫入請求已被拒絕", 403)
                return
            body: dict[str, Any] = {}
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8")) or {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._error("請求內容不是合法的 JSON")
                    return
            for route_method, pattern, fn in ROUTES:
                if route_method != method:
                    continue
                match = pattern.match(path)
                if match:
                    try:
                        self._json(fn(self.workspace, match, query, body))
                    except ApiError as exc:
                        self._error(exc.message, exc.status)
                    except Exception as exc:        # noqa: BLE001
                        self._error("伺服器錯誤：" + str(exc), 500)
                    return
            self._error("沒有這個 API：" + method + " " + path, 404)
            return

        if method != "GET":
            self._error("不支援的方法", 405)
            return
        self._serve_static(path)

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC_DIR / rel).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._error("不允許的路徑", 403)
            return
        if not target.is_file():
            self._error("找不到檔案：" + rel, 404)
            return
        self._send(200, target.read_bytes(),
                   CONTENT_TYPES.get(target.suffix.lower(),
                                     "application/octet-stream"))

    def do_GET(self) -> None:       # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:      # noqa: N802
        self._handle("POST")

    def do_PUT(self) -> None:       # noqa: N802
        self._handle("PUT")

    def do_DELETE(self) -> None:    # noqa: N802
        self._handle("DELETE")

    def log_message(self, fmt: str, *args: Any) -> None:
        # 預設會把每個請求印到 stderr，太吵；只留錯誤
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(fmt, *args)


def serve(ws: Workspace, host: str = "127.0.0.1", port: int = 8765,
          open_browser: bool = True) -> None:
    Handler.workspace = ws
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = "http://" + host + ":" + str(port) + "/"
    print("design-dna Web UI: " + url)
    print("工作區: " + str(ws.root))
    print("按 Ctrl+C 結束。")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
