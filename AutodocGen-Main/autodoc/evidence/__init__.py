"""Evidence Model — shadow mode 旁路证据采集包。

本包为 TODO P0#2 的实现：不改变 docx 输出，旁路生成机器可用 evidence。
人工审查层默认只显示质量摘要，不暴露 AST/IR/clang 细节。

模块
----
- ``models``: 数据结构（SourceRange / FunctionEvidence / CommentEvidence /
  VariableEvidence / ExpressionEvidence / LogicStepEvidence / RenderedLineEvidence）
- ``collector``: 旁路采集器，从 LogicStep + parse/semantic/lsp_facts 采集 evidence，
  生成 evidence-backed 质量摘要
"""

from __future__ import annotations

from .models import (
    EvidenceSourceRange,
    CommentEvidence,
    VariableEvidence,
    ExpressionEvidence,
    LogicStepEvidence,
    RenderedLineEvidence,
    FunctionEvidence,
    QualitySummary,
)
from .collector import (
    collect_function_evidence,
    build_quality_summary,
    record_function_evidence,
    get_recorded_evidence,
    clear_recorded_evidence,
    write_evidence_report,
)
from .clang_provider import (
    CompileCommandHealth,
    TypedefPointerFact,
    SymbolTypeFact,
    CallReferenceFact,
    ClangEvidence,
    collect_clang_evidence,
    to_lsp_fact_evidence,
)

__all__ = [
    "EvidenceSourceRange",
    "CommentEvidence",
    "VariableEvidence",
    "ExpressionEvidence",
    "LogicStepEvidence",
    "RenderedLineEvidence",
    "FunctionEvidence",
    "QualitySummary",
    "collect_function_evidence",
    "build_quality_summary",
    "CompileCommandHealth",
    "TypedefPointerFact",
    "SymbolTypeFact",
    "CallReferenceFact",
    "ClangEvidence",
    "collect_clang_evidence",
    "to_lsp_fact_evidence",
    "record_function_evidence",
    "get_recorded_evidence",
    "clear_recorded_evidence",
    "write_evidence_report",
]
