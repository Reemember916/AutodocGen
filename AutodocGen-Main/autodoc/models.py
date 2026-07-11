from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional


@dataclass
class AppConfig:
    section_prefix: str = ""
    req_id_prefix: str = ""
    project_root: str = ""
    template_path: str = ""
    include_locals: bool = True
    include_logic: bool = True
    include_flowchart: bool = True
    ai_assist: bool = False
    ai_mode: int = 0
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AiConfig:
    provider: str = ""
    model: str = ""
    api_key: str = ""
    api_url: str = ""
    temperature: float = 0.0
    profile: str = ""
    naming_authority: str = "ai_first"


@dataclass
class UiHooks:
    log: Optional[Callable[..., None]] = None
    event: Optional[Callable[[dict[str, Any]], None]] = None
    stop_requested: Optional[Callable[[], bool]] = None


@dataclass
class RuntimeState:
    project_root: str = ""
    symbol_memory_path: str = ""
    title_index_path: str = ""
    symbol_index_path: str = ""
    semantic_index_path: str = ""
    naming_index_refresh: str = "auto"
    semantic_provider: str = "structured"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationOptions:
    only_with_comment: bool = False
    open_after_done: bool = False
    prefilter_project_files: bool = True
    project_file_order: Optional[dict[str, list[Any]]] = None
    symbol_dict_overrides: Optional[dict[str, str]] = None
    resume_state: dict[str, Any] = field(default_factory=dict)
    continuing: bool = False


@dataclass
class SingleFileResumeState:
    func_pos: int = 1
    func_index: int = 1


@dataclass
class ProjectResumeState:
    layer_index: int = 0
    file_index: int = 0
    func_pos: int = 1
    func_index: int = 1
    module_counter: int = 1
    layer_started: bool = False
    module_started: bool = False
    module_id: Optional[str] = None
    module_files: list[str] = field(default_factory=list)
    file: str = ""
    func_name: str = ""


@dataclass
class RuntimeContext:
    app: AppConfig
    ai: AiConfig
    runtime: RuntimeState
    ui: UiHooks
    generation: GenerationOptions = field(default_factory=GenerationOptions)
    legacy_cfg: Any = None


@dataclass
class FileContext:
    source_file: str = ""
    module_key: str = ""
    family_prefix: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    func_cn_map: dict[str, str] = field(default_factory=dict)
    symbol_map: dict[str, str] = field(default_factory=dict)
    member_symbol_map: dict[str, str] = field(default_factory=dict)
    variable_type_map: dict[str, str] = field(default_factory=dict)
    typedefs: list[str] = field(default_factory=list)
    header_typedefs: list[str] = field(default_factory=list)
    macros: list[str] = field(default_factory=list)
    neighbor_prototypes: list[str] = field(default_factory=list)
    neighbor_func_names: list[str] = field(default_factory=list)
    callee_funcs: list[str] = field(default_factory=list)
    caller_funcs: list[str] = field(default_factory=list)
    codegraph_status: dict[str, Any] = field(default_factory=dict)
    codegraph_node: dict[str, Any] = field(default_factory=dict)
    codegraph_callers: list[dict[str, Any]] = field(default_factory=list)
    codegraph_callees: list[dict[str, Any]] = field(default_factory=list)
    codegraph_impact: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FunctionContext:
    func_name: str = ""
    prototype: str = ""
    ret_type: str = ""
    comment_info: dict[str, Any] = field(default_factory=dict)
    file_context: FileContext = field(default_factory=FileContext)
    body: str = ""


@dataclass
class SemanticPack:
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class NamingRequest:
    kind: str = ""
    ident: str = ""
    decl_type: str = ""
    role: str = ""
    module_key: str = ""
    family_prefix: str = ""
    usage_examples: list[str] = field(default_factory=list)
    retrieved_examples: list[dict[str, Any]] = field(default_factory=list)
    canonical_name: str = ""
    semantic_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class NamingCandidate:
    text: str = ""
    usage: str = ""
    confidence: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogicNode:
    kind: str = ""
    text: str = ""
    condition: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogicIR:
    nodes: list[LogicNode] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    state_effects: list[str] = field(default_factory=list)


@dataclass
class SourceRange:
    start_line: int = 0
    end_line: int = 0
    start_col: int = 0
    end_col: int = 0


@dataclass
class FactItem:
    source: str = ""
    confidence: float = 0.0
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FunctionFact:
    name: str = ""
    signature: str = ""
    range: SourceRange = field(default_factory=SourceRange)
    source: str = ""
    confidence: float = 0.0
    verified: bool = False


@dataclass
class BlockFact(FactItem):
    id: str = ""
    kind: str = ""
    parent: str = ""
    condition: str = ""
    range: SourceRange = field(default_factory=SourceRange)


@dataclass
class LocalFact(FactItem):
    name: str = ""
    decl_type: str = ""
    scope: str = "local"
    decl_range: SourceRange = field(default_factory=SourceRange)


@dataclass
class CallFact(FactItem):
    callee: str = ""
    call_text: str = ""
    signature: str = ""
    definition_file: str = ""
    definition_line: int = 0
    definition_comment: str = ""
    range: SourceRange = field(default_factory=SourceRange)


@dataclass
class MemberFact(FactItem):
    base: str = ""
    member: str = ""
    owner_type: str = ""
    access_text: str = ""


@dataclass
class AccessFact(FactItem):
    expr: str = ""
    kind: str = ""
    lhs: str = ""
    rhs: str = ""
    range: SourceRange = field(default_factory=SourceRange)


