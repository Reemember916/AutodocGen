"""匹配策略 + LLM 解析单元测试（LLM HTTP 用 mock，不访问外网）。"""

import json
import unittest
from unittest import mock

from model.ast import Block, Segment
from tickets.llm_match import _parse_matches_json, build_llm_prompt, llm_match_tickets
from tickets.match import MatchResult, apply_matched_tickets
from tickets.strategy import (
    HybridMatchStrategy,
    MatchContext,
    RulesMatchStrategy,
    get_match_strategy,
    run_match_strategy,
)
from tickets.tickets import Ticket


def _para_seg(text: str, seg_id: str = "_MAIN") -> Segment:
    return Segment(
        seg_id=seg_id,
        blocks=[Block(text, "para", "body", None, ("k", seg_id, 0))],
    )


class StrategyRegistryTests(unittest.TestCase):
    def test_get_strategies(self):
        self.assertEqual("rules", get_match_strategy("rules").name)
        self.assertEqual("llm", get_match_strategy("llm").name)
        self.assertEqual("hybrid", get_match_strategy("hybrid").name)

    def test_rules_strategy_matches_doc_id(self):
        changes = [
            {
                "type": "修改",
                "key": "X（D/R_AA_001）",
                "seg": "a",
                "old": _para_seg("1"),
                "new": _para_seg("2"),
            }
        ]
        tickets = {1: Ticket(1, "D/R_AA_001 变更", "DFKS112-WT-01")}
        hits = RulesMatchStrategy().match(changes, tickets, MatchContext())
        self.assertEqual(1, len(hits))
        self.assertEqual(0, hits[0].change_index)


class LlmParseTests(unittest.TestCase):
    def test_parse_plain_json(self):
        content = json.dumps(
            {
                "matches": [
                    {"ticket_seq": 1, "change_index": 0, "score": 0.9, "reason": "doc_id"}
                ]
            }
        )
        rows = _parse_matches_json(content)
        self.assertEqual(1, len(rows))
        self.assertEqual(1, rows[0]["ticket_seq"])

    def test_parse_fenced_json(self):
        content = "```json\n{\"matches\":[{\"ticket_seq\":2,\"change_index\":1,\"score\":0.8}]}\n```"
        rows = _parse_matches_json(content)
        self.assertEqual(1, len(rows))
        self.assertEqual(2, rows[0]["ticket_seq"])

    def test_build_prompt_contains_cards(self):
        changes = [{"type": "修改", "key": "src/a.c", "seg": "Foo", "old_text": "x", "new_text": "y"}]
        tickets = {1: Ticket(1, "Foo 函数修改", "DFKS112-WT-01")}
        p = build_llm_prompt(changes, tickets)
        self.assertIn("Foo", p)
        self.assertIn("ticket_seq", p)


class LlmMatchMockTests(unittest.TestCase):
    def test_llm_match_with_mocked_http(self):
        changes = [
            {"type": "修改", "key": "src/a.c", "seg": "AlphaFn", "old_text": "a", "new_text": "b"},
            {"type": "修改", "key": "src/b.c", "seg": "BetaFn", "old_text": "c", "new_text": "d"},
        ]
        tickets = {
            1: Ticket(1, "请修改 AlphaFn", "DFKS112-WT-01"),
            2: Ticket(2, "请修改 BetaFn", "DFKS112-WT-02"),
        }
        fake_content = json.dumps(
            {
                "matches": [
                    {"ticket_seq": 1, "change_index": 0, "score": 0.91, "reason": "函数名 AlphaFn"},
                    {"ticket_seq": 2, "change_index": 1, "score": 0.88, "reason": "函数名 BetaFn"},
                ]
            }
        )
        ctx = MatchContext(
            llm_api_base="https://example.invalid/v1",
            llm_api_key="sk-test",
            llm_model="test-model",
            llm_min_score=0.55,
        )
        with mock.patch("tickets.llm_match._chat_completions", return_value=fake_content):
            hits = llm_match_tickets(changes, tickets, ctx)
        self.assertEqual(2, len(hits))
        self.assertEqual({0, 1}, {h.change_index for h in hits})
        self.assertTrue(all(h.reason.startswith("llm") for h in hits))


class HybridStrategyTests(unittest.TestCase):
    def test_hybrid_falls_back_to_rules_without_llm(self):
        changes = [
            {
                "type": "修改",
                "key": "Y（D/R_BB_002）",
                "seg": "_MAIN",
                "old": _para_seg("1"),
                "new": _para_seg("2"),
            }
        ]
        tickets = {5: Ticket(5, "D/R_BB_002 需求", "DFKS112-WT-05")}
        # 无 api key：hybrid ≡ rules
        hits = HybridMatchStrategy().match(changes, tickets, MatchContext(llm_enabled=False))
        self.assertEqual(1, len(hits))
        self.assertEqual(5, hits[0].ticket_seq)

    def test_hybrid_adds_llm_for_unmatched(self):
        changes = [
            {
                "type": "修改",
                "key": "Y（D/R_BB_002）",
                "seg": "_MAIN",
                "old": _para_seg("1"),
                "new": _para_seg("2"),
            },
            {
                "type": "修改",
                "key": "模糊描述章节",
                "seg": "_MAIN",
                "old": _para_seg("hello world unique body"),
                "new": _para_seg("hello world unique body changed"),
            },
        ]
        tickets = {
            1: Ticket(1, "D/R_BB_002 明确编号", "DFKS112-WT-01"),
            2: Ticket(2, "与正文相关的含糊需求 hello world unique", "DFKS112-WT-02"),
        }
        # rules 应先挂 ticket1；ticket2 可能弱匹配或未匹配
        rules_hits = RulesMatchStrategy().match(changes, tickets, MatchContext(min_score=0.42))
        self.assertTrue(any(m.ticket_seq == 1 for m in rules_hits))

        fake = json.dumps(
            {
                "matches": [
                    {
                        "ticket_seq": 2,
                        "change_index": 0,  # 在 sub_changes 中的下标
                        "score": 0.8,
                        "reason": "语义相近",
                    }
                ]
            }
        )
        ctx = MatchContext(
            llm_enabled=True,
            llm_api_base="https://example.invalid/v1",
            llm_api_key="sk-test",
            llm_min_score=0.55,
        )
        with mock.patch("tickets.llm_match._chat_completions", return_value=fake):
            hits = HybridMatchStrategy().match(changes, tickets, ctx)
        seqs = {m.ticket_seq for m in hits}
        self.assertIn(1, seqs)
        # LLM 补全 ticket 2
        self.assertIn(2, seqs)

    def test_apply_matched_with_strategy_rules(self):
        changes = [
            {
                "type": "修改",
                "key": "A（D/R_AA_001）",
                "seg": "a",
                "old": _para_seg("x"),
                "new": _para_seg("y"),
            }
        ]
        tickets = {1: Ticket(1, "D/R_AA_001", "DFKS112-WT-01")}
        out = apply_matched_tickets(
            changes,
            tickets,
            match_strategy="rules",
            ticket_prefix="DFKS112-WT",
        )
        self.assertEqual("DFKS112-WT-01", out[0]["ticket_no"])
        self.assertIn(out[0]["ticket_match_method"], {"auto", "rules-rules"})


if __name__ == "__main__":
    unittest.main()
