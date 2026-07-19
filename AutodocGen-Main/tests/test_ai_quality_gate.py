from __future__ import annotations

from autodoc.models import AIBuildMeta, FunctionDesign
from autodoc.pipeline import _fallback_structural_logic_lines, compose_quality_feedback_text
from autodoc.quality_gate import inspect_logic_lines, is_safe_ai_text
from autodoc.review_workspace import build_review_function


def _design(lines, meta):
    return FunctionDesign("测试", "D/R_001", "void Demo(void)", (), (), True, (), tuple(lines), meta)


def test_gate_rejects_single_raw_bitwise_and_full_width_unclosed_bracket():
    issues = inspect_logic_lines(("将标志 & 掩码写入状态；", "将关闭标志（写入状态；"))

    assert [item["code"] for item in issues] == ["logic_truncated", "logic_truncated"]
    assert not is_safe_ai_text("关闭标志 & 掩码")
    assert not is_safe_ai_text("关闭标志（")
    assert is_safe_ai_text("关闭标志（RCV1_Close）")


def test_feedback_uses_raw_source_anchor_and_line_fallback_omits_unsafe_baseline():
    bad = ("AI 改进说明；", "将关闭标志（写入状态；")
    anchors = (
        {"idx": 1, "raw_code": "ok = Check();"},
        {"idx": 2, "file": "demo.c", "start_line": 27, "end_line": 28, "raw_code": "flags & mask"},
    )
    meta = AIBuildMeta(logic_source_audit=anchors, quality_issues=inspect_logic_lines(bad, source_anchors=anchors))

    feedback = compose_quality_feedback_text(meta)
    assert "flags & mask" in feedback
    assert "逻辑第 2 行" in feedback

    recovered = _fallback_structural_logic_lines(_design(bad, meta), _design(("确定性说明；", "if(flag && mask)"), AIBuildMeta()))
    assert recovered.logic_lines == ("AI 改进说明；", "")
    assert not inspect_logic_lines(recovered.logic_lines)
    assert recovered.ai_meta.quality_recovery[-1]["omitted_lines"] == (2,)


def test_review_workspace_exposes_quality_recovery_audit():
    meta = AIBuildMeta(quality_recovery=({"action": "line_deterministic_fallback", "lines": (2,), "omitted_lines": ()},))
    review_fn = build_review_function(_design(("读取状态；",), meta), {"func_info": {"func_name": "Demo"}})

    audit = next(block for block in review_fn.blocks if block.kind == "quality_audit")
    assert audit.editable is False
    assert audit.rows[0]["action"] == "line_deterministic_fallback"
