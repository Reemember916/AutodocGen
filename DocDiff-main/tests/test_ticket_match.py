"""方案 A：问题单台账 → 自动匹配到 diff 变更。"""

import unittest

from tickets.match import (
    apply_matched_tickets,
    match_report,
    match_tickets_to_changes,
)
from tickets.tickets import Ticket
from model.ast import Block, Segment


def _para_seg(text: str, seg_id: str = "_MAIN") -> Segment:
    return Segment(
        seg_id=seg_id,
        blocks=[Block(text, "para", "body", None, ("k", seg_id, 0))],
    )


class MatchEngineTests(unittest.TestCase):
    def test_match_by_doc_id_in_ticket_title(self):
        changes = [
            {
                "type": "修改",
                "key": "模块 > IFBITStateUpdate（D/R_SDD01_001_003）",
                "seg": "c",
                "old": _para_seg("Uint16"),
                "new": _para_seg("Uint32"),
            },
            {
                "type": "修改",
                "key": "模块 > 其它（D/R_SDD01_099_001）",
                "seg": "a",
                "old": _para_seg("aaa"),
                "new": _para_seg("bbb"),
            },
        ]
        tickets = {
            1: Ticket(1, "IFBIT 状态更新 D/R_SDD01_001_003 类型变更", "DFKS112-WT-01"),
            2: Ticket(2, "无关的需求说明", "DFKS112-WT-02"),
        }
        matches = match_tickets_to_changes(changes, tickets)
        by_t = {m.ticket_seq: m for m in matches}
        self.assertIn(1, by_t)
        self.assertEqual(0, by_t[1].change_index)
        self.assertGreaterEqual(by_t[1].score, 0.9)
        self.assertIn("doc_id", by_t[1].reason)

    def test_match_by_function_name(self):
        changes = [
            {
                "type": "修改",
                "key": "src/control.c",
                "seg": "ProcessRedundancy",
                "old_text": "int ProcessRedundancy(void) { return 0; }",
                "new_text": "int ProcessRedundancy(void) { return 1; }",
            },
            {
                "type": "修改",
                "key": "src/other.c",
                "seg": "Helper",
                "old_text": "void Helper(void) {}",
                "new_text": "void Helper(void) {;}",
            },
        ]
        tickets = {
            3: Ticket(3, "ProcessRedundancy 函数冗余优化", "DFKS112-WT-03"),
        }
        matches = match_tickets_to_changes(changes, tickets)
        self.assertEqual(1, len(matches))
        self.assertEqual(0, matches[0].change_index)
        self.assertEqual(3, matches[0].ticket_seq)
        self.assertIn("symbol", matches[0].reason)

    def test_apply_reorders_by_ticket_seq(self):
        # diff 顺序与问题单序号相反
        changes = [
            {
                "type": "修改",
                "key": "B（D/R_BB_002）",
                "seg": "_MAIN",
                "old": _para_seg("b1"),
                "new": _para_seg("b2"),
            },
            {
                "type": "修改",
                "key": "A（D/R_AA_001）",
                "seg": "_MAIN",
                "old": _para_seg("a1"),
                "new": _para_seg("a2"),
            },
        ]
        tickets = {
            1: Ticket(1, "修改 A D/R_AA_001", "DFKS112-WT-01"),
            2: Ticket(2, "修改 B D/R_BB_002", "DFKS112-WT-02"),
        }
        out = apply_matched_tickets(
            changes,
            tickets,
            ticket_prefix="DFKS112-WT",
            reorder=True,
        )
        self.assertEqual(2, len(out))
        # 问题1 应对 A
        self.assertIn("D/R_AA_001", out[0]["key"])
        self.assertEqual("DFKS112-WT-01", out[0]["ticket_no"])
        self.assertEqual("auto", out[0]["ticket_match_method"])
        self.assertIn("D/R_BB_002", out[1]["key"])
        self.assertEqual("DFKS112-WT-02", out[1]["ticket_no"])

    def test_unmatched_gets_prefix_number_only(self):
        changes = [
            {
                "type": "修改",
                "key": "无关章节",
                "seg": "_MAIN",
                "old": _para_seg("x"),
                "new": _para_seg("y"),
            }
        ]
        tickets = {
            1: Ticket(1, "完全不搭边的问题描述 XYZQQQ", "DFKS112-WT-01"),
        }
        out = apply_matched_tickets(
            changes,
            tickets,
            ticket_prefix="DFKS112-WT",
            min_score=0.9,  # 抬高阈值使内容匹配失败
        )
        self.assertEqual("none", out[0]["ticket_match_method"])
        self.assertEqual("DFKS112-WT-01", out[0]["ticket_no"])  # 前缀兜底
        self.assertEqual("", out[0].get("ticket_title") or "")

    def test_match_report_structure(self):
        changes = [
            {
                "type": "修改",
                "key": "Foo（REQ_12_3）",
                "seg": "a",
                "old": _para_seg("1"),
                "new": _para_seg("2"),
            }
        ]
        tickets = {1: Ticket(1, "REQ_12_3 接口变更", "DFKS112-WT-01")}
        rep = match_report(changes, tickets)
        self.assertEqual(1, rep["matched_count"])
        self.assertEqual(1, len(rep["matches"]))
        self.assertEqual([], rep["unmatched_tickets"])


if __name__ == "__main__":
    unittest.main()
