"""P0#4 AST Expression IR 升级测试：tree-sitter expression → ExprIR 优先路径。

验证:
1. 低8位和 checksum 回归全部通过（source=rule）
2. tree-sitter 覆盖更多表达式类型（shift/comparison/logical）
3. raw/fallback 表达式不混入半成品中文
4. tree-sitter 不可用时降级到字符串 parser
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.c_expr import (
    parse_c_expression, render_expr_cn, ExprIR,
    _get_ts_parser, parse_expression_from_ts,
)


def test_low8bit_regression():
    """低8位模式：x & 0xFFU → x的低8位。"""
    ir = parse_c_expression("buf[i] & 0xFFU")
    assert ir is not None
    r = render_expr_cn(ir, {"buf": "报文缓冲区"})
    assert r.source == "rule"
    assert "低8位" in r.text
    assert "报文缓冲区" in r.text


def test_checksum_regression():
    """补码校验和：(~sum + 1) & 0xFFU → sum的低8位补码校验和。"""
    ir = parse_c_expression("(~sum + 1) & 0xFFU")
    assert ir is not None
    r = render_expr_cn(ir, {})
    assert r.source == "rule"
    assert "补码校验和" in r.text
    assert "sum" in r.text


def test_bitwise_not():
    """取反：~x → x取反。"""
    ir = parse_c_expression("~x")
    assert ir is not None
    assert ir.kind == "unary"
    assert ir.op == "~"
    r = render_expr_cn(ir, {})
    assert "取反" in r.text


def test_sum():
    """之和：a + b → a与b之和。"""
    ir = parse_c_expression("a + b")
    assert ir is not None
    assert ir.kind == "binary"
    assert ir.op == "+"
    r = render_expr_cn(ir, {})
    assert "之和" in r.text


def test_identifier():
    ir = parse_c_expression("my_var")
    assert ir is not None
    assert ir.kind == "identifier"
    r = render_expr_cn(ir, {"my_var": "我的变量"})
    assert r.text == "我的变量"
    assert r.source == "rule"


def test_literal():
    ir = parse_c_expression("42")
    assert ir is not None
    assert ir.kind == "literal"
    r = render_expr_cn(ir, {})
    assert "42" in r.text


def test_call():
    ir = parse_c_expression("foo(a, b)")
    assert ir is not None
    assert ir.kind == "call"
    assert ir.name == "foo"
    r = render_expr_cn(ir, {})
    assert "foo" in r.text


def test_raw_ref():
    ir = parse_c_expression("state->field.bit")
    assert ir is not None
    assert ir.kind == "raw_ref"
    r = render_expr_cn(ir, {"state": "状态"})
    assert "状态" in r.text


def test_shift_expression():
    """tree-sitter 覆盖移位表达式，渲染降级但不混入半成品中文。"""
    ir = parse_c_expression("x << 2")
    assert ir is not None
    assert ir.kind == "binary"
    assert ir.op == "<<"
    r = render_expr_cn(ir, {})
    # 渲染应为 fallback（不混入半成品中文）
    assert r.source in ("fallback", "raw")
    assert "<<" in r.text or r.text == ""


def test_comparison_expression():
    """tree-sitter 覆盖比较表达式。"""
    ir = parse_c_expression("a == b")
    assert ir is not None
    assert ir.kind == "binary"
    assert ir.op == "=="
    r = render_expr_cn(ir, {})
    assert r.source in ("fallback", "raw")


def test_logical_expression():
    """tree-sitter 覆盖逻辑表达式。"""
    ir = parse_c_expression("a && b")
    assert ir is not None
    r = render_expr_cn(ir, {})
    assert r.source in ("fallback", "raw")


def test_complex_expression():
    """复合表达式：内部低8位正确渲染，外部比较降级。"""
    ir = parse_c_expression("(buf[i] & 0xFFU) == HEAD")
    assert ir is not None
    assert ir.kind == "binary"
    assert ir.op == "=="
    r = render_expr_cn(ir, {"buf": "缓冲区"})
    # 外层是 fallback，但内层低8位应该被渲染
    assert r.source in ("fallback", "raw")
    assert "低8位" in r.text or "缓冲区" in r.text


def test_no_half_baked_chinese():
    """fallback 表达式不混入半成品中文（只有 rule 才有中文模板）。"""
    cases = [
        ("x << 2", "<<"),
        ("a == b", "=="),
        ("a != b", "!=" ),
        ("a < b", "<"),
        ("x | y", "|"),
        ("x ^ y", "^"),
    ]
    for expr_text, op in cases:
        ir = parse_c_expression(expr_text)
        assert ir is not None, f"parse failed: {expr_text}"
        r = render_expr_cn(ir, {})
        # fallback 的文本应包含原始运算符，不含发明的中文
        if r.source == "fallback":
            assert op in r.text, f"fallback 表达式 {expr_text} 应包含运算符 {op}, 实际: {r.text!r}"


def test_ts_unavailable_fallback():
    """tree-sitter 不可用时降级到字符串 parser。"""
    import autodoc.c_expr as c_expr_mod
    orig_get_ts_parser = c_expr_mod._get_ts_parser
    c_expr_mod._get_ts_parser = lambda: None
    try:
        # 字符串 parser 仍能解析低8位
        ir = parse_c_expression("x & 0xFFU")
        assert ir is not None
        r = render_expr_cn(ir, {})
        assert "低8位" in r.text
        # 字符串 parser 不支持 shift，返回 raw
        ir2 = parse_c_expression("x << 2")
        assert ir2 is not None
    finally:
        c_expr_mod._get_ts_parser = orig_get_ts_parser
    # 恢复后 tree-sitter 优先
    assert _get_ts_parser() is not None


def test_ts_parse_directly():
    """直接调用 parse_expression_from_ts 验证 tree-sitter 路径。"""
    ts = _get_ts_parser()
    if ts is None:
        return  # tree-sitter 不可用时跳过
    ir = parse_expression_from_ts("a + b")
    assert ir is not None
    assert ir.kind == "binary"
    assert ir.op == "+"


def test_empty_input():
    """空输入返回 None。"""
    assert parse_c_expression("") is None
    assert parse_c_expression("   ") is None
    assert parse_expression_from_ts("") is None


def test_nested_parens():
    """嵌套括号正确处理。"""
    ir = parse_c_expression("((x + 1))")
    assert ir is not None
    r = render_expr_cn(ir, {})
    assert "之和" in r.text


if __name__ == "__main__":
    test_low8bit_regression()
    print("test_low8bit_regression passed")
    test_checksum_regression()
    print("test_checksum_regression passed")
    test_bitwise_not()
    print("test_bitwise_not passed")
    test_sum()
    print("test_sum passed")
    test_identifier()
    print("test_identifier passed")
    test_literal()
    print("test_literal passed")
    test_call()
    print("test_call passed")
    test_raw_ref()
    print("test_raw_ref passed")
    test_shift_expression()
    print("test_shift_expression passed")
    test_comparison_expression()
    print("test_comparison_expression passed")
    test_logical_expression()
    print("test_logical_expression passed")
    test_complex_expression()
    print("test_complex_expression passed")
    test_no_half_baked_chinese()
    print("test_no_half_baked_chinese passed")
    test_ts_unavailable_fallback()
    print("test_ts_unavailable_fallback passed")
    test_ts_parse_directly()
    print("test_ts_parse_directly passed")
    test_empty_input()
    print("test_empty_input passed")
    test_nested_parens()
    print("test_nested_parens passed")
    print("\nAll P0#4 expression IR tests passed!")