@dataclass
class FunctionFactPack:
    function: FunctionFact = field(default_factory=FunctionFact)
    blocks: list[BlockFact] = field(default_factory=list)
    locals: list[LocalFact] = field(default_factory=list)
    calls: list[CallFact] = field(default_factory=list)
    members: list[MemberFact] = field(default_factory=list)
    reads: list[AccessFact] = field(default_factory=list)
    writes: list[AccessFact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommentHint:
    kind: Literal["action", "condition", "purpose", "constraint", "history", "debug", "noise"]
    text: str
    confidence: float = 0.0


@dataclass(frozen=True)
class SymbolEvidence:
    symbol: str
    kind: str
    decl_type: str = ""
    owner_type: str = ""
    usage_patterns: tuple[str, ...] = ()
    consumer_patterns: tuple[str, ...] = ()
    sink_patterns: tuple[str, ...] = ()
    dataflow_roles: tuple[str, ...] = ()
    neighbor_symbols: tuple[str, ...] = ()
    paired_symbols: tuple[str, ...] = ()
    source_comment_hints: tuple[str, ...] = ()
    normalized_comment_hint: str = ""
    producer_kind: str = ""
    producer_call: str = ""
    producer_args: tuple[str, ...] = ()
    producer_arg_tags: tuple[str, ...] = ()
    preferred_cn: str = ""
    memory_cn: str = ""


@dataclass(frozen=True)
class SymbolInference:
    symbol: str
    kind: str
    candidate_cn: str = ""
    role: str = ""
    confidence: float = 0.0
    evidence_kinds: int = 0
    persist_scope: str = "off"
    reason: str = ""


@dataclass(frozen=True)
class IOElement:
    name: str
    ident: str
    c_type: str
    direction: Literal["输入", "输出", "输入/输出"]


@dataclass(frozen=True)
class LocalDataElement:
    name: str
    ident: str
    c_type: str
    usage: str


@dataclass(frozen=True)
class FunctionDesign:
    title: str
    req_id: str
    prototype: str
    description_lines: tuple[str, ...]
    io_elements: tuple[IOElement, ...]
    io_none: bool
    local_elements: Optional[tuple[LocalDataElement, ...]]
    logic_lines: Optional[tuple[str, ...]]
    ai_meta: Any = None


@dataclass
class DesignModel:
    func_name: str = ""
    func_cn_name: str = ""
    desc: str = ""
    params: list[dict[str, Any]] = field(default_factory=list)
    locals: list[dict[str, Any]] = field(default_factory=list)
    logic_steps: list[str] = field(default_factory=list)
    file_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class FunctionBuildResult:
    task: dict[str, Any] = field(default_factory=dict)
    design: Any = None
    error: Optional[Exception] = None


@dataclass
class FunctionFailureRecord:
    """函数失败记录，用于 GUI 错误报告。"""

    func_name: str = ""
    file_path: str = ""
    line_start: int = 0
    error_type: str = ""  # ai_timeout, ai_parse_error, network_error, unknown
    error_message: str = ""
    task: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "func_name": self.func_name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "task": self.task,
        }

    @classmethod
    def from_exception(cls, task: dict, exc: Exception) -> "FunctionFailureRecord":
        """从异常创建失败记录。"""
        func_name = task.get("func_name", "") or task.get("func_data", {}).get("func_name", "")
        file_path = task.get("source_file", "") or task.get("file", "")
        line_start = int(task.get("line_start", 0) or 0)

        # 分类错误类型
        error_type = "unknown"
        error_message = str(exc)
        exc_str = str(type(exc).__name__).lower()

        if "timeout" in error_message.lower() or "timeout" in exc_str:
            error_type = "ai_timeout"
        elif "json" in error_message.lower() or "parse" in error_message.lower():
            error_type = "ai_parse_error"
        elif "network" in error_message.lower() or "connection" in error_message.lower():
            error_type = "network_error"
        elif "ai" in error_message.lower():
            error_type = "ai_error"

        return cls(
            func_name=func_name,
            file_path=file_path,
            line_start=line_start,
            error_type=error_type,
            error_message=error_message[:200],  # 截断过长的错误信息
            task=dict(task),
        )


@dataclass(frozen=True)
class AIBuildMeta:
    ai_enabled: bool = False
    ai_failed: bool = False
    regression_needed: bool = False
    regression_round: int = 0
    regression_reasons: tuple[str, ...] = ()
    logic_placeholders: int = 0
    unresolved_local_symbols: tuple[str, ...] = ()
    unresolved_param_symbols: tuple[str, ...] = ()
    unresolved_logic_symbols: tuple[str, ...] = ()
    generic_logic_count: int = 0
    comment_leak_count: int = 0
    term_drift_count: int = 0
    over_translation_count: int = 0
    bad_symbol_guess_count: int = 0
    raw_func_title: str = ""
    pre_rerank_func_title: str = ""
    title_candidates: tuple[str, ...] = ()
    title_pattern: str = ""
    title_rerank_changed: bool = False
    title_fallback_used: bool = False
    title_model_confidence: float = 0.0
    title_retry_used: bool = False
    title_stage_debug: tuple[dict[str, Any], ...] = ()
    logic_source_audit: tuple[dict[str, Any], ...] = ()
    quality_issues: tuple[dict[str, Any], ...] = ()
    lsp_fact_snapshot: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AIBuildMeta",
    "AiConfig",
    "AppConfig",
    "CommentHint",
    "DesignModel",
    "FileContext",
    "FunctionBuildResult",
    "FunctionDesign",
    "FunctionContext",
    "FunctionFailureRecord",
    "GenerationOptions",
    "IOElement",
    "LocalDataElement",
    "LogicIR",
    "LogicNode",
    "NamingCandidate",
    "NamingRequest",
    "ProjectResumeState",
    "RuntimeContext",
    "RuntimeState",
    "SemanticPack",
    "SingleFileResumeState",
    "SymbolEvidence",
    "SymbolInference",
    "UiHooks",
]
