"""Evidence 旁路采集器。

从 LogicStep + parse 产出的 func_data + 可选 LSP facts 采集 evidence，
生成 evidence-backed 质量摘要。不改变 docx 输出（shadow mode）。
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from .models import (
    EvidenceSourceRange,
    CommentEvidence,
    VariableEvidence,
    ExpressionEvidence,
    LogicStepEvidence,
    RenderedLineEvidence,
    LspFactEvidence,
    FunctionEvidence,
    QualitySummary,
)


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def collect_comment_evidence(func_data: dict) -> CommentEvidence:
    """从 func_data 的 comment_info 提取注释证据。"""
    ci = func_data.get("comment_info") or {}
    # 只检查内容字段（不含 func_name/func_cn_name，它们只是标识符）
    content_keys = ("desc", "input_desc", "output_desc", "other_desc", "return_desc")
    has = bool(ci and any(_safe_str(ci.get(k)) for k in content_keys))
    source = "block_comment" if has else "none"
    return CommentEvidence(
        func_name=_safe_str(ci.get("func_name")),
        func_cn_name=_safe_str(ci.get("func_cn_name")),
        description=_safe_str(ci.get("desc")),
        input_desc=_safe_str(ci.get("input_desc")),
        output_desc=_safe_str(ci.get("output_desc")),
        other_desc=_safe_str(ci.get("other_desc")),
        return_desc=_safe_str(ci.get("return_desc")),
        has_comment=has,
        source=source,
        confidence=0.85 if has else 0.0,
    )


def collect_variable_evidence(func_data: dict, name_map: Optional[dict] = None) -> list[VariableEvidence]:
    """从 func_data 的参数/局部变量提取变量证据。"""
    out: list[VariableEvidence] = []
    name_map = name_map or {}
    file_ctx = func_data.get("file_context") or {}
    symbol_map = file_ctx.get("symbol_map") or {}

    # 参数
    for p in func_data.get("params") or []:
        ident = _safe_str(p.get("ident") or p.get("name"))
        if not ident:
            continue
        cn = _safe_str(p.get("cn_name")) or _safe_str(name_map.get(ident)) or _safe_str(symbol_map.get(ident))
        direction = _safe_str(p.get("direction"))
        out.append(VariableEvidence(
            ident=ident,
            cn_name=cn,
            decl_type=_safe_str(p.get("c_type") or p.get("type")),
            role="param",
            direction=direction,
            confidence=0.8 if cn else 0.3,
            source="symbol_dict" if cn else "rule",
        ))

    # 局部变量
    for lv in func_data.get("local_vars") or []:
        ident = _safe_str(lv.get("ident") or lv.get("name"))
        if not ident:
            continue
        cn = _safe_str(lv.get("cn_name")) or _safe_str(name_map.get(ident)) or _safe_str(symbol_map.get(ident))
        out.append(VariableEvidence(
            ident=ident,
            cn_name=cn,
            decl_type=_safe_str(lv.get("c_type") or lv.get("decl_type") or lv.get("type")),
            role="local",
            confidence=0.7 if cn else 0.2,
            source="symbol_dict" if cn else "rule",
            usage_patterns=tuple(_safe_str(lv.get("usage")).split(";")) if lv.get("usage") else (),
        ))

    return out


def collect_expression_evidence(logic_steps: Sequence) -> list[ExpressionEvidence]:
    """从 LogicStep 序列提取表达式证据（尝试用 c_expr 渲染）。"""
    out: list[ExpressionEvidence] = []
    try:
        from ..c_expr import parse_c_expression, render_expr_cn
    except Exception:
        parse_c_expression = None
        render_expr_cn = None

    for step in logic_steps:
        expr = getattr(step, "expression_text", "") or getattr(step, "condition", "") or ""
        if not expr:
            continue
        rendered = ""
        ir_kind = ""
        confidence = 0.5
        source = "raw"
        is_low8 = False
        is_checksum = False

        if render_expr_cn and parse_c_expression:
            try:
                ir = parse_c_expression(expr)
                if ir:
                    ir_kind = ir.kind
                    r = render_expr_cn(ir, name_map={})
                    if r and r.text:
                        rendered = r.text
                        confidence = r.confidence
                        source = r.source
                        is_low8 = "低8位" in rendered
                        is_checksum = "补码校验和" in rendered
            except Exception:
                pass

        out.append(ExpressionEvidence(
            raw_text=expr,
            rendered_cn=rendered,
            ir_kind=ir_kind,
            confidence=confidence,
            source=source,
            is_low8bit=is_low8,
            is_checksum=is_checksum,
        ))
    return out


def collect_logic_step_evidence(logic_steps: Sequence) -> list[LogicStepEvidence]:
    """从 LogicStep 序列提取逻辑步骤证据。"""
    out: list[LogicStepEvidence] = []
    for step in logic_steps:
        sr = getattr(step, "source_range", None)
        out.append(LogicStepEvidence(
            step_kind=getattr(step, "kind", "unknown"),
            source_line=getattr(sr, "start_line", 0) if sr else 0,
            expression_text=getattr(step, "expression_text", ""),
            scope_depth=getattr(step, "scope_depth", 0),
            confidence=getattr(step, "confidence", 1.0),
            fallback_reason=getattr(step, "fallback_reason", ""),
            is_empty_else=getattr(step, "is_empty", False) if hasattr(step, "is_empty") else False,
            is_declaration=getattr(step, "is_declaration", False) if hasattr(step, "is_declaration") else False,
            attached_comments=getattr(step, "attached_comments", ()),
        ))
    return out


def collect_lsp_fact_evidence(fact_pack: Any) -> LspFactEvidence:
    """从 FunctionFactPack 提取 LSP 事实证据摘要。"""
    if not fact_pack:
        return LspFactEvidence()
    meta = getattr(fact_pack, "metadata", None) or {}
    if isinstance(meta, dict):
        pass
    else:
        meta = {}
    blocks = getattr(fact_pack, "blocks", None) or ()
    calls = getattr(fact_pack, "calls", None) or ()
    members = getattr(fact_pack, "members", None) or ()
    locals_ = getattr(fact_pack, "locals", None) or ()

    # 质量分估算
    q = 0.5
    if blocks: q += 0.15
    if calls: q += 0.15
    if members: q += 0.10
    if locals_: q += 0.10
    q = min(1.0, q)

    return LspFactEvidence(
        available=True,
        degraded=bool(meta.get("lsp_degraded", False)),
        clangd_version=_safe_str(meta.get("clangd_version")),
        block_count=len(blocks),
        call_count=len(calls),
        member_count=len(members),
        local_count=len(locals_),
        quality_score=round(q, 2),
    )


def collect_function_evidence(
    func_data: dict,
    logic_steps: Sequence,
    name_map: Optional[dict] = None,
    *,
    lsp_fact_pack: Any = None,
) -> FunctionEvidence:
    """采集函数级证据（shadow mode 旁路）。

    参数
    -----
    func_data : parse.prepare_func_list_for_c_file 产出的单函数数据
    logic_steps : logic_ir.build_logic_steps 产出的 LogicStep 序列
    name_map : 标识符→中文名映射
    lsp_fact_pack : 可选的 lsp_facts.FunctionFactPack

    返回
    -----
    FunctionEvidence 聚合根
    """
    func_info = func_data.get("func_info") or {}
    file_ctx = func_data.get("file_context") or {}
    source_file = _safe_str(file_ctx.get("source_file"))

    fi_range = func_info.get("start", 0) or 0
    fi_end = func_info.get("end", 0) or 0

    comment_ev = collect_comment_evidence(func_data)
    var_evs = collect_variable_evidence(func_data, name_map)
    expr_evs = collect_expression_evidence(logic_steps)
    step_evs = collect_logic_step_evidence(logic_steps)
    lsp_ev = collect_lsp_fact_evidence(lsp_fact_pack)

    has_empty_else = any(s.is_empty_else for s in step_evs)
    has_unknown = any(s.step_kind == "unknown" for s in step_evs)
    has_low_conf_vars = any(v.confidence < 0.5 for v in var_evs)
    has_fallback_expr = any(e.source in ("raw", "fallback", "empty") for e in expr_evs)

    return FunctionEvidence(
        func_name=_safe_str(func_info.get("func_name")),
        source_file=source_file,
        source_range=EvidenceSourceRange(
            file=source_file,
            start_line=fi_range,
            end_line=fi_end,
        ),
        prototype=_safe_str(func_info.get("prototype")),
        ret_type=_safe_str(func_info.get("ret_type")),
        comment=comment_ev,
        variables=tuple(var_evs),
        expressions=tuple(expr_evs),
        logic_steps=tuple(step_evs),
        lsp_facts=lsp_ev,
        has_empty_else=has_empty_else,
        has_unknown_steps=has_unknown,
        has_low_confidence_vars=has_low_conf_vars,
        has_fallback_expressions=has_fallback_expr,
    )


def build_quality_summary(ev: FunctionEvidence) -> QualitySummary:
    """从 FunctionEvidence 生成 evidence-backed 质量摘要。"""
    total_steps = len(ev.logic_steps)
    unknown_count = sum(1 for s in ev.logic_steps if s.step_kind == "unknown")
    empty_else_count = sum(1 for s in ev.logic_steps if s.is_empty_else)

    var_count = len(ev.variables)
    low_conf_var_count = sum(1 for v in ev.variables if v.confidence < 0.5)

    expr_count = len(ev.expressions)
    fallback_expr_count = sum(1 for e in ev.expressions if e.source in ("raw", "fallback", "empty"))

    avg_step_conf = 0.0
    if total_steps > 0:
        avg_step_conf = round(sum(s.confidence for s in ev.logic_steps) / total_steps, 3)

    avg_var_conf = 0.0
    if var_count > 0:
        avg_var_conf = round(sum(v.confidence for v in ev.variables) / var_count, 3)

    comment_coverage = 0.0
    if var_count > 0:
        with_comment = sum(1 for v in ev.variables if v.cn_name)
        comment_coverage = round(with_comment / var_count, 3)

    flags = []
    if unknown_count > 0:
        flags.append("has_unknown_steps")
    if empty_else_count > 0:
        flags.append("has_empty_else")
    if low_conf_var_count > 0:
        flags.append("low_confidence_variables")
    if fallback_expr_count > 0:
        flags.append("fallback_expressions")
    if ev.lsp_facts.degraded:
        flags.append("lsp_degraded")
    if not ev.comment.has_comment:
        flags.append("missing_comment")

    # 综合质量分（0-100）
    score = 100.0
    if total_steps > 0:
        score -= (unknown_count / total_steps) * 30        # 未知步骤最多扣 30
    score -= empty_else_count * 2                            # 空 ELSE 每个扣 2
    if var_count > 0:
        score -= (low_conf_var_count / var_count) * 20      # 低置信变量最多扣 20
    if expr_count > 0:
        score -= (fallback_expr_count / expr_count) * 15   # fallback 表达式最多扣 15
    if not ev.comment.has_comment:
        score -= 10                                           # 缺注释扣 10
    if ev.lsp_facts.available and ev.lsp_facts.degraded:
        score -= 5                                           # LSP 降级扣 5
    score = max(0.0, min(100.0, round(score, 1)))

    return QualitySummary(
        func_name=ev.func_name,
        total_steps=total_steps,
        unknown_step_count=unknown_count,
        unknown_ratio=round(unknown_count / total_steps, 3) if total_steps > 0 else 0.0,
        empty_else_count=empty_else_count,
        variable_count=var_count,
        low_confidence_var_count=low_conf_var_count,
        expression_count=expr_count,
        fallback_expression_count=fallback_expr_count,
        avg_step_confidence=avg_step_conf,
        avg_var_confidence=avg_var_conf,
        lsp_available=ev.lsp_facts.available,
        lsp_degraded=ev.lsp_facts.degraded,
        lsp_quality_score=ev.lsp_facts.quality_score,
        comment_coverage=comment_coverage,
        quality_flags=tuple(flags),
        overall_score=score,
    )
