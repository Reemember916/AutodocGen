"""Logic IR helpers used to stabilize rule/AI logic rendering."""

from __future__ import annotations

import hashlib
import json
import re
from types import SimpleNamespace
from typing import Any, Optional, Sequence

from ._legacy_support import legacy_backend
from . import utils
from . import text as text_utils
from .models import FunctionDesign, IOElement, LocalDataElement, LogicIR, LogicNode
from . import parse as parse_utils


def build_logic_ir(body: str, cfg: Optional[Any] = None, *, name_map: Optional[dict[str, str]] = None) -> LogicIR:
    legacy = legacy_backend()
    ir = LogicIR()
    for cond in legacy._collect_condition_signatures_from_body(body):
        text = utils._safe_strip(cond)
        if text:
            ir.conditions.append(text)
            ir.nodes.append(LogicNode(kind="condition", text=text, condition=text))
    for callee in legacy._collect_callee_names_from_body(body):
        text = utils._safe_strip(callee)
        if text:
            ir.callees.append(text)
            ir.nodes.append(LogicNode(kind="call", text=f"调用{text}"))
    for effect in legacy._collect_member_access_signatures_from_body(body):
        text = utils._safe_strip(effect)
        if text:
            ir.state_effects.append(text)
    return ir


def render_logic_ir(ir: LogicIR, cfg: Optional[Any] = None, *, name_map: Optional[dict[str, str]] = None) -> list[str]:
    legacy = legacy_backend()
    steps: list[str] = []
    for node in ir.nodes:
        text = utils._safe_strip(node.text)
        if text:
            steps.append(legacy._normalize_logic_line_for_output(text, name_map=name_map))
    return steps


def _render_semantic_action_text(
    item: dict[str, Any],
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    kind = utils._safe_strip(item.get("kind"))
    label = utils._safe_strip(item.get("label"))
    raw_lhs = utils._safe_strip(item.get("lhs"))
    raw_rhs = utils._safe_strip(item.get("rhs"))
    if kind in {"state_sync", "feedback_compute", "control_compute"} and raw_lhs and raw_rhs:
        rendered_rhs = _render_supported_c_expr_cn(raw_rhs, name_map)
        if rendered_rhs:
            lhs_for_supported = _logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend)
            lhs_for_supported = _normalize_logic_compute_target(
                lhs_for_supported or raw_lhs,
                raw_ident=raw_lhs,
                backend_module=backend,
            )
            if lhs_for_supported:
                return f"将{rendered_rhs}写入{lhs_for_supported}"
    direct_text = _render_raw_assignment_template(raw_lhs, raw_rhs, kind=kind, name_map=name_map, backend_module=backend)
    if direct_text:
        return direct_text
    lhs = _logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend)
    rhs = _logic_cn_expr(raw_rhs, name_map=name_map, backend_module=backend)
    if _looks_like_decl_assignment(raw_lhs):
        target = _simplify_decl_target(lhs or raw_lhs, backend_module=backend)
        if kind == "reset_or_clear":
            return f"初始化{target}" if target else ""
        if target:
            return f"初始化{target}"
    if kind == "reset_or_clear":
        return f"清零{lhs}" if lhs else ""
    if kind == "pack_buffer_fill":
        pack_label = label or _infer_pack_label(raw_lhs or lhs, backend_module=backend)
        if pack_label:
            return f"组装{pack_label}"
        if lhs:
            return f"填充{lhs}"
        return "组装输出数据"
    if kind == "result_surface_write":
        pack_label = label or _infer_pack_label(raw_lhs or raw_rhs or lhs or rhs, backend_module=backend)
        if pack_label:
            return f"将{pack_label}写入结果面"
        if lhs and rhs:
            return f"将 {rhs} 写入 {lhs}"
        return "写入结果面"
    if kind == "compat_word_fill":
        compat_label = label or _infer_pack_label(raw_lhs or lhs, backend_module=backend) or "兼容字"
        return f"计算{compat_label}各故障位"
    if kind == "mode_word_sync":
        mode_label = label or lhs or "模式字"
        if rhs:
            return f"同步{mode_label}"
        return f"更新{mode_label}"
    if kind == "error_flag_assign":
        err_label = label or lhs or "错误标志"
        if rhs:
            return f"标记{err_label}"
        return f"更新{err_label}"
    if kind == "validity_flag_assign":
        valid_label = label or lhs or "有效性标志"
        return f"标记{valid_label}"
    if kind == "counter_update":
        counter_label = label or lhs or "计数值"
        return f"更新{counter_label}"
    if kind == "snapshot_compare":
        snapshot_label = label or lhs or "状态快照"
        return f"记录{snapshot_label}并比较变化"
    if kind == "filter_output":
        filter_label = label or "数字滤波"
        return f"执行{filter_label}"
    if kind == "local_init":
        if lhs and rhs:
            return f"设置{lhs} = {rhs}"
        if lhs:
            return f"设置{lhs}"
        return ""
    if kind == "pack_output":
        if lhs and rhs:
            return f"将 {rhs} 打包写入 {lhs}"
        return "执行数据打包输出"
    if kind == "compound_assign":
        op = utils._safe_strip(item.get("op"))
        verb = {
            "+=": "累加",
            "-=": "递减",
            "*=": "乘以并更新",
            "/=": "除以并更新",
            "%=": "取余并更新",
            "<<=": "左移并更新",
            ">>=": "右移并更新",
            "&=": "按位与并更新",
            "|=": "按位或并更新",
            "^=": "按位异或并更新",
        }.get(op, "更新")
        if lhs and rhs:
            rhs_display = _render_shift_expression_text(raw_rhs, name_map=name_map, backend_module=backend) or rhs
            return f"{lhs}{verb}{rhs_display}"
        return f"更新{lhs}" if lhs else ""
    if kind == "state_sync":
        bit_chain = _render_bitwise_chain_assignment(raw_lhs, raw_rhs, name_map, backend_module=backend)
        if bit_chain:
            return bit_chain
        if lhs and rhs:
            return f"将 {rhs} 写入 {lhs}"
        return ""
    if kind in {"feedback_compute", "control_compute"}:
        polished_lhs = _normalize_logic_compute_target(lhs or raw_lhs, raw_ident=raw_lhs, backend_module=backend)
        bit_chain = _render_bitwise_chain_assignment(raw_lhs, raw_rhs, name_map, backend_module=backend)
        if bit_chain:
            return bit_chain
        if lhs and rhs:
            return f"计算 {polished_lhs or lhs} = {rhs}"
        if polished_lhs or lhs:
            return f"更新{polished_lhs or lhs}"
    return ""


def _render_raw_assignment_template(
    lhs: str,
    rhs: str,
    *,
    kind: str = "",
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    raw_lhs = utils._safe_strip(lhs)
    raw_rhs = utils._safe_strip(rhs)
    if not raw_lhs or not raw_rhs:
        return ""
    if kind and kind not in {"control_compute", "feedback_compute", "state_sync"}:
        return ""
    lhs_cn = _logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend)
    rhs_compact = re.sub(r"\s+", "", raw_rhs)
    lhs_ref = _render_assignment_ref_label(raw_lhs, name_map=name_map, backend_module=backend)
    rhs_ref = _render_assignment_ref_label(raw_rhs, name_map=name_map, backend_module=backend)
    if lhs_cn == "返回结果" and re.match(r"l[a-z]?_", raw_lhs.lower()):
        rhs_label = rhs_ref or _logic_cn_expr(raw_rhs, name_map=name_map, backend_module=backend)
        if rhs_label:
            return f"暂存{rhs_label}作为返回结果"
    decl_target_match = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?$", raw_lhs)
    decl_pointer_like = bool(re.search(r"\*", raw_lhs) and decl_target_match)
    if _looks_like_decl_assignment(raw_lhs) or decl_pointer_like:
        raw_target = utils._safe_strip(decl_target_match.group(1) if decl_target_match else "")
        target = _logic_cn_expr(raw_target, name_map=name_map, backend_module=backend) if raw_target else ""
        target = target or _simplify_decl_target(_logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend) or raw_lhs, backend_module=backend)
        if re.fullmatch(r"(?:NULL|0(?:\.0)?F?|0U?L?)", rhs_compact, flags=re.IGNORECASE):
            if "指针" in target:
                return f"初始化{target}为空"
            return f"初始化{target}"
    call_match = re.fullmatch(r"(?P<func>[A-Za-z_]\w*)\s*\((?P<args>.*)\)", raw_rhs)
    if call_match and "指针" in lhs_cn:
        return f"获取{lhs_cn}"
    status_text = _render_status_assignment_text(raw_lhs, raw_rhs, lhs_cn, name_map=name_map, backend_module=backend)
    if status_text:
        return status_text
    ternary_text = _render_ternary_assignment_text(raw_lhs, raw_rhs, lhs_cn, name_map=name_map, backend_module=backend)
    if ternary_text:
        return ternary_text
    binary_text = _render_binary_assignment_text(raw_lhs, raw_rhs, lhs_cn, name_map=name_map, backend_module=backend)
    if binary_text:
        return binary_text
    pointer_target = _normalize_logic_compute_target(lhs_cn or raw_lhs, raw_ident=raw_lhs, backend_module=backend)
    if pointer_target and "指向的变量" in pointer_target and raw_rhs:
        rhs_cn = _logic_cn_expr(raw_rhs, name_map=name_map, backend_module=backend)
        if rhs_cn:
            return f"将{rhs_cn}写入{pointer_target}"
    if lhs_ref and rhs_ref and lhs_ref != rhs_ref:
        return f"将{rhs_ref}写入{lhs_ref}"
    if rhs_ref and _is_temp_value_label(lhs_cn):
        return f"读取{rhs_ref}"
    if rhs_ref and lhs_cn and not _is_temp_value_label(lhs_cn):
        return f"选取{rhs_ref}作为{lhs_cn}"
    if lhs_ref and raw_rhs:
        rhs_cn = _logic_cn_expr(raw_rhs, name_map=name_map, backend_module=backend)
        if rhs_cn and rhs_cn != raw_rhs:
            return f"将{rhs_cn}写入{lhs_ref}"
    if lhs_ref and re.fullmatch(r"[A-Za-z_]\w*", raw_rhs):
        rhs_cn = _logic_cn_expr(raw_rhs, name_map=name_map, backend_module=backend)
        return f"将{rhs_cn}写入{lhs_ref}" if rhs_cn else ""
    return ""


def _split_top_level_ternary(expr: str) -> Optional[tuple[str, str, str]]:
    value = utils._safe_strip(expr)
    if "?" not in value or ":" not in value:
        return None
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    q_pos = -1
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
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if ch == "?" and depth == 0:
            q_pos = idx
            break
    if q_pos < 0:
        return None
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for idx in range(q_pos + 1, len(value)):
        ch = value[idx]
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
        if ch == ":" and depth == 0:
            cond = _strip_outer_parens(value[:q_pos])
            true_expr = _strip_outer_parens(value[q_pos + 1 : idx])
            false_expr = _strip_outer_parens(value[idx + 1 :])
            if cond and true_expr and false_expr:
                return cond, true_expr, false_expr
            return None
    return None


def _render_ternary_assignment_text(
    raw_lhs: str,
    raw_rhs: str,
    lhs_cn: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    split = _split_top_level_ternary(raw_rhs)
    if not split:
        return ""
    cond, true_expr, false_expr = split
    cond_cn, _ = _render_structured_condition_cn(cond, (), name_map, None, backend_module=backend)
    true_cn = _logic_cn_expr(true_expr, name_map=name_map, backend_module=backend)
    false_cn = _logic_cn_expr(false_expr, name_map=name_map, backend_module=backend)
    target = _normalize_logic_compute_target(lhs_cn or _logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend) or raw_lhs, raw_ident=raw_lhs, backend_module=backend)
    if cond_cn and true_cn and false_cn and target:
        if "指向的变量" in target:
            return f"根据{cond_cn}选择{true_cn}，否则选择{false_cn}写入{target}"
        return f"根据{cond_cn}选择{true_cn}，否则选择{false_cn}作为{target}"
    if true_cn and false_cn and target:
        return f"选择{true_cn}或{false_cn}作为{target}"
    return ""


