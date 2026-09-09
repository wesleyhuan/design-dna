---
id: contrast-minimum
title: 文字對比至少 4.5:1
category: a11y
priority: must
status: proposed
confidence: 0.95
updated: '2026-09-08'
tags:
- 無障礙
- 色彩
related:
- reduced-motion
evidence:
- source: builtin
  detail: 工具內建的起手式，不是從你的資料抽出來的。確認前請先確定你同意。
---

## Rule

- 一般內文與背景的對比至少 **4.5:1**
- 大字（18px 以上粗體，或 24px 以上）至少 **3:1**
- 表單邊框、icon 等非文字的圖形元素至少 **3:1**

決定任何「淺灰色說明文字」之前，先算對比。

## Rationale

這是 WCAG 2.1 AA 的門檻，也是低視力與強光下使用手機的人能不能讀到內容的分界。
設計稿在你的高階螢幕上看起來沒問題，不代表在別人的螢幕上讀得到。

最常見的違規是「次要文字」—— 為了視覺層次把灰階拉太淡。
要做層次，改用字級與字重，不要靠犧牲對比。

## Do

```css
/* #64748B on #FFFFFF = 4.76:1，剛好過關 */
.hint { color: #64748B; }
```

## Avoid

```css
/* #94A3B8 on #FFFFFF = 2.56:1，不合格 */
.hint { color: #94A3B8; }
```
