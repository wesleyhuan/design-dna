---
id: spacing-rhythm
title: 8px 間距尺標
category: spacing
priority: must
status: confirmed
confidence: 0.85
updated: '2026-09-08'
tags:
- 間距
- token
related:
- type-scale
- design-token-first
evidence:
- source: 20260908-005028-sample-site
  detail: 間距值集中在 8 / 16 / 24 / 32 / 48px，唯一的例外是按鈕的 12px 垂直內距
---

## Rule

所有 margin / padding / gap 只能取 `4, 8, 16, 24, 32, 48` px。

唯一允許的例外：按鈕的垂直內距 `12px`（配 `24px` 水平內距）。
需要其他值時，先問「是不是版面結構有問題」，而不是開新的間距值。

## Rationale

這是一組 8px 基準、只在最小端補 4px 的尺標。限制值域讓垂直節奏自動對齊，
也讓不同人（或不同 agent）寫出來的區塊間距不會各憑感覺。

## Do

```css
.stack { display: flex; flex-direction: column; gap: 16px; }
.section { padding: 48px 24px; }
```

## Avoid

```css
.card { padding: 20px; margin-bottom: 18px; }
```
