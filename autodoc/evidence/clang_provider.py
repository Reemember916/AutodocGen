"""Clang Evidence Provider — shadow mode 旁路 clang/clangd 事实采集。

复用现有 compile_commands.json / lsp_facts / lsp_gateway 基础，
clang/clangd 先只产出旁路 facts，不影响生成。

采集内容
--------
- compile command health（compile_commands.json 可用性 + flags hash）
- symbol/type facts（从 FunctionFactPack 的 locals/members 提取）
- typedef pointer/type info（从 MemberFact.owner_type 提取，覆盖 FooState* 场景）
- definition/reference availability（从 CallFact.verified/definition 提取）
- 质量评分（复用 lsp_facts 的 _assess_lsp_quality 逻辑）

验收
----
- clang 不可用时自动降级（available=False），不影响生成
- clang 可用时输出 facts 和质量评分
- 能解释 FooState* state 这类 typedef pointer 场景
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from .models import LspFactEvidence, EvidenceSourceRange


@dataclass(frozen=True)
class CompileCommandHealth:
    """compile_commands.json 健康度。"""
    available: bool = False
    mode: str = ""               # existing / generated / missing
    entry_count: int = 0
    flags_hash: str = ""


@dataclass(frozen=True)
class TypedefPointerFact:
    """typedef pointer 事实：覆盖 FooState* state 场景。"""
    variable_name: str = ""
    decl_type: str = ""
    resolved_type: str = ""      # clangd typeDefinition 穿透后的底层类型
    owner_type: str = ""         # 从 typeDefinition targetUri 或 hover 提取
    has_definition: bool = False
    source: str = ""            # typeDefinition / hover / fallback


@dataclass(frozen=True)
class SymbolTypeFact:
    """符号类型事实。"""
    symbol: str = ""
    decl_type: str = ""
    source: str = ""            # hover / typeDefinition / fallback
    confidence: float = 0.0
    verified: bool = False


@dataclass(frozen=True)
class CallReferenceFact:
    """调用/引用可用性事实。"""
    callee: str = ""
    has_definition: bool = False
    definition_file: str = ""
    definition_line: int = 0
    has_references: bool = False
    source: str = ""            # callHierarchy / references / definition
    confidence: float = 0.0


@dataclass(frozen=True)
class ClangEvidence:
    """clang/clangd 旁路证据聚合。"""
    available: bool = False
    degraded: bool = False
    clangd_version: str = ""
    compile_health: CompileCommandHealth = field(default_factory=CompileCommandHealth)
    lsp_quality_score: float = 0.0

    typedef_pointer_facts: Tuple[TypedefPointerFact, ...] = ()
    symbol_type_facts: Tuple[SymbolTypeFact, ...] = ()
    call_reference_facts: Tuple[CallReferenceFact, ...] = ()

    # 统计
    block_count: int = 0
    call_count: int = 0
    member_count: int = 0
    local_count: int = 0

    # typedef pointer 覆盖率
    typedef_pointer_resolved_count: int = 0
    typedef_pointer_total_count: int = 0


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _collect_compile_health(fact_pack: Any) -> CompileCommandHealth:
    """从 FunctionFactPack.metadata 提取 compile command 健康度。"""
    if not fact_pack:
        return CompileCommandHealth()
    meta = getattr(fact_pack, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    return CompileCommandHealth(
        available=bool(meta.get("compile_db_mode") and meta.get("compile_db_mode") != "missing"),
        mode=_safe_str(meta.get("compile_db_mode")),
        entry_count=int(meta.get("compile_db_entry_count") or 0),
        flags_hash=_safe_str(meta.get("compile_flags_hash")),
    )


def _collect_typedef_pointer_facts(fact_pack: Any) -> list[TypedefPointerFact]:
    """从 MemberFact 提取 typedef pointer 事实。

    覆盖 FooState* state → a->b 场景：clangd typeDefinition 穿透 typedef
    和指针找到底层 struct，owner_type 即为穿透结果。
    """
    if not fact_pack:
        return []
    members = getattr(fact_pack, "members", None) or []
    out: list[TypedefPointerFact] = []
    for m in members:
        base = _safe_str(getattr(m, "base", "")) or _safe_str(getattr(m, "member", ""))
        if not base:
            continue
        owner_type = _safe_str(getattr(m, "owner_type", ""))
        access_text = _safe_str(getattr(m, "access_text", ""))
        source = _safe_str(getattr(m, "source", ""))
        # owner_type 非空说明 clangd typeDefinition 成功穿透
        has_def = bool(owner_type)
        resolved = owner_type if has_def else ""
        # 判断是否是指针型访问（access_text 含 ->）
        is_pointer = "->" in access_text
        out.append(TypedefPointerFact(
            variable_name=base,
            decl_type=_safe_str(getattr(m, "decl_type", "")),
            resolved_type=resolved,
            owner_type=owner_type,
            has_definition=has_def,
            source=source if source else ("typeDefinition" if has_def else "hover"),
        ))
    # 去重（同 base 只保留置信最高的）
    seen: dict[str, TypedefPointerFact] = {}
    for f in out:
        if f.variable_name not in seen or (f.has_definition and not seen[f.variable_name].has_definition):
            seen[f.variable_name] = f
    return list(seen.values())


def _collect_symbol_type_facts(fact_pack: Any) -> list[SymbolTypeFact]:
    """从 LocalFact 提取符号类型事实。"""
    if not fact_pack:
        return []
    out: list[SymbolTypeFact] = []
    locals_ = getattr(fact_pack, "locals", None) or []
    for lf in locals_:
        name = _safe_str(getattr(lf, "name", ""))
        if not name:
            continue
        decl_type = _safe_str(getattr(lf, "decl_type", ""))
        source = _safe_str(getattr(lf, "source", ""))
        confidence = float(getattr(lf, "confidence", 0.0) or 0.0)
        verified = bool(getattr(lf, "verified", False))
        out.append(SymbolTypeFact(
            symbol=name,
            decl_type=decl_type,
            source=source or ("hover" if confidence > 0.75 else "fallback"),
            confidence=confidence,
            verified=verified,
        ))
    return out


def _collect_call_reference_facts(fact_pack: Any) -> list[CallReferenceFact]:
    """从 CallFact 提取调用/引用可用性事实。"""
    if not fact_pack:
        return []
    out: list[CallReferenceFact] = []
    calls = getattr(fact_pack, "calls", None) or []
    for c in calls:
        callee = _safe_str(getattr(c, "callee", ""))
        if not callee:
            continue
        def_file = _safe_str(getattr(c, "definition_file", ""))
        def_line = int(getattr(c, "definition_line", 0) or 0)
        has_def = bool(def_file or getattr(c, "definition", None))
        has_refs = bool(getattr(c, "has_references", False) or getattr(c, "references", None))
        source = _safe_str(getattr(c, "source", ""))
        confidence = float(getattr(c, "confidence", 0.0) or 0.0)
        out.append(CallReferenceFact(
            callee=callee,
            has_definition=has_def,
            definition_file=def_file,
            definition_line=def_line,
            has_references=has_refs,
            source=source,
            confidence=confidence,
        ))
    return out


def collect_clang_evidence(
    fact_pack: Any = None,
    *,
    compile_health: Optional[CompileCommandHealth] = None,
) -> ClangEvidence:
    """采集 clang/clangd 旁路证据（shadow mode）。

    参数
    -----
    fact_pack : lsp_facts.FunctionFactPack（可为 None，表示 clang 不可用）
    compile_health : 可选的 CompileCommandHealth（从 compile_db 获取）

    返回
    -----
    ClangEvidence 聚合
    """
    if not fact_pack:
        return ClangEvidence(
            available=False,
            degraded=True,
            compile_health=compile_health or CompileCommandHealth(),
        )

    meta = getattr(fact_pack, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    degraded = bool(meta.get("lsp_degraded", False))
    clangd_version = _safe_str(meta.get("clangd_version"))

    blocks = getattr(fact_pack, "blocks", None) or ()
    calls = getattr(fact_pack, "calls", None) or ()
    members = getattr(fact_pack, "members", None) or ()
    locals_ = getattr(fact_pack, "locals", None) or ()

    # 质量评分（复用 lsp_facts 的评估逻辑）
    q = 0.5
    if blocks:
        q += 0.15
    if calls:
        q += 0.15
    if members:
        q += 0.10
    if locals_:
        q += 0.10
    q = min(1.0, round(q, 2))

    typedef_facts = _collect_typedef_pointer_facts(fact_pack)
    symbol_facts = _collect_symbol_type_facts(fact_pack)
    call_facts = _collect_call_reference_facts(fact_pack)

    typedef_resolved = sum(1 for f in typedef_facts if f.has_definition)
    typedef_total = len(typedef_facts)

    return ClangEvidence(
        available=not degraded,
        degraded=degraded,
        clangd_version=clangd_version,
        compile_health=compile_health or _collect_compile_health(fact_pack),
        lsp_quality_score=q,
        typedef_pointer_facts=tuple(typedef_facts),
        symbol_type_facts=tuple(symbol_facts),
        call_reference_facts=tuple(call_facts),
        block_count=len(blocks),
        call_count=len(calls),
        member_count=len(members),
        local_count=len(locals_),
        typedef_pointer_resolved_count=typedef_resolved,
        typedef_pointer_total_count=typedef_total,
    )


def to_lsp_fact_evidence(ce: ClangEvidence) -> LspFactEvidence:
    """将 ClangEvidence 转换为简化的 LspFactEvidence（向后兼容 evidence/collector.py）。"""
    return LspFactEvidence(
        available=ce.available,
        degraded=ce.degraded,
        clangd_version=ce.clangd_version,
        block_count=ce.block_count,
        call_count=ce.call_count,
        member_count=ce.member_count,
        local_count=ce.local_count,
        quality_score=ce.lsp_quality_score,
    )


__all__ = [
    "CompileCommandHealth",
    "TypedefPointerFact",
    "SymbolTypeFact",
    "CallReferenceFact",
    "ClangEvidence",
    "collect_clang_evidence",
    "to_lsp_fact_evidence",
]
