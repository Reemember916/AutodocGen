"""LogicStep IR — shadow mode 结构化逻辑步骤。

本模块为 TODO P0#5 的实现：为每个 C 函数体构建结构化 LogicStep 序列，
**不替换** `logic.generate_logic_from_body()` 的文本渲染路径。

设计目标
--------
- 旁路（shadow）输出：与现有文本渲染并行运行，不影响 docx 产出。
- 每个 LogicStep 保留：source_range / attached_comments / expression_text /
  scope_depth / confidence / fallback_reason。
- 空 ELSE、loop reset、default init 等边界场景能被结构化标记。
- 后续由 ``LogicStep + SemanticElement`` 交给确定性 renderer 输出 GJB 风格短句。

数据结构
--------
所有 step 类型继承 ``LogicStep`` 基类（frozen dataclass），按 C 控制流分类：
  IfStep / ElseIfStep / ElseStep / ForStep / WhileStep / DoWhileStep /
  SwitchStep / CaseStep / DefaultStep / AssignmentStep / CallStep /
  ReturnStep / BreakStep / ContinueStep / EndBlockStep / UnknownStep

构建器
------
``build_logic_steps(body, local_vars, cfg, name_map)`` 复用 logic.py 的行预处理
helper（``_join_c_line_continuations`` / ``_expand_inline_control_line_infos``
/ ``_merge_multiline_expression_line_infos``），独立做 block_stack 跟踪与
模式匹配，产出 ``list[LogicStep]``。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

from ._legacy_support import legacy_backend
from . import utils
from . import parse as parse_utils


# ── 数据结构 ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceRange:
    """源码行号范围（1-indexed，与 line_infos 对齐）。"""
    start_line: int = 0
    end_line: int = 0
    raw_snippet: str = ""


@dataclass(frozen=True)
class LogicStep:
    """所有 LogicStep 的基类。

    ``kind`` 标识步骤类型，下游 renderer / evidence 据此分派。
    """
    kind: str = "unknown"
    source_range: SourceRange = field(default_factory=SourceRange)
    attached_comments: tuple[str, ...] = ()
    expression_text: str = ""          # 原始 C 表达式（去注释后）
    scope_depth: int = 0              # block_stack 深度
    confidence: float = 1.0           # 1.0=确定性规则；<1.0=启发式/降级
    fallback_reason: str = ""         # confidence<1.0 时的降级原因
    extra: tuple = ()                 # 类型特定的附加字段


@dataclass(frozen=True)
class IfStep(LogicStep):
    kind: str = "if"
    condition: str = ""


@dataclass(frozen=True)
class ElseIfStep(LogicStep):
    kind: str = "else_if"
    condition: str = ""


@dataclass(frozen=True)
class ElseStep(LogicStep):
    kind: str = "else"
    is_empty: bool = False            # 空 ELSE 标记（后续 ELSE 后紧接 END IF）


@dataclass(frozen=True)
class ForStep(LogicStep):
    kind: str = "for"
    init: str = ""
    condition: str = ""
    update: str = ""


@dataclass(frozen=True)
class WhileStep(LogicStep):
    kind: str = "while"
    condition: str = ""


@dataclass(frozen=True)
class DoWhileStep(LogicStep):
    kind: str = "do_while"
    condition: str = ""


@dataclass(frozen=True)
class SwitchStep(LogicStep):
    kind: str = "switch"
    expression: str = ""


@dataclass(frozen=True)
class CaseStep(LogicStep):
    kind: str = "case"
    value: str = ""


@dataclass(frozen=True)
class DefaultStep(LogicStep):
    kind: str = "default"


@dataclass(frozen=True)
class AssignmentStep(LogicStep):
    kind: str = "assignment"
    lhs: str = ""
    rhs: str = ""
    op: str = "="                     # = += -= <<= 等
    is_declaration: bool = False      # 带初始化的声明行


@dataclass(frozen=True)
class CallStep(LogicStep):
    kind: str = "call"
    callee: str = ""
    args: str = ""
    lhs: str = ""                     # 赋值型调用 x = foo()


@dataclass(frozen=True)
class ReturnStep(LogicStep):
    kind: str = "return"
    expression: str = ""


@dataclass(frozen=True)
class BreakStep(LogicStep):
    kind: str = "break"


@dataclass(frozen=True)
class ContinueStep(LogicStep):
    kind: str = "continue"


@dataclass(frozen=True)
class EndBlockStep(LogicStep):
    """控制块结束标记：END IF / NEXT / END WHILE / END DO WHILE / END SWITCH。"""
    kind: str = "end_block"
    block_type: str = ""              # IF / FOR / WHILE / DO WHILE / SWITCH


@dataclass(frozen=True)
class UnknownStep(LogicStep):
    """无法分类的语句，记录原始代码供 AI 二次填充。"""
    kind: str = "unknown"
    code: str = ""


LogicStepType = Union[
    IfStep, ElseIfStep, ElseStep, ForStep, WhileStep, DoWhileStep,
    SwitchStep, CaseStep, DefaultStep, AssignmentStep, CallStep,
    ReturnStep, BreakStep, ContinueStep, EndBlockStep, UnknownStep,
]


# ── 构建器 ─────────────────────────────────────────────────────────


def _is_noop(code: str) -> bool:
    """空语句 / 纯分号 / 纯花括号。"""
    c = code.strip()
    if not c:
        return True
    if c in ("{", "}", "{}", "{;}", "};"):
        return True
    core = re.sub(r"[{};]", "", c).strip()
    return not core


def _is_declaration(code: str) -> bool:
    """粗判是否为声明行（含类型 + 标识符 + 可选初始化）。"""
    c = code.strip()
    if not c:
        return False
    if re.match(r"^(if|else|for|while|do|switch|case|default|return|break|continue)\b", c):
        return False
    # Tagged aggregate declarations are valid even when the tag is lowercase,
    # e.g. ``union arinc429Data l_rdata_un[...]``.
    if re.match(
        r"^(?:static\s+|const\s+|volatile\s+|register\s+)*"
        r"(?:struct|union|enum)\s+[A-Za-z_]\w*\s+\**\s*[A-Za-z_]\w*",
        c,
    ):
        return True
    return bool(re.match(
        r"^(static\s+|const\s+|volatile\s+|register\s+)*"
        r"(unsigned\s+|signed\s+)?"
        r"(void|char|short|int|long|float|double|"
        r"[A-Za-z_]\w*_t|[A-Z][A-Za-z0-9_]*)"
        r"(\s+\*+|\s*\*+|\s+)\w+", c))


def _extract_condition(header: str) -> str:
    """从 ``if (cond)`` / ``while (cond)`` 等提取括号内条件文本。"""
    m = re.search(r"\((.*)\)\s*\{?\s*$", header, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _split_for_header(header: str) -> tuple[str, str, str]:
    """从 ``for (init; cond; update)`` 提取三段。"""
    cond = _extract_condition(header)
    parts = cond.split(";")
    init = parts[0].strip() if len(parts) > 0 else ""
    condition = parts[1].strip() if len(parts) > 1 else ""
    update = parts[2].strip() if len(parts) > 2 else ""
    return (init, condition, update)


def _split_assignment(code: str) -> Optional[tuple[str, str, str]]:
    """拆 ``lhs op rhs``，返回 (lhs, op, rhs) 或 None。

    支持 = += -= *= /= %= <<= >>= &= |= ^=
    """
    c = code.strip().rstrip(";").strip()
    for op in ("<<=", ">>=", "==", "!=", "<=", ">=", "&&", "||",
               "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "="):
        idx = c.find(op)
        if idx > 0:
            lhs = c[:idx].strip()
            rhs = c[idx + len(op):].strip()
            if lhs and rhs:
                return (lhs, op, rhs)
    return None


def _extract_call(code: str) -> Optional[tuple[str, str, str]]:
    """从 ``foo(args)`` 或 ``lhs = foo(args)`` 提取 (callee, args, lhs)。

    lhs 为空表示无赋值的裸调用。
    """
    c = code.strip().rstrip(";").strip()
    lhs = ""
    eq = _split_assignment(c)
    if eq:
        lhs, _, rhs = eq
        c = rhs
    m = re.search(r"([A-Za-z_]\w*)\s*\((.*)\)\s*$", c, re.DOTALL)
    if m:
        return (m.group(1), m.group(2).strip(), lhs)
    return None


def build_logic_steps(
    body: str,
    local_vars: Any = None,
    cfg: Any = None,
    name_map: Optional[dict[str, str]] = None,
    *,
    backend_module: Any = None,
) -> list[LogicStep]:
    """为 C 函数体构建结构化 LogicStep 序列（shadow mode）。

    本函数**不替换** ``logic.generate_logic_from_body()`` 的文本渲染，
    只产出旁路 IR，供 evidence / 确定性 renderer 消费。

    参数
    -----
    body : C 函数体文本（不含函数签名）
    local_vars : 局部变量列表（仅用于上下文，当前未深度使用）
    cfg : GenConfig
    name_map : 标识符→中文名映射（当前未深度使用，留给后续 renderer）
    backend_module : 可选的 backend 模块注入

    返回
    -----
    list[LogicStep]，按源码顺序排列
    """
    backend = backend_module or legacy_backend()
    steps: list[LogicStep] = []

    # ── 阶段 1: 行预处理（复用 logic.py 的 helper）──
    # Block comments may span several lines.  Removing only one line at a
    # time leaves `* comment` / `*/` fragments, which then become unknown
    # logic steps and leak into the rendered flow. Preserve line count while
    # removing the entire block so source ranges remain valid.
    def _strip_block_comment_keep_lines(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")

    code_body = re.sub(r"/\*.*?\*/", _strip_block_comment_keep_lines, body or "", flags=re.DOTALL)
    lines = parse_utils._join_c_line_continuations(code_body).splitlines()
    line_infos: list[dict[str, Any]] = []
    for line_no, raw in enumerate(lines, start=1):
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
        line_infos.append({
            "raw": raw,
            "code": tmp.strip(),
            "comments": comments,
            "attached": [],
            "line_no": line_no,
        })

    # 复用 logic.py 的 inline 展开 + 多行合并
    try:
        from .logic import _expand_inline_control_line_infos, _merge_multiline_expression_line_infos
        line_infos = _merge_multiline_expression_line_infos(
            _expand_inline_control_line_infos(line_infos)
        )
    except Exception:
        pass  # fallback: 用原始 line_infos

    # ── 阶段 2: 注释挂接 ──
    comment_mode = parse_utils._get_logic_comment_mode(cfg)
    use_comment = comment_mode != "off"
    if use_comment:
        pending_comments: list[str] = []
        for info in line_infos:
            code = info["code"]
            inline_comments = [c for c in info["comments"]
                               if not parse_utils._is_non_semantic_comment(c)]
            core = code.replace("{", "").replace("}", "").replace(";", "").strip()
            if not core:
                pending_comments.extend(inline_comments)
                continue
            if _is_declaration(code):
                pending_comments = []
                continue
            attached: list[str] = []
            if inline_comments:
                attached.extend(inline_comments)
                pending_comments = []
            else:
                if pending_comments:
                    attached.extend(pending_comments)
                    pending_comments = []
            info["attached"] = tuple(attached)
    else:
        for info in line_infos:
            info["attached"] = ()

    # ── 阶段 3: 大括号深度 ──
    brace_depth = 0
    for info in line_infos:
        info["brace_depth_before"] = brace_depth
        code = info["code"]
        brace_depth += code.count("{")
        brace_depth -= code.count("}")
        info["brace_depth_after"] = brace_depth

    # ── 阶段 4: 主循环 + block_stack ──
    block_stack: list[dict[str, Any]] = []
    case_active = False
    case_depth: Optional[int] = None

    def _scope_depth() -> int:
        d = len(block_stack)
        if case_active:
            d += 1
        return d

    def _src(info: dict, raw_snippet: str = "") -> SourceRange:
        return SourceRange(
            start_line=info.get("line_no", 0),
            end_line=info.get("line_no", 0),
            raw_snippet=raw_snippet or info.get("raw", ""),
        )

    def _next_significant(start_idx: int) -> tuple[Optional[str], Optional[int]]:
        for j in range(start_idx + 1, len(line_infos)):
            code = line_infos[j]["code"].strip()
            core = code.replace("{", "").replace("}", "").replace(";", "").strip()
            if not core or _is_declaration(code):
                continue
            header_local = code.lstrip()
            depth = line_infos[j].get("brace_depth_before")
            if re.match(r"^else\s+if\s*\(", header_local):
                return "ELSE IF", depth
            if re.match(r"^else\b", header_local):
                return "ELSE", depth
            return None, depth
        return None, None

    for idx, info in enumerate(line_infos):
        code = info["code"].strip()
        attached_c: tuple[str, ...] = info.get("attached", ())
        line_no = info.get("line_no", idx + 1)
        src = _src(info)

        if case_active and info.get("brace_depth_before", 0) < (case_depth or 0):
            case_active = False
            case_depth = None

        # ── `}` 关闭块（必须在 _is_noop 之前，因为 _is_noop("}") 返回 True）──
        if code in ("}", "};"):
            close_after = info.get("brace_depth_after", 0)
            while block_stack and close_after <= block_stack[-1].get("close_depth", -1):
                top = block_stack.pop()
                if top.get("type") == "SWITCH":
                    case_active = False
                    case_depth = None
                t = top.get("type")
                if t == "IF":
                    nxt, nxt_depth = _next_significant(idx)
                    same_level = nxt_depth is not None and nxt_depth == close_after
                    if nxt in ("ELSE", "ELSE IF") and same_level:
                        block_stack.append(top)
                        break
                # ELSE / ELSE IF are branches of the retained IF block, not
                # independent control structures.  Closing them must not
                # render the invalid pseudo-lines "END ELSE" / "END ELSE IF".
                if t in ("ELSE", "ELSE IF"):
                    continue
                steps.append(EndBlockStep(
                    source_range=src,
                    attached_comments=(),
                    scope_depth=len(block_stack),
                    block_type=t or "",
                ))
            continue

        if not code or _is_noop(code):
            continue

        header = code.lstrip()

        # ── if ──
        if re.match(r"^if\s*\(", header):
            cond = _extract_condition(header)
            steps.append(IfStep(
                source_range=src, attached_comments=attached_c,
                expression_text=cond, condition=cond,
                scope_depth=_scope_depth(),
            ))
            block_stack.append({"type": "IF", "close_depth": info.get("brace_depth_before", 0)})
            continue

        # ── else if ──
        if re.match(r"^else\s+if\s*\(", header):
            cond = _extract_condition(header)
            steps.append(ElseIfStep(
                source_range=src, attached_comments=attached_c,
                expression_text=cond, condition=cond,
                scope_depth=max(0, _scope_depth() - 1),
            ))
            block_stack.append({"type": "ELSE IF", "close_depth": info.get("brace_depth_before", 0),
                                 "no_body_indent": True})
            continue

        # ── else ──
        if re.match(r"^else\b", header):
            # 空 ELSE 检测：ELSE 后下一个非空非声明行是 `}`
            nxt, _ = _next_significant(idx)
            is_empty = (nxt is None)  # 下一个 significant 是 `}` → nxt 为 None
            steps.append(ElseStep(
                source_range=src, attached_comments=attached_c,
                scope_depth=max(0, _scope_depth() - 1),
                is_empty=is_empty,
            ))
            block_stack.append({"type": "ELSE", "close_depth": info.get("brace_depth_before", 0),
                                 "no_body_indent": True})
            continue

        # ── for ──
        if re.match(r"^for\s*\(", header):
            init, cond, update = _split_for_header(header)
            steps.append(ForStep(
                source_range=src, attached_comments=attached_c,
                expression_text=header, init=init, condition=cond, update=update,
                scope_depth=_scope_depth(),
            ))
            block_stack.append({"type": "FOR", "close_depth": info.get("brace_depth_before", 0)})
            continue

        # ── while ──
        if re.match(r"^while\s*\(", header):
            cond = _extract_condition(header)
            steps.append(WhileStep(
                source_range=src, attached_comments=attached_c,
                expression_text=cond, condition=cond,
                scope_depth=_scope_depth(),
            ))
            block_stack.append({"type": "WHILE", "close_depth": info.get("brace_depth_before", 0)})
            continue

        # ── do while ──
        if re.match(r"^do\s+while\s*\(", header):
            cond = _extract_condition(header)
            steps.append(DoWhileStep(
                source_range=src, attached_comments=attached_c,
                expression_text=cond, condition=cond,
                scope_depth=_scope_depth(),
            ))
            block_stack.append({"type": "DO WHILE", "close_depth": info.get("brace_depth_before", 0)})
            continue

        # ── switch ──
        if re.match(r"^switch\s*\(", header):
            expr = _extract_condition(header)
            steps.append(SwitchStep(
                source_range=src, attached_comments=attached_c,
                expression_text=expr, expression=expr,
                scope_depth=_scope_depth(),
            ))
            block_stack.append({"type": "SWITCH", "close_depth": info.get("brace_depth_before", 0)})
            continue

        # ── case ──
        if re.match(r"^case\b", header):
            m = re.match(r"^case\s+(.+?)\s*:", header)
            val = m.group(1).strip() if m else ""
            steps.append(CaseStep(
                source_range=src, attached_comments=attached_c,
                expression_text=val, value=val,
                scope_depth=_scope_depth(),
            ))
            case_active = True
            case_depth = info.get("brace_depth_before", 0)
            continue

        # ── default ──
        if re.match(r"^default\b", header):
            steps.append(DefaultStep(
                source_range=src, attached_comments=attached_c,
                scope_depth=_scope_depth(),
            ))
            case_active = True
            case_depth = info.get("brace_depth_before", 0)
            continue

        # ── 声明行（带初始化）──
        if _is_declaration(code):
            decl = _split_assignment(code)
            if decl:
                lhs, op, rhs = decl
                steps.append(AssignmentStep(
                    source_range=src, attached_comments=attached_c,
                    expression_text=code, lhs=lhs, rhs=rhs, op=op,
                    is_declaration=True, scope_depth=_scope_depth(),
                ))
            continue

        # ── return ──
        if re.match(r"^return\b", header):
            expr = re.sub(r"^return\s*", "", code).rstrip(";").strip()
            steps.append(ReturnStep(
                source_range=src, attached_comments=attached_c,
                expression_text=expr, expression=expr,
                scope_depth=_scope_depth(),
            ))
            continue

        # ── break ──
        if re.match(r"^break\b", header):
            steps.append(BreakStep(
                source_range=src, attached_comments=attached_c,
                scope_depth=_scope_depth(),
            ))
            continue

        # ── continue ──
        if re.match(r"^continue\b", header):
            steps.append(ContinueStep(
                source_range=src, attached_comments=attached_c,
                scope_depth=_scope_depth(),
            ))
            continue

        # ── 赋值 / 调用 ──
        call = _extract_call(code)
        if call:
            callee, args, lhs = call
            steps.append(CallStep(
                source_range=src, attached_comments=attached_c,
                expression_text=code, callee=callee, args=args, lhs=lhs,
                scope_depth=_scope_depth(),
            ))
            continue

        assign = _split_assignment(code)
        if assign:
            lhs, op, rhs = assign
            steps.append(AssignmentStep(
                source_range=src, attached_comments=attached_c,
                expression_text=code, lhs=lhs, rhs=rhs, op=op,
                scope_depth=_scope_depth(),
            ))
            continue

        # ── 纯调用（无赋值）──
        m = re.match(r"^([A-Za-z_]\w*)\s*\((.*)\)\s*;?\s*$", code, re.DOTALL)
        if m:
            callee = m.group(1)
            args = m.group(2).strip()
            steps.append(CallStep(
                source_range=src, attached_comments=attached_c,
                expression_text=code, callee=callee, args=args,
                scope_depth=_scope_depth(),
            ))
            continue

        # ── 未知 ──
        steps.append(UnknownStep(
            source_range=src, attached_comments=attached_c,
            expression_text=code, code=code,
            scope_depth=_scope_depth(),
            confidence=0.5,
            fallback_reason="unclassified_statement",
        ))

    return steps


# ── 未翻译标识符收集（module-level, 供 AI 批量建议后写回 symbol_memory）──

_UNTRANSLATED_IDENTS: set[str] = set()


def _mark_untranslated(ident: str) -> None:
    key = str(ident or "").strip()
    if not key:
        return
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*$", key):
        _UNTRANSLATED_IDENTS.add(key)


def get_untranslated_idents() -> list[str]:
    return sorted(_UNTRANSLATED_IDENTS)


def clear_untranslated_idents() -> None:
    _UNTRANSLATED_IDENTS.clear()


def summarize_logic_steps(steps: Sequence[LogicStep]) -> dict[str, Any]:
    """生成 LogicStep 序列的质量摘要（供 evidence / 质量评估消费）。"""
    total = len(steps)
    if total == 0:
        return {"total": 0, "kinds": {}, "unknown_ratio": 0.0,
                "empty_else_count": 0, "avg_confidence": 0.0}

    kind_counts: dict[str, int] = {}
    unknown_count = 0
    empty_else_count = 0
    confidence_sum = 0.0
    for s in steps:
        kind_counts[s.kind] = kind_counts.get(s.kind, 0) + 1
        if s.kind == "unknown":
            unknown_count += 1
        if isinstance(s, ElseStep) and s.is_empty:
            empty_else_count += 1
        confidence_sum += s.confidence

    return {
        "total": total,
        "kinds": kind_counts,
        "unknown_count": unknown_count,
        "unknown_ratio": round(unknown_count / total, 3),
        "empty_else_count": empty_else_count,
        "avg_confidence": round(confidence_sum / total, 3),
    }


_IDENT_STRIP_RE = re.compile(
    r"^(?:(?:s_|g_|l_|p_|v_|m_|k_|t_|ls_|lr_))"
    r"|(?:_(?:u8|u16|u32|u64|i8|i16|i32|i64|f|d|s|t|un|st|af|ptr|idx|_t))"
    r"|(?:_[A-Za-z]\w+_t$)"
)


def _try_ident_cn(key: str, name_map: dict[str, str], *, backend_module=None) -> str:
    """Strip common C prefixes/suffixes and try to look up the identifier."""
    try:
        backend = backend_module or legacy_backend()
    except Exception:
        backend = None
    # 1) exact
    if key in name_map:
        return name_map[key]
    # 2) symbol dictionary
    if backend is not None:
        try:
            exact = backend._lookup_symbol_dictionary(key)
            if exact:
                return exact
        except Exception:
            pass
    # 3) strip prefixes
    stripped = re.sub(r"^(?:s_|g_|l_|p_|v_|m_|k_|t_|ls_|lr_)", "", key)
    if stripped != key:
        if stripped in name_map:
            return name_map[stripped]
        if backend is not None:
            try:
                exact = backend._lookup_symbol_dictionary(stripped)
                if exact:
                    return exact
            except Exception:
                pass
    # 4) strip numeric type suffixes
    stripped2 = re.sub(r"_(?:u8|u16|u32|u64|i8|i16|i32|i64|f|d|s|un|st|af|ptr|idx|_t)$", "", stripped, flags=re.IGNORECASE)
    if stripped2 != stripped:
        if stripped2 in name_map:
            return name_map[stripped2]
        if backend is not None:
            try:
                exact = backend._lookup_symbol_dictionary(stripped2)
                if exact:
                    return exact
            except Exception:
                pass
    return ""


def _cn_expr(text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    raw = utils._safe_strip(text)
    if not raw:
        return ""
    names = dict(name_map or {})
    try:
        backend = backend_module or legacy_backend()
    except Exception:
        backend = None

    # Simple identifier: try token-level lookup before falling back to _logic_cn_expr
    if re.fullmatch(r"[A-Za-z_]\w*", raw):
        cn = _try_ident_cn(raw, names, backend_module=backend)
        if cn:
            return cn
        if backend is not None:
            try:
                guessed = backend._guess_cn_from_ident(raw)
                if guessed and guessed != raw:
                    return guessed
            except Exception:
                pass
        # Last resort: strip suffixes and try _logic_cn_expr
        try:
            from . import logic as logic_utils
            result = utils._safe_strip(
                logic_utils._logic_cn_expr(raw, name_map=names, backend_module=backend)
            )
            if result and result != raw:
                return result
        except Exception:
            pass
        _mark_untranslated(raw)
        return raw

    # Complex expression: delegate to _logic_cn_expr
    try:
        from . import logic as logic_utils
        result = utils._safe_strip(
            logic_utils._logic_cn_expr(raw, name_map=names, backend_module=backend)
        ) or raw
        return result
    except Exception:
        return names.get(raw, raw)


def _indent(depth: int) -> str:
    return "  " * max(0, int(depth or 0))


def _cn_condition(text: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    """Translate a C comparison/boolean condition into readable Chinese.

    Delegates to ``_cn_expr`` for identifier translation, then replaces
    C operators with Chinese equivalents.  Parentheses are kept as-is
    because replacing them with full-width forms breaks function-call
    readability.
    """
    cn = _cn_expr(text, name_map, backend_module=backend_module)
    cn = cn.replace(" != ", " 不等于 ")
    cn = cn.replace(" == ", " 等于 ")
    cn = cn.replace(" >= ", " 大于等于 ")
    cn = cn.replace(" <= ", " 小于等于 ")
    cn = cn.replace(" > ", " 大于 ")
    cn = cn.replace(" < ", " 小于 ")
    cn = cn.replace(" && ", " 且 ")
    cn = cn.replace(" || ", " 或 ")
    cn = cn.replace("! ", "非 ")
    cn = re.sub(r"\s+", " ", cn).strip()
    return cn


def _volatile_register_label(expression: str, name_map: Optional[dict[str, str]], *, backend_module=None) -> str:
    """Return a readable hardware-register label for volatile pointer access."""
    raw = utils._safe_strip(expression)
    if "volatile" not in raw or "*" not in raw:
        return ""
    known = (
        ("WReg_rFifo_EN", "接收FIFO读使能寄存器"),
        ("RReg_FiFo_Cnt", "接收FIFO计数寄存器"),
        ("RReg_FiFo_2Byte_L", "接收FIFO低16位数据寄存器"),
        ("RReg_FiFo_2Byte_H", "接收FIFO高16位数据寄存器"),
        ("WReg_resetRFifo", "接收FIFO复位寄存器"),
        ("WReg_tFifo_EN", "发送FIFO使能寄存器"),
        ("WReg_FiFo_2Byte_L", "发送FIFO低16位数据寄存器"),
        ("WReg_FiFo_2Byte_H", "发送FIFO高16位数据寄存器"),
    )
    for marker, label in known:
        if marker in raw:
            return label
    # Generic fallback: remove pointer cast/dereference and translate the
    # underlying structure member, never leaking ``volatile Uint16 *``.
    member = re.findall(r"\.([A-Za-z_]\w*)\s*\)?\s*$", raw)
    if member:
        return _cn_expr(member[-1], name_map, backend_module=backend_module) or member[-1]
    return "硬件寄存器"


def _render_volatile_assignment(
    lhs_raw: str,
    rhs_raw: str,
    name_map: Optional[dict[str, str]],
    *,
    backend_module=None,
) -> str:
    """Render ``volatile`` pointer reads/writes without C cast syntax."""
    lhs_register = _volatile_register_label(lhs_raw, name_map, backend_module=backend_module)
    rhs_register = _volatile_register_label(rhs_raw, name_map, backend_module=backend_module)
    lhs_cn = _cn_expr(lhs_raw, name_map, backend_module=backend_module)
    rhs_cn = _cn_expr(rhs_raw, name_map, backend_module=backend_module)
    if lhs_register:
        return f"向{lhs_register}写入{rhs_cn}" if rhs_cn else f"写入{lhs_register}"
    if rhs_register:
        return f"读取{rhs_register}并写入{lhs_cn}" if lhs_cn else f"读取{rhs_register}"
    return ""


def render_logic_steps_to_lines(
    steps: Sequence[LogicStep],
    *,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> list[str]:
    """Deterministic GJB-style lines from LogicStep IR (opt-in main path).

    Skips pure declarations; unknown steps fall back to expression_text / code.
    """
    backend = backend_module or legacy_backend()
    lines: list[str] = []
    for step in steps or []:
        kind = utils._safe_strip(getattr(step, "kind", "") or "unknown")
        depth = int(getattr(step, "scope_depth", 0) or 0)
        ind = _indent(depth)
        text = ""

        if kind == "if":
            cond = _cn_condition(getattr(step, "condition", "") or step.expression_text, name_map, backend_module=backend)
            text = f"IF {cond} 时" if cond else "IF"
        elif kind == "else_if":
            cond = _cn_condition(getattr(step, "condition", "") or step.expression_text, name_map, backend_module=backend)
            text = f"ELSE IF {cond} 时" if cond else "ELSE IF"
        elif kind == "else":
            if getattr(step, "is_empty", False):
                continue
            text = "ELSE"
        elif kind == "for":
            cond = _cn_condition(getattr(step, "condition", "") or step.expression_text, name_map, backend_module=backend)
            text = f"FOR {cond} 循环" if cond else "FOR 循环"
        elif kind == "while":
            cond = _cn_condition(getattr(step, "condition", "") or step.expression_text, name_map, backend_module=backend)
            text = f"WHILE {cond} 时" if cond else "WHILE"
        elif kind == "do_while":
            cond = _cn_condition(getattr(step, "condition", "") or step.expression_text, name_map, backend_module=backend)
            text = f"DO WHILE {cond} 时" if cond else "DO WHILE"
        elif kind == "switch":
            expr = _cn_expr(getattr(step, "expression", "") or step.expression_text, name_map, backend_module=backend)
            text = f"SWITCH 根据 {expr} 分支处理" if expr else "SWITCH"
        elif kind == "case":
            val = _cn_expr(getattr(step, "value", "") or step.expression_text, name_map, backend_module=backend)
            text = f"CASE 分支 {val}" if val else "CASE"
        elif kind == "default":
            text = "DEFAULT"
        elif kind == "break":
            text = "退出当前循环或分支"
        elif kind == "continue":
            text = "跳过本轮循环，进入下一轮循环"
        elif kind == "return":
            expr = utils._safe_strip(getattr(step, "expression", "") or step.expression_text)
            if not expr:
                text = "返回"
            else:
                try:
                    from . import semantic_elements as se

                    ret = se.infer_return_semantic(expr, name_map)
                    text = se.render_return_semantic(ret) or f"返回 {_cn_expr(expr, name_map, backend_module=backend)}"
                except Exception:
                    text = f"返回 {_cn_expr(expr, name_map, backend_module=backend)}"
        elif kind == "end_block":
            bt = utils._safe_strip(getattr(step, "block_type", "")).upper()
            end_map = {
                "IF": "END IF",
                "FOR": "NEXT",
                "WHILE": "END WHILE",
                "DO WHILE": "END DO WHILE",
                "DO_WHILE": "END DO WHILE",
                "SWITCH": "END SWITCH",
            }
            text = end_map.get(bt, f"END {bt}" if bt else "")
        elif kind == "assignment":
            if getattr(step, "is_declaration", False):
                continue
            code = utils._safe_strip(step.expression_text) or (
                f"{getattr(step, 'lhs', '')} {getattr(step, 'op', '=')} {getattr(step, 'rhs', '')}"
            )
            try:
                from . import semantic_elements as se

                act = se.infer_action_semantic(code, name_map)
                text = se.render_action_semantic(act) or ""
            except Exception:
                text = ""
            if not text:
                lhs_raw = utils._safe_strip(getattr(step, "lhs", ""))
                rhs_raw = utils._safe_strip(getattr(step, "rhs", ""))
                text = _render_volatile_assignment(
                    lhs_raw, rhs_raw, name_map, backend_module=backend
                )
                lhs = _cn_expr(lhs_raw, name_map, backend_module=backend)
                rhs = _cn_expr(rhs_raw, name_map, backend_module=backend)
                op = utils._safe_strip(getattr(step, "op", "=")) or "="
                if not text and lhs and rhs and lhs != rhs:
                    text = f"{lhs} {op} {rhs}"
                elif not text and lhs and rhs:
                    # lhs == rhs after translation → the line is meaningless, skip
                    pass
                elif not text:
                    fallback_text = _cn_expr(code, name_map, backend_module=backend)
                    # Guard: if the fallback renders as "A = A" (identical l/r), skip
                    if fallback_text and "=" in fallback_text:
                        parts = fallback_text.split("=", 1)
                        if len(parts) == 2 and parts[0].strip() == parts[1].strip().rstrip("；;"):
                            fallback_text = ""
                    text = fallback_text
        elif kind == "call":
            code = utils._safe_strip(step.expression_text) or (
                f"{getattr(step, 'callee', '')}({getattr(step, 'args', '')})"
            )
            try:
                from . import semantic_elements as se

                act = se.infer_action_semantic(code, name_map)
                text = se.render_action_semantic(act) or ""
            except Exception:
                text = ""
            if not text:
                callee = utils._safe_strip(getattr(step, "callee", ""))
                callee_cn = _cn_expr(callee, name_map, backend_module=backend) or callee
                lhs = _cn_expr(getattr(step, "lhs", ""), name_map, backend_module=backend)
                if callee == "Ccdl429LabOrderRev" and lhs:
                    text = f"对{lhs}进行429标签位序翻转"
                elif lhs:
                    text = f"调用 {callee_cn}，结果写入 {lhs}"
                else:
                    text = f"调用 {callee_cn}" if callee_cn else code
        elif kind == "unknown":
            code = utils._safe_strip(getattr(step, "code", "") or step.expression_text)
            if not code or code in ("{", "}", ";"):
                continue
            try:
                from . import semantic_elements as se

                act = se.infer_action_semantic(code, name_map)
                text = se.render_action_semantic(act) or ""
            except Exception:
                text = ""
            if not text:
                text = _cn_expr(code, name_map, backend_module=backend) or code
        else:
            text = _cn_expr(step.expression_text, name_map, backend_module=backend)

        text = utils._safe_strip(text)
        if not text:
            continue
        # Statement lines get Chinese full stop; control headers do not.
        control = kind in {
            "if", "else_if", "else", "for", "while", "do_while",
            "switch", "case", "default", "end_block",
        }
        if (not control) and (not text.endswith("；")) and (not text.endswith(";")):
            text = text + "；"
        lines.append(ind + text)
    return lines


def auto_suggest_symbol_translations(cfg: Any, *, project_root: str = "") -> dict[str, str]:
    """Use AI to translate collected untranslated identifiers and write to symbol memory.

    Call after LogicStep rendering completes.  Requires ``ai_assist=True``.
    Returns ``{ident: cn}`` for the suggestions that were written.
    """
    idents = get_untranslated_idents()
    if not idents:
        return {}
    try:
        backend = legacy_backend()
    except Exception:
        return {}
    if not getattr(cfg, "ai_assist", False):
        return {}
    if not utils.cfg_get_int(cfg, "logic_step_auto_translate", 1):
        return {}

    # Build prompt with minimal context
    chunk = [{"name": name} for name in idents[:40]]
    prompt = (
        "你是嵌入式软件术语整理助手。请为以下 C 代码标识符生成稳定、保守的中文名称。\n"
        "规则：\n"
        "- 名称要短，偏中性；不确定就返回空字符串，不要硬猜。\n"
        "- 只输出 JSON，不要解释。\n\n"
        f"输入：\n{json.dumps(chunk, ensure_ascii=False, indent=2)}\n\n"
        "输出格式：\n{\"symbol_name\": {\"cn_name\": \"中文名\", \"confidence\": 0.0}}"
    )
    try:
        js = backend.call_llm_json(prompt, cfg)
    except Exception:
        return {}
    if not isinstance(js, dict):
        return {}

    written: dict[str, str] = {}
    for name, item in js.items():
        if isinstance(item, dict):
            cn = utils._safe_strip(item.get("cn_name") or item.get("cn") or "")
        else:
            cn = utils._safe_strip(item)
        if not cn or cn == name:
            continue
        written[name] = cn

    if written and project_root:
        try:
            from . import naming as naming_utils
            path = naming_utils._default_project_symbol_memory_path(project_root)
            import json as _json
            existing: dict[str, Any] = {}
            if __import__("os").path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = _json.load(f) if isinstance(_json.load(f), dict) else {}
            existing.setdefault("symbols", {})
            for k, v in written.items():
                existing["symbols"][k] = {"cn": v, "source": "ai_auto_suggest", "confidence": 0.7}
            parent = __import__("os").path.dirname(path) or "."
            __import__("os").makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(existing, f, ensure_ascii=False, indent=2)
                f.write("\n")
            # Also update runtime symbol dictionary
            naming_utils.apply_symbol_dictionary_overrides(
                {k: v for k, v in written.items()},
                backend_module=backend,
            )
            try:
                backend.save_project_symbol_memory()
            except Exception:
                pass
        except Exception:
            pass

    clear_untranslated_idents()
    return written


__all__ = [
    "SourceRange",
    "LogicStep",
    "IfStep", "ElseIfStep", "ElseStep", "ForStep", "WhileStep", "DoWhileStep",
    "SwitchStep", "CaseStep", "DefaultStep", "AssignmentStep", "CallStep",
    "ReturnStep", "BreakStep", "ContinueStep", "EndBlockStep", "UnknownStep",
    "LogicStepType",
    "build_logic_steps",
    "summarize_logic_steps",
    "render_logic_steps_to_lines",
    "get_untranslated_idents",
    "clear_untranslated_idents",
    "auto_suggest_symbol_translations",
]
