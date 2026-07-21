"""S5: forward Markdown macro extraction."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.forward.extractor import MarkdownExtractor  # noqa: E402


SAMPLE = """
## 模块: demo.h
> 描述: 演示模块

## 宏定义
- MAX_COUNT = 16 — 最大计数
- `BUF_SIZE`: 32

| 宏名 | 取值 | 说明 |
| --- | --- | --- |
| ERR_OK | 0 | 成功码 |

#define DEMO_FLAG 1U // 演示标志

### 函数: Demo_Init
- 中文名: 初始化
- 描述: 初始化演示模块
- 返回值: void
"""


def test_parse_macros_from_markdown():
    ir = MarkdownExtractor().parse(SAMPLE)
    names = {m.name: m for m in ir.macros}
    assert "MAX_COUNT" in names
    assert names["MAX_COUNT"].value.startswith("16")
    assert "BUF_SIZE" in names
    assert names["BUF_SIZE"].value.strip().startswith("32")
    assert "ERR_OK" in names
    assert names["ERR_OK"].value.strip() == "0"
    assert "DEMO_FLAG" in names
    assert names["DEMO_FLAG"].value.startswith("1U")
    assert ir.functions and ir.functions[0].name == "Demo_Init"


def test_empty_md_no_macros():
    ir = MarkdownExtractor().parse("")
    assert ir.macros == []
    assert ir.functions == []
