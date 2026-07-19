"""Small C expression parser/renderer for design-document logic text.

P0#4: tree-sitter expression node -> ExprIR 成为优先路径，
现有字符串 parser 退为 fallback。失败时仅该表达式降级。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional, Sequence


# ── tree-sitter 表达式 parser（P0#4 优先路径）──────────────────────

_TS_PARSER = None
_TS_READY = False


def _get_ts_parser():
    """惰性初始化 tree-sitter C parser。"""
    global _TS_PARSER, _TS_READY
    if _TS_READY:
        return _TS_PARSER
    _TS_READY = True
    try:
        from .tree_sitter_compat import create_c_parser

        _TS_PARSER = create_c_parser()
    except Exception:
        _TS_PARSER = None
    return _TS_PARSER


def _ts_text(source_bytes: bytes, node: Any) -> str:
    try:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""


def _ts_child(node: Any, field_name: str) -> Any:
    """获取 node 的指定 field 子节点。"""
    try:
        return node.child_by_field_name(field_name)
    except Exception:
        return None


def _ts_children(node: Any) -> list:
    try:
        return list(node.children or [])
    except Exception:
        return []


def _ts_node_type(node: Any) -> str:
    return getattr(node, "type", "") or ""


def _build_exprir_from_ts(node: Any, source_bytes: bytes) -> Optional[ExprIR]:
    """从 tree-sitter expression node 递归构建 ExprIR。

    覆盖范围: identifier / literal / call / subscript / field /
    unary / binary / cast / parenthesized。
    """
    if node is None:
        return None
    nt = _ts_node_type(node)
    text = _ts_text(source_bytes, node)

    # parenthesized_expression → 递归内部
    if nt == "parenthesized_expression":
        children = _ts_children(node)
        inner = None
        for c in children:
            if _ts_node_type(c) not in ("(", ")"):
                inner = c
                break
        return _build_exprir_from_ts(inner, source_bytes) or ExprIR(kind="raw", text=text)

    # cast_expression → 递归 value
    if nt == "cast_expression":
        value_node = _ts_child(node, "value")
        if value_node is not None:
            inner = _build_exprir_from_ts(value_node, source_bytes)
            if inner:
                return inner
        return ExprIR(kind="raw", text=text)

    # identifier
    if nt == "identifier":
        return ExprIR(kind="identifier", text=text, name=text)

    # number_literal / string_literal / char_literal
    if nt in ("number_literal", "string_literal", "char_literal"):
        return ExprIR(kind="literal", text=text, value=text)

    # call_expression: function + arguments
    if nt == "call_expression":
        func_node = _ts_child(node, "function")
        args_node = _ts_child(node, "arguments")
        func_name = _ts_text(source_bytes, func_node) if func_node else text
        # 提取实参
        arg_irs: list[ExprIR] = []
        if args_node is not None:
            for ac in _ts_children(args_node):
                if _ts_node_type(ac) == "argument_list" or _ts_node_type(ac) == "(" or _ts_node_type(ac) == ")":
                    continue
                arg_ir = _build_exprir_from_ts(ac, source_bytes)
                if arg_ir:
                    arg_irs.append(arg_ir)
        return ExprIR(kind="call", text=text, name=func_name, children=tuple(arg_irs))

    # subscript_expression: array[index]
    if nt == "subscript_expression":
        return ExprIR(kind="raw_ref", text=text)

    # field_expression: arg.field 或 arg->field
    if nt == "field_expression":
        return ExprIR(kind="raw_ref", text=text)

    # unary_expression: operator + argument
    if nt == "unary_expression":
        op_node = _ts_child(node, "operator")
        arg_node = _ts_child(node, "argument")
        op = _ts_text(source_bytes, op_node) if op_node else ""
        # The renderer has deterministic wording for bitwise/logical negation.
        # Address/dereference and signed arithmetic remain deliberately raw.
        if op in {"~", "!"} and arg_node is not None:
            child = _build_exprir_from_ts(arg_node, source_bytes)
            if child:
                return ExprIR(kind="unary", text=text, op=op, children=(child,))
        return ExprIR(kind="raw", text=text)

    # binary_expression: left + operator + right
    if nt == "binary_expression":
        left_node = _ts_child(node, "left")
        right_node = _ts_child(node, "right")
        op_node = _ts_child(node, "operator")
        op = _ts_text(source_bytes, op_node) if op_node else ""
        if left_node and right_node and op:
            left = _build_exprir_from_ts(left_node, source_bytes)
            right = _build_exprir_from_ts(right_node, source_bytes)
            if left and right:
                return ExprIR(kind="binary", text=text, op=op, children=(left, right))
        return ExprIR(kind="raw", text=text)

    # assignment_expression（赋值出现在条件中时）
    if nt == "assignment_expression":
        left_node = _ts_child(node, "left")
        right_node = _ts_child(node, "right")
        op_node = _ts_child(node, "operator")
        op = _ts_text(source_bytes, op_node) if op_node else "="
        if left_node and right_node:
            left = _build_exprir_from_ts(left_node, source_bytes)
            right = _build_exprir_from_ts(right_node, source_bytes)
            if left and right:
                return ExprIR(kind="binary", text=text, op=op, children=(left, right))
        return ExprIR(kind="raw", text=text)

    # conditional_expression (ternary): a ? b : c
    if nt == "conditional_expression":
        return ExprIR(kind="raw", text=text)

    # 兜底
    return ExprIR(kind="raw", text=text)


def parse_expression_from_ts(expr_text: str) -> ExprIR | None:
    """用 tree-sitter 解析 C 表达式，构建 ExprIR（优先路径）。

    将表达式包装为 ``int __ts_var = <expr>;`` 解析，
    然后从 init_declarator 的 value 提取表达式 AST。
    失败时返回 None，调用方应回退字符串 parser。
    """
    parser = _get_ts_parser()
    if parser is None:
        return None
    raw = str(expr_text or "").strip()
    if not raw:
        return None
    # 包装为完整 C 声明语句
    wrapper = f"int __ts_var = {raw};"
    source_bytes = wrapper.encode("utf-8", errors="replace")
    try:
        tree = parser.parse(source_bytes)
    except Exception:
        return None
    if tree is None or tree.root_node is None:
        return None

    # 遍历找到 init_declarator 的 value（即表达式）
    stack = [tree.root_node]
    while stack:
        current = stack.pop()
        nt = _ts_node_type(current)
        if nt == "init_declarator":
            value_node = _ts_child(current, "value")
            if value_node is not None:
                return _build_exprir_from_ts(value_node, source_bytes)
        stack.extend(reversed(_ts_children(current)))
    return None


@dataclass(frozen=True)
class ExprIR:
    kind: str
    text: str = ""
    op: str = ""
    name: str = ""
    value: str = ""
    children: tuple["ExprIR", ...] = ()


@dataclass(frozen=True)
class RenderedExpr:
    text: str
    confidence: float = 1.0
    source: str = "rule"


_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
_NUMBER_RE = re.compile(r"^(?:0[xX][0-9A-Fa-f]+|\d+)(?:[uUlL]*)$")
_BYTE_MASK_RE = re.compile(r"^0[xX]0*FF(?:[uUlL]*)$")
_ONE_RE = re.compile(r"^1(?:[uUlL]*)$")


def _safe(text: object) -> str:
    return str(text or "").strip()


def _balanced(text: str) -> bool:
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            continue
        if ch == "'":
            in_squote = True
            continue
        if ch == '"':
            in_dquote = True
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_squote and not in_dquote and not escape


def _strip_outer_parens(text: str) -> str:
    value = _safe(text)
    for _ in range(8):
        if not (value.startswith("(") and value.endswith(")")):
            break
        depth = 0
        balanced_outer = True
        in_squote = False
        in_dquote = False
        escape = False
        for idx, ch in enumerate(value):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_squote:
                if ch == "'":
                    in_squote = False
                continue
            if in_dquote:
                if ch == '"':
                    in_dquote = False
                continue
            if ch == "'":
                in_squote = True
                continue
            if ch == '"':
                in_dquote = True
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(value) - 1:
                    balanced_outer = False
                    break
        if not balanced_outer or depth != 0:
            break
        value = value[1:-1].strip()
    return value


def _is_standalone_binary_op(value: str, idx: int, op: str) -> bool:
    if not value.startswith(op, idx):
        return False
    prev_ch = value[idx - 1] if idx > 0 else ""
    next_idx = idx + len(op)
    next_ch = value[next_idx] if next_idx < len(value) else ""
    if op == "&" and (prev_ch == "&" or next_ch == "&"):
        return False
    if op == "|" and (prev_ch == "|" or next_ch == "|"):
        return False
    if op == "+" and (prev_ch == "+" or next_ch == "+"):
        return False
    return True


def _split_top_level_binary(expr: str, ops: Sequence[str]) -> Optional[tuple[str, str, str]]:
    value = _safe(expr)
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    ordered_ops = sorted(ops, key=len, reverse=True)
    idx = 0
    while idx < len(value):
        ch = value[idx]
        if escape:
            escape = False
            idx += 1
            continue
        if ch == "\\":
            escape = True
            idx += 1
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            idx += 1
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            idx += 1
            continue
        if ch == "'":
            in_squote = True
            idx += 1
            continue
        if ch == '"':
            in_dquote = True
            idx += 1
            continue
        if ch in "([{":
            depth += 1
            idx += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            idx += 1
            continue
        if depth == 0:
            for op in ordered_ops:
                if _is_standalone_binary_op(value, idx, op):
                    lhs = _strip_outer_parens(value[:idx])
                    rhs = _strip_outer_parens(value[idx + len(op):])
                    if lhs and rhs:
                        return lhs, op, rhs
        idx += 1
    return None


def _split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for idx, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            continue
        if ch == "'":
            in_squote = True
            continue
        if ch == '"':
            in_dquote = True
            continue
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if depth == 0 and ch == delimiter:
            parts.append(text[start:idx].strip())
            start = idx + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _parse_call(value: str) -> Optional[ExprIR]:
    match = re.match(r"^([A-Za-z_]\w*)\s*\(", value)
    if not match or not value.endswith(")"):
        return None
    open_idx = value.find("(", len(match.group(1)))
    if _strip_outer_parens(value[open_idx:]) != value[open_idx + 1:-1].strip():
        return None
    args_text = value[open_idx + 1:-1].strip()
    args = tuple(
        parsed
        for parsed in (parse_c_expression(arg) for arg in _split_top_level(args_text, ","))
        if parsed is not None
    )
    return ExprIR(kind="call", text=value, name=match.group(1), children=args)


def _looks_like_ref_chain(value: str) -> bool:
    if not value or value[0].isdigit():
        return False
    return bool(re.match(r"^[A-Za-z_]\w*(?:\s*(?:->|\.|\[).*)?$", value)) and (
        "." in value or "->" in value or "[" in value
    )


def parse_c_expression(expr_text: str) -> ExprIR | None:
    """解析 C 表达式为 ExprIR。

    P0#4: tree-sitter 优先路径，字符串 parser 退为 fallback。
    tree-sitter 不可用或解析失败时仅该表达式降级到字符串 parser。
    """
    # 优先路径: tree-sitter
    ts_result = parse_expression_from_ts(expr_text)
    if ts_result is not None:
        return ts_result

    # 回退: 字符串 parser
    value = _strip_outer_parens(expr_text)
    if not value or not _balanced(value):
        return None

    # Match from low to high precedence so the string fallback preserves the
    # same broad structure as the tree-sitter path.  It is intentionally
    # conservative: a malformed expression falls through as raw rather than
    # emitting half-translated C syntax.
    for ops in (
        ("||",), ("&&",), ("==", "!=", "<=", ">=", "<", ">"),
        ("|",), ("^",), ("&",), ("<<", ">>"), ("+", "-"),
        ("*", "/", "%"),
    ):
        split = _split_top_level_binary(value, ops)
        if split:
            lhs, op, rhs = split
            left = parse_c_expression(lhs)
            right = parse_c_expression(rhs)
            if left and right:
                return ExprIR(kind="binary", text=value, op=op, children=(left, right))

    if value.startswith(("~", "!")):
        child = parse_c_expression(value[1:])
        if child:
            return ExprIR(kind="unary", text=value, op=value[0], children=(child,))

    call = _parse_call(value)
    if call:
        return call

    if _looks_like_ref_chain(value):
        return ExprIR(kind="raw_ref", text=value)
    if _IDENT_RE.match(value):
        return ExprIR(kind="identifier", text=value, name=value)
    if _NUMBER_RE.match(value):
        return ExprIR(kind="literal", text=value, value=value)
    return ExprIR(kind="raw", text=value)


def _mapped(text: str, name_map: dict[str, str]) -> str:
    return name_map.get(text, text)


def _literal_text(value: str) -> str:
    match = re.match(r"^((?:0[xX][0-9A-Fa-f]+)|\d+)(?:[uUlL]*)$", value)
    return match.group(1) if match else value


def _is_byte_mask(expr: ExprIR) -> bool:
    return expr.kind == "literal" and bool(_BYTE_MASK_RE.match(expr.value))


def _is_one(expr: ExprIR) -> bool:
    return expr.kind == "literal" and bool(_ONE_RE.match(expr.value))


def _checksum_base(expr: ExprIR) -> Optional[ExprIR]:
    if expr.kind != "binary" or expr.op != "+" or len(expr.children) != 2:
        return None
    left, right = expr.children
    if left.kind == "unary" and left.op == "~" and len(left.children) == 1 and _is_one(right):
        return left.children[0]
    if right.kind == "unary" and right.op == "~" and len(right.children) == 1 and _is_one(left):
        return right.children[0]
    return None


def _contains_raw_arithmetic_operator(text: str) -> bool:
    return bool(re.search(r"[*/%]|\s[+\-]\s", text or ""))


def _segment_with_indexes(segment: str) -> tuple[str, list[str]]:
    head_end = segment.find("[")
    if head_end < 0:
        return segment.strip(), []
    head = segment[:head_end].strip()
    indexes: list[str] = []
    idx = head_end
    while idx < len(segment):
        if segment[idx] != "[":
            idx += 1
            continue
        depth = 1
        start = idx + 1
        idx += 1
        while idx < len(segment) and depth:
            if segment[idx] == "[":
                depth += 1
            elif segment[idx] == "]":
                depth -= 1
            idx += 1
        if depth == 0:
            indexes.append(segment[start:idx - 1].strip())
    return head, indexes


def _render_raw_ref(text: str, name_map: dict[str, str]) -> str:
    alias = name_map.get(text)
    if not alias:
        normalized_text = text.replace("->", ".")
        alias = name_map.get(normalized_text)
    if alias:
        return alias
    value = text.replace("->", ".")
    rendered_segments: list[str] = []
    for segment in _split_top_level(value, "."):
        head, indexes = _segment_with_indexes(segment)
        rendered = _mapped(head, name_map) if head else ""
        for index in indexes:
            rendered_index = render_expr_cn(parse_c_expression(index), name_map).text or index
            rendered += f"[{rendered_index}]"
        if rendered:
            rendered_segments.append(rendered)
    return "的".join(rendered_segments) if rendered_segments else value


def render_expr_cn(
    expr: ExprIR | None,
    name_map: dict[str, str] | None = None,
    rules: object = None,
) -> RenderedExpr:
    del rules
    names = name_map or {}
    if expr is None:
        return RenderedExpr("", confidence=0.0, source="empty")

    if expr.kind == "binary" and len(expr.children) == 2:
        left, right = expr.children
        if expr.op == "&" and _is_byte_mask(right):
            checksum = _checksum_base(left)
            if checksum is not None:
                base_rendered = render_expr_cn(checksum, names)
                if (
                    base_rendered.source in {"raw", "fallback"}
                    or any(op in base_rendered.text for op in ("&", "|", "^", "<<", ">>"))
                    or _contains_raw_arithmetic_operator(base_rendered.text)
                ):
                    return RenderedExpr("", confidence=0.0, source="fallback")
                return RenderedExpr(f"{base_rendered.text}的低8位补码校验和")
            left_rendered = render_expr_cn(left, names)
            if (
                left_rendered.source in {"raw", "fallback"}
                or any(op in left_rendered.text for op in ("&", "|", "^", "<<", ">>"))
                or _contains_raw_arithmetic_operator(left_rendered.text)
            ):
                return RenderedExpr("", confidence=0.0, source="fallback")
            return RenderedExpr(f"{left_rendered.text}的低8位")
        if expr.op == "+":
            left_rendered = render_expr_cn(left, names)
            right_rendered = render_expr_cn(right, names)
            text = f"{left_rendered.text}与{right_rendered.text}之和"
            if (
                left_rendered.source in {"raw", "fallback"}
                or right_rendered.source in {"raw", "fallback"}
                or _contains_raw_arithmetic_operator(left_rendered.text)
                or _contains_raw_arithmetic_operator(right_rendered.text)
            ):
                return RenderedExpr(text, confidence=0.5, source="fallback")
            return RenderedExpr(text)
        left_rendered = render_expr_cn(left, names)
        right_rendered = render_expr_cn(right, names)
        if (
            not left_rendered.text
            or not right_rendered.text
            or left_rendered.source in {"raw", "fallback"}
            or right_rendered.source in {"raw", "fallback"}
        ):
            return RenderedExpr("", confidence=0.0, source="fallback")
        templates = {
            "&": "{left}与{right}按位与结果",
            "|": "{left}与{right}按位或结果",
            "^": "{left}与{right}按位异或结果",
            "<<": "{left}左移{right}位结果",
            ">>": "{left}右移{right}位结果",
            "-": "{left}与{right}之差",
            "*": "{left}与{right}之积",
            "/": "{left}除以{right}的结果",
            "%": "{left}除以{right}的余数",
            "==": "{left}等于{right}",
            "!=": "{left}不等于{right}",
            "<": "{left}小于{right}",
            "<=": "{left}小于等于{right}",
            ">": "{left}大于{right}",
            ">=": "{left}大于等于{right}",
            "&&": "{left}且{right}",
            "||": "{left}或{right}",
        }
        template = templates.get(expr.op)
        if template:
            return RenderedExpr(template.format(left=left_rendered.text, right=right_rendered.text))
        return RenderedExpr("", confidence=0.0, source="fallback")

    if expr.kind == "unary" and expr.op in {"~", "!"} and expr.children:
        child_text = render_expr_cn(expr.children[0], names).text
        if not child_text:
            return RenderedExpr("", confidence=0.0, source="fallback")
        return RenderedExpr(f"{child_text}{'取反' if expr.op == '~' else '不成立'}")
    if expr.kind == "call":
        return RenderedExpr(f"{_mapped(expr.name, names)}结果")
    if expr.kind == "raw_ref":
        return RenderedExpr(_render_raw_ref(expr.text, names))
    if expr.kind == "identifier":
        return RenderedExpr(_mapped(expr.name, names))
    if expr.kind == "literal":
        return RenderedExpr(_literal_text(expr.value), confidence=0.9)
    return RenderedExpr(expr.text, confidence=0.5, source="raw")
