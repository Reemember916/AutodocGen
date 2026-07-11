"""Tests for autodoc.evidence Evidence Model shadow mode."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.evidence import (
    collect_function_evidence, build_quality_summary,
    FunctionEvidence, QualitySummary,
)
from autodoc.logic_ir import build_logic_steps


def _make_func_data(func_name, body, comment_desc=""):
    return {
        "func_info": {"func_name": func_name, "ret_type": "void",
                      "prototype": f"void {func_name}(void)", "start": 1, "end": 10},
        "comment_info": {"func_name": func_name, "desc": comment_desc},
        "body": body,
        "file_context": {"source_file": "test.c"},
        "params": [],
        "local_vars": [],
    }


def test_collect_basic():
    body = "if (x == 1) { y = 2; }"
    func_data = _make_func_data("test_func", body, "test description")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    assert isinstance(ev, FunctionEvidence)
    assert ev.func_name == "test_func"
    assert ev.comment.has_comment is True
    assert ev.comment.description == "test description"
    assert len(ev.logic_steps) > 0


def test_quality_summary_scoring():
    body = """if (x == 1) {
    y = 2;
} else {
}
return y;"""
    func_data = _make_func_data("test_func", body, "desc")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    qs = build_quality_summary(ev)
    assert isinstance(qs, QualitySummary)
    assert qs.func_name == "test_func"
    assert qs.total_steps > 0
    assert qs.unknown_ratio == 0.0
    assert qs.empty_else_count == 1
    assert "has_empty_else" in qs.quality_flags
    assert 0 <= qs.overall_score <= 100


def test_empty_else_flag():
    body = """if (x == 1) {
    y = 2;
} else {
}"""
    func_data = _make_func_data("f", body, "")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    assert ev.has_empty_else is True
    qs = build_quality_summary(ev)
    assert qs.empty_else_count == 1
    assert "has_empty_else" in qs.quality_flags


def test_unknown_step_flag():
    body = "goto label;"
    func_data = _make_func_data("f", body, "")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    assert ev.has_unknown_steps is True
    qs = build_quality_summary(ev)
    assert qs.unknown_step_count > 0
    assert "has_unknown_steps" in qs.quality_flags


def test_missing_comment_flag():
    body = "y = 2;"
    func_data = _make_func_data("f", body, "")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    assert ev.comment.has_comment is False
    qs = build_quality_summary(ev)
    assert "missing_comment" in qs.quality_flags


def test_variable_evidence():
    func_data = _make_func_data("f", "y = 2;", "desc")
    func_data["params"] = [{"ident": "v_input", "c_type": "Uint16", "cn_name": "输入值", "direction": "输入"}]
    func_data["local_vars"] = [{"ident": "l_count", "c_type": "Uint16", "cn_name": "计数"}]
    steps = build_logic_steps("y = 2;", None, None)
    ev = collect_function_evidence(func_data, steps)
    assert len(ev.variables) == 2
    params = [v for v in ev.variables if v.role == "param"]
    locals_ = [v for v in ev.variables if v.role == "local"]
    assert len(params) == 1
    assert len(locals_) == 1
    assert params[0].cn_name == "输入值"
    assert locals_[0].cn_name == "计数"
    qs = build_quality_summary(ev)
    assert qs.variable_count == 2


def test_expression_evidence():
    body = "result = buf[i] & 0xFFU;"
    func_data = _make_func_data("f", body, "desc")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps)
    assert len(ev.expressions) > 0
    qs = build_quality_summary(ev)
    assert qs.expression_count > 0


def test_lsp_fact_evidence_none():
    body = "y = 2;"
    func_data = _make_func_data("f", body, "")
    steps = build_logic_steps(body, None, None)
    ev = collect_function_evidence(func_data, steps, lsp_fact_pack=None)
    assert ev.lsp_facts.available is False
    qs = build_quality_summary(ev)
    assert qs.lsp_available is False


if __name__ == "__main__":
    test_collect_basic()
    test_quality_summary_scoring()
    test_empty_else_flag()
    test_unknown_step_flag()
    test_missing_comment_flag()
    test_variable_evidence()
    test_expression_evidence()
    test_lsp_fact_evidence_none()
    print("All evidence tests passed!")
