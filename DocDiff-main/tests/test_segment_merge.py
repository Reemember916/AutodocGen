"""Tests for segment merge behavior when entire sections are added/deleted."""

import tempfile
import unittest
from pathlib import Path

from diff.collect_changes import collect_changes
from model.ast import Block, DocumentAST, Section, Segment


def _section(level, title, key, segs: dict) -> Section:
    sec = Section(level=level, title=title, key=key, segments={})
    for seg_id, body in segs.items():
        sec.segments[seg_id] = Segment(
            seg_id=seg_id,
            blocks=[
                Block(
                    text=body,
                    block_type="para",
                    source="body",
                    raw=None,
                    path=(key, seg_id, 0),
                )
            ],
        )
    return sec


def _ast(sections) -> DocumentAST:
    return DocumentAST(sections=list(sections))


class WholeSectionAddWithMultipleSegments(unittest.TestCase):
    """Entirely new section with a) b) c) d) e) should collapse to 1 change."""

    def test_add_collapses_to_one_change(self):
        old = _ast([])
        new = _ast(
            [
                _section(
                    4,
                    "新增功能",
                    "H1 > H2 > H3 > 新增功能",
                    {
                        "_MAIN": "概述",
                        "a": "功能一描述",
                        "b": "功能二描述",
                        "c": "功能三描述",
                        "d": "功能四描述",
                        "e": "功能五描述",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        self.assertEqual(1, len(changes))
        self.assertEqual("新增", changes[0]["type"])
        self.assertEqual("全部", changes[0]["seg"])

    def test_add_collapsed_contains_all_blocks(self):
        old = _ast([])
        new = _ast(
            [
                _section(
                    4,
                    "新增功能",
                    "H1 > 新增功能",
                    {
                        "a": "步骤A",
                        "b": "步骤B",
                        "c": "步骤C",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        blocks = getattr(changes[0]["new"], "blocks", []) or []
        texts = [getattr(b, "text", "") for b in blocks]
        self.assertIn("步骤A", texts)
        self.assertIn("步骤B", texts)
        self.assertIn("步骤C", texts)


class WholeSectionDeleteWithMultipleSegments(unittest.TestCase):
    """Entirely deleted section with a) b) c) d) e) should collapse to 1 change."""

    def test_delete_collapses_to_one_change(self):
        old = _ast(
            [
                _section(
                    4,
                    "删除功能",
                    "H1 > H2 > H3 > 删除功能",
                    {
                        "_MAIN": "概述",
                        "a": "功能一描述",
                        "b": "功能二描述",
                        "c": "功能三描述",
                    },
                ),
            ]
        )
        new = _ast([])
        changes = collect_changes(old, new)
        self.assertEqual(1, len(changes))
        self.assertEqual("删除", changes[0]["type"])
        self.assertEqual("全部", changes[0]["seg"])

    def test_delete_collapsed_contains_all_blocks(self):
        old = _ast(
            [
                _section(
                    4,
                    "旧功能",
                    "H1 > 旧功能",
                    {
                        "a": "旧步骤A",
                        "b": "旧步骤B",
                    },
                ),
            ]
        )
        new = _ast([])
        changes = collect_changes(old, new)
        blocks = getattr(changes[0]["old"], "blocks", []) or []
        texts = [getattr(b, "text", "") for b in blocks]
        self.assertIn("旧步骤A", texts)
        self.assertIn("旧步骤B", texts)


class SingleMainSegmentUnchanged(unittest.TestCase):
    """Section with only _MAIN should keep original behavior (no collapse)."""

    def test_add_single_main(self):
        old = _ast([])
        new = _ast(
            [
                _section(4, "新增", "H1 > 新增", {"_MAIN": "正文内容"}),
            ]
        )
        changes = collect_changes(old, new)
        self.assertEqual(1, len(changes))
        self.assertEqual("新增", changes[0]["type"])
        self.assertEqual("_MAIN", changes[0]["seg"])

    def test_delete_single_main(self):
        old = _ast(
            [
                _section(4, "删除", "H1 > 删除", {"_MAIN": "正文内容"}),
            ]
        )
        new = _ast([])
        changes = collect_changes(old, new)
        self.assertEqual(1, len(changes))
        self.assertEqual("删除", changes[0]["type"])
        self.assertEqual("_MAIN", changes[0]["seg"])


class PartialSegmentChangesWithinPairedSection(unittest.TestCase):
    """Individual segment add/delete within a paired section should remain."""

    def test_partial_add_one_segment(self):
        old = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > H2 > 功能",
                    {
                        "a": "步骤A",
                        "b": "步骤B",
                    },
                ),
            ]
        )
        new = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > H2 > 功能",
                    {
                        "a": "步骤A",
                        "b": "步骤B",
                        "c": "步骤C（新增）",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        added = [c for c in changes if c["type"] == "新增"]
        self.assertEqual(1, len(added))
        self.assertEqual("c", added[0]["seg"])

    def test_partial_delete_one_segment(self):
        old = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > H2 > 功能",
                    {
                        "a": "步骤A",
                        "b": "步骤B（将被删）",
                        "c": "步骤C",
                    },
                ),
            ]
        )
        new = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > H2 > 功能",
                    {
                        "a": "步骤A",
                        "c": "步骤C",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        deleted = [c for c in changes if c["type"] == "删除"]
        self.assertEqual(1, len(deleted))
        self.assertEqual("b", deleted[0]["seg"])

    def test_modify_segment_keeps_seg_id(self):
        old = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > 功能",
                    {
                        "a": "旧内容",
                        "b": "不变内容",
                    },
                ),
            ]
        )
        new = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > 功能",
                    {
                        "a": "新内容",
                        "b": "不变内容",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        modified = [c for c in changes if c["type"] == "修改"]
        self.assertEqual(1, len(modified))
        self.assertEqual("a", modified[0]["seg"])


class RegressionNoFalseCollapse(unittest.TestCase):
    """Ensure no false collapse when sections are paired but content differs."""

    def test_paired_section_with_different_segments_not_collapsed(self):
        old = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > 功能",
                    {
                        "a": "旧A",
                        "b": "旧B",
                    },
                ),
            ]
        )
        new = _ast(
            [
                _section(
                    4,
                    "功能",
                    "H1 > 功能",
                    {
                        "a": "新A",
                        "b": "新B",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        self.assertEqual(2, len(changes))
        for c in changes:
            self.assertIn(c["seg"], {"a", "b"})
            self.assertEqual("修改", c["type"])


class MultipleNewSections(unittest.TestCase):
    """Multiple new sections each with segments should each collapse independently."""

    def test_two_new_sections_both_collapsed(self):
        old = _ast([])
        new = _ast(
            [
                _section(
                    4,
                    "功能A",
                    "H1 > 功能A",
                    {
                        "a": "A1",
                        "b": "A2",
                        "c": "A3",
                    },
                ),
                _section(
                    4,
                    "功能B",
                    "H1 > 功能B",
                    {
                        "a": "B1",
                        "b": "B2",
                    },
                ),
            ]
        )
        changes = collect_changes(old, new)
        self.assertEqual(2, len(changes))
        for c in changes:
            self.assertEqual("新增", c["type"])
            self.assertEqual("全部", c["seg"])


if __name__ == "__main__":
    unittest.main()
