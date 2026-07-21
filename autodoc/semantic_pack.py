"""Semantic pack builders for AI-facing function understanding."""

from __future__ import annotations

import re
from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import utils
from . import naming as naming_utils
from . import parse as parse_utils


_WRITE_RE = re.compile(
    r"\b([A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)+)\s*(?:[+\-*/%&|^]?=)"
)
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def _uniq_texts(items: list[str], *, limit: int = 12) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _safe_list(items: Any, *, limit: int = 12) -> list[str]:
    out: list[str] = []
    for item in items or ():
        text = str(item or "").strip()
        if text:
            out.append(text)
    return _uniq_texts(out, limit=limit)


def _matching_symbol_profile(semantic_record: dict[str, Any], name: str) -> dict[str, Any]:
    for item in semantic_record.get("symbol_profiles") or ():
        if utils._safe_strip((item or {}).get("name")) == utils._safe_strip(name):
            return dict(item or {})
    return {}


def _extract_member_writes(body: str) -> list[str]:
    writes: list[str] = []
    for raw in parse_utils._join_c_line_continuations(body or "").splitlines():
        code, _ = parse_utils._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt:
            continue
        for hit in _WRITE_RE.findall(stmt):
            writes.append(re.sub(r"\s+", "", str(hit or "")))
    return _uniq_texts(writes)


def _extract_call_actions(body: str) -> list[str]:
    actions: list[str] = []
    for raw in parse_utils._join_c_line_continuations(body or "").splitlines():
        code, _ = parse_utils._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt or "=" in stmt:
            continue
        m = _CALL_RE.search(stmt)
        if not m:
            continue
        callee = utils._safe_strip(m.group(1))
        if not callee or callee in {"if", "for", "while", "switch", "return", "sizeof"}:
            continue
        actions.append(f"调用{callee}")
    return _uniq_texts(actions)


def _build_role_summary(*, func_name: str, comment_desc: str, semantic_record: dict[str, Any]) -> str:
    compact = naming_utils.normalize_function_cn_title(comment_desc, func_name=func_name, comment_desc=comment_desc)
    if compact and compact != func_name:
        return compact
    family_prefix = utils._safe_strip(semantic_record.get("family_prefix"))
    action_suffix = utils._safe_strip(semantic_record.get("action_suffix"))
    guess = "".join(
        utils._safe_strip(naming_utils.guess_cn_from_ident(piece))
        for piece in (family_prefix, action_suffix)
        if utils._safe_strip(piece)
    )
    return guess or utils._safe_strip(func_name)


def _build_state_effects(semantic_record: dict[str, Any], member_writes: list[str], return_exprs: list[str]) -> list[str]:
    effects: list[str] = []
    for member in member_writes[:6]:
        effects.append(f"写入{member}")
    for callee in _safe_list(semantic_record.get("callee_names"), limit=4):
        effects.append(f"调用{callee}")
    for expr in return_exprs[:2]:
        effects.append(f"返回{expr}")
    return _uniq_texts(effects, limit=10)


def _build_control_skeleton(semantic_record: dict[str, Any], member_writes: list[str], call_actions: list[str]) -> list[str]:
    skeleton: list[str] = []
    for cond in _safe_list(semantic_record.get("condition_signatures"), limit=6):
        skeleton.append(f"条件:{cond}")
    for member in member_writes[:4]:
        skeleton.append(f"写入:{member}")
    for action in call_actions[:4]:
        skeleton.append(f"动作:{action}")
    return _uniq_texts(skeleton, limit=12)


