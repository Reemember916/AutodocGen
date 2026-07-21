import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from model.ast import Block, Segment
from render.change_order import render_change_order
from tickets.tickets import (
    Ticket,
    apply_tickets_to_changes,
    ensure_ticket_no,
    format_problem_heading,
    format_ticket_no,
    load_tickets,
    normalize_ticket_prefix,
    write_ticket_template,
)


class TicketNumberFormatTests(unittest.TestCase):
    def test_format_ticket_no(self):
        self.assertEqual("DFKS112-WT-01", format_ticket_no("DFKS112-WT", 1))
        self.assertEqual("DFKS112-WT-02", format_ticket_no("DFKS112-WT", 2))
        self.assertEqual("DFKS112-WT-01", format_ticket_no("DFKS112", 1))
        self.assertEqual("DFKS112-WT-01", format_ticket_no("DFKS112-WT-", 1))

    def test_normalize_prefix(self):
        self.assertEqual("DFKS112-WT", normalize_ticket_prefix("DFKS112-WT"))
        self.assertEqual("DFKS112-WT", normalize_ticket_prefix("dfks112"))
        self.assertEqual("DFKS112-WT", normalize_ticket_prefix("DFKS112-WT-"))

    def test_ensure_ticket_no(self):
        self.assertEqual(
            "DFKS112-WT-01",
            ensure_ticket_no("DFKS112-WT-01", 1, prefix="DFKS112-WT"),
        )
        self.assertEqual(
            "DFKS112-WT-03",
            ensure_ticket_no("DFKS112-WT", 3, prefix=""),
        )
        self.assertEqual(
            "DFKS112-WT-05",
            ensure_ticket_no("", 5, prefix="DFKS112-WT"),
        )


class TicketLoadTests(unittest.TestCase):
    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.csv"
            path.write_text(
                "序号,问题,问题单编号\n"
                "1,xxx需求变更,DFKS112-WT-01\n"
                "2,xxx函数冗余,DFKS112-WT-02\n",
                encoding="utf-8-sig",
            )
            m = load_tickets(str(path))
            self.assertEqual(2, len(m))
            self.assertEqual("DFKS112-WT-01", m[1].ticket_no)
            self.assertEqual("xxx需求变更", m[1].title)
            self.assertEqual("DFKS112-WT-02", m[2].ticket_no)

    def test_load_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.json"
            path.write_text(
                json.dumps(
                    {
                        "tickets": [
                            {"seq": 1, "title": "需求A", "ticket_no": "DFKS112-WT-01"},
                            {"序号": 3, "问题": "仅第三条", "问题单编号": "DFKS112-WT-03"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            m = load_tickets(str(path))
            self.assertIn(1, m)
            self.assertIn(3, m)
            self.assertEqual("DFKS112-WT-03", m[3].ticket_no)

    def test_write_and_reload_csv_template(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tpl.csv"
            write_ticket_template(str(path), ticket_prefix="DFKS112-WT")
            m = load_tickets(str(path))
            self.assertGreaterEqual(len(m), 2)
            self.assertEqual("DFKS112-WT-01", m[1].ticket_no)
            self.assertEqual("DFKS112-WT-02", m[2].ticket_no)


class TicketApplyTests(unittest.TestCase):
    def test_apply_by_seq(self):
        changes = [{"type": "修改", "key": "A", "seg": "a"}, {"type": "新增", "key": "B", "seg": "b"}]
        tickets = {
            1: Ticket(1, "需求变更", "DFKS112-WT-01"),
            2: Ticket(2, "函数冗余", "DFKS112-WT-02"),
        }
        out = apply_tickets_to_changes(changes, tickets, problem_start=1)
        self.assertEqual(1, out[0]["problem_index"])
        self.assertEqual("DFKS112-WT-01", out[0]["ticket_no"])
        self.assertEqual("需求变更", out[0]["ticket_title"])
        self.assertEqual("DFKS112-WT-02", out[1]["ticket_no"])

    def test_auto_number_with_prefix_only(self):
        changes = [{"type": "修改"}, {"type": "修改"}, {"type": "修改"}]
        out = apply_tickets_to_changes(
            changes,
            {},
            problem_start=1,
            ticket_prefix="DFKS112-WT",
        )
        self.assertEqual(
            ["DFKS112-WT-01", "DFKS112-WT-02", "DFKS112-WT-03"],
            [c["ticket_no"] for c in out],
        )

    def test_prefix_fills_missing_ledger_numbers(self):
        changes = [{"type": "修改"}, {"type": "修改"}]
        tickets = {1: Ticket(1, "有描述无单号", "")}
        out = apply_tickets_to_changes(
            changes,
            tickets,
            ticket_prefix="DFKS112-WT",
        )
        self.assertEqual("DFKS112-WT-01", out[0]["ticket_no"])
        self.assertEqual("有描述无单号", out[0]["ticket_title"])
        self.assertEqual("DFKS112-WT-02", out[1]["ticket_no"])

    def test_heading_format(self):
        self.assertEqual(
            "（问题1，修改，DFKS112-WT-01）章 - a",
            format_problem_heading(1, "修改", "章", "a", "DFKS112-WT-01"),
        )
        self.assertEqual(
            "（问题2，删除）章 - b",
            format_problem_heading(2, "删除", "章", "b", ""),
        )


class TicketRenderTests(unittest.TestCase):
    def test_render_includes_ticket_no(self):
        seg = Segment(
            seg_id="a",
            blocks=[Block("old", "para", "body", None, ("K", "a", 0))],
        )
        seg2 = Segment(
            seg_id="a",
            blocks=[Block("new", "para", "body", None, ("K", "a", 0))],
        )
        changes = apply_tickets_to_changes(
            [{"type": "修改", "key": "K > T", "seg": "a", "old": seg, "new": seg2}],
            {1: Ticket(1, "xxx需求变更", "DFKS112-WT-01")},
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.docx"
            render_change_order(
                changes,
                str(out),
                tickets={1: Ticket(1, "xxx需求变更", "DFKS112-WT-01")},
            )
            doc = Document(str(out))
            all_text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("DFKS112-WT-01", all_text)
            self.assertIn("xxx需求变更", all_text)


if __name__ == "__main__":
    unittest.main()
