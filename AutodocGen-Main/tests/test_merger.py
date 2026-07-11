"""测试 autodoc.forward.merger — 保护区无损合并引擎。"""

from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.forward.merger import UserCodeMerger


class TestUserCodeMerger(unittest.TestCase):
    """UserCodeMerger 单元测试。"""

    def setUp(self):
        self.merger = UserCodeMerger()

    # ── test_extract_blocks ────────────────────────────────────────

    def test_extract_blocks(self):
        """断言能从旧代码中正确提取两个保护区，且多行格式不乱。"""
        old_code = r"""#include "APP_Config.h"

void Control_Refuel_Process(Uint16 cmd)
{
    /* USER CODE BEGIN: InitVars */
    Uint16 l_fuel_qty = 0;
    Uint16 l_status = 0;
    /* USER CODE END: InitVars */

    l_fuel_qty = ReadFuelSensor();

    /* USER CODE BEGIN: ControlLogic */
    if (cmd == 0x01) {
        StartPump();
        l_status = 1;
    } else {
        StopPump();
        l_status = 0;
    }
    /* USER CODE END: ControlLogic */
}
"""
        blocks = self.merger.extract(old_code)

        # 断言提取了 2 个区块
        self.assertEqual(len(blocks), 2, f"期望 2 个区块，实际 {len(blocks)}")
        self.assertIn("InitVars", blocks)
        self.assertIn("ControlLogic", blocks)

        # 断言 InitVars 内容保留多行和缩进
        self.assertIn("Uint16 l_fuel_qty = 0;", blocks["InitVars"])
        self.assertIn("Uint16 l_status = 0;", blocks["InitVars"])
        self.assertIn("\n", blocks["InitVars"], "InitVars 应保留换行符")

        # 断言 ControlLogic 内容保留多行和缩进
        self.assertIn("if (cmd == 0x01)", blocks["ControlLogic"])
        self.assertIn("StartPump();", blocks["ControlLogic"])
        self.assertIn("StopPump();", blocks["ControlLogic"])

    # ── test_merge_blocks ──────────────────────────────────────────

    def test_merge_blocks(self):
        """断言能将提取出的块精准注入到新骨架代码中，且标签完好。"""
        # 旧代码（含手写逻辑）
        old_code = r"""void Control_Refuel_Process(Uint16 cmd)
{
    /* USER CODE BEGIN: InitVars */
    Uint16 l_fuel_qty = 0;
    /* USER CODE END: InitVars */

    /* USER CODE BEGIN: ControlLogic */
    if (cmd == 0x01) {
        StartPump();
    }
    /* USER CODE END: ControlLogic */
}
"""
        # 新骨架代码（保护区为空）
        new_skel = r"""void Control_Refuel_Process(Uint16 cmd)
{
    /* USER CODE BEGIN: InitVars */
    /* USER CODE END: InitVars */

    /* USER CODE BEGIN: ControlLogic */
    /* USER CODE END: ControlLogic */
}
"""
        user_blocks = self.merger.extract(old_code)
        merged = self.merger.merge(new_skel, user_blocks)

        # 断言 BEGIN/END 标签完好保留
        self.assertIn("/* USER CODE BEGIN: InitVars */", merged)
        self.assertIn("/* USER CODE END: InitVars */", merged)
        self.assertIn("/* USER CODE BEGIN: ControlLogic */", merged)
        self.assertIn("/* USER CODE END: ControlLogic */", merged)

        # 断言手写代码被注入到正确位置
        self.assertIn("Uint16 l_fuel_qty = 0;", merged)
        self.assertIn("if (cmd == 0x01)", merged)
        self.assertIn("StartPump();", merged)

        # 断言 InitVars 的代码在 BEGIN 和 END 之间
        init_pos = merged.index("/* USER CODE BEGIN: InitVars */")
        init_end = merged.index("/* USER CODE END: InitVars */")
        init_content = merged[init_pos:init_end]
        self.assertIn("Uint16 l_fuel_qty = 0;", init_content)

        # 断言 ControlLogic 的代码在 BEGIN 和 END 之间
        ctrl_pos = merged.index("/* USER CODE BEGIN: ControlLogic */")
        ctrl_end = merged.index("/* USER CODE END: ControlLogic */")
        ctrl_content = merged[ctrl_pos:ctrl_end]
        self.assertIn("if (cmd == 0x01)", ctrl_content)

    # ── test_orphan_block ──────────────────────────────────────────

    def test_orphan_block(self):
        """断言旧代码有 3 个块而新骨架只有 2 个时，不崩溃，只合并 2 个。"""
        old_code = r"""void Demo(void)
{
    /* USER CODE BEGIN: InitVars */
    int x = 0;
    /* USER CODE END: InitVars */

    /* USER CODE BEGIN: ControlLogic */
    x = x + 1;
    /* USER CODE END: ControlLogic */

    /* USER CODE BEGIN: DebugOutput */
    printf("x=%d\n", x);
    /* USER CODE END: DebugOutput */
}
"""
        # 新骨架中删除了 DebugOutput 区块
        new_skel = r"""void Demo(void)
{
    /* USER CODE BEGIN: InitVars */
    /* USER CODE END: InitVars */

    /* USER CODE BEGIN: ControlLogic */
    /* USER CODE END: ControlLogic */
}
"""
        user_blocks = self.merger.extract(old_code)

        # 捕获 stderr 中的 warning
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr_capture
        try:
            merged = self.merger.merge(new_skel, user_blocks)
        finally:
            sys.stderr = old_stderr

        warning_output = stderr_capture.getvalue()

        # 断言不崩溃，成功返回合并结果
        self.assertIsInstance(merged, str)
        self.assertGreater(len(merged), 0)

        # 断言 InitVars 和 ControlLogic 被正确合并
        self.assertIn("int x = 0;", merged)
        self.assertIn("x = x + 1;", merged)

        # 断言 DebugOutput 未出现在合并结果中
        self.assertNotIn("printf", merged)
        self.assertNotIn("DebugOutput", merged)

        # 断言打印了 WARNING
        self.assertIn("WARNING", warning_output)
        self.assertIn("DebugOutput", warning_output)

    # ── test_empty_source ──────────────────────────────────────────

    def test_empty_source(self):
        """空输入不崩溃。"""
        self.assertEqual(self.merger.extract(""), {})
        self.assertEqual(self.merger.extract(None), {})
        self.assertEqual(self.merger.merge("", {}), "")

    # ── test_idempotent_merge ──────────────────────────────────────

    def test_idempotent_merge(self):
        """对已经合并过的代码再次提取+合并，结果不变。"""
        old_code = r"""void F(void)
{
    /* USER CODE BEGIN: MyBlock */
    int y = 42;
    /* USER CODE END: MyBlock */
}
"""
        new_skel = r"""void F(void)
{
    /* USER CODE BEGIN: MyBlock */
    /* USER CODE END: MyBlock */
}
"""
        blocks = self.merger.extract(old_code)
        merged1 = self.merger.merge(new_skel, blocks)
        blocks2 = self.merger.extract(merged1)
        merged2 = self.merger.merge(new_skel, blocks2)

        self.assertEqual(merged1, merged2)

    # ── test_crlf_line_endings ─────────────────────────────────────

    def test_crlf_line_endings(self):
        """Windows 换行符 \\r\\n 正确处理。"""
        old_code = (
            "void F(void)\r\n"
            "{\r\n"
            "    /* USER CODE BEGIN: Block1 */\r\n"
            "    int a = 1;\r\n"
            "    /* USER CODE END: Block1 */\r\n"
            "}\r\n"
        )
        blocks = self.merger.extract(old_code)
        self.assertIn("Block1", blocks)
        self.assertIn("int a = 1;", blocks["Block1"])


if __name__ == "__main__":
    unittest.main()