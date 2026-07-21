"""Deterministic, source-backed function effect analysis.

The module deliberately stays independent of AI and optional CodeGraph/LSP
providers.  It consumes fact packs when they are available and falls back to
the same statement scanner used by ``lsp_facts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any, Iterable, Optional

from . import lsp_facts, parse
from .models import EffectFact, SourceRange


_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_RETURN_RE = re.compile(r"\breturn\b\s*(?P<expr>.*?);", re.S)
_CALL_RE = re.compile(r"\b(?P<callee>[A-Za-z_]\w*)\s*\(")
_C_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "return", "sizeof", "case", "do",
    "typedef", "struct", "union", "enum", "static", "const", "volatile",
})


@dataclass(frozen=True)
class EffectSummary:
    func_name: str
    source_file: str
    params: tuple[dict[str, str], ...] = ()
    effects: tuple[EffectFact, ...] = ()


@dataclass
class EffectIndex:
    by_name: dict[str, list[EffectSummary]] = field(default_factory=dict)

    def add(self, summary: EffectSummary) -> None:
        self.by_name.setdefault(summary.func_name, []).append(summary)

    def resolve(self, name: str) -> Optional[EffectSummary]:
        matches = self.by_name.get(str(name or ""), [])
        return matches[0] if len(matches) == 1 else None


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _range(value: Any) -> SourceRange:
    raw = value if isinstance(value, dict) else {}
    try:
        start_line = int(raw.get("start_line") or 0)
    except (TypeError, ValueError):
        start_line = 0
    try:
        end_line = int(raw.get("end_line") or start_line)
    except (TypeError, ValueError):
        end_line = start_line
    return SourceRange(start_line=start_line, end_line=end_line)


def _root_identifier(expr: str) -> str:
    value = _safe(expr)
    value = re.sub(r"^\s*\*+\s*", "", value)
    value = value.lstrip("(").strip()
    match = _IDENT_RE.search(value)
    return match.group(0) if match else ""


def _is_writable_lvalue(expr: str) -> bool:
    value = _safe(expr)
    value = re.sub(r"^&\s*", "", value).strip()
    return bool(re.fullmatch(r"\*?\s*[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*|\s*\[[^\]]+\])*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)*", value))


def _param_is_const(param: dict[str, Any]) -> bool:
    return bool(re.search(r"\bconst\b", _safe(param.get("type")), re.I))


def _operation(item: dict[str, Any]) -> str:
    op = _safe(dict(item.get("metadata") or {}).get("op"))
    if op == "|=":
        return "置位"
    if op == "&=":
        return "按位更新"
    if op in {"+=", "-=", "*=", "/="}:
        return "复合更新"
    rhs = _safe(item.get("rhs"))
    if rhs in {"0", "0U", "0UL", "NULL"}:
        return "清零"
    return "写入"


def _display_name(ident: str, name_map: dict[str, str]) -> str:
    value = _safe(ident)
    root = _root_identifier(value)
    return _safe(name_map.get(value) or name_map.get(root) or value)


def _effect_from_write(
    item: dict[str, Any],
    *,
    params: Iterable[dict[str, Any]],
    local_names: set[str],
    name_map: dict[str, str],
    source_file: str,
    source_function: str,
) -> Optional[EffectFact]:
    lhs = _safe(item.get("lhs"))
    root = _root_identifier(lhs)
    if not lhs or not root:
        return None
    param_map = {_safe(param.get("name")): dict(param) for param in params if _safe(param.get("name"))}
    definition_range = _range(item.get("range"))
    if root in param_map:
        param = param_map[root]
        if _param_is_const(param):
            return None
        if not ("*" in _safe(param.get("type")) or "[" in lhs or lhs.lstrip().startswith("*") or "->" in lhs):
            return None
        return EffectFact(
            kind="param_write", target_ident=lhs, target_name=_display_name(lhs, name_map),
            c_type=_safe(param.get("type")), operation=_operation(item), source_function=source_function,
            caller_source_file=source_file, caller_range=definition_range,
            definition_source_file=source_file, definition_range=definition_range,
            confidence=float(item.get("confidence") or 0.8), verified=bool(item.get("verified", True)),
        )
    if root in local_names or root in _C_KEYWORDS:
        return None
    return EffectFact(
        kind="global_write", target_ident=lhs, target_name=_display_name(lhs, name_map),
        c_type="", operation=_operation(item), source_function=source_function,
        caller_source_file=source_file, caller_range=definition_range,
        definition_source_file=source_file, definition_range=definition_range,
        confidence=float(item.get("confidence") or 0.8), verified=bool(item.get("verified", True)),
    )


def _condition_for_offset(body: str, offset: int) -> str:
    prefix = body[:max(0, offset)]
    matches = list(re.finditer(r"\bif\s*\((?P<condition>[^()]*(?:\([^()]*\)[^()]*)*)\)", prefix, re.S))
    return _safe(matches[-1].group("condition")) if matches else ""


def _return_effects(
    body: str, *, source_file: str, source_function: str, ret_type: str, name_map: dict[str, str]
) -> tuple[EffectFact, ...]:
    if not _safe(ret_type) or re.sub(r"\b(?:static|extern|const|volatile)\b", "", ret_type).strip().lower() == "void":
        return ()
    out: list[EffectFact] = []
    for match in _RETURN_RE.finditer(body or ""):
        expr = _safe(match.group("expr"))
        if not expr:
            continue
        line = (body or "")[:match.start()].count("\n") + 1
        value_name = _display_name(expr, name_map)
        out.append(EffectFact(
            kind="return", target_ident=expr, target_name=value_name, c_type=_safe(ret_type),
            operation="返回", source_function=source_function, caller_source_file=source_file,
            caller_range=SourceRange(start_line=line, end_line=line), definition_source_file=source_file,
            definition_range=SourceRange(start_line=line, end_line=line), confidence=0.9, verified=True,
            condition=_condition_for_offset(body, match.start()),
        ))
    return tuple(out)


def extract_direct_effects(
    func_data: dict[str, Any], *, params: Optional[Iterable[dict[str, Any]]] = None,
    local_vars: Optional[Iterable[dict[str, Any]]] = None, fact_pack: Optional[dict[str, Any]] = None,
    name_map: Optional[dict[str, str]] = None,
) -> tuple[tuple[EffectFact, ...], tuple[EffectFact, ...]]:
    """Return direct write effects and all non-void return branches."""
    data = dict(func_data or {})
    func_info = dict(data.get("func_info") or {})
    body = _safe(data.get("body"))
    file_context = dict(data.get("file_context") or {})
    source_file = _safe(file_context.get("source_file"))
    func_name = _safe(func_info.get("func_name"))
    params_list = list(params if params is not None else parse.parse_params_from_prototype(func_info))
    locals_list = list(local_vars or [])
    if fact_pack is None:
        _reads, writes = lsp_facts._collect_accesses(body)
        write_items = [
            {"lhs": item.lhs, "rhs": item.rhs, "range": vars(item.range), "metadata": item.metadata,
             "confidence": item.confidence, "verified": item.verified}
            for item in writes
        ]
    else:
        write_items = [dict(item) for item in (fact_pack.get("writes") or ()) if isinstance(item, dict)]
    names = dict(name_map or {})
    local_names = {_safe(item.get("name")) for item in locals_list if _safe(item.get("name"))}
    effects = []
    seen = set()
    for item in write_items:
        effect = _effect_from_write(
            item, params=params_list, local_names=local_names, name_map=names,
            source_file=source_file, source_function=func_name,
        )
        if effect is None:
            continue
        key = (effect.kind, effect.target_ident, effect.operation, effect.caller_range.start_line)
        if key not in seen:
            seen.add(key)
            effects.append(effect)
    returns = _return_effects(
        body, source_file=source_file, source_function=func_name,
        ret_type=_safe(func_info.get("ret_type")), name_map=names,
    )
    return tuple(effects), returns


def _iter_c_files(project_root: str, exclude_dirs: Iterable[str]) -> Iterable[str]:
    excluded = {str(item).lower() for item in exclude_dirs or ()}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [name for name in dirs if name.lower() not in excluded and not name.startswith(".")]
        for name in files:
            if name.lower().endswith(".c"):
                yield os.path.join(root, name)


def build_effect_index(project_root: str, cfg: Any = None) -> EffectIndex:
    """Build a direct-effect index without requiring optional project tools."""
    index = EffectIndex()
    if not project_root or not os.path.isdir(project_root):
        return index
    excluded = getattr(cfg, "exclude_dirs", ()) if cfg is not None else ()
    for path in _iter_c_files(project_root, excluded):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
            entries = parse.associate_comments_and_functions(code, file_context_extra={"source_file": path})
        except Exception:
            continue
        for entry in entries or ():
            func_info = dict(entry.get("func_info") or {})
            name = _safe(func_info.get("func_name"))
            if not name:
                continue
            params = parse.parse_params_from_prototype(func_info)
            local_vars = []
            try:
                local_vars = parse.parse_local_variables_from_body(_safe(entry.get("body")))
            except Exception:
                pass
            effects, _returns = extract_direct_effects(entry, params=params, local_vars=local_vars)
            index.add(EffectSummary(
                func_name=name, source_file=path,
                params=tuple({"name": _safe(param.get("name")), "type": _safe(param.get("type"))} for param in params),
                effects=effects,
            ))
    return index


def _call_arguments(call_text: str) -> list[str]:
    text = _safe(call_text)
    open_pos = text.find("(")
    close_pos = text.rfind(")")
    if open_pos < 0 or close_pos <= open_pos:
        return []
    out, current, depth = [], [], 0
    for char in text[open_pos + 1:close_pos]:
        if char == "," and depth == 0:
            out.append(_safe("".join(current)))
            current = []
            continue
        current.append(char)
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
    tail = _safe("".join(current))
    if tail:
        out.append(tail)
    return out


def _callsite_range(item: dict[str, Any]) -> SourceRange:
    return _range(item.get("range"))


def resolve_one_hop_effects(
    fact_pack: dict[str, Any], *, index: EffectIndex, source_file: str,
    source_function: str, name_map: Optional[dict[str, str]] = None,
) -> tuple[tuple[EffectFact, ...], tuple[dict[str, Any], ...]]:
    """Map verified direct callee effects to the current call site."""
    names = dict(name_map or {})
    effects: list[EffectFact] = []
    issues: list[dict[str, Any]] = []
    seen = set()
    for call in (fact_pack.get("calls") or ()):
        if not isinstance(call, dict):
            continue
        callee = _safe(call.get("callee"))
        if not callee or callee in _C_KEYWORDS:
            continue
        call_range = _callsite_range(call)
        if callee == source_function:
            issues.append({"code": "callee_effect_unresolved", "severity": "warning", "message": f"递归调用 {callee} 的副作用未展开", "source_anchor": {"file": source_file, **vars(call_range)}})
            continue
        summary = index.resolve(callee)
        if summary is None:
            issues.append({"code": "callee_effect_unresolved", "severity": "warning", "message": f"调用 {callee} 的副作用未确认", "source_anchor": {"file": source_file, **vars(call_range)}})
            continue
        args = _call_arguments(_safe(call.get("call_text")))
        if len(args) != len(summary.params):
            issues.append({"code": "callee_effect_unresolved", "severity": "warning", "message": f"调用 {callee} 的参数无法可靠映射", "source_anchor": {"file": source_file, **vars(call_range)}})
            continue
        formal_index = {item.get("name", ""): idx for idx, item in enumerate(summary.params)}
        for inherited in summary.effects:
            if not inherited.verified:
                continue
            if inherited.kind == "global_write":
                target = inherited.target_ident
                kind = "callee_effect"
            elif inherited.kind == "param_write":
                formal = _root_identifier(inherited.target_ident)
                pos = formal_index.get(formal, -1)
                raw_actual = _safe(args[pos]) if pos >= 0 else ""
                passed_address = bool(re.match(r"^&\s*", raw_actual))
                actual = re.sub(r"^&\s*", "", raw_actual).strip()
                if not _is_writable_lvalue(actual):
                    issues.append({"code": "callee_effect_unresolved", "severity": "warning", "message": f"调用 {callee} 的输出参数 {formal} 未映射到可写实参", "source_anchor": {"file": source_file, **vars(call_range)}})
                    continue
                if passed_address:
                    # ``*out`` in the callee denotes the caller object passed
                    # as ``&result``; remove that formal dereference.
                    target = re.sub(rf"^\s*\*+\s*{re.escape(formal)}", actual, inherited.target_ident)
                else:
                    target = re.sub(rf"\b{re.escape(formal)}\b", actual, inherited.target_ident, count=1)
                kind = "callee_effect"
            else:
                continue
            effect = EffectFact(
                kind=kind, target_ident=target, target_name=_display_name(target, names), c_type=inherited.c_type,
                operation=inherited.operation, source_function=callee, caller_source_file=source_file,
                caller_range=call_range, definition_source_file=inherited.definition_source_file,
                definition_range=inherited.definition_range, confidence=min(0.85, inherited.confidence),
                verified=True, condition="",
            )
            key = (effect.target_ident, effect.source_function, effect.operation, effect.caller_range.start_line)
            if key not in seen:
                seen.add(key)
                effects.append(effect)
    return tuple(effects), tuple(issues)


__all__ = ["EffectIndex", "EffectSummary", "build_effect_index", "extract_direct_effects", "resolve_one_hop_effects"]
