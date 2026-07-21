"""Configuration classes and exceptions for AutoDocGen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


# =============== 异常类 ===============

class ToolError(Exception):
    """工具的基类异常（用于 UI/CLI 分层处理）。"""


class NoDataError(ToolError):
    """输入合法，但没有可生成的数据（例如未解析到任何函数）。"""


class SourceReadError(ToolError):
    """源文件读取失败（找不到/编码无法识别等）。"""


class ParseError(ToolError):
    """解析失败（输入存在，但结构不符合预期或内部解析错误）。"""


class RenderError(ToolError):
    """Word 渲染失败（docx 生成/保存失败等）。"""


class SkipFunctionError(ToolError):
    """AI 失败策略：跳过当前函数。"""


# =============== 配置类 ===============

@dataclass
class GenConfig:
    """设计文档生成配置。"""

    # ---------------- 设计文档生成 ----------------
    section_prefix: str = "5.1.1."
    req_id_prefix: str = "D/R_SDD01_"
    only_with_comment: bool = False
    include_locals: bool = True
    include_logic: bool = True
    # 逻辑语句是否使用注释（关闭则仅按名称映射直译）
    logic_use_comment: bool = True
    logic_comment_mode: str = "hint_only"
    open_after_done: bool = False

    # ---------------- AI 总开关 ----------------
    ai_assist: bool = False
    ai_provider: str = "local"           # local(如 Ollama) / openrouter
    ai_model: str = "DeepseekR1:32b"
    ai_profile: str = ""
    ai_temperature: float = 0.1
    ai_top_p: float = 0.5
    ai_max_tokens: int = 32800
    ai_num_ctx: int = 0                 # Ollama /v1/chat/completions: options.num_ctx（0=不传）
    ai_read_timeout: float = 40.0       # 本地/兼容接口读取超时（秒）

    # API / KEY
    ai_api_base: str = "10.11.34.200:11434/v1"  # 本地模型 base URL
    ai_api_key: str = ""                 # GUI 输入 KEY
    ai_use_auth: bool = True             # 本地模型是否需要 Bearer Token
    wire_api: str = "chat_completions"   # chat_completions（标准 OpenAI）/ responses（OpenAI Responses API）
    # AI 模式。公开入口只暴露二元开关：
    # 0 = 无 AI
    # 1 = 开启 AI（事实由规则/LSP/AST 约束，AI 只做受控表达增强）
    # 历史非零模式由 GUI/工具入口统一折叠为 1。
    ai_mode: int = 1
    # AI 上下文范围：target_only 默认只允许目标函数 AI 辅助；local_neighbors/project 需显式开启。
    ai_context_scope: str = "target_only"

    # ---------------- AI 置信度阈值（旧逻辑依赖这些字段） ----------------
    ai_conf_param: float = 0.7           # 输入/输出参数描述
    ai_conf_local: float = 0.1          # 局部变量用途/中文名
    ai_conf_logic: float = 0.6           # 逻辑图中"待人工修改"补全
    ai_conf_func: float = 0.7            # 函数中文名 / 功能说明
    ai_conf_symbol: float = 0.5          # ★ 新增：逻辑条件中的符号说明置信度（你旧逻辑需要的）
    symbol_infer_enabled: bool = True
    symbol_infer_min_conf: float = 0.82
    symbol_infer_min_evidence_kinds: int = 2
    symbol_infer_scope: str = "graded"

    # ---------------- AI 模式控制 ----------------
    force_ai: bool = False               # 忽略置信度直接采用返回
    review_mode: bool = False        # 是否在 AI 填写内容后加"(AI)"
    ai_circuit_break: bool = False       # 是否因为错误而停止后续 AI 调用
    no_proxy: bool = False               # 禁用代理环境变量

    # ★ 新增：HTTP 代理（如 127.0.0.1:7890）
    proxy: str = ""

    # ★ 逻辑流程图 AI 输出格式（json）
    # json：使用 call_llm_json，返回 {"0": "...", "1": "..."} 形式
    ai_logic_format: str = "json"

    # 逻辑/流程图生成策略：默认使用 hybrid，优先采用可证明的结构化事实。
    ai_logic_policy: str = "hybrid"

    # 历史兼容字段：公开 GUI/质量检查入口固定关闭，避免 AI 策略分叉。
    ai_one_call: bool = False
    # 本地模型下，超大函数自动禁用 one-call 并回退多次 AI 调用
    auto_disable_large_one_call: bool = True
    # 开启 AI 后的函数级并发数（1=串行）
    ai_workers: int = 1
    # ---------------- 日志与 GUI ----------------
    verbose: bool = False
    gui_log: Optional[Callable[[str], None]] = None
    gui_event: Optional[Callable[[dict], None]] = None  # GUI 事件（步骤/函数/AI 细节）
    stop_event: Optional["threading.Event"] = None  # GUI 停止信号
    template_path: str = ""                # 可选：详细设计模板 docx 路径
    log_every_n: int = 5                   # verbose 日志采样：每 N 个函数打印一次

    # ---------------- 工程扫描（CCS/Eclipse 目录习惯） ----------------
    # 这些目录通常是 IDE/构建产物，既不需要生成文档，也会影响头文件索引与扫描速度。
    exclude_dirs: tuple[str, ...] = (
        ".git",
        ".settings",
        ".launches",
        "debug",
        "release",
        "__pycache__",
    )
    # 工程分层规则：目录关键词（相对 src 的路径中包含该关键词 → 归入对应层；大小写不敏感）
    mid_dir_keywords: tuple[str, ...] = ("common",)
    drv_dir_keywords: tuple[str, ...] = ("dspdriver",)

    # AI 失败策略
    ai_retry_times: int = 0
    ai_fail_policy: str = "fallback"  # fallback | skip_function | circuit_fallback
    ai_regression_rounds: int = 2
    ai_quality_hard_fail_policy: str = "line_deterministic_fallback"

    # 可观测副作用分析：off | direct | one_hop。
    effect_analysis_mode: str = "one_hop"

    # 解析头文件时，是否递归解析其 #include 的头文件（用于 Global.h 这类"汇总头"）。
    # 0 表示不递归；建议 4~10。
    header_transitive_depth: int = 8

    # 预处理并行度（0=自动，1=禁用并行）
    preprocess_workers: int = 0
    # 工程生成时预筛选无注释/无函数文件
    prefilter_project_files: bool = True
    # GUI 可覆盖工程文件/模块生成顺序（按层：app/mid/drv）
    # - 旧格式：{"app":[abs_path, ...], "mid":[...], "drv":[...]}
    # - 新格式（支持合并模块）：list 内可包含 dict {"module": "...", "files":[abs_path,...]}
    project_file_order: Optional[dict[str, list[Any]]] = None
    # GUI 动态参数：用于 AI key/变量名容错等高级调参（如 max_dist/min_ratio）
    extra_params: Optional[dict[str, Any]] = None
    # 运行期：当前项目根目录与项目符号记忆库路径
    project_root: str = ""
    symbol_memory_path: str = ""
    term_table_path: str = ""
    symbol_dict_overrides: Optional[dict[str, str]] = None
    # 单函数导出时启用的增强伪代码归并；默认关闭，避免影响整文导出
    enhanced_single_func_pseudocode: bool = False
    # 增量生成：只生成变更的函数
    incremental: bool = False
    # CodeGraph/调用图谱增强
    codegraph_mode: str = "auto"          # auto | off | force
    graph_output: str = "off"             # off | html | word | both
    graph_depth: int = 2
    graph_max_nodes: int = 40
    codegraph_auto_index: bool = True
    codegraph_path: str = ""


# =============== 辅助函数 ===============

def _normalize_ai_profile_label(value: Any) -> str:
    """规范化 AI profile 标签。"""
    from .utils import _safe_strip

    text = _safe_strip(value).lower().replace("-", "_")
    if text in ("small_model", "small", "compact", "strict_compact"):
        return "small"
    if text in ("large_model", "large", "full"):
        return "large"
    return ""


__all__ = [
    "ToolError",
    "NoDataError",
    "SourceReadError",
    "ParseError",
    "RenderError",
    "SkipFunctionError",
    "GenConfig",
    "_normalize_ai_profile_label",
]
