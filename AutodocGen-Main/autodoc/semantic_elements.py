"""Semantic elements for deterministic logic text rendering."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass(frozen=True)
class SemanticElement:
    kind: str
    target_id: str
    label: str
    role: str
    confidence: float = 1.0
    source: str = "rule"
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConditionSemantic:
    left_label: str
    relation: str
    right_label: str
    confidence: float = 1.0
    source: str = "rule"
    evidence_ids: tuple[str, ...] = ()


_OPERATOR_RELATIONS = {
    "==": "equals",
    "!=": "not_equals",
    "<": "less_than",
    "<=": "less_equal",
    ">": "greater_than",
    ">=": "greater_equal",
}

_RELATION_TEMPLATES = {
    "equals": "{left}等于{right}",
    "not_equals": "{left}不等于{right}",
    "less_than": "{left}小于{right}",
    "less_equal": "{left}小于等于{right}",
    "greater_than": "{left}大于{right}",
    "greater_equal": "{left}大于等于{right}",
}

_SWAPPED_RELATIONS = {
    "less_than": "greater_than",
    "less_equal": "greater_equal",
    "greater_than": "less_than",
    "greater_equal": "less_equal",
}



_IDENTIFIER_RE = re.compile(r"^[A-Za-z_]\w*$")
_LITERAL_RE = re.compile(r"^(?:0[xX][0-9A-Fa-f]+|\d+)(?:[uUlL]*)?$")


def _normalize_label(label: str) -> str:
    value = re.sub(r"\s+", "", str(label or ""))
    value = value.replace("的低8位", "低8位")
    value = value.replace("的低8位补码校验和", "低8位补码校验和")
    return value.strip()


def _is_literal(text: str) -> bool:
    return bool(_LITERAL_RE.fullmatch(str(text or "").strip()))


def _macro_label_from_identifier(raw: str) -> str:
    value = str(raw or "").strip()
    match = re.fullmatch(r"RS422_COMM_FRAME_HEAD_([12])", value)
    if match:
        return f"RS422通信接收报文帧头{match.group(1)}"
    match = re.fullmatch(r"RS422_COMM_TX_FRAME_HEAD_([12])", value)
    if match:
        return f"RS422通信发送报文帧头{match.group(1)}"
    match = re.fullmatch(r"COMM422_ID_NUM", value)
    if match:
        return "422通信数量"
    return ""





def _contains_call(expr: object) -> bool:
    if getattr(expr, "kind", "") == "call":
        return True
    text = str(getattr(expr, "text", "") or "")
    if re.search(r"\b[A-Za-z_]\w*\s*\(", text):
        return True
    return any(_contains_call(child) for child in getattr(expr, "children", ()) or ())

def _is_unmapped_identifier(raw: str, rendered_text: str, name_map: dict[str, str]) -> bool:
    value = str(raw or "").strip()
    if not _IDENTIFIER_RE.fullmatch(value):
        return False
    if value in name_map:
        return False
    return rendered_text.strip() == value


def _operand_label(operand: str, name_map: dict[str, str]) -> Optional[str]:
    from . import c_expr as c_expr_utils

    raw = str(operand or "").strip()
    if not raw:
        return None
    parsed = c_expr_utils.parse_c_expression(raw)
    if parsed is None:
        return None
    if _contains_call(parsed):
        return None
    rendered = c_expr_utils.render_expr_cn(parsed, name_map)
    text = str(getattr(rendered, "text", "") or "").strip()
    if not text:
        return None
    if getattr(rendered, "source", "") in {"raw", "fallback"}:
        return None
    if _is_unmapped_identifier(raw, text, name_map):
        macro_label = _macro_label_from_identifier(raw)
        if macro_label:
            return _normalize_label(macro_label)
        return None
    if text == raw and not _is_literal(raw):
        macro_label = _macro_label_from_identifier(raw)
        if macro_label:
            return _normalize_label(macro_label)
        return None
    label = _normalize_label(text)
    return label or None


def _is_supported_condition_pair(left_label: str, right_label: str) -> bool:
    joined = f"{left_label}{right_label}"
    if "低8位" in joined or "补码校验和" in joined:
        return True
    return "RS422" in left_label and "RS422" in right_label


def _semantic_prefers_rhs_subject(lhs: str, rhs: str, name_map: dict[str, str]) -> bool:
    lhs_raw = str(lhs or "").strip()
    rhs_raw = str(rhs or "").strip()
    if not lhs_raw or not rhs_raw:
        return False
    if lhs_raw in name_map and rhs_raw not in name_map:
        return False
    if rhs_raw in name_map and lhs_raw not in name_map:
        return True
    if _is_literal(lhs_raw) and not _is_literal(rhs_raw):
        return True
    return bool(_IDENTIFIER_RE.fullmatch(lhs_raw) and lhs_raw.isupper() and not rhs_raw.isupper())



def infer_condition_semantic(
    cond: str,
    name_map: Optional[dict[str, str]] = None,
) -> Optional[ConditionSemantic]:
    """Infer a deterministic semantic condition for supported simple comparisons."""
    from . import logic as logic_utils

    split = logic_utils._split_top_level_comparison(str(cond or "").strip())
    if not split:
        return None
    lhs, op, rhs = split
    relation = _OPERATOR_RELATIONS.get(op)
    if relation is None:
        return None
    names = name_map or {}
    if logic_utils._should_swap_condition_comparison_operands(lhs, op, rhs) or _semantic_prefers_rhs_subject(lhs, rhs, names):
        lhs, rhs = rhs, lhs
        relation = _SWAPPED_RELATIONS.get(relation, relation)
    left_label = _operand_label(lhs, names)
    right_label = _operand_label(rhs, names)
    if not left_label or not right_label:
        return None
    if not _is_supported_condition_pair(left_label, right_label):
        return None
    return ConditionSemantic(left_label=left_label, relation=relation, right_label=right_label)


def render_condition_semantic(condition: Optional[ConditionSemantic]) -> str:
    if condition is None:
        return ""
    template = _RELATION_TEMPLATES.get(condition.relation)
    if not template:
        return ""
    left = _normalize_label(condition.left_label)
    right = _normalize_label(condition.right_label)
    if not left or not right:
        return ""
    return template.format(left=left, right=right)
