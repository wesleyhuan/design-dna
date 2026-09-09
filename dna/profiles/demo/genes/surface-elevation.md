---
id: surface-elevation
title: 卡片圓角與陰影
category: component
priority: should
status: confirmed
confidence: 0.8
updated: '2026-09-08'
tags:
- 元件
- 卡片
related:
- core-color-palette
- motion-timing
evidence:
- source: 20260908-005028-sample-site
  detail: border-radius 全站只有 12px 一個值；陰影只有靜置與 hover 兩階
---

## Rule

所有可點擊的容器（按鈕、卡片、輸入框）圓角固定 `12px`。

陰影只有兩階，而且顏色一定是主文字色的透明版，不是純黑：

```css
--shadow-card:  0 1px 3px  rgba(15, 23, 42, 0.08);  /* 靜置 */
--shadow-hover: 0 8px 24px rgba(15, 23, 42, 0.12);  /* hover */
```

## Rationale

單一圓角值讓所有元件看起來像同一套系統。用帶色陰影（slate 的透明版）而非純黑，
陰影才會融進背景，不會像髒污浮在上面。

## Do

```css
.card { border-radius: 12px; box-shadow: var(--shadow-card); }
.card:hover { box-shadow: var(--shadow-hover); }
```

## Avoid

```css
.card { border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }
```
