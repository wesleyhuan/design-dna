---
id: reduced-motion
title: 尊重 prefers-reduced-motion
category: a11y
priority: must
status: proposed
confidence: 0.95
updated: '2026-09-08'
tags:
- 無障礙
- 動效
related:
- contrast-minimum
evidence:
- source: builtin
  detail: 工具內建的起手式，不是從你的資料抽出來的。確認前請先確定你同意。
---

## Rule

每個專案的全域樣式都要包含這段，位置放在樣式表最後：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## Rationale

前庭功能障礙的使用者會因為位移動畫而暈眩。這是作業系統層級的明確表態，
不照做等於忽略使用者已經講出口的需求。

用 `0.01ms` 而不是 `none`，是為了讓 `transitionend` 事件照常觸發，
不會讓依賴它的 JS 邏輯卡在半路。

## Do

把上面那段當成專案 reset 的一部分，跟 `box-sizing: border-box` 寫在一起。

## Avoid

```css
/* 只關掉部分元件，漏掉的那些才是會出事的 */
@media (prefers-reduced-motion: reduce) { .hero { animation: none; } }
```
