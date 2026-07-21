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


@dataclass(frozen=True)
class ActionSemantic:
    """动作语义元素：锁定高频/安全关键调用与赋值模式。

    坚持窄锁定原则——仅覆盖 memset/memcpy/清零/拷贝等确定性模式，
    其余一律回退现有 logic.py 规则链。
    """
    action: str = ""          # clear / fill / copy / set
    target: str = ""         # 目标中文标签
    source: str = ""         # 源中文标签（copy 用）
    value: str = ""          # 填充值中文标签（fill 用）
    confidence: float = 1.0
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReturnSemantic:
    """返回语义元素：锁定常见返回值模式（NULL/TRUE/FALSE/错误码）。"""
    label: str = ""          # 返回值中文标签
    is_void: bool = False   # 无返回值（裸 return）
    confidence: float = 1.0
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


# ── ActionSemantic ──────────────────────────────────────────────────


_ZERO_RE = re.compile(r"^0(?:[UuLl]*)$|^0x0(?:[UuLl]*)$")

_CALL_RE = re.compile(r"^([A-Za-z_]\w*)\s*\((.*)\)\s*;?\s*$", re.DOTALL)

_MEMSET_RE = re.compile(
    r"^memset\s*\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,", re.IGNORECASE,
)
_MEMCPY_RE = re.compile(
    r"^(?:memcpy|memmove)\s*\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,", re.IGNORECASE,
)

_ASSIGN_RE = re.compile(r"^([^=]+?)\s*=\s*(.+?)\s*;?\s*$", re.DOTALL)

def _operand_cn(operand: str, name_map: dict[str, str]) -> str:
    """用 c_expr 渲染操作数中文，失败则回退 name_map 直接查。"""
    from . import c_expr as c_expr_utils

    raw = str(operand or "").strip()
    if not raw:
        return ""
    parsed = c_expr_utils.parse_c_expression(raw)
    if parsed:
        rendered = c_expr_utils.render_expr_cn(parsed, name_map=name_map)
        text = str(getattr(rendered, "text", "") or "").strip()
        if text and getattr(rendered, "source", "") not in ("raw", "fallback", "empty"):
            return _normalize_label(text)
    return _normalize_label(name_map.get(raw, raw))


def infer_action_semantic(
    code: str,
    name_map: Optional[dict[str, str]] = None,
) -> Optional[ActionSemantic]:
    """推断动作语义元素（窄锁定：memset/memcpy/memmove/清零/布尔赋值）。

    返回 None 时调用方应回退现有 logic.py 规则链。
    """
    c = str(code or "").strip()
    if not c:
        return None
    names = name_map or {}

    # memset(ptr, 0, ...) → 清零
    m = _MEMSET_RE.match(c)
    if m:
        target_raw = m.group(1).strip()
        for _ in range(3):
            target_raw = re.sub(r"^\([^)]*\)\s*", "", target_raw).strip()
        target_raw = target_raw.lstrip("&").strip()
        value_raw = m.group(2).strip()
        target_cn = _operand_cn(target_raw, names)
        if not target_cn:
            return None
        if _ZERO_RE.match(value_raw):
            return ActionSemantic(action="clear", target=target_cn)
        value_cn = _operand_cn(value_raw, names)
        if not value_cn:
            return None
        return ActionSemantic(action="fill", target=target_cn, value=value_cn)

    # memcpy/memmove(dst, src, ...) → 拷贝
    m = _MEMCPY_RE.match(c)
    if m:
        dst_raw = m.group(1).strip()
        src_raw = m.group(2).strip()
        dst_cn = _operand_cn(dst_raw, names)
        src_cn = _operand_cn(src_raw, names)
        if not dst_cn or not src_cn:
            return None
        return ActionSemantic(action="copy", target=dst_cn, source=src_cn)

    # 裸赋值 lhs = rhs
    m = _ASSIGN_RE.match(c)
    if m:
        lhs_raw = m.group(1).strip()
        rhs_raw = m.group(2).strip().rstrip(";")
        lhs_cn = _operand_cn(lhs_raw, names)
        if not lhs_cn:
            return None
        # lhs = 0 → 清零
        if _ZERO_RE.match(rhs_raw):
            return ActionSemantic(action="clear", target=lhs_cn)
        # lhs = TRUE/FALSE → 置位/清除标志（0 已作为清零处理）
        if rhs_raw in ("TRUE", "true", "1", "0x1"):
            return ActionSemantic(action="set_true", target=lhs_cn, value="真")
        if rhs_raw in ("FALSE", "false"):
            return ActionSemantic(action="set_false", target=lhs_cn, value="假")
        return None

    return None


def render_action_semantic(action: Optional[ActionSemantic]) -> str:
    if action is None:
        return ""
    a = action.action
    if a == "clear":
        return f"清零{action.target}" if action.target else ""
    if a == "fill":
        if not action.target or not action.value:
            return ""
        return f"填充{action.target}为{action.value}"
    if a == "copy":
        if not action.target or not action.source:
            return ""
        return f"拷贝{action.source}到{action.target}"
    if a == "set_true":
        return f"将{action.target}置为真" if action.target else ""
    if a == "set_false":
        return f"将{action.target}置为假" if action.target else ""
    return ""


# ── ReturnSemantic ─────────────────────────────────────────────────


_RETURN_LABEL_MAP = {
    "NULL": "空指针",
    "null": "空指针",
    "TRUE": "真",
    "FALSE": "假",
    "true": "真",
    "false": "假",
    "E_OK": "成功",
    "E_FAIL": "失败",
    "E_NOT_OK": "失败",
    "E_BUSY": "忙",
    "E_PARAM": "参数错误",
    "E_INVALID": "无效",
    "E_TIMEOUT": "超时",
    "STATUS_OK": "成功",
    "STATUS_ERROR": "错误",
    "STATUS_FAIL": "失败",
    "OK": "成功",
    "ERROR": "错误",
    "PASS": "通过",
    "FAIL": "失败",
    "RET_OK": "成功",
    "RET_ERR": "错误",
    "RET_FAIL": "失败",
    "RET_ERROR": "错误",
    "SUCCESS": "成功",
    "FAILURE": "失败",
}


def infer_return_semantic(
    expr: str,
    name_map: Optional[dict[str, str]] = None,
) -> Optional[ReturnSemantic]:
    """推断返回语义元素（窄锁定：NULL/TRUE/FALSE/常见错误码）。"""
    raw = str(expr or "").strip()
    if not raw:
        return ReturnSemantic(label="", is_void=True)
    # 纯标识符/常量 → 查映射表
    ident = raw.rstrip(";").strip()
    if _IDENTIFIER_RE.fullmatch(ident) or _LITERAL_RE.fullmatch(ident):
        label = _RETURN_LABEL_MAP.get(ident)
        if label:
            return ReturnSemantic(label=label)
        # 0/1 → 返回0/返回1（不猜测语义，由 name_map 决定是否为成功/失败）
        if _LITERAL_RE.fullmatch(ident):
            names = name_map or {}
            cn = names.get(ident, ident)
            return ReturnSemantic(label=cn)
    return None


def render_return_semantic(ret: Optional[ReturnSemantic]) -> str:
    if ret is None:
        return ""
    if ret.is_void:
        return "返回"
    if ret.label:
        return f"返回{ret.label}"
    return ""
