"""Parsing and file-context helpers for AutoDocGen."""

from __future__ import annotations

from dataclasses import asdict
import glob
import os
import re
from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import scanner as scanner_utils
from . import utils as utils_module
from . import text as text_utils
from .models import CommentHint, FileContext, FunctionContext
from .comment_normalizer import normalize_comment_block


_HEADER_INDEX_CACHE: dict[str, tuple[float, dict[str, list[str]]]] = {}
_HEADER_SYMBOL_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_HEADER_TYPEDEF_CACHE: dict[str, tuple[float, list[str]]] = {}
_HEADER_MEMBER_MAP_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_SYMBOL_MAP_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_RELATED_TYPEDEF_CACHE: dict[str, tuple[float, list[str], dict[str, str]]] = {}
_C_FILE_PARSE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_C_FILE_SCAN_CACHE: dict[str, tuple[float, bool, bool]] = {}

_FAST_FUNC_RE = re.compile(
    r"([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{",
    re.MULTILINE,
)
_FAST_COMMENT_RE = re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE)

_LOGIC_LABEL_ACTION_PREFIXES = (
    "读取", "判断", "检查", "获取", "更新", "计算", "清除", "设置", "写入",
    "拷贝", "比较", "确认", "处理", "执行", "检测", "刷新", "发送", "接收",
)
_LOGIC_LABEL_PURPOSE_MARKERS = ("用于", "以便", "供", "表示", "表示为", "默认", "注意", "说明", "例如", "如下")


def _looks_like_placeholder_desc(text: Any, *, func_name: str = "") -> bool:
    value = utils_module._safe_strip(text)
    if not value:
        return True
    compact = re.sub(r"\s+", "", value)
    name = utils_module._safe_strip(func_name)
    if re.match(r"^【?说明】?\s*[:：]", value):
        return True
    if name and compact.strip(":：") == name:
        return True
    if name and re.fullmatch(rf"【?说明】?[:：]?{re.escape(name)}", compact):
        return True
    return False


def _strip_comment_markup(line: Any) -> str:
    value = utils_module._safe_strip(line)
    value = re.sub(r"^/\*+", "", value)
    value = re.sub(r"\*/$", "", value)
    value = re.sub(r"^\*+", "", value).strip()
    value = re.sub(r"^[：:]\s*", "", value).strip()
    return value


def _looks_like_descriptive_comment_line(text: str) -> bool:
    value = utils_module._safe_strip(text)
    if not value:
        return False
    if _looks_like_placeholder_desc(value):
        return False
    if re.match(r"^(?:输入参数|输出参数|其他说明|返回|返回值|函数名|函数名称|参数)\s*[:：]", value):
        return False
    if re.match(r"^(?:\[(?:输入参数|输出参数|其他说明|返回|返回值|函数名|函数名称|参数)\]|【(?:输入参数|输出参数|其他说明|返回|返回值|函数名|函数名称|参数)】)", value):
        return False
    if re.match(r"^[A-Za-z_]\w*\s*[：:]\s*$", value):
        return False
    if re.fullmatch(r"[A-Za-z_]\w*", value):
        return False
    return text_utils._contains_cjk(value)


def extract_effective_comment_desc(raw_comment: Any, *, parsed_desc: str = "", func_name: str = "") -> str:
    """Return the actionable description from a C comment block.

    Many legacy comments use the first desc line as a placeholder like
    "【说明】:SciConfig" and place the real Chinese description on following
    free-text lines.  Downstream call-role logic needs the real description,
    not the placeholder label.
    """
    parsed = utils_module._safe_strip(parsed_desc)
    if parsed and not _looks_like_placeholder_desc(parsed, func_name=func_name):
        return parsed
    raw = str(raw_comment or "")
    if not raw and parsed:
        return ""
    candidates: list[str] = []
    for line in raw.splitlines():
        value = _strip_comment_markup(line)
        value = re.sub(
            r"^(?:\[(?:功能描述|功能说明|功能|说明)\]|【(?:功能描述|功能说明|功能|说明)】)\s*[:：]?\s*",
            "",
            value,
        ).strip()
        value = re.sub(r"[。；;]+$", "", value).strip()
        if not _looks_like_descriptive_comment_line(value):
            continue
        candidates.append(value)
    if candidates:
        return candidates[0]
    return "" if _looks_like_placeholder_desc(parsed, func_name=func_name) else parsed


def _stop_requested(cfg: Optional[Any]) -> bool:
    return bool(cfg is not None and utils_module.stop_requested(cfg))


