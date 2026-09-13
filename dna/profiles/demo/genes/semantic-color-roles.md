---
id: semantic-color-roles
title: 色彩用語意命名，不用外觀命名
category: color
priority: should
status: confirmed
confidence: 0.8
updated: '2026-09-08'
tags:
- 色彩
- 命名
related:
- core-color-palette
- design-token-first
evidence:
- source: 20260913-144030-sample-site
  detail: 19 個 CSS 變數全部是 --color-primary / --color-ink 這類語意名，沒有 --blue-500
---

## Rule

CSS 變數用**用途**命名（`--color-primary`、`--color-ink`、`--color-danger`），
不要用**外觀**命名（`--blue-500`、`--gray-dark`）。

## Rationale

語意命名讓換色不用改任何使用端。之後要做深色模式，只要換一組變數值，
所有元件自動跟著走；用 `--blue-500` 的話，深色模式下的藍就會卡在名字裡。

## Do

```css
:root { --color-danger: #DC2626; }
.alert { border-color: var(--color-danger); }
```

## Avoid

```css
:root { --red-600: #DC2626; }
.alert { border-color: var(--red-600); }
```
