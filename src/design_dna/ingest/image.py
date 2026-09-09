"""從設計稿 / 截圖抽取可量測事實（主色票、版面比例、明暗）。

只做機器看得準的部分。「這張圖給人的感覺」交給 agent 看圖判斷。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}


def _luminance(rgb: tuple[int, int, int]) -> float:
    chan = []
    for c8 in rgb:
        c = c8 / 255.0
        chan.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]


def _saturation(rgb: tuple[int, int, int]) -> float:
    hi, lo = max(rgb), min(rgb)
    return 0.0 if hi == 0 else (hi - lo) / hi


def analyze_image(path: Path | str, palette_size: int = 8) -> dict[str, Any]:
    path = Path(path)
    try:
        from PIL import Image
    except ImportError:
        return {
            "available": False,
            "note": "未安裝 Pillow，無法自動取色。請 pip install pillow，"
                    "或讓 agent 直接看圖描述。",
        }

    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:                       # noqa: BLE001 圖檔格式千奇百怪
        return {"available": False, "note": "無法讀取圖片：" + str(exc)}

    width, height = img.size
    rgb = img.convert("RGB")
    # 縮圖後量化，避免大圖拖慢速度
    sample = rgb.copy()
    sample.thumbnail((400, 400))
    quant = sample.quantize(colors=palette_size, method=2)
    pal = quant.getpalette() or []
    counts = sorted(quant.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1

    palette = []
    for count, idx in counts:
        r, g, b = pal[idx * 3:idx * 3 + 3] or (0, 0, 0)
        palette.append({
            "hex": "#{:02X}{:02X}{:02X}".format(r, g, b),
            "share": round(count / total, 4),
            "luminance": round(_luminance((r, g, b)), 4),
            "saturation": round(_saturation((r, g, b)), 3),
        })

    avg_lum = sum(p["luminance"] * p["share"] for p in palette)
    accents = [p for p in palette if p["saturation"] > 0.35 and p["share"] < 0.25]
    neutrals = [p for p in palette if p["saturation"] <= 0.15]

    return {
        "available": True,
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 3) if height else 0,
        "orientation": "landscape" if width > height else
                       ("portrait" if height > width else "square"),
        "palette": palette,
        "average_luminance": round(avg_lum, 4),
        "mode": "dark" if avg_lum < 0.35 else ("light" if avg_lum > 0.7 else "mixed"),
        "accent_candidates": [p["hex"] for p in accents[:4]],
        "neutral_candidates": [p["hex"] for p in neutrals[:4]],
    }


def analyze_images(paths: list[Path]) -> dict[str, Any]:
    results = []
    for p in paths:
        info = analyze_image(p)
        info["file"] = p.name
        results.append(info)
    modes = [r.get("mode") for r in results if r.get("available")]
    return {
        "image_count": len(results),
        "images": results,
        "dominant_mode": max(set(modes), key=modes.count) if modes else "",
    }
