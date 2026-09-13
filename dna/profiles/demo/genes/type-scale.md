---
id: type-scale
title: 字級尺標與字族
category: typography
priority: must
status: confirmed
confidence: 0.88
updated: '2026-09-08'
tags:
- 排版
related:
- spacing-rhythm
evidence:
- source: 20260913-144030-sample-site
  detail: 字級只出現 14 / 16 / 24 / 32 / 48px 五階，沒有任何中間值
- source: 20260913-144030-sample-site
  detail: font-family 全站唯一一組：Inter + Noto Sans TC + system-ui
---

## Rule

字族固定為 `"Inter", "Noto Sans TC", system-ui, sans-serif`（英數在前、中文在後）。

字級只用這五階，不要出現中間值：

| 用途 | size | weight | line-height | tracking |
| --- | --- | --- | --- | --- |
| h1 | 48px | 700 | 1.15 | -0.02em |
| h2 | 32px | 700 | 1.25 | — |
| h3 | 24px | 600 | 1.3 | — |
| body | 16px | 400 | 1.6 | -0.01em |
| small | 14px | 400 | 1.6 | — |

## Rationale

五階夠用、且階與階之間差距大（1.5x 左右），階層一眼就分得出來。
字級越大行高越緊、字距越負，是為了讓大標不鬆散。
中文字族擺第二位，讓英數走 Inter、中文走 Noto Sans TC，避免中文被 Inter 的 fallback 渲染得歪掉。

## Do

```css
h1 { font-size: 48px; font-weight: 700; line-height: 1.15; letter-spacing: -0.02em; }
```

## Avoid

```css
/* 不要為了「差一點點」開新階 */
.subtitle { font-size: 20px; }
/* 不要把中文字族放第一位 */
body { font-family: "Noto Sans TC", "Inter", sans-serif; }
```
