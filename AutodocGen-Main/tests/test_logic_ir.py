"""Tests for autodoc.logic_ir LogicStep IR shadow mode."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.logic_step_ir import (
    build_logic_steps, summarize_logic_steps,
    IfStep, ElseIfStep, ElseStep, ForStep, WhileStep, SwitchStep,
    CaseStep, DefaultStep, AssignmentStep, CallStep, ReturnStep,
    BreakStep, ContinueStep, EndBlockStep, UnknownStep,
)


def test_if_else_chain():
    body = """if (x == 1) {
    y = 2;
} else if (x == 2) {
    y = 3;
} else {
}"""
    steps = build_logic_steps(body, None, None)
    kinds = [s.kind for s in steps]
    assert "if" in kinds
    assert "else_if" in kinds
    assert "else" in kinds
    # IF chain: END IF should only appear once at the end, not between IF/ELSE IF/ELSE
    end_ifs = [s for s in steps if isinstance(s, EndBlockStep) and s.block_type == "IF"]
    assert len(end_ifs) == 1
    # Empty ELSE detection
    else_steps = [s for s in steps if isinstance(s, ElseStep)]
    assert len(else_steps) == 1
    assert else_steps[0].is_empty is True


def test_for_loop_end_block():
    body = """for (i = 0; i < 10; i++) {
    buf[i] = 0;
}"""
    steps = build_logic_steps(body, None, None)
    assert any(isinstance(s, ForStep) for s in steps)
    end_fors = [s for s in steps if isinstance(s, EndBlockStep) and s.block_type == "FOR"]
    assert len(end_fors) == 1


def test_switch_case():
    body = """switch (mode) {
case 0:
    x = 1;
    break;
default:
    x = 0;
    break;
}"""
    steps = build_logic_steps(body, None, None)
    kinds = [s.kind for s in steps]
    assert "switch" in kinds
    assert "case" in kinds
    assert "default" in kinds
    assert "break" in kinds
    end_switches = [s for s in steps if isinstance(s, EndBlockStep) and s.block_type == "SWITCH"]
    assert len(end_switches) == 1


def test_assignment_and_call():
    body = """y = foo(a);
bar(b);"""
    steps = build_logic_steps(body, None, None)
    calls = [s for s in steps if isinstance(s, CallStep)]
    assert len(calls) >= 1


def test_return():
    steps = build_logic_steps("return 0;", None, None)
    rets = [s for s in steps if isinstance(s, ReturnStep)]
    assert len(rets) == 1
    assert rets[0].expression == "0"


def test_unknown_statement():
    steps = build_logic_steps("goto label;", None, None)
    unknowns = [s for s in steps if isinstance(s, UnknownStep)]
    assert len(unknowns) == 1
    assert unknowns[0].confidence < 1.0
    assert unknowns[0].fallback_reason != ""


def test_empty_body():
    steps = build_logic_steps("", None, None)
    assert len(steps) == 0
    sm = summarize_logic_steps(steps)
    assert sm["total"] == 0


def test_summary():
    body = """if (x == 1) {
    y = 2;
} else {
}
for (i = 0; i < 10; i++) {
    buf[i] = 0;
}
return y;"""
    steps = build_logic_steps(body, None, None)
    sm = summarize_logic_steps(steps)
    assert sm["total"] > 0
    assert sm["unknown_ratio"] == 0.0
    assert sm["empty_else_count"] == 1
    assert sm["avg_confidence"] == 1.0


def test_scope_depth():
    body = """if (x == 1) {
    if (y == 2) {
        z = 3;
    }
}"""
    steps = build_logic_steps(body, None, None)
    ifs = [s for s in steps if isinstance(s, IfStep)]
    assert len(ifs) == 2
    assert ifs[0].scope_depth == 0
    assert ifs[1].scope_depth == 1


def test_declaration_assignment():
    body = "Uint16 l_count_u16 = 0U;"
    steps = build_logic_steps(body, None, None)
    assigns = [s for s in steps if isinstance(s, AssignmentStep)]
    assert len(assigns) == 1
    assert assigns[0].is_declaration is True


def test_break_continue():
    body = """break;
continue;"""
    steps = build_logic_steps(body, None, None)
    breaks = [s for s in steps if isinstance(s, BreakStep)]
    continues = [s for s in steps if isinstance(s, ContinueStep)]
    assert len(breaks) == 1
    assert len(continues) == 1


if __name__ == "__main__":
    test_if_else_chain()
    test_for_loop_end_block()
    test_switch_case()
    test_assignment_and_call()
    test_return()
    test_unknown_statement()
    test_empty_body()
    test_summary()
    test_scope_depth()
    test_declaration_assignment()
    test_break_continue()
    print("All logic_ir tests passed!")
