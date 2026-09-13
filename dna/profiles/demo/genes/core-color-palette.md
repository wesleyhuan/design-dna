---
id: core-color-palette
title: 核心色票
category: color
priority: must
status: confirmed
confidence: 0.9
updated: '2026-09-08'
tags:
- 色彩
- token
related:
- semantic-color-roles
- design-token-first
evidence:
- source: 20260913-144030-sample-site
  detail: '#2563EB / #0F172A / #64748B / #FFFFFF 跨 4 個檔案穩定出現，且都有對應的 CSS 變數'
---

## Rule

固定使用這組色票，不要臨時調色：

| 角色 | 色碼 | 用途 |
| --- | --- | --- |
| primary | `#2563EB` | 主要 CTA、連結、選取狀態 |
| primary-dark | `#1D4ED8` | 只用於 primary 的 hover / active |
| ink | `#0F172A` | 主文字 |
| muted | `#64748B` | 次要文字、說明文字 |
| surface | `#FFFFFF` | 卡片與主要背景 |
| surface-alt | `#F8FAFC` | 區塊分隔、淺色底 |
| danger | `#DC2626` | 錯誤與破壞性操作 |
| success | `#16A34A` | 成功狀態 |

## Rationale

這是一組 slate 中性色 + 單一藍色強調的配置。藍色只出現在需要被點擊的東西上，
所以畫面上「藍色 = 可互動」這件事是可預測的。中性色全部落在 slate 色階，
不混其他灰，冷暖才不會打架。

## Do

```css
.btn-primary { background: var(--color-primary); color: var(--color-surface); }
.hint { color: var(--color-muted); }
```

## Avoid

```css
/* 不要另外發明藍色 */
.btn { background: #3B82F6; }
/* 不要用純黑當文字色 */
body { color: #000000; }
```

語意角色的細節見 [[semantic-color-roles]]。
