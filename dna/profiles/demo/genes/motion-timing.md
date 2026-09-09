---
id: motion-timing
title: 動效只有一組時長與曲線
category: motion
priority: should
status: confirmed
confidence: 0.78
updated: '2026-09-08'
tags:
- 動效
related:
- surface-elevation
- reduced-motion
evidence:
- source: 20260908-005028-sample-site
  detail: 所有 transition 都是 200ms cubic-bezier(0.16, 1, 0.3, 1)，沒有第二組
---

## Rule

所有轉場一律 `200ms cubic-bezier(0.16, 1, 0.3, 1)`。
只對會變的屬性做轉場（`background`、`box-shadow`、`transform`、`opacity`），
**不要寫 `transition: all`。**

## Rationale

這條曲線起步快、尾巴長，收尾時看起來像自然減速。200ms 短到不擋操作、
長到能被眼睛看見。統一一組值，整站的手感才會一致。
`transition: all` 會連 layout 屬性一起補間，是掉幀的主要來源。

## Do

```css
.card { transition: box-shadow 200ms cubic-bezier(0.16, 1, 0.3, 1); }
```

## Avoid

```css
.card { transition: all 0.3s ease-in-out; }
```

減量偏好的處理見 [[reduced-motion]]。
