"""Evidence Model 数据结构。

所有 evidence 类型为 frozen dataclass，便于序列化和不可变传递。
``FunctionEvidence`` 是聚合根，一个函数对应一条。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Tuple


@dataclass(frozen=True)
class EvidenceSourceRange:
    """源码行号范围（1-indexed）。"""
    file: str = ""
    start_line: int = 0
    end_line: int = 0
    raw_snippet: str = ""


@dataclass(frozen=True)
class CommentEvidence:
    """注释证据：从 comment_normalizer / parse 提取的规范化注释字段。"""
    func_name: str = ""
    func_cn_name: str = ""
    description: str = ""
    input_desc: str = ""
    output_desc: str = ""
    other_desc: str = ""
    return_desc: str = ""
    has_comment: bool = False
    source: str = ""              # "block_comment" / "line_comment" / "none"
    confidence: float = 0.0


@dataclass(frozen=True)
class VariableEvidence:
    """变量证据：从 semantic 符号推断提取。"""
    ident: str = ""
    cn_name: str = ""
    decl_type: str = ""
    role: str = ""                # param / local / global
    direction: str = ""           # 输入/输出/输入输出（仅 param）
    confidence: float = 0.0
    evidence_kinds: int = 0
    source: str = ""             # symbol_dict / symbol_memory / comment / rule / ai
    usage_patterns: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpressionEvidence:
    """表达式证据：从 c_expr ExprIR 提取。"""
    raw_text: str = ""
    rendered_cn: str = ""
    ir_kind: str = ""            # binary / unary / call / raw_ref / identifier / literal / raw
    confidence: float = 0.0
    source: str = ""             # rule / raw / fallback / empty
    is_low8bit: bool = False
    is_checksum: bool = False


@dataclass(frozen=True)
class LogicStepEvidence:
    """逻辑步骤证据：从 logic_ir LogicStep 提取。"""
    step_kind: str = ""          # if / else_if / else / for / while / assignment / call / ...
    source_line: int = 0
    expression_text: str = ""
    scope_depth: int = 0
    confidence: float = 1.0
    fallback_reason: str = ""
    is_empty_else: bool = False
    is_declaration: bool = False
    attached_comments: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderedLineEvidence:
    """渲染行证据：从 logic.py 最终文本提取，关联到 LogicStep。"""
    line_index: int = 0
    rendered_text: str = ""
    indent_level: int = 0
    matched_step_kind: str = ""  # 对应的 LogicStep kind（若可关联）
    source: str = ""             # rule / ai / heuristic / fallback


@dataclass(frozen=True)
class LspFactEvidence:
    """LSP 事实证据摘要：从 lsp_facts FunctionFactPack 提取。"""
    available: bool = False
    degraded: bool = False
    clangd_version: str = ""
    block_count: int = 0
    call_count: int = 0
    member_count: int = 0
    local_count: int = 0
    quality_score: float = 0.0


@dataclass(frozen=True)
class FunctionEvidence:
    """函数级证据聚合根：一个函数对应一条。"""
    func_name: str = ""
    source_file: str = ""
    source_range: EvidenceSourceRange = field(default_factory=EvidenceSourceRange)
    prototype: str = ""
    ret_type: str = ""

    comment: CommentEvidence = field(default_factory=CommentEvidence)
    variables: Tuple[VariableEvidence, ...] = ()
    expressions: Tuple[ExpressionEvidence, ...] = ()
    logic_steps: Tuple[LogicStepEvidence, ...] = ()
    rendered_lines: Tuple[RenderedLineEvidence, ...] = ()
    lsp_facts: LspFactEvidence = field(default_factory=LspFactEvidence)

    # 质量标记
    has_empty_else: bool = False
    has_unknown_steps: bool = False
    has_low_confidence_vars: bool = False
    has_fallback_expressions: bool = False


@dataclass(frozen=True)
class QualitySummary:
    """Evidence-backed 质量摘要（供人工审查层显示）。"""
    func_name: str = ""
    total_steps: int = 0
    unknown_step_count: int = 0
    unknown_ratio: float = 0.0
    empty_else_count: int = 0
    variable_count: int = 0
    low_confidence_var_count: int = 0
    expression_count: int = 0
    fallback_expression_count: int = 0
    avg_step_confidence: float = 0.0
    avg_var_confidence: float = 0.0
    lsp_available: bool = False
    lsp_degraded: bool = False
    lsp_quality_score: float = 0.0
    comment_coverage: float = 0.0       # 有注释的变量比例
    quality_flags: Tuple[str, ...] = ()
    overall_score: float = 0.0          # 0-100 综合质量分
