---
id: semantic-html-first
title: 先用對的 HTML 標籤，再談樣式
category: code
priority: should
status: proposed
confidence: 0.9
updated: '2026-09-08'
tags:
- HTML
- 無障礙
related:
- contrast-minimum
evidence:
- source: builtin
  detail: 工具內建的起手式，不是從你的資料抽出來的。確認前請先確定你同意。
---

## Rule

會被點的東西：導航用 `<a href>`，觸發動作用 `<button>`。
一律不要用 `<div onclick>`。

版面骨架用 `<header> <nav> <main> <aside> <footer>`，
標題層級 `h1`~`h6` 依照文件結構排，不要為了字級大小跳級。

## Rationale

語意標籤自帶鍵盤操作、焦點順序、螢幕閱讀器語意。用 `div` 重做這些，
你要自己補 `tabindex`、`role`、`aria-*`、Enter/Space 鍵盤處理，
而且幾乎一定會漏掉其中一項。

用對標籤是成本最低的無障礙投資 —— 它不用額外寫任何程式碼。

## Do

```html
<nav>
  <a href="/docs">文件</a>
  <button type="button" onclick="openMenu()">選單</button>
</nav>
```

## Avoid

```html
<div class="nav">
  <div class="link" onclick="location.href='/docs'">文件</div>
  <div class="btn" onclick="openMenu()">選單</div>
</div>
```
