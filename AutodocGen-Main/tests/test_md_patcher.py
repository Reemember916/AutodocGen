"""Tests for autodoc.backward.md_patcher — MarkdownPatcher.

Verifies:
1. New parameters are inserted into the table
2. Human-written context text before/after the table is preserved
3. Type changes are reflected in the patched table
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.logic_ir import (
    CTypeInfo,
    FunctionIR,
    HeaderFileIR,
    ParameterIR,
)
from autodoc.backward.md_patcher import MarkdownPatcher


# ── Hardcoded fixture: old Markdown document ─────────────────────────────

OLD_MD = """## 模块: Control_Module.h

> 描述: 控制模块接口头文件

### 函数: Control_Process

- 中文名: 控制处理流程
- 描述: 根据输入标志位执行控制逻辑，并通过指针参数输出结果
- 返回值: uint16_t

【人工备注】此处是工程师手写的业务背景说明：
本函数用于处理上层下发的控制指令，包含超时检测和异常上报逻辑，
请注意 flag 参数的低 4 位为指令编码，高 4 位为优先级。

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| flag | uint16_t | IN | 控制标志位 |
| p_out | uint16_t* | OUT | 输出结果指针 |

【人工备注】表格结束后的补充说明：
p_out 指向的缓冲区必须由调用方预先分配，至少 4 字节。
"""


# ── Helper: build updated IR ────────────────────────────────────────────


def _build_updated_ir() -> HeaderFileIR:
    """Build an updated IR with:
    - flag type changed from uint16_t → uint32_t
    - p_out unchanged
    - new_flag added (new parameter)
    """
    return HeaderFileIR(
        file_name="Control_Module.h",
        brief_description="控制模块接口头文件",
        macros=[],
        functions=[
            FunctionIR(
                name="Control_Process",
                chinese_name="控制处理流程",
                description="根据输入标志位执行控制逻辑",
                return_type=CTypeInfo(base_type="uint16_t"),
                parameters=[
                    ParameterIR(
                        name="flag",
                        type_info=CTypeInfo(base_type="uint32_t", is_pointer=False),
                        direction="IN",
                        business_meaning="控制标志位（含优先级编码）",
                    ),
                    ParameterIR(
                        name="new_flag",
                        type_info=CTypeInfo(base_type="uint16_t", is_pointer=False),
                        direction="IN",
                        business_meaning="新增扩展标志位",
                    ),
                    ParameterIR(
                        name="p_out",
                        type_info=CTypeInfo(base_type="uint16_t", is_pointer=True),
                        direction="OUT",
                        business_meaning="输出结果指针",
                    ),
                ],
            )
        ],
    )


class TestMarkdownPatcher(unittest.TestCase):
    """Integration tests for MarkdownPatcher."""

    @classmethod
    def setUpClass(cls):
        cls.patcher = MarkdownPatcher()
        cls.updated_ir = _build_updated_ir()
        cls.patched = cls.patcher.patch_header(OLD_MD, cls.updated_ir)

    # ── 1. New parameter appears in the patched table ────────────────

    def test_new_parameter_row_present(self):
        self.assertIn("new_flag", self.patched)

    def test_new_parameter_business_meaning(self):
        self.assertIn("新增扩展标志位", self.patched)

    # ── 2. Human-written context preserved ───────────────────────────

    def test_pre_table_human_text_preserved(self):
        self.assertIn("本函数用于处理上层下发的控制指令", self.patched)

    def test_pre_table_low_4_bit_reference(self):
        self.assertIn("低 4 位为指令编码", self.patched)

    def test_post_table_human_text_preserved(self):
        self.assertIn("p_out 指向的缓冲区必须由调用方预先分配", self.patched)

    def test_post_table_4_bytes_reference(self):
        self.assertIn("至少 4 字节", self.patched)

    # ── 3. Type change reflected ─────────────────────────────────────

    def test_updated_type_in_table(self):
        self.assertIn("uint32_t", self.patched)

    def test_old_type_removed_from_table(self):
        self.assertNotIn("| flag | uint16_t ", self.patched)

    # ── 4. Structural integrity ──────────────────────────────────────

    def test_function_heading_preserved(self):
        self.assertIn("### 函数: Control_Process", self.patched)

    def test_module_heading_preserved(self):
        self.assertIn("## 模块: Control_Module.h", self.patched)

    def test_markdown_table_header_present(self):
        self.assertIn("| 参数名 | 类型 | 方向 | 业务含义 |", self.patched)

    def test_table_separator_present(self):
        self.assertIn("|---|---|---|---|", self.patched)

    def test_overall_length_sanity(self):
        """Patched document should be longer than original (new params)."""
        self.assertGreater(len(self.patched), len(OLD_MD))


if __name__ == "__main__":
    unittest.main()