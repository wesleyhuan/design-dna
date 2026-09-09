"""基因分類法（taxonomy）與欄位詞彙表。

這是整個知識庫的 schema。CLI、Web UI、analyzer、exporter 全部
從這裡取得合法值，改這一個檔就能擴充分類。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    hint: str
    #  匯出到 AGENTS.md 時的區塊排序，小的在前
    order: int


CATEGORIES: tuple[Category, ...] = (
    Category("identity", "設計哲學 / 品牌調性",
             "整體氣質、想給人的第一印象、設計時的取捨原則", 10),
    Category("color", "色彩",
             "色票、語意色、明暗模式、對比策略", 20),
    Category("typography", "字體排版",
             "字族、字級尺標、字重、行高、字距", 30),
    Category("spacing", "間距節奏",
             "間距單位、留白偏好、區塊垂直節奏", 40),
    Category("layout", "佈局與網格",
             "容器寬度、網格系統、對齊方式、頁面骨架", 50),
    Category("responsive", "響應式策略",
             "斷點、行動優先與否、各尺寸的取捨", 60),
    Category("component", "元件慣例",
             "按鈕、表單、卡片、導覽列等的固定做法", 70),
    Category("motion", "動效與互動",
             "轉場曲線、時長、hover/focus 行為、載入狀態", 80),
    Category("imagery", "圖像與插畫",
             "圖片風格、圓角、陰影、icon 系統、比例", 90),
    Category("content", "文案語氣",
             "標題寫法、按鈕用字、錯誤訊息口吻、稱謂", 100),
    Category("a11y", "無障礙",
             "對比要求、鍵盤操作、語意標籤、動效減量", 110),
    Category("stack", "技術棧偏好",
             "框架、CSS 方案、UI 套件、建置工具的選用與理由", 120),
    Category("code", "程式碼慣例",
             "命名、檔案結構、class 撰寫方式、註解密度", 130),
    Category("antipattern", "明確禁止",
             "不想再看到的做法（負面規則，優先級最高）", 140),
)

CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES)
CATEGORY_MAP: dict[str, Category] = {c.key: c for c in CATEGORIES}

# 規則強度：直接對應匯出時的措辭（MUST / SHOULD / MAY）
PRIORITIES: tuple[str, ...] = ("must", "should", "may")
PRIORITY_LABEL = {
    "must": "必須",
    "should": "建議",
    "may": "可選",
}
PRIORITY_WORD = {
    "must": "MUST",
    "should": "SHOULD",
    "may": "MAY",
}

# 生命週期：proposed 由 AI 提出待確認、confirmed 已被使用者採納、
# deprecated 已淘汰（保留在庫中當作歷史，不匯出）
STATUSES: tuple[str, ...] = ("proposed", "confirmed", "deprecated")
STATUS_LABEL = {
    "proposed": "待確認",
    "confirmed": "已確認",
    "deprecated": "已淘汰",
}

# 基因 Markdown body 的標準區塊。解析器本身是通用的（任何 ## 都收），
# 這裡只是給 AI 與 UI 一個共同預設。
SECTIONS: tuple[str, ...] = ("Rule", "Rationale", "Do", "Avoid")
SECTION_LABEL = {
    "Rule": "規則",
    "Rationale": "理由",
    "Do": "正例",
    "Avoid": "反例",
}


def category_label(key: str) -> str:
    cat = CATEGORY_MAP.get(key)
    return cat.label if cat else key


def category_order(key: str) -> int:
    cat = CATEGORY_MAP.get(key)
    return cat.order if cat else 999
