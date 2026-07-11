"""Small C expression parser/renderer for design-document logic text."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Sequence


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
    value = _strip_outer_parens(expr_text)
    if not value or not _balanced(value):
        return None

    split = _split_top_level_binary(value, ("&",))
    if split:
        lhs, op, rhs = split
        left = parse_c_expression(lhs)
        right = parse_c_expression(rhs)
        if left and right:
            return ExprIR(kind="binary", text=value, op=op, children=(left, right))

    split = _split_top_level_binary(value, ("+",))
    if split:
        lhs, op, rhs = split
        left = parse_c_expression(lhs)
        right = parse_c_expression(rhs)
        if left and right:
            return ExprIR(kind="binary", text=value, op=op, children=(left, right))

    if value.startswith("~"):
        child = parse_c_expression(value[1:])
        if child:
            return ExprIR(kind="unary", text=value, op="~", children=(child,))

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
        left_text = render_expr_cn(left, names).text
        right_text = render_expr_cn(right, names).text
        return RenderedExpr(f"{left_text} {expr.op} {right_text}", confidence=0.6, source="fallback")

    if expr.kind == "unary" and expr.op == "~" and expr.children:
        child_text = render_expr_cn(expr.children[0], names).text
        return RenderedExpr(f"{child_text}取反")
    if expr.kind == "call":
        return RenderedExpr(f"{_mapped(expr.name, names)}结果")
    if expr.kind == "raw_ref":
        return RenderedExpr(_render_raw_ref(expr.text, names))
    if expr.kind == "identifier":
        return RenderedExpr(_mapped(expr.name, names))
    if expr.kind == "literal":
        return RenderedExpr(_literal_text(expr.value), confidence=0.9)
    return RenderedExpr(expr.text, confidence=0.5, source="raw")
