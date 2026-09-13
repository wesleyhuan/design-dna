---
id: utility-with-named-components
title: Tailwind 與具名 class 的分工
category: code
priority: should
status: confirmed
confidence: 0.62
updated: '2026-09-08'
tags:
- Tailwind
- 命名
related:
- design-token-first
evidence:
- source: 20260913-144030-sample-site
  detail: JSX 同時出現 Tailwind utility（flex gap-4 px-6）與具名 class（btn-primary、section）
- source: 20260913-144030-sample-site
  detail: CSS 選擇器命名以 kebab-case 為主（7 次），卡片使用 BEM（card__title / card--featured，3 次）
---

## Rule

兩套並用，分工如下：

- **版面配置**（flex、grid、gap、padding）用 Tailwind utility 直接寫在 JSX 上
- **可重複的視覺元件**（按鈕、卡片、導覽列）用具名 class，樣式寫在 CSS 檔

具名 class 用 kebab-case；元件有內部結構時才升級成 BEM
（`card__title`、`card--featured`）。

## Rationale

版面是一次性的，寫在 JSX 上最好讀；元件是會重複的，抽出來才不會到處長出變體。

信心度偏低：來源專案的樣本量小，這條比較像是觀察到的傾向而不是明確的決定。
如果實際上有更明確的規則（例如「元件一律用 shadcn」），請直接改掉這條。

## Do

```jsx
<section className="section flex flex-col gap-4">
  <a className="btn-primary" href="/start">開始使用</a>
</section>
```

## Avoid

```jsx
<a className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700">
  開始使用
</a>
```
