---
id: design-token-first
title: 先定 token 再寫元件
category: code
priority: must
status: confirmed
confidence: 0.85
updated: '2026-09-08'
tags:
- 流程
- CSS
related:
- core-color-palette
- spacing-rhythm
- type-scale
evidence:
- source: 20260908-005028-sample-site
  detail: 專案分成 tokens.css（19 個變數）與 components.css，元件檔沒有任何硬編碼的新值
---

## Rule

樣式分兩層，順序不能反：

1. `tokens.css` — 只有 `:root` 變數（色彩、間距、圓角、陰影、緩動曲線）
2. `components.css` — 只能引用 token，不得引入新的原始值

寫元件時如果找不到適用的 token，先回頭決定要不要新增 token，
而不是就地寫死一個值。

## Rationale

這條規則是上面所有數值規則之所以守得住的原因。
一旦允許元件檔硬編碼，尺標就會慢慢腐蝕，半年後回頭看會有 11 種灰。

## Do

```css
/* components.css */
.card { padding: var(--space-4); border-radius: var(--radius-md); }
```

## Avoid

```css
/* components.css */
.card { padding: 24px; border-radius: 12px; }
```
