"""Design DNA — 可攜式的個人網頁設計風格知識庫。

核心概念：把「設計習慣與風格」拆成一顆顆 *gene*（基因），
每顆基因是一個帶 frontmatter 的 Markdown 檔（LLM wiki 節點），
彼此以 [[wikilink]] 互連。整個 dna/ 目錄是純文字，
複製到任何地方、餵給任何 coding agent 都能用。
"""

__version__ = "0.1.0"

DNA_DIR_NAME = "dna"
BUILD_DIR_NAME = "build"
