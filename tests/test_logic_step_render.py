"""LogicStep primary render path smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.logic_step_ir import build_logic_steps, render_logic_steps_to_lines  # noqa: E402
from autodoc.pipeline import logic_step_ir_primary  # noqa: E402
from types import SimpleNamespace


BODY = """
{
    unsigned int status = 0U;
    if (status != 0U)
    {
        status = 0U;
    }
    return NULL;
}
"""


def test_render_logic_steps_basic():
    steps = build_logic_steps(BODY, [], None, name_map={"status": "状态"})
    assert steps
    lines = render_logic_steps_to_lines(steps, name_map={"status": "状态"})
    joined = "\n".join(lines)
    assert "IF" in joined or "if" in joined.lower() or any("状态" in ln for ln in lines)
    assert any("返回" in ln for ln in lines)


def test_logic_step_primary_flag():
    assert logic_step_ir_primary(SimpleNamespace(extra_params={"logic_step_ir": "primary"})) is True
    assert logic_step_ir_primary(SimpleNamespace(extra_params={"logic_step_ir": "shadow"})) is False
    assert logic_step_ir_primary(SimpleNamespace(extra_params={})) is False


def test_else_branch_does_not_render_invalid_end_else():
    body = """
    {
        if (flag)
        {
            value = 1U;
        }
        else
        {
            value = 0U;
        }
    }
    """
    steps = build_logic_steps(body, [], None, name_map={"flag": "标志", "value": "数值"})
    lines = render_logic_steps_to_lines(steps, name_map={"flag": "标志", "value": "数值"})
    assert "END ELSE" not in lines
    assert "END ELSE IF" not in lines
    assert lines.count("END IF") == 1


def test_volatile_register_access_and_label_reverse_are_readable():
    body = """
    {
        l_count_u16 = *(volatile Uint16 *)(cfg.RReg_FiFo_Cnt_u16);
        (*(volatile Uint16 *)(cfg.WReg_rFifo_EN_u16)) = DRI429_R_EN_VALID;
        data.bit.label = Ccdl429LabOrderRev(data.bit.label);
    }
    """
    steps = build_logic_steps(body, [], None, name_map={"l_count_u16": "接收计数", "label": "标签"})
    lines = render_logic_steps_to_lines(steps, name_map={"l_count_u16": "接收计数", "label": "标签"})
    joined = "\n".join(lines)
    assert "读取接收FIFO计数寄存器并写入接收计数" in joined
    assert "向接收FIFO读使能寄存器写入" in joined
    assert "对标签进行429标签位序翻转" in joined
    assert "volatile" not in joined


def test_multiline_block_comment_never_becomes_logic_step():
    body = """
    {
        /*
         * 三路数据最终都走同一套label解析表。
         * 本地429来自硬件FIFO，另外两路来自CCDL原始字镜像。
         */
        value = 1U;
    }
    """
    steps = build_logic_steps(body, [], None, name_map={"value": "数值"})
    lines = render_logic_steps_to_lines(steps, name_map={"value": "数值"})
    joined = "\n".join(lines)
    assert "三路数据" not in joined
    assert "本地429" not in joined
    assert "*/" not in joined
    assert "*；" not in joined


def test_condition_operators_translated_to_chinese():
    body = """
    {
        if (VALID != presetReady)
        {
            return INVALID;
        }
        if (count > 0U && flag == TRUE)
        {
            value = 1U;
        }
    }
    """
    steps = build_logic_steps(body, [], None, name_map={"presetReady": "预设准备完成标志", "count": "计数", "flag": "标志", "value": "数值"})
    lines = render_logic_steps_to_lines(steps, name_map={"presetReady": "预设准备完成标志", "count": "计数", "flag": "标志", "value": "数值"})
    joined = "\n".join(lines)
    assert "!=" not in joined
    assert "&&" not in joined
    assert ">" not in joined
    assert "不等于" in joined
    assert "且" in joined
    assert "大于" in joined


def test_ident_cn_strips_prefixes_and_suffixes():
    from autodoc.logic_step_ir import _cn_expr
    # With name_map providing translations
    name_map = {
        "valveFeedback": "活门反馈", "wheelLoad": "轮载",
        "presetReady": "预设就绪", "perTankTargetKg": "每油箱目标公斤",
    }
    assert _cn_expr("l_valveFeedback_u16", name_map) == "活门反馈"
    assert _cn_expr("s_wheelLoad_u16", name_map) == "轮载"
    assert _cn_expr("presetReady", name_map) == "预设就绪"
    assert _cn_expr("v_perTankTargetKg_f", name_map) == "每油箱目标公斤"


def test_identical_lhs_rhs_skipped():
    body = """
    {
        int x = 0;
        x = x;
        x = 2;
    }
    """
    steps = build_logic_steps(body, [], None, name_map={"x": "X"})
    lines = render_logic_steps_to_lines(steps, name_map={"x": "X"})
    joined = "\n".join(lines)
    assert "X = X" not in joined
    assert len(lines) >= 1, f"expected at least 1 line, got: {lines}"


def test_union_and_struct_declarations_do_not_become_logic_steps():
    body = """
    {
        union arinc429Data l_rdata_un[A429_RX_DATA_NUM_MAX];
        struct device_state l_state_t;
        l_rdata_un[0].msgData = 0U;
    }
    """
    steps = build_logic_steps(body, [], None, name_map={})
    lines = render_logic_steps_to_lines(steps, name_map={})
    joined = "\n".join(lines)
    assert "arinc429Data" not in joined
    assert "device_state" not in joined
    assert any("msgData" in line for line in lines)


def test_untranslated_idents_collected():
    from autodoc.logic_step_ir import clear_untranslated_idents, get_untranslated_idents
    name_map = {"x": "X"}
    body = """{
    int x = 0;
    y = z;
}"""
    clear_untranslated_idents()
    lines = render_logic_steps_to_lines(
        build_logic_steps(body, [], None, name_map=name_map),
        name_map=name_map,
    )
    collected = get_untranslated_idents()
    assert "y" in collected or "z" in collected
    assert "x" not in collected
    clear_untranslated_idents()
    assert get_untranslated_idents() == []
