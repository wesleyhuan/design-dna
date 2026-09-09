"""從前端原始碼反推設計事實。

這一層完全是確定性的字串/正則分析，不呼叫任何 LLM。
目的是把「可量測的」東西先算出來（色票出現次數、字級分佈、斷點、
命名慣例、技術棧），LLM 只負責後面的詮釋與取捨。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 檔案蒐集
# ---------------------------------------------------------------------------

STYLE_EXTS = {".css", ".scss", ".sass", ".less", ".styl"}
CODE_EXTS = STYLE_EXTS | {
    ".html", ".htm", ".vue", ".svelte", ".astro",
    ".js", ".jsx", ".ts", ".tsx",
}
IGNORE_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", "dist", "build", "out",
    "__pycache__", ".venv", "venv", "coverage", ".svelte-kit", "vendor",
    ".turbo", ".cache",
}
MAX_FILE_BYTES = 2_000_000
MAX_FILES = 400


def collect_files(root: Path) -> list[Path]:
    """走訪目錄收集前端檔案；單檔就直接回傳。"""
    root = Path(root)
    if root.is_file():
        return [root]
    found: list[Path] = []
    for p in sorted(root.rglob("*")):
        if len(found) >= MAX_FILES:
            break
        if not p.is_file():
            continue
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in CODE_EXTS and p.stat().st_size <= MAX_FILE_BYTES:
            found.append(p)
    return found


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# 色彩
# ---------------------------------------------------------------------------

HEX_RE = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
RGB_RE = re.compile(r"rgba?\(\s*([0-9.]+)\s*[, ]\s*([0-9.]+)\s*[, ]\s*([0-9.]+)")
HSL_RE = re.compile(r"hsla?\(\s*([0-9.]+)(?:deg)?\s*[, ]\s*([0-9.]+)%\s*[, ]\s*([0-9.]+)%")


def _hex_norm(raw: str) -> str:
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return "#" + raw[:6].upper()


def _hsl_to_hex(h: float, s: float, ll: float) -> str:
    h = (h % 360) / 360.0
    s /= 100.0
    ll /= 100.0
    if s == 0:
        v = int(round(ll * 255))
        return "#{:02X}{:02X}{:02X}".format(v, v, v)

    def hue(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = ll * (1 + s) if ll < 0.5 else ll + s - ll * s
    p = 2 * ll - q
    rgb = [hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)]
    return "#{:02X}{:02X}{:02X}".format(*[int(round(c * 255)) for c in rgb])


def extract_colors(text: str) -> Counter:
    counts: Counter = Counter()
    for m in HEX_RE.finditer(text):
        counts[_hex_norm(m.group(1))] += 1
    for m in RGB_RE.finditer(text):
        try:
            r, g, b = (min(255, int(float(v))) for v in m.groups())
            counts["#{:02X}{:02X}{:02X}".format(r, g, b)] += 1
        except ValueError:
            continue
    for m in HSL_RE.finditer(text):
        try:
            counts[_hsl_to_hex(*(float(v) for v in m.groups()))] += 1
        except ValueError:
            continue
    return counts


def relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return 0.0
    chan = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        chan.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


# ---------------------------------------------------------------------------
# 排版 / 間距 / 圓角 / 陰影 / 動效
# ---------------------------------------------------------------------------

def _decl_re(prop: str) -> re.Pattern:
    return re.compile(prop + r"\s*:\s*([^;}\n]+)", re.I)


FONT_FAMILY_RE = _decl_re("font-family")
FONT_SIZE_RE = _decl_re("font-size")
FONT_WEIGHT_RE = _decl_re("font-weight")
LINE_HEIGHT_RE = _decl_re("line-height")
LETTER_SPACING_RE = _decl_re("letter-spacing")
RADIUS_RE = _decl_re("border-radius")
SHADOW_RE = _decl_re("box-shadow")
TRANSITION_RE = _decl_re("transition")
SPACING_RE = re.compile(
    r"\b(?:margin|padding|gap|row-gap|column-gap)(?:-(?:top|right|bottom|left|inline|block))?"
    r"\s*:\s*([^;}\n]+)", re.I)
MEDIA_RE = re.compile(r"@media[^{]*?\(\s*(min|max)-width\s*:\s*([0-9.]+)(px|rem|em)", re.I)
CSS_VAR_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;}\n]+)")
CLASS_SELECTOR_RE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
CLASS_ATTR_RE = re.compile(r"class(?:Name)?\s*=\s*[\"']([^\"']+)[\"']")
LENGTH_TOKEN_RE = re.compile(r"(-?[0-9]*\.?[0-9]+)(px|rem|em|%|vh|vw)")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().strip(",")


def extract_lengths(values: list[str]) -> Counter:
    counts: Counter = Counter()
    for v in values:
        if "var(" in v or "calc(" in v:
            continue
        for num, unit in LENGTH_TOKEN_RE.findall(v):
            if unit == "%":
                continue
            try:
                n = float(num)
            except ValueError:
                continue
            if n == 0:
                continue
            counts[("{:g}".format(n)) + unit] += 1
    return counts


def detect_naming(selectors: list[str]) -> dict[str, Any]:
    """判斷 class 命名慣例：BEM / kebab / camel / snake / utility。"""
    tally = Counter()
    for s in selectors:
        if "__" in s or "--" in s:
            tally["bem"] += 1
        elif re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", s):
            tally["kebab"] += 1
        elif re.fullmatch(r"[a-z]+(?:[A-Z][a-z0-9]*)+", s):
            tally["camel"] += 1
        elif "_" in s:
            tally["snake"] += 1
        elif re.fullmatch(r"[a-z0-9]+", s):
            tally["single-word"] += 1
    total = sum(tally.values())
    # single-word 不算一種「慣例」——任何慣例都允許單字名稱，
    # 拿它當 dominant 會蓋掉真正的訊號（BEM / kebab / camel）。
    signal = Counter({k: v for k, v in tally.items() if k != "single-word"})
    return {
        "counts": dict(tally.most_common()),
        "dominant": signal.most_common(1)[0][0] if signal else "single-word",
        "sampled": total,
    }


TAILWIND_HINT = re.compile(
    r"^(?:sm|md|lg|xl|2xl|hover|focus|active|group|dark|first|last|peer):|"
    r"^(?:flex|grid|gap|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|min|max|"
    r"text|font|bg|border|rounded|shadow|space|items|justify|self|col|row|"
    r"absolute|relative|fixed|sticky|z|opacity|transition|duration|ease|"
    r"transform|scale|translate|rotate|overflow|truncate|leading|tracking|"
    r"container|mx-auto|inline|block|hidden|cursor|ring|divide|backdrop)[-a-z0-9./\[\]]*$"
)


def extract_tailwind(text: str) -> Counter:
    counts: Counter = Counter()
    for m in CLASS_ATTR_RE.finditer(text):
        for token in m.group(1).split():
            if TAILWIND_HINT.match(token):
                counts[token] += 1
    return counts


# ---------------------------------------------------------------------------
# 技術棧
# ---------------------------------------------------------------------------

STACK_MARKERS = {
    "next": "Next.js", "react": "React", "vue": "Vue", "svelte": "Svelte",
    "astro": "Astro", "nuxt": "Nuxt", "tailwindcss": "Tailwind CSS",
    "styled-components": "styled-components", "@emotion/react": "Emotion",
    "sass": "Sass", "bootstrap": "Bootstrap", "@mui/material": "MUI",
    "@chakra-ui/react": "Chakra UI", "antd": "Ant Design",
    "framer-motion": "Framer Motion", "gsap": "GSAP",
    "vite": "Vite", "webpack": "Webpack", "typescript": "TypeScript",
    "shadcn-ui": "shadcn/ui", "radix-ui": "Radix UI",
    "@radix-ui/react-dialog": "Radix UI", "daisyui": "daisyUI",
}


def detect_stack(root: Path) -> dict[str, Any]:
    root = Path(root)
    base = root if root.is_dir() else root.parent
    found: list[str] = []
    config_files: list[str] = []

    pkg = base / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            deps = {}
            deps.update(data.get("dependencies") or {})
            deps.update(data.get("devDependencies") or {})
            for key, label in STACK_MARKERS.items():
                if any(d == key or d.startswith(key) for d in deps):
                    if label not in found:
                        found.append(label)
        except (OSError, json.JSONDecodeError):
            pass

    for pattern, label in (
        ("tailwind.config.*", "Tailwind CSS"),
        ("next.config.*", "Next.js"),
        ("vite.config.*", "Vite"),
        ("svelte.config.*", "Svelte"),
        ("astro.config.*", "Astro"),
        ("nuxt.config.*", "Nuxt"),
        ("tsconfig.json", "TypeScript"),
    ):
        for hit in base.glob(pattern):
            config_files.append(hit.name)
            if label not in found:
                found.append(label)

    return {"detected": found, "config_files": sorted(set(config_files))}


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _top(counter: Counter, n: int = 20) -> list[dict[str, Any]]:
    return [{"value": v, "count": c} for v, c in counter.most_common(n)]


def analyze_code(root: Path | str | None,
                 extra_texts: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any]:
    """回傳一包可量測的設計事實。

    root=None 代表沒有本地檔案要掃（例如 web ingest 只給 extra_texts），
    這時絕不能誤把當前工作目錄當成掃描目標。
    """
    root = Path(root) if root is not None else None
    files = collect_files(root) if (root is not None and root.exists()) else []

    docs: list[tuple[str, str]] = [(str(f), read_text(f)) for f in files]
    if extra_texts:
        docs.extend(extra_texts)

    colors: Counter = Counter()
    families: Counter = Counter()
    sizes: Counter = Counter()
    weights: Counter = Counter()
    line_heights: Counter = Counter()
    tracking: Counter = Counter()
    radii: Counter = Counter()
    shadows: Counter = Counter()
    transitions: Counter = Counter()
    spacing_raw: list[str] = []
    breakpoints: Counter = Counter()
    css_vars: dict[str, str] = {}
    selectors: list[str] = []
    tailwind: Counter = Counter()
    ext_counts: Counter = Counter()

    for name, text in docs:
        if not text:
            continue
        ext_counts[Path(name).suffix.lower() or "(inline)"] += 1
        colors.update(extract_colors(text))
        for m in FONT_FAMILY_RE.finditer(text):
            families[_clean(m.group(1))] += 1
        sizes.update(extract_lengths([_clean(m.group(1))
                                      for m in FONT_SIZE_RE.finditer(text)]))
        for m in FONT_WEIGHT_RE.finditer(text):
            weights[_clean(m.group(1))] += 1
        for m in LINE_HEIGHT_RE.finditer(text):
            line_heights[_clean(m.group(1))] += 1
        for m in LETTER_SPACING_RE.finditer(text):
            tracking[_clean(m.group(1))] += 1
        radii.update(extract_lengths([_clean(m.group(1))
                                      for m in RADIUS_RE.finditer(text)]))
        for m in SHADOW_RE.finditer(text):
            shadows[_clean(m.group(1))] += 1
        for m in TRANSITION_RE.finditer(text):
            transitions[_clean(m.group(1))] += 1
        spacing_raw.extend(_clean(m.group(1)) for m in SPACING_RE.finditer(text))
        for kind, num, unit in MEDIA_RE.findall(text):
            breakpoints[kind + "-width: " + num + unit] += 1
        for name_, val in CSS_VAR_RE.findall(text):
            css_vars.setdefault(name_, _clean(val))
        # class 選擇器只從樣式表取。在 .tsx/.js 裡，`.` 幾乎都是屬性存取
        # （props.className、arr.map），一起收進來會把命名慣例判斷帶歪。
        if Path(name).suffix.lower() in STYLE_EXTS or "<style#" in name:
            selectors.extend(CLASS_SELECTOR_RE.findall(text))
        else:
            for m in CLASS_ATTR_RE.finditer(text):
                selectors.extend(
                    t for t in m.group(1).split()
                    if not TAILWIND_HINT.match(t)
                )
        tailwind.update(extract_tailwind(text))

    spacing = extract_lengths(spacing_raw)

    facts: dict[str, Any] = {
        "scanned_files": len(docs),
        "file_types": dict(ext_counts.most_common()),
        "colors": _top(colors, 24),
        "font_families": _top(families, 8),
        "font_sizes": _top(sizes, 16),
        "font_weights": _top(weights, 8),
        "line_heights": _top(line_heights, 8),
        "letter_spacing": _top(tracking, 6),
        "spacing_values": _top(spacing, 16),
        "border_radius": _top(radii, 10),
        "box_shadows": _top(shadows, 8),
        "transitions": _top(transitions, 8),
        "breakpoints": _top(breakpoints, 10),
        "css_variables": dict(list(css_vars.items())[:60]),
        "naming": detect_naming(selectors),
        "tailwind_classes": _top(tailwind, 40),
        "stack": (detect_stack(root) if (root is not None and root.exists())
                  else {"detected": [], "config_files": []}),
    }

    # 額外算個對比度提示：最常見的深色 vs 最常見的淺色
    ranked = [c["value"] for c in facts["colors"]]
    darks = [c for c in ranked if relative_luminance(c) < 0.2]
    lights = [c for c in ranked if relative_luminance(c) > 0.8]
    if darks and lights:
        facts["contrast_sample"] = {
            "fg": darks[0],
            "bg": lights[0],
            "ratio": contrast_ratio(darks[0], lights[0]),
        }
    return facts
