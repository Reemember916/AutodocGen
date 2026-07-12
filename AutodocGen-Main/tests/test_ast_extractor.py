"""Tests for autodoc.backward.ast_extractor — CAsTExtractor.

Verifies:
1. Macro fact extraction (name, value, description)
2. Pointer type recognition (CTypeInfo.is_pointer)
3. Semantic lossless backfill (business_meaning from comment)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.backward.ast_extractor import CAsTExtractor


# ── Hardcoded C header fixture ──────────────────────────────────────────

C_HEADER_FIXTURE = """/*
 * 最大重试次数定义
 */
#define MAX_RETRY 3

/*
 * [函数中文名] 控制处理流程
 * [功能描述] 根据输入标志位执行控制逻辑，并通过指针参数输出结果
 * [输入参数说明]
 * - flag: [业务含义] 控制标志位
 * [输出参数说明]
 * - p_out: [业务含义] 输出结果指针
 */
extern uint16_t Control_Process(uint16_t flag, uint16_t * p_out);
"""


class TestCAsTExtractor(unittest.TestCase):
    """Integration tests for CAsTExtractor against a realistic C header."""

    @classmethod
    def setUpClass(cls):
        cls.extractor = CAsTExtractor()
        cls.ir = cls.extractor.extract_header(C_HEADER_FIXTURE, "test_header.h")

    # ── 1. Macro fact extraction ──────────────────────────────────────

    def test_macro_count(self):
        self.assertGreaterEqual(len(self.ir.macros), 1)

    def test_macro_name(self):
        macro = self.ir.macros[0]
        self.assertEqual(macro.name, "MAX_RETRY")

    def test_macro_value(self):
        macro = self.ir.macros[0]
        self.assertEqual(macro.value, "3")

    def test_macro_description(self):
        macro = self.ir.macros[0]
        self.assertIn("最大重试次数", macro.description)

    # ── 2. Pointer type recognition ───────────────────────────────────

    def test_function_count(self):
        self.assertGreaterEqual(len(self.ir.functions), 1)

    def test_function_name(self):
        fn = self.ir.functions[0]
        self.assertEqual(fn.name, "Control_Process")

    def test_pointer_parameter_detected(self):
        fn = self.ir.functions[0]
        p_out = next((p for p in fn.parameters if p.name == "p_out"), None)
        self.assertIsNotNone(p_out, "p_out parameter not found")
        self.assertTrue(
            p_out.type_info.is_pointer,
            f"Expected p_out.is_pointer=True, got {p_out.type_info.is_pointer}",
        )

    def test_non_pointer_parameter(self):
        fn = self.ir.functions[0]
        flag = next((p for p in fn.parameters if p.name == "flag"), None)
        self.assertIsNotNone(flag, "flag parameter not found")
        self.assertFalse(flag.type_info.is_pointer)

    # ── 3. Semantic lossless backfill ─────────────────────────────────

    def test_chinese_name_extracted(self):
        fn = self.ir.functions[0]
        self.assertEqual(fn.chinese_name, "控制处理流程")

    def test_description_extracted(self):
        fn = self.ir.functions[0]
        self.assertIn("控制逻辑", fn.description)

    def test_flag_business_meaning(self):
        fn = self.ir.functions[0]
        flag = next((p for p in fn.parameters if p.name == "flag"), None)
        self.assertIsNotNone(flag)
        self.assertEqual(flag.business_meaning, "控制标志位")

    def test_p_out_business_meaning(self):
        fn = self.ir.functions[0]
        p_out = next((p for p in fn.parameters if p.name == "p_out"), None)
        self.assertIsNotNone(p_out)
        self.assertEqual(p_out.business_meaning, "输出结果指针")


if __name__ == "__main__":
    unittest.main()