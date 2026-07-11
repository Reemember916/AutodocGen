"""Tests for the variable batch naming prompt builder.

These tests pin the minimum information the LLM must receive so it can
infer Chinese names for un-commented local variables from the function body.
"""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc import backend
from autodoc import naming
from autodoc import naming_context as nc


def _build_prompt() -> str:
    body = """
    {
        Uint16 l_subcmd_u16 = 0U;
        if (channel >= NUM) return;
        l_subcmd_u16 = s_rs422CommBuff_t[channel].commBuff_u16[index + 4U] & 0xFFU;
        Comm429RIUSimApplySubcmd(l_subcmd_u16, &s_rs422CommBuff_t[channel].commBuff_u16[index + 5U]);
    }
    """
    func_data = {
        "func_info": {
            "func_name": "MaintRIUSimInjectProcess",
            "prototype": "static void MaintRIUSimInjectProcess(Uint16 v_commID_u16, Uint16 v_sIndex_u16)",
        },
        "body": body,
        "comment_info": {"desc": "维护 RIU 模拟注入数据处理"},
    }
    return nc.build_variable_batch_prompt(
        func_data,
        func_cn_name="维护 RIU 模拟注入",
        body_summary="从缓冲区取出 1 字节作为子命令调用 Comm429RIUSimApplySubcmd。",
    )


class TestVariableBatchPromptBodyIncluded(unittest.TestCase):
    def test_prompt_contains_function_body_context(self):
        prompt = _build_prompt()
        # The LLM must see enough body context to infer un-commented locals.
        self.assertIn("l_subcmd_u16", prompt)
        self.assertIn("Comm429RIUSimApplySubcmd", prompt)
        self.assertIn("commBuff_u16", prompt)


class TestVariableBatchParserAcceptsChinese(unittest.TestCase):
    def test_parser_extracts_chinese_for_uncommented_local(self):
        raw = (
            "```json\n"
            "{\n"
            '  "v_commID_u16": "通信ID",\n'
            '  "v_sIndex_u16": "子帧索引",\n'
            '  "l_subcmd_u16": "子命令码"\n'
            "}\n"
            "```"
        )
        parsed = nc.parse_variable_batch_response(raw)
        self.assertEqual(parsed.get("l_subcmd_u16"), "子命令码")
        self.assertEqual(parsed.get("v_commID_u16"), "通信ID")

    def test_batch_naming_returns_cn_when_cfg_enables_ai(self):
        body = (
            "Uint16 l_subcmd_u16 = 0U;\n"
            "l_subcmd_u16 = s_buf[ch].p[0] & 0xFFU;\n"
        )
        func_data = {
            "func_info": {
                "func_name": "MaintRIUSimInjectProcess",
                "prototype": "static void MaintRIUSimInjectProcess(Uint16 v_commID_u16, Uint16 v_sIndex_u16)",
            },
            "body": body,
            "comment_info": {"desc": "维护 RIU 模拟注入"},
        }
        cfg = SimpleNamespace(
            ai_assist=True, ai_temperature=0.1, ai_top_p=0.9,
            extra_params={}, verbose=False, gui_log=None,
        )
        fake_response = (
            '{\n  "l_subcmd_u16": "子命令码",\n  "v_commID_u16": "通信ID",\n'
            '  "v_sIndex_u16": "子帧索引"\n}'
        )
        with mock.patch("autodoc.ai.call_llm_text", return_value=fake_response):
            result = naming.get_variable_chinese_names_batch(
                func_data,
                func_cn_name="维护 RIU 模拟注入",
                body_summary="从缓冲区取出子命令并下传。",
                cfg=cfg,
                backend_module=backend,
            )
        self.assertEqual(result.get("l_subcmd_u16"), "子命令码")
        self.assertEqual(result.get("v_commID_u16"), "通信ID")


if __name__ == "__main__":
    unittest.main()
