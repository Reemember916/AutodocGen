"""Tests for autodoc.hub.resolver — BiDirectionalResolver.

Verifies:
1. Macro conflict detection (same name, different value)
2. Function conflict detection (same name, different params)
3. Forward-only changes (item only in doc)
4. Backward-only changes (item only in code)
5. Aligned items (identical on both sides)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.logic_ir import (
    CTypeInfo,
    FunctionIR,
    HeaderFileIR,
    MacroIR,
    ParameterIR,
)
from autodoc.hub.resolver import BiDirectionalResolver


class TestBiDirectionalResolver(unittest.TestCase):
    """Integration tests for BiDirectionalResolver."""

    @classmethod
    def setUpClass(cls):
        cls.resolver = BiDirectionalResolver()

    # ── fixture helpers ──────────────────────────────────────────────

    @staticmethod
    def _doc_ir() -> HeaderFileIR:
        """Document-side IR: TIMEOUT=500, 1 function."""
        return HeaderFileIR(
            file_name="test.h",
            macros=[
                MacroIR(name="TIMEOUT", value="500", description="超时阈值"),
            ],
            functions=[
                FunctionIR(
                    name="Control_Process",
                    chinese_name="控制处理流程",
                    description="doc 侧描述",
                    return_type=CTypeInfo(base_type="uint16_t"),
                    parameters=[
                        ParameterIR(
                            name="flag",
                            type_info=CTypeInfo(base_type="uint16_t"),
                            direction="IN",
                            business_meaning="控制标志位",
                        ),
                    ],
                ),
            ],
        )

    @staticmethod
    def _code_ir() -> HeaderFileIR:
        """Code-side IR: TIMEOUT=1000 (conflict!), 1 function with extra param."""
        return HeaderFileIR(
            file_name="test.h",
            macros=[
                MacroIR(name="TIMEOUT", value="1000", description="超时阈值"),
            ],
            functions=[
                FunctionIR(
                    name="Control_Process",
                    chinese_name="控制处理流程",
                    description="doc 侧描述",
                    return_type=CTypeInfo(base_type="uint16_t"),
                    parameters=[
                        ParameterIR(
                            name="flag",
                            type_info=CTypeInfo(base_type="uint16_t"),
                            direction="IN",
                            business_meaning="控制标志位",
                        ),
                        ParameterIR(
                            name="p_New_Fault",
                            type_info=CTypeInfo(
                                base_type="uint16_t", is_pointer=True
                            ),
                            direction="OUT",
                            business_meaning="新增故障码",
                        ),
                    ],
                ),
            ],
        )

    @staticmethod
    def _forward_only_ir() -> HeaderFileIR:
        """IR with an item only in doc side."""
        return HeaderFileIR(
            file_name="test.h",
            macros=[
                MacroIR(name="DOC_ONLY", value="42", description="仅在文档侧"),
            ],
        )

    @staticmethod
    def _backward_only_ir() -> HeaderFileIR:
        """IR with an item only in code side."""
        return HeaderFileIR(
            file_name="test.h",
            macros=[
                MacroIR(name="CODE_ONLY", value="99", description="仅在代码侧"),
            ],
        )

    @staticmethod
    def _aligned_ir() -> HeaderFileIR:
        """IR fully aligned with doc_ir."""
        return HeaderFileIR(
            file_name="test.h",
            macros=[
                MacroIR(name="TIMEOUT", value="500", description="超时阈值"),
            ],
            functions=[
                FunctionIR(
                    name="Control_Process",
                    chinese_name="控制处理流程",
                    description="doc 侧描述",
                    return_type=CTypeInfo(base_type="uint16_t"),
                    parameters=[
                        ParameterIR(
                            name="flag",
                            type_info=CTypeInfo(base_type="uint16_t"),
                            direction="IN",
                            business_meaning="控制标志位",
                        ),
                    ],
                ),
            ],
        )

    @staticmethod
    def _empty_ir() -> HeaderFileIR:
        return HeaderFileIR(file_name="empty.h")

    # ── 1. Macro conflict detection ────────────────────────────────

    def test_macro_conflict_contains_TIMEOUT(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        conflict_names = [c["name"] for c in verdict["CONFLICTS"]]
        self.assertIn("TIMEOUT", conflict_names)

    def test_macro_conflict_kind(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        for c in verdict["CONFLICTS"]:
            if c["name"] == "TIMEOUT":
                self.assertEqual(c["kind"], "macro")

    def test_macro_conflict_doc_value(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        for c in verdict["CONFLICTS"]:
            if c["name"] == "TIMEOUT":
                self.assertEqual(c["doc"]["value"], "500")

    def test_macro_conflict_code_value(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        for c in verdict["CONFLICTS"]:
            if c["name"] == "TIMEOUT":
                self.assertEqual(c["code"]["value"], "1000")

    # ── 2. Function conflict detection (extra param in code) ────────

    def test_function_conflict_contains_Control_Process(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        conflict_names = [c["name"] for c in verdict["CONFLICTS"]]
        self.assertIn("Control_Process", conflict_names)

    def test_function_conflict_kind(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        for c in verdict["CONFLICTS"]:
            if c["name"] == "Control_Process":
                self.assertEqual(c["kind"], "function")

    def test_function_conflict_param_count_differs(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._code_ir())
        for c in verdict["CONFLICTS"]:
            if c["name"] == "Control_Process":
                self.assertEqual(len(c["doc"]["parameters"]), 1)
                self.assertEqual(len(c["code"]["parameters"]), 2)

    # ── 3. Forward-only changes ─────────────────────────────────────

    def test_forward_change_contains_DOC_ONLY(self):
        verdict = self.resolver.compare_ir(
            self._forward_only_ir(), self._empty_ir()
        )
        fwd_names = [f["name"] for f in verdict["FORWARD_CHANGES"]]
        self.assertIn("DOC_ONLY", fwd_names)

    def test_forward_change_code_is_none(self):
        verdict = self.resolver.compare_ir(
            self._forward_only_ir(), self._empty_ir()
        )
        for f in verdict["FORWARD_CHANGES"]:
            if f["name"] == "DOC_ONLY":
                self.assertIsNone(f["code"])

    # ── 4. Backward-only changes ────────────────────────────────────

    def test_backward_change_contains_CODE_ONLY(self):
        verdict = self.resolver.compare_ir(
            self._empty_ir(), self._backward_only_ir()
        )
        bwd_names = [b["name"] for b in verdict["BACKWARD_CHANGES"]]
        self.assertIn("CODE_ONLY", bwd_names)

    def test_backward_change_doc_is_none(self):
        verdict = self.resolver.compare_ir(
            self._empty_ir(), self._backward_only_ir()
        )
        for b in verdict["BACKWARD_CHANGES"]:
            if b["name"] == "CODE_ONLY":
                self.assertIsNone(b["doc"])

    # ── 5. Aligned items ────────────────────────────────────────────

    def test_aligned_contains_TIMEOUT(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._aligned_ir())
        aligned_names = [a["name"] for a in verdict["ALIGNED"]]
        self.assertIn("TIMEOUT", aligned_names)

    def test_aligned_contains_Control_Process(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._aligned_ir())
        aligned_names = [a["name"] for a in verdict["ALIGNED"]]
        self.assertIn("Control_Process", aligned_names)

    def test_aligned_count_when_identical(self):
        verdict = self.resolver.compare_ir(self._doc_ir(), self._aligned_ir())
        # 1 macro + 1 function = 2 aligned
        self.assertEqual(len(verdict["ALIGNED"]), 2)

    # ── 6. Edge: empty IRs ──────────────────────────────────────────

    def test_empty_irs_no_changes(self):
        verdict = self.resolver.compare_ir(self._empty_ir(), self._empty_ir())
        self.assertEqual(len(verdict["FORWARD_CHANGES"]), 0)
        self.assertEqual(len(verdict["BACKWARD_CHANGES"]), 0)
        self.assertEqual(len(verdict["CONFLICTS"]), 0)
        self.assertEqual(len(verdict["ALIGNED"]), 0)

    # ── 7. Four-key structure guarantee ──────────────────────────────

    def test_result_has_four_keys(self):
        verdict = self.resolver.compare_ir(self._empty_ir(), self._empty_ir())
        self.assertEqual(
            set(verdict.keys()),
            {"FORWARD_CHANGES", "BACKWARD_CHANGES", "CONFLICTS", "ALIGNED"},
        )


if __name__ == "__main__":
    unittest.main()