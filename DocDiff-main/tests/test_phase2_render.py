"""Phase-2: change-order metadata, table key-column align, JSON export."""

import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from model.ast import Block, Segment
from render.change_order import (
    _detect_key_column,
    _diff_table_rows,
    changes_to_jsonable,
    render_change_order,
)


class _FakeTable:
    def __init__(self, rows):
        self.rows = [_FakeRow(r) for r in rows]


class _FakeRow:
    def __init__(self, cells):
        self.cells = [_FakeCell(c) for c in cells]


class _FakeCell:
    def __init__(self, text):
        self.text = text


class TableKeyColumnTests(unittest.TestCase):
    def test_detect_key_column_field_name(self):
        self.assertEqual(0, _detect_key_column(["字段名", "类型", "说明"], ("字段名", "名称")))
        self.assertEqual(1, _detect_key_column(["序号", "名称", "值"], ("字段名", "名称")))

    def test_key_column_aligns_reordered_rows(self):
        """行顺序打乱但主键相同：只应保留真正改动的行，而不是整表。"""
        old_tbl = _FakeTable(
            [
                ["字段名", "类型", "说明"],
                ["alpha", "int", "旧说明A"],
                ["beta", "str", "说明B"],
                ["gamma", "bool", "说明C"],
            ]
        )
        new_tbl = _FakeTable(
            [
                ["字段名", "类型", "说明"],
                ["gamma", "bool", "说明C"],
                ["beta", "str", "说明B"],
                ["alpha", "int", "新说明A"],
            ]
        )
        old_block = Block(text="", block_type="table", source="table", raw=old_tbl, path=("k", "_MAIN", 0))
        new_block = Block(text="", block_type="table", source="table", raw=new_tbl, path=("k", "_MAIN", 0))

        old_slice, new_slice = _diff_table_rows(old_block, new_block, use_key_column=True)
        self.assertEqual(0, old_slice["key_column"])
        # 表头 + alpha 行
        self.assertIn(0, old_slice["keep_rows"])
        self.assertIn(1, old_slice["keep_rows"])  # alpha old
        self.assertNotIn(2, old_slice["keep_rows"])  # beta unchanged
        self.assertNotIn(3, old_slice["keep_rows"])  # gamma unchanged
        self.assertIn(0, new_slice["keep_rows"])
        self.assertIn(3, new_slice["keep_rows"])  # alpha new (last after reorder)

    def test_sequence_fallback_without_key_header(self):
        old_tbl = _FakeTable([["列A", "列B"], ["1", "x"], ["2", "y"]])
        new_tbl = _FakeTable([["列A", "列B"], ["1", "x"], ["2", "z"]])
        old_block = Block("", "table", "table", old_tbl, ("k", "_MAIN", 0))
        new_block = Block("", "table", "table", new_tbl, ("k", "_MAIN", 0))
        old_slice, new_slice = _diff_table_rows(old_block, new_block, use_key_column=True)
        self.assertIsNone(old_slice["key_column"])
        self.assertTrue(old_slice["keep_rows"])
        self.assertTrue(new_slice["keep_rows"])


class MetadataRenderTests(unittest.TestCase):
    def test_metadata_written_to_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "co.docx"
            old_seg = Segment(
                "_MAIN",
                [Block("旧", "para", "body", None, ("k", "_MAIN", 0))],
            )
            new_seg = Segment(
                "_MAIN",
                [Block("新", "para", "body", None, ("k", "_MAIN", 0))],
            )
            changes = [
                {
                    "type": "修改",
                    "key": "模块 > 功能",
                    "seg": "_MAIN",
                    "old": old_seg,
                    "new": new_seg,
                }
            ]
            render_change_order(
                changes,
                str(out),
                metadata={
                    "doc_no": "WG-2026-001",
                    "version": "V1.2",
                    "author": "测试员",
                    "date": "2026-07-19",
                },
                problem_start=3,
            )
            doc = Document(str(out))
            texts = [p.text for p in doc.paragraphs]
            joined = "\n".join(texts)
            self.assertIn("软件文档更改说明书", joined)
            self.assertIn("文号：WG-2026-001", joined)
            self.assertIn("版本：V1.2", joined)
            self.assertIn("编制人：测试员", joined)
            self.assertIn("编制日期：2026-07-19", joined)
            self.assertTrue(any("问题3" in t for t in texts))


class JsonableTests(unittest.TestCase):
    def test_changes_to_jsonable(self):
        old_seg = Segment("_MAIN", [Block("old text body", "para", "body", None, ("k", "_MAIN", 0))])
        new_seg = Segment("_MAIN", [Block("new text body", "para", "body", None, ("k", "_MAIN", 0))])
        rows = changes_to_jsonable(
            [
                {
                    "type": "修改",
                    "key": "A > B",
                    "seg": "_MAIN",
                    "match_method": "key",
                    "match_score": 1.0,
                    "old": old_seg,
                    "new": new_seg,
                }
            ]
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("修改", rows[0]["type"])
        self.assertIn("old", rows[0]["old_preview"])
        payload = json.dumps({"changes": rows}, ensure_ascii=False)
        self.assertIn("match_method", payload)


if __name__ == "__main__":
    unittest.main()