def build_function_semantic_pack(func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
    from . import semantic as semantic_utils

    func_info = (func_data or {}).get("func_info") or {}
    comment_info = (func_data or {}).get("comment_info") or {}
    file_context = (func_data or {}).get("file_context") or {}
    body = utils._safe_text((func_data or {}).get("body"))
    func_name = utils._safe_strip(func_info.get("func_name"))
    if not func_name:
        return {}

    semantic_record = semantic_utils.resolve_current_function_semantic_record(func_data, cfg, backend_module=legacy_backend())
    module_key = utils._safe_strip(file_context.get("module_key")) or utils._safe_strip(semantic_record.get("module_key"))
    family_prefix = utils._safe_strip(file_context.get("family_prefix")) or utils._safe_strip(semantic_record.get("family_prefix"))
    action_suffix = utils._safe_strip(semantic_record.get("action_suffix")) or legacy_backend()._identifier_action_suffix(func_name)
    params = parse_utils.parse_params_from_prototype(func_info)
    local_vars = parse_utils.parse_local_variables_from_body(body)
    local_vars = parse_utils._filter_local_vars_against_params(local_vars, params, cfg=cfg, func_name=func_name)
    comment_desc = utils._safe_strip(comment_info.get("desc")) or utils._safe_strip(semantic_record.get("comment_desc"))
    member_writes = _extract_member_writes(body)
    return_exprs = _safe_list(semantic_record.get("return_exprs"), limit=4)
    call_actions = _extract_call_actions(body)

    symbol_profiles: list[dict[str, Any]] = []
    for item in list(params or []) + list(local_vars or []):
        name = utils._safe_strip((item or {}).get("name"))
        if not name:
            continue
        profile = _matching_symbol_profile(semantic_record, name)
        symbol_profiles.append(
            {
                "name": name,
                "scope": utils._safe_strip(profile.get("scope")) or ("param" if item in params else "local"),
                "decl_type": utils._safe_strip((item or {}).get("type")) or utils._safe_strip(profile.get("decl_type")),
                "role": utils._safe_strip(profile.get("role")),
                "direction": utils._safe_strip(profile.get("direction")),
                "producer_call": utils._safe_strip(profile.get("producer_call")),
                "producer_arg_tags": _safe_list(profile.get("producer_arg_tags"), limit=6),
                "consumer_patterns": _safe_list(profile.get("consumer_patterns"), limit=6),
                "sink_patterns": _safe_list(profile.get("sink_patterns"), limit=6),
                "dataflow_roles": _safe_list(profile.get("dataflow_roles"), limit=6),
                "usage_patterns": _safe_list(profile.get("usage_patterns"), limit=6),
                "paired_symbols": _safe_list(profile.get("paired_symbols"), limit=4),
                "existing_cn": naming_utils.resolve_canonical_symbol_name(name, kind="symbols", fallback=name, allow_guess=False),
            }
        )

    return {
        "func_name": func_name,
        "source_file": utils._safe_strip(file_context.get("source_file")),
        "module_key": module_key,
        "family_prefix": family_prefix,
        "action_suffix": action_suffix,
        "comment_desc": comment_desc,
        "ret_type": utils._safe_strip(func_info.get("ret_type")) or utils._safe_strip(semantic_record.get("ret_type")),
        "params": [
            {"name": utils._safe_strip((item or {}).get("name")), "type": utils._safe_strip((item or {}).get("type"))}
            for item in (params or []) if utils._safe_strip((item or {}).get("name"))
        ],
        "locals": [
            {"name": utils._safe_strip((item or {}).get("name")), "type": utils._safe_strip((item or {}).get("type"))}
            for item in (local_vars or []) if utils._safe_strip((item or {}).get("name"))
        ],
        "callee_names": _safe_list(semantic_record.get("callee_names"), limit=8),
        "macro_refs": _safe_list(semantic_record.get("macro_refs"), limit=8),
        "conditions": _safe_list(semantic_record.get("condition_signatures"), limit=8),
        "member_accesses": _safe_list(semantic_record.get("member_accesses"), limit=10),
        "member_writes": member_writes,
        "return_exprs": return_exprs,
        "return_symbols": _safe_list(semantic_record.get("return_symbols"), limit=4),
        "written_params": _safe_list(semantic_record.get("written_params"), limit=8),
        "read_params": _safe_list(semantic_record.get("read_params"), limit=8),
        "role_summary": _build_role_summary(func_name=func_name, comment_desc=comment_desc, semantic_record=semantic_record),
        "state_effects": _build_state_effects(semantic_record, member_writes, return_exprs),
        "control_skeleton": _build_control_skeleton(semantic_record, member_writes, call_actions),
        "symbol_profiles": symbol_profiles,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
