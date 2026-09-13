---
id: breakpoint-strategy
title: 行動優先的兩個斷點
category: responsive
priority: must
status: confirmed
confidence: 0.82
updated: '2026-09-08'
tags:
- RWD
related:
- container-and-sections
evidence:
- source: 20260913-144030-sample-site
  detail: '只出現 min-width: 768px 與 min-width: 1024px 兩個斷點，沒有任何 max-width query'
---

## Rule

只用兩個斷點，且一律是 `min-width`：

- `768px` — 平板
- `1024px` — 桌機

基礎樣式寫手機版，斷點只往上加東西。**不要寫 `max-width` query。**

## Rationale

min-width 疊加的方向是單向的，樣式來源永遠可以往回追；
max-width 一混進來就會出現「兩邊都命中、看誰後寫」的覆蓋問題。
兩個斷點也足以涵蓋絕大多數版面切換，開第三個之前先確認真的必要。

## Do

```css
.grid { display: flex; flex-direction: column; gap: 24px; }
@media (min-width: 1024px) {
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); }
}
```

## Avoid

```css
@media (max-width: 767px) { .grid { display: block; } }
```