def _render_ternary_return_text(
    raw_expr: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    split = _split_top_level_ternary(raw_expr)
    if not split:
        return ""
    cond, true_expr, false_expr = split
    cond_cn, _ = _render_structured_condition_cn(cond, (), name_map, None, backend_module=backend)
    true_cn = _logic_cn_expr(true_expr, name_map=name_map, backend_module=backend)
    false_cn = _logic_cn_expr(false_expr, name_map=name_map, backend_module=backend)
    if cond_cn and true_cn and false_cn:
        return f"根据{cond_cn}选择{true_cn}，否则选择{false_cn}作为返回值"
    if true_cn and false_cn:
        return f"选择{true_cn}或{false_cn}作为返回值"
    return ""


def _split_top_level_binary_arithmetic(expr: str) -> Optional[tuple[str, str, str]]:
    value = utils._safe_strip(expr)
    if not value:
        return None
    depth = 0
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
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if depth != 0 or ch not in "+-":
            continue
        if idx == 0:
            continue
        prev = value[idx - 1]
        nxt = value[idx + 1] if idx + 1 < len(value) else ""
        if prev in "+-*/%<>=!&|^" or nxt in "+-*/%<>=!&|^":
            continue
        lhs = _strip_balanced_outer_parens(value[:idx])
        rhs = _strip_balanced_outer_parens(value[idx + 1 :])
        if lhs and rhs:
            return lhs, ch, rhs
    return None


def _render_binary_assignment_text(
    raw_lhs: str,
    raw_rhs: str,
    lhs_cn: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    split = _split_top_level_binary_arithmetic(raw_rhs)
    if not split:
        return ""
    left_expr, op, right_expr = split
    left_cn = _logic_cn_expr(left_expr, name_map=name_map, backend_module=backend)
    right_cn = _logic_cn_expr(right_expr, name_map=name_map, backend_module=backend)
    target = _normalize_logic_compute_target(
        lhs_cn or _logic_cn_expr(raw_lhs, name_map=name_map, backend_module=backend) or raw_lhs,
        raw_ident=raw_lhs,
        backend_module=backend,
    )
    if not left_cn or not right_cn or not target:
        return ""
    if op == "+":
        return f"将{left_cn}与{right_cn}之和写入{target}"
    if op == "-":
        return f"将{left_cn}减去{right_cn}的结果写入{target}"
    return ""


def _render_status_assignment_text(
    lhs: str,
    rhs: str,
    lhs_cn: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    lhs_raw = utils._safe_strip(lhs)
    rhs_raw = utils._safe_strip(rhs)
    lhs_label = utils._safe_strip(lhs_cn)
    if not lhs_raw or not rhs_raw:
        return ""
    lhs_lower = lhs_raw.lower()
    rhs_upper = rhs_raw.upper()
    rhs_cn = _logic_cn_expr(rhs_raw, name_map=name_map, backend_module=backend)
    if not any(token in lhs_lower for token in ("state", "status", "result", "rlst", "ret")):
        if not any(token in lhs_label for token in ("状态", "结果", "检测")):
            return ""
    if rhs_upper.endswith("_ERR") or "ERROR" in rhs_upper or "FAULT" in rhs_upper or "告警" in rhs_cn or "故障" in rhs_cn:
        subject = _status_assignment_subject(lhs_label, raw_ident=lhs_raw)
        return f"标记{subject}为{_normalize_status_value_label(rhs_cn)}"
    if rhs_upper.endswith("_OK") or rhs_upper.endswith("_PASS") or "通过" in rhs_cn or "正常" in rhs_cn:
        subject = _status_assignment_subject(lhs_label, raw_ident=lhs_raw)
        return f"标记{subject}为{_normalize_status_value_label(rhs_cn)}"
    return ""


def _status_assignment_subject(label: str, *, raw_ident: str = "") -> str:
    value = re.sub(r"\s+", "", utils._safe_strip(label))
    raw_lower = utils._safe_strip(raw_ident).lower()
    if raw_lower.startswith(("l_state", "l_pbit", "l_result", "l_rlst")) and value in {"", "状态", "状态值", "结果"}:
        return "检测结果"
    if not value:
        return "检测结果"
    if value in {"状态", "状态值", "检测结果", "结果"}:
        return value
    if value.endswith(("状态", "状态值", "检测结果", "结果")):
        return value
    return f"{value}状态"


def _is_temp_value_label(text: str) -> bool:
    value = re.sub(r"\s+", "", utils._safe_strip(text))
    return value in {"中间结果", "中间值", "临时值", "暂存值"} or bool(re.fullmatch(r"(?:暂存|缓存)?(?:中间|临时).{0,4}", value))


def _strip_outer_parens(text: str) -> str:
    value = utils._safe_strip(text)
    for _ in range(6):
        if not (value.startswith("(") and value.endswith(")")):
            break
        depth = 0
        balanced_outer = True
        for idx, ch in enumerate(value):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(value) - 1:
                    balanced_outer = False
                    break
        if not balanced_outer:
            break
        value = value[1:-1].strip()
    return value


def _render_assignment_ref_label(expr: str, *, name_map: Optional[dict[str, str]] = None, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = _strip_outer_parens(str(expr or "").replace("->", "."))
    if not raw:
        return ""
    raw = re.sub(r"^\*\s*", "", raw).strip()
    if re.fullmatch(r"[A-Za-z_]\w*", raw):
        return ""
    alias = _lookup_logic_expr_alias(raw, name_map, backend_module=backend)
    if alias:
        return _normalize_assignment_ref_label(alias, backend_module=backend)

    indexed_member = _render_indexed_member_ref_label(raw, name_map=name_map, backend_module=backend)
    if indexed_member:
        return _normalize_assignment_ref_label(indexed_member, backend_module=backend)

    member_match = re.fullmatch(
        r"(?P<base>[A-Za-z_]\w*)\s*(?:\[\s*(?P<index>[^\]]+)\s*\])?\s*\.\s*(?P<member>[A-Za-z_]\w*)",
        raw,
    )
    if member_match:
        base_raw = utils._safe_strip(member_match.group("base"))
        index_raw = utils._safe_strip(member_match.group("index"))
        member_raw = utils._safe_strip(member_match.group("member"))
        base_cn = _logic_cn_expr(base_raw, name_map=name_map, backend_module=backend)
        member_cn = _prettify_logic_ident(member_raw, name_map, backend_module=backend)
        member_cn = _normalize_member_value_label(member_cn, backend_module=backend)
        if index_raw:
            index_cn = _logic_cn_expr(index_raw, name_map=name_map, backend_module=backend)
            index_cn = _normalize_array_index_value_label(index_cn, backend_module=backend)
            if index_cn and not _is_generic_index_label(index_cn):
                label = f"{index_cn}{member_cn}"
            else:
                label = f"{base_cn}当前项的{member_cn}" if base_cn else f"当前项的{member_cn}"
        else:
            label = f"{base_cn}的{member_cn}" if base_cn else member_cn
        return _normalize_assignment_ref_label(label, backend_module=backend)

    array_match = re.fullmatch(r"(?P<base>[A-Za-z_]\w*)\s*\[\s*(?P<index>[^\]]+)\s*\]", raw)
    if array_match:
        base_raw = utils._safe_strip(array_match.group("base"))
        index_raw = utils._safe_strip(array_match.group("index"))
        base_cn = _logic_cn_expr(base_raw, name_map=name_map, backend_module=backend)
        index_cn = _logic_cn_expr(index_raw, name_map=name_map, backend_module=backend)
        index_cn = _normalize_array_index_value_label(index_cn, backend_module=backend)
        if index_cn and not _is_generic_index_label(index_cn):
            return _normalize_assignment_ref_label(f"{base_cn}的{index_cn}项" if base_cn else f"{index_cn}项", backend_module=backend)
        return _normalize_assignment_ref_label(f"{base_cn}当前项" if base_cn else "当前项", backend_module=backend)
    return ""


def _render_indexed_member_ref_label(expr: str, *, name_map: Optional[dict[str, str]] = None, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(str(expr or "").replace("->", "."))
    if "." not in raw:
        return ""
    match = re.search(r"\.(?P<member>[A-Za-z_]\w*)\s*(?:\[\s*(?P<index>[^\]]+)\s*\])?\s*$", raw)
    if not match:
        return ""
    member_raw = utils._safe_strip(match.group("member"))
    index_raw = utils._safe_strip(match.group("index"))
    if not member_raw:
        return ""
    member_cn = _prettify_logic_ident(member_raw, name_map, backend_module=backend)
    member_cn = _normalize_member_value_label(member_cn, backend_module=backend)
    if not member_cn or member_cn == member_raw:
        return ""
    if index_raw:
        index_cn = _logic_cn_expr(index_raw, name_map=name_map, backend_module=backend)
        index_cn = _normalize_array_index_value_label(index_cn, backend_module=backend)
        if index_cn and not _is_generic_index_label(index_cn):
            return _combine_index_member_label(index_cn, member_cn)
    return member_cn


def _combine_index_member_label(index_cn: str, member_cn: str) -> str:
    index = re.sub(r"\s+", "", utils._safe_strip(index_cn))
    member = re.sub(r"\s+", "", utils._safe_strip(member_cn))
    if not index:
        return member
    if not member:
        return index
    member = re.sub(r"^(?:高、低|高低)", "", member)
    if index.endswith("握手") and member.startswith("握手"):
        member = member[len("握手"):]
    if index.endswith("状态") and member.startswith("状态"):
        member = member[len("状态"):]
    return f"{index}{member}"


def _is_generic_index_label(text: str) -> bool:
    value = re.sub(r"\s+", "", utils._safe_strip(text))
    return value in {"项", "当前项", "循环项", "索引", "循环索引", "下标", "计数", "计数值"}


def _normalize_assignment_ref_label(text: str, *, backend_module=None) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = value.replace("缓存值[", "").replace("]", "")
    value = re.sub(r"^\d+\s*[-－]\s*(?:模拟量|通道)\s*", "", value)
    value = value.replace("的滤波后", "滤波值")
    value = value.replace("滤波后", "滤波值")
    value = value.replace("滤波数据", "滤波值")
    value = re.sub(r"(?:数据指针|指针)(?:的)?当前项的", "当前项的", value)
    value = re.sub(r"(?:数据指针|指针)项的", "当前项的", value)
    value = re.sub(r"当前项的滤波值", "当前项滤波值", value)
    value = re.sub(r"的当前项$", "当前项", value)
    value = re.sub(r"项项", "项", value)
    value = re.sub(r"\s+", "", value)
    return value


def _normalize_status_value_label(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = value.replace("该PBIT测试项告警", "告警状态")
    value = value.replace("该PBIT测试项通过", "通过状态")
    return value


def _strip_ascii_parenthetical_hint(text: str) -> str:
    value = utils._safe_strip(text)
    if not value or not text_utils._contains_cjk(value):
        return value
    value = re.sub(r"\s*[（(]\s*[A-Za-z_][A-Za-z0-9_]*\s*[）)]\s*", " ", value).strip()
    return re.sub(r"\s+", " ", value).strip()


def _normalize_member_value_label(text: str, *, backend_module=None) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = _strip_ascii_parenthetical_hint(value)
    replacements = {
        "滤波数据": "滤波值",
        "滤波后": "滤波值",
        "filtData": "滤波值",
        "filtData_f": "滤波值",
    }
    return replacements.get(value, value)


def _normalize_array_index_value_label(text: str, *, backend_module=None) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = re.sub(r"^\d+\s*[-－]\s*(?:模拟量|通道)\s*", "", value)
    value = re.sub(r"\s+", "", value)
    return value


def _infer_pack_label(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return ""
    match = re.search(r"(\d{3})", value)
    if match:
        return f"{match.group(1)}字故障输出数据"
    if "pack" in value.lower():
        return "输出数据"
    return ""


def _normalize_logic_compute_target(text: str, *, raw_ident: str = "", backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    ident = utils._safe_strip(raw_ident)
    compact = re.sub(r"\s+", "", value)
    ident_compact = re.sub(r"\s+", "", ident)
    lower_ident = ident_compact.lower()
    if not value:
        return value
    pointer_like = ident_compact.startswith("*") or compact.startswith("*")
    if pointer_like:
        value = value.lstrip("*").strip()
        if value:
            return f"{value}指向的变量"
    if compact.startswith("存放l_") or compact.startswith("缓存l_"):
        value = value[2:] if value.startswith("存放") else value[2:]
    if any(token in lower_ident for token in ("ratio", "scale")):
        return "换算系数"
    if "gain" in lower_ident:
        return "增益系数"
    if any(token in lower_ident for token in ("temp", "tmp")):
        return "中间结果"
    if compact.startswith("存放") and ident_compact:
        tail = compact[2:]
        if tail == ident_compact:
            guessed = _semantic_label_for_ident(ident, backend_module=backend) or backend._guess_cn_from_ident(ident)
            if guessed and guessed != ident:
                return guessed
            if any(token in lower_ident for token in ("ratio", "scale")):
                return "换算系数"
            if "gain" in lower_ident:
                return "增益系数"
            return "中间结果"
    return value


def _guess_cn_for_low_quality_local_ident(ident: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(ident)
    lower = raw.lower()
    if not raw:
        return ""
    semantic_label = _semantic_label_for_ident(raw, backend_module=backend)
    if semantic_label:
        return semantic_label
    if any(token in lower for token in ("ratio", "scale")):
        return "换算系数"
    if "gain" in lower:
        return "增益系数"
    match = re.search(r"l_data(\d{3})_", lower)
    if match:
        return f"{match.group(1)}字打包缓存"
    if "actcompat" in lower:
        return "作动器故障兼容字"
    if "modesrccompat" in lower:
        return "模式源字"
    if lower.endswith("srcerr_u16"):
        return "源有效性错误标志"
    if lower.endswith("modeerr_u16"):
        return "模式错误标志"
    guessed = backend._guess_cn_from_ident(raw)
    if guessed and guessed != raw:
        return guessed
    return ""


def _semantic_label_for_ident(ident: str, *, backend_module=None) -> str:
    try:
        from . import semantic_registry

        return utils._safe_strip(semantic_registry.infer_local_semantic_label(ident))
    except Exception:
        return ""


def _replace_low_quality_local_phrases(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return value
    return re.sub(
        r"(?:存放|缓存)(l_[A-Za-z_]\w*)",
        lambda m: _guess_cn_for_low_quality_local_ident(m.group(1), backend_module=backend) or "中间结果",
        value,
    )


def _is_one_literal(text: str) -> bool:
    return bool(re.fullmatch(r"\(?\s*1(?:[uUlL]*)\s*\)?", utils._safe_strip(text)))


def _render_shift_expression_text(expr: str, target: str = "", *, name_map: Optional[dict[str, str]] = None, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(expr)
    if "<<" not in value and ">>" not in value:
        return ""
    compact = value
    compact = re.sub(r"\(\s*(0[xX]1|1)(?:[uUlL]*)\s*\)", r"\1", compact)
    for _ in range(4):
        compact = re.sub(r"^\((.*)\)$", r"\1", compact.strip())
    match = re.search(r"\(*\s*(0[xX]1|1)(?:[uUlL]*)\s*\)*\s*<<\s*\(?\s*([A-Za-z_]\w*|\d+)(?:[uUlL]*)\s*\)?", compact)
    if match:
        bit = utils._safe_strip(match.group(2))
        bit_cn = _logic_cn_expr(bit, name_map=name_map, backend_module=backend)
        return f"构造第{bit_cn}位标志"
    match = re.fullmatch(r"(.+?)\s*(<<|>>)\s*(.+)", compact)
    if match:
        left = _logic_cn_expr(match.group(1), name_map=name_map, backend_module=backend)
        op = "左移" if match.group(2) == "<<" else "右移"
        count = _logic_cn_expr(match.group(3), name_map=name_map, backend_module=backend)
        return f"将{left}{op}{count}位"
    return ""


def _is_flag_like_label(text: str) -> bool:
    value = utils._safe_strip(text)
    return bool(value) and any(token in value for token in ("标志", "状态", "完成", "关闭指令", "使能"))


def _is_index_like_label(text: str) -> bool:
    value = utils._safe_strip(text)
    return bool(value) and any(token in value for token in ("索引", "下标", "序号"))


_CALL_ROLE_ACTION_PREFIXES = (
    "读取",
    "获取",
    "采集",
    "清除",
    "置位",
    "翻转",
    "初始化",
    "复位",
    "汇总",
    "解包",
    "打包",
    "转换",
    "同步",
    "更新",
    "检查",
    "设置",
    "拉低",
    "拉高",
    "等待",
    "保持",
    "按",
    "将",
    "把",
    "置",
    "下发",
    "上报",
    "切入",
    "切换",
    "判定",
    "结束",
    "禁止",
    "允许",
)


def _is_specific_call_role(role: str) -> bool:
    text = str(role or "").strip()
    if not text:
        return False
    return text not in {"相关处理", "相关计算", "相关更新", "状态更新", "控制处理", "设置处理", "选择处理", "条件判定", "状态检查", "读取数据", "读取结果"}


_GENERIC_CALL_ROLES = {"相关处理", "相关计算", "相关更新", "状态更新", "控制处理", "设置处理", "选择处理", "条件判定", "状态检查", "读取数据", "读取结果"}


def _specific_role_from_callee(callee_text: str, current_role: str) -> str:
    if not callee_text:
        return ""
    try:
        from . import semantic_registry

        specific_role = utils._safe_strip(semantic_registry.classify_call_role(callee_text))
    except Exception:
        specific_role = ""
    if not specific_role:
        return ""
    if specific_role == current_role or specific_role in _GENERIC_CALL_ROLES:
        return ""
    return specific_role


def _render_specific_call_role_text(role_text: str) -> str:
    role_text = utils._safe_strip(role_text)
    if not role_text:
        return ""
    if role_text.startswith(_CALL_ROLE_ACTION_PREFIXES) or role_text.startswith("执行"):
        return role_text
    return f"执行{role_text}"


_CALL_ACTION_TOKEN_MAP = {
    "select": "选择",
    "sel": "选择",
    "get": "获取",
    "read": "读取",
    "obtain": "获取",
    "check": "检查",
    "verify": "校验",
    "judge": "判定",
    "clear": "清除",
    "clr": "清除",
    "reset": "复位",
    "rst": "复位",
    "update": "更新",
    "set": "设置",
    "write": "写入",
    "init": "初始化",
    "calc": "计算",
    "cal": "计算",
    "compute": "计算",
}


_CALL_ACTION_CN_SUFFIXES = {
    "选择": ("选择",),
    "获取": ("获取", "读取", "采集"),
    "读取": ("读取", "获取", "采集"),
    "检查": ("检查", "校验", "检测"),
    "校验": ("校验", "检查", "检测"),
    "判定": ("判定", "判断"),
    "清除": ("清除", "清零", "清空"),
    "复位": ("复位",),
    "更新": ("更新",),
    "设置": ("设置",),
    "写入": ("写入",),
    "初始化": ("初始化",),
    "计算": ("计算",),
}


def _render_named_call_action_from_ident(
    func: str,
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(func)
    if not raw:
        return ""
    tokens = text_utils._split_ident_tokens(raw)
    verb = ""
    for token in reversed(tokens):
        verb = _CALL_ACTION_TOKEN_MAP.get(utils._safe_strip(token).lower(), "")
        if verb:
            break
    if not verb:
        return ""
    func_cn = utils._safe_strip(_map_func_ident(raw, name_map, backend_module=backend))
    if not func_cn:
        return ""
    compact = re.sub(r"\s+", "", func_cn)
    compact = re.sub(r"函数$", "", compact)
    suffixes = _CALL_ACTION_CN_SUFFIXES.get(verb, (verb,))
    obj = compact
    for suffix in suffixes:
        if obj.endswith(suffix) and len(obj) > len(suffix):
            obj = obj[: -len(suffix)]
            break
    if obj.startswith(verb) and len(obj) > len(verb):
        obj = obj[len(verb):]
    obj = obj.strip("，,；;：: ")
    if not obj or obj in {"函数", "数据", "结果", "处理", "操作"}:
        return ""
    return f"{verb}{obj}"


def _clean_definition_comment_lines(definition_comment: str, *, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(definition_comment)
    if not raw:
        return []
    desc = raw
    if re.search(r"(?:\[|【)\s*(?:功能描述|功能说明|功能)\s*(?:\]|】)", raw):
        try:
            parsed = parse_utils.parse_single_comment_block(raw)
            parsed_desc = utils._safe_strip((parsed or {}).get("desc"))
            if parsed_desc:
                desc = parsed_desc
        except Exception:
            desc = raw
    out: list[str] = []
    for line in str(desc or "").splitlines():
        value = utils._safe_strip(line)
        if not value:
            continue
        value = re.sub(r"^/\*+", "", value)
        value = re.sub(r"\*/$", "", value)
        value = re.sub(r"^\*+", "", value).strip()
        value = re.sub(r"^(?:\[(?:功能描述|功能说明|功能)\]|【(?:功能描述|功能说明|功能)】)\s*[:：]?\s*", "", value).strip()
        if not value:
            continue
        if re.match(r"^(?:输入参数|输出参数|其他说明|返回|返回值|函数名|函数名称)\s*[:：]", value):
            continue
        if parse_utils._looks_like_placeholder_desc(value):
            continue
        if re.match(r"^[A-Za-z_]\w*\s*[：:]", value):
            continue
        if backend._is_noop_comment(value) or backend._looks_like_logic_noise_comment(value):
            continue
        value = re.sub(r"[。；;]+$", "", value).strip()
        if value:
            out.append(value)
    return out


def _looks_like_definition_comment_action(text: str) -> bool:
    value = re.sub(r"\s+", "", utils._safe_strip(text))
    if len(value) < 4 or len(value) > 72:
        return False
    if not text_utils._contains_cjk(value):
        return False
    return bool(
        re.search(
            r"(?:读取|获取|采集|检查|校验|判断|设置|更新|写入|清除|清空|同步|转换|打包|解包|汇总|初始化|复位|建立|发送|下发|上报|切入|切换|结束|收口|禁止|允许|计算|执行|控制|选择|按|把|将|置)",
            value,
        )
    )


def _definition_comment_action(definition_comment: str, *, backend_module=None) -> str:
    lines = _clean_definition_comment_lines(definition_comment, backend_module=backend_module)
    if not lines:
        return ""
    first = lines[0]
    if not _looks_like_definition_comment_action(first):
        return ""
    selected = first
    if len(re.sub(r"\s+", "", first)) <= 32 and len(lines) > 1:
        second = lines[1]
        candidate = f"{first}，{second}"
        if _looks_like_definition_comment_action(second) and len(re.sub(r"\s+", "", candidate)) <= 72:
            selected = candidate
    selected = re.sub(r"^(?:本函数|该函数|此函数)\s*", "", utils._safe_strip(selected))
    selected = re.sub(r"[。；;]+$", "", selected).strip()
    return selected


def _render_call_role_action(
    callee: str,
    role: str,
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
    definition_comment: str = "",
) -> str:
    backend = backend_module or legacy_backend()
    role_text = utils._safe_strip(role)
    callee_text = utils._safe_strip(callee)
    if parse_utils._looks_like_placeholder_desc(role_text, func_name=callee_text):
        role_text = ""
    comment_action = _definition_comment_action(definition_comment, backend_module=backend)
    if not role_text and callee_text:
        if comment_action:
            return comment_action
        return _render_call_function_action(callee_text, name_map, backend_module=backend)
    if not role_text:
        return ""
    if comment_action and role_text in _GENERIC_CALL_ROLES:
        return comment_action
    if role_text in _GENERIC_CALL_ROLES and callee_text:
        specific_role = _specific_role_from_callee(callee_text, role_text)
        if specific_role:
            return _render_specific_call_role_text(specific_role)
        named_action = _render_named_call_action_from_ident(callee_text, name_map, backend_module=backend)
        if named_action:
            return named_action
    if role_text.startswith(_CALL_ROLE_ACTION_PREFIXES):
        return role_text
    if role_text.startswith("执行"):
        return role_text
    if role_text in {"状态更新", "相关更新"} and callee_text:
        specific_role = _specific_role_from_callee(callee_text, role_text)
        if specific_role:
            return _render_specific_call_role_text(specific_role)
        named_action = _render_named_call_action_from_ident(callee_text, name_map, backend_module=backend)
        if named_action:
            return named_action
        func_cn = _map_func_ident(callee_text, name_map, backend_module=backend)
        if func_cn:
            if func_cn.endswith("函数"):
                return f"调用{func_cn}"
            return f"调用{func_cn}函数"
        return _render_call_function_action(callee_text, name_map, backend_module=backend)
    if _is_specific_call_role(role_text):
        return f"执行{role_text}"
    if callee_text:
        if comment_action:
            return comment_action
        if role_text in _GENERIC_CALL_ROLES:
            return _render_call_function_action(callee_text, name_map, backend_module=backend)
        return f"{_render_call_function_action(callee_text, name_map, backend_module=backend)}完成{role_text}"
    return f"执行{role_text}"


def _line_updates_consume_call(updates: Sequence[dict[str, Any]], callee: str) -> bool:
    callee_text = utils._safe_strip(callee)
    if not callee_text:
        return False
    call_re = re.compile(rf"\b{re.escape(callee_text)}\s*\(")
    for item in updates or ():
        rhs = utils._safe_strip((item or {}).get("rhs"))
        if rhs and call_re.search(rhs):
            return True
    return False


def _looks_like_decl_assignment(lhs: str) -> bool:
    text = str(lhs or "").strip()
    if not text or " " not in text:
        return False
    return bool(
        re.match(
            r"^(?:static\s+|const\s+|volatile\s+|register\s+|signed\s+|unsigned\s+|struct\s+\w+\s+|union\s+\w+\s+|enum\s+\w+\s+|[A-Za-z_]\w*\s+)+[*\s]*[A-Za-z_]\w*(?:\s*\[[^\]]*\])?$",
            text,
        )
    )


def _simplify_decl_target(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return value
    match = re.search(r"([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)(?:\s*\[[^\]]*\])?$", value)
    if match:
        return utils._safe_strip(match.group(1))
    return value


def _should_skip_semantic_action(item: dict[str, Any], *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    lhs = utils._safe_strip(item.get("lhs"))
    rhs = utils._safe_strip(item.get("rhs"))
    kind = utils._safe_strip(item.get("kind"))
    compact = re.sub(r"\s+", "", f"{lhs}={rhs}")
    if re.match(r"^(?:for|if|while|switch)\s*\(", lhs, flags=re.IGNORECASE):
        return True
    if re.match(r"^(?:for|if|while|switch)\(", compact, flags=re.IGNORECASE):
        return True
    if kind in {"control_compute", "feedback_compute"} and re.match(r"^(?:for|if|while|switch)\b", lhs, flags=re.IGNORECASE):
        return True
    if _looks_like_decl_assignment(lhs):
        return True
    if kind == "reset_or_clear" and _looks_like_decl_assignment(lhs):
        return True
    if kind in {"control_compute", "feedback_compute"} and lhs and rhs and _looks_like_decl_assignment(lhs):
        return True
    return False


def _collapse_pattern_items_for_logic(items: Sequence[dict[str, Any]], *, backend_module=None) -> list[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    collapsed: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in (items or ()):
        item = dict(raw or {})
        pattern = utils._safe_strip(item.get("pattern"))
        label = utils._safe_strip(item.get("label"))
        subject = utils._safe_strip(item.get("subject"))
        if pattern in {"compat_word_fill", "pack_buffer_fill", "error_flag_assign", "validity_flag_assign", "counter_update", "mode_word_sync", "snapshot_compare", "filter_output"}:
            key = (pattern, label, subject)
        else:
            key = (pattern, label, subject + utils._safe_strip(item.get("object")))
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(item)
    return collapsed


def _coerce_comment_hint_objects(hints: Sequence[Any]) -> list[Any]:
    out: list[Any] = []
    for hint in hints or ():
        if hasattr(hint, "kind") and hasattr(hint, "text"):
            out.append(hint)
            continue
        if not isinstance(hint, dict):
            continue
        kind = utils._safe_strip(hint.get("kind"))
        text = utils._safe_strip(hint.get("text"))
        if not kind or not text:
            continue
        try:
            confidence = float(hint.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        out.append(SimpleNamespace(kind=kind, text=text, confidence=confidence))
    return out


def generate_logic_from_semantic_pack(
    logic_semantic_pack: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    backend_module=None,
    name_map: Optional[dict[str, str]] = None,
) -> tuple[str, list[dict[str, Any]]]:
    backend = backend_module or legacy_backend()
    pack = dict(logic_semantic_pack or {})
    effective_name_map: dict[str, str] = {}
    effective_name_map.update(dict(pack.get("name_map") or {}))
    effective_name_map.update(dict(pack.get("entity_aliases") or {}))
    effective_name_map.update(dict(name_map or {}))
    name_map = effective_name_map
    control_blocks = [dict(item) for item in (pack.get("control_blocks") or []) if isinstance(item, dict)]
    state_updates = [dict(item) for item in (pack.get("state_updates") or []) if isinstance(item, dict)]
    call_roles = [dict(item) for item in (pack.get("call_roles") or []) if isinstance(item, dict)]
    return_actions = [dict(item) for item in (pack.get("return_actions") or []) if isinstance(item, dict)]
    flow_actions = [dict(item) for item in (pack.get("flow_actions") or []) if isinstance(item, dict)]
    pattern_hits = [dict(item) for item in (pack.get("pattern_hits") or []) if isinstance(item, dict)]
    if not control_blocks and not state_updates and not call_roles and not return_actions and not flow_actions and not pattern_hits:
        return "", []

    def _is_if_chain_kind(kind: str) -> bool:
        return kind in {"if", "else_if", "else"}

    def _close_block(block: dict[str, Any], active_stack: list[dict[str, Any]]) -> None:
        tail = utils._safe_strip((block or {}).get("kind"))
        if _is_if_chain_kind(tail):
            lines.append("    " * len(active_stack) + "END IF")
        elif tail == "while":
            lines.append("    " * len(active_stack) + "END WHILE")
        elif tail == "for":
            lines.append("    " * len(active_stack) + "NEXT")
        elif tail == "switch":
            lines.append("    " * len(active_stack) + "END SWITCH")

    def _normalize_condition_literals(expr: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            return _normalize_simple_int_literal(match.group(0))

        return re.sub(r"\b(?:0[xX][0-9A-Fa-f]+|[0-9]+)(?:[uUlL]+)\b", _replace, expr or "")

    def _line_of(item: dict[str, Any]) -> int:
        rng = dict(item.get("range") or {})
        try:
            return int(rng.get("start_line") or 0)
        except Exception:
            return 0

    def _end_line_of(item: dict[str, Any]) -> int:
        rng = dict((item or {}).get("range") or {})
        try:
            value = int(rng.get("end_line") or 0)
        except Exception:
            value = 0
        start_line = _line_of(item)
        return value if value > start_line else 0

    def _block_depth(item: dict[str, Any]) -> int:
        try:
            meta = dict((item or {}).get("metadata") or {})
            return max(0, int(meta.get("brace_depth_before") or 0))
        except Exception:
            return 0

    block_start_lines: dict[int, list[dict[str, Any]]] = {}
    for item in control_blocks:
        line_no = _line_of(item)
        if line_no > 0:
            block_start_lines.setdefault(line_no, []).append(dict(item))
    updates_by_line: dict[int, list[dict[str, Any]]] = {}
    for item in state_updates:
        updates_by_line.setdefault(_line_of(item), []).append(item)
    calls_by_line: dict[int, list[dict[str, Any]]] = {}
    for item in call_roles:
        calls_by_line.setdefault(_line_of(item), []).append(item)
    returns_by_line: dict[int, list[dict[str, Any]]] = {}
    for item in return_actions:
        returns_by_line.setdefault(_line_of(item), []).append(item)
    flows_by_line: dict[int, list[dict[str, Any]]] = {}
    for item in flow_actions:
        flows_by_line.setdefault(_line_of(item), []).append(item)
    patterns_by_line: dict[int, list[dict[str, Any]]] = {}
    for item in pattern_hits:
        patterns_by_line.setdefault(_line_of(item), []).append(item)

    lines: list[str] = []
    stack: list[dict[str, Any]] = []
    ordered_lines = sorted({x for x in list(block_start_lines) + list(updates_by_line) + list(calls_by_line) + list(returns_by_line) + list(flows_by_line) + list(patterns_by_line) if x > 0})
    if not ordered_lines:
        ordered_lines = list(range(1, max(len(state_updates) + len(call_roles) + len(return_actions) + len(flow_actions) + len(pattern_hits), 1) + 1))

    def _render_flow_action_text(item: dict[str, Any]) -> str:
        kind = utils._safe_strip((item or {}).get("kind"))
        if kind == "continue":
            return "跳过本轮循环，进入下一轮循环"
        if kind == "break":
            for active in reversed(stack):
                active_kind = utils._safe_strip(active.get("kind"))
                if active_kind in {"for", "while"}:
                    return "退出当前循环"
                if active_kind == "switch":
                    return "结束当前分支"
            return "退出当前循环或分支"
        return ""

    for lineno in ordered_lines:
        current_blocks = block_start_lines.get(lineno) or []
        current_first = current_blocks[0] if current_blocks else {}
        current_first_kind = utils._safe_strip(current_first.get("kind"))
        current_first_parent = utils._safe_strip(current_first.get("parent"))
        while stack and _end_line_of(stack[-1]) > 0 and lineno > _end_line_of(stack[-1]):
            if (
                _is_if_chain_kind(current_first_kind)
                and current_first_kind in {"else_if", "else"}
                and _is_if_chain_kind(utils._safe_strip(stack[-1].get("kind")))
                and current_first_parent == utils._safe_strip(stack[-1].get("parent"))
            ):
                stack.pop()
                break
            popped = stack.pop()
            _close_block(popped, stack)

        for current_block in current_blocks:
            current_kind = utils._safe_strip(current_block.get("kind"))
            current_parent = utils._safe_strip(current_block.get("parent"))
            while stack:
                top = stack[-1]
                top_id = utils._safe_strip(top.get("id"))
                top_kind = utils._safe_strip(top.get("kind"))
                if (
                    _is_if_chain_kind(current_kind)
                    and current_kind in {"else_if", "else"}
                    and _is_if_chain_kind(top_kind)
                    and current_parent == utils._safe_strip(top.get("parent"))
                ):
                    stack.pop()
                    break
                if (
                    _is_if_chain_kind(current_kind)
                    and _is_if_chain_kind(top_kind)
                    and current_parent == utils._safe_strip(top.get("parent"))
                ):
                    popped = stack.pop()
                    _close_block(popped, stack)
                    continue
                if current_parent and current_parent == top_id:
                    break
                if _end_line_of(top) and lineno <= _end_line_of(top):
                    break
                current_depth = _block_depth(current_block)
                top_depth = _block_depth(top)
                if current_depth <= top_depth:
                    if _is_if_chain_kind(current_kind) and current_kind in {"else_if", "else"} and current_parent == utils._safe_strip(top.get("parent")):
                        stack.pop()
                        break
                    popped = stack.pop()
                    _close_block(popped, stack)
                    continue
                popped = stack.pop()
                _close_block(popped, stack)
            indent = "    " * len(stack)
            kind = current_kind
            cond = _normalize_condition_literals(utils._safe_strip(current_block.get("condition")))
            cond_cn, _ = _render_structured_condition_cn(cond, (), name_map, cfg, backend_module=backend) if cond else ("", False)
            if kind == "if":
                lines.append(f"{indent}IF {cond_cn} 时" if cond_cn else f"{indent}IF 条件成立时")
                stack.append(current_block)
            elif kind == "else_if":
                lines.append(f"{indent}ELSE IF {cond_cn} 时" if cond_cn else f"{indent}ELSE IF 条件成立时")
                stack.append(current_block)
            elif kind == "else":
                lines.append(f"{indent}ELSE")
                stack.append(current_block)
            elif kind == "while":
                lines.append(f"{indent}WHILE {cond_cn} 时" if cond_cn else f"{indent}WHILE 条件成立时")
                stack.append(current_block)
            elif kind == "for":
                lines.append(f"{indent}{_render_for_header_cn(cond, name_map=name_map, backend_module=backend)}")
                stack.append(current_block)
            elif kind == "switch":
                lines.append(f"{indent}SWITCH 根据 {cond_cn} 分支处理" if cond_cn else f"{indent}SWITCH 分支处理")
                stack.append(current_block)
            elif kind == "case":
                lines.append(f"{indent}CASE 分支 {cond_cn or utils._safe_strip(current_block.get('condition'))}")
            elif kind == "default":
                lines.append(f"{indent}DEFAULT 默认分支")

        indent = "    " * len(stack)
        line_patterns = _collapse_pattern_items_for_logic(patterns_by_line.get(lineno, []), backend_module=backend)
        if line_patterns:
            for item in line_patterns:
                text = _render_semantic_action_text(
                    {
                        "kind": utils._safe_strip(item.get("pattern")),
                        "label": utils._safe_strip(item.get("label")),
                        "lhs": utils._safe_strip(item.get("subject")),
                        "rhs": utils._safe_strip(item.get("object")),
                    },
                    name_map=name_map,
                    backend_module=backend,
                )
                if text:
                    lines.append(f"{indent}{text}")
        for item in updates_by_line.get(lineno, []):
            if line_patterns:
                line_kind = utils._safe_strip(item.get("kind"))
                if line_kind in {"pack_buffer_fill", "result_surface_write", "compat_word_fill", "mode_word_sync", "error_flag_assign", "validity_flag_assign", "counter_update", "snapshot_compare", "filter_output"}:
                    continue
            if _should_skip_semantic_action(item, backend_module=backend):
                continue
            text = _render_semantic_action_text(item, name_map=name_map, backend_module=backend)
            if text:
                lines.append(f"{indent}{text}")
        for item in calls_by_line.get(lineno, []):
            callee = utils._safe_strip(item.get("callee"))
            role = utils._safe_strip(item.get("role"))
            if _line_updates_consume_call(updates_by_line.get(lineno, []), callee):
                continue
            args = [utils._safe_strip(arg) for arg in (item.get("args") or [])]
            action = ""
            if callee == "memset" and len(args) >= 2:
                target_clean = args[0]
                for _ in range(3):
                    target_clean = re.sub(r"^\([^)]*\)\s*", "", target_clean).strip()
                target_clean = target_clean.lstrip("&").strip()
                tgt_cn = _logic_cn_expr(target_clean, name_map=name_map, backend_module=backend)
                value = utils._safe_strip(args[1])
                val_cn = _logic_cn_expr(value, name_map=name_map, backend_module=backend)
                action = f"清零{tgt_cn}" if re.match(r"^0([UuLl]*)$|^0x0([UuLl]*)$", value) else f"填充{tgt_cn}为{val_cn}"
            elif callee in {"memcpy", "memmove"} and len(args) >= 2:
                dst_cn = _logic_cn_expr(args[0], name_map=name_map, backend_module=backend)
                src_cn = _logic_cn_expr(args[1], name_map=name_map, backend_module=backend)
                action = f"拷贝{src_cn}到{dst_cn}"
            hints = _coerce_comment_hint_objects(item.get("comment_hints") or [])
            definition_comment = utils._safe_strip(item.get("definition_comment"))
            if not action:
                action = _render_call_role_action(
                    callee,
                    role,
                    name_map,
                    backend_module=backend,
                    definition_comment="" if hints else definition_comment,
                )
            if hints:
                action = apply_comment_hints_to_logic(
                    action,
                    hints,
                    mode=parse_utils._get_logic_comment_mode(cfg),
                    backend_module=backend,
                )
            if definition_comment and (not action or any(phrase in action for phrase in backend._GENERIC_LOGIC_PHRASES)):
                action = _render_call_role_action(
                    callee,
                    role,
                    name_map,
                    backend_module=backend,
                    definition_comment=definition_comment,
                )
            if action:
                lines.append(f"{indent}{action}")
        for item in flows_by_line.get(lineno, []):
            action = _render_flow_action_text(item)
            if action:
                lines.append(f"{indent}{action}")
        for item in returns_by_line.get(lineno, []):
            expr = utils._safe_strip(item.get("expr"))
            ternary_ret = _render_ternary_return_text(expr, name_map=name_map, backend_module=backend) if expr else ""
            if ternary_ret:
                lines.append(f"{indent}{ternary_ret}")
                continue
            expr_cn = _logic_cn_expr(expr, name_map=name_map, backend_module=backend) if expr else ""
            if re.fullmatch(r"返回结果(?:\s*[（(][^）)]*[）)])?", expr_cn):
                expr_cn = "处理结果"
            lines.append(f"{indent}返回 {expr_cn or expr}".rstrip())

    while stack:
        popped = stack.pop()
        _close_block(popped, stack)

    lines = _collapse_adjacent_pattern_logic_lines(lines, backend_module=backend)
    rendered = "\n".join([line for line in lines if utils._safe_strip(line)])
    return _polish_semantic_logic_text(rendered, backend_module=backend), []


def _collapse_adjacent_pattern_logic_lines(lines: Sequence[str], *, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    result: list[str] = []
    seen_in_run: set[tuple[str, str, int]] = set()

    def _pattern_key(line: str) -> tuple[str, str, int]:
        text = utils._safe_strip(line)
        indent_len = len(str(line or "")) - len(str(line or "").lstrip())
        for prefix in ("计算", "组装", "标记", "同步", "记录", "执行"):
            if text.startswith(prefix):
                normalized = re.sub(r"[；;]+$", "", text)
                return prefix, normalized, indent_len
        return "", "", indent_len

    for line in (lines or ()):
        key = _pattern_key(line)
        if not key[0] or backend._is_control_logic_line(utils._safe_strip(line)):
            seen_in_run.clear()
            result.append(str(line))
            continue
        if key in seen_in_run:
            continue
        seen_in_run.add(key)
        result.append(str(line))
    return result


def _polish_semantic_logic_text(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not text:
        return ""
    lines = [str(line or "") for line in str(text).splitlines()]
    polished = _polish_logic_lines(lines, backend_module=backend)
    polished = _cleanup_final_logic_lines(polished, backend_module=backend)
    return "\n".join(polished)


def _remove_empty_else_branches_indexed(lines: Sequence[tuple[tuple[int, ...], str]]) -> list[tuple[tuple[int, ...], str]]:
    """Drop empty ELSE markers while preserving their matching END IF."""
    result: list[tuple[tuple[int, ...], str]] = []
    items = list(lines or [])
    idx = 0
    while idx < len(items):
        sources, current = items[idx]
        current = str(current or "")
        stripped = current.strip()
        if stripped == "ELSE":
            nxt = idx + 1
            while nxt < len(items) and not str(items[nxt][1] or "").strip():
                nxt += 1
            if nxt < len(items) and str(items[nxt][1] or "").strip() == "END IF":
                idx += 1
                continue
        result.append((sources, current))
        idx += 1
    return result


def _remove_empty_else_branches(lines: Sequence[str]) -> list[str]:
    indexed = [((idx,), str(line or "")) for idx, line in enumerate(lines or [])]
    return [line for _sources, line in _remove_empty_else_branches_indexed(indexed)]


def _collapse_duplicate_setup_lines_indexed(lines: Sequence[tuple[tuple[int, ...], str]]) -> list[tuple[tuple[int, ...], str]]:
    """Collapse adjacent duplicate setup lines by their full normalized text."""
    result: list[tuple[tuple[int, ...], str]] = []
    last_global_setup_line: dict[str, int] = {}
    for sources, raw in lines or []:
        line = str(raw or "")
        stripped = line.strip()
        is_setup = bool(re.match(r"^(?:设置|初始化|清零).+", stripped))
        setup_key = ""
        if is_setup:
            setup_key = re.sub(r"\s+", " ", stripped)
            setup_key = re.sub(r"\s*([=＝])\s*", r"\1", setup_key)
            setup_key = setup_key.rstrip("；;").strip()
        indent = len(line) - len(line.lstrip(" "))
        if is_setup and indent == 0 and setup_key:
            previous = last_global_setup_line.get(setup_key)
            if previous is not None and previous == len(result) - 1:
                prev_sources, _prev_line = result[-1]
                result[-1] = (prev_sources + tuple(sources), line)
                continue
            last_global_setup_line[setup_key] = len(result)
        result.append((tuple(sources), line))
    return result


def _collapse_duplicate_setup_lines(lines: Sequence[str]) -> list[str]:
    indexed = [((idx,), str(line or "")) for idx, line in enumerate(lines or [])]
    return [line for _sources, line in _collapse_duplicate_setup_lines_indexed(indexed)]


def _cleanup_final_logic_lines(
    lines: Sequence[str],
    *,
    backend_module=None,
    return_index_map: bool = False,
) -> list[str] | tuple[list[str], dict[int, int]]:
    indexed = [((idx,), str(line or "")) for idx, line in enumerate(lines or [])]
    cleaned = _validate_control_blocks_indexed(indexed, backend_module=backend_module)
    cleaned = _remove_empty_else_branches_indexed(cleaned)
    cleaned = _collapse_duplicate_setup_lines_indexed(cleaned)
    cleaned_lines = [line for _sources, line in cleaned]
    if not return_index_map:
        return cleaned_lines
    index_map: dict[int, int] = {}
    for new_idx, (sources, _line) in enumerate(cleaned):
        for source_idx in sources:
            index_map[int(source_idx)] = new_idx
    return cleaned_lines, index_map


def _repair_domain_typos_in_logic_text(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = re.sub(r"受油模式\s*[（(]?\s*ECIEVE\s*[）)]?", "受油模式", value, flags=re.IGNORECASE)
    return value


def _repair_corrupt_hardware_aliases_in_logic(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    value = re.sub(
        r"标志位\([^；;，,、]*?RIUSendData_t[^；;，,、]*?\)",
        "RIU发送数据",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"标志位\([^；;，,、]*?RIU[^；;，,、]*?(?:Send|发送)数据\)",
        "RIU发送数据",
        value,
        flags=re.IGNORECASE,
    )
    return value.replace("RIUSend数据", "RIU发送数据")


def _polish_logic_lines(lines: Sequence[str], *, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    result: list[str] = []
    last_key = ""
    blocked_markers = ("存放l_", "调用函数围绕当前", "缓存缓存值")
    # Declaration-like Chinese phrases that shouldn't appear in logic flow
    _decl_cn_pattern = re.compile(r"^\s*(定义|声明|申明)\s*.*(指针|变量|常量|数组|结构|联合)")
    # Raw C expressions that leaked through into Chinese logic
    _raw_c_cast = re.compile(r"\(\s*(?:Uint16|uint16_t|Uint32|uint32_t|Uint8|uint8_t|int16_t|int32_t|int8_t|float|double)\s*\)")
    _raw_ternary = re.compile(r"\?\s*[^:]*\s*:")
    _raw_l_ident = re.compile(r"\bl_[a-z_]+\b")  # unresolved l_ local identifiers
    last_pack_label = ""
    last_result_surface_label = ""
    for raw_line in (lines or ()):
        line = str(raw_line or "").rstrip()
        if not utils._safe_strip(line):
            continue
        indent = line[: len(line) - len(line.lstrip())]
        body = _repair_corrupt_hardware_aliases_in_logic(_repair_domain_typos_in_logic_text(line.strip()))
        protected_control = _sanitize_control_logic_line(body, backend_module=backend)
        if protected_control:
            protected_control = re.sub(
                r"(?:存放|缓存)((?:ls|lc|lp|l|s)_[A-Za-z_][A-Za-z0-9_]*)",
                lambda m: _guess_cn_for_low_quality_local_ident(m.group(1), backend_module=backend) or "中间结果",
                protected_control,
            )
            protected_control = _repair_corrupt_hardware_aliases_in_logic(_repair_domain_typos_in_logic_text(protected_control))
            protected_control = _collapse_repeated_parenthesized_cjk(_dedupe_adjacent_cjk_phrases(protected_control))
            normalized_key = indent + re.sub(r"[；;]+$", "", protected_control)
            if normalized_key == last_key:
                continue
            last_key = normalized_key
            result.append(indent + protected_control)
            continue
        body = re.sub(
            r"(?:存放|缓存)((?:ls|lc|lp|l|s)_[A-Za-z_][A-Za-z0-9_]*)",
            lambda m: _guess_cn_for_low_quality_local_ident(m.group(1), backend_module=backend) or "中间结果",
            body,
        )
        body = re.sub(r"^计算\s+存放([^=]+)\s*=", r"计算 \1 =", body)
        body = re.sub(r"^(更新)存放", r"\1", body)
        body = body.replace("缓存缓存值", "缓存值")
        body = re.sub(r"\b存放(?:ls|lc|lp|l|s)_[A-Za-z_]\w*", "中间结果", body)
        body = re.sub(r"\b缓存(?:ls|lc|lp|l|s)_[A-Za-z_]\w*", "中间结果", body)
        body = _repair_corrupt_hardware_aliases_in_logic(_repair_domain_typos_in_logic_text(_humanize_logic_action_body(body, backend_module=backend)))
        body = _collapse_repeated_parenthesized_cjk(_dedupe_adjacent_cjk_phrases(body))
        body = re.sub(r"^将\s+(.+?)\s+写入\s+(.+?)([；;]?)$", r"将\1写入\2\3", body)
        body = re.sub(r"^返回\s+返回结果(?:\s*[（(][^）)]*[）)])?([；;]?)$", r"返回 处理结果\1", body)
        # Strip all parentheses from control lines — Chinese format doesn't need them
        is_control = bool(re.match(r"^(IF|ELSE\s*IF|WHILE|FOR|SWITCH|CASE|DEFAULT)\b", body))
        if is_control:
            body = body.replace("(", "").replace(")", "")
        else:
            # Remove C number type suffixes from action lines only (not control/CASE)
            body = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", body)
        # Fix "X 不等于 有效 时" → "X 不等于有效值时"
        body = re.sub(r"([\u4e00-\u9fff])\s+位标志", r"\1位标志", body)
        body = re.sub(r"(\S)\s+时$", r"\1时", body)
        body = re.sub(r"\s+", " ", body).strip()
        # Filter declaration-like lines, raw C expressions
        if any(marker in body for marker in blocked_markers):
            continue
        if (
            re.fullmatch(r"(?:数据指针|对应项|缓存值)(?:项)?(?:[；;])?", body)
            or re.search(r"(?:数据指针|对应项)对应项", body)
            or re.fullmatch(r"(?:计算|暂存|缓存|存放)\s*(?:数据指针|对应项|缓存值)(?:项)?(?:[；;])?", body)
        ):
            continue
        if _decl_cn_pattern.search(body):
            continue
        if _raw_c_cast.search(body):
            continue
        if _raw_ternary.search(body):
            continue
        if re.fullmatch(r"暂存\s*(?:1|0)(?:[；;])?", body):
            continue
        # Filter lines with unresolved l_ local identifiers in otherwise Chinese text
        if _raw_l_ident.search(body) and text_utils._contains_cjk(body):
            continue
        pack_match = re.match(r"组装(\d{3}字故障输出数据)", body)
        if pack_match:
            if last_pack_label == pack_match.group(1):
                continue
            last_pack_label = pack_match.group(1)
        else:
            last_pack_label = ""
        result_match = re.match(r"将(\d{3}字故障输出数据)写入结果面", body)
        if result_match:
            if last_result_surface_label == result_match.group(1):
                continue
            last_result_surface_label = result_match.group(1)
        else:
            last_result_surface_label = ""
        normalized_key = re.sub(r"[；;]+$", "", body)
        if normalized_key == last_key:
            continue
        last_key = normalized_key
        result.append(indent + body)
    return result


def _humanize_logic_action_body(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return value
    protected_control = _sanitize_control_logic_line(value, backend_module=backend)
    if protected_control:
        return protected_control
    value = re.sub(r"\b0[xX]([0-9A-Fa-f]+)[uUlL]*(?=$|[^A-Za-z0-9_])", lambda m: f"0x{m.group(1)}", value)
    value = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", value)
    value = re.sub(r"\(\s*(?:无符号|有符号)?\s*(?:8|16|32|64)位整型\s*\)\s*", "", value)
    value = re.sub(r"\(\s*(?:Uint(?:8|16|32|64)|Int(?:8|16|32|64)|uint(?:8|16|32|64)_t|int(?:8|16|32|64)_t)\s*\)\s*", "", value, flags=re.IGNORECASE)
    value = value.replace("临时32位整型", "临时值")
    value = value.replace("临时16位整型", "临时值")
    value = value.replace("临时8位整型", "临时值")
    value = re.sub(r"\bconst\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\*\.", "的", value)
    value = value.replace("Redun临时整体数据", "余度温度数据")
    value = re.sub(r"\bComm429Rx整体数据\b", "429接收数据", value)
    value = re.sub(r"缓存值\[([^\]]+)\]", r"\1", value)
    value = _repair_generated_array_fragment_text(value)
    value = re.sub(r"=\s*\(([^()]+(?:获取|读取|检查|检测)\([^()]*\))\)", r"= \1", value)
    value = re.sub(r"^计算\s+中间结果\s*=\s*(.+?)([；;]?)$", lambda m: _render_humanized_compute_line("中间结果", m.group(1), m.group(2), backend_module=backend), value)
    value = re.sub(r"^计算\s+中间值\s*=\s*(.+?)([；;]?)$", lambda m: _render_humanized_compute_line("中间值", m.group(1), m.group(2), backend_module=backend), value)
    value = re.sub(r"^计算\s+返回结果\s*=\s*(.+?)([；;]?)$", r"暂存\1作为返回结果\2", value)
    value = re.sub(r"^计算\s+(.+?)\s*=\s*(.+?)([；;]?)$", lambda m: _render_humanized_compute_line(m.group(1), m.group(2), m.group(3), backend_module=backend), value)
    value = re.sub(r"将\(([^()；;、]+)\)、([^；;、]+?)按位与结果写入([^；;]+)([；;]?)$", r"将\1按\2掩码后写入\3\4", value)
    value = re.sub(r"将([^；;、]+)、([^；;、]+?)按位与结果写入([^；;]+)([；;]?)$", r"将\1按\2掩码后写入\3\4", value)
    value = re.sub(r"将\(([^()；;、]+)\)、([^；;、]+?)按位或结果写入([^；;]+)([；;]?)$", r"将\1与\2合并后写入\3\4", value)
    value = re.sub(r"将([^；;、]+)、([^；;、]+?)按位或结果写入([^；;]+)([；;]?)$", r"将\1与\2合并后写入\3\4", value)
    return re.sub(r"\s+", " ", value).strip()


def _render_humanized_compute_line(lhs: str, rhs: str, suffix: str = "", *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    left = utils._safe_strip(lhs)
    right = utils._safe_strip(rhs)
    tail = suffix or ""
    if not left:
        return f"计算 {right}{tail}".strip()
    if _is_flag_like_label(left) and _is_one_literal(right):
        return f"置位{left}{tail}"
    if _is_flag_like_label(left) and _is_zero_literal(right):
        return f"清零{left}{tail}"
    shift_text = _render_shift_expression_text(right, left, backend_module=backend)
    if shift_text:
        if left in {"中间结果", "中间值"}:
            return f"暂存{shift_text}{tail}"
        return f"将{shift_text}写入{left}{tail}"
    if _is_temp_value_label(left):
        return f"暂存 {right}{tail}"
    if (
        left
        and right
        and left != right
        and _looks_like_humanized_reference_label(left)
        and not _is_temp_value_label(left)
    ):
        return f"将{right}写入{left}{tail}"
    if (
        left
        and right
        and left != right
        and ("项" in left or "项" in right or "数组" in left or "数组" in right)
        and not _is_index_like_label(left)
    ):
        return f"将{right}写入{left}{tail}"
    if left == "返回结果":
        return f"返回 {right}{tail}"
    call_match = re.fullmatch(r"([A-Za-z_]\w*|[\u4e00-\u9fffA-Za-z0-9_]+)\s*\((.*)\)", right)
    if call_match:
        func_name = call_match.group(1)
        if str(func_name).lower() == "systime" or "系统时间" in str(func_name):
            return f"记录当前系统时间到{left}{tail}"
        if re.search(r"[\u4e00-\u9fff]", str(func_name or "")):
            return f"计算 {left} = {right}{tail}"
        func_label = _map_func_ident(func_name, None, backend_module=backend)
        if func_label and not str(func_label).endswith("函数"):
            func_label = f"{func_label}函数"
        if func_label:
            return f"将{func_label}返回结果写入{left}{tail}"
    if re.search(r"\s[*×/+-]\s|[*×/]", right) and not re.search(r"\b(?:for|while|if)\b", right, flags=re.IGNORECASE):
        return f"由{right}计算得到{left}{tail}"
    return f"计算 {left} = {right}{tail}"


def _looks_like_humanized_reference_label(text: str) -> bool:
    value = re.sub(r"\s+", "", utils._safe_strip(text))
    if not value:
        return False
    if any(token in value for token in ("指针的", "当前项", "第")):
        return True
    return value.endswith("项") or bool(re.search(r"(?:缓存|数组).+项", value))


def _validate_control_blocks_indexed(
    lines: Sequence[tuple[tuple[int, ...], str]],
    *,
    backend_module=None,
) -> list[tuple[tuple[int, ...], str]]:
    """Fix control pairing while preserving switch case body nesting and source indexes."""
    backend = backend_module or legacy_backend()
    control_if = re.compile(r"^(\s*)IF\b")
    control_else_if = re.compile(r"^(\s*)ELSE\s+IF\b")
    control_else = re.compile(r"^(\s*)ELSE\b")
    control_end = re.compile(r"^(\s*)END\s+(DO\s+WHILE|IF|WHILE|SWITCH)\b")
    control_next = re.compile(r"^(\s*)NEXT\b")
    control_for = re.compile(r"^(\s*)FOR\b")
    control_while = re.compile(r"^(\s*)WHILE\b")
    control_switch = re.compile(r"^(\s*)SWITCH\b")
    control_do_while = re.compile(r"^(\s*)DO\s+WHILE\b")
    control_case = re.compile(r"^(\s*)CASE\b")
    control_default = re.compile(r"^(\s*)DEFAULT\b")

    cleaned: list[tuple[tuple[int, ...], str]] = []
    for sources, raw in (lines or ()):
        line = str(raw or "").rstrip()
        stripped = utils._safe_strip(line)
        if not stripped:
            continue
        leading = line[: len(line) - len(line.lstrip())]
        # Bracket residue cleanup
        body = _sanitize_control_logic_line(stripped, backend_module=backend) or stripped
        body = re.sub(r"^(IF\s.*?)\s*\(\s*$", r"\1 ", body)
        body = re.sub(r"^(IF\s.*?)\(\s*([^)]+?)\s*时$", r"\1\2时", body)
        body = re.sub(r"(\S)\s+时$", r"\1时", body)
        cleaned.append((tuple(sources), leading + body))

    def _indent_for_depth(depth: int) -> str:
        return "    " * max(0, int(depth or 0))

    # Stack-based control block pairing
    result: list[tuple[tuple[int, ...], str]] = []
    block_stack: list[str] = []  # tracks open IF/FOR/WHILE/DO WHILE/SWITCH plus CASE pseudo-regions

    for sources, line in cleaned:
        stripped = utils._safe_strip(line)

        is_else_if = bool(control_else_if.match(stripped))
        is_else_only = bool(control_else.match(stripped)) if not is_else_if else False
        if_m = control_if.match(stripped) if not is_else_if and not is_else_only else None
        for_m = control_for.match(stripped) if not if_m and not is_else_if and not is_else_only else None
        while_m = control_while.match(stripped) if not if_m and not is_else_if and not is_else_only and not for_m else None
        do_while_m = control_do_while.match(stripped) if not if_m and not is_else_if and not is_else_only and not for_m and not while_m else None
        switch_m = control_switch.match(stripped) if not if_m and not is_else_if and not is_else_only and not for_m and not while_m and not do_while_m else None
        case_m = control_case.match(stripped) if not if_m and not is_else_if and not is_else_only and not for_m and not while_m and not do_while_m and not switch_m else None
        default_m = control_default.match(stripped) if not if_m and not is_else_if and not is_else_only and not for_m and not while_m and not do_while_m and not switch_m and not case_m else None
        end_m = control_end.match(stripped)
        next_m = control_next.match(stripped)

        if if_m:
            block_stack.append("IF")
            result.append((sources, _indent_for_depth(len(block_stack) - 1) + stripped))
        elif is_else_if or is_else_only:
            # ELSE IF / ELSE continue the current IF chain — no new block
            result.append((sources, _indent_for_depth(max(0, len(block_stack) - 1)) + stripped))
        elif for_m:
            block_stack.append("FOR")
            result.append((sources, _indent_for_depth(len(block_stack) - 1) + stripped))
        elif while_m:
            block_stack.append("WHILE")
            result.append((sources, _indent_for_depth(len(block_stack) - 1) + stripped))
        elif do_while_m:
            block_stack.append("DO WHILE")
            result.append((sources, _indent_for_depth(len(block_stack) - 1) + stripped))
        elif switch_m:
            block_stack.append("SWITCH")
            result.append((sources, _indent_for_depth(len(block_stack) - 1) + stripped))
        elif case_m or default_m:
            if "SWITCH" in block_stack:
                if block_stack and block_stack[-1] == "CASE":
                    block_stack.pop()
                result.append((sources, _indent_for_depth(len(block_stack)) + stripped))
                block_stack.append("CASE")
            else:
                result.append((sources, _indent_for_depth(len(block_stack)) + stripped))
        elif end_m:
            end_kind = end_m.group(2)
            if end_kind == "SWITCH" and block_stack and block_stack[-1] == "CASE":
                block_stack.pop()
            if block_stack and block_stack[-1] == end_kind:
                depth = max(0, len(block_stack) - 1)
                block_stack.pop()
                result.append((sources, _indent_for_depth(depth) + f"END {end_kind}"))
            elif block_stack and end_kind == "IF" and block_stack[-1] in ("FOR", "WHILE", "DO WHILE", "SWITCH", "CASE"):
                # Mismatched END against non-IF block: skip
                pass
            elif block_stack:
                # Pop the top regardless (best-effort matching)
                depth = max(0, len(block_stack) - 1)
                block_stack.pop()
                result.append((sources, _indent_for_depth(depth) + stripped))
            # else: orphaned END IF — skip
        elif next_m:
            if block_stack and block_stack[-1] == "FOR":
                depth = max(0, len(block_stack) - 1)
                block_stack.pop()
                result.append((sources, _indent_for_depth(depth) + "NEXT"))
            # else: orphaned NEXT — skip
        else:
            result.append((sources, _indent_for_depth(len(block_stack)) + stripped))

    # Append missing END IF for any unclosed blocks
    for kind in reversed(block_stack):
        depth = max(0, len(block_stack) - 1)
        if kind in ("IF", "ELSE_IF", "ELSE"):
            result.append(((), _indent_for_depth(depth) + "END IF"))
        elif kind == "FOR":
            result.append(((), _indent_for_depth(depth) + "NEXT"))
        elif kind == "WHILE":
            result.append(((), _indent_for_depth(depth) + "END WHILE"))
        elif kind == "DO WHILE":
            result.append(((), _indent_for_depth(depth) + "END DO WHILE"))
        elif kind == "SWITCH":
            result.append(((), _indent_for_depth(depth) + "END SWITCH"))
        block_stack.pop()

    return result


def _validate_control_blocks(lines: Sequence[str], *, backend_module=None) -> list[str]:
    """Fix IF/END IF pairing and bracket residues in generated logic lines.

    - Tracks IF / loop / SWITCH pairing via a stack
    - ELSE IF / ELSE do NOT create new blocks (they continue the same IF chain)
    - Appends missing END markers at end of output
    - Removes orphaned (unmatched) END IF
    - Cleans bracket residues like ``IF (xxx 时`` → ``IF xxx 时``
    """
    indexed = [((idx,), str(line or "")) for idx, line in enumerate(lines or [])]
    return [line for _sources, line in _validate_control_blocks_indexed(indexed, backend_module=backend_module)]


def select_ai_logic_polish_unknowns(
    logic: str,
    *,
    max_items: int = 12,
    backend_module=None,
) -> list[dict[str, Any]]:
    """
    Pick action-only flowchart lines that are safe for AI wording polish.

    The returned shape intentionally reuses the existing ``unknowns`` contract:
    AI may replace only these exact line indexes, while control structure lines
    remain locked by the caller.
    """
    backend = backend_module or legacy_backend()
    out: list[dict[str, Any]] = []
    forced_markers = (
        "待人工修改",
        "执行操作",
        "对应项",
        "数据指针",
        "缓存值",
        "存放l_",
        "调用函数围绕当前",
    )
    generic_call_markers = (
        "调用函数",
        "函数",
        "完成相关处理",
        "完成相关计算",
        "完成相关更新",
    )
    protected_prefixes = (
        "组装",
        "汇总",
        "写入结果面",
        "清空结果面",
        "执行数据字打包",
        "执行数字滤波",
    )
    lines = str(logic or "").splitlines()
    for idx, raw in enumerate(lines):
        if len(out) >= max(0, int(max_items or 0)):
            break
        line = str(raw or "").rstrip()
        body = utils._safe_strip(line)
        if not body:
            continue
        if _is_control_logic_line(body) or body.startswith("初始化"):
            continue
        reason = ""
        priority = 0
        if any(marker in body for marker in forced_markers):
            reason = "bad_static_marker"
            priority = 100
        elif any(marker in body for marker in generic_call_markers):
            reason = "generic_call"
            priority = 80
        if not reason:
            continue
        indent = line[: len(line) - len(line.lstrip())]
        out.append(
            {
                "idx": idx,
                "code": "",
                "code_cn": body,
                "indent": indent,
                "comment_hints": [],
                "polish_only": True,
                "polish_reason": reason,
                "polish_priority": priority,
            }
        )
    return out


def _split_inline_c_statements(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    parts: list[str] = []
    cur: list[str] = []
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0
    in_squote = False
    in_dquote = False
    escape = False
    for ch in value:
        cur.append(ch)
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
            depth_paren += 1
            continue
        if ch == ")":
            depth_paren = max(0, depth_paren - 1)
            continue
        if ch == "[":
            depth_brack += 1
            continue
        if ch == "]":
            depth_brack = max(0, depth_brack - 1)
            continue
        if ch == "{":
            depth_brace += 1
            continue
        if ch == "}":
            depth_brace = max(0, depth_brace - 1)
            continue
        if ch == ";" and depth_paren == 0 and depth_brack == 0 and depth_brace == 0:
            stmt = "".join(cur).strip()
            if stmt:
                parts.append(stmt)
            cur = []
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
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
            if depth == 0:
                return idx
    return -1


def _find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
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
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _expand_inline_control_line_infos(line_infos: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    def _clone(info: dict[str, Any], code: str, *, comments: Optional[list[str]] = None) -> dict[str, Any]:
        return {
            "raw": code,
            "code": code,
            "comments": list(comments if comments is not None else []),
            "attached": [],
            "hints": [],
            "attached_origin": "none",
        }

    def _expand_one(info: dict[str, Any]) -> list[dict[str, Any]]:
        code = str(info.get("code") or "").strip()
        if not code:
            return [dict(info)]
        m_do = re.match(r"^do\b(.*)$", code, flags=re.S)
        if m_do:
            rest_do = (m_do.group(1) or "").strip()
            if rest_do.startswith("{"):
                close_brace = _find_matching_brace(rest_do, 0)
                if close_brace >= 0:
                    body_do = rest_do[1:close_brace].strip()
                    tail_do = rest_do[close_brace + 1 :].strip()
                    m_while_tail = re.match(r"^while\s*\((.*)\)\s*;?\s*$", tail_do, flags=re.S)
                    if m_while_tail:
                        cond = (m_while_tail.group(1) or "").strip()
                        expanded = [_clone(info, f"do while({cond})", comments=list(info.get("comments") or [])), _clone(info, "{")]
                        for stmt in _split_inline_c_statements(body_do):
                            if stmt and stmt not in ("{", "}"):
                                expanded.extend(_expand_one(_clone(info, stmt)))
                        expanded.append(_clone(info, "}"))
                        return expanded
        if code.startswith("}"):
            close_count = 0
            while close_count < len(code) and code[close_count] == "}":
                close_count += 1
            tail = code[close_count:].strip()
            if tail:
                expanded = [_clone(info, "}") for _ in range(close_count)]
                expanded.extend(_expand_one(_clone(info, tail, comments=list(info.get("comments") or []))))
                return expanded
        m_case = re.match(r"^(case\s+[^:]+:|default\s*:?)\s*(.+)$", code, flags=re.S)
        if m_case:
            label = m_case.group(1).strip()
            body = (m_case.group(2) or "").strip()
            if body:
                expanded = [_clone(info, label, comments=list(info.get("comments") or []))]
                for stmt in _split_inline_c_statements(body):
                    if stmt:
                        expanded.extend(_expand_one(_clone(info, stmt)))
                return expanded
        prefix = ""
        rest = ""
        m_else = re.match(r"^else\b(.*)$", code, flags=re.S)
        if m_else and not re.match(r"^else\s+if\s*\(", code):
            prefix = "else"
            rest = m_else.group(1).strip()
        else:
            m_head = re.match(r"^(else\s+if|if|for|while|switch)\s*\(", code, flags=re.S)
            if not m_head:
                return [dict(info)]
            open_idx = code.find("(", m_head.end() - 1)
            close_idx = _find_matching_paren(code, open_idx)
            if close_idx < 0:
                return [dict(info)]
            prefix = code[: close_idx + 1].strip()
            rest = code[close_idx + 1 :].strip()
        if not rest:
            return [dict(info)]
        body = ""
        tail = ""
        if rest.startswith("{"):
            close_brace = _find_matching_brace(rest, 0)
            if close_brace < 0:
                return [dict(info)]
            body = rest[1:close_brace].strip()
            tail = rest[close_brace + 1 :].strip()
        else:
            body = rest.strip()
        if not body:
            return [dict(info)]
        comments = list(info.get("comments") or [])
        expanded = [_clone(info, prefix, comments=comments), _clone(info, "{")]
        for stmt in _split_inline_c_statements(body):
            if stmt not in ("{", "}"):
                expanded.extend(_expand_one(_clone(info, stmt)))
        expanded.append(_clone(info, "}"))
        if tail.startswith("else"):
            expanded.extend(_expand_one(_clone(info, tail)))
        elif tail:
            for stmt in _split_inline_c_statements(tail):
                if stmt:
                    expanded.extend(_expand_one(_clone(info, stmt)))
        return expanded

    expanded: list[dict[str, Any]] = []
    for info in line_infos or ():
        expanded.extend(_expand_one(dict(info)))

    normalized: list[dict[str, Any]] = []
    i = 0
    while i < len(expanded):
        info = expanded[i]
        code = str(info.get("code") or "").strip()
        if code == "do" and i + 1 < len(expanded) and str(expanded[i + 1].get("code") or "").strip() == "{":
            depth = 0
            close_idx: Optional[int] = None
            for j in range(i + 1, len(expanded)):
                part = str(expanded[j].get("code") or "").strip()
                if part == "{":
                    depth += 1
                elif part == "}":
                    depth -= 1
                    if depth == 0:
                        close_idx = j
                        break
            if close_idx is not None and close_idx + 1 < len(expanded):
                tail = str(expanded[close_idx + 1].get("code") or "").strip()
                m_tail = re.match(r"^while\s*\((.*)\)\s*;?\s*$", tail, flags=re.S)
                if m_tail:
                    cond = (m_tail.group(1) or "").strip()
                    normalized.append(_clone(info, f"do while({cond})", comments=list(info.get("comments") or [])))
                    normalized.extend(expanded[i + 1 : close_idx + 1])
                    i = close_idx + 2
                    continue
        normalized.append(info)
        i += 1
    return normalized


def _merge_multiline_expression_line_infos(line_infos: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for info in line_infos or ():
        current = dict(info)
        code = str(current.get("code") or "").strip()
        if merged and code and not re.match(r"^(?:if|else|for|while|switch|case|default|return|break|continue)\b", code):
            prev_code = str(merged[-1].get("code") or "").rstrip()
            prev_is_control = bool(
                re.match(r"^(?:if|else|for|while|switch|case|default|return|break|continue)\b", prev_code)
            )
            # Continuation if either the next line starts with an operator
            # (existing behavior) or the previous line ends in ``=`` (new
            # behavior for multi-line struct-field / array-element
            # assignments).  Without the second case, an assignment
            # statement like
            #     s_xxx.f1 =
            #         l_xxx.f1;
            # was being split into two ``raw`` IR nodes, which the
            # downstream simple-action renderer can't translate, so the
            # whole statement fell back to the ``待人工修改`` placeholder.
            if re.match(r"^(?:[&|^]|&&|\|\|)\s*\S+", code):
                pass
            elif (not prev_is_control) and prev_code.endswith("=") and not prev_code.endswith("==") and not prev_code.endswith("!=") and not prev_code.endswith("<=") and not prev_code.endswith(">="):
                pass
            else:
                merged.append(current)
                continue
            prev = merged[-1]
            joiner = " " if prev_code else ""
            prev["code"] = f"{prev_code}{joiner}{code}"
            prev_raw = str(prev.get("raw") or "").rstrip()
            prev["raw"] = f"{prev_raw}{joiner}{str(current.get('raw') or code).strip()}"
            prev_comments = list(prev.get("comments") or [])
            for comment in list(current.get("comments") or []):
                if comment and comment not in prev_comments:
                    prev_comments.append(comment)
            prev["comments"] = prev_comments
            continue
        merged.append(current)
    return merged


def generate_logic_from_body(
    body: str,
    local_vars,
    cfg,
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
):
    backend = backend_module or legacy_backend()
    lines = parse_utils._join_c_line_continuations(body).splitlines()
    comment_mode = parse_utils._get_logic_comment_mode(cfg)
    use_comment = comment_mode != "off"
    use_cond_comment = comment_mode in {"legacy_inline", "hint_only"} and bool(utils.cfg_get_int(cfg, "structured_cond_use_comment", 1))
    literal_mode = comment_mode == "off"

    if backend._is_small_model_strict_mode(cfg):
        ai_policy = (getattr(cfg, "ai_logic_policy", "hybrid") or "hybrid").strip().lower()
        _ = ai_policy

    line_infos = []
    for raw in lines:
        tmp = raw
        block_comments = re.findall(r"/\*\s*(.*?)\s*\*/", tmp)
        block_comments = [c.strip() for c in block_comments if c.strip()]
        tmp = re.sub(r"/\*.*?\*/", "", tmp)
        line_comment = None
        m = re.search(r"//(.*)", tmp)
        if m:
            line_comment = m.group(1).strip()
            tmp = tmp[: m.start()]
        comments = block_comments[:]
        if line_comment:
            comments.append(line_comment)
        code_no_cmt = tmp.strip()
        line_infos.append(
            {
                "raw": raw,
                "code": code_no_cmt,
                "comments": comments,
                "attached": [],
                "hints": [],
                "attached_origin": "none",
            }
        )
    line_infos = _merge_multiline_expression_line_infos(_expand_inline_control_line_infos(line_infos))

    if use_comment:
        pending_comments = []
        for info in line_infos:
            code = info["code"]
            inline_comments = [c for c in info["comments"] if not parse_utils._is_non_semantic_comment(c)]
            core = code.replace("{", "").replace("}", "").replace(";", "").strip()
            if not core:
                pending_comments.extend(inline_comments)
                continue
            if is_declaration_line(code):
                pending_comments = []
                continue
            attached = []
            if inline_comments:
                attached.extend(inline_comments)
                pending_comments = []
                info["attached_origin"] = "inline"
            else:
                if pending_comments:
                    attached.extend(pending_comments)
                    pending_comments = []
                    info["attached_origin"] = "pending"
            info["attached"] = attached
            info["hints"] = parse_utils.extract_statement_hints(code, attached)
    else:
        for info in line_infos:
            info["attached"] = []
            info["hints"] = []
            info["attached_origin"] = "none"

    brace_depth = 0
    for info in line_infos:
        info["brace_depth_before"] = brace_depth
        code = info["code"]
        brace_depth += code.count("{")
        brace_depth -= code.count("}")
        info["brace_depth_after"] = brace_depth

    def next_significant_header(start_idx):
        for j in range(start_idx + 1, len(line_infos)):
            code = line_infos[j]["code"].strip()
            core = code.replace("{", "").replace("}", "").replace(";", "").strip()
            if not core:
                continue
            if is_declaration_line(code):
                continue
            header_local = code.lstrip()
            depth = line_infos[j].get("brace_depth_before")
            if re.match(r"^else\s+if\s*\(", header_local):
                return "ELSE IF", depth
            if re.match(r"^else\b", header_local):
                return "ELSE", depth
            return None, depth
        return None, None

    steps = []
    unknowns = []
    block_stack = []
    indent_level = 0
    case_active = False
    case_depth = None
    pending_bulk_steps: list[dict[str, str]] = []

    def calc_indent():
        base = sum(1 for b in block_stack if not b.get("no_body_indent"))
        if case_active:
            base += 1
        return base

    def indent():
        return "    " * indent_level

    def flush_pending_bulk_steps():
        if not pending_bulk_steps:
            return
        summary = _summarize_bulk_assignment_run(
            pending_bulk_steps,
            name_map=name_map,
            local_var_usages=local_var_usages,
            backend_module=backend,
        )
        if summary:
            steps.append(f"{pending_bulk_steps[0]['indent']}{summary}")
        else:
            for item in pending_bulk_steps:
                steps.append(f"{item['indent']}{item['text']}")
        pending_bulk_steps.clear()

    def emit_step_text(text: str, *, code_for_bulk: Optional[str] = None, allow_bulk: bool = False):
        if allow_bulk and code_for_bulk:
            new_group = _extract_assignment_group_key(code_for_bulk, backend_module=backend)
            if pending_bulk_steps:
                prev_group = pending_bulk_steps[-1].get("group_key") or ""
                if new_group and prev_group and new_group != prev_group:
                    flush_pending_bulk_steps()
            pending_bulk_steps.append(
                {
                    "indent": indent(),
                    "text": text,
                    "code": code_for_bulk,
                    "group_key": new_group,
                }
            )
            return
        flush_pending_bulk_steps()
        steps.append(f"{indent()}{text}")

    local_var_usages = {v["name"]: (v.get("cn_name") or v.get("usage") or "") for v in local_vars}
    # Merge local var Chinese names into name_map so all downstream sees them
    if name_map is None:
        name_map = {}
    for k, v in local_var_usages.items():
        if k and v and k not in name_map:
            name_map[k] = v

    def _is_generic_heuristic(text: Optional[str]) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        if not (t.startswith("将 ") and " 写入 " in t):
            return False
        # Only treat ``将 X 写入 Y`` as a generic filler when at least one
        # side is still a gap label (循环索引, 缓存值, 待人工修改, ...).
        # Once the parser/naming layers produce real, distinct semantic
        # names for both sides (e.g. ``将 sci信息的计数值 写入
        # CCDLComm信息项的计数值``) the line carries actionable content
        # and must be kept.
        m = re.match(r"^将\s+(.+?)\s+写入\s+(.+)$", t)
        if not m:
            return True
        lhs_cn, rhs_cn = m.group(1).strip(), m.group(2).strip()
        if not lhs_cn or not rhs_cn:
            return True
        if backend._is_missing_gap_text(lhs_cn) or backend._is_missing_gap_text(rhs_cn):
            return True
        if lhs_cn == rhs_cn:
            return True
        return False

    for idx, info in enumerate(line_infos):
        code = info["code"].strip()
        attached = info["attached"]
        hints = info.get("hints") or []
        if case_active and info.get("brace_depth_before", 0) < (case_depth or 0):
            case_active = False
            case_depth = None
        indent_level = calc_indent()
        if not code:
            continue
        if code in ("{", "{;}"):
            continue
        if is_noop_statement(code):
            continue
        header = code.lstrip()

        if code in ("}", "};"):
            flush_pending_bulk_steps()
            while block_stack and info.get("brace_depth_after") <= block_stack[-1].get("close_depth", -1):
                top = block_stack.pop()
                if top.get("type") == "SWITCH":
                    case_active = False
                    case_depth = None
                indent_level = calc_indent()
                t = top.get("type")
                if t == "IF":
                    nxt, nxt_depth = next_significant_header(idx)
                    same_level = nxt_depth is not None and nxt_depth == info.get("brace_depth_after")
                    if nxt in ("ELSE", "ELSE IF") and same_level:
                        block_stack.append(top)
                        indent_level = len(block_stack)
                        break
                    steps.append(f"{indent()}END IF")
                elif t == "FOR":
                    steps.append(f"{indent()}NEXT")
                elif t == "WHILE":
                    steps.append(f"{indent()}END WHILE")
                elif t == "DO WHILE":
                    steps.append(f"{indent()}END DO WHILE")
                elif t == "SWITCH":
                    steps.append(f"{indent()}END SWITCH")
            continue

        if re.match(r"^if\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg, use_cond_comment=use_cond_comment)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "IF", "close_depth": info.get("brace_depth_before", 0)})
            continue

        if re.match(r"^else\s+if\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = max(0, calc_indent() - 1)
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg, use_cond_comment=use_cond_comment)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "ELSE IF", "close_depth": info.get("brace_depth_before", 0), "no_body_indent": True})
            continue

        if re.match(r"^else\b", header):
            flush_pending_bulk_steps()
            indent_level = max(0, calc_indent() - 1)
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg)
            text = _render_logic_ir_node(
                node or {"kind": "else", "code": header},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "ELSE", "close_depth": info.get("brace_depth_before", 0), "no_body_indent": True})
            continue

        if re.match(r"^for\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "FOR", "close_depth": info.get("brace_depth_before", 0)})
            continue

        if re.match(r"^while\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg, use_cond_comment=use_cond_comment)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "WHILE", "close_depth": info.get("brace_depth_before", 0)})
            continue

        if re.match(r"^do\s+while\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg, use_cond_comment=use_cond_comment)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "DO WHILE", "close_depth": info.get("brace_depth_before", 0)})
            continue

        if re.match(r"^switch\s*\(", header):
            flush_pending_bulk_steps()
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            block_stack.append({"type": "SWITCH", "close_depth": info.get("brace_depth_before", 0)})
            continue

        if re.match(r"^case\b", header):
            flush_pending_bulk_steps()
            case_active = False
            case_depth = None
            indent_level = calc_indent()
            case_attached = attached if not (cfg.ai_assist and getattr(cfg, "ai_mode", 1) == 2) else []
            node = _build_logic_ir_node(header, attached=case_attached, name_map=name_map, cfg=cfg)
            text = _render_logic_ir_node(
                node or {"kind": "raw", "code": info["raw"]},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            case_active = True
            case_depth = info.get("brace_depth_before", 0)
            continue

        if re.match(r"^default\b", header):
            flush_pending_bulk_steps()
            case_active = False
            case_depth = None
            indent_level = calc_indent()
            node = _build_logic_ir_node(header, attached=attached, name_map=name_map, cfg=cfg)
            text = _render_logic_ir_node(
                node or {"kind": "default", "code": header},
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
            steps.append(f"{indent()}{text}")
            case_active = True
            case_depth = info.get("brace_depth_before", 0)
            continue

        if is_declaration_line(code):
            decl_action = _render_simple_decl_initializer_action(
                code,
                name_map=name_map,
                backend_module=backend,
            )
            if decl_action:
                emit_step_text(decl_action, code_for_bulk=code, allow_bulk=False)
            continue
        if not attached and not code.endswith(";"):
            continue
        core = re.sub(r"[{};]", "", code).strip()
        if not core:
            continue

        ir_node = _build_logic_ir_node(code, attached=attached, name_map=name_map, cfg=cfg, use_cond_comment=use_cond_comment)
        simple_action = ""
        if ir_node and utils._safe_strip(ir_node.get("kind")) in (
            "assign",
            "assign_call",
            "compound_assign",
            "call",
            "return",
            "break",
            "continue",
        ):
            simple_action = _render_logic_ir_node(
                ir_node,
                name_map=name_map,
                local_var_usages=local_var_usages,
                literal=literal_mode,
                backend_module=backend,
            )
        else:
            simple_action = _render_simple_statement_action(code, name_map=name_map, local_var_usages=local_var_usages, backend_module=backend)
        indent_level = calc_indent()
        ai_policy = (getattr(cfg, "ai_logic_policy", "hybrid") or "hybrid").strip().lower()

        if simple_action:
            simple_action = apply_comment_hints_to_logic(simple_action, hints, mode=comment_mode, backend_module=backend)
            emit_step_text(simple_action, code_for_bulk=code, allow_bulk=bool(_split_plain_assignment(code)))
            continue

        if cfg.ai_assist and getattr(cfg, "ai_mode", 1) == 2:
            flush_pending_bulk_steps()
            if ai_policy == "ai_non_structured":
                step_text = f"{indent()}待人工修改"
                unknowns.append(
                    {
                        "idx": len(steps),
                        "code": info["raw"].strip(),
                        "code_cn": _logic_cn_expr(info.get("code") or "", name_map=name_map, backend_module=backend),
                        "indent": indent(),
                        "comment_hints": [{"kind": h.kind, "text": h.text} for h in hints if h.kind not in ("history", "debug", "noise")],
                    }
                )
                steps.append(step_text)
            else:
                guess = heuristic_logic_line(code, name_map=name_map, literal=literal_mode, backend_module=backend)
                guess = apply_comment_hints_to_logic(guess or "", hints, mode=comment_mode, backend_module=backend)
                if guess and (not _is_generic_heuristic(guess)):
                    steps.append(f"{indent()}{guess}")
                else:
                    step_text = f"{indent()}待人工修改"
                    unknowns.append(
                        {
                            "idx": len(steps),
                            "code": info["raw"].strip(),
                            "code_cn": _logic_cn_expr(info.get("code") or "", name_map=name_map, backend_module=backend),
                            "indent": indent(),
                            "comment_hints": [{"kind": h.kind, "text": h.text} for h in hints if h.kind not in ("history", "debug", "noise")],
                            "fallback_text": guess or None,
                        }
                    )
                    steps.append(step_text)
            continue

        if cfg.ai_assist and ai_policy == "ai_non_structured":
            flush_pending_bulk_steps()
            step_text = f"{indent()}待人工修改"
            unknowns.append(
                {
                    "idx": len(steps),
                    "code": info["raw"].strip(),
                    "code_cn": _logic_cn_expr(info.get("code") or "", name_map=name_map, backend_module=backend),
                    "indent": indent(),
                    "comment_hints": [{"kind": h.kind, "text": h.text} for h in hints if h.kind not in ("history", "debug", "noise")],
                }
            )
            steps.append(step_text)
            continue

        if cfg.ai_assist:
            flush_pending_bulk_steps()
            guess = heuristic_logic_line(code, name_map=name_map, literal=literal_mode, backend_module=backend)
            guess = apply_comment_hints_to_logic(guess or "", hints, mode=comment_mode, backend_module=backend)
            if guess and (not _is_generic_heuristic(guess)):
                steps.append(f"{indent()}{guess}")
            else:
                step_text = f"{indent()}待人工修改"
                unknowns.append(
                    {
                        "idx": len(steps),
                        "code": info["raw"].strip(),
                        "code_cn": _logic_cn_expr(info.get("code") or "", name_map=name_map, backend_module=backend),
                        "indent": indent(),
                        "comment_hints": [{"kind": h.kind, "text": h.text} for h in hints if h.kind not in ("history", "debug", "noise")],
                        "fallback_text": guess or None,
                    }
                )
                steps.append(step_text)
        else:
            guess = heuristic_logic_line(code, name_map=name_map, literal=literal_mode, backend_module=backend)
            guess = apply_comment_hints_to_logic(guess or "", hints, mode=comment_mode, backend_module=backend)
            if guess:
                emit_step_text(guess, code_for_bulk=code, allow_bulk=bool(_split_plain_assignment(code)))
            else:
                flush_pending_bulk_steps()
                if literal_mode:
                    steps.append(f"{indent()}{fallback_logic_line(info['raw'], name_map=name_map, backend_module=backend)}")
                else:
                    steps.append(f"{indent()}待人工修改")
    # Flush a trailing bulk-assignment run before final cleanup validates lines.
    flush_pending_bulk_steps()
    steps, cleanup_index_map = _cleanup_final_logic_lines(steps, backend_module=backend, return_index_map=True)
    remapped_unknowns = []
    for unknown in unknowns:
        try:
            old_idx = int(unknown.get("idx"))
        except (TypeError, ValueError):
            continue
        new_idx = cleanup_index_map.get(old_idx)
        if new_idx is None:
            continue
        remapped = dict(unknown)
        remapped["idx"] = new_idx
        remapped_unknowns.append(remapped)
    return "\n".join(steps), remapped_unknowns


def _clean_description_lines(desc: str) -> tuple[str, ...]:
    if not desc:
        return ()
    lines: list[str] = []
    for line in desc.splitlines():
        raw = line.strip()
        if not raw:
            continue
        clean = re.sub(r"^[：:，,\s]+", "", raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            lines.append(clean)
    return tuple(lines)


_CONTROL_LOGIC_RE = re.compile(
    r"^(IF|ELSE IF|ELSE|FOR|WHILE|DO WHILE|SWITCH|CASE|DEFAULT|END IF|END WHILE|END DO WHILE|END SWITCH|NEXT)\b"
)
_SIMPLE_INT_LITERAL_RE = re.compile(r"^(0[xX][0-9a-fA-F]+|\d+)(?:[uUlL]+)?$")
_TXPACK_TEMP_ASSIGN_RE = re.compile(r"^(?:l_(?:high|low)(?:_[iu]\d+)?|l_vpcCal_u32)$", re.I)
_SIMPLE_LOOP_INDEX_RE = re.compile(r"^(?:i|j|k|ii|jj|kk|idx|index|cnt|count|n)$", re.I)
_KNOWN_BULK_OWNER_LABELS = {
    "s_RIUSendData_t.ValveCtrl_t": "RIU发送阀门控制",
    "s_RIUSendData_t.RIUfltInfo1_t": "RIU故障信息1",
    "s_RIUSendData_t.RIUfltInfo2_t": "RIU故障信息2",
    "s_RIUSendData_t.RCVcmd_t": "RIU接收阀命令",
    "s_RIUSendData_t": "RIU发送数据",
    "aceSta1_un": "ACE状态字1",
    "aceSta2_un": "ACE状态字2",
    "acePbitSta_un": "PBIT状态字",
    "act1Mon1_un": "ACT1状态字1",
    "act1Mon2_un": "ACT1状态字2",
    "c1394StofMon_un": "STOF监测状态字",
    "c1394CmdMon_un": "指令监测状态字",
    "acePmFl192_un": "PMFL192状态字",
    "acePmFl196_un": "PMFL196状态字",
    "acePmFl200_un": "PMFL200状态字",
    "acePmFl212_un": "PMFL212状态字",
}


def _is_control_logic_line(text: str) -> bool:
    return bool(_CONTROL_LOGIC_RE.match((text or "").strip()))


def _sanitize_control_logic_line(text: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = str(text or "").rstrip()
    indent = raw[: len(raw) - len(raw.lstrip(" \t"))].replace("\t", "    ")
    value = utils._safe_strip(raw)
    if not value:
        return ""
    value = re.sub(r"[；;]+$", "", value).strip()
    value = re.sub(
        r"^(?:计算|赋值|执行)\s+(?=(?:IF|ELSE\s+IF|ELSE|FOR|WHILE|DO\s+WHILE|SWITCH|CASE|DEFAULT|END\s+IF|END\s+WHILE|END\s+DO\s+WHILE|END\s+SWITCH|NEXT)\b)",
        "",
        value,
    ).strip()
    value = re.sub(r"^(?:调用函数|调用)\s+(?=(?:IF|FOR|WHILE|SWITCH)\b)", "", value).strip()
    if not _is_control_logic_line(value):
        return ""
    value = value.replace("->", ".")
    value = re.sub(r"\bextern的", "", value)
    value = re.sub(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\b", "", value)
    value = re.sub(r"\bbit_u\d+\b\.?", "", value)
    value = re.sub(r"\bmem_u\d+\b\.?", "", value)
    value = re.sub(r"\ball_(?:u16|u32|32)\b\.?", "", value, flags=re.IGNORECASE)
    value = _replace_member_chain_with_owner(value, name_map, backend_module=backend)
    value = _strip_ascii_parenthetical_hint(value)
    value = _replace_idents_for_logic_ex(value, name_map, allow_member=True, backend_module=backend)
    value = re.sub(r"\s+", " ", value).strip()
    if value.startswith("FOR "):
        value = re.sub(
            r"\bfor\s*\((.*?)\)",
            lambda m: _render_for_header_cn(f"for({m.group(1)})", backend_module=backend),
            value,
            flags=re.IGNORECASE,
        )
        value = value.replace("(", "").replace(")", "")
    elif re.match(r"^(IF|ELSE\s+IF|WHILE|DO\s+WHILE)\b", value):
        value = _strip_ascii_parenthetical_hint(value)
        value = value.replace("(", "").replace(")", "")
        value = _prettify_condition_expr_text(value)
    elif re.match(r"^(SWITCH|CASE|DEFAULT|END\s+IF|END\s+WHILE|END\s+DO\s+WHILE|END\s+SWITCH|NEXT)\b", value):
        value = value.replace("(", "").replace(")", "")
    value = re.sub(r"(?:或\s+){2,}", "或 ", value)
    value = re.sub(r"(?:且\s+){2,}", "且 ", value)
    value = _normalize_null_condition_text(value)
    value = _normalize_valid_condition_text(value)
    value = re.sub(r"([\u4e00-\u9fff])\s+项(?=\s|等于|不等于|大于|小于|时|$)", r"\1项", value)
    value = re.sub(r"(\S)\s+时$", r"\1时", value)
    return indent + re.sub(r"\s+", " ", value).strip()


def _normalize_null_condition_text(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    kw = r"(IF|ELSE\s+IF|WHILE|DO\s+WHILE)"
    null_word = r"(?:空|NULL)"
    value = re.sub(rf"^{kw}\s+{null_word}\s+等于\s+(.+?)时$", r"\1 \2为空时", value)
    value = re.sub(rf"^{kw}\s+(.+?)\s+等于\s+{null_word}时$", r"\1 \2为空时", value)
    value = re.sub(rf"^{kw}\s+{null_word}\s+不等于\s+(.+?)时$", r"\1 \2不为空时", value)
    value = re.sub(rf"^{kw}\s+(.+?)\s+不等于\s+{null_word}时$", r"\1 \2不为空时", value)
    return value


def _normalize_valid_condition_text(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value
    match = re.match(r"^(?P<kw>IF|ELSE\s+IF|WHILE|DO\s+WHILE)\s+(?P<cond>.*?)(?P<tail>时)?$", value)
    if not match:
        return value
    cond = utils._safe_strip(match.group("cond"))
    tail = match.group("tail") or ""
    if not cond:
        return value
    pieces = re.split(r"(\s+(?:且|或)\s+)", cond)

    def _subject_ok(subject: str) -> bool:
        text = re.sub(r"\s+", "", utils._safe_strip(subject))
        if len(text) < 2 or len(text) > 28:
            return False
        if any(token in text for token in (" 大于", " 小于", " 等于", " 不等于", "或", "且")):
            return False
        return bool(re.search(r"(?:结果|标志|状态|到位|完成|有效|控制权|反馈|指令|原因)$", text) or re.search(r"(?:结果|标志|状态|到位|完成|有效|控制权|反馈|指令|原因)", text))

    def _rewrite_part(part: str) -> str:
        raw = utils._safe_strip(part)
        if not raw:
            return part
        patterns = [
            (r"^有效\s+等于\s+(.+)$", "有效"),
            (r"^(.+?)\s+等于\s+有效$", "有效"),
            (r"^无效\s+等于\s+(.+)$", "无效"),
            (r"^(.+?)\s+等于\s+无效$", "无效"),
            (r"^有效\s+不等于\s+(.+)$", "无效"),
            (r"^(.+?)\s+不等于\s+有效$", "无效"),
            (r"^无效\s+不等于\s+(.+)$", "有效"),
            (r"^(.+?)\s+不等于\s+无效$", "有效"),
        ]
        for pattern, state in patterns:
            m = re.match(pattern, raw)
            if not m:
                continue
            subject = utils._safe_strip(m.group(1))
            if not _subject_ok(subject):
                return raw
            return f"{subject}{state}"
        return raw

    rewritten = "".join(piece if re.fullmatch(r"\s+(?:且|或)\s+", piece) else _rewrite_part(piece) for piece in pieces)
    return f"{match.group('kw')} {rewritten}{tail}"


def is_decorative_comment(text: str) -> bool:
    return bool(re.search(r"(\*|-|=|_){3,}", text or ""))


def is_noop_statement(code: str) -> bool:
    s = (code or "").strip()
    if not s:
        return True
    return s in {";", "{;}"}


def is_declaration_line(code: str) -> bool:
    if not code:
        return False
    s = code.strip()
    if not s.endswith(";"):
        return False
    if re.match(r"^(return|goto|case|default)\b", s):
        return False
    s = s[:-1].strip()
    s = re.sub(r"^\s*extern\s+", "", s)
    head = s.split(",", 1)[0].strip() if "," in s else s
    type_prefix = r"(?:static\s+|const\s+|volatile\s+|register\s+)*"
    type_name = r"(?:struct\s+\w+|union\s+\w+|enum\s+\w+|[A-Za-z_]\w*)"
    type_suffix = r"(?:\s+(?:const|volatile)\b)*"
    pointer = r"(?:\s*(?:(?:const|volatile)\s*)?\*\s*(?:const\s+|volatile\s+)*)*"
    var_name = r"[A-Za-z_]\w*"
    array = r"(?:\s*\[[^\]]*\])*"
    init = r"(?:\s*=\s*.+)?"
    full_pattern = r"^" + type_prefix + type_name + type_suffix + pointer + r"\s+" + var_name + array + init + r"$"
    return bool(re.match(full_pattern, head))


def _render_simple_decl_initializer_action(
    code: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> Optional[str]:
    backend = backend_module or legacy_backend()
    if not is_declaration_line(code):
        return None
    parts = _split_plain_assignment(code)
    if not parts:
        return None
    raw_lhs, raw_rhs = parts
    target_match = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?$", raw_lhs)
    if not target_match:
        return None
    target_ident = utils._safe_strip(target_match.group(1))
    rhs = utils._safe_strip(raw_rhs)
    if not target_ident or not rhs:
        return None
    if any(token in rhs for token in ("?", ":", "(", ")", "{", "}")):
        return None
    if _is_zero_literal(rhs):
        return None
    if not (
        re.fullmatch(r"[A-Za-z_]\w*", rhs)
        or _SIMPLE_INT_LITERAL_RE.match(rhs)
        or re.fullmatch(r"0[xX][0-9A-Fa-f]+[UuLl]*", rhs)
    ):
        return None
    lhs_cn = _logic_cn_expr(target_ident, name_map=name_map, backend_module=backend)
    rhs_cn = _logic_cn_expr(rhs, name_map=name_map, backend_module=backend)
    lhs_cn = utils._safe_strip(lhs_cn)
    rhs_cn = utils._safe_strip(rhs_cn)
    if not lhs_cn or not rhs_cn or lhs_cn == target_ident:
        return None
    return f"设置{lhs_cn} = {rhs_cn}"


def detect_increment_action(code: str, local_var_usages: dict):
    s = (code or "").strip().rstrip(";")
    m = re.match(r"([A-Za-z_]\w*)\s*=\s*\1\s*\+\s*1[Uu]?", s)
    if m:
        var = m.group(1)
        cn = (local_var_usages or {}).get(var)
        if cn:
            return f"{cn}加1；"
    m2 = re.match(r"([A-Za-z_]\w*)\s*\+\+", s)
    if m2:
        var = m2.group(1)
        cn = (local_var_usages or {}).get(var)
        if cn:
            return f"{cn}加1；"
    m3 = re.match(r"([A-Za-z_]\w*)\s*\+=\s*1[Uu]?", s)
    if m3:
        var = m3.group(1)
        cn = (local_var_usages or {}).get(var)
        if cn:
            return f"{cn}加1；"
    return None


def _normalize_simple_int_literal(text: str) -> str:
    s = (text or "").strip()
    m = _SIMPLE_INT_LITERAL_RE.match(s)
    if not m:
        return s
    return m.group(1)


def _is_zero_literal(text: str) -> bool:
    s = (text or "").strip()
    s = re.sub(r"^\((.*)\)$", r"\1", s).strip()
    return bool(re.fullmatch(r"(?:0(?:\.0+)?|0[xX]0)(?:[uUlLfF]*)", s))


def _strip_balanced_outer_parens(text: str) -> str:
    value = (text or "").strip()
    while value.startswith("(") and value.endswith(")") and len(value) >= 2:
        depth = 0
        ok = True
        for idx, ch in enumerate(value):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(value) - 1:
                    ok = False
                    break
        if not ok:
            break
        inner = value[1:-1].strip()
        if not inner:
            break
        value = inner
    return indent + value


def _strip_leading_c_casts(text: str) -> str:
    value = (text or "").strip()
    cast_re = re.compile(
        r"^\(\s*(?:const\s+|volatile\s+|signed\s+|unsigned\s+)*"
        r"(?:Uint(?:8|16|32|64)|Int(?:8|16|32|64)|uint(?:8|16|32|64)_t|int(?:8|16|32|64)_t|"
        r"float|double|char|short|int|long|void|[A-Z_]\w*(?:_t)?)"
        r"(?:\s*[*])?\s*\)",
    )
    prev = None
    while prev != value:
        prev = value
        if not value.startswith("("):
            break
        m = cast_re.match(value)
        if not m:
            break
        value = value[m.end():].strip()
    return value


def _render_mask_assignment(
    lhs: str,
    rhs: str,
    name_map: Optional[dict[str, str]],
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    chain = _split_top_level_bitwise_chain(rhs)
    if not chain:
        return ""
    op, parts = chain
    if op != "&" or len(parts) != 2:
        return ""
    rendered_c_expr = _render_supported_c_expr_cn(rhs, name_map)
    if rendered_c_expr:
        lhs_cn = _logic_cn_expr(lhs, name_map=name_map, backend_module=backend)
        return f"将{rendered_c_expr}写入{lhs_cn}" if lhs_cn else f"计算{rendered_c_expr}"
    left, right = parts
    mask = ""
    value_expr = ""
    for part in (left, right):
        stripped = _strip_balanced_outer_parens(_strip_leading_c_casts(part))
        if _SIMPLE_INT_LITERAL_RE.fullmatch(stripped):
            mask = _normalize_simple_int_literal(stripped)
        else:
            value_expr = stripped
    if not mask or not value_expr:
        return ""
    lhs_cn = _logic_cn_expr(lhs, name_map=name_map, backend_module=backend)
    value_cn = _logic_cn_expr(value_expr, name_map=name_map, backend_module=backend)
    if value_cn == lhs_cn:
        return f"将{value_cn}按{mask}掩码处理"
    return f"将{value_cn}按{mask}掩码后写入{lhs_cn}"


def _render_simple_statement_action(
    code: str,
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> Optional[str]:
    backend = backend_module or legacy_backend()
    s = (code or "").strip()
    if not s:
        return None
    s = s.rstrip(";").strip()
    if not s:
        return None
    effective_map = dict(name_map or {})
    for k, v in (local_var_usages or {}).items():
        if k and v and k not in effective_map:
            effective_map[k] = v


    def _render_display_expr(expr: str) -> str:
        effective_map = dict(name_map or {})
        for k, v in (local_var_usages or {}).items():
            if k and v and k not in effective_map:
                effective_map[k] = v
        s2 = _logic_cn_expr(expr, name_map=effective_map, backend_module=backend)
        return re.sub(r"\s+", " ", (s2 or "").strip())

    def _parse_simple_operand(expr: str) -> Optional[str]:
        x = (expr or "").strip()
        if not x:
            return None
        for _ in range(2):
            x2 = x.strip()
            x2 = re.sub(r"^\([^)]*\)\s*", "", x2).strip()
            if x2.startswith("(") and x2.endswith(")"):
                inner = x2[1:-1].strip()
                if inner:
                    x2 = inner
            x = x2
        if re.match(r"^[A-Za-z_]\w*$", x) or re.match(lv_re + r"$", x):
            return _render_display_expr(x)
        if _SIMPLE_INT_LITERAL_RE.match(x):
            return _normalize_simple_int_literal(x)
        return None

    lv_re = r"[A-Za-z_]\w*(?:\s*\[[^]]*\]|\s*(?:\.|->)\s*[A-Za-z_]\w*)*"

    if re.match(r"^return\b", s):
        ret_expr = s[len("return"):].strip()
        if not ret_expr:
            return "返回"
        ret_expr = ret_expr.rstrip(";").strip().lstrip("&").strip()
        for _ in range(2):
            ret_expr = re.sub(r"^\([^)]*\)\s*", "", ret_expr).strip()
            if ret_expr.startswith("(") and ret_expr.endswith(")"):
                inner = ret_expr[1:-1].strip()
                if inner:
                    ret_expr = inner
        if not ret_expr:
            return "返回"
        ternary_ret = _render_ternary_return_text(ret_expr, name_map=name_map, backend_module=backend)
        if ternary_ret:
            return ternary_ret
        return f"返回{_render_display_expr(ret_expr)}"

    m = re.match(rf"^(?:\+\+\s*)?(?P<var>{lv_re})\s*(?:\+\+)?$", s)
    if m and ("++" in s):
        return f"{_render_display_expr(m.group('var').strip())}+1"
    m = re.match(rf"^(?:--\s*)?(?P<var>{lv_re})\s*(?:--)?$", s)
    if m and ("--" in s):
        return f"{_render_display_expr(m.group('var').strip())}-1"

    m = re.match(rf"^(?P<lhs>{lv_re})\s*(?P<op>\+=|-=)\s*(?P<rhs>.+)$", s)
    if m:
        rhs = _parse_simple_operand(m.group("rhs"))
        if rhs is None:
            return None
        sign = "+" if m.group("op") == "+=" else "-"
        return f"{_render_display_expr(m.group('lhs'))}{sign}{rhs}"

    m = re.match(rf"^(?P<lhs>{lv_re})\s*=\s*(?P<rhs>.+)$", s)
    if not m:
        return None
    lhs = m.group("lhs")
    rhs_raw = (m.group("rhs") or "").strip()
    rhs_clean = _strip_balanced_outer_parens(rhs_raw)
    rhs_norm = _normalize_simple_int_literal(rhs_clean)
    if _is_zero_literal(rhs_clean):
        return f"清零{_render_display_expr(lhs)}"
    if rhs_norm in ("1", "0x1", "0X1"):
        return f"置{_render_display_expr(lhs)}为1"
    rhs_simple = _parse_simple_operand(rhs_clean)
    if rhs_simple is not None:
        if rhs_simple in {"有效", "无效", "真", "假"}:
            return f"置{_render_display_expr(lhs)}为{rhs_simple}"
        return f"将 {rhs_simple} 写入 {_render_display_expr(lhs)}"
    binary_text = _render_binary_assignment_text(
        lhs,
        rhs_clean,
        _render_display_expr(lhs),
        name_map=effective_map,
        backend_module=backend,
    )
    if binary_text:
        return binary_text
    mask_action = _render_mask_assignment(lhs, rhs_clean, name_map, backend_module=backend)
    if mask_action:
        return mask_action
    lhs_norm = re.sub(r"\s+", "", lhs)
    rhs_norm2 = re.sub(r"\s+", "", rhs_clean)
    m2 = re.match(rf"^{re.escape(lhs_norm)}(?P<op>[+-])(?P<rhs>.+)$", rhs_norm2)
    if m2:
        rhs = _parse_simple_operand(m2.group("rhs"))
        if rhs is None:
            return None
        return f"{_render_display_expr(lhs)}{m2.group('op')}{rhs}"
    if "^" in rhs_raw:
        xor_parts = [p.strip() for p in rhs_raw.split("^") if p.strip()]
        if len(xor_parts) == 2 and re.sub(r"\s+", "", xor_parts[0]) == lhs_norm:
            rhs_cn = _render_display_expr(xor_parts[1])
            return f"{_render_display_expr(lhs)}按位异或累加{rhs_cn}"
    return None


def _split_plain_assignment(code: str) -> Optional[tuple[str, str]]:
    s = (code or "").strip()
    if not s.endswith(";"):
        return None
    core = s[:-1].strip()
    if not core:
        return None
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for i, ch in enumerate(core):
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
        if depth != 0 or ch != "=":
            continue
        prev = core[i - 1] if i > 0 else ""
        nxt = core[i + 1] if i + 1 < len(core) else ""
        if prev in "<>!=+-*/%&|^" or nxt == "=":
            continue
        lhs = core[:i].strip()
        rhs = core[i + 1:].strip()
        if lhs and rhs:
            return lhs, rhs
        return None
    return None


def _extract_txpack_bias_name(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    s = utils._safe_strip(text)
    if not s:
        return ""
    m = re.search(r"\[(NDB_BIAS_[A-Za-z0-9_]+)\]", s)
    if m:
        return utils._safe_strip(m.group(1))
    return ""


def _is_txpack_dest_expr(expr: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    s = utils._safe_strip(expr)
    return bool(s and ("s_1394TxPackDat_u32[" in s or "s_1394TxPackDat[" in s))


def _is_txpack_temp_assignment(lhs: str, rhs: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    lhs_name = utils._safe_strip(lhs)
    rhs_text = utils._safe_strip(rhs)
    return bool(_TXPACK_TEMP_ASSIGN_RE.fullmatch(lhs_name) and ("DataTransFToInt(" in rhs_text or "^" in rhs_text))


def _humanize_bulk_owner(
    owner: str,
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    s = utils._safe_strip(owner).replace("->", ".")
    if not s:
        return ""
    known = getattr(backend, "_KNOWN_BULK_OWNER_LABELS", None) or _KNOWN_BULK_OWNER_LABELS
    for token, label in known.items():
        if token in s:
            return label
    effective_map = dict(name_map or {})
    for k, v in (local_var_usages or {}).items():
        if k and v and k not in effective_map:
            effective_map[k] = v
    out = _logic_cn_expr(s, name_map=effective_map, backend_module=backend)
    out = re.sub(r"(?:\.|的)?(?:bit|all|word\d+|mem)_u\d+", "", out)
    out = re.sub(r"(?:_un|_st)\b", "", out)
    out = re.sub(r"\s+", " ", out).strip(" ._")
    return out


def _extract_assignment_owner(expr: str) -> str:
    s = (expr or "").strip()
    if not s:
        return ""
    s = re.sub(r"^[A-Za-z_]\w*\s*\([^)]*\)\s*", "", s).strip()
    s = re.sub(r"\[[^\]]*\]", "", s)
    m = re.match(r"([A-Za-z_]\w*)", s)
    if not m:
        return ""
    return (m.group(1) or "").strip()


def _extract_assignment_group_key(code: str, *, backend_module=None) -> str:
    parts = _split_plain_assignment(code)
    if not parts:
        return ""
    lhs, rhs = parts
    if _is_txpack_temp_assignment(lhs, rhs, backend_module=backend_module):
        return "txpack_words"
    if _is_txpack_dest_expr(lhs, backend_module=backend_module) and ("s_c1394AceDataTx_t." in rhs):
        tokens = [t for t in re.split(r"\s*(?:\.|->)\s*", rhs.strip().replace("->", ".")) if t]
        if len(tokens) >= 2 and tokens[0] == "s_c1394AceDataTx_t":
            return ".".join(tokens[:2])
    if _is_txpack_dest_expr(lhs, backend_module=backend_module):
        rhs_owner = _extract_assignment_owner(rhs)
        if rhs_owner.startswith("s_c1394AceDataTx_t"):
            tokens = [t for t in re.split(r"\s*(?:\.|->)\s*", rhs.strip().replace("->", ".")) if t]
            return ".".join(tokens[:2]) if len(tokens) >= 2 else rhs_owner
        return "txpack_words"
    anchor = rhs if ("HARD_XINT_" in lhs or "DRAM_WADR_" in lhs) else lhs
    s = (anchor or "").strip()
    has_index = "[" in s and "]" in s
    s = re.sub(r"^[A-Za-z_]\w*\s*\([^)]*\)\s*", "", s).strip()
    s = re.sub(r"\[[^\]]*\]", "", s)
    tokens = [t for t in re.split(r"\s*(?:\.|->)\s*", s) if t]
    if not tokens:
        return ""
    if tokens[0] == "s_c1394AceDataTx_t" and len(tokens) >= 2:
        return ".".join(tokens[:2])
    return tokens[0] if not has_index else (".".join(tokens[:2]) if len(tokens) >= 2 else tokens[0])


def _summarize_bulk_assignment_run(
    items: Sequence[dict[str, str]],
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> Optional[str]:
    backend = backend_module or legacy_backend()
    owners: dict[str, int] = {}
    read_hw = 0
    write_hw = 0
    clear_count = 0
    txpack_writes = 0
    txpack_pack_ops = 0
    txpack_biases: list[str] = []
    for item in items:
        parts = _split_plain_assignment((item or {}).get("code") or "")
        if not parts:
            return None
        lhs, rhs = parts
        if _is_txpack_dest_expr(lhs, backend_module=backend):
            txpack_writes += 1
            bias = _extract_txpack_bias_name(lhs, backend_module=backend)
            if bias:
                txpack_biases.append(bias)
        if _is_txpack_temp_assignment(lhs, rhs, backend_module=backend) or "U32PackUp(" in rhs:
            txpack_pack_ops += 1
        owner = _extract_assignment_owner(rhs) if ("HARD_XINT_" in lhs or "DRAM_WADR_" in lhs) else _extract_assignment_owner(lhs)
        if owner:
            owners[owner] = owners.get(owner, 0) + 1
        rhs_norm = _normalize_simple_int_literal(rhs)
        if rhs_norm in ("0", "0x0", "0X0"):
            clear_count += 1
        if "HARD_XINT_" in rhs or "DRAM_RADR_" in rhs:
            read_hw += 1
        if "HARD_XINT_" in lhs or "DRAM_WADR_" in lhs:
            write_hw += 1

    main_owner = ""
    main_owner_count = 0
    if owners:
        main_owner, main_owner_count = max(owners.items(), key=lambda kv: kv[1])
    if main_owner_count < max(5, int(len(items) * 0.6)):
        main_owner = ""
    if (not main_owner) and items:
        group_key = utils._safe_strip((items[0] or {}).get("group_key"))
        if "." in group_key:
            main_owner = group_key
    if main_owner == "s_c1394AceDataTx_t" and items:
        lhs0, _rhs0 = _split_plain_assignment((items[0] or {}).get("code") or "") or ("", "")
        toks0 = [t for t in re.split(r"\s*(?:\.|->)\s*", lhs0.replace("->", ".")) if t]
        if len(toks0) >= 2 and toks0[0] == "s_c1394AceDataTx_t":
            main_owner = ".".join(toks0[:2])

    effective_map = dict(name_map or {})
    for k, v in (local_var_usages or {}).items():
        if k and v and k not in effective_map:
            effective_map[k] = v
    owner_cn = _humanize_bulk_owner(main_owner, name_map=effective_map, local_var_usages=local_var_usages, backend_module=backend) if main_owner else ""

    if txpack_writes >= max(4, len(items) // 3):
        bitfield_writes = sum(
            1
            for item in items
            if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", (item or {}).get("code") or "")
        )
        if bitfield_writes >= max(4, len(items) // 3):
            return f"批量汇总{owner_cn}位域并写入1394发送数据字" if owner_cn else "批量汇总状态字位域并写入1394发送数据字"
        if txpack_pack_ops >= max(3, txpack_writes):
            if len(set(txpack_biases)) <= 2 and txpack_biases:
                return f"采集并转换测量量，打包写入{txpack_biases[-1]}"
            return "批量采集并转换测量量，打包更新1394发送数据字"
        if owner_cn and len(items) >= 3:
            return f"汇总{owner_cn}并写入1394发送数据字"
        if len(items) >= 6:
            return "批量更新1394发送数据字"
    elif txpack_writes >= 1:
        bitfield_writes = sum(
            1
            for item in items
            if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", (item or {}).get("code") or "")
        )
        if bitfield_writes >= 3 and len(items) >= 4:
            return f"汇总{owner_cn}位域并写入1394发送数据字" if owner_cn else "汇总状态字位域并写入1394发送数据字"

    if read_hw >= max(3, len(items) // 3):
        if len(items) < 5:
            return None
        summary = "批量读取硬件寄存器"
        if owner_cn:
            summary += f"并刷新{owner_cn}相关字段"
        elif write_hw > 0:
            summary += "并更新控制字段"
        return summary
    if write_hw >= max(3, len(items) // 3):
        if len(items) < 5:
            return None
        summary = "批量写入硬件控制寄存器"
        if owner_cn:
            summary += f"并同步{owner_cn}相关字段"
        return summary
    bitfield_writes = sum(
        1
        for item in items
        if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", (item or {}).get("code") or "")
    )
    if bitfield_writes >= max(5, len(items) // 2):
        if len(items) < 6:
            return None
        summary = "批量汇总状态字位域"
        if owner_cn:
            summary += f"并更新{owner_cn}相关字段"
        return summary
    if len(items) < 8:
        return None
    if main_owner and (clear_count >= 3 or len(items) >= 10):
        summary = f"批量更新{owner_cn}相关字段"
        if clear_count >= 3:
            summary += "并初始化部分成员"
        return summary
    return None


def _replace_idents_for_logic(text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    return _replace_idents_for_logic_ex(text, name_map, allow_member=False, backend_module=backend_module)


def _normalize_logic_expr_alias_key(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = s.replace("->", ".")
    s = re.sub(r"\s+", "", s)
    return s


def _is_transparent_union_container_member(name: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:bit|all|mem|word\d+)(?:_(?:u|i)\d+)?",
            utils._safe_strip(name),
            flags=re.IGNORECASE,
        )
    )


def _clean_member_alias_label(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return ""
    value = re.sub(r"^bit\d+\s*[:：]\s*", "", value, flags=re.IGNORECASE).strip()
    bit_wrapped = re.fullmatch(r"bit\d+\(([^()]+)\)", value, flags=re.IGNORECASE)
    if bit_wrapped:
        return utils._safe_strip(bit_wrapped.group(1))
    if re.fullmatch(r"bit\d+", value, flags=re.IGNORECASE):
        return ""
    return value


def _is_low_specificity_logic_alias(text: str) -> bool:
    compact = re.sub(r"\s+", "", utils._safe_strip(text))
    if not compact:
        return True
    compact = re.sub(r"[（(][^（）()]*[）)]", "", compact).strip()
    return compact in {
        "上一周期值",
        "缓存值",
        "状态值",
        "标志值",
        "请求值",
        "当前值",
        "临时值",
        "中间值",
        "结果值",
        "指令",
        "有效",
    }


def _lookup_logic_expr_alias(expr: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not expr or not name_map:
        return ""
    raw = utils._safe_strip(expr)
    if not raw:
        return ""
    if "." not in raw and "->" not in raw and _is_transparent_union_container_member(raw):
        return ""
    for key in (raw, raw.replace("->", "."), _normalize_logic_expr_alias_key(raw)):
        alias = utils._safe_strip((name_map or {}).get(key))
        if alias:
            cleaned = _repair_corrupt_hardware_aliases_in_logic(_clean_member_alias_label(alias))
            tail = re.split(r"\s*(?:\.|->)\s*", raw.replace("->", "."))[-1]
            semantic_label = _semantic_label_for_ident(tail, backend_module=backend)
            if (
                semantic_label
                and semantic_label not in {"状态", "状态值", "标志", "标志位", "数据状态", "时间值", "缓存值"}
                and _is_low_specificity_logic_alias(cleaned)
            ):
                return semantic_label
            return cleaned
    return ""


def _prettify_logic_ident(ident: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = str(ident or "").strip()
    if not value:
        return value
    if text_utils._contains_cjk(value):
        return value
    if _is_transparent_union_container_member(value):
        return ""
    hardware_bit = _hardware_bitfield_display_name(value)
    mapped = (name_map or {}).get(value)
    if mapped and backend._looks_like_low_quality_symbol_cn(mapped, raw_ident=value):
        mapped = ""
    if hardware_bit and (not mapped or _is_low_specificity_hardware_label(mapped)):
        return hardware_bit
    threshold_label = _guess_threshold_macro_label(value)
    if threshold_label and not mapped:
        return threshold_label
    macro_label = _heuristic_macro_display_name(value, name_map=name_map, backend_module=backend)
    if macro_label:
        return macro_label
    if mapped and not backend._should_preserve_macro_token(value, mapped):
        return _repair_corrupt_hardware_aliases_in_logic(mapped)
    resolved = backend.resolve_canonical_symbol_name(
        value,
        kind=backend._symbol_kind_for_name(value),
        fallback=value,
        allow_guess=False,
    )
    if resolved and backend._looks_like_low_quality_symbol_cn(resolved, raw_ident=value):
        resolved = ""
    if hardware_bit and (not resolved or resolved == value or _is_low_specificity_hardware_label(resolved)):
        return hardware_bit
    if resolved and resolved != value and not backend._should_preserve_macro_token(value, resolved):
        return resolved
    if value in backend._C_KEYWORDS:
        return value
    if re.fullmatch(r"(?:bit|all|mem|word\d+)_u\d+", value, flags=re.IGNORECASE):
        return ""
    if backend._is_macro_identifier(value):
        macro_guess = _heuristic_macro_display_name(value, name_map=name_map, backend_module=backend)
        if macro_guess:
            return macro_guess
        guessed_macro = utils._safe_strip(backend._guess_cn_from_ident(value, glossary=name_map or backend.DOMAIN_GLOSSARY))
        if guessed_macro and guessed_macro != value and text_utils._contains_cjk(guessed_macro):
            return guessed_macro
        return value
    semantic_label = _semantic_label_for_ident(value, backend_module=backend)
    if semantic_label and semantic_label not in {"状态", "状态值", "标志", "标志位", "数据状态", "时间值", "缓存值"}:
        return semantic_label
    base = re.sub(r"_(?:u|i)(?:8|16|32|64|6)\b", "", value, flags=re.IGNORECASE)
    compact = re.sub(r"^(?:gc|gs|sc|gp|sp|lp|vp|fp|cp|tp|g|s|l|v|p)_", "", base)
    compact = re.sub(r"_(?:tp|pt|ptr|buf|arr|list|tbl|table|t|p|un)\b", "", compact, flags=re.IGNORECASE)
    compact = compact.strip("_") or base
    guessed = backend._guess_cn_from_ident(compact, glossary=name_map or backend.DOMAIN_GLOSSARY)
    return guessed or base


def _heuristic_macro_display_name(ident: str, *, name_map: Optional[dict[str, str]] = None, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(ident)
    if not raw or not re.fullmatch(r"[A-Z][A-Z0-9_]*", raw):
        return ""
    mapped = utils._safe_strip((name_map or {}).get(raw))
    upper = raw.upper()
    literal_labels = {
        "VALID": "有效",
        "INVALID": "无效",
        "NULL": "空",
    }
    if upper in literal_labels:
        return literal_labels[upper]
    adc_sequence_labels = {
        "ADC_SEQ1": "ADC序列器1",
        "ADC_SEQ2": "ADC序列器2",
        "ADC_SEQ1_SEQ2": "ADC序列器1和2",
        "ADC_SEQ1_INT": "ADC序列器1中断",
        "ADC_SEQ2_INT": "ADC序列器2中断",
    }
    if upper in adc_sequence_labels:
        return adc_sequence_labels[upper]
    maint_labels = {
        "MAINT_CMD_EXE_DONE": "维护指令执行结束",
        "MAINT_CMD_EXE_NEW": "维护指令执行未结束且有新指令",
    }
    if upper in maint_labels:
        return maint_labels[upper]
    comm429_labels = {
        "COMM429_RIU_1": "本通道任务计算机通信",
        "COMM429_RIU_2": "备份通道任务计算机通信SCI口",
        "COMM429_RIU_3": "备份通道任务计算机通信CPLD口",
        "COMM429_RIU_NUM": "任务计算机通信数量",
    }
    if upper in comm429_labels:
        return comm429_labels[upper]
    kzzz_time_request_labels = {
        "KZZZ_TIME_REQUEST_SIDE_LEFT": "左吊舱当前时间请求",
        "KZZZ_TIME_REQUEST_SIDE_RIGHT": "右吊舱当前时间请求",
        "KZZZ_TIME_REQUEST_VALID": "KZZZ时间请求有效",
        "KZZZ_TIME_REQUEST_INVALID": "KZZZ时间请求无效",
    }
    if upper in kzzz_time_request_labels:
        return kzzz_time_request_labels[upper]
    comm_source_labels = {
        "COMM_SOURCE_1": "数据来源于通信1",
        "COMM_SOURCE_2": "数据来源于通信2",
        "COMM_SOURCE_3": "数据来源于通信3",
        "COMM_SOURCE_INVALID": "当前无有效通信来源",
    }
    if upper in comm_source_labels:
        return comm_source_labels[upper]
    if upper == "TMIE_WORK_SUM_MAX":
        return "系统累计工作时间上限"
    chv_labels = {
        "CHV_VALID": "通道有效信号输出有效",
        "CHV_INVALID": "通道有效信号输出无效",
        "WDV_IN_NOMAL": "WDV正常",
        "CPUV_IN_NOMAL": "CPUV正常",
        "LATCH_EN_VALID": "锁存使能有效",
    }
    if upper in chv_labels:
        return chv_labels[upper]
    function_like_macro_labels = {
        "HARD_XINT_UINT16": "硬件16位输入寄存器读取",
    }
    if upper in function_like_macro_labels:
        return function_like_macro_labels[upper]
    if upper.startswith("REFUEL_TARGET_"):
        tail = upper[len("REFUEL_TARGET_"):]
        if tail == "TANK0":
            return "0号油箱目标"
        if tail == "TANK23":
            return "2/3号油箱目标"
        if tail == "LRP_ALL":
            return "左右吊舱全部目标"
    if (upper.startswith("REFUELVALVE") or upper.startswith("REFUEL_VALVE")) and "OPEN" in upper:
        return "开阀指令"
    if (upper.startswith("REFUELVALVE") or upper.startswith("REFUEL_VALVE")) and "CLOSE" in upper:
        return "关阀指令"
    if upper.startswith("RECEIVE_RIU_STATE_"):
        state_tail = upper[len("RECEIVE_RIU_STATE_"):]
        state_labels = {
            "IDLE": "RIU受油空闲状态",
            "REQUEST_PRESET": "RIU受油请求预位状态",
            "ACTIVE": "RIU受油执行状态",
            "COMPLETE": "RIU受油完成状态",
            "FAULT": "RIU受油故障状态",
        }
        if state_tail in state_labels:
            return state_labels[state_tail]
    if upper.startswith("RECEIVE_RIU_REASON_"):
        reason_tail = upper[len("RECEIVE_RIU_REASON_"):]
        reason_labels = {
            "NONE": "无检查原因",
            "HL_SENSOR": "高低液位传感器故障原因",
            "MEASURE": "测量故障原因",
            "IMBALANCE": "不平衡故障原因",
            "PRESET_FAIL": "预位失败原因",
            "VALVE_TIMEOUT": "阀位超时原因",
        }
        if reason_tail in reason_labels:
            return reason_labels[reason_tail]
    status_suffix = ""
    if upper.endswith("_VALID"):
        status_suffix = "有效"
    elif upper.endswith("_INVALID"):
        status_suffix = "无效"
    elif upper.endswith("_OK"):
        status_suffix = "有效"
    elif upper.endswith("_ERR"):
        status_suffix = "异常"
    if status_suffix:
        guessed = utils._safe_strip(backend._guess_cn_from_ident(upper, glossary=backend.DOMAIN_GLOSSARY))
        guessed = _repair_corrupt_hardware_aliases_in_logic(guessed)
        if guessed and guessed != upper and text_utils._contains_cjk(guessed) and status_suffix in guessed:
            if (
                not mapped
                or mapped == raw
                or status_suffix not in mapped
                or re.search(r"bit\d+", mapped, flags=re.IGNORECASE)
            ):
                return guessed
    if mapped and mapped != raw:
        # name_map 已有翻译（如 "CPU测试"）但缺后缀区分时，补上 _OK/_ERR/_VALID/_INVALID 后缀，
        # 避免同一前缀的多个宏在逻辑图里全部塌缩成同一个泛化名。
        _suffix_map = {"_VALID": "有效", "_INVALID": "无效", "_OK": "有效", "_ERR": "异常"}
        # mapped 已含成功/失败语义时不再追加后缀（避免"CPU测试通过有效"这类重复）
        _mapped_has_ok_sem = any(w in mapped for w in ("通过", "成功", "正常", "有效"))
        _mapped_has_err_sem = any(w in mapped for w in ("失败", "故障", "错误", "异常", "无效"))
        for suf, cn_suf in _suffix_map.items():
            if upper.endswith(suf):
                base = upper[:-len(suf)]
                if base and len(base.split("_")) <= 6 and text_utils._contains_cjk(mapped) and cn_suf not in mapped:
                    if (cn_suf == "有效" and _mapped_has_ok_sem) or (cn_suf == "异常" and _mapped_has_err_sem):
                        return mapped
                    return f"{mapped}{cn_suf}"
                break
        return ""
    if upper.endswith("_VALID"):
        base = upper[:-len("_VALID")]
        if base and len(base.split("_")) <= 4:
            return "有效"
    if upper.endswith("_INVALID"):
        base = upper[:-len("_INVALID")]
        if base and len(base.split("_")) <= 4:
            return "无效"
    if upper.endswith("_OK"):
        base = upper[:-len("_OK")]
        if base and len(base.split("_")) <= 6:
            return "有效"
    if upper.endswith("_ERR"):
        base = upper[:-len("_ERR")]
        if base and len(base.split("_")) <= 6:
            return "异常"
    return ""


def _hardware_bitfield_display_name(ident: str) -> str:
    value = utils._safe_strip(ident)
    if not value:
        return ""
    core = re.sub(r"_(?:b|u|i)(?:1|8|16|32|64)?$", "", value, flags=re.IGNORECASE)
    upper = core.upper()
    if not any(ch.isdigit() for ch in upper):
        return ""
    voltage = ""
    matches = re.findall(r"(\d{1,3})V", upper)
    if matches:
        voltage = f"{matches[-1]}V"
    else:
        match = re.search(r"(?:^|_)V(\d{1,3})(?=[NP]|CH|$)", upper)
        if match:
            voltage = f"{match.group(1)}V"
    if not voltage:
        match = re.search(r"(?:^|_)(\d{1,3})(?=[NP](?:_|$))", upper)
        if match:
            voltage = f"{match.group(1)}V"
    if not voltage:
        return ""
    if not voltage:
        return ""
    polarity = ""
    if re.search(r"(?:^|_)(?:N|NV|NEG)(?:$|_)", upper) or re.search(r"\d+N(?:_|$)", upper) or upper.endswith("NV"):
        polarity = "负"
    elif re.search(r"(?:^|_)(?:P|PV|POS)(?:$|_)", upper) or re.search(r"\d+P(?:_|$)", upper) or upper.endswith("PV"):
        polarity = "正"
    channel = "通道" if re.search(r"(?:CH|CHAN|CHANNEL)\d*$", upper) or "CH" in upper else ""
    valid = "有效" if re.search(r"(?:VLD|VALID|PV|NV|PSV|_V$|V$)", upper) or bool(re.search(r"_b1$", value, flags=re.IGNORECASE)) else ""
    parts = [voltage, polarity, channel, valid]
    return "".join(part for part in parts if part)


def _is_low_specificity_hardware_label(text: str) -> bool:
    compact = re.sub(r"\s+", "", utils._safe_strip(text))
    if not compact:
        return True
    return compact in {"电压", "阈值", "状态", "有效", "位标志", "通道", "电源", "寄存器"}


def _replace_idents_for_logic_ex(
    text: str,
    name_map: Optional[dict[str, str]],
    allow_member: bool,
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    if not text or not name_map:
        if not text:
            return text
        name_map = name_map or {}

    def _is_cjk_neighbor(pos: int) -> bool:
        if pos < 0 or pos >= len(text):
            return False
        return bool(re.match(r"[\u3400-\u9fff]", text[pos]))

    def repl(match: re.Match) -> str:
        ident = match.group(0)
        if ident in backend._C_KEYWORDS:
            return ident
        if _is_cjk_neighbor(match.start() - 1) or _is_cjk_neighbor(match.end()):
            return ident
        if (not allow_member) and match.start() > 0 and text[match.start() - 1] == ".":
            return ident
        return _prettify_logic_ident(ident, name_map, backend_module=backend)

    return backend._C_IDENT_RE.sub(repl, text)


def _map_func_ident(func: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not func:
        return func
    mapped = (name_map or {}).get(func)
    if mapped:
        return mapped
    resolved = backend.resolve_canonical_symbol_name(func, kind="functions", fallback=func)
    if resolved and resolved != func:
        return resolved
    guessed = utils._safe_strip(backend._guess_cn_from_ident(func))
    if guessed and guessed != func and text_utils._contains_cjk(guessed):
        return _repair_corrupt_hardware_aliases_in_logic(guessed)
    return resolved or func


def _render_call_function_action(func: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    func_cn = _map_func_ident(func, name_map, backend_module=backend_module)
    if not func_cn:
        return "调用函数"
    if str(func_cn).endswith("函数"):
        return f"调用{func_cn}"
    return f"调用{func_cn}函数"


def _collect_unresolved_macro_candidates(body: str, *, known_names: Optional[set[str]] = None, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    known = set(known_names or set())
    hits: list[str] = []
    for raw in parse_utils._join_c_line_continuations(body or "").splitlines():
        code, _comments = parse_utils._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt:
            continue
        for name in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", stmt):
            if name in known or name in backend._C_KEYWORDS:
                continue
            hits.append(name)
    return list(dict.fromkeys(hits))


def _collect_member_access_candidates(
    body: str,
    *,
    known_members: Optional[set[str]] = None,
    backend_module=None,
) -> list[tuple[str, str]]:
    backend = backend_module or legacy_backend()
    known = set(known_members or set())
    pairs: list[tuple[str, str]] = []
    for raw in parse_utils._join_c_line_continuations(body or "").splitlines():
        code, _comments = parse_utils._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt:
            continue
        for match in re.finditer(
            r"(?P<base>[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)\s*(?:\.|->)\s*(?P<rest>[A-Za-z_]\w*(?:\s*(?:\.|->)\s*[A-Za-z_]\w*)*)",
            stmt,
        ):
            base = utils._safe_strip(match.group("base"))
            rest = utils._safe_strip(match.group("rest"))
            parts = [part.strip() for part in re.split(r"\s*(?:\.|->)\s*", rest) if part.strip()]
            if not parts:
                continue
            member = parts[-1]
            if member in known or re.fullmatch(r"(?:bit|all|mem|word\d+)_u\d+", member, flags=re.IGNORECASE):
                continue
            pairs.append((member, base))
    return list(dict.fromkeys(pairs))


def _replace_member_chain_with_owner(text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not text:
        return text

    def _base_display(base: str) -> str:
        alias = _lookup_logic_expr_alias(base, name_map, backend_module=backend)
        if alias:
            return alias
        base_norm = base.replace("->", ".")
        base_cn = _replace_idents_for_logic_ex(base_norm, name_map, allow_member=True, backend_module=backend)
        return re.sub(r"\s+", " ", (base_cn or "").strip())

    def _member_display(member: str) -> str:
        if not member:
            return member
        if _is_transparent_union_container_member(member):
            return ""
        raw_alias = utils._safe_strip((name_map or {}).get(member, ""))
        alias = _clean_member_alias_label(raw_alias)
        if alias:
            return alias
        if raw_alias and re.fullmatch(r"bit\d+", raw_alias, flags=re.IGNORECASE):
            return member
        hardware_bit = _hardware_bitfield_display_name(member)
        if hardware_bit:
            return hardware_bit
        return _prettify_logic_ident(member, name_map, backend_module=backend)

    def repl(match: re.Match) -> str:
        base = (match.group("base") or "").strip()
        rest = (match.group("rest") or "").strip()
        if not base or not rest:
            return match.group(0)
        raw_parts = [part.strip() for part in re.split(r"\s*(?:\.|->)\s*", rest) if part.strip()]
        parts = [part for part in raw_parts if not _is_transparent_union_container_member(part)]
        if not parts:
            return _base_display(base)
        full_expr = f"{base}.{'.'.join(parts)}"
        full_alias = _lookup_logic_expr_alias(full_expr, name_map, backend_module=backend)
        if full_alias:
            return full_alias
        if len(parts) > 1:
            nested_alias_keys = [
                f"{base}.{parts[0]}.{parts[-1]}",
                f"{parts[0]}.{parts[-1]}",
            ]
            if len(raw_parts) > 1:
                nested_alias_keys.extend(
                    [
                        f"{base}.{'.'.join(raw_parts)}",
                        ".".join(raw_parts),
                    ]
                )
            for alias_key in nested_alias_keys:
                nested_alias = _lookup_logic_expr_alias(alias_key, name_map, backend_module=backend)
                if nested_alias:
                    owner_alias = _lookup_logic_expr_alias(f"{base}.{parts[0]}", name_map, backend_module=backend)
                    if owner_alias and nested_alias not in owner_alias and owner_alias not in nested_alias:
                        return f"{owner_alias}的{nested_alias}"
                    return nested_alias
        if len(parts) > 1:
            root_member_alias = _lookup_logic_expr_alias(f"{base}.{parts[-1]}", name_map, backend_module=backend)
            if root_member_alias:
                return root_member_alias
        owner_alias = _lookup_logic_expr_alias(f"{base}.{parts[0]}", name_map, backend_module=backend) or _lookup_logic_expr_alias(parts[0], name_map, backend_module=backend)
        if owner_alias:
            if len(parts) == 1:
                return owner_alias
            mem_cn = _member_display(parts[-1]) or parts[-1]
            if mem_cn and mem_cn in owner_alias:
                return owner_alias
            return f"{owner_alias}的{mem_cn}"
        owner_cn = ""
        owner_key = f"{base}.{parts[0]}" if parts else base
        known_owner_labels = getattr(backend, "_KNOWN_BULK_OWNER_LABELS", None) or _KNOWN_BULK_OWNER_LABELS
        for token, label in known_owner_labels.items():
            if token in owner_key:
                owner_cn = label
                break
        if owner_cn:
            if len(parts) == 1:
                return owner_cn
            mem_cn = _member_display(parts[-1])
            if mem_cn and mem_cn in owner_cn:
                return owner_cn
            return f"{owner_cn}的{mem_cn}"
        base_cn = _base_display(base)
        mem_cn = _member_display(parts[-1])
        if (base_cn != base) or (mem_cn != parts[-1]):
            if mem_cn and mem_cn in base_cn:
                return base_cn
            return f"{base_cn}的{mem_cn}"
        return match.group(0)

    return re.sub(
        r"(?P<base>[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)\s*(?:\.|->)\s*(?P<rest>[A-Za-z_]\w*(?:\s*(?:\.|->)\s*[A-Za-z_]\w*)*)",
        repl,
        text,
    )


def _refresh_control_logic_line_idents(text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    """
    仅对结构化控制行（IF/ELSE IF/WHILE/SWITCH/CASE）做一次最终替换，
    用于 one-call 模式下的补齐命名收口。
    """
    backend = backend_module or legacy_backend()
    if not text or not name_map:
        return text
    indent = text[: len(text) - len(text.lstrip())]
    stripped = text.strip()

    match = re.match(r"^(ELSE IF|IF|WHILE)\s+(.+?)\s*时\s*$", stripped)
    if match:
        head, cond = match.group(1), (match.group(2) or "").strip()
        cond2 = _replace_idents_for_logic_ex(cond, name_map, allow_member=True, backend_module=backend)
        cond2 = _replace_member_chain_with_owner(cond2.replace("->", "."), name_map, backend_module=backend)
        cond2 = re.sub(r"\s+", " ", cond2).strip()
        return f"{indent}{head} {cond2} 时"

    match = re.match(r"^SWITCH\s+根据\s+(.+?)\s*分支处理\s*$", stripped)
    if match:
        expr = (match.group(1) or "").strip()
        expr2 = _replace_idents_for_logic_ex(expr, name_map, allow_member=True, backend_module=backend)
        expr2 = _replace_member_chain_with_owner(expr2.replace("->", "."), name_map, backend_module=backend)
        expr2 = re.sub(r"\s+", " ", expr2).strip()
        return f"{indent}SWITCH 根据 {expr2} 分支处理"

    match = re.match(r"^CASE\s+分支\s+(.+?)\s*$", stripped)
    if match:
        value = (match.group(1) or "").strip()
        value2 = _replace_idents_for_logic_ex(value, name_map, allow_member=True, backend_module=backend)
        value2 = _replace_member_chain_with_owner(value2.replace("->", "."), name_map, backend_module=backend)
        value2 = re.sub(r"\s+", " ", value2).strip()
        return f"{indent}CASE 分支 {value2}"

    match = re.match(r"^FOR\s+遍历\s+(.+?)\s*$", stripped)
    if match:
        tail = (match.group(1) or "").strip()
        tail2 = _normalize_array_subscript_text(tail, name_map=name_map, backend_module=backend)
        tail2 = _replace_idents_for_logic_ex(tail2, name_map, allow_member=True, backend_module=backend)
        tail2 = _replace_member_chain_with_owner(tail2.replace("->", "."), name_map, backend_module=backend)
        tail2 = re.sub(r"\s+", " ", tail2).strip()
        return f"{indent}FOR 遍历 {tail2}"

    return text


def _strip_previous_prefix(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if value.startswith("上拍"):
        return value[2:]
    if value.startswith("上一拍"):
        return value[3:]
    return value


def _count_logic_placeholder_lines(logic: Any, *, backend_module=None) -> int:
    backend = backend_module or legacy_backend()
    text = utils._safe_text(logic)
    if not text:
        return 0
    return sum(1 for line in text.splitlines() if "待人工修改" in str(line or ""))


def _is_resolved_symbol_text(symbol_name: str, text: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    stripped = utils._safe_strip(text)
    if (not stripped) or backend._is_missing_gap_text(stripped):
        return False
    if not text_utils._contains_cjk(stripped):
        return False
    return bool(symbol_name) and symbol_name not in stripped


def _looks_like_sentence_cn(text: str) -> bool:
    stripped = re.sub(r"\s+", "", (text or "").strip())
    if not stripped:
        return False
    if len(stripped) >= 12:
        return True
    sentence_markers = ("时", "当", "如果", "则", "用于", "以便", "认定", "初始化", "恢复", "读取", "写入")
    return any(marker in stripped for marker in sentence_markers)


def apply_comment_hints_to_logic(
    action_text: str,
    hints: Sequence[Any],
    mode: str = "hint_only",
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    action = utils._safe_strip(action_text)
    comment_mode = utils._safe_strip(mode).lower() or "hint_only"
    if comment_mode == "off":
        return action
    useful_hints = [hint for hint in (hints or []) if hint.kind not in ("purpose", "history", "debug", "noise")]
    if not useful_hints:
        return action
    best_action = next((hint for hint in useful_hints if hint.kind == "action" and hint.confidence >= 0.8), None)
    best_actionable_condition = next(
        (
            hint
            for hint in useful_hints
            if hint.kind in ("condition", "constraint")
            and hint.confidence >= 0.6
            and _looks_like_actionable_comment_hint_text(hint.text)
        ),
        None,
    )
    replacement_hint = best_action or best_actionable_condition
    if comment_mode == "legacy_inline":
        if action:
            return action
        if replacement_hint:
            return replacement_hint.text
        return action
    if (not action) and best_action:
        return best_action.text
    if replacement_hint and (
        any(phrase in action for phrase in backend._GENERIC_LOGIC_PHRASES)
        or action in _GENERIC_CALL_ROLES
    ):
        return replacement_hint.text
    if replacement_hint and re.fullmatch(r"调用(?:[A-Za-z_]\w*|[^，,；;()（）\s]+)函数", action):
        return replacement_hint.text
    return action


def _looks_like_actionable_comment_hint_text(text: str) -> bool:
    value = utils._safe_strip(text)
    compact = re.sub(r"\s+", "", value)
    if len(compact) < 4 or len(compact) > 36:
        return False
    return bool(
        re.search(
            r"(?:直接|立即|统一)?(?:结束|切入|切换|切到|收口|推进|建立|发送|下发|读取|获取|检查|校验|判断|写入|清除|清空|更新|置位|复位|上报|禁止|允许)",
            compact,
        )
    )


def _should_keep_symbol_cn(name: str, cn: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    stripped = re.sub(r"\s+", "", (cn or "").strip())
    if not stripped:
        return False
    if parse_utils._is_noop_comment(stripped):
        return False
    if backend._is_macro_identifier(name) and re.search(r"(?:阈值|门限|最大值|最小值|上限|下限|检测\d*|传感器\d*)$", stripped):
        return True
    if backend._is_macro_identifier(name) and len(stripped) <= 12 and re.search(r"(?:控制权|主控|备控|持有)", stripped):
        return True
    if backend._is_macro_identifier(name) and _looks_like_sentence_cn(stripped):
        return False
    return True


_AI_ACTION_PURPOSE_TAIL_RE = re.compile(r"(供(?:读取|读|写|获取|使用|访问).*)$")
_AI_ACTION_PURPOSE_TAIL_RE2 = re.compile(r"((?:用于|以便).*)$")
_AI_ACTION_REDUNDANT_STORE_RE = re.compile(r"(并存储.*写入)$")


def _sanitize_ai_logic_action(text: str) -> str:
    """
    清理 AI 输出的流程动作短句，避免把用途/目的拼到动作后面。
    """
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    stripped = re.sub(r"[。;；]+$", "", stripped).strip()
    match = _AI_ACTION_PURPOSE_TAIL_RE.search(stripped)
    if match and match.start() > 0:
        stripped = stripped[: match.start()].rstrip()
    match2 = _AI_ACTION_PURPOSE_TAIL_RE2.search(stripped)
    if match2 and match2.start() > 0:
        stripped = stripped[: match2.start()].rstrip()
    match3 = _AI_ACTION_REDUNDANT_STORE_RE.search(stripped)
    if match3 and match3.start() > 0:
        stripped = stripped[: match3.start()].rstrip()
    stripped = re.sub(r"供+$", "", stripped).strip()
    return stripped


def _cn_compare_op(op: str) -> str:
    return {
        "==": "等于",
        "!=": "不等于",
        ">=": "大于等于",
        "<=": "小于等于",
        ">": "大于",
        "<": "小于",
    }.get((op or "").strip(), (op or "").strip())


def _prettify_logic_expr_text(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    prev = None
    while prev != stripped:
        prev = stripped
        stripped = re.sub(r"\bfabs\s*\(\s*([^()]+?)\s*\)", r"\1的绝对值", stripped)
    stripped = re.sub(r"\s*<<\s*", " 左移 ", stripped)
    stripped = re.sub(r"\s*>>\s*", " 右移 ", stripped)
    stripped = re.sub(r"\s*\|\s*", " 按位或 ", stripped)
    stripped = re.sub(r"\s*&\s*", " 按位与 ", stripped)
    stripped = re.sub(r"\s*\^\s*", " 按位异或 ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped


def _prettify_condition_expr_text(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    stripped = re.sub(r"缓存值\[([^\]]+)\]", r"\1", stripped)
    stripped = _prettify_logic_expr_text(stripped)
    stripped = _normalize_condition_domain_labels(stripped)
    stripped = _prettify_condition_comparison_tokens(stripped)
    stripped = re.sub(r"(?:按位或\s+){2,}", "按位或 ", stripped)
    stripped = re.sub(r"(?:按位与\s+){2,}", "按位与 ", stripped)
    stripped = re.sub(r"(?:按位异或\s+){2,}", "按位异或 ", stripped)
    if not re.search(r"(?:左移|右移)", stripped):
        stripped = re.sub(r"\b按位或\b", "或", stripped)
        stripped = re.sub(r"\b按位与\b", "且", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped


def _normalize_condition_domain_labels(text: str) -> str:
    value = utils._safe_strip(text)
    if not value:
        return value

    def _replace_whitespace(m):
        cleaned = re.sub(r"\s+", "", m.group(1))
        return f"{cleaned}当前状态"

    value = re.sub(
        r"周期自检结构体数组\[(.+?)\]的当前状态",
        _replace_whitespace,
        value,
    )
    value = re.sub(
        r"周期自检结构体数组\[(.+?)\]当前状态",
        _replace_whitespace,
        value,
    )
    value = re.sub(r"周期自检结构体数组的(.+?)项的当前状态", r"\1当前状态", value)
    value = re.sub(r"周期自检结构体数组的(.+?)项当前状态", r"\1当前状态", value)
    value = re.sub(r"缓存值的(.+?)项的当前状态", r"\1当前状态", value)
    value = re.sub(r"缓存值的(.+?)项当前状态", r"\1当前状态", value)
    value = re.sub(r"(.+?)项的该PBIT检测当前状态", r"\1当前状态", value)
    value = re.sub(r"(.+?)项的该PBIT检测项当前状态", r"\1当前状态", value)
    value = re.sub(r"(?<!阈值)(最大值|最小值)\b", lambda m: "上限阈值" if m.group(1) == "最大值" else "下限阈值", value)
    value = value.replace("该PBIT测试项告警", "告警状态")
    value = value.replace("该PBIT测试项通过", "通过状态")
    value = value.replace("该PBIT检测项当前状态", "当前状态")
    return value


def _prettify_condition_comparison_tokens(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    value = re.sub(r"\b0[xX]([0-9A-Fa-f]+)[uUlL]*\b", lambda m: f"0x{m.group(1)}", value)
    value = re.sub(r"\s*(==|!=|>=|<=|>|<)\s*", lambda m: f" {_cn_compare_op(m.group(1))} ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+时$", "时", value)
    return value


_STRUCTURED_COND_AI_CACHE: dict[str, str] = {}
_COND_FUNC_CALL_RE = re.compile(r"\b[A-Za-z_]\w*\s*\(")


def _condition_function_call_label(expr: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = _strip_balanced_outer_parens(utils._safe_strip(expr))
    match = re.fullmatch(r"([A-Za-z_]\w*)\s*\((.*)\)", value, flags=re.S)
    if not match:
        return ""
    args = match.group(2)
    if not any(token in args for token in (",", "?", "&", "==", "!=", "&&", "||")):
        return ""
    func = match.group(1)
    specific_label = _specific_condition_call_label(func, args, name_map, backend_module=backend)
    if specific_label:
        return specific_label
    label = _map_func_ident(func, name_map, backend_module=backend)
    if not label or label == func:
        specific_role = _specific_role_from_callee(func, "")
        label = specific_role or label
    label = re.sub(r"函数$", "", utils._safe_strip(label))
    if not label:
        return ""
    if label.endswith("结果"):
        return label
    return f"{label}结果"


def _condition_call_arg_labels(args_text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    labels: list[str] = []
    for arg in _split_c_call_args(args_text):
        arg_text = utils._safe_strip(arg).lstrip("&").strip()
        if not arg_text:
            continue
        label = _logic_cn_expr(arg_text, name_map=name_map, backend_module=backend)
        label = re.sub(r"\s+", "", utils._safe_strip(label))
        if label:
            labels.append(label)
    return labels


def _pick_condition_subject_label(labels: Sequence[str]) -> str:
    fallback = ""
    for label in reversed([utils._safe_strip(x) for x in labels if utils._safe_strip(x)]):
        compact = re.sub(r"\s+", "", label)
        if not compact:
            continue
        if not fallback:
            fallback = compact
        if compact in {"有效", "无效", "真", "假"}:
            continue
        if any(token in compact for token in ("链路号", "链路ID", "通道间SCI通信")):
            continue
        return compact
    return fallback


def _specific_condition_call_label(
    func: str,
    args_text: str,
    name_map: Optional[dict[str, str]],
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    func_lower = utils._safe_strip(func).lower()
    labels = _condition_call_arg_labels(args_text, name_map, backend_module=backend)
    subject = _pick_condition_subject_label(labels)
    if "rxstateget" in func_lower or ("rx" in func_lower and "stateget" in func_lower):
        return f"{subject}接收状态" if subject else "接收状态"
    if "ccdl" in func_lower and "validget" in func_lower:
        prefix = f"{subject}CCDL镜像" if subject else "CCDL镜像"
        return f"{prefix}有效性结果"
    return ""


def _condition_function_member_label(expr: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = _strip_balanced_outer_parens(utils._safe_strip(expr))
    match = re.fullmatch(
        r"(?P<func>[A-Za-z_]\w*)\s*\((?P<args>.*)\)\s*(?:\.|->)\s*(?P<member>[A-Za-z_]\w*)",
        value,
        flags=re.S,
    )
    if not match:
        return ""
    func = match.group("func")
    member = match.group("member")
    member_lower = member.lower()
    labels = _condition_call_arg_labels(match.group("args"), name_map, backend_module=backend)
    subject = _pick_condition_subject_label(labels)
    member_cn = _prettify_logic_ident(member, name_map, backend_module=backend)
    member_cn = _normalize_member_value_label(member_cn, backend_module=backend)
    func_lower = func.lower()
    if member_lower.startswith("rxstate") or "rxstateget" in func_lower:
        return f"{subject}接收状态" if subject else "接收状态"
    if member_cn and "stateget" in func_lower:
        return f"{subject}{member_cn}" if subject else member_cn
    return ""


def _is_complex_condition(cond: str) -> bool:
    s = (cond or "").strip()
    if not s:
        return False
    return bool(_COND_FUNC_CALL_RE.search(s) or _split_top_level_logical(s))


def _condition_has_rule_locked_relation(cond: str) -> bool:
    expr = _strip_balanced_outer_parens(cond)
    if not expr:
        return False
    if _split_top_level_logical(expr):
        return True
    split = _split_top_level_comparison(expr)
    if not split:
        return False
    lhs, op, rhs = split
    if op in ("==", "!=", ">=", "<=", ">", "<"):
        return _is_condition_constant_expr(lhs) or _is_condition_constant_expr(rhs)
    return False


def _is_condition_constant_expr(expr: str) -> bool:
    value = _strip_balanced_outer_parens(_strip_c_type_casts(str(expr or "").strip()))
    if not value:
        return False
    if re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?)(?:[uUlLfF]+)?", value):
        return True
    if re.fullmatch(r"'(?:\\.|[^'])+'|\"(?:\\.|[^\"])*\"", value):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
        return True
    return False


def _should_swap_condition_comparison_operands(lhs: str, op: str, rhs: str) -> bool:
    if (op or "").strip() not in ("==", "!="):
        return False
    left = _strip_balanced_outer_parens(str(lhs or "").strip())
    right = _strip_balanced_outer_parens(str(rhs or "").strip())
    if not left or not right:
        return False
    return _is_condition_constant_expr(left) and not _is_condition_constant_expr(right)


def _split_top_level_comparison(cond: str) -> Optional[tuple[str, str, str]]:
    s = (cond or "").strip()
    if not s:
        return None
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    i = 0
    ops2 = ("==", "!=", ">=", "<=")
    ops1 = (">", "<")
    while i < len(s):
        ch = s[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\":
            escape = True
            i += 1
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            i += 1
            continue
        if ch == "'":
            in_squote = True
            i += 1
            continue
        if ch == '"':
            in_dquote = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0:
            two = s[i:i + 2]
            if two in ops2:
                lhs = s[:i].strip()
                rhs = s[i + 2:].strip()
                if lhs and rhs:
                    return lhs, two, rhs
            if ch in ops1:
                prev = s[i - 1] if i > 0 else ""
                nxt = s[i + 1] if i + 1 < len(s) else ""
                if (ch == "<" and (prev == "<" or nxt == "<")) or (ch == ">" and (prev == ">" or nxt == ">")):
                    i += 1
                    continue
                lhs = s[:i].strip()
                rhs = s[i + 1:].strip()
                if lhs and rhs:
                    return lhs, ch, rhs
        i += 1
    return None


def _strip_balanced_outer_parens(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        balanced = True
        encloses_all = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    balanced = False
                    break
                if depth == 0 and i != len(s) - 1:
                    encloses_all = False
                    break
        if not balanced or depth != 0 or not encloses_all:
            break
        s = s[1:-1].strip()
    return s


def _split_top_level_logical(cond: str) -> Optional[tuple[str, str, str]]:
    s = (cond or "").strip()
    if not s:
        return None
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    i = 0
    while i < len(s) - 1:
        ch = s[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\":
            escape = True
            i += 1
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            i += 1
            continue
        if ch == "'":
            in_squote = True
            i += 1
            continue
        if ch == '"':
            in_dquote = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0:
            two = s[i:i + 2]
            if two in ("&&", "||"):
                lhs = s[:i].strip()
                rhs = s[i + 2:].strip()
                if lhs and rhs:
                    return lhs, two, rhs
            if ch == "|":
                prev = s[i - 1] if i > 0 else ""
                nxt = s[i + 1] if i + 1 < len(s) else ""
                if prev != "|" and nxt != "|" and prev != "=" and nxt != "=":
                    lhs = s[:i].strip()
                    rhs = s[i + 1:].strip()
                    if lhs and rhs:
                        return lhs, "|", rhs
        i += 1
    return None


def _extract_condition_hint_from_attached(attached: Sequence[str], *, backend_module=None) -> str:
    if not attached:
        return ""
    for text in attached:
        short = parse_utils._normalize_short_logic_label_comment(
            text,
            strip_action_prefix=True,
        )
        if short:
            return short
    return ""


def _ai_structured_condition_cn(
    cond: str,
    attached: Sequence[str],
    name_map: Optional[dict[str, str]],
    cfg: Any,
    *,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    try:
        key = hashlib.sha256(
            (
                str(cond)
                + "\n"
                + "\n".join(attached or [])
                + "\n"
                + json.dumps(name_map or {}, ensure_ascii=False, sort_keys=True)
            ).encode("utf-8", errors="ignore")
        ).hexdigest()
    except Exception:
        key = ""
    if key and key in _STRUCTURED_COND_AI_CACHE:
        return _STRUCTURED_COND_AI_CACHE.get(key) or ""

    hint = _extract_condition_hint_from_attached(attached, backend_module=backend)
    prompt = f"""你是嵌入式 C 代码条件语句翻译助手。
请把给定条件表达式翻译为用于"IF ... 时"的中文条件短语，并严格返回 JSON。

要求：
- 保留比较关系：等于/不等于/大于等于/小于等于/大于/小于；保留逻辑连接：且/或。
- 条件里出现函数调用（含宏函数式调用）时：优先结合上方注释推断其语义；不确定则只描述"某函数判断结果"，不要臆测业务。
- 尽量使用下方术语映射；若映射为空可忽略。
- 输出短句，不要句号，不要解释。

输入：
- 条件表达式：{cond}
- 上方注释（可能为空）：{hint}
- 术语映射（标识符->中文）：{json.dumps(name_map or {}, ensure_ascii=False)}

输出格式（严格 JSON）：
{{"cond_cn":"..."}}
"""
    js = backend.call_llm_json(prompt, cfg, log_title="AI 条件翻译", log_preview=True, log_full_output=True)
    out = ""
    if isinstance(js, dict):
        out = backend._safe_textish(js.get("cond_cn") or js.get("cond") or js.get("cn") or "")
    if out and key:
        _STRUCTURED_COND_AI_CACHE[key] = out
    return out


def _render_structured_condition_cn(
    cond: str,
    attached: Sequence[str],
    name_map: Optional[dict[str, str]],
    cfg: Any,
    *,
    backend_module=None,
) -> tuple[str, bool]:
    backend = backend_module or legacy_backend()
    cond_raw = _strip_balanced_outer_parens(cond)
    used_hint = False

    def _rule_cn(expr: str) -> str:
        expr_text = _strip_balanced_outer_parens(expr)
        rendered_c_expr = _render_supported_c_expr_cn(expr_text, name_map)
        if rendered_c_expr:
            return rendered_c_expr
        call_label = (
            _condition_function_member_label(expr_text, name_map, backend_module=backend)
            or _condition_function_call_label(expr_text, name_map, backend_module=backend)
        )
        text = call_label or _logic_cn_expr(expr_text, name_map=name_map, backend_module=backend)
        text = _strip_ascii_parenthetical_hint(text)
        text = _prettify_condition_expr_text(text)
        return re.sub(r"\s+", " ", text).strip()

    def _semantic_condition_cn(expr: str) -> str:
        try:
            from . import semantic_elements as semantic_element_utils

            semantic = semantic_element_utils.infer_condition_semantic(expr, name_map)
            return semantic_element_utils.render_condition_semantic(semantic)
        except Exception:
            return ""


    def _render_rule_recursive(expr: str) -> str:
        expr2 = _strip_balanced_outer_parens(expr)
        logical = _split_top_level_logical(expr2)
        if logical:
            lhs, op, rhs = logical
            op_cn = "且" if op == "&&" else "或"
            return f"{_render_rule_recursive(lhs)} {op_cn} {_render_rule_recursive(rhs)}".strip()
        split2 = _split_top_level_comparison(expr2)
        if split2:
            semantic_cn = _semantic_condition_cn(expr2)
            if semantic_cn:
                return semantic_cn
            lhs, op, rhs = split2
            if _should_swap_condition_comparison_operands(lhs, op, rhs):
                lhs, rhs = rhs, lhs
            return f"{_rule_cn(lhs)} {_cn_compare_op(op)} {_rule_cn(rhs)}".strip()
        return _rule_cn(expr2)

    if _is_complex_condition(cond_raw):
        logical = _split_top_level_logical(cond_raw)
        split = None if logical else _split_top_level_comparison(cond_raw)
        hint = _extract_condition_hint_from_attached(attached, backend_module=backend)
        relation_locked = _condition_has_rule_locked_relation(cond_raw)
        if logical:
            cond_cn = _render_rule_recursive(cond_raw)
        elif split:
            semantic_cn = _semantic_condition_cn(cond_raw)
            if semantic_cn:
                return semantic_cn, used_hint
            lhs, op, rhs = split
            if _should_swap_condition_comparison_operands(lhs, op, rhs):
                lhs, rhs = rhs, lhs
            lhs_is_call = bool(_COND_FUNC_CALL_RE.search(lhs))
            rhs_is_call = bool(_COND_FUNC_CALL_RE.search(rhs))
            lhs_cn = _rule_cn(lhs)
            rhs_cn = _rule_cn(rhs)
            if hint:
                if rhs_is_call and (not lhs_is_call):
                    rhs_cn = hint
                    used_hint = True
                elif lhs_is_call and (not rhs_is_call):
                    lhs_cn = hint
                    used_hint = True
                elif rhs_is_call and lhs_is_call:
                    rhs_cn = hint
                    used_hint = True
            cond_cn = f"{lhs_cn} {_cn_compare_op(op)} {rhs_cn}".strip()
        else:
            if hint:
                cond_cn = hint
                used_hint = True
            else:
                cond_cn = _render_rule_recursive(cond_raw)
        ai_mode = utils.cfg_get_int(cfg, "structured_cond_ai", 0)
        if utils.cfg_get_int(cfg, "lock_structured_conditions", 1):
            ai_mode = 0
        if getattr(cfg, "ai_assist", False) and ai_mode in (1, 2) and not relation_locked:
            if (ai_mode == 2) or (ai_mode == 1 and not used_hint):
                ai_cn = _ai_structured_condition_cn(cond_raw, attached, name_map, cfg, backend_module=backend)
                if ai_cn:
                    cond_cn = ai_cn.strip()
                    used_hint = True if attached else used_hint
        return cond_cn, used_hint

    cond_cn = _strip_balanced_outer_parens(cond_raw).replace("->", ".")
    split = _split_top_level_comparison(cond_cn)
    semantic_cn = _semantic_condition_cn(cond_raw)
    if semantic_cn:
        return semantic_cn, False
    if split:
        lhs, op, rhs = split
        if _should_swap_condition_comparison_operands(lhs, op, rhs):
            lhs, rhs = rhs, lhs
        cond_cn = f"{_rule_cn(lhs)} {_cn_compare_op(op)} {_rule_cn(rhs)}"
    else:
        cond_cn = re.sub(r"==", " 等于 ", cond_cn)
        cond_cn = re.sub(r"!=", " 不等于 ", cond_cn)
        cond_cn = re.sub(r">=", " 大于等于 ", cond_cn)
        cond_cn = re.sub(r"<=", " 小于等于 ", cond_cn)
        cond_cn = re.sub(r">", " 大于 ", cond_cn)
        cond_cn = re.sub(r"<", " 小于 ", cond_cn)
        cond_cn = cond_cn.replace("&&", " 且 ").replace("||", " 或 ")
        cond_cn = _replace_member_chain_with_owner(cond_cn, name_map, backend_module=backend)
        cond_cn = _replace_idents_for_logic_ex(cond_cn, name_map, allow_member=True, backend_module=backend)
    cond_cn = _prettify_condition_expr_text(cond_cn)
    cond_cn = _strip_ascii_parenthetical_hint(cond_cn)
    cond_cn = re.sub(r"\s+", " ", cond_cn).strip()
    return cond_cn, False


def render_logic_action_from_code(
    code_line: str,
    *,
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    hints: Sequence[Any] = (),
    comment_mode: str = "hint_only",
    literal: bool = False,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    node = _build_logic_ir_node(code_line, attached=[], name_map=name_map, cfg=backend.GenConfig())
    action = ""
    if node and utils._safe_strip(node.get("kind")) in ("assign", "assign_call", "call", "return", "break", "continue"):
        action = _render_logic_ir_node(
            node,
            name_map=name_map,
            local_var_usages=local_var_usages or {},
            literal=literal,
            backend_module=backend,
        )
    if not action:
        action = _render_simple_statement_action(
            code_line,
            name_map=name_map,
            local_var_usages=local_var_usages or {},
            backend_module=backend,
        )
    if not action:
        action = heuristic_logic_line(code_line, name_map=name_map, literal=literal, backend_module=backend) or ""
    return apply_comment_hints_to_logic(action, hints, mode=comment_mode, backend_module=backend)


def _collect_statement_like_units(body: str, *, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    units: list[str] = []
    pending: list[str] = []
    for raw in parse_utils._join_c_line_continuations(body).splitlines():
        tmp = re.sub(r"/\*.*?\*/", "", raw)
        tmp = re.sub(r"//.*", "", tmp).strip()
        if not tmp or tmp.startswith("#"):
            continue
        pending.append(tmp)
        joined = " ".join(x for x in pending if x).strip()
        if not joined:
            pending.clear()
            continue
        if joined.endswith(";") or joined.endswith("{") or joined in ("}", "};"):
            units.append(joined)
            pending.clear()
    if pending:
        joined = " ".join(x for x in pending if x).strip()
        if joined:
            units.append(joined)
    return units


def _build_pack_block_summary(
    codes: Sequence[str],
    *,
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    backend_module=None,
) -> Optional[tuple[str, str]]:
    backend = backend_module or legacy_backend()
    if not codes:
        return None
    txpack_writes = 0
    data_trans_count = 0
    packup_count = 0
    fixed_count = 0
    xor_count = 0
    has_for = False
    has_svpc_store = False
    owners: dict[str, int] = {}
    txpack_owner = ""
    for code in codes:
        stmt = utils._safe_strip(code)
        if not stmt:
            continue
        if re.match(r"^for\s*\(", stmt):
            has_for = True
        parts = backend._split_plain_assignment(stmt)
        if not parts:
            continue
        lhs, rhs = parts
        rhs_s = utils._safe_strip(rhs)
        if "^" in rhs_s:
            xor_count += 1
        if "SVpc" in lhs or "Svpc" in lhs:
            has_svpc_store = True
        if "DataTransFToInt(" in rhs_s:
            data_trans_count += 1
        if "U32PackUp(" in rhs_s:
            packup_count += 1
        if backend._is_txpack_dest_expr(lhs):
            txpack_writes += 1
            if rhs_s.startswith("s_c1394AceDataTx_t."):
                tokens = [t for t in re.split(r"\s*(?:\.|->)\s*", rhs_s.replace("->", ".")) if t]
                if len(tokens) >= 2:
                    txpack_owner = ".".join(tokens[:2])
            if (
                backend._normalize_simple_int_literal(rhs_s) in ("0", "0x0", "0X0")
                or "g_sendFrameCnt" in rhs_s
                or "heart" in lhs.lower()
                or "hlt_" in lhs.lower()
            ):
                fixed_count += 1
        owner = backend._extract_assignment_group_key(stmt)
        if owner and owner not in ("txpack_words",):
            owners[owner] = owners.get(owner, 0) + 1
    if txpack_writes <= 0:
        return None
    if has_for and xor_count > 0 and (has_svpc_store or txpack_writes > 0):
        return ("checksum", "遍历1394发送数据字计算校验值，并回填SVPC及校验字")
    effective_map = dict(name_map or {})
    for k, v in (local_var_usages or {}).items():
        if k and v and k not in effective_map:
            effective_map[k] = v
    owner_key = txpack_owner or (max(owners.items(), key=lambda kv: kv[1])[0] if owners else "")
    owner_cn = backend._humanize_bulk_owner(owner_key, name_map=effective_map, local_var_usages=local_var_usages) if owner_key else ""
    if owner_cn and ("状态字" in owner_cn or "PMFL" in owner_cn or "监测" in owner_cn):
        return ("state_word", f"汇总{owner_cn}并写入1394发送数据字")
    if data_trans_count > 0:
        return ("txpack_measure", "采集并转换测量量，打包更新1394发送数据字")
    if packup_count > 0:
        return ("txpack_cmd", "打包控制指令和反馈量，更新1394发送数据字")
    if fixed_count > 0:
        return ("txpack_fixed", "写入健康状态字、心跳计数等固定打包项")
    last_code = utils._safe_strip(codes[-1])
    parts = backend._split_plain_assignment(last_code)
    if parts:
        lhs, _rhs = parts
        bias = backend._extract_txpack_bias_name(lhs)
        if bias:
            return ("txpack_generic", f"更新{bias}对应的1394发送数据字")
    return ("txpack_generic", "更新1394发送数据字")


def _merge_pack_block_summaries(items: Sequence[tuple[str, str]]) -> list[str]:
    merged: list[tuple[str, str]] = []
    for kind, text in items:
        if merged and kind in ("txpack_measure", "txpack_cmd") and merged[-1][0] in ("txpack_measure", "txpack_cmd"):
            merged[-1] = ("txpack_measure", "批量打包控制指令、反馈量和测量量，更新1394发送数据字")
            continue
        if merged and kind == "txpack_fixed" and merged[-1][0] == "txpack_fixed":
            continue
        if merged and kind == "txpack_generic" and merged[-1][0] == "txpack_generic" and merged[-1][1] == text:
            continue
        merged.append((kind, text))
    return [text for _kind, text in merged]


def _build_enhanced_single_function_logic(body: str, local_vars, *, name_map: Optional[dict[str, str]] = None, backend_module=None) -> Optional[str]:
    backend = backend_module or legacy_backend()
    units = _collect_statement_like_units(body, backend_module=backend)
    if not units:
        return None
    txpack_touch_count = 0
    for unit in units:
        parts = backend._split_plain_assignment(unit)
        if not parts:
            continue
        lhs, rhs = parts
        if backend._is_txpack_dest_expr(lhs) or "s_1394TxPackDat" in rhs:
            txpack_touch_count += 1
    if txpack_touch_count < 6:
        return None
    local_var_usages = {v["name"]: (v.get("cn_name") or v.get("usage") or "") for v in (local_vars or []) if v.get("name")}
    block_codes: list[str] = []
    block_summaries: list[tuple[str, str]] = []
    for unit in units:
        stmt = utils._safe_strip(unit)
        if not stmt:
            continue
        block_codes.append(stmt)
        parts = backend._split_plain_assignment(stmt)
        if not parts:
            continue
        lhs, _rhs = parts
        if not backend._is_txpack_dest_expr(lhs):
            continue
        summary = _build_pack_block_summary(
            block_codes,
            name_map=name_map,
            local_var_usages=local_var_usages,
            backend_module=backend,
        )
        if summary:
            block_summaries.append(summary)
        block_codes = []
    if not block_summaries:
        return None
    merged_lines = _merge_pack_block_summaries(block_summaries)
    state_hits = sum(1 for line in merged_lines if ("状态字" in line or "PMFL" in line or "监测" in line))
    if len(merged_lines) < 4 or state_hits < 2:
        return None
    return "\n".join(merged_lines)


def _suggest_enhanced_single_function_desc(func_info: dict, body: str, current_desc: str = "", *, backend_module=None) -> Optional[str]:
    backend = backend_module or legacy_backend()
    units = _collect_statement_like_units(body, backend_module=backend)
    if not units:
        return None
    txpack_writes = 0
    state_word_writes = 0
    checksum_hits = 0
    for unit in units:
        parts = backend._split_plain_assignment(unit)
        if not parts:
            continue
        lhs, rhs = parts
        rhs_s = utils._safe_strip(rhs)
        if backend._is_txpack_dest_expr(lhs):
            txpack_writes += 1
            if rhs_s.startswith("s_c1394AceDataTx_t."):
                state_word_writes += 1
        if "^" in rhs_s and "s_1394TxPackDat" in rhs_s:
            checksum_hits += 1
    func_name = utils._safe_strip((func_info or {}).get("func_name"))
    looks_like_pack_func = bool(
        txpack_writes >= 6 and state_word_writes >= 2 and (
            checksum_hits > 0 or "pack" in func_name.lower() or "s_1394TxPackDat" in body
        )
    )
    if not looks_like_pack_func:
        return None
    desc = "采集测量量和状态字，打包生成1394发送数据并计算校验"
    current = utils._safe_strip(current_desc)
    if current and current == desc:
        return current
    return desc


def _looks_like_output_label_text(text: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    stripped = re.sub(r"\s+", "", utils._safe_strip(text))
    if (not stripped) or (not text_utils._contains_cjk(stripped)):
        return False
    if len(stripped) > 20:
        return False
    if any(mark in stripped for mark in ("，", ",", "；", ";", "：", ":", "(", ")", "（", "）")):
        return False
    if any(mark in stripped for mark in ("用于", "以便", "根据", "然后", "并", "输出")) and len(stripped) >= 8:
        return False
    return True


def _looks_like_stable_usage_text(text: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    stripped = re.sub(r"\s+", "", utils._safe_strip(text))
    if (not stripped) or (not text_utils._contains_cjk(stripped)):
        return False
    if any(mark in stripped for mark in ("->", ".", "(", ")", "（", "）", "[", "]", "=", ";", "；", "{", "}")):
        return False
    if re.search(r"\b[a-z_][A-Za-z0-9_]*\b", stripped):
        return False
    if re.match(r"^(?:记录|暂存|存放|缓存)[A-Z0-9\u4e00-\u9fff]{2,24}(?:快照|状态|结果|标志|计数|原因)?$", stripped):
        return True
    if re.match(r"^(?:与|和)本拍[A-Z0-9\u4e00-\u9fff]{2,24}比较$", stripped):
        return True
    return False


def _normalize_function_design_texts(design: Any, name_map: Optional[dict[str, str]] = None, *, backend_module=None):
    backend = backend_module or legacy_backend()
    title = _normalize_explanatory_text_for_output(design.title, name_map=name_map, backend_module=backend)
    description_lines = tuple(
        _normalize_explanatory_text_for_output(line, name_map=name_map, backend_module=backend)
        for line in (design.description_lines or ())
        if utils._safe_strip(line)
    )
    io_elements = tuple(
        IOElement(
            name=(e.name if _looks_like_output_label_text(e.name, backend_module=backend) else _normalize_explanatory_text_for_output(e.name, name_map=name_map, backend_module=backend)),
            ident=e.ident,
            c_type=e.c_type,
            direction=e.direction,
        )
        for e in (design.io_elements or ())
    )
    if design.local_elements is None:
        local_elements = None
    else:
        local_elements = tuple(
            LocalDataElement(
                name=(e.name if _looks_like_output_label_text(e.name, backend_module=backend) else _normalize_explanatory_text_for_output(e.name, name_map=name_map, backend_module=backend)),
                ident=e.ident,
                c_type=e.c_type,
                usage=(
                    e.usage
                    if _looks_like_stable_usage_text(e.usage, backend_module=backend)
                    else _normalize_explanatory_text_for_output(e.usage, name_map=name_map, backend_module=backend)
                ),
            )
            for e in design.local_elements
        )
    logic_lines = None if design.logic_lines is None else tuple(
        _normalize_logic_line_for_output(line, name_map=name_map, backend_module=backend)
        for line in design.logic_lines
    )
    return FunctionDesign(
        title=title,
        req_id=design.req_id,
        prototype=design.prototype,
        description_lines=description_lines,
        io_elements=io_elements,
        io_none=design.io_none,
        local_elements=local_elements,
        logic_lines=logic_lines,
        ai_meta=design.ai_meta,
    )


def _build_canonical_file_symbol_map(
    file_context: Optional[dict],
    body: str,
    local_vars: Sequence[dict],
    params: Sequence[dict],
    cfg: Optional[Any],
    *,
    backend_module=None,
) -> tuple[dict[str, str], dict[str, Any]]:
    backend = backend_module or legacy_backend()
    ctx = file_context or {}
    explicit_map = dict(ctx.get("symbol_map") or {})
    typedef_blocks = ctx.get("typedefs") or []
    member_map = dict(ctx.get("member_symbol_map") or {})
    for name, cn in parse_utils._extract_member_symbol_map_from_typedefs(list(typedef_blocks or [])).items():
        ident = utils._safe_strip(name)
        text = utils._safe_strip(cn)
        if ident and text and ident not in member_map:
            member_map[ident] = text

    canonical: dict[str, str] = {}
    inference_log: dict[str, Any] = {}

    for name, cn in explicit_map.items():
        ident = utils._safe_strip(name)
        if not ident:
            continue
        resolved = backend.resolve_canonical_symbol_name(
            ident,
            kind=backend._symbol_kind_for_name(ident),
            comment_cn=utils._safe_strip(cn),
            fallback=ident,
        )
        if resolved and resolved != ident:
            canonical[ident] = resolved
    for ident in _collect_register_base_candidates(body):
        if ident and ident not in canonical:
            guessed = _guess_register_base_label(ident, backend_module=backend)
            if guessed:
                canonical[ident] = guessed

    for name, cn in member_map.items():
        ident = utils._safe_strip(name)
        if not ident:
            continue
        resolved = backend.resolve_canonical_symbol_name(
            ident,
            kind="members",
            comment_cn=utils._safe_strip(cn),
            fallback=ident,
        )
        if resolved and resolved != ident:
            canonical[ident] = resolved

    local_names = {utils._safe_strip((item or {}).get("name")) for item in (local_vars or []) if utils._safe_strip((item or {}).get("name"))}
    param_names = {utils._safe_strip((item or {}).get("name")) for item in (params or []) if utils._safe_strip((item or {}).get("name"))}
    known_names = set(canonical.keys()) | local_names | param_names

    for name in backend._collect_unresolved_body_symbol_candidates(
        body,
        local_names=local_names,
        param_names=param_names,
        known_names=known_names,
    ):
        evidence = backend.collect_symbol_evidence(name, kind="symbols", body=body)
        inference = backend.infer_symbol_semantics(evidence, cfg)
        inference_log[name] = inference
        if inference.candidate_cn and inference.persist_scope != "off":
            canonical[name] = inference.candidate_cn

    for name in _collect_unresolved_macro_candidates(body, known_names=set(canonical.keys()), backend_module=backend):
        evidence = backend.collect_symbol_evidence(name, kind="macros", body=body)
        inference = backend.infer_symbol_semantics(evidence, cfg)
        inference_log[name] = inference
        if inference.candidate_cn and inference.persist_scope != "off":
            canonical[name] = inference.candidate_cn

    member_pairs = _collect_member_access_candidates(body, known_members=set(member_map.keys()), backend_module=backend)
    member_neighbors = [name for name, _base in member_pairs]
    for member, base in member_pairs:
        evidence = backend.collect_symbol_evidence(
            member,
            kind="members",
            body=body,
            owner_type=base,
            neighbor_symbols=member_neighbors,
        )
        inference = backend.infer_symbol_semantics(evidence, cfg)
        inference_log[f"{base}.{member}"] = inference
        if inference.candidate_cn and inference.persist_scope != "off" and not backend._looks_like_low_quality_member_cn(inference.candidate_cn):
            canonical[member] = inference.candidate_cn

    return canonical, inference_log


def _collect_register_base_candidates(body: str) -> list[str]:
    seen: dict[str, None] = {}
    for match in re.finditer(
        r"\b(?P<base>[A-Za-z_]\w*(?:Ureg|Reg|Register)[A-Za-z0-9_]*)\s*(?:\.|->)\s*(?:bit|all|mem|word\d+)_",
        body or "",
        flags=re.IGNORECASE,
    ):
        ident = utils._safe_strip(match.group("base"))
        if ident:
            seen.setdefault(ident, None)
    return list(seen.keys())


def _guess_register_base_label(ident: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(ident)
    if not raw:
        return ""
    stem = re.sub(r"^(?:gc|gs|sc|gp|sp|lp|vp|fp|cp|tp|g|s|l|v|p)_", "", raw)
    stem = re.sub(r"_(?:tp|pt|ptr|buf|arr|list|tbl|table|t|p|un)\b", "", stem, flags=re.IGNORECASE)
    guessed = utils._safe_strip(backend._guess_cn_from_ident(stem))
    guessed = re.sub(r"(?:union|Union|UN|un)$", "", guessed).strip()
    guessed = re.sub(r"(寄存器){2,}", "寄存器", guessed).strip()
    if guessed and text_utils._contains_cjk(guessed) and guessed != "寄存器" and not backend._looks_like_bad_canonical_name(guessed, raw_ident=raw):
        return guessed
    if re.search(r"(?:Ureg|Reg|Register)", stem, flags=re.IGNORECASE):
        prefix = re.split(r"(?:Ureg|Reg|Register)", stem, maxsplit=1, flags=re.IGNORECASE)[0].strip("_")
        prefix_cn = utils._safe_strip(backend._guess_cn_from_ident(prefix)) if prefix else ""
        prefix_cn = re.sub(r"(?:union|Union|UN|un)$", "", prefix_cn).strip()
        if prefix_cn and text_utils._contains_cjk(prefix_cn) and prefix_cn != "寄存器" and not backend._looks_like_bad_canonical_name(prefix_cn, raw_ident=raw):
            return f"{prefix_cn}寄存器"
        acronym = re.sub(r"[^A-Za-z0-9]", "", prefix or "")
        if acronym and len(acronym) <= 8 and acronym.upper() == acronym:
            return f"{acronym}寄存器"
        if prefix and len(prefix) <= 8:
            return f"{prefix.upper()}寄存器"
    return ""


def _dedupe_adjacent_cjk_phrases(text: str) -> str:
    """Collapse adjacent duplicated CJK phrases (1-6 chars) such as
    "状态字状态字状态字" -> "状态字" or "有效有效" -> "有效".
    """
    if not text:
        return text
    pattern = re.compile(r"([\u4e00-\u9fff]{1,6})\1+")
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(r"\1", text)
    return text


def _collapse_repeated_parenthesized_cjk(text: str) -> str:
    if not text:
        return text
    pattern = re.compile(r"([\u4e00-\u9fff]{1,6})\s*[（(]\s*\1\s*[）)]")
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(r"\1", text)
    return text


def _cleanup_generated_logic_text(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = str(text or "").strip()
    if not value:
        return value
    protected_control = _sanitize_control_logic_line(value, backend_module=backend)
    if protected_control:
        return protected_control
    value = value.replace("->", ".")
    value = re.sub(r"\bextern的", "", value)
    value = re.sub(r"\bReadCpuTimer1Counter\s*\(\s*\)", "CPU定时器1计数值", value)
    value = re.sub(r"\bReadCpuTimer1Counter函数结果", "CPU定时器1计数值", value)
    value = re.sub(r"\b([A-Za-z_]\w*)函数判断结果\b", lambda m: f"{_map_func_ident(m.group(1), None, backend_module=backend)}结果", value)
    value = re.sub(r"的const[；;]?", "的", value)
    value = _repair_generated_array_fragment_text(value)
    value = re.sub(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\b", "", value)
    value = re.sub(r"\bbit_u\d+\b\.?", "", value)
    value = re.sub(r"\bmem_u\d+\b\.?", "", value)
    value = re.sub(r"\ball_(?:u16|u32|32)\b\.?", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b([A-Za-z_]\w*)_((?:u|i)(?:8|16|32|64|6))\b", r"\1", value)
    value = re.sub(r"(存放){2,}", "存放", value)
    value = re.sub(r"(缓存){2,}值", "缓存值", value)
    value = re.sub(r"(缓存值){2,}", "缓存值", value)
    value = re.sub(r"(缓存){2,}(?!值)", "缓存", value)
    # Generic CJK duplicate phrase collapse (e.g. "状态字状态字状态字" → "状态字")
    value = _dedupe_adjacent_cjk_phrases(value)
    value = _collapse_repeated_parenthesized_cjk(value)
    value = _strip_ascii_parenthetical_hint(value)
    # Strip all parentheses from control lines
    if re.match(r"^(IF|ELSE\s*IF|WHILE|FOR|SWITCH)\b", value):
        value = value.replace("(", "").replace(")", "")
    value = re.sub(r"([\u4e00-\u9fff])\s+位标志", r"\1位标志", value)
    # Fix spacing before 时
    value = re.sub(r"(\S)\s+时$", r"\1时", value)
    return re.sub(r"\s+", " ", value).strip()


def _repair_generated_array_fragment_text(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    if "[" not in value:
        value = re.sub(r"(\S+项)\s*\]", r"\1", value)
        value = re.sub(r"(\S+)\s*\]\s*([；;])?$", lambda m: f"{m.group(1)}{m.group(2) or ''}", value)
    value = re.sub(r"^计算\s+([^=；;]+?)\s*=\s*\1\]([；;]?)$", r"读取\1\2", value)
    value = re.sub(r"^计算\s+([^=；;]+?)\s*=\s*\1([；;]?)$", r"读取\1\2", value)
    return value


def _normalize_explanatory_text_for_output(text: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not text:
        return text
    body = utils._safe_strip(text)
    if not body:
        return body
    protected_control = _sanitize_control_logic_line(body, backend_module=backend)
    if protected_control:
        return protected_control

    def _replace_macro_guess(match: re.Match) -> str:
        ident = utils._safe_strip(match.group(0))
        guessed = utils._safe_strip(backend._guess_cn_from_ident(ident))
        return guessed or ident

    body = _cleanup_generated_logic_text(body, backend_module=backend)
    # Remove C type casts and ternary expressions that leaked from AI output
    body = re.sub(r"\(\s*(?:Uint16|uint16_t|Uint32|uint32_t|Uint8|uint8_t|int16_t|int32_t|int8_t|float|double|char\s*\*?)\s*\)\s*", "", body)
    body = re.sub(r"\([^()]*\?\s*[^:]*:[^()]*\)", "", body)  # ternary in parens
    body = _replace_low_quality_local_phrases(body, backend_module=backend)
    body = body.replace("->", ".")
    body = _replace_member_chain_with_owner(body, name_map, backend_module=backend)
    body = _replace_idents_for_logic_ex(body, name_map, allow_member=True, backend_module=backend)
    body = re.sub(r"\b[A-Z][A-Z0-9_]{2,}\b", _replace_macro_guess, body)
    body = _cleanup_generated_logic_text(body, backend_module=backend)
    body = body.replace("接收的数据是否上报", "有效")
    body = body.replace("act有效监测有效un", "ACT状态字")
    body = body.replace("acePbit状态un", "PBIT状态字")
    body = body.replace("acePBIT状态un", "PBIT状态字")
    body = body.replace("有效un", "状态字")
    body = body.replace("a有效", "A通道")
    body = body.replace("DSP有效", "DSP")
    body = re.sub(r"\bbit_u\d+\b", "", body)
    body = re.sub(r"\b([A-Za-z_]\w*)有效([A-Za-z_]\w*)\b", r"\1\2", body)
    body = _normalize_array_subscript_text(body, name_map=name_map, backend_module=backend)
    body = re.sub(r"\.+$", "", body)
    body = _replace_low_quality_local_phrases(body, backend_module=backend)
    return re.sub(r"\s+", " ", body).strip()


def _normalize_logic_line_for_output(text: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    if not text:
        return text
    indent = text[: len(text) - len(text.lstrip())]
    stripped = text.strip()
    body = _sanitize_control_logic_line(stripped, name_map=name_map, backend_module=backend) or _normalize_explanatory_text_for_output(stripped, name_map=name_map, backend_module=backend)
    body = re.sub(r"^计算\s+返回结果\s*=\s*(.+?)([；;]?)$", r"暂存\1作为返回结果\2", body)
    body = body.replace("必须为CVGE_DOWN_DMA_PACK_WT_CTRL", "")
    body = re.sub(r"\.+；?$", "；", body)
    body = re.sub(r"\s+", " ", body).strip()
    return indent + body


def _split_c_call_args(arg_text: str) -> list[str]:
    value = str(arg_text or "").strip()
    if not value:
        return []

    args: list[str] = []
    cur: list[str] = []
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0
    in_squote = False
    in_dquote = False
    escape = False

    for ch in value:
        if escape:
            cur.append(ch)
            escape = False
            continue
        if ch == "\\":
            cur.append(ch)
            escape = True
            continue
        if in_squote:
            cur.append(ch)
            if ch == "'":
                in_squote = False
            continue
        if in_dquote:
            cur.append(ch)
            if ch == '"':
                in_dquote = False
            continue
        if ch == "'":
            in_squote = True
            cur.append(ch)
            continue
        if ch == '"':
            in_dquote = True
            cur.append(ch)
            continue
        if ch == "(":
            depth_paren += 1
            cur.append(ch)
            continue
        if ch == ")":
            depth_paren = max(0, depth_paren - 1)
            cur.append(ch)
            continue
        if ch == "[":
            depth_brack += 1
            cur.append(ch)
            continue
        if ch == "]":
            depth_brack = max(0, depth_brack - 1)
            cur.append(ch)
            continue
        if ch == "{":
            depth_brace += 1
            cur.append(ch)
            continue
        if ch == "}":
            depth_brace = max(0, depth_brace - 1)
            cur.append(ch)
            continue
        if ch == "," and depth_paren == 0 and depth_brack == 0 and depth_brace == 0:
            part = "".join(cur).strip()
            if part:
                args.append(part)
            cur = []
            continue
        cur.append(ch)

    last = "".join(cur).strip()
    if last:
        args.append(last)
    return args


_C_TYPE_CAST_RE = re.compile(r"""
    \(\s*                                                # opening paren
    (?:const|volatile|unsigned|signed|static|inline)\s+   # qualifier prefix
    (?:\s*(?:const|volatile|unsigned|signed|static|inline)\s+)*
    [A-Za-z_][A-Za-z0-9_]*                                # type name
    (?:\s*\*\s*)*                                         # pointer stars
    \s*\)
""", re.VERBOSE | re.IGNORECASE)

# Leading type casts: strip (TypeName)(...) or (type_keyword)expr at expression start.
# Only match if the type starts with uppercase (typedef convention) or is a C keyword.
_C_TYPE_KEYWORDS = frozenset({
    "int", "char", "short", "long", "float", "double", "void", "bool",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "int8_t", "int16_t", "int32_t", "int64_t",
})
# Type cast pattern: (TypeName)expr — matches typedefs (uppercase) and lowercase C types.
_C_LEADING_CAST_RE = re.compile(
    r"""^\(\s*(?:[A-Z][A-Za-z0-9_]*|"""
    r"""float\d{2}|sint\d{2}|uint\d{2}|int|char|short|long|float|double|void|bool)"""
    r"""(?:\s*\*)?\s*\)""",
    re.VERBOSE,
)


def _strip_c_type_casts(expr: str) -> str:
    value = str(expr or "").strip()
    if not value:
        return value
    prev = None
    while prev != value:
        prev = value
        start = value.lstrip()
        m = _C_LEADING_CAST_RE.match(start)
        if m:
            value = start[m.end():].lstrip()
    return value.strip()


def _render_supported_c_expr_cn(expr: str, name_map: Optional[dict[str, str]] = None) -> str:
    try:
        from . import c_expr as c_expr_utils

        parsed = c_expr_utils.parse_c_expression(expr)
        rendered = c_expr_utils.render_expr_cn(parsed, name_map or {})
        text = utils._safe_strip(rendered.text)
        if not text:
            return ""
        if text == utils._safe_strip(expr):
            return ""
        if getattr(rendered, "source", "") == "fallback":
            return ""
        if "&" in text or "|" in text or "^" in text or "<<" in text or ">>" in text:
            return ""
        if "低8位" in text or "低 8 位" in text or "补码校验和" in text:
            return text
        return ""
    except Exception:
        return ""


def _logic_cn_expr(expr: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = str(expr or "").strip()
    if not value:
        return value
    value = _strip_c_type_casts(value)
    if not value:
        return value
    rendered_c_expr = _render_supported_c_expr_cn(value, name_map)
    if rendered_c_expr:
        return rendered_c_expr
    if re.fullmatch(r"[A-Za-z_]\w*", value):
        hardware_bit = _hardware_bitfield_display_name(value)
        mapped = utils._safe_strip((name_map or {}).get(value))
        if hardware_bit and (not mapped or _is_low_specificity_hardware_label(mapped)):
            return hardware_bit
        threshold_label = _guess_threshold_macro_label(value)
        if threshold_label and not mapped:
            return threshold_label
        macro_label = _heuristic_macro_display_name(value, name_map=name_map, backend_module=backend)
        if macro_label:
            return macro_label
    alias = _lookup_logic_expr_alias(value, name_map, backend_module=backend)
    if alias:
        return alias
    match = re.match(r"^(?P<func>[A-Za-z_]\w*)\s*\((?P<args>.*)\)\s*$", value)
    if match:
        func = match.group("func")
        args = _split_c_call_args(match.group("args"))
        macro_label = _heuristic_macro_display_name(func, name_map=name_map, backend_module=backend)
        if macro_label:
            return f"{macro_label}结果"
        if func.lower() == "systime":
            return "系统时间"
        specific_role = _specific_role_from_callee(func, "")
        if specific_role:
            if specific_role.startswith(("读取", "获取", "采集")):
                if args:
                    args_cn = "、".join(_logic_cn_expr(arg, name_map=name_map, backend_module=backend) for arg in args if arg.strip())
                    return f"{specific_role}结果({args_cn})" if args_cn else f"{specific_role}结果"
                return f"{specific_role}结果"
            return f"{specific_role}结果"
        func_cn = _map_func_ident(func, name_map, backend_module=backend)
        if func == "ReadCpuTimer1Counter":
            return "CPU定时器1计数值"
        if func.lower().endswith("check"):
            rendered = _render_check_call_expr_cn(func, args, name_map=name_map, backend_module=backend)
            if rendered:
                return rendered
            return f"{func_cn}结果"
        if func.lower().startswith(("get", "read")):
            if args:
                args_cn = "、".join(_logic_cn_expr(arg, name_map=name_map, backend_module=backend) for arg in args if arg.strip())
                return f"{func_cn}结果({args_cn})"
            return f"{func_cn}结果"
        if args:
            args_cn = "、".join(_logic_cn_expr(arg, name_map=name_map, backend_module=backend) for arg in args if arg.strip())
            return f"{func_cn}结果({args_cn})" if args_cn else f"{func_cn}结果"
        return f"{func_cn}结果"
    value = value.replace("->", ".")
    value = _replace_member_chain_with_owner(value, name_map, backend_module=backend)
    value = _replace_idents_for_logic_ex(value, name_map, allow_member=True, backend_module=backend)
    value = _cleanup_generated_logic_text(value, backend_module=backend)
    value = _normalize_array_subscript_text(value, name_map=name_map, backend_module=backend)
    return re.sub(r"\s+", " ", value).strip()


def _render_check_call_expr_cn(
    func: str,
    args: Sequence[str],
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    func_cn = utils._safe_strip(_map_func_ident(func, name_map, backend_module=backend))
    if not func_cn:
        return ""
    core = func_cn.replace("有效校验", "有效性校验")
    args_cn = [
        _logic_cn_expr(arg, name_map=name_map, backend_module=backend)
        for arg in (args or ())
        if utils._safe_strip(arg)
    ]
    args_cn = [utils._safe_strip(arg) for arg in args_cn if utils._safe_strip(arg)]
    if not args_cn:
        return f"{core}结果"
    if len(args_cn) != 1:
        return f"{core}结果({'、'.join(args_cn)})"
    subject = args_cn[0]
    compact_subject = re.sub(r"\s+", "", subject)
    compact_core = re.sub(r"\s+", "", core)
    if not compact_subject or not compact_core:
        return f"{core}结果({subject})"
    overlap = 0
    for size in range(min(len(compact_subject), len(compact_core)), 1, -1):
        if compact_subject.endswith(compact_core[:size]):
            overlap = size
            break
    if overlap:
        merged = compact_subject + compact_core[overlap:]
    else:
        merged = f"{compact_subject}的{compact_core}"
    return f"{merged}结果"


def _guess_threshold_macro_label(ident: str) -> str:
    raw = utils._safe_strip(ident)
    upper = raw.upper()
    if not raw or not re.fullmatch(r"[A-Z][A-Z0-9_]*", raw):
        return ""
    if "COMPTEMPCTRL" in upper:
        if upper.endswith("MIN"):
            return "压气机出口温度恢复下限阈值"
        if upper.endswith("MAX"):
            return "压气机出口温度控制上限阈值"
    return ""


def _format_call_expr(expr: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> Optional[tuple[str, str]]:
    backend = backend_module or legacy_backend()
    value = _strip_c_type_casts(str(expr or "").strip())
    match = re.match(r"^(?P<func>[A-Za-z_]\w*)\s*\((?P<args>.*)\)\s*$", value)
    if not match:
        return None
    func = match.group("func")
    if func in backend._C_KEYWORDS:
        return None
    args = _split_c_call_args(match.group("args"))
    args_cn = ", ".join(_logic_cn_expr(arg, name_map=name_map, backend_module=backend) for arg in args if arg.strip())
    return func, args_cn


def _looks_unresolved_logic_label(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if re.search(r"[A-Z_]{2,}", value):
        return True
    return False


def _guess_loop_bound_label(expr: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(expr)
    if not raw:
        return ""
    alias = _lookup_logic_expr_alias(raw, name_map, backend_module=backend)
    if alias:
        return alias
    token = raw.strip("() ")
    token_upper = token.upper()
    if not re.fullmatch(r"[A-Za-z_]\w*", token):
        return ""
    mapped = utils._safe_strip((name_map or {}).get(token))
    if mapped and not _looks_unresolved_logic_label(mapped):
        return mapped
    if re.search(r"(?:^|_)BIAS_DATA$", token_upper):
        return "数据字数量"
    if re.search(r"(?:^|_)(?:DATA_NUM|DATA_COUNT|DATA_CNT|WORD_NUM|WORD_COUNT|WORD_CNT)$", token_upper):
        return "数据字数量"
    if re.search(r"(?:^|_)(?:LEN|LENGTH)$", token_upper):
        return "长度"
    if re.search(r"(?:^|_)(?:SIZE)$", token_upper):
        return "大小"
    if re.search(r"(?:^|_)(?:NUM|COUNT|CNT)$", token_upper):
        return "数量"
    if re.search(r"(?:^|_)(?:MAX|LIMIT)$", token_upper):
        return "最大数量"
    guessed = backend._guess_cn_from_ident(token)
    guessed = re.sub(r"\s+", "", utils._safe_strip(guessed)).strip()
    if guessed and guessed != token and not _looks_unresolved_logic_label(guessed):
        if guessed.endswith(("数量", "长度", "大小", "上限")):
            return guessed
        if any(word in guessed for word in ("数据", "字", "通道", "作动器", "节点")):
            return f"{guessed}数量"
    return ""


def _normalize_array_subscript_text(text: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = str(text or "")
    if "[" not in value or "]" not in value:
        return value

    def _replace(match: re.Match[str]) -> str:
        raw_index = utils._safe_strip(match.group(1))
        if not raw_index:
            return ""
        if text_utils._contains_cjk(raw_index) and "当前状态" in value:
            index_cn0 = re.sub(r"\s+", "", raw_index).strip()
            if index_cn0.endswith("项"):
                return f"的{index_cn0}"
            return f"的{index_cn0}项"
        if _SIMPLE_INT_LITERAL_RE.fullmatch(raw_index) or _SIMPLE_LOOP_INDEX_RE.fullmatch(raw_index):
            return "项"
        index_cn = _logic_cn_expr(raw_index, name_map=name_map, backend_module=backend)
        index_cn = re.sub(r"\s+", " ", utils._safe_strip(index_cn)).strip()
        if not index_cn or index_cn == raw_index or _looks_unresolved_logic_label(index_cn):
            return "项"
        if index_cn.endswith("项"):
            return f"的{index_cn}"
        return f"的{index_cn}项"

    normalized = re.sub(r"\[([^\]]+)\]", _replace, value)
    normalized = re.sub(r"(?:的)?项(?:项)+", "项", normalized)
    normalized = normalized.replace("的项", "项")
    return normalized


def _render_for_header_cn(header: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    raw = utils._safe_strip(header)
    if not raw:
        return "FOR 遍历循环项"
    match = re.match(r"^for\s*\((.*)\)\s*$", raw)
    content = utils._safe_strip(match.group(1) if match else raw)
    parts = [utils._safe_strip(part) for part in content.split(";", 2)]
    if len(parts) == 3:
        _init, cond, _step = parts
    else:
        cond = content
    cond = utils._safe_strip(cond)
    if not cond:
        return "FOR 遍历循环项"
    cond_match = re.match(r"([A-Za-z_]\w*)\s*(<=|<|>=|>)\s*(.+)", cond)
    if cond_match:
        idx, op, rhs = cond_match.groups()
        idx_cn = _replace_idents_for_logic(idx, name_map, backend_module=backend)
        rhs_cn = _logic_cn_expr(rhs, name_map=name_map, backend_module=backend)
        rhs_cn = re.sub(r"\s+", " ", rhs_cn).strip()
        if _looks_unresolved_logic_label(rhs_cn):
            rhs_cn = _guess_loop_bound_label(rhs, name_map=name_map, backend_module=backend) or "循环上限"
        op_cn = {"<": "小于", "<=": "小于等于", ">": "大于", ">=": "大于等于"}.get(op, op)
        return f"FOR 遍历 {idx_cn} {op_cn} {rhs_cn}" if rhs_cn else f"FOR 遍历 {idx_cn}"
    cond_cn = _logic_cn_expr(cond, name_map=name_map, backend_module=backend)
    cond_cn = re.sub(r"\s+", " ", cond_cn).strip()
    return f"FOR 遍历 {cond_cn}" if cond_cn else "FOR 遍历循环项"


def _build_logic_ir_node(
    code_line: str,
    *,
    attached: Optional[Sequence[str]] = None,
    name_map: Optional[dict[str, str]] = None,
    cfg: Optional[Any] = None,
    use_cond_comment: bool = False,
    backend_module=None,
) -> Optional[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    line = utils._safe_strip(code_line)
    if not line:
        return None

    m_if = re.match(r"^if\s*\((.+)\)", line)
    if m_if:
        cond = utils._safe_strip(m_if.group(1))
        cond_cn = ""
        if cond:
            cond_cn, _ = _render_structured_condition_cn(
                cond,
                list(attached or []) if use_cond_comment else [],
                name_map,
                cfg if isinstance(cfg, backend.GenConfig) else backend.GenConfig(),
                backend_module=backend,
            )
        return {"kind": "if", "cond": cond, "cond_cn": cond_cn, "code": line}

    m_elif = re.match(r"^else\s+if\s*\((.+)\)", line)
    if m_elif:
        cond = utils._safe_strip(m_elif.group(1))
        cond_cn = ""
        if cond:
            cond_cn, _ = _render_structured_condition_cn(
                cond,
                list(attached or []) if use_cond_comment else [],
                name_map,
                cfg if isinstance(cfg, backend.GenConfig) else backend.GenConfig(),
                backend_module=backend,
            )
        return {"kind": "else_if", "cond": cond, "cond_cn": cond_cn, "code": line}

    if re.match(r"^else\b", line):
        return {"kind": "else", "code": line}

    m_while = re.match(r"^while\s*\((.+)\)", line)
    if m_while:
        cond = utils._safe_strip(m_while.group(1))
        cond_cn = ""
        if cond:
            cond_cn, _ = _render_structured_condition_cn(
                cond,
                list(attached or []) if use_cond_comment else [],
                name_map,
                cfg if isinstance(cfg, backend.GenConfig) else backend.GenConfig(),
                backend_module=backend,
            )
        return {"kind": "while", "cond": cond, "cond_cn": cond_cn, "code": line}

    m_do_while = re.match(r"^do\s+while\s*\((.+)\)", line)
    if m_do_while:
        cond = utils._safe_strip(m_do_while.group(1))
        cond_cn = ""
        if cond:
            cond_cn, _ = _render_structured_condition_cn(
                cond,
                list(attached or []) if use_cond_comment else [],
                name_map,
                cfg if isinstance(cfg, backend.GenConfig) else backend.GenConfig(),
                backend_module=backend,
            )
        return {"kind": "do_while", "cond": cond, "cond_cn": cond_cn, "code": line}

    m_for = re.match(r"^for\s*\((.+)\)", line)
    if m_for:
        return {"kind": "for", "header": utils._safe_strip(m_for.group(1)), "code": line}

    m_switch = re.match(r"^switch\s*\((.+)\)", line)
    if m_switch:
        return {"kind": "switch", "expr": utils._safe_strip(m_switch.group(1)), "code": line}

    m_case = re.match(r"^case\s+([^:]+):", line)
    if m_case:
        return {
            "kind": "case",
            "value": utils._safe_strip(m_case.group(1)),
            "label_hint": _extract_condition_hint_from_attached(attached or (), backend_module=backend),
            "code": line,
        }

    if re.match(r"^default\b", line):
        return {
            "kind": "default",
            "label_hint": _extract_condition_hint_from_attached(attached or (), backend_module=backend),
            "code": line,
        }

    if line in ("break", "break;"):
        return {"kind": "break", "code": line}
    if line in ("continue", "continue;"):
        return {"kind": "continue", "code": line}

    m_compound = re.match(r"^(?P<lhs>.+?)\s*(?P<op>\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)\s*(?P<rhs>.+?);?$", line)
    if m_compound:
        return {
            "kind": "compound_assign",
            "lhs": utils._safe_strip(m_compound.group("lhs")),
            "op": utils._safe_strip(m_compound.group("op")),
            "rhs": utils._safe_strip(m_compound.group("rhs")),
            "code": line,
        }

    m_ret = re.match(r"^return(?:\s+(.+?))?;?$", line)
    if m_ret:
        return {"kind": "return", "expr": utils._safe_strip(m_ret.group(1)), "code": line}

    assign = _split_plain_assignment(line if line.endswith(";") else f"{line};")
    if assign:
        lhs, rhs = assign
        call = _format_call_expr(rhs, name_map=name_map, backend_module=backend)
        if call:
            func, _args_cn = call
            args_match = re.match(r"^[A-Za-z_]\w*\s*\((.*)\)\s*$", rhs)
            args = _split_c_call_args(args_match.group(1)) if args_match else []
            return {"kind": "assign_call", "lhs": lhs, "rhs": rhs, "func": func, "args": args, "code": line}
        return {"kind": "assign", "lhs": lhs, "rhs": rhs, "code": line}

    call = _format_call_expr(line[:-1].strip() if line.endswith(";") else line, name_map=name_map, backend_module=backend)
    if call:
        func, _args_cn = call
        args_match = re.match(r"^[A-Za-z_]\w*\s*\((.*)\)\s*$", line[:-1].strip() if line.endswith(";") else line)
        args = _split_c_call_args(args_match.group(1)) if args_match else []
        return {"kind": "call", "func": func, "args": args, "code": line}

    return {"kind": "raw", "code": line}


def _render_logic_ir_node(
    node: dict[str, Any],
    *,
    name_map: Optional[dict[str, str]] = None,
    local_var_usages: Optional[dict[str, str]] = None,
    literal: bool = False,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    kind = utils._safe_strip((node or {}).get("kind"))
    code = utils._safe_strip((node or {}).get("code"))
    effective_map = dict(name_map or {})
    for k, v in (local_var_usages or {}).items():
        if k and v and k not in effective_map:
            effective_map[k] = v

    if kind == "if":
        cond_cn = utils._safe_strip((node or {}).get("cond_cn"))
        return f"IF {cond_cn} 时" if cond_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "else_if":
        cond_cn = utils._safe_strip((node or {}).get("cond_cn"))
        return f"ELSE IF {cond_cn} 时" if cond_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "else":
        return "ELSE"
    if kind == "while":
        cond_cn = utils._safe_strip((node or {}).get("cond_cn"))
        return f"WHILE {cond_cn} 时" if cond_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "do_while":
        cond_cn = utils._safe_strip((node or {}).get("cond_cn"))
        return f"DO WHILE {cond_cn} 时" if cond_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "for":
        return fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "switch":
        expr = utils._safe_strip((node or {}).get("expr"))
        expr_cn = _logic_cn_expr(expr, name_map=effective_map, backend_module=backend)
        expr_cn = re.sub(r"\s+", " ", expr_cn).strip()
        return f"SWITCH 根据 {expr_cn} 分支处理" if expr_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "case":
        label_hint = utils._safe_strip((node or {}).get("label_hint"))
        if label_hint:
            return f"CASE 分支 {label_hint}"
        value = utils._safe_strip((node or {}).get("value"))
        value_cn = _logic_cn_expr(value, name_map=effective_map, backend_module=backend)
        value_cn = re.sub(r"\s+", " ", value_cn).strip()
        return f"CASE 分支 {value_cn}" if value_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "default":
        return "DEFAULT"
    if kind == "break":
        return "退出当前循环或分支"
    if kind == "continue":
        return "跳过本轮循环，进入下一轮循环"
    if kind == "return":
        expr = utils._safe_strip((node or {}).get("expr"))
        if not expr:
            return "返回"
        ternary_ret = _render_ternary_return_text(expr, name_map=effective_map, backend_module=backend)
        if ternary_ret:
            return ternary_ret
        expr_cn = _logic_cn_expr(expr, name_map=effective_map, backend_module=backend)
        return f"返回 {expr_cn or expr}"
    if kind == "call":
        func = utils._safe_strip((node or {}).get("func"))
        args = list((node or {}).get("args") or [])
        if func == "memset" and len(args) >= 2:
            target_clean = utils._safe_strip(args[0])
            for _ in range(3):
                target_clean = re.sub(r"^\([^)]*\)\s*", "", target_clean).strip()
            target_clean = target_clean.lstrip("&").strip()
            tgt_cn = _logic_cn_expr(target_clean, name_map=effective_map, backend_module=backend)
            value = utils._safe_strip(args[1])
            val_cn = _logic_cn_expr(value, name_map=effective_map, backend_module=backend)
            if re.match(r"^0([UuLl]*)$|^0x0([UuLl]*)$", value):
                return f"清零 {tgt_cn}"
            return f"填充 {tgt_cn} 为 {val_cn}"
        if func == "memcpy" and len(args) >= 2:
            dst_cn = _logic_cn_expr(args[0], name_map=effective_map, backend_module=backend)
            src_cn = _logic_cn_expr(args[1], name_map=effective_map, backend_module=backend)
            return f"拷贝 {src_cn} 到 {dst_cn}"
        func_cn = _map_func_ident(func, effective_map, backend_module=backend)
        if re.search(r"unpack$", func, re.IGNORECASE):
            tail = re.sub(r"解包$", "", func_cn)
            return f"解包{tail}".strip()
        if re.search(r"pack$", func, re.IGNORECASE):
            tail = re.sub(r"打包$", "", func_cn)
            return f"打包{tail}".strip()
        return _render_call_function_action(func, effective_map, backend_module=backend) if func_cn else fallback_logic_line(code, name_map=effective_map, backend_module=backend)
    if kind == "assign_call":
        lhs = utils._safe_strip((node or {}).get("lhs"))
        rhs = utils._safe_strip((node or {}).get("rhs"))
        func = utils._safe_strip((node or {}).get("func"))
        args = list((node or {}).get("args") or [])
        lhs_cn = _logic_cn_expr(lhs, name_map=effective_map, backend_module=backend)
        func_cn = _map_func_ident(func, effective_map, backend_module=backend)
        args_cn = ", ".join(_logic_cn_expr(a, name_map=effective_map, backend_module=backend) for a in args if utils._safe_strip(a))
        call_text = _render_call_function_action(func, effective_map, backend_module=backend)
        if args_cn:
            call_text = f"{call_text}({args_cn})"
        if func == "DataTransFToInt":
            src_cn = _logic_cn_expr(args[0], name_map=effective_map, backend_module=backend) if args else "输入量"
            return f"转换{src_cn}到{lhs_cn}"
        if func == "U32PackUp" and _is_txpack_dest_expr(lhs, backend_module=backend):
            bias = _extract_txpack_bias_name(lhs, backend_module=backend) or "1394发送数据字"
            return f"打包高低字并写入{bias}"
        if func.lower().startswith(("get", "read")):
            return f"读取 {func_cn} 写入 {lhs_cn}"
        if func.lower() in ("scigetchar",):
            return f"读取 {func}({args_cn}) 写入 {lhs_cn}"
        if func.lower() in ("scirxfifocount",):
            return f"获取 {func}({args_cn}) 写入 {lhs_cn}"
        if literal:
            rhs_cn = _logic_cn_expr(rhs, name_map=effective_map, backend_module=backend)
            return f"{lhs_cn} = {rhs_cn}"
        if args_cn:
            return f"{call_text}，结果写入 {lhs_cn}"
        return f"{call_text}并写入{lhs_cn}"
    if kind == "compound_assign":
        lhs = utils._safe_strip((node or {}).get("lhs"))
        rhs = utils._safe_strip((node or {}).get("rhs"))
        op = utils._safe_strip((node or {}).get("op"))
        lhs_cn = _logic_cn_expr(lhs, name_map=effective_map, backend_module=backend)
        rhs_clean = _strip_balanced_outer_parens(rhs)
        rhs_cn = _logic_cn_expr(rhs_clean, name_map=effective_map, backend_module=backend)
        verb = {
            "+=": "累加",
            "-=": "递减",
            "*=": "乘以并更新",
            "/=": "除以并更新",
            "%=": "取余并更新",
            "<<=": "左移并更新",
            ">>=": "右移并更新",
            "&=": "按位与并更新",
            "|=": "按位或并更新",
            "^=": "按位异或并更新",
        }.get(op, "更新")
        if _is_zero_literal(rhs_clean):
            return f"清零{lhs_cn}"
        if literal:
            return f"{lhs_cn} {op} {rhs_cn}"
        return f"{lhs_cn}{verb}{rhs_cn}"
    if kind == "assign":
        simple = _render_simple_statement_action(code, name_map=effective_map, local_var_usages=local_var_usages, backend_module=backend)
        if simple:
            return simple
        lhs = utils._safe_strip((node or {}).get("lhs"))
        rhs = utils._safe_strip((node or {}).get("rhs"))
        lhs_cn = _logic_cn_expr(lhs, name_map=effective_map, backend_module=backend)
        rhs_clean = _strip_balanced_outer_parens(rhs)
        rhs_cn = _logic_cn_expr(rhs_clean, name_map=effective_map, backend_module=backend)
        bit_chain = _render_bitwise_chain_assignment(lhs, rhs_clean, effective_map, backend_module=backend)
        if bit_chain:
            return bit_chain
        if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", lhs):
            return f"更新{lhs_cn}"
        if _is_zero_literal(rhs_clean):
            return f"清零{lhs_cn}"
        if re.search(r"(\bsizeof\b|[()+*/%]|-)", rhs_clean):
            if literal:
                return f"{lhs_cn} = {rhs_cn}"
            return f"计算 {lhs_cn} = {rhs_cn}"
        if literal:
            return f"{lhs_cn} = {rhs_cn}"
        return f"将 {rhs_cn} 写入 {lhs_cn}"
    if kind == "raw":
        return fallback_logic_line(code, name_map=effective_map, backend_module=backend)

    return fallback_logic_line(code, name_map=effective_map, backend_module=backend)


def _split_top_level_bitwise_chain(expr: str) -> Optional[tuple[str, list[str]]]:
    value = str(expr or "").strip()
    if not value:
        return None
    parts: list[str] = []
    operators: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in value:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if depth == 0 and ch in "&|^":
            part = "".join(current).strip()
            if part:
                parts.append(part)
            operators.append(ch)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    if len(parts) < 2 or not operators or len(set(operators)) != 1 or len(operators) != len(parts) - 1:
        return None
    return operators[0], parts


def _render_bitwise_chain_assignment(lhs: str, rhs: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    chain = _split_top_level_bitwise_chain(rhs)
    if not chain:
        return ""
    op, parts = chain
    lhs_cn = _logic_cn_expr(lhs, name_map=name_map, backend_module=backend)
    part_names = [_logic_cn_expr(part, name_map=name_map, backend_module=backend) for part in parts]
    part_names = [_simplify_bitwise_operand_text(item, backend_module=backend) for item in part_names if utils._safe_strip(item)]
    if len(part_names) < 2:
        return ""
    verb = {"&": "按位与", "|": "按位或", "^": "按位异或"}.get(op, "位运算")
    return f"将{'、'.join(part_names)}{verb}结果写入{lhs_cn}"


def _simplify_bitwise_operand_text(text: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return ""
    value = re.sub(r"^\s*\(\s*", "", value)
    value = re.sub(r"\s*\)\s*$", "", value)
    value = re.sub(r"^\s*(?:无符号|有符号)?\s*(?:8|16|32|64)位整型\s*", "", value)
    value = re.sub(r"^\s*(?:Uint(?:8|16|32|64)|Int(?:8|16|32|64)|uint(?:8|16|32|64)_t|int(?:8|16|32|64)_t)\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^const\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", "", value)
    value = value.replace("临时32位整型", "临时值")
    value = value.replace("中间结果", "中间值")
    return value or text



_RAW_BITWISE_CONDITION_OP_RE = re.compile(r"(?<![&])&(?![&=])|(?<![|])\|(?![|=])|\^(?!=)")


def _contains_raw_bitwise_condition_operator(expr: str) -> bool:
    return bool(_RAW_BITWISE_CONDITION_OP_RE.search(str(expr or "")))

def fallback_logic_line(code_line: str, name_map: Optional[dict[str, str]] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    line = str(code_line or "").strip()
    match_if = re.match(r"(?:else\s+)?if\s*\((.+)\)", line)
    if match_if:
        cond = match_if.group(1).strip()
        if cond.startswith("(") and (cond.count("(") == cond.count(")") + 1):
            cond = cond[1:].strip()
        cond_cn = cond.replace("->", ".")
        cond_cn = _strip_c_type_casts(cond_cn)
        raw_bitwise_cond = _contains_raw_bitwise_condition_operator(cond_cn)
        supported_bitwise_cond = _render_supported_c_expr_cn(cond_cn, name_map) if raw_bitwise_cond else ""
        if supported_bitwise_cond:
            return f"{'ELSE IF' if line.lstrip().startswith('else if') else 'IF'} {supported_bitwise_cond} 时"
        if "<<" not in cond_cn and ">>" not in cond_cn and not raw_bitwise_cond:
            structured, _ = _render_structured_condition_cn(cond_cn, (), name_map, None, backend_module=backend)
            if structured:
                return f"{'ELSE IF' if line.lstrip().startswith('else if') else 'IF'} {structured} 时"
        cond_cn = cond_cn.replace("<<", " 左移 ").replace(">>", " 右移 ")
        cond_cn = re.sub(r"==", " 等于 ", cond_cn)
        cond_cn = re.sub(r"!=", " 不等于 ", cond_cn)
        cond_cn = re.sub(r">=", " 大于等于 ", cond_cn)
        cond_cn = re.sub(r"<=", " 小于等于 ", cond_cn)
        cond_cn = re.sub(r">", " 大于 ", cond_cn)
        cond_cn = re.sub(r"<", " 小于 ", cond_cn)
        cond_cn = cond_cn.replace("&&", " 且 ").replace("||", " 或 ")
        cond_cn = _replace_member_chain_with_owner(cond_cn, name_map, backend_module=backend)
        cond_cn = _replace_idents_for_logic_ex(cond_cn, name_map, allow_member=True, backend_module=backend)
        cond_cn = re.sub(r"\s+", " ", cond_cn).strip()
        cond_cn = _dedupe_adjacent_cjk_phrases(cond_cn)
        return f"{'ELSE IF' if line.lstrip().startswith('else if') else 'IF'} {cond_cn} 时"

    match_while = re.match(r"while\s*\((.+)\)", line)
    if match_while:
        cond_cn = match_while.group(1).strip()
        if cond_cn.startswith("(") and (cond_cn.count("(") == cond_cn.count(")") + 1):
            cond_cn = cond_cn[1:].strip()
        cond_cn = cond_cn.replace("->", ".")
        cond_cn = _strip_c_type_casts(cond_cn)
        raw_bitwise_cond = _contains_raw_bitwise_condition_operator(cond_cn)
        supported_bitwise_cond = _render_supported_c_expr_cn(cond_cn, name_map) if raw_bitwise_cond else ""
        if supported_bitwise_cond:
            return f"WHILE {supported_bitwise_cond} 时"
        if "<<" not in cond_cn and ">>" not in cond_cn and not raw_bitwise_cond:
            structured, _ = _render_structured_condition_cn(cond_cn, (), name_map, None, backend_module=backend)
            if structured:
                return f"WHILE {structured} 时"
        cond_cn = cond_cn.replace("<<", " 左移 ").replace(">>", " 右移 ")
        cond_cn = re.sub(r"==", " 等于 ", cond_cn)
        cond_cn = re.sub(r"!=", " 不等于 ", cond_cn)
        cond_cn = re.sub(r">=", " 大于等于 ", cond_cn)
        cond_cn = re.sub(r"<=", " 小于等于 ", cond_cn)
        cond_cn = re.sub(r">", " 大于 ", cond_cn)
        cond_cn = re.sub(r"<", " 小于 ", cond_cn)
        cond_cn = cond_cn.replace("&&", " 且 ").replace("||", " 或 ")
        cond_cn = _replace_member_chain_with_owner(cond_cn, name_map, backend_module=backend)
        cond_cn = _replace_idents_for_logic_ex(cond_cn, name_map, allow_member=True, backend_module=backend)
        cond_cn_normalized = re.sub(r"\s+", " ", cond_cn).strip()
        cond_cn_normalized = _dedupe_adjacent_cjk_phrases(cond_cn_normalized)
        return f"WHILE {cond_cn_normalized} 时"

    match_for = re.match(r"for\s*\(([^;]*);([^;]*);", line)
    if match_for:
        return _render_for_header_cn(line, name_map=name_map, backend_module=backend)

    match_switch = re.match(r"switch\s*\((.+)\)", line)
    if match_switch:
        expr_cn = match_switch.group(1).strip().replace("->", ".")
        expr_cn = _replace_member_chain_with_owner(expr_cn, name_map, backend_module=backend)
        expr_cn = _replace_idents_for_logic_ex(expr_cn, name_map, allow_member=True, backend_module=backend)
        expr_cn_normalized = re.sub(r"\s+", " ", expr_cn).strip()
        return f"SWITCH 根据 {expr_cn_normalized} 分支处理"

    match_case = re.match(r"case\s+([^:]+):", line)
    if match_case:
        val_cn = match_case.group(1).strip().replace("->", ".")
        val_cn = _replace_member_chain_with_owner(val_cn, name_map, backend_module=backend)
        val_cn = _replace_idents_for_logic_ex(val_cn, name_map, allow_member=True, backend_module=backend)
        val_cn_normalized = re.sub(r"\s+", " ", val_cn).strip()
        return f"CASE 分支 {val_cn_normalized}"

    if line.lstrip().startswith("default"):
        return "DEFAULT 默认分支"

    match_ret = re.match(r"return\s+(.+);", line)
    if match_ret:
        val_cn = _logic_cn_expr(match_ret.group(1).strip(), name_map=name_map, backend_module=backend)
        return f"返回 {val_cn or match_ret.group(1).strip()}"

    if "=" in line and line.endswith(";"):
        core = line[:-1].strip()
        if ("=" in core) and (not re.search(r"(==|!=|>=|<=|\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)", core)):
            lhs, rhs = [part.strip() for part in core.split("=", 1)]
            lhs_cn = _logic_cn_expr(lhs, name_map=name_map, backend_module=backend)
            call = _format_call_expr(rhs, name_map=name_map, backend_module=backend)
            if call:
                func, args_cn = call
                call_text = _render_call_function_action(func, name_map, backend_module=backend)
                if args_cn:
                    call_text = f"{call_text}({args_cn})"
                return f"{call_text}，结果写入 {lhs_cn or lhs}"
            rhs_cn = _logic_cn_expr(rhs, name_map=name_map, backend_module=backend)
            if lhs_cn and rhs_cn:
                return f"将 {rhs_cn} 写入 {lhs_cn}"
        var = core.split("=", 1)[0].strip()
        return f"赋值 {_logic_cn_expr(var, name_map=name_map, backend_module=backend) or var}"

    call_core = line[:-1].strip() if line.endswith(";") else line
    call = _format_call_expr(call_core, name_map=name_map, backend_module=backend)
    if call:
        func, _args_cn = call
        if func not in backend._C_KEYWORDS:
            return _render_named_call_action_from_ident(func, name_map, backend_module=backend) or _render_call_function_action(func, name_map, backend_module=backend)
    code_hint = _logic_cn_expr(call_core, name_map=name_map, backend_module=backend) or call_core
    if code_hint and code_hint != call_core:
        return f"执行操作（{code_hint}）"
    return f"执行操作：{call_core or '未知语句'}"


def heuristic_logic_line(code_line: str, name_map: Optional[dict[str, str]] = None, *, literal: bool = False, backend_module=None) -> Optional[str]:
    backend = backend_module or legacy_backend()
    line = str(code_line or "").strip()
    if not line:
        return None
    core = line[:-1].strip() if line.endswith(";") else line
    normalized_core = _strip_c_type_casts(core)
    call = _format_call_expr(core, name_map=name_map, backend_module=backend)
    if call:
        func, _args_cn = call
        args_match = re.match(r"^[A-Za-z_]\w*\s*\((.*)\)\s*$", normalized_core)
        args = _split_c_call_args(args_match.group(1)) if args_match else []
        if func == "memset" and len(args) >= 2:
            target_clean = args[0].strip()
            for _ in range(3):
                target_clean = re.sub(r"^\([^)]*\)\s*", "", target_clean).strip()
            target_clean = target_clean.lstrip("&").strip()
            tgt_cn = _logic_cn_expr(target_clean, name_map=name_map, backend_module=backend)
            val_cn = _logic_cn_expr(args[1], name_map=name_map, backend_module=backend)
            if re.match(r"^0([UuLl]*)$|^0x0([UuLl]*)$", args[1].strip()):
                return f"清零 {tgt_cn}"
            return f"填充 {tgt_cn} 为 {val_cn}"
        if func == "memcpy" and len(args) >= 2:
            dst_cn = _logic_cn_expr(args[0], name_map=name_map, backend_module=backend)
            src_cn = _logic_cn_expr(args[1], name_map=name_map, backend_module=backend)
            return f"拷贝 {src_cn} 到 {dst_cn}"
        if func and func not in backend._C_KEYWORDS:
            func_cn = _map_func_ident(func, name_map, backend_module=backend)
            if re.search(r"unpack$", func, re.IGNORECASE):
                return f"解包{re.sub(r'解包$', '', func_cn)}".strip()
            if re.search(r"pack$", func, re.IGNORECASE):
                return f"打包{re.sub(r'打包$', '', func_cn)}".strip()
            return _render_named_call_action_from_ident(func, name_map, backend_module=backend) or _render_call_function_action(func, name_map, backend_module=backend)

    match_sizeof = re.match(r"^(?P<lhs>.+?)\s*=\s*sizeof\s*\((?P<what>.+)\)\s*$", core)
    if match_sizeof:
        lhs_cn = _logic_cn_expr(match_sizeof.group("lhs"), name_map=name_map, backend_module=backend)
        what_cn = _logic_cn_expr(match_sizeof.group("what"), name_map=name_map, backend_module=backend)
        return f"获取 {what_cn} 大小到 {lhs_cn}"

    parts = backend._split_plain_assignment(core + ";")
    if parts:
        lhs, rhs = parts
        lhs_cn = _logic_cn_expr(lhs, name_map=name_map, backend_module=backend)
        rhs_cn = _logic_cn_expr(rhs, name_map=name_map, backend_module=backend)
        call2 = _format_call_expr(rhs, name_map=name_map, backend_module=backend)
        if call2:
            func, args_cn = call2
            normalized_rhs = _strip_c_type_casts(rhs)
            args_match = re.match(r"^[A-Za-z_]\w*\s*\((.*)\)\s*$", normalized_rhs)
            args = _split_c_call_args(args_match.group(1)) if args_match else []
            func_cn = _map_func_ident(func, name_map, backend_module=backend)
            call_text = _render_call_function_action(func, name_map, backend_module=backend)
            if args_cn:
                call_text = f"{call_text}({args_cn})"
            if func == "DataTransFToInt":
                src_cn = _logic_cn_expr(args[0], name_map=name_map, backend_module=backend) if args else "输入量"
                return f"转换{src_cn}到{lhs_cn}"
            if func == "U32PackUp" and backend._is_txpack_dest_expr(lhs):
                bias = backend._extract_txpack_bias_name(lhs) or "1394发送数据字"
                return f"打包高低字并写入{bias}"
            if func.lower().startswith(("get", "read")):
                return f"读取 {func_cn} 写入 {lhs_cn}"
            if func.lower() in ("scigetchar",):
                return f"读取 {func}({args_cn}) 写入 {lhs_cn}"
            if func.lower() in ("scirxfifocount",):
                return f"获取 {lhs_cn} = {func}({args_cn})"
            return f"{lhs_cn} = {call_text}" if literal else f"{call_text} 获取 {lhs_cn}"
        if re.search(r"(\\bsizeof\\b|[()+*/%]|-)", rhs):
            if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", lhs):
                return f"更新{lhs_cn}"
            return f"{lhs_cn} = {rhs_cn}" if literal else f"计算 {lhs_cn} = {rhs_cn}"
        if re.search(r"(?:\.|->)\s*(?:bit|all|mem|word\d+)_u\d+\s*(?:\.|->)", lhs):
            return f"更新{lhs_cn}"
        return f"{lhs_cn} = {rhs_cn}" if literal else f"将 {rhs_cn} 写入 {lhs_cn}"
    return None


def _replace_generic_call_with_verb(
    line: str,
    func_name: str,
    name_map: Optional[dict[str, str]] = None,
) -> str:
    if "获取" in line:
        return line.replace("调用函数", "")
    if func_name and any("\u4e00" <= ch <= "\u9fff" for ch in func_name):
        return line.replace("调用函数", "")
    lowered = func_name.lower()
    if any(part in lowered for part in ("read", "get", "recv", "rx", "acquire")):
        return line.replace("调用函数", "读取 ")
    if any(part in lowered for part in ("write", "set", "send", "tx")):
        return line.replace("调用函数", "写入 ")
    if any(part in lowered for part in ("check", "valid", "verify", "monitor", "mntr")):
        return line.replace("调用函数", "检查 ")
    if any(part in lowered for part in ("calc", "comput", "eval", "ctrl")):
        return line.replace("调用函数", "执行 ")
    if any(part in lowered for part in ("init", "reset", "clear", "clr")):
        return line.replace("调用函数", "初始化 ")
    if any(part in lowered for part in ("convert", "trans", "pack")):
        return line.replace("调用函数", "转换 ")
    return line


def repair_unresolved_logic_lines(logic_lines: Sequence[str], symbol_map: dict[str, str]) -> list[str]:
    if not symbol_map:
        return list(logic_lines)
    repaired: list[str] = []
    structural_keywords = frozenset({"END", "ELSE", "FOR", "SWITCH", "CASE", "DEFAULT", "NEXT"})
    unresolved_ident_re = re.compile(r"\b([A-Za-z]+_[A-Za-z0-9_]{2,}|[A-Z]{2,}[A-Za-z0-9_]{2,})\b")
    for line in logic_lines:
        stripped = line.strip()
        first_word = stripped.split()[0] if stripped else ""
        if first_word in structural_keywords:
            repaired.append(line)
            continue
        new_line = line
        changed = False
        for match in unresolved_ident_re.finditer(line):
            ident = match.group(1)
            if ident in symbol_map:
                new_line = new_line.replace(ident, symbol_map[ident])
                changed = True
        refreshed = _sanitize_control_logic_line(new_line, name_map=symbol_map) if changed else ""
        if refreshed:
            new_line = refreshed
        repaired.append(new_line)
    return repaired


def repair_generic_logic_calls(
    logic_lines: Sequence[str],
    body: str = "",
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> list[str]:
    backend = backend_module or legacy_backend()
    if not logic_lines:
        return list(logic_lines)
    result: list[str] = []
    for line in logic_lines:
        stripped = line.strip()
        if "调用函数" not in stripped:
            result.append(line)
            continue
        match = re.search(r"调用函数([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)?", stripped)
        if not match:
            result.append(line)
            continue
        func_name = (match.group(1) or "").strip()
        indent = line[: len(line) - len(line.lstrip())]
        if not func_name and body:
            for code_line in body.split("\n"):
                candidate = code_line.strip()
                found = re.search(r"([A-Za-z_]\w+)\s*\(", candidate)
                if found and not candidate.startswith("//") and not candidate.startswith("/*"):
                    func_name = found.group(1)
                    break
        if not func_name:
            result.append(line)
            continue
        improved = False
        if body and func_name in body:
            for code_line in body.split("\n"):
                candidate = code_line.strip()
                if func_name in candidate and candidate and not candidate.startswith("//"):
                    hint = heuristic_logic_line(candidate, name_map=name_map, backend_module=backend)
                    if hint and "调用函数" not in hint:
                        result.append(indent + hint)
                        improved = True
                        break
        if not improved:
            result.append(indent + _replace_generic_call_with_verb(stripped, func_name))
    return result


def expand_thin_logic(
    logic_lines: Sequence[str],
    body: str,
    name_map: Optional[dict[str, str]] = None,
    cfg: Optional[Any] = None,
) -> list[str]:
    if not logic_lines or len(logic_lines) > 1 or not body or not body.strip():
        return list(logic_lines)
    try:
        new_logic, _new_unknowns = generate_logic_from_body(body, local_vars=[], cfg=cfg or legacy_backend().GenConfig(), name_map=name_map)
        new_lines = [line for line in new_logic.split("\n") if line.strip()]
        if len(new_lines) > len(logic_lines):
            return new_lines
    except Exception:
        pass
    return list(logic_lines)


def _select_local_usage_text(item: dict, *, body: str, comment_desc: str = "", cfg: Optional[Any] = None, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    working_item = dict(item or {})
    neighbor_symbols = [utils._safe_strip(x) for x in (working_item.get("neighbor_symbols") or ()) if utils._safe_strip(x)]
    backend._repair_local_cn_name_with_profile(
        working_item,
        body=body,
        neighbor_symbols=neighbor_symbols,
        comment_desc=comment_desc,
        backup_cn=utils._safe_strip(working_item.get("cn_name")) or utils._safe_strip(working_item.get("comment_hint")),
        cfg=cfg,
    )
    name = utils._safe_strip(working_item.get("name"))
    cn_name = backend._select_local_display_name(working_item)
    raw_usage = utils._safe_strip(working_item.get("usage"))
    evidence = backend.collect_symbol_evidence(
        name,
        kind="symbols",
        body=body,
        decl_type=utils._safe_strip(working_item.get("type")),
        neighbor_symbols=neighbor_symbols,
        source_comment_hints=[cn_name, raw_usage, comment_desc],
    )
    tags = set(evidence.producer_arg_tags or ())
    consumers = set(evidence.consumer_patterns or ())
    sinks = set(evidence.sink_patterns or ())
    dataflow_roles = set(evidence.dataflow_roles or ())
    decl_lower = utils._safe_strip(evidence.decl_type).lower()
    sym_lower = utils._safe_strip(name).lower()
    digit_match = re.search(r"(\d{3})", cn_name or name)
    if cn_name.endswith("打包缓存") and digit_match:
        return f"组装{digit_match.group(1)}字故障输出数据"
    if cn_name.endswith("兼容字"):
        return f"汇总{cn_name}"
    if cn_name == "换算系数":
        return "提供数值换算系数"
    if cn_name.endswith("错误标志"):
        return f"标记{cn_name}"
    if cn_name == "模式源字":
        return "缓存模式源状态字"
    if evidence.producer_call == "RedunDataGet" and cn_name:
        return f"记录{cn_name}快照"
    if "results_bit32" in tags and cn_name:
        if sym_lower.startswith(("l_s_", "s_")):
            return f"与本拍{_strip_previous_prefix(cn_name, backend_module=backend).replace('快照', '')}比较"
        return f"记录{cn_name}"
    if cn_name and ((sym_lower.startswith("l_s_") and "used_in_condition" in consumers) or ("compared_to_static_prev" in consumers)):
        base = _strip_previous_prefix(cn_name, backend_module=backend)
        if base:
            return f"与本拍{base.replace('快照', '')}比较"
    if ("state_snapshot" in dataflow_roles or ("previous_snapshot" in dataflow_roles and "state_value" in dataflow_roles)) and cn_name:
        base = _strip_previous_prefix(cn_name, backend_module=backend).replace("快照", "")
        if base:
            return f"记录{base}快照"
    if "eval" in decl_lower and cn_name:
        return f"暂存{cn_name}"
    if "counter_value" in dataflow_roles and cn_name and cn_name.endswith(("计数", "次数")):
        return f"累计{cn_name}"
    if "output_limit" in dataflow_roles and cn_name:
        return "限制制动输出" if ("brk" in sym_lower or "break" in sym_lower) else "限制输出范围"
    if "clamp_result" in dataflow_roles and cn_name:
        return "执行限幅约束"
    if "pointer_write" in sinks and cn_name:
        return f"输出{cn_name}"
    if "state_member_write" in sinks and cn_name:
        return f"更新{cn_name}"
    if cn_name:
        estimate_match = re.match(r"(.+?)估算值$", cn_name)
        if estimate_match:
            return f"估算{estimate_match.group(1)}"
        calc_match = re.match(r"(.+?)计算值$", cn_name)
        if calc_match:
            return f"计算{calc_match.group(1)}"
        if cn_name.endswith("绝对值"):
            return f"计算{cn_name}"
    raw_usage_usable = raw_usage and (not backend._looks_like_too_generic_usage_text(raw_usage)) and (not backend._looks_like_generic_local_usage(raw_usage, cn_name))
    if raw_usage_usable:
        cleaned = backend._sanitize_ai_usage_text(raw_usage)
        if cleaned:
            return cleaned
    return backend._normalize_local_usage(cfg or backend.GenConfig(ai_assist=False), raw_usage if raw_usage_usable else "", name, cn_name)


def _build_local_param_symbol_map(
    local_vars: Sequence[dict],
    params: Sequence[dict],
    in_map: dict[str, str],
    out_map: dict[str, str],
    param_ai_name_map: dict[str, str],
    *,
    backend_module=None,
) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    mapping: dict[str, str] = {}
    for pinfo in params or []:
        name = (pinfo or {}).get("name") or ""
        if not name:
            continue
        desc_cn = backend.resolve_canonical_symbol_name(
            name,
            kind="symbols",
            comment_cn=(in_map or {}).get(name) or (out_map or {}).get(name) or (param_ai_name_map or {}).get(name) or "",
            fallback=name,
        )
        desc_cn = backend._shorten_element_display_name(desc_cn, fallback=name)
        if desc_cn and desc_cn != name:
            mapping[name] = desc_cn
    for item in local_vars or []:
        name = (item or {}).get("name") or ""
        if not name:
            continue
        preferred_cn = backend._preferred_local_cn_hint(item)
        cn = backend.resolve_canonical_symbol_name(
            name,
            kind="symbols",
            comment_cn=preferred_cn,
            fallback=((item or {}).get("usage") or name),
        )
        cn = backend._shorten_element_display_name(cn, fallback=name)
        if cn and cn != name:
            mapping[name] = cn
    # Disambiguate: 不同 C 变量映射到同一中文名时追加小写原始名后缀
    seen: dict[str, list[str]] = {}
    for c_name, cn_name in mapping.items():
        seen.setdefault(cn_name, []).append(c_name)
    for cn_name, c_names in seen.items():
        if len(c_names) <= 1:
            continue
        for c_name in c_names:
            compact = re.sub(r"^(?:[glsvp]_)?", "", c_name)
            compact = re.sub(r"_(?:u|i)(?:8|16|32|64)\b", "", compact, flags=re.IGNORECASE)
            compact = compact.strip("_")
            if compact.lower() == c_name.lower():
                compact = c_name[-6:]
            mapping[c_name] = f"{cn_name}({compact})"
    return mapping


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "LogicIR",
    "LogicNode",
    "_build_canonical_file_symbol_map",
    "_build_local_param_symbol_map",
    "_cleanup_generated_logic_text",
    "_format_call_expr",
    "_logic_cn_expr",
    "_map_func_ident",
    "_normalize_explanatory_text_for_output",
    "_normalize_logic_line_for_output",
    "_prettify_logic_ident",
    "_replace_idents_for_logic",
    "_replace_idents_for_logic_ex",
    "_replace_member_chain_with_owner",
    "_select_local_usage_text",
    "build_logic_ir",
    "expand_thin_logic",
    "fallback_logic_line",
    "generate_logic_from_body",
    "heuristic_logic_line",
    "render_logic_ir",
    "repair_generic_logic_calls",
    "repair_unresolved_logic_lines",
    "select_ai_logic_polish_unknowns",
    "_collect_unresolved_logic_symbols",
]


def _collect_unresolved_logic_symbols(
    logic_lines,
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> list[str]:
    """Scan logic lines for English identifiers not covered by name_map.

    Returns a list of unresolved symbol names (deduplicated, sorted).
    """
    backend = backend_module or legacy_backend()
    known = set(name_map or {})
    # C keywords and control-flow tokens that are expected in Chinese logic lines
    c_keywords = frozenset({
        "IF", "ELSE", "END", "WHILE", "FOR", "SWITCH", "CASE",
        "DEFAULT", "NEXT", "RETURN", "BREAK", "CONTINUE", "GOTO",
        "NULL", "TRUE", "FALSE", "void", "int", "char", "float",
        "double", "short", "long", "unsigned", "signed", "static",
        "const", "volatile", "extern", "register", "struct",
        "union", "enum", "typedef", "sizeof", "return", "if",
        "else", "while", "for", "switch", "case", "default",
        "break", "continue", "goto", "do",
    })
    ignored_patterns = (
        re.compile(r"^(?:FPGA|DSP|CPU|ACE|ACT|PMFL|STOF|VMC|GSE|CHV|PDE|MDR|PBIT|MBIT|PUBIT|IFBIT|WOW|LRU|NVM|PSV|CHID|PBIT|CVGE|DMA|MD1|EN|BIT)$"),
        re.compile(r"^[A-Z][A-Z0-9_]{0,2}$"),  # Very short acronym-like tokens
    )
    found: set[str] = set()
    ident_re = re.compile(r"\b([A-Za-z_]\w{2,})\b")
    for line in (logic_lines or ()):
        for m in ident_re.finditer(str(line or "")):
            ident = m.group(1)
            if ident in c_keywords:
                continue
            if ident in known:
                continue
            if any(pat.match(ident) for pat in ignored_patterns):
                continue
            if ident.startswith("l_") and len(ident) <= 8:
                continue  # local variable prefix pattern
            found.add(ident)
    return sorted(found)