def _normalize_file_context(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    backend = legacy_backend()
    ctx = dict(raw or {})
    normalized = FileContext(
        source_file=utils_module._safe_strip(ctx.get("source_file")),
        module_key=utils_module._safe_strip(ctx.get("module_key")),
        family_prefix=utils_module._safe_strip(ctx.get("family_prefix")),
        glossary=dict(ctx.get("glossary") or {}),
        func_cn_map=dict(ctx.get("func_cn_map") or {}),
        symbol_map=dict(ctx.get("symbol_map") or {}),
        member_symbol_map=dict(ctx.get("member_symbol_map") or {}),
        variable_type_map=dict(ctx.get("variable_type_map") or {}),
        typedefs=list(ctx.get("typedefs") or []),
        header_typedefs=list(ctx.get("header_typedefs") or []),
        macros=list(ctx.get("macros") or []),
        neighbor_prototypes=list(ctx.get("neighbor_prototypes") or []),
        neighbor_func_names=list(ctx.get("neighbor_func_names") or []),
        callee_funcs=list(ctx.get("callee_funcs") or []),
        caller_funcs=list(ctx.get("caller_funcs") or []),
        codegraph_status=dict(ctx.get("codegraph_status") or {}),
        codegraph_node=dict(ctx.get("codegraph_node") or {}),
        codegraph_callers=list(ctx.get("codegraph_callers") or []),
        codegraph_callees=list(ctx.get("codegraph_callees") or []),
        codegraph_impact=list(ctx.get("codegraph_impact") or []),
    )
    return asdict(normalized)


def _normalize_func_entry(entry: dict[str, Any]) -> dict[str, Any]:
    item = dict(entry or {})
    item["file_context"] = _normalize_file_context(item.get("file_context") or {})
    return item


def build_function_context(func_data: dict[str, Any]) -> FunctionContext:
    backend = legacy_backend()
    func_info = dict((func_data or {}).get("func_info") or {})
    comment_info = dict((func_data or {}).get("comment_info") or {})
    file_context = _normalize_file_context((func_data or {}).get("file_context") or {})
    return FunctionContext(
        func_name=utils_module._safe_strip(func_info.get("func_name")),
        prototype=utils_module._safe_strip(func_info.get("prototype")),
        ret_type=utils_module._safe_strip(func_info.get("ret_type")),
        comment_info=comment_info,
        file_context=FileContext(**file_context),
        body=utils_module._safe_text((func_data or {}).get("body")),
    )


def _build_func_cn_map(func_list: list[dict[str, Any]], *, cfg: Optional[Any] = None) -> dict[str, str]:
    backend = legacy_backend()
    from . import naming as naming_utils

    out: dict[str, str] = {}
    for item in func_list or []:
        func_info = dict((item or {}).get("func_info") or {})
        func_name = utils_module._safe_strip(func_info.get("func_name"))
        if not func_name:
            continue
        if cfg is not None and _stop_requested(cfg):
            break
        cn_name = naming_utils.get_function_chinese_name(
            item.get("comment_info") or {},
            func_info,
            resolve_canonical_name=backend.resolve_canonical_symbol_name,
        )
        if cn_name and cn_name != func_name:
            out[func_name] = cn_name
    return out


def _clone_func_item(item: dict, file_context_extra: Optional[dict[str, Any]] = None) -> dict:
    file_context = dict((item or {}).get("file_context") or {})
    if file_context_extra:
        file_context.update(file_context_extra)
    return _normalize_func_entry(
        {
            "comment_info": dict((item or {}).get("comment_info") or {}),
            "func_info": dict((item or {}).get("func_info") or {}),
            "body": (item or {}).get("body") or "",
            "file_context": file_context,
        }
    )


def _parse_c_file_base(code: str, cfg: Optional[Any] = None) -> list[dict]:
    backend = legacy_backend()
    active_code = backend._strip_inactive_preprocessor_regions_keep_layout(code)
    comments = _find_all_comment_blocks(active_code)
    funcs = find_function_prototypes(active_code)
    _cross_check_tree_sitter_functions(active_code, funcs, cfg)

    # Build call graph via tree-sitter for richer neighbor info
    callers_map: dict[str, list[str]] = {}
    callees_map: dict[str, list[str]] = {}
    try:
        from . import callgraph as cgmod
        cg = cgmod.build_call_graph(code)
        if cg:
            for name, fd in cg.functions.items():
                callees_map[name] = fd.calls
            for name, fd in cg.functions.items():
                for callee in fd.calls:
                    callers_map.setdefault(callee, []).append(name)
    except Exception:
        pass

    results = []
    for idx, func_info in enumerate(funcs):
        nearest = _select_preceding_function_comment(comments, active_code, func_info["start"])

        brace_index = active_code.find("{", func_info["end"] - 1)
        body = extract_function_body(active_code, brace_index) if brace_index != -1 else ""

        func_name = utils_module._safe_strip(func_info.get("func_name"))
        prev_proto = funcs[idx - 1]["prototype"] if idx > 0 else ""
        next_proto = funcs[idx + 1]["prototype"] if idx + 1 < len(funcs) else ""
        file_context = {
            "typedefs": extract_nearby_typedefs(active_code, func_info["start"]),
            "macros": extract_nearby_macros(active_code, func_info["start"]),
            "neighbor_prototypes": [p for p in (prev_proto, next_proto) if p],
            "neighbor_func_names": [
                utils_module._safe_strip((funcs[idx - 1] or {}).get("func_name")) if idx > 0 else "",
                utils_module._safe_strip((funcs[idx + 1] or {}).get("func_name")) if idx + 1 < len(funcs) else "",
            ],
            "glossary": backend.DOMAIN_GLOSSARY,
            "callee_funcs": callees_map.get(func_name, []),
            "caller_funcs": callers_map.get(func_name, []),
        }
        results.append(
            {
                "comment_info": nearest["parsed"] if nearest and any((nearest.get("parsed") or {}).values()) else {},
                "func_info": func_info,
                "body": body,
                "file_context": file_context,
            }
        )
    return results


def _has_parsed_comment_content(parsed: Optional[dict[str, Any]]) -> bool:
    return any(utils_module._safe_strip(value) for value in (parsed or {}).values())


def _strip_param_identifier_prefixes(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        cleaned = utils_module._safe_strip(line)
        if _is_non_semantic_comment(cleaned):
            lines.append(cleaned)
            continue
        cleaned = re.sub(r"^[A-Za-z_]\w*\s*(?:[-—]{2,}|[:：])\s*", "", cleaned).strip()
        lines.append(cleaned)
    return "\n".join(line for line in lines if line)


def _function_comment_semantic_filter_text(parsed: dict[str, Any]) -> str:
    desc = utils_module._safe_strip((parsed or {}).get("desc"))
    if desc:
        return desc

    parts = []
    for key in ("other_desc", "return_desc"):
        value = utils_module._safe_strip((parsed or {}).get(key))
        if value:
            parts.append(value)
    for key in ("input_desc", "output_desc"):
        value = _strip_param_identifier_prefixes(utils_module._safe_strip((parsed or {}).get(key)))
        if value:
            parts.append(value)
    return "\n".join(parts)


def _gap_contains_only_comments_or_whitespace(text: str) -> bool:
    if not text:
        return True
    stripped = re.sub(r"/\*{1,2}[\s\S]*?\*/", "", text)
    stripped = re.sub(r"//[^\n]*", "", stripped)
    return not stripped.strip()


def _select_preceding_function_comment(
    comments: list[dict[str, Any]],
    code: str,
    func_start: int,
    *,
    max_gap_lines: int = 120,
) -> Optional[dict[str, Any]]:
    for comment in reversed([item for item in comments if int(item.get("end", 0)) <= func_start]):
        gap = code[int(comment.get("end", 0)):func_start]
        if gap.count("\n") > max_gap_lines:
            break
        if not _gap_contains_only_comments_or_whitespace(gap):
            break
        parsed = dict(comment.get("parsed") or {})
        if not _has_parsed_comment_content(parsed):
            continue
        semantic_text = _function_comment_semantic_filter_text(parsed)
        filter_text = semantic_text or "\n".join(
            utils_module._safe_strip(value) for value in parsed.values() if utils_module._safe_strip(value)
        )
        if filter_text and _is_non_semantic_comment(filter_text):
            continue
        return comment
    return None


def associate_comments_and_functions(code: str, file_context_extra: Optional[dict[str, Any]] = None):
    base = _parse_c_file_base(code)
    return [_clone_func_item(item, file_context_extra) for item in base]


def get_cached_func_list_for_c_file(*args, **kwargs):
    c_path = args[0] if args else kwargs.get("c_path", "")
    code = args[1] if len(args) > 1 else kwargs.get("code", "")
    file_context_extra = args[2] if len(args) > 2 else kwargs.get("file_context_extra")
    ap = os.path.abspath(c_path or "")
    if not ap:
        return associate_comments_and_functions(code, file_context_extra=file_context_extra)
    mtime = _get_file_mtime(ap)
    cached = _C_FILE_PARSE_CACHE.get(ap)
    if cached and cached[0] == mtime:
        base = cached[1]
    else:
        base = _parse_c_file_base(code, cfg=kwargs.get("cfg"))
        _C_FILE_PARSE_CACHE[ap] = (mtime, base)
    return [_clone_func_item(item, file_context_extra) for item in base]


def prepare_func_list_for_c_file(*args, **kwargs):
    backend = legacy_backend()
    from . import semantic as semantic_utils

    c_path = args[0] if args else kwargs.get("c_path", "")
    project_root = kwargs.get("project_root", args[1] if len(args) > 1 else None)
    cfg = kwargs.get("cfg", args[2] if len(args) > 2 else None)
    prefilter = kwargs.get("prefilter", args[3] if len(args) > 3 else False)
    need_symbol_map = kwargs.get("need_symbol_map", True)

    code = backend.load_c_file(c_path)
    if prefilter:
        has_func, has_comment = _get_cached_scan_result(c_path, code)
        if not has_func:
            return [], "no_func"
        if not has_comment:
            return [], "no_comment"

    symbol_map = {}
    header_typedefs: list[str] = []
    header_member_symbol_map: dict[str, str] = {}
    if _stop_requested(cfg):
        need_symbol_map = False
    if need_symbol_map:
        symbol_map = build_global_symbol_map_for_c_file(
            c_path,
            code,
            project_root=project_root,
            cfg=cfg,
        )
    try:
        if not _stop_requested(cfg):
            header_typedefs, header_member_symbol_map = build_related_header_context_for_c_file(
                c_path,
                code,
                project_root,
                cfg,
            )
    except Exception:
        header_typedefs, header_member_symbol_map = [], {}

    # Enrich member_symbol_map via tree-sitter struct parsing of header typedefs
    try:
        from . import struct_tree as stmod
        ts_members = stmod.build_member_symbol_map("\n\n".join(header_typedefs))
        header_member_symbol_map.update(ts_members)
    except Exception:
        pass

    func_list = get_cached_func_list_for_c_file(
        c_path,
        code,
        file_context_extra={
            "symbol_map": symbol_map,
            "header_typedefs": list(header_typedefs),
            "member_symbol_map": dict(header_member_symbol_map),
        },
        cfg=cfg,
    )
    source_file = os.path.abspath(c_path)
    module_key = backend._module_key_for_source(source_file)
    for item in func_list:
        func_info = item.get("func_info") or {}
        ctx = dict(item.get("file_context") or {})
        merged_typedefs: list[str] = []
        for block in list(ctx.get("typedefs") or []) + list(header_typedefs or []):
            text = utils_module._safe_strip(block)
            if text and text not in merged_typedefs:
                merged_typedefs.append(text)
        ctx["source_file"] = source_file
        ctx["module_key"] = module_key
        ctx["family_prefix"] = backend._identifier_family_prefix(utils_module._safe_strip(func_info.get("func_name")))
        ctx["typedefs"] = merged_typedefs[:18]
        ctx["member_symbol_map"] = dict(header_member_symbol_map or {})
        ctx["glossary"] = semantic_utils.build_project_glossary(
            file_symbols=ctx.get("symbol_map") or {},
            backend_module=backend,
        )
        item["file_context"] = ctx
    func_cn_map = _build_func_cn_map(func_list, cfg=cfg)
    func_comment_map: dict[str, str] = {}
    for item in func_list:
        func_info = dict((item or {}).get("func_info") or {})
        comment_info = dict((item or {}).get("comment_info") or {})
        name = utils_module._safe_strip(func_info.get("func_name"))
        desc = extract_effective_comment_desc(
            comment_info.get("raw") or comment_info.get("comment") or comment_info.get("block") or "",
            parsed_desc=utils_module._safe_strip(comment_info.get("desc")),
            func_name=name,
        )
        if name and desc:
            func_comment_map[name] = desc
    if func_cn_map:
        for item in func_list:
            ctx = dict(item.get("file_context") or {})
            merged = dict(ctx.get("symbol_map") or {})
            merged.update(func_cn_map)
            ctx["symbol_map"] = merged
            ctx["func_cn_map"] = func_cn_map
            ctx["func_comment_map"] = dict(func_comment_map)
            ctx["glossary"] = semantic_utils.build_project_glossary(
                file_symbols=merged,
                backend_module=backend,
            )
            item["file_context"] = ctx
    elif func_comment_map:
        for item in func_list:
            ctx = dict(item.get("file_context") or {})
            ctx["func_comment_map"] = dict(func_comment_map)
            item["file_context"] = ctx
    if project_root and bool(getattr(cfg, "_codegraph_project_enabled", False)):
        try:
            from . import codegraph_adapter

            codegraph_adapter.enrich_function_entries(func_list, project_root, cfg)
        except Exception as exc:
            backend.vlog(cfg, f"[CodeGraph] 调用关系增强失败，已使用本地回退：{exc}")
    return func_list, None


def _get_file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def _extract_includes(code: str) -> list[str]:
    includes: list[str] = []
    for line in (code or "").splitlines():
        match = re.match(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', line)
        if not match:
            continue
        include = (match.group(1) or "").strip()
        if include.lower().endswith(".h"):
            includes.append(include)
    return includes


def _quick_scan_c_code(code: str) -> tuple[bool, bool]:
    backend = legacy_backend()
    if not code:
        return False, False
    active_code = backend._strip_inactive_preprocessor_regions_keep_layout(code)
    sanitized = backend._strip_c_comments_keep_layout(active_code)
    return bool(_FAST_FUNC_RE.search(sanitized)), bool(find_comment_blocks(active_code))


def _get_cached_scan_result(c_path: str, code: str) -> tuple[bool, bool]:
    if not c_path:
        return _quick_scan_c_code(code)
    ap = os.path.abspath(c_path)
    mtime = _get_file_mtime(ap)
    cached = _C_FILE_SCAN_CACHE.get(ap)
    if cached and cached[0] == mtime:
        return cached[1], cached[2]
    has_func, has_comment = _quick_scan_c_code(code)
    _C_FILE_SCAN_CACHE[ap] = (mtime, has_func, has_comment)
    return has_func, has_comment


_TS_C_PARSER = None
_TS_C_PARSER_READY = False


def _get_tree_sitter_c_parser():
    global _TS_C_PARSER, _TS_C_PARSER_READY
    if _TS_C_PARSER_READY:
        return _TS_C_PARSER
    _TS_C_PARSER_READY = True
    try:
        from .tree_sitter_compat import create_c_parser

        _TS_C_PARSER = create_c_parser()
    except Exception:
        _TS_C_PARSER = None
    return _TS_C_PARSER


def _node_text(source_bytes: bytes, node) -> str:
    try:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""


def _find_descendant_by_type(node, node_type: str):
    stack = [node]
    while stack:
        current = stack.pop()
        if getattr(current, "type", "") == node_type:
            return current
        stack.extend(reversed(getattr(current, "children", []) or []))
    return None


def _find_descendants_by_type(node, node_type: str) -> list[Any]:
    out: list[Any] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if getattr(current, "type", "") == node_type:
            out.append(current)
        stack.extend(getattr(current, "children", []) or [])
    return out


def _extract_tree_sitter_functions(code: str) -> list[dict[str, Any]]:
    parser = _get_tree_sitter_c_parser()
    if parser is None:
        return []
    source_bytes = (code or "").encode("utf-8", errors="replace")
    try:
        tree = parser.parse(source_bytes)
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for node in _find_descendants_by_type(tree.root_node, "function_definition"):
        declarator = _find_descendant_by_type(node, "function_declarator")
        name_node = _find_descendant_by_type(declarator, "identifier") if declarator is not None else None
        if name_node is None:
            continue
        body_node = _find_descendant_by_type(node, "compound_statement")
        proto_end = body_node.start_byte if body_node is not None else node.end_byte
        prototype = re.sub(r"\s+", " ", source_bytes[node.start_byte:proto_end].decode("utf-8", errors="replace")).strip()
        out.append(
            {
                "func_name": _node_text(source_bytes, name_node).strip(),
                "start": int(node.start_byte),
                "end": int(node.end_byte),
                "start_line": int(node.start_point[0]) + 1,
                "end_line": int(node.end_point[0]) + 1,
                "prototype": prototype,
            }
        )
    return sorted(out, key=lambda item: int(item.get("start", 0)))


def _tree_sitter_cross_check_enabled(cfg: Optional[Any]) -> bool:
    if cfg is None:
        return False
    direct = getattr(cfg, "tree_sitter_cross_check", None)
    if direct is not None:
        return bool(direct)
    return bool(utils_module.cfg_get_int(cfg, "tree_sitter_cross_check", 0))


def _line_for_offset(code: str, offset: int) -> int:
    return (code or "")[: max(0, int(offset or 0))].count("\n") + 1


def _cross_check_tree_sitter_functions(code: str, regex_funcs: list[dict], cfg: Optional[Any]) -> list[str]:
    if not _tree_sitter_cross_check_enabled(cfg):
        return []
    messages: list[str] = []
    try:
        ts_funcs = _extract_tree_sitter_functions(code)
        if not ts_funcs:
            return []

        regex_by_name = {utils_module._safe_strip(item.get("func_name")): item for item in (regex_funcs or []) if item.get("func_name")}
        ts_by_name = {utils_module._safe_strip(item.get("func_name")): item for item in ts_funcs if item.get("func_name")}

        for name in sorted(set(ts_by_name) - set(regex_by_name)):
            messages.append(f"[tree_sitter_cross_check] regex missed function: {name}")
        for name in sorted(set(regex_by_name) - set(ts_by_name)):
            messages.append(f"[tree_sitter_cross_check] tree-sitter missed function: {name}")

        for name in sorted(set(regex_by_name) & set(ts_by_name)):
            regex_line = _line_for_offset(code, int(regex_by_name[name].get("start", 0)))
            ts_line = int(ts_by_name[name].get("start_line", 0) or 0)
            if abs(regex_line - ts_line) > 1:
                messages.append(
                    f"[tree_sitter_cross_check] span mismatch: {name} regex_line={regex_line} tree_sitter_line={ts_line}"
                )
    except Exception as exc:
        messages.append(f"[tree_sitter_cross_check] unavailable: {exc!r}")

    for message in messages:
        try:
            utils_module.vlog(cfg, message)
        except Exception:
            pass
    return messages


def _build_header_index(root_dir: str, exclude_dirs: Optional[list[str]] = None, cfg: Optional[Any] = None) -> dict[str, list[str]]:
    backend = legacy_backend()
    index: dict[str, list[str]] = {}
    if not root_dir or not os.path.isdir(root_dir):
        return index
    for dirpath, _, files in scanner_utils.walk_filtered(root_dir, exclude_dirs=exclude_dirs):
        if _stop_requested(cfg):
            return index
        for filename in files:
            if _stop_requested(cfg):
                return index
            if not filename.lower().endswith(".h"):
                continue
            key = filename.lower()
            index.setdefault(key, []).append(os.path.join(dirpath, filename))
    for key in list(index.keys()):
        index[key] = sorted(set(index[key]))
    return index


def _get_header_index(root_dir: str, exclude_dirs: Optional[list[str]] = None, cfg: Optional[Any] = None) -> dict[str, list[str]]:
    excludes = tuple(sorted({str(item).strip().lower() for item in (exclude_dirs or []) if str(item).strip()}))
    root_abs = os.path.abspath(root_dir or "")
    cache_key = root_abs + "|ex=" + ",".join(excludes)
    root_mtime = _get_file_mtime(root_abs)
    cached = _HEADER_INDEX_CACHE.get(cache_key)
    if cached and cached[0] == root_mtime:
        return cached[1]
    index = _build_header_index(root_abs, exclude_dirs=exclude_dirs, cfg=cfg)
    _HEADER_INDEX_CACHE[cache_key] = (root_mtime, index)
    return index


def _split_code_and_comments_for_symbol(line: str) -> tuple[str, list[str]]:
    tmp = line or ""
    block_comments = re.findall(r"/\*\s*(.*?)\s*\*/", tmp)
    block_comments = [comment.strip() for comment in block_comments if comment and comment.strip()]
    tmp = re.sub(r"/\*.*?\*/", "", tmp)

    line_comment = None
    match = re.search(r"//(.*)", tmp)
    if match:
        line_comment = (match.group(1) or "").strip()
        tmp = tmp[:match.start()]

    comments = block_comments[:]
    if line_comment:
        comments.append(line_comment)
    return tmp.strip(), comments


def _join_c_line_continuations(text: str) -> str:
    if not text:
        return text
    out: list[str] = []
    buf: Optional[str] = None
    for raw in (text or "").splitlines():
        line = raw if buf is None else raw.lstrip()
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            part = stripped[:-1].rstrip()
            buf = (buf or "") + part + " "
            continue
        if buf is not None:
            out.append(buf + line)
            buf = None
        else:
            out.append(line)
    if buf is not None:
        out.append(buf.rstrip())
    return "\n".join(out)


def _clean_symbol_comment_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^[\s\*<!/!]+", "", cleaned).strip()
    cleaned = re.sub(r"^@brief\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^brief\s*[:：]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\\brief\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _is_noop_comment(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (text or "").strip()).strip(" ;,，。")
    if not cleaned:
        return True
    upper = cleaned.upper()
    if upper in {"NO DEAL WITH", "NO DEAL", "NO ACTION", "NO OP", "NOOP", "NONE", "NULL"}:
        return True
    if cleaned in {"无操作", "不处理", "空操作", "无需处理", "无", "无动作"}:
        return True
    return False


def _looks_like_logic_noise_comment(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", _clean_symbol_comment_text(text)).strip(" ;,，。")
    if not cleaned:
        return True
    compact = re.sub(r"\s+", "", cleaned)
    lower = cleaned.lower()
    if re.search(r"\b(?:todo|fixme|tbd|xxx|zlh)\b", lower):
        return True
    if any(token in lower for token in ("ti file", "checkin", "$revision", "$release date", "ti release")):
        return True
    if any(token in compact for token in ("修改记录", "版本记录", "发布日期", "文件日期", "开发单位")):
        return True
    if re.search(r"20\d{2}[-/年.]\d{1,2}(?:[-/月.]\d{1,2})?", compact):
        return True
    return False



def _is_decorative_only_comment(text: str) -> bool:
    compact = re.sub(r"\s+", "", _clean_symbol_comment_text(text))
    return bool(compact) and bool(re.fullmatch(r"[*/\-_=#]+", compact))


def _is_non_semantic_comment(text: str) -> bool:
    return _is_decorative_only_comment(text) or _is_noop_comment(text) or _looks_like_logic_noise_comment(text)


def _looks_like_noise_symbol_comment(text: str) -> bool:
    backend = legacy_backend()
    s = _clean_symbol_comment_text(text)
    compact = re.sub(r"\s+", "", s)
    if not compact:
        return True
    if "//" in s or compact.count("/") >= 2:
        return True
    if re.search(r"[=;；:：]", compact) and not text_utils._contains_cjk(compact):
        return True
    if re.match(r"^[A-Za-z]?\d+(?:[A-Za-z_]\w*)?$", compact):
        return True
    if re.match(r"^[A-Za-z_]\w*//", compact):
        return True
    if not text_utils._contains_cjk(compact):
        return True
    if re.search(r"20\d{6,}", compact):
        return True
    if "改为" in compact or "非负载数据" in compact:
        return True
    if compact.count("，") + compact.count(",") >= 2:
        return True
    if len(compact) >= 18 and ("注释" in compact or "修改" in compact or "心跳字" in compact):
        return True
    return False

def _get_logic_comment_mode(cfg: Optional[Any]) -> str:
    backend = legacy_backend()
    mode = utils_module._safe_strip(getattr(cfg, "logic_comment_mode", "")).lower()
    use_comment = bool(getattr(cfg, "logic_use_comment", True))
    if mode == "legacy_inline":
        return mode
    if not use_comment:
        return "off"
    if mode in ("off", "hint_only"):
        return mode
    return "hint_only"


def classify_comment_hint(text: str):
    backend = legacy_backend()
    s = _clean_symbol_comment_text(text)
    s = re.sub(r"[。;；]+$", "", (s or "").strip())
    compact = re.sub(r"\s+", "", s)
    if (not s) or _is_non_semantic_comment(s):
        return CommentHint(kind="noise", text="", confidence=0.0)
    lower = s.lower()
    if any(token in lower for token in ("todo", "fixme", "testonly", "debug", "trace")):
        return CommentHint(kind="debug", text=s, confidence=0.92)
    if any(mark in compact for mark in backend._HISTORY_MARKERS) or re.search(r"20\d{2}", compact):
        return CommentHint(kind="history", text=s, confidence=0.92)
    if any(mark in compact for mark in backend._PURPOSE_MARKERS):
        return CommentHint(kind="purpose", text=s, confidence=0.88)
    if any(mark in compact for mark in ("仅在", "范围", "单位", "默认", "最大", "最小", "上限", "下限")):
        return CommentHint(kind="constraint", text=s, confidence=0.82)
    if any(mark in compact for mark in ("如果", "若", "当", "超时", "满足", "成立", "无效", "有效")):
        return CommentHint(kind="condition", text=s, confidence=0.78)
    normalized = _normalize_short_logic_label_comment(s)
    if normalized:
        conf = 0.84 if len(re.sub(r"\s+", "", normalized)) <= 10 else 0.72
        return CommentHint(kind="action", text=normalized, confidence=conf)
    return CommentHint(kind="condition", text=s, confidence=0.62)


def extract_statement_hints(code_line: str, comments: list[str]):
    _ = code_line
    hints = []
    for raw in (comments or []):
        hint = classify_comment_hint(raw)
        if hint.kind == "noise" or not hint.text:
            continue
        hints.append(hint)
    return hints


def _normalize_short_logic_label_comment(text: str, *, strip_action_prefix: bool = False) -> str:
    backend = legacy_backend()
    cleaned = _clean_symbol_comment_text(text)
    cleaned = re.sub(r"[。;；]+$", "", (cleaned or "").strip()).strip()
    if not cleaned or _is_non_semantic_comment(cleaned):
        return ""
    cleaned = re.split(r"[，,；;。]", cleaned, maxsplit=1)[0].strip()
    if not cleaned:
        return ""
    if strip_action_prefix:
        for verb in _LOGIC_LABEL_ACTION_PREFIXES:
            if cleaned.startswith(verb) and len(cleaned) > len(verb) + 1:
                cleaned = cleaned[len(verb):].strip()
                break
    compact = re.sub(r"\s+", "", cleaned)
    if not compact:
        return ""
    if any(mark in compact for mark in _LOGIC_LABEL_PURPOSE_MARKERS):
        return ""
    if len(compact) > 16:
        return ""
    if sum(compact.count(ch) for ch in "，,；;。:：") >= 1:
        return ""
    if re.search(r"[=\[\]\{\}<>]", compact):
        return ""
    if backend._looks_like_sentence_cn(compact):
        return ""
    return cleaned


def _shorten_header_cn_comment(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    bit_label = re.match(r"^bit\d+\s*[:：]\s*(.+)$", cleaned, flags=re.IGNORECASE)
    if bit_label:
        cleaned = bit_label.group(1).strip()
    compact_space = re.sub(r"\s+", "", cleaned)
    if re.match(r"^[A-Z]{2,8}[A-Z0-9]?[\u4e00-\u9fff]", compact_space):
        cleaned = compact_space
    cut = None
    for ch in (",", "，", " ", "\t"):
        idx = cleaned.find(ch)
        if idx >= 0:
            cut = idx if cut is None else min(cut, idx)
    if cut is None or cut <= 0:
        return cleaned
    out = cleaned[:cut].strip()
    return out or cleaned


def _normalize_header_comment_cn(cn_name: str, usage: str = "") -> str:
    backend = legacy_backend()
    primary = _shorten_header_cn_comment(cn_name)
    fallback = _shorten_header_cn_comment(usage)
    if re.fullmatch(r"\d+", primary):
        primary = fallback
    primary = re.sub(r"^\d+\s*[-:：]\s*", "", utils_module._safe_strip(primary))
    if re.fullmatch(r"\d+", primary):
        return ""
    return primary


def find_comment_blocks(code: str):
    return [item for item in _find_all_comment_blocks(code) if any((item.get("parsed") or {}).values())]


def _find_all_comment_blocks(code: str):
    blocks = []
    pattern = re.compile(r"/\*{1,2}([\s\S]*?)\*/", re.MULTILINE)
    for match in pattern.finditer(code or ""):
        raw = match.group(1)
        parsed = parse_single_comment_block(raw)
        blocks.append(
            {
                "start": match.start(),
                "end": match.end(),
                "raw": raw,
                "parsed": parsed,
            }
        )
    blocks.extend(_find_line_comment_blocks(code, include_unparsed=True))
    blocks.sort(key=lambda item: (int(item.get("start", 0)), int(item.get("end", 0))))
    return blocks


def parse_single_comment_block(raw: str) -> dict:
    normalized = normalize_comment_block(raw)
    return normalized.to_parse_dict()

def _parse_line_comment_block(raw_lines: list[str]) -> dict:
    lines: list[str] = []
    for raw in (raw_lines or []):
        s = str(raw or "").strip()
        s = re.sub(r"^\s*//+\s?", "", s).strip()
        if s:
            lines.append(s)
    if not lines:
        return {}

    text = "\n".join(lines)
    parsed = parse_single_comment_block(text)
    if any(parsed.values()):
        return parsed

    func_name = ""
    desc = ""
    for line in lines:
        stripped = line.strip().strip("-=:;,. ")
        if not stripped:
            continue
        match = re.match(r"^(?:Example\s*:\s*)?([A-Za-z_]\w*)\s*:?\s*$", stripped, re.IGNORECASE)
        if match:
            func_name = match.group(1).strip()
            continue
        if stripped.lower().startswith(("file:", "title:", "$ti ", "checkin ", "revision ")):
            continue
        if stripped.startswith(("//", "#")):
            continue
        if not desc:
            desc = stripped
    if desc:
        desc = re.sub(r"[。;；]+$", "", desc).strip()
    out = {
        "func_name": func_name,
        "func_cn_name": "",
        "desc": desc,
        "input_desc": "",
        "output_desc": "",
        "other_desc": "",
        "return_desc": "",
    }
    return out if any(out.values()) else {}


def _find_line_comment_blocks(code: str, *, include_unparsed: bool = False) -> list[dict]:
    if not code:
        return []
    blocks: list[dict] = []
    lines = code.splitlines(keepends=True)
    offset = 0
    pending_lines: list[str] = []
    pending_start: Optional[int] = None
    pending_end = 0

    def _flush() -> None:
        nonlocal pending_lines, pending_start, pending_end
        if not pending_lines or pending_start is None:
            pending_lines = []
            pending_start = None
            pending_end = 0
            return
        parsed = _parse_line_comment_block(pending_lines)
        if include_unparsed or any((parsed or {}).values()):
            blocks.append(
                {
                    "start": pending_start,
                    "end": pending_end,
                    "raw": "\n".join(pending_lines),
                    "parsed": parsed,
                }
            )
        pending_lines = []
        pending_start = None
        pending_end = 0

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if re.match(r"^\s*//", line):
            if pending_start is None:
                pending_start = offset
            pending_lines.append(line)
            pending_end = offset + len(raw_line)
        elif pending_lines and (not line.strip()):
            pending_lines.append(line)
            pending_end = offset + len(raw_line)
        else:
            _flush()
        offset += len(raw_line)
    _flush()
    return blocks


_FILE_HEADER_LABELS = (
    "模块名称",
    "模块名",
    "文件名称",
    "文件中文名",
    "中文文件名",
    "功能描述",
    "文件描述",
    "文件功能",
    "模块功能",
)


def _clean_comment_line(line: str) -> str:
    s = (line or "").strip()
    s = re.sub(r"^/\*+", "", s).strip()
    s = re.sub(r"^\*+", "", s).strip()
    return s


def _extract_file_header_info(code: str) -> dict[str, str]:
    backend = legacy_backend()
    if not code:
        return {}
    pattern = re.compile(r"/\*{1,2}([\s\S]*?)\*/", re.MULTILINE)
    for match in pattern.finditer(code):
        if match.start() > 2000:
            break
        raw = match.group(1)
        info: dict[str, str] = {}
        for line in (raw or "").splitlines():
            stripped = _clean_comment_line(line)
            if not stripped:
                continue
            m2 = re.match(r"\[(.+?)\]\s*(.*)", stripped)
            if m2:
                key = m2.group(1).strip()
                val = m2.group(2).strip()
                if key and val:
                    info[key] = val
                continue
            m3 = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", stripped)
            if m3:
                key = m3.group(1).strip()
                val = m3.group(2).strip()
                if key and val and text_utils._contains_cjk(key):
                    info[key] = val
        if info:
            return info
    return {}


def _extract_module_cn_from_header(code: str) -> str:
    backend = legacy_backend()
    info = _extract_file_header_info(code)
    if not info:
        return ""

    def _pick_cn_from_value(val: str) -> str:
        v = (val or "").strip()
        if not v:
            return ""
        paren = ""
        matches = re.findall(r"[\(（]\s*([^)）]+?)\s*[\)）]", v)
        if matches:
            paren = (matches[-1] or "").strip()
        if paren and (text_utils._contains_cjk(paren) or len(paren) >= 2):
            return paren
        if re.match(r"^[A-Za-z0-9_\-]+\.(c|h|cpp)$", v, re.IGNORECASE):
            return ""
        return v

    for key in _FILE_HEADER_LABELS:
        val = (info.get(key) or "").strip()
        if not val:
            continue
        if val.upper() in ("NONE", "N/A", "NA") or val in ("无", "None"):
            continue
        val = re.sub(r"[。;；]+$", "", val).strip()
        picked = _pick_cn_from_value(val)
        if picked:
            return picked
    return ""


def _derive_module_display_name(c_path: str, code: str) -> str:
    backend = legacy_backend()
    base = os.path.splitext(os.path.basename(c_path or ""))[0]
    header_cn = _extract_module_cn_from_header(code or "")
    if header_cn:
        return header_cn
    return backend._guess_cn_from_ident(base, glossary=backend.DOMAIN_GLOSSARY) or base


def _extract_symbol_map_from_header_code(header_code: str) -> dict[str, str]:
    backend = legacy_backend()
    symbol_map: dict[str, str] = {}
    pending_comments: list[str] = []
    stmt_skip_words = {
        "return", "goto", "case", "default", "break", "continue",
        "if", "else", "for", "while", "switch", "do",
    }
    enum_waiting_for_brace = False
    in_enum = False
    enum_balance = 0

    for raw in (header_code or "").splitlines():
        code, comments = _split_code_and_comments_for_symbol(raw)
        inline_comments = [_clean_symbol_comment_text(c) for c in comments if c and not _is_non_semantic_comment(c)]
        inline_comments = [c for c in inline_comments if c]
        core = (code or "").strip()

        if not in_enum:
            if enum_waiting_for_brace:
                if "{" in core:
                    in_enum = True
                    enum_waiting_for_brace = False
                    enum_balance = 0
            else:
                if re.search(r"\benum\b", core) and "{" in core:
                    in_enum = True
                    enum_balance = 0
                elif re.search(r"\benum\b", core):
                    enum_waiting_for_brace = True

        core_no_punct = re.sub(r"[{};]", "", core).strip()
        if not core_no_punct:
            if inline_comments:
                pending_comments.extend(inline_comments)
            if in_enum:
                enum_balance += core.count("{") - core.count("}")
                if enum_balance <= 0 and "}" in core:
                    in_enum = False
                    enum_balance = 0
            continue

        if core.lstrip().startswith("#"):
            match_def = re.match(r"^\s*#\s*define\s+(?P<name>[A-Za-z_]\w*)\b", core)
            if match_def:
                name = match_def.group("name")
                comment_text = ""
                if inline_comments:
                    comment_text = "；".join(inline_comments)
                    pending_comments = []
                elif pending_comments:
                    comment_text = "；".join(pending_comments)
                    pending_comments = []
                if comment_text:
                    cn, _ = backend._split_cn_name_and_usage_from_comment(comment_text)
                    cn = _normalize_header_comment_cn((cn or "").strip(), "")
                    if cn and cn != name and backend._should_keep_symbol_cn(name, cn):
                        symbol_map.setdefault(name, cn)
            else:
                pending_comments = []
            continue

        if in_enum:
            if not (re.search(r"\benum\b", core) or core.lstrip().startswith(("typedef", "}"))):
                for part in [p.strip() for p in core.split(",") if p.strip()]:
                    match_name = re.match(r"(?P<name>[A-Za-z_]\w*)\b", part)
                    if not match_name:
                        continue
                    name = match_name.group("name")
                    comment_text = ""
                    if inline_comments:
                        comment_text = "；".join(inline_comments)
                        pending_comments = []
                    elif pending_comments:
                        comment_text = "；".join(pending_comments)
                        pending_comments = []
                    if comment_text:
                        cn, _ = backend._split_cn_name_and_usage_from_comment(comment_text)
                        cn = _normalize_header_comment_cn((cn or "").strip(), "")
                        if cn and cn != name and backend._should_keep_symbol_cn(name, cn):
                            symbol_map.setdefault(name, cn)
            enum_balance += core.count("{") - core.count("}")
            if enum_balance <= 0 and "}" in core:
                in_enum = False
                enum_balance = 0
            continue

        if core.endswith(";") and "(" not in core:
            stmt = core[:-1].strip()
            if stmt.startswith(("typedef ", "struct ", "union ", "enum ", "}")) or ("{" in stmt) or ("}" in stmt):
                pending_comments = []
                continue
            stmt = re.sub(r"^\s*extern\s+", "", stmt)
            if stmt.startswith("typedef "):
                pending_comments = []
                continue
            left = stmt.split("=", 1)[0].strip()
            left = re.sub(r"\[[^\]]*\]", "", left).strip()
            if (not left) or left.startswith(("*", "&")) or ("->" in left) or ("." in left):
                pending_comments = []
                continue
            tokens = left.replace("*", " * ").split()
            if len(tokens) < 2:
                pending_comments = []
                continue
            name = tokens[-1].lstrip("*").strip()
            skip_words = {
                "extern", "static", "const", "volatile", "register",
                "struct", "union", "enum", "typedef",
                "unsigned", "signed", "short", "long", "int", "char", "float", "double", "void",
            }
            if (not name) or (name in skip_words):
                pending_comments = []
                continue
            if tokens and (tokens[0] in stmt_skip_words):
                pending_comments = []
                continue
            if not re.fullmatch(r"[A-Za-z_]\w*", name):
                pending_comments = []
                continue

            comment_text = ""
            if inline_comments:
                comment_text = "；".join(inline_comments)
                pending_comments = []
            elif pending_comments:
                comment_text = "；".join(pending_comments)
                pending_comments = []
            else:
                pending_comments = []
            if comment_text:
                cn, _ = backend._split_cn_name_and_usage_from_comment(comment_text)
                cn = _normalize_header_comment_cn((cn or "").strip(), "")
                if cn and cn != name and backend._should_keep_symbol_cn(name, cn):
                    symbol_map.setdefault(name, cn)
            continue

        pending_comments = []

    return symbol_map


def _extract_member_symbol_map_from_typedefs(typedef_blocks: list[str]) -> dict[str, str]:
    return _extract_member_symbol_map_from_header_code("\n\n".join(block for block in (typedef_blocks or []) if block))


def _composite_type_names_from_open(core: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"\b(?:struct|union|enum)\s+([A-Za-z_]\w*)", core or ""):
        name = utils_module._safe_strip(match.group(1))
        if name and name not in names:
            names.append(name)
    return names


def _composite_type_names_from_close(core: str) -> list[str]:
    if "}" not in (core or ""):
        return []
    tail = (core or "").split("}", 1)[1]
    tail = tail.split(";", 1)[0]
    names: list[str] = []
    for part in tail.split(","):
        part = re.sub(r"\[[^\]]*\]", "", part)
        idents = re.findall(r"\b[A-Za-z_]\w*\b", part)
        if not idents:
            continue
        name = idents[-1]
        if name and name not in names:
            names.append(name)
    return names


def _add_qualified_member_names(
    member_map: dict[str, str],
    type_names: list[str],
    members: list[tuple[str, str]],
) -> None:
    for type_name in type_names:
        type_key = utils_module._safe_strip(type_name)
        if not type_key:
            continue
        for member_name, cn_name in members:
            ident = utils_module._safe_strip(member_name)
            text = utils_module._safe_strip(cn_name)
            if ident and text:
                member_map.setdefault(f"{type_key}.{ident}", text)


def _extract_variable_type_map_from_code(code: str) -> dict[str, str]:
    type_map: dict[str, str] = {}
    scalar_types = {
        "void", "char", "short", "int", "long", "float", "double", "signed", "unsigned",
        "Uint8", "Uint16", "Uint32", "Uint64", "Sint8", "Sint16", "Sint32", "Sint64",
        "uint8_t", "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t",
    }
    storage_re = re.compile(r"^(?:(?:extern|static|const|volatile|register)\s+)+")
    for raw in (code or "").splitlines():
        core, _comments = _split_code_and_comments_for_symbol(raw)
        core = utils_module._safe_strip(core)
        if (
            not core
            or core.startswith("#")
            or not core.endswith(";")
            or "(" in core
            or "{" in core
            or "}" in core
            or core.startswith("typedef")
        ):
            continue
        stmt = core[:-1].strip()
        stmt = storage_re.sub("", stmt).strip()
        match = re.match(
            r"(?P<type>(?:struct|union|enum)\s+[A-Za-z_]\w*|[A-Za-z_]\w*)\s+(?P<decls>.+)$",
            stmt,
        )
        if not match:
            continue
        type_name = utils_module._safe_strip(match.group("type"))
        if (not type_name) or type_name in scalar_types:
            continue
        type_name = re.sub(r"^(?:struct|union|enum)\s+", "", type_name)
        for part in match.group("decls").split(","):
            item = part.split("=", 1)[0]
            item = re.sub(r"\[[^\]]*\]", "", item)
            item = item.replace("*", " ")
            idents = re.findall(r"\b[A-Za-z_]\w*\b", item)
            if not idents:
                continue
            name = idents[-1]
            if name and name not in scalar_types:
                type_map.setdefault(name, type_name)
    return type_map


def _expand_member_symbol_map_with_variable_types(
    member_map: dict[str, str],
    variable_type_map: dict[str, str],
) -> dict[str, str]:
    expanded = dict(member_map or {})
    for var_name, type_name in (variable_type_map or {}).items():
        var_key = utils_module._safe_strip(var_name)
        type_key = utils_module._safe_strip(type_name)
        if not var_key or not type_key:
            continue
        prefix = f"{type_key}."
        for key, value in list(member_map.items()):
            key_s = utils_module._safe_strip(key)
            if not key_s.startswith(prefix):
                continue
            member_name = key_s[len(prefix):]
            if member_name:
                expanded.setdefault(f"{var_key}.{member_name}", value)
    return expanded


def _extract_member_symbol_map_from_header_code(header_code: str) -> dict[str, str]:
    backend = legacy_backend()
    member_map: dict[str, str] = {}
    pending_comments: list[str] = []
    in_composite = False
    brace_depth = 0
    current_type_names: list[str] = []
    current_members: list[tuple[str, str]] = []

    def close_current_composite(core: str) -> None:
        nonlocal current_type_names, current_members
        closing_names = _composite_type_names_from_close(core)
        for type_name in closing_names:
            if type_name and type_name not in current_type_names:
                current_type_names.append(type_name)
        _add_qualified_member_names(member_map, current_type_names, current_members)
        current_type_names = []
        current_members = []

    for raw in (header_code or "").splitlines():
        code, comments = _split_code_and_comments_for_symbol(raw)
        inline_comments = [_clean_symbol_comment_text(c) for c in comments if c and not _is_non_semantic_comment(c)]
        inline_comments = [c for c in inline_comments if c]
        core = (code or "").strip()
        core_no_punct = re.sub(r"[{};]", "", core).strip()

        if not in_composite:
            if re.search(r"\b(?:struct|union|enum)\b", core) and "{" in core:
                in_composite = True
                brace_depth = core.count("{") - core.count("}")
                current_type_names = _composite_type_names_from_open(core)
                current_members = []
                if brace_depth <= 0:
                    close_current_composite(core)
                    in_composite = False
                    brace_depth = 0
                pending_comments = []
                continue
            if re.fullmatch(r"(?:typedef\s+)?(?:struct|union|enum)(?:\s+[A-Za-z_]\w*)?", core_no_punct):
                in_composite = True
                brace_depth = 0
                current_type_names = _composite_type_names_from_open(core)
                current_members = []
                pending_comments = []
                continue
            if not core_no_punct and inline_comments:
                pending_comments.extend(inline_comments)
            continue

        brace_depth += core.count("{") - core.count("}")
        if not core_no_punct:
            if inline_comments:
                pending_comments.extend(inline_comments)
            if brace_depth <= 0:
                close_current_composite(core)
                in_composite = False
                brace_depth = 0
                pending_comments = []
            continue

        if core.lstrip().startswith("}"):
            if brace_depth <= 0:
                close_current_composite(core)
                in_composite = False
                brace_depth = 0
            pending_comments = []
            continue

        if (not core.endswith(";")) or ("(" in core) or core.lstrip().startswith(("#", "typedef")):
            if brace_depth <= 0:
                close_current_composite(core)
                in_composite = False
                brace_depth = 0
            pending_comments = []
            continue

        stmt = core[:-1].strip()
        left = stmt.split("=", 1)[0].strip()
        left = left.split(":", 1)[0].strip()
        left = re.sub(r"\[[^\]]*\]", "", left)
        idents = re.findall(r"\b[A-Za-z_]\w*\b", left)
        if not idents:
            if brace_depth <= 0:
                in_composite = False
                brace_depth = 0
            pending_comments = []
            continue
        name = idents[-1]

        comment_text = ""
        if inline_comments:
            comment_text = "；".join(inline_comments)
            pending_comments = []
        elif pending_comments:
            comment_text = "；".join(pending_comments)
            pending_comments = []
        else:
            pending_comments = []

        if comment_text:
            cn, usage = backend._split_cn_name_and_usage_from_comment(comment_text)
            cn = _normalize_header_comment_cn(cn, usage)
            if not cn:
                cn = _normalize_header_comment_cn(re.split(r"[（(]", comment_text, maxsplit=1)[0], "")
            if cn and cn != name and backend._should_keep_symbol_cn(name, cn):
                member_map.setdefault(name, cn)
                current_members.append((name, cn))

        if brace_depth <= 0:
            close_current_composite(core)
            in_composite = False
            brace_depth = 0
            pending_comments = []

    return member_map


def _strip_function_bodies_keep_layout(code: str) -> str:
    backend = legacy_backend()
    if not code:
        return ""
    masked = code
    funcs = backend.find_function_prototypes(code or "")
    if not funcs:
        return masked
    for item in reversed(funcs):
        start = int((item or {}).get("start", 0) or 0)
        brace_index = masked.find("{", max(0, int((item or {}).get("end", 0) or 0) - 1))
        if brace_index < 0:
            continue
        depth = 0
        end_index = -1
        for idx in range(brace_index, len(masked)):
            ch = masked[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_index = idx
                    break
        if end_index < 0 or end_index < start:
            continue
        span = masked[start:end_index + 1]
        masked = masked[:start] + backend._mask_non_newline_chars(span) + masked[end_index + 1:]
    return masked


def find_function_prototypes(code: str):
    backend = legacy_backend()
    active_code = backend._strip_inactive_preprocessor_regions_keep_layout(code or "")
    sanitized_code = backend._strip_c_comments_keep_layout(active_code)
    sanitized_code = re.sub(
        r"^[ \t]*#.*$",
        lambda m: " " * len(m.group(0)),
        sanitized_code,
        flags=re.MULTILINE,
    )
    pattern = re.compile(
        r"([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{",
        re.MULTILINE,
    )
    funcs = []
    for match in pattern.finditer(sanitized_code):
        ret_type_raw = match.group(1).strip()
        func_name = match.group(2)
        if func_name in ("if", "for", "while", "switch"):
            continue
        if ret_type_raw in ("if", "for", "while", "switch", "else"):
            continue
        ret_type = " ".join(ret_type_raw.split())
        params = match.group(3).strip()
        prototype = f"{ret_type} {func_name}({params})"
        funcs.append(
            {
                "start": match.start(),
                "end": match.end(),
                "ret_type": ret_type,
                "func_name": func_name,
                "params": params,
                "prototype": prototype,
            }
        )
    return funcs


def extract_function_body(code: str, brace_start_index: int) -> str:
    depth = 0
    start_body = brace_start_index + 1
    for idx in range(brace_start_index, len(code)):
        ch = code[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return code[start_body:idx]
    return ""


def extract_nearby_typedefs(code: str, before_index: int, max_blocks: int = 3):
    blocks = []
    pattern = re.compile(r"(typedef\\s+(?:struct|union|enum)[\\s\\S]*?};)", re.MULTILINE)
    for match in pattern.finditer(code):
        if match.end() <= before_index:
            blocks.append(match.group(1).strip())
    return blocks[-max_blocks:]


def _extract_typedef_blocks_from_code(code: str, max_blocks: int = 24) -> list[str]:
    backend = legacy_backend()
    text = str(code or "")
    if not text:
        return []
    blocks: list[str] = []
    patterns = (
        re.compile(r"(typedef\s+(?:struct|union|enum)\b[\s\S]*?}\s*[A-Za-z_]\w*\s*;)", re.MULTILINE),
        re.compile(r"((?:struct|union|enum)\s+[A-Za-z_]\w*\s*\{[\s\S]*?};)", re.MULTILINE),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            block = utils_module._safe_strip(match.group(1))
            if block and block not in blocks:
                blocks.append(block)
                if len(blocks) >= max_blocks:
                    return blocks
    return blocks


def extract_nearby_macros(code: str, before_index: int, max_items: int = 6):
    lines_before = code[:before_index].splitlines()
    macros = [ln.strip() for ln in lines_before if re.match(r"^\\s*#define\\s+\\w+", ln)]
    return macros[-max_items:]


def _load_header_symbol_map(header_path: str, cfg) -> dict[str, str]:
    backend = legacy_backend()
    path = os.path.abspath(header_path or "")
    if not path:
        return {}
    mtime = _get_file_mtime(path)
    cached = _HEADER_SYMBOL_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        code = backend.load_c_file(path)
    except backend.SourceReadError:
        _HEADER_SYMBOL_CACHE[path] = (mtime, {})
        return {}
    sym = _extract_symbol_map_from_header_code(code)
    _HEADER_SYMBOL_CACHE[path] = (mtime, sym)
    return sym


def _load_header_typedef_blocks(header_path: str) -> list[str]:
    backend = legacy_backend()
    path = os.path.abspath(header_path or "")
    if not path:
        return []
    mtime = _get_file_mtime(path)
    cached = _HEADER_TYPEDEF_CACHE.get(path)
    if cached and cached[0] == mtime:
        return list(cached[1])
    try:
        code = backend.load_c_file(path)
    except backend.SourceReadError:
        _HEADER_TYPEDEF_CACHE[path] = (mtime, [])
        return []
    blocks = backend._extract_typedef_blocks_from_code(code)
    _HEADER_TYPEDEF_CACHE[path] = (mtime, list(blocks))
    return list(blocks)


def _load_header_member_symbol_map(header_path: str) -> dict[str, str]:
    backend = legacy_backend()
    path = os.path.abspath(header_path or "")
    if not path:
        return {}
    mtime = _get_file_mtime(path)
    cached = _HEADER_MEMBER_MAP_CACHE.get(path)
    if cached and cached[0] == mtime:
        return dict(cached[1])
    try:
        code = backend.load_c_file(path)
    except backend.SourceReadError:
        _HEADER_MEMBER_MAP_CACHE[path] = (mtime, {})
        return {}
    member_map = _extract_member_symbol_map_from_header_code(code)
    _HEADER_MEMBER_MAP_CACHE[path] = (mtime, dict(member_map))
    return dict(member_map)


def _iter_parent_dirs(start_dir: str, max_levels: int = 6) -> list[str]:
    out: list[str] = []
    cur = os.path.abspath(start_dir or "")
    for _ in range(max_levels):
        if not cur or cur in out:
            break
        out.append(cur)
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        cur = parent
    return out


def _guess_project_root_for_source(source_path: str, max_levels: int = 8) -> str:
    fdir = os.path.dirname(os.path.abspath(source_path or "")) if source_path else ""
    if not fdir:
        return ""
    parts = os.path.normpath(fdir).split(os.sep)
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx].lower() == "src":
            return os.sep.join(parts[:idx]) or fdir
    for path in _iter_parent_dirs(fdir, max_levels=max_levels):
        try:
            entries = {p.lower() for p in os.listdir(path)}
        except Exception:
            continue
        if "src" in entries:
            return path
        if "include" in entries or "inc" in entries:
            return path
    return fdir


def _build_candidate_include_dirs(
    c_dir: str,
    project_root: str,
    exclude_dirs: Optional[Sequence[str]] = None,
    include_subdir_depth: int = 6,
) -> list[str]:
    backend = legacy_backend()
    dirs: list[str] = []
    for path in _iter_parent_dirs(c_dir, max_levels=6):
        dirs.append(path)
    if project_root:
        root = os.path.abspath(project_root)
        dirs.append(root)
        for name in ("include", "Include", "INC", "inc"):
            cand = os.path.join(root, name)
            if os.path.isdir(cand):
                dirs.extend(
                    scanner_utils.iter_subdirs(
                        cand,
                        max_depth=include_subdir_depth,
                        exclude_dirs=exclude_dirs,
                    )
                )
    seen: set[str] = set()
    out: list[str] = []
    for path in dirs:
        abs_path = os.path.abspath(path)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        out.append(abs_path)
    return out


def _resolve_header_path(
    include: str,
    search_dirs: Sequence[str],
    header_index: Optional[dict[str, list[str]]],
) -> Optional[str]:
    inc = (include or "").strip()
    if not inc:
        return None
    for base_dir in (search_dirs or []):
        cand = os.path.normpath(os.path.join(base_dir, inc))
        if os.path.isfile(cand):
            return cand
    base = os.path.basename(inc).lower()
    if not header_index:
        return None
    cands = header_index.get(base) or []
    if not cands:
        return None
    if inc and ("/" in inc or "\\" in inc):
        tail = os.path.normpath(inc).lower()
        for path in cands:
            if os.path.normpath(path).lower().endswith(tail):
                return path
    return cands[0]


def _resolve_header_path_with_reason(
    include: str,
    search_dirs: Sequence[str],
    header_index: Optional[dict[str, list[str]]],
) -> tuple[Optional[str], str]:
    inc = (include or "").strip()
    if not inc:
        return None, "empty_include"
    for base_dir in (search_dirs or []):
        cand = os.path.normpath(os.path.join(base_dir, inc))
        if os.path.isfile(cand):
            return cand, f"dir:{base_dir}"
    base = os.path.basename(inc).lower()
    if not header_index:
        return None, "no_header_index"
    cands = header_index.get(base) or []
    if not cands:
        return None, f"not_found:{base}"
    if inc and ("/" in inc or "\\" in inc):
        tail = os.path.normpath(inc).lower()
        for path in cands:
            if os.path.normpath(path).lower().endswith(tail):
                return path, "index:tail_match"
    return cands[0], "index:basename_first"


def _collect_transitive_headers(
    start_headers: Sequence[str],
    search_dirs: Sequence[str],
    header_index: Optional[dict[str, list[str]]],
    cfg,
) -> list[str]:
    backend = legacy_backend()
    max_depth = int(getattr(cfg, "header_transitive_depth", 0) or 0)
    if max_depth <= 0:
        return [os.path.abspath(path) for path in (start_headers or []) if path and os.path.isfile(path)]

    out: list[str] = []
    visited: set[str] = set()
    queue: list[tuple[str, int]] = []
    for path in (start_headers or []):
        abs_path = os.path.abspath(path or "")
        if not abs_path or abs_path in visited or not os.path.isfile(abs_path):
            continue
        visited.add(abs_path)
        queue.append((abs_path, 0))
        out.append(abs_path)

    while queue:
        if _stop_requested(cfg):
            break
        cur, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        try:
            code = backend.load_c_file(cur)
        except backend.SourceReadError:
            continue
        cur_dir = os.path.dirname(os.path.abspath(cur))
        nested_search_dirs = [cur_dir] + list(search_dirs or [])
        for include in _extract_includes(code):
            if _stop_requested(cfg):
                break
            header_path = _resolve_header_path(include, nested_search_dirs, header_index)
            if not header_path:
                continue
            abs_path = os.path.abspath(header_path)
            if abs_path in visited or not os.path.isfile(abs_path):
                continue
            visited.add(abs_path)
            out.append(abs_path)
            queue.append((abs_path, depth + 1))
    return out


def _collect_related_header_paths_for_c_file(
    c_path: str,
    c_code: str,
    project_root: Optional[str],
    cfg,
) -> list[str]:
    c_dir = os.path.dirname(os.path.abspath(c_path or "")) if c_path else ""
    search_root = project_root or c_dir
    if _stop_requested(cfg):
        return []
    header_index = _get_header_index(search_root, exclude_dirs=getattr(cfg, "exclude_dirs", None), cfg=cfg) if search_root else {}
    search_dirs = _build_candidate_include_dirs(c_dir, search_root, exclude_dirs=getattr(cfg, "exclude_dirs", None)) if c_dir else []
    header_paths: list[str] = []
    if c_dir and c_path:
        base_h = os.path.join(c_dir, os.path.splitext(os.path.basename(c_path))[0] + ".h")
        if os.path.isfile(base_h):
            header_paths.append(base_h)
    for inc in _extract_includes(c_code or ""):
        if _stop_requested(cfg):
            break
        hp, _reason = _resolve_header_path_with_reason(inc, search_dirs, header_index)
        if hp:
            header_paths.append(hp)
    seen: set[str] = set()
    uniq_headers: list[str] = []
    for path in header_paths:
        abs_path = os.path.abspath(path)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        uniq_headers.append(abs_path)
    return _collect_transitive_headers(
        uniq_headers,
        search_dirs=search_dirs,
        header_index=header_index,
        cfg=cfg,
    )


def build_related_header_context_for_c_file(
    c_path: str,
    c_code: str,
    project_root: Optional[str],
    cfg,
    *,
    backend_module=None,
) -> tuple[list[str], dict[str, str]]:
    backend = backend_module or legacy_backend()
    if _stop_requested(cfg):
        return [], {}
    c_abs = os.path.abspath(c_path or "")
    if c_abs:
        root_abs = os.path.abspath(project_root or "")
        excludes = ",".join(sorted({str(d).strip().lower() for d in (getattr(cfg, "exclude_dirs", []) or []) if str(d).strip()}))
        depth = int(getattr(cfg, "header_transitive_depth", 0) or 0)
        cache_key = f"{c_abs}|root={root_abs}|ex={excludes}|depth={depth}"
        mtime = _get_file_mtime(c_abs)
        cached = _RELATED_TYPEDEF_CACHE.get(cache_key)
        if cached and cached[0] == mtime:
            return list(cached[1]), dict(cached[2])

    typedef_blocks: list[str] = []
    member_symbol_map: dict[str, str] = {}
    variable_type_map: dict[str, str] = {}
    variable_type_map.update(_extract_variable_type_map_from_code(_strip_function_bodies_keep_layout(c_code or "")))
    for header_path in _collect_related_header_paths_for_c_file(c_path, c_code, project_root, cfg):
        if _stop_requested(cfg):
            break
        header_code = ""
        try:
            header_code = backend.load_c_file(header_path)
        except Exception:
            header_code = ""
        if header_code:
            variable_type_map.update(_extract_variable_type_map_from_code(header_code))
        for block in _load_header_typedef_blocks(header_path):
            if _stop_requested(cfg):
                break
            block_text = utils_module._safe_strip(block)
            if block_text and block_text not in typedef_blocks:
                typedef_blocks.append(block_text)
        if _stop_requested(cfg):
            break
        for name, cn in _load_header_member_symbol_map(header_path).items():
            if _stop_requested(cfg):
                break
            ident = utils_module._safe_strip(name)
            text = utils_module._safe_strip(cn)
            if ident and text and ident not in member_symbol_map:
                member_symbol_map[ident] = text
    member_symbol_map = _expand_member_symbol_map_with_variable_types(member_symbol_map, variable_type_map)

    if c_abs:
        _RELATED_TYPEDEF_CACHE[cache_key] = (mtime, list(typedef_blocks), dict(member_symbol_map))
    return typedef_blocks, member_symbol_map


def build_global_symbol_map_for_c_file(
    c_path: str,
    c_code: str,
    project_root: Optional[str],
    cfg,
    *,
    backend_module=None,
):
    backend = backend_module or legacy_backend()
    if _stop_requested(cfg):
        return {}
    c_abs = os.path.abspath(c_path or "")
    if c_abs:
        root_abs = os.path.abspath(project_root or "")
        excludes = ",".join(sorted({str(d).strip().lower() for d in (getattr(cfg, "exclude_dirs", []) or []) if str(d).strip()}))
        depth = int(getattr(cfg, "header_transitive_depth", 0) or 0)
        cache_key = f"{c_abs}|root={root_abs}|ex={excludes}|depth={depth}"
        mtime = _get_file_mtime(c_abs)
        cached = _SYMBOL_MAP_CACHE.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]

    c_dir = os.path.dirname(os.path.abspath(c_path or "")) if c_path else ""
    search_root = project_root or c_dir
    header_index = _get_header_index(search_root, exclude_dirs=getattr(cfg, "exclude_dirs", None), cfg=cfg) if search_root else {}
    search_dirs = _build_candidate_include_dirs(c_dir, search_root, exclude_dirs=getattr(cfg, "exclude_dirs", None)) if c_dir else []

    header_paths: list[str] = []
    if getattr(cfg, "verbose", False):
        utils_module.vlog(cfg, "[include] c_path=", c_path)
        utils_module.vlog(cfg, "[include] project_root=", project_root or "")
        utils_module.vlog(cfg, "[include] search_root=", search_root or "")
        utils_module.vlog(cfg, "[include] search_dirs=", len(search_dirs))
        for item in (search_dirs[:20] if search_dirs else []):
            utils_module.vlog(cfg, "    -", item)
        utils_module.vlog(cfg, "[include] header_index_files=", len(header_index or {}))

    if c_dir and c_path:
        base_h = os.path.join(c_dir, os.path.splitext(os.path.basename(c_path))[0] + ".h")
        if os.path.isfile(base_h):
            header_paths.append(base_h)
            if getattr(cfg, "verbose", False):
                utils_module.vlog(cfg, "[include] sibling_header=", base_h)

    includes = _extract_includes(c_code or "")
    if getattr(cfg, "verbose", False):
        utils_module.vlog(cfg, "[include] includes_extracted=", len(includes))

    for include in includes:
        if _stop_requested(cfg):
            break
        header_path, reason = _resolve_header_path_with_reason(include, search_dirs, header_index)
        if getattr(cfg, "verbose", False):
            utils_module.vlog(cfg, "[include] resolve", include, "=>", (header_path or ""), f"({reason})")
        if header_path:
            header_paths.append(header_path)

    seen: set[str] = set()
    uniq_headers: list[str] = []
    for header_path in header_paths:
        abs_path = os.path.abspath(header_path)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        uniq_headers.append(abs_path)

    all_headers = _collect_transitive_headers(
        uniq_headers,
        search_dirs=search_dirs,
        header_index=header_index,
        cfg=cfg,
    )
    if getattr(cfg, "verbose", False):
        utils_module.vlog(cfg, "[include] headers_selected=", len(uniq_headers), "headers_transitive=", len(all_headers))

    c_top_level_code = _strip_function_bodies_keep_layout(c_code or "")
    merged: dict[str, str] = _extract_symbol_map_from_header_code(c_top_level_code)
    for header_path in all_headers:
        if _stop_requested(cfg):
            break
        sym_map = _load_header_symbol_map(header_path, cfg)
        if getattr(cfg, "verbose", False):
            utils_module.vlog(cfg, "[include] symbols_from", os.path.basename(header_path), "=", len(sym_map))
        merged.update(sym_map)
    if getattr(backend, "SYMBOL_DICTIONARY_RUNTIME", None):
        merged.update(backend.SYMBOL_DICTIONARY_RUNTIME)
    if c_abs:
        _SYMBOL_MAP_CACHE[cache_key] = (mtime, merged)
    return merged


def _classify_symbol_kind(name: str) -> str:
    upper = (name or "").upper()
    if upper == name and "_" in (name or ""):
        return "macros"
    if (name or "").startswith("g_") or (name or "").startswith("l_"):
        return "symbols"
    return "members"


def _extract_all_define_names(header_code: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in (header_code or "").splitlines():
        m = re.match(r"\s*#\s*define\s+([A-Za-z_]\w*)\b(.*)", raw)
        if not m:
            continue
        name = m.group(1)
        rest = m.group(2)
        comment = ""
        for sep in ("//", "/*"):
            idx = rest.find(sep)
            if idx >= 0:
                comment = rest[idx + len(sep):].split("*/", 1)[0].strip()
                break
        result[name] = comment
    return result


def _group_symbols_by_prefix(symbols: list[str], max_group_size: int = 50) -> list[list[str]]:
    if not symbols:
        return []
    groups: dict[str, list[str]] = {}
    for sym in symbols:
        parts = (sym or "").split("_")
        prefix = "_".join(parts[:2]) if len(parts) >= 3 else parts[0]
        groups.setdefault(prefix, []).append(sym)
    result: list[list[str]] = []
    batch: list[str] = []
    for grp in groups.values():
        for sym in grp:
            batch.append(sym)
            if len(batch) >= max_group_size:
                result.append(batch)
                batch = []
    if batch:
        result.append(batch)
    return result


def batch_translate_symbols(symbols: list[str], kind: str = "macros", cfg: Optional[Any] = None) -> dict[str, str]:
    from . import ai as ai_utils

    if not symbols:
        return {}
    if cfg is None or not getattr(cfg, "ai_assist", False):
        return {}
    groups = _group_symbols_by_prefix(symbols)
    result: dict[str, str] = {}
    for batch in groups:
        prompt = (
            "你是嵌入式软件术语翻译助手。请为以下 C 语言宏/枚举标识符生成简洁的中文翻译。\n"
            "只输出 JSON 对象，不要解释。不确定的项值留空字符串。\n\n"
            f"输入标识符（{kind}类）：\n"
            + "\n".join(f"- {s}" for s in batch)
            + "\n\n输出格式：\n{\"标识符\": \"中文翻译\", ...}\n"
            + "规则：翻译要简洁（2~8字），保留领域术语缩写（如BIT、CCDL、1394）。"
        )
        try:
            raw = ai_utils.call_llm_json(prompt, cfg, kind="batch_translate")
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, str) and v.strip() and k in batch:
                        result[k] = v.strip()
        except Exception:
            pass
    return result


def merge_prebuilt_symbols_into_runtime(prebuilt: dict) -> None:
    backend = legacy_backend()
    for category in ("macros", "members", "symbols"):
        for sym, cn_name in (prebuilt or {}).get(category, {}).items():
            if sym not in backend.SYMBOL_DICTIONARY_RUNTIME:
                backend.SYMBOL_DICTIONARY_RUNTIME[sym] = cn_name


def prebuild_project_symbol_db(project_dir: str, cfg: Optional[Any] = None) -> dict:
    backend = legacy_backend()
    result: dict[str, dict[str, str]] = {"macros": {}, "members": {}, "symbols": {}}
    untranslated_macros: list[str] = []
    if _stop_requested(cfg):
        result["untranslated_macros"] = untranslated_macros
        return result

    header_patterns = [
        os.path.join(project_dir, "Include", "**", "*.h"),
        os.path.join(project_dir, "include", "**", "*.h"),
    ]
    header_files: list[str] = []
    for pattern in header_patterns:
        if _stop_requested(cfg):
            break
        header_files.extend(glob.glob(pattern, recursive=True))

    seen_symbols: set[str] = set()
    all_defines: dict[str, str] = {}
    for hpath in header_files:
        if _stop_requested(cfg):
            break
        try:
            code = backend.load_c_file(hpath)
        except Exception:
            continue
        for dn, dc in _extract_all_define_names(code).items():
            if _stop_requested(cfg):
                break
            if dn not in all_defines:
                all_defines[dn] = dc
        try:
            sym_map = _extract_symbol_map_from_header_code(code)
        except Exception:
            continue
        for sym, cn_name in sym_map.items():
            if _stop_requested(cfg):
                break
            if sym in seen_symbols:
                continue
            seen_symbols.add(sym)
            if not cn_name or not cn_name.strip():
                continue
            kind = _classify_symbol_kind(sym)
            if kind in result:
                result[kind][sym] = cn_name.strip()

    for dn, dc in all_defines.items():
        if _stop_requested(cfg):
            break
        if dn in seen_symbols:
            continue
        if _classify_symbol_kind(dn) != "macros":
            continue
        if dc and dc.strip():
            result["macros"][dn] = dc.strip()
            seen_symbols.add(dn)
        else:
            untranslated_macros.append(dn)

    result["untranslated_macros"] = untranslated_macros
    return result


def parse_params_from_prototype(func_info: dict):
    params_str = (func_info or {}).get("params", "").strip()
    if not params_str or params_str == "void":
        return []
    params = []
    for part in params_str.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.replace("*", " *").split()
        if len(tokens) < 2:
            continue
        raw_name = tokens[-1]
        pointer_prefix = "*" * (len(raw_name) - len(raw_name.lstrip("*")))
        name = raw_name.lstrip("*")
        type_tokens = list(tokens[:-1])
        if pointer_prefix:
            type_tokens.append(pointer_prefix)
        ptype = " ".join(type_tokens).replace(" *", "*").strip()
        params.append({"name": name, "type": ptype})
    return params


_PAREN_SUFFIX_RE = re.compile(r"\s*[\(（][^)\）]*[\)）]\s*$")


def _strip_trailing_paren_content(text: str) -> str:
    if not text:
        return text
    return _PAREN_SUFFIX_RE.sub("", text).strip()


def parse_param_desc(desc_text: str, *, strip_paren_content: bool = False):
    mapping = {}
    if not desc_text:
        return mapping
    head = desc_text.strip()
    if head in ("无",) or head.upper() in ("NONE", "N/A", "NA"):
        return mapping
    for line in desc_text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\u2022]\s*", "", line)
        match = re.match(r"([A-Za-z_]\w*)\s*[:：]\s*(.+)", line)
        if not match:
            match = re.match(r"([A-Za-z_]\w*)\s*[-–—]{1,4}\s*(.+)", line)
        if match:
            name = match.group(1)
            desc = re.sub(r"[。;；]+$", "", match.group(2).strip())
            if strip_paren_content:
                desc = _strip_trailing_paren_content(desc)
            mapping[name] = desc
    return mapping


def _split_cn_name_and_usage_from_comment(comment: str) -> tuple[str, str]:
    if not comment:
        return "", ""
    comment = _clean_symbol_comment_text(comment)
    if _looks_like_noise_symbol_comment(comment):
        head = re.split(r"[,，]", comment, maxsplit=1)[0].strip()
        if head and head != comment and (not _looks_like_noise_symbol_comment(head)):
            comment = head
        else:
            return "", ""
    match = re.match(r"^\s*(.+?)\s*[\(（]\s*(.+?)\s*[\)）]\s*$", comment)
    if match:
        cn_name = match.group(1).strip()
        usage = re.sub(r"[。;；]+$", "", match.group(2).strip())
        return cn_name, usage
    match2 = re.match(r"^\s*(.+?)\s*[-–—]{1,2}\s*(.+?)\s*$", comment)
    if match2:
        cn_name = match2.group(1).strip()
        usage = re.sub(r"[。;；]+$", "", match2.group(2).strip())
        return cn_name, usage
    label, tail = _split_short_label_and_tail(comment)
    if label:
        return label, tail
    one = re.sub(r"[。;；]+$", "", comment.strip())
    return one, ""


def _looks_like_compact_cn_label(text: str) -> bool:
    backend = legacy_backend()
    s = re.sub(r"\s+", "", (text or "").strip())
    if (not s) or (not text_utils._contains_cjk(s)):
        return False
    if len(s) > 18:
        return False
    if any(mark in s for mark in ("用于", "以便", "表示", "范围", "单位", "默认", "说明", "例如")):
        return False
    if re.search(r"从.+到", s):
        return False
    if sum(s.count(ch) for ch in "，,；;:：") >= 1:
        return False
    return True


def _split_short_label_and_tail(text: str) -> tuple[str, str]:
    backend = legacy_backend()
    s = re.sub(r"[。;；]+$", "", utils_module._safe_strip(text))
    if not s:
        return "", ""
    for sep in ("，", ",", "；", ";", "：", ":"):
        if sep not in s:
            continue
        left, right = s.split(sep, 1)
        left = left.strip()
        right = right.strip()
        if _looks_like_compact_cn_label(left) and right:
            return left, right
    match = re.match(r"^\s*(?P<label>.+?)\s*(?P<tail>(?:范围|取值范围|单位|默认|用于|以便|表示|对应|从.+到.+).*)$", s)
    if match:
        label = utils_module._safe_strip(match.group("label"))
        tail = utils_module._safe_strip(match.group("tail"))
        if _looks_like_compact_cn_label(label) and tail:
            return label, tail
    return "", ""


def _shorten_element_display_name(text: str, fallback: str = "") -> str:
    backend = legacy_backend()
    s = utils_module._safe_strip(text)
    if not s:
        return utils_module._safe_strip(fallback)
    label, _tail = _split_short_label_and_tail(s)
    if label:
        return label
    return s


def _split_top_level_commas(text: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    value = str(text or "")
    for idx, ch in enumerate(value):
        if ch in "([{":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(value[start:idx].strip())
            start = idx + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _split_comment_labels_for_declarators(comment: str, count: int) -> list[str]:
    value = _clean_symbol_comment_text(comment)
    if not value or count <= 1:
        return []
    for sep in ("，", "、", "/", ","):
        if sep not in value:
            continue
        parts = [part.strip() for part in value.split(sep) if part.strip()]
        if len(parts) == count and all(_looks_like_compact_cn_label(part) for part in parts):
            return parts
    return []


def _semantic_identifier_tokens(name: str) -> set[str]:
    value = utils_module._safe_strip(name)
    if not value:
        return set()
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", value)
    return {token.lower() for token in re.split(r"[^A-Za-z0-9]+", value) if token}


def _fallback_local_cn_from_ident(name: str) -> str:
    tokens = _semantic_identifier_tokens(name)
    if not tokens:
        return ""
    if "min" in tokens:
        return "最小值"
    if "max" in tokens:
        return "最大值"
    if "sum" in tokens:
        return "累加和"
    if "count" in tokens or "cnt" in tokens:
        return "计数"
    if "ii" in tokens:
        return "循环索引ii"
    if "jj" in tokens:
        return "循环索引jj"
    if "index" in tokens or "idx" in tokens:
        return "循环索引"
    return ""


def parse_local_variables_from_body(body: str):
    backend = legacy_backend()
    variables = []
    lines = _join_c_line_continuations(body).splitlines()

    def split_code_and_comment(line: str):
        m_block = re.search(r"/\*\s*(.*?)\s*\*/\s*$", line)
        if m_block:
            return line[:m_block.start()].rstrip(), m_block.group(1).strip()
        m_line = re.search(r"//\s*(.*)$", line)
        if m_line:
            return line[:m_line.start()].rstrip(), m_line.group(1).strip()
        return line.rstrip(), ""

    type_prefix = r"(?:static\s+|const\s+|volatile\s+|register\s+)*"
    # C 基本类型关键词可多词组合（unsigned int / long long / unsigned char ...），
    # typedef 名仍是单个标识符；两者互斥，避免贪婪吃掉变量名。
    _c_type_kw = r"(?:void|_Bool|char|short|int|long|float|double|signed|unsigned)"
    type_name = rf"(?:struct\s+\w+|union\s+\w+|enum\s+\w+|{_c_type_kw}(?:\s+{_c_type_kw})*|[A-Za-z_]\w*)"
    type_suffix = r"(?:\s+(?:const|volatile)\b)*"
    pointer = r"(?:\s*(?:(?:const|volatile)\s*)?\*\s*(?:const\s+|volatile\s+)*)*"
    identifier = r"[A-Za-z_]\w*"
    var_name = rf"(?P<name>{identifier})"
    array = r"(?:\s*\[[^\]]*\])*"
    decl_head_re = re.compile(rf"^\s*(?P<type>{type_prefix}{type_name}{type_suffix})\s+(?P<decls>.+?)\s*;\s*$")
    declarator_re = re.compile(rf"^\s*(?P<pointer>{pointer}){var_name}{array}(?:\s*=\s*.+)?\s*$")

    def normalize_pointer_attached_type(code: str, comment: str = "") -> str:
        match = re.match(rf"^(?P<type>\s*{type_prefix}{type_name}{type_suffix})(?P<pointer>\*+)(?=\s*[A-Za-z_])", code)
        if not match:
            return code
        type_text = " ".join(match.group("type").split())
        type_tokens = type_text.split()
        last_type_token = type_tokens[-1] if type_tokens else ""
        qualifiers = {"const", "volatile", "static", "register"}
        has_type_qualifier = any(token in qualifiers for token in type_tokens)
        known_c_types = {
            "bool",
            "char",
            "double",
            "float",
            "int",
            "long",
            "short",
            "signed",
            "unsigned",
            "void",
            "_bool",
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
            "int8",
            "int16",
            "int32",
            "int64",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
            "sint8",
            "sint16",
            "sint32",
            "sint64",
            "float32",
            "float64",
        }
        typedef_suffixes = ("State", "Config", "Type", "Info", "Handle", "Ptr", "Struct")
        last_type_lower = last_type_token.lower()
        declaration_comment_keywords = (
            "pointer", "ptr", "typedef", "declaration", "decl",
            "指针", "声明",
        )
        comment_compact = re.sub(r"\s+", "", comment or "")
        comment_lower = comment_compact.lower()
        comment_says_pointer_local_declaration = bool(comment_lower) and any(
            keyword in comment_lower for keyword in declaration_comment_keywords
        )
        is_existing_local_name = any(item.get("name") == last_type_token for item in variables)
        declarator_tail = code[match.end("pointer") :]
        declaration_like_declarator = bool(
            re.match(
                rf"^\s*{identifier}{array}(?:\s*=\s*[^;]+)?(?:\s*,\s*{pointer}{identifier}{array}(?:\s*=\s*[^;]+)?)*\s*;\s*$",
                declarator_tail,
            )
        )
        has_custom_typedef_evidence = (
            declaration_like_declarator
            and not last_type_token.isupper()
            and last_type_token[:1].isupper()
            and (
                comment_says_pointer_local_declaration
                or has_type_qualifier
                or any(last_type_token.endswith(suffix) for suffix in typedef_suffixes)
            )
        )
        looks_like_type = (
            not is_existing_local_name
            and (
                has_type_qualifier
                or last_type_lower in known_c_types
                or last_type_lower.endswith("_t")
                or type_text.startswith(("struct ", "union ", "enum "))
                or has_custom_typedef_evidence
            )
        )
        if not looks_like_type:
            return code
        return f"{match.group('type')} {match.group('pointer')}{code[match.end('pointer') :]}"

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^return\b", line):
            continue
        code, cmt = split_code_and_comment(raw)
        stripped_code = code.strip()
        normalized_code = normalize_pointer_attached_type(stripped_code, cmt)
        match_head = decl_head_re.match(normalized_code)
        if not match_head:
            if "(" in stripped_code and ")" in stripped_code and not re.search(r"\[\s*\]", stripped_code):
                if re.search(r";\s*$", stripped_code):
                    continue
            continue

        base_type = " ".join(match_head.group("type").split())
        declarators = _split_top_level_commas(match_head.group("decls"))
        comment_labels = _split_comment_labels_for_declarators(cmt, len(declarators))

        for idx, declarator in enumerate(declarators):
            match_decl = declarator_re.match(declarator)
            if not match_decl:
                continue
            pointer_text = " ".join((match_decl.group("pointer") or "").split())
            v_type = " ".join(part for part in (base_type, pointer_text) if part)
            v_name = match_decl.group("name")
            name_source = ""
            name_confidence = 0.0

            if comment_labels:
                cn_name = comment_labels[idx]
                usage = ""
                comment_cn_name = cn_name
                comment_hint = ""
                name_source = "inline_comment_split"
                name_confidence = 0.95
            else:
                cn_name, usage = _split_cn_name_and_usage_from_comment(cmt)
                comment_cn_name = cn_name if (cmt and cn_name) else ""
                comment_hint = ""
                if cmt and cn_name and (not usage):
                    if re.search(r"[\(（].*?[\)）]", cmt):
                        name_source = "inline_comment"
                        name_confidence = 0.85
                    elif len(cn_name) <= 10:
                        comment_hint = cn_name
                        cn_name = ""
                        usage = ""
                    else:
                        usage = cn_name
                        cn_name = ""
                elif cn_name:
                    name_source = "inline_comment"
                    name_confidence = 0.85
                if not cn_name:
                    cn_name = backend._lookup_symbol_dictionary(v_name)
                    if cn_name:
                        name_source = "symbol_dictionary"
                        name_confidence = 0.75
                if not cn_name:
                    cn_name = _fallback_local_cn_from_ident(v_name)
                    if cn_name:
                        name_source = "identifier_fallback"
                        name_confidence = 0.65
            variables.append(
                {
                    "type": v_type,
                    "name": v_name,
                    "usage": usage,
                    "cn_name": cn_name,
                    "comment_cn_name": comment_cn_name,
                    "comment_hint": comment_hint,
                    "name_source": name_source,
                    "name_confidence": name_confidence,
                }
            )
    return variables


def _filter_local_vars_against_params(
    local_vars: list[dict],
    params: list[dict],
    *,
    cfg: Optional[Any] = None,
    func_name: str = "",
) -> list[dict]:
    backend = legacy_backend()
    local_items = list(local_vars or [])
    if not local_items:
        return local_items
    param_names = {
        utils_module._safe_strip((p or {}).get("name"))
        for p in (params or [])
        if utils_module._safe_strip((p or {}).get("name"))
    }
    if not param_names:
        return local_items
    filtered: list[dict] = []
    dropped: list[str] = []
    for item in local_items:
        name = utils_module._safe_strip((item or {}).get("name"))
        if name and name in param_names:
            dropped.append(name)
            continue
        filtered.append(item)
    if dropped and cfg is not None:
        fn = utils_module._safe_strip(func_name) or "(unknown)"
        utils_module.vlog(cfg, f"函数 {fn} 过滤误判局部变量(与参数重名): {sorted(set(dropped))}")
    return filtered


def parse_return_var_from_body(body: str):
    match = re.search(r"\breturn\s*\(?\s*&\s*([A-Za-z_]\w*)\s*\)?\s*;", body)
    if match:
        return match.group(1)
    match2 = re.search(r"\breturn\s*\(?\s*([A-Za-z_]\w*)\s*\)?\s*;", body)
    if match2:
        return match2.group(1)
    return None


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "FileContext",
    "FunctionContext",
    "_build_func_cn_map",
    "_clone_func_item",
    "_clean_comment_line",
    "_clean_symbol_comment_text",
    "_classify_symbol_kind",
    "_build_candidate_include_dirs",
    "_collect_related_header_paths_for_c_file",
    "_collect_transitive_headers",
    "_cross_check_tree_sitter_functions",
    "_derive_module_display_name",
    "_extract_file_header_info",
    "_extract_tree_sitter_functions",
    "_extract_all_define_names",
    "_extract_includes",
    "_extract_member_symbol_map_from_header_code",
    "_extract_member_symbol_map_from_typedefs",
    "_extract_module_cn_from_header",
    "_extract_symbol_map_from_header_code",
    "_extract_typedef_blocks_from_code",
    "_get_file_mtime",
    "_get_header_index",
    "_guess_project_root_for_source",
    "_is_noop_comment",
    "_join_c_line_continuations",
    "_looks_like_noise_symbol_comment",
    "_load_header_member_symbol_map",
    "_load_header_symbol_map",
    "_load_header_typedef_blocks",
    "_normalize_header_comment_cn",
    "_normalize_short_logic_label_comment",
    "_parse_c_file_base",
    "_find_line_comment_blocks",
    "_filter_local_vars_against_params",
    "_parse_line_comment_block",
    "_get_cached_scan_result",
    "_quick_scan_c_code",
    "_group_symbols_by_prefix",
    "_resolve_header_path",
    "_resolve_header_path_with_reason",
    "_shorten_header_cn_comment",
    "_split_code_and_comments_for_symbol",
    "_strip_function_bodies_keep_layout",
    "_strip_trailing_paren_content",
    "associate_comments_and_functions",
    "build_function_context",
    "build_related_header_context_for_c_file",
    "build_global_symbol_map_for_c_file",
    "batch_translate_symbols",
    "classify_comment_hint",
    "extract_function_body",
    "extract_nearby_macros",
    "extract_nearby_typedefs",
    "extract_statement_hints",
    "find_comment_blocks",
    "find_function_prototypes",
    "get_cached_func_list_for_c_file",
    "merge_prebuilt_symbols_into_runtime",
    "parse_local_variables_from_body",
    "parse_param_desc",
    "parse_params_from_prototype",
    "parse_return_var_from_body",
    "prebuild_project_symbol_db",
    "prepare_func_list_for_c_file",
]
