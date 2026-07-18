"""Function-level revision profile support.

Revision profiles are intentionally outside the generic rule engine.  They
capture reviewer feedback for a specific function and let users regenerate that
function without teaching one sample's phrasing to every other function.
"""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import os
import re
from functools import lru_cache
from typing import Any, Iterable, Sequence


def _safe_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def _as_text_list(value: Any) -> list[str]:
    return [text for text in (_safe_text(item) for item in _as_list(value)) if text]


def _as_logic_text_list(value: Any) -> list[str]:
    lines = [
        str(item if item is not None else "").expandtabs(4).rstrip()
        for item in _as_list(value)
    ]
    return [line for line in lines if line.strip()]


@lru_cache(maxsize=16)
def _load_json_file_cached(path: str, mtime_ns: int) -> dict[str, Any]:
    del mtime_ns
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _profile_from_value(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return copy.deepcopy(value)
    text = _safe_text(value)
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    path = os.path.abspath(os.path.expanduser(text))
    if not os.path.exists(path):
        return {}
    try:
        stat = os.stat(path)
        return copy.deepcopy(_load_json_file_cached(path, int(stat.st_mtime_ns)))
    except Exception:
        return {}


def load_revision_profile(cfg_or_value: Any) -> dict[str, Any]:
    """Load a revision profile from cfg.extra_params or a direct value.

    Supported values:
    - cfg.extra_params["revision_profile"] as a file path, JSON string, or dict
    - cfg.extra_params["revision_profile_json"] as an inline JSON object
    - a direct path/string/dict value
    """

    extra = getattr(cfg_or_value, "extra_params", None)
    if isinstance(extra, dict):
        for key in ("revision_profile", "revision_profile_json"):
            profile = _profile_from_value(extra.get(key))
            if profile:
                return profile
        return {}
    return _profile_from_value(cfg_or_value)


def _norm_path(path: Any) -> str:
    text = _safe_text(path)
    if not text:
        return ""
    try:
        return os.path.normcase(os.path.abspath(os.path.expanduser(text)))
    except Exception:
        return text


def _function_keys(source_file: str, func_name: str) -> tuple[str, ...]:
    func = _safe_text(func_name)
    src = _safe_text(source_file)
    keys: list[str] = []
    for path in (_norm_path(src), src):
        if path and func:
            keys.append(f"{path}::{func}")
    if src and func:
        keys.append(f"{os.path.basename(src)}::{func}")
    if func:
        keys.append(func)
    return tuple(dict.fromkeys(keys))


def _merge_patch(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            next_value = dict(merged[key])
            next_value.update(value)
            merged[key] = next_value
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = list(merged[key]) + list(value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _patch_matches_item(item: dict[str, Any], source_file: str, func_name: str) -> bool:
    func = _safe_text(func_name)
    if _safe_text(item.get("function") or item.get("func_name")) not in ("", func):
        return False
    item_file = _safe_text(item.get("file") or item.get("source_file"))
    if not item_file:
        return True
    return _norm_path(item_file) == _norm_path(source_file) or os.path.basename(item_file) == os.path.basename(source_file)


def find_function_patch(profile: dict[str, Any], source_file: str, func_name: str) -> dict[str, Any]:
    """Return the patch for a function, merging generic and file-specific entries."""

    if not isinstance(profile, dict):
        return {}
    funcs = profile.get("functions") or {}
    matched: dict[str, Any] = {}
    if isinstance(funcs, dict):
        keys = set(_function_keys(source_file, func_name))
        for key in reversed(_function_keys(source_file, func_name)):
            value = funcs.get(key)
            if isinstance(value, dict):
                matched = _merge_patch(matched, value)
        # Also accept non-normalized file keys by comparing their suffix / payload.
        for key, value in funcs.items():
            if key in keys or not isinstance(value, dict):
                continue
            key_text = str(key)
            if "::" in key_text:
                file_part, func_part = key_text.rsplit("::", 1)
                if _safe_text(func_part) != _safe_text(func_name):
                    continue
                if (
                    not file_part
                    or file_part in (".", "./")
                    or _norm_path(file_part) == _norm_path(source_file)
                    or os.path.basename(file_part) == os.path.basename(source_file)
                ):
                    matched = _merge_patch(matched, value)
                continue
            # Fallback: match by embedded function/file fields when key is opaque.
            if _patch_matches_item(value, source_file, func_name):
                matched = _merge_patch(matched, value)
    elif isinstance(funcs, list):
        for item in funcs:
            if isinstance(item, dict) and _patch_matches_item(item, source_file, func_name):
                matched = _merge_patch(matched, item)
    if matched:
        matched.setdefault("_matched_function", _safe_text(func_name))
    return matched


def _locked_name_items(patch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_map: dict[str, Any] = {}
    for key in ("locked_names", "names", "name_overrides"):
        value = patch.get(key) if isinstance(patch, dict) else None
        if isinstance(value, dict):
            raw_map.update(value)

    out: dict[str, dict[str, Any]] = {}
    for raw, value in raw_map.items():
        ident = _safe_text(raw)
        if not ident:
            continue
        if isinstance(value, dict):
            display = _safe_text(value.get("display") or value.get("cn_name") or value.get("name"))
            item = dict(value)
        else:
            display = _safe_text(value)
            item = {}
        if not display:
            continue
        item.update(
            {
                "raw": ident,
                "display": display,
                "kind": _safe_text(item.get("kind")) or "symbol",
                "source": _safe_text(item.get("source")) or "revision_profile",
                "confidence": float(item.get("confidence", 1.0) or 1.0),
                "locked": True,
            }
        )
        out[ident] = item
    return out


def _set_symbol_map_value(target: dict[str, Any], raw: str, display: str) -> None:
    if raw and display:
        target[raw] = display
        target[raw.replace("->", ".")] = display


def _apply_locked_names_to_semantic_pack(pack: dict[str, Any], locked: dict[str, dict[str, Any]]) -> None:
    if not isinstance(pack, dict) or not locked:
        return
    aliases = dict(pack.get("entity_aliases") or {})
    for raw, item in locked.items():
        _set_symbol_map_value(aliases, raw, item["display"])
    pack["entity_aliases"] = aliases

    for key in ("control_blocks", "state_updates", "call_roles", "return_actions", "flow_actions", "pattern_hits"):
        items = pack.get(key) or ()
        if not isinstance(items, (list, tuple)):
            continue
        for fact in items:
            if not isinstance(fact, dict):
                continue
            refs = []
            for ref in fact.get("name_refs") or ():
                if not isinstance(ref, dict):
                    refs.append(ref)
                    continue
                raw = _safe_text(ref.get("raw"))
                locked_item = locked.get(raw) or locked.get(raw.replace("->", "."))
                if locked_item:
                    new_ref = dict(ref)
                    new_ref.update(locked_item)
                    refs.append(new_ref)
                else:
                    refs.append(ref)
            if refs:
                fact["name_refs"] = tuple(refs)


def apply_revision_to_context(ctx: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    """Apply reviewer-locked names and title/description overrides to context."""

    if not isinstance(ctx, dict) or not isinstance(patch, dict) or not patch:
        return ctx

    ctx["_revision_patch"] = patch
    locked = _locked_name_items(patch)
    if locked:
        ctx["_revision_locked_names"] = locked
        var_cn_map = dict(ctx.get("var_cn_map") or {})
        param_ai_name_map = dict(ctx.get("param_ai_name_map") or {})
        global_symbol_map = dict(ctx.get("global_symbol_map") or {})
        file_context = dict(ctx.get("file_context") or {})
        file_symbol_map = dict(file_context.get("symbol_map") or {})
        member_symbol_map = dict(file_context.get("member_symbol_map") or {})
        entity_aliases = dict(ctx.get("entity_aliases") or {})

        for raw, item in locked.items():
            display = item["display"]
            _set_symbol_map_value(var_cn_map, raw, display)
            _set_symbol_map_value(param_ai_name_map, raw, display)
            _set_symbol_map_value(global_symbol_map, raw, display)
            _set_symbol_map_value(file_symbol_map, raw, display)
            _set_symbol_map_value(member_symbol_map, raw, display)
            _set_symbol_map_value(entity_aliases, raw, display)
            for local in ctx.get("local_vars") or ():
                if isinstance(local, dict) and _safe_text(local.get("name")) == raw:
                    local["cn_name"] = display
                    if _safe_text(item.get("usage")):
                        local["usage"] = _safe_text(item.get("usage"))

        file_context["symbol_map"] = file_symbol_map
        file_context["member_symbol_map"] = member_symbol_map
        ctx["file_context"] = file_context
        ctx["var_cn_map"] = var_cn_map
        ctx["param_ai_name_map"] = param_ai_name_map
        ctx["global_symbol_map"] = global_symbol_map
        ctx["entity_aliases"] = entity_aliases
        _apply_locked_names_to_semantic_pack(ctx.get("logic_semantic_pack") or {}, locked)

    comment_info = dict(ctx.get("comment_info") or {})
    func_title = _safe_text(patch.get("function_name") or patch.get("func_cn_name") or patch.get("title"))
    if func_title:
        comment_info["func_cn_name"] = func_title
    desc = _safe_text(patch.get("description") or patch.get("function_desc") or patch.get("desc"))
    if desc:
        comment_info["desc"] = desc
    return_desc = _safe_text(patch.get("return_desc"))
    if return_desc:
        comment_info["return_desc"] = return_desc
    if comment_info:
        ctx["comment_info"] = comment_info
    return ctx


def _normalize_logic_line(text: str) -> str:
    raw = str(text or "").expandtabs(4).rstrip()
    if not raw.strip():
        return ""
    indent = raw[: len(raw) - len(raw.lstrip(" "))]
    value = raw.lstrip(" ")
    control = re.match(
        r"^(?:IF\b|ELSE(?:\s+IF\b)?|FOR\b|WHILE\b|DO\s+WHILE\b|"
        r"SWITCH\b|CASE\b|DEFAULT\b|END\s+(?:IF|WHILE|DO\s+WHILE|SWITCH)\b|NEXT\b)",
        value,
    )
    if control:
        return indent + re.sub(r"[；;。]+$", "", value).rstrip()
    if value.endswith(("；", "。", "：", ":", ";")):
        value = value[:-1].rstrip() + "；" if value.endswith(";") else value
        return indent + value
    return indent + value + "；"


def _normalize_logic_structure(lines: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(line for line in (_normalize_logic_line(item) for item in lines) if line)
    if not normalized:
        return ()
    try:
        from .logic import _validate_control_blocks

        return tuple(_validate_control_blocks(normalized))
    except Exception:
        return normalized


def _replacement_matches(line: str, rule: dict[str, Any], index: int) -> bool:
    if not isinstance(rule, dict):
        return False
    if "index" in rule:
        try:
            if index != int(rule.get("index")):
                return False
        except Exception:
            return False
    if "line" in rule:
        try:
            if index + 1 != int(rule.get("line")):
                return False
        except Exception:
            return False
    contains = _safe_text(rule.get("contains"))
    if contains and contains not in line:
        return False
    regex = _safe_text(rule.get("regex") or rule.get("pattern"))
    if regex:
        try:
            if not re.search(regex, line):
                return False
        except re.error:
            return False
    return bool(contains or regex or "index" in rule or "line" in rule)


def _replacement_text(rule: dict[str, Any]) -> str:
    for key in ("replace", "replacement", "text", "with"):
        if key in rule:
            return _safe_text(rule.get(key))
    return ""


def apply_revision_to_logic_lines(logic_lines: Sequence[str] | None, patch: dict[str, Any] | None) -> tuple[str, ...] | None:
    """Apply line-level reviewer feedback to generated logic statements."""

    if not isinstance(patch, dict) or not patch:
        return tuple(logic_lines or ()) if logic_lines is not None else None
    if "logic_lines" in patch or "logic_override" in patch:
        override = patch.get("logic_lines", patch.get("logic_override"))
        return _normalize_logic_structure(_as_logic_text_list(override))

    lines = [_safe_text(line) for line in (logic_lines or ()) if _safe_text(line)]
    for rule in _as_list(patch.get("logic_replacements") or patch.get("logic_line_replacements")):
        if not isinstance(rule, dict):
            continue
        next_lines: list[str] = []
        for idx, line in enumerate(lines):
            if _replacement_matches(line, rule, idx):
                if bool(rule.get("delete")):
                    continue
                replacement = _replacement_text(rule)
                if not replacement:
                    continue
                next_lines.append(_normalize_logic_line(replacement))
            else:
                next_lines.append(line)
        lines = next_lines

    for contains in _as_text_list(patch.get("logic_delete_contains")):
        lines = [line for line in lines if contains not in line]

    prepend = [_normalize_logic_line(line) for line in _as_text_list(patch.get("logic_prepend"))]
    append = [_normalize_logic_line(line) for line in _as_text_list(patch.get("logic_append") or patch.get("logic_additions"))]
    lines = prepend + lines + append
    return _normalize_logic_structure(line for line in lines if _safe_text(line))


def apply_revision_to_design(design: Any, patch: dict[str, Any] | None) -> Any:
    """Reapply reviewer-locked values after automatic text normalization."""

    if design is None or not isinstance(patch, dict) or not patch:
        return design
    changes: dict[str, Any] = {}
    title = _safe_text(patch.get("function_name") or patch.get("func_cn_name") or patch.get("title"))
    if title:
        changes["title"] = title
    if any(key in patch for key in ("description", "function_desc", "desc")):
        description = _safe_text(patch.get("description") or patch.get("function_desc") or patch.get("desc"))
        changes["description_lines"] = tuple(line.strip() for line in description.splitlines() if line.strip())

    locked = _locked_name_items(patch)
    if locked:
        io_items = []
        for item in tuple(getattr(design, "io_elements", ()) or ()):
            locked_item = locked.get(_safe_text(getattr(item, "ident", "")))
            io_items.append(replace(item, name=locked_item["display"]) if locked_item else item)
        changes["io_elements"] = tuple(io_items)

        local_items = []
        for item in tuple(getattr(design, "local_elements", ()) or ()):
            locked_item = locked.get(_safe_text(getattr(item, "ident", "")))
            if not locked_item:
                local_items.append(item)
                continue
            values = {"name": locked_item["display"]}
            usage = _safe_text(locked_item.get("usage"))
            if usage:
                values["usage"] = usage
            local_items.append(replace(item, **values))
        changes["local_elements"] = tuple(local_items) if getattr(design, "local_elements", None) is not None else None

    if "logic_lines" in patch or "logic_override" in patch:
        changes["logic_lines"] = apply_revision_to_logic_lines(getattr(design, "logic_lines", None), patch)
    return replace(design, **changes) if changes else design


def find_golden_expectations(profile: dict[str, Any], source_file: str, func_name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(profile, dict):
        return ()
    out: list[dict[str, Any]] = []
    for item in profile.get("golden") or profile.get("golden_samples") or ():
        if isinstance(item, dict) and _patch_matches_item(item, source_file, func_name):
            out.append(dict(item))
    return tuple(out)


def audit_golden_text(text: str, expectations: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    issues: list[dict[str, Any]] = []
    haystack = str(text or "")
    for item in expectations or ():
        label = _safe_text(item.get("name") or item.get("function") or item.get("func_name")) or "golden"
        for needle in _as_text_list(item.get("must_contain")):
            if needle not in haystack:
                issues.append(
                    {
                        "code": "golden_must_contain_missing",
                        "severity": "error",
                        "message": needle,
                        "scope": label,
                    }
                )
        for needle in _as_text_list(item.get("must_not_contain")):
            if needle in haystack:
                issues.append(
                    {
                        "code": "golden_must_not_contain_hit",
                        "severity": "error",
                        "message": needle,
                        "scope": label,
                    }
                )
    return tuple(issues)


__all__ = [
    "apply_revision_to_context",
    "apply_revision_to_design",
    "apply_revision_to_logic_lines",
    "audit_golden_text",
    "find_function_patch",
    "find_golden_expectations",
    "load_revision_profile",
]
