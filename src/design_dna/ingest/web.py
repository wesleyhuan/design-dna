"""從線上網址抓取頁面與其樣式表，再交給 code 分析器。

注意：這會實際對外發出 HTTP 請求，只在使用者明確給定網址時執行。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from .code import analyze_code

USER_AGENT = "design-dna/0.1 (+local design style analyzer)"
MAX_CSS_FILES = 12
TIMEOUT = 20


def _fetch(url: str) -> tuple[str, str]:
    """回傳 (text, content_type)。失敗時 text 為空字串。"""
    try:
        import requests
    except ImportError:
        return "", ""
    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp.text, resp.headers.get("content-type", "")
    except Exception:                              # noqa: BLE001 網路什麼都可能壞
        return "", ""


LINK_RE = re.compile(
    r"<link[^>]+rel=[\"']?stylesheet[\"']?[^>]*>", re.I)
HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_DESC_RE = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']*)[\"']", re.I)


def fetch_site(url: str) -> dict[str, Any]:
    """抓 HTML + 外部 CSS，回傳可餵給 analyze_code 的 (name, text) 清單與 meta。"""
    if not urlparse(url).scheme:
        url = "https://" + url

    html, _ = _fetch(url)
    if not html:
        return {"ok": False, "url": url,
                "note": "抓取失敗（網路錯誤、對方擋爬、或未安裝 requests）。"}

    docs: list[tuple[str, str]] = [(url, html)]
    css_urls: list[str] = []
    for tag in LINK_RE.findall(html):
        m = HREF_RE.search(tag)
        if m:
            css_urls.append(urljoin(url, m.group(1)))

    fetched_css = []
    for css_url in css_urls[:MAX_CSS_FILES]:
        text, _ = _fetch(css_url)
        if text:
            docs.append((css_url, text))
            fetched_css.append(css_url)

    for i, block in enumerate(STYLE_BLOCK_RE.findall(html)):
        docs.append((url + " <style#" + str(i) + ">", block))

    title = TITLE_RE.search(html)
    desc = META_DESC_RE.search(html)
    return {
        "ok": True,
        "url": url,
        "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
        "description": desc.group(1).strip() if desc else "",
        "stylesheets": fetched_css,
        "docs": docs,
        "html_bytes": len(html),
    }


def analyze_url(url: str) -> dict[str, Any]:
    site = fetch_site(url)
    if not site.get("ok"):
        return site
    docs = site.pop("docs")
    facts = analyze_code(None, extra_texts=docs)
    facts["site"] = site
    return facts
