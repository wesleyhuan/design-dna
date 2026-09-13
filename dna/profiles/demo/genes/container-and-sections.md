---
id: container-and-sections
title: 版面容器與區塊節奏
category: layout
priority: should
status: confirmed
confidence: 0.75
updated: '2026-09-08'
tags:
- 版面
related:
- spacing-rhythm
- breakpoint-strategy
evidence:
- source: 20260913-144030-sample-site
  detail: '.section 固定 max-width: 1200px + margin: 0 auto，垂直內距一律 48px'
---

## Rule

頁面內容包在 `max-width: 1200px; margin: 0 auto` 的容器裡。
區塊的垂直內距固定 `48px`，水平內距隨斷點放大：手機 `24px`、平板 `32px`、桌機 `48px`。

版面用 flex 原語組合，不要每個地方重寫：
- `.stack` — 垂直堆疊，`gap: 16px`
- `.cluster` — 水平排列並垂直置中，`gap: 8px`

## Rationale

1200px 在 1440 螢幕上左右各留約 120px，長文行寬不會過寬。
垂直內距不隨斷點變，是因為手機上的垂直空間比水平空間值錢，
縮水平就好。

## Do

```css
.section { max-width: 1200px; margin: 0 auto; padding: 48px 24px; }
@media (min-width: 1024px) { .section { padding: 48px; } }
```

## Avoid

```css
/* 不要讓內容貼著螢幕邊 */
.section { max-width: 100%; padding: 48px 0; }
```
