"""Function-level structure facts used to stabilize logic rendering."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
import re
from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import text
from . import utils
from . import parse as parse_utils
from .models import (
    AccessFact,
    BlockFact,
    CallFact,
    FunctionFact,
    FunctionFactPack,
    LocalFact,
    MemberFact,
    SourceRange,
)


_FACT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FACT_CACHE_MAX = 256
_FACT_SCHEMA_VERSION = "lsp-v3"
_ASSIGN_RE = re.compile(r"^(?P<lhs>.+?)(?P<op>\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=|(?<![=!<>])=(?![=]))(?P<rhs>.+)$")
_DECL_ASSIGN_LHS_RE = re.compile(
    r"^(?:(?:static|const|volatile|register|extern)\s+)*"
    r"(?:(?:unsigned|signed)\s+)?"
    r"(?:struct\s+[A-Za-z_]\w*|union\s+[A-Za-z_]\w*|enum\s+[A-Za-z_]\w*|[A-Za-z_]\w*)"
    r"(?:\s*\*+\s*|\s+)"
    r"[A-Za-z_]\w*(?:\s*\[[^\]]*\])?$"
)
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_MEMBER_RE = re.compile(
    r"(?P<base>[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)\s*(?:\.|->)\s*(?P<member>[A-Za-z_]\w*)"
)
_CONTROL_HEAD_RE = re.compile(r"^(?:if|else|for|while|switch|case|default|return|break|continue)\b")


def _strip_case_label_from_statement(stmt: str) -> str:
    value = utils._safe_strip(stmt)
    value = re.sub(r"^(?:case\s+[^:]+|default)\s*:\s*", "", value)
    value = re.sub(r";\s*break\s*$", "", value, flags=re.IGNORECASE)
    return value


def _split_inline_c_statements(text_value: str) -> list[str]:
    value = str(text_value or "").strip()
    if not value:
        return []
    parts: list[str] = []
    cur: list[str] = []
    depth_paren = 0
    depth_brack = 0
    depth_brace = 0
    in_squote = False
    in_dquote = False
    escape = False
    for ch in value:
        cur.append(ch)
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            continue
        if ch == "'":
            in_squote = True
            continue
        if ch == '"':
            in_dquote = True
            continue
        if ch == "(":
            depth_paren += 1
            continue
        if ch == ")":
            depth_paren = max(0, depth_paren - 1)
            continue
        if ch == "[":
            depth_brack += 1
            continue
        if ch == "]":
            depth_brack = max(0, depth_brack - 1)
            continue
        if ch == "{":
            depth_brace += 1
            continue
        if ch == "}":
            depth_brace = max(0, depth_brace - 1)
            continue
        if ch == ";" and depth_paren == 0 and depth_brack == 0 and depth_brace == 0:
            stmt = "".join(cur).strip()
            if stmt:
                parts.append(stmt)
            cur = []
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract_inline_braced_statements(stmt: str) -> list[str]:
    value = utils._safe_strip(stmt)
    if not value or "{" not in value or "}" not in value or not _CONTROL_HEAD_RE.match(value):
        return [value] if value else []
    bodies: list[str] = []
    cur: list[str] = []
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    for ch in value:
        if escape:
            if depth > 0:
                cur.append(ch)
            escape = False
            continue
        if ch == "\\":
            if depth > 0:
                cur.append(ch)
            escape = True
            continue
        if in_squote:
            if depth > 0:
                cur.append(ch)
            if ch == "'":
                in_squote = False
            continue
        if in_dquote:
            if depth > 0:
                cur.append(ch)
            if ch == '"':
                in_dquote = False
            continue
        if ch == "'":
            if depth > 0:
                cur.append(ch)
            in_squote = True
            continue
        if ch == '"':
            if depth > 0:
                cur.append(ch)
            in_dquote = True
            continue
        if ch == "{":
            if depth > 0:
                cur.append(ch)
            depth += 1
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                body = "".join(cur).strip()
                if body:
                    bodies.extend(_split_inline_c_statements(body))
                cur = []
            else:
                cur.append(ch)
            continue
        if depth > 0:
            cur.append(ch)
    return bodies or [value]


def _extract_control_header(lines: list[str], start_idx: int, *, backend_module=None) -> tuple[str, int]:
    legacy = backend_module or legacy_backend()
    collected: list[str] = []
    paren_depth = 0
    seen_open = False
    end_idx = start_idx
    for idx in range(start_idx, len(lines) + 1):
        raw = lines[idx - 1]
        code = re.sub(r"//.*", "", raw).strip()
        code = re.sub(r"/\*.*?\*/", "", code).strip()
        if not code:
            continue
        collected.append(code)
        for ch in code:
            if ch == "(":
                paren_depth += 1
                seen_open = True
            elif ch == ")":
                paren_depth = max(0, paren_depth - 1)
        end_idx = idx
        if "{" in code and (not seen_open or paren_depth <= 0):
            break
        if seen_open and paren_depth <= 0:
            break
        if not seen_open:
            break
    return " ".join(collected).strip(), end_idx


def _extract_parenthesized_header_condition(header: str) -> str:
    value = utils._safe_strip(header)
    start = value.find("(")
    if start < 0:
        return ""
    depth = 0
    chars: list[str] = []
    for ch in value[start:]:
        if ch == "(":
            depth += 1
            if depth == 1:
                continue
        elif ch == ")":
            depth -= 1
            if depth <= 0:
                break
        if depth >= 1:
            chars.append(ch)
    return utils._safe_strip("".join(chars))


def _get_file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def _range_for_lines(start_line: int, end_line: int, line_text: str = "") -> SourceRange:
    width = max(0, len(str(line_text or "")))
    return SourceRange(start_line=start_line, end_line=end_line, start_col=1, end_col=max(1, width))


def _offset_source_range(range_obj: Optional[SourceRange], line_offset: int) -> None:
    if range_obj is None or line_offset <= 0:
        return
    if int(range_obj.start_line or 0) > 0:
        range_obj.start_line = int(range_obj.start_line or 0) + line_offset
    if int(range_obj.end_line or 0) > 0:
        range_obj.end_line = int(range_obj.end_line or 0) + line_offset


def _offset_fact_ranges_to_function_lines(pack: FunctionFactPack) -> None:
    try:
        line_offset = int(pack.function.range.start_line or 0)
    except Exception:
        line_offset = 0
    if line_offset <= 0:
        return
    for group in (pack.blocks, pack.reads, pack.writes, pack.calls, pack.members):
        for item in group:
            _offset_source_range(getattr(item, "range", None), line_offset)
    for item in pack.locals:
        _offset_source_range(getattr(item, "decl_range", None), line_offset)


def _collect_code_statements(body: str, *, backend_module=None) -> list[dict[str, Any]]:
    legacy = backend_module or legacy_backend()
    statements: list[dict[str, Any]] = []
    pending_code: list[str] = []
    pending_raw: list[str] = []
    start_line = 0

    def _flush(end_line: int) -> None:
        nonlocal start_line
        code = " ".join(part for part in pending_code if part).strip()
        raw_text = " ".join(part.strip() for part in pending_raw if part.strip()).strip()
        pending_code.clear()
        pending_raw.clear()
        if code:
            statements.append(
                {
                    "code": code,
                    "raw": raw_text or code,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )
        start_line = 0

    for idx, raw in enumerate(legacy._join_c_line_continuations(body or "").splitlines(), start=1):
        code, _ = legacy._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt or stmt.startswith("#"):
            continue
        if (
            pending_code
            and re.match(r"^(?:[&|^]|&&|\|\|)\s*\S+", stmt)
            and not _CONTROL_HEAD_RE.match(stmt)
        ):
            pending_code.append(stmt)
            pending_raw.append(raw)
            if stmt.endswith(";"):
                _flush(idx)
            continue
        if pending_code:
            _flush(max(start_line, idx - 1))
        start_line = idx
        pending_code.append(stmt)
        pending_raw.append(raw)
        if stmt.endswith(";") or stmt.endswith("{") or stmt in ("}", "};"):
            _flush(idx)
    if pending_code:
        _flush(max(start_line, len((body or "").splitlines())))
    return statements


def _make_cache_key(func_data: dict[str, Any], source_file: str) -> str:
    legacy = legacy_backend()
    func_info = dict((func_data or {}).get("func_info") or {})
    func_name = utils._safe_strip(func_info.get("func_name"))
    prototype = utils._safe_strip(func_info.get("prototype"))
    body = utils._safe_text((func_data or {}).get("body"))
    body_lines = len(body.splitlines()) if body else 0
    compile_seed = "|".join(
        [
            utils.cfg_get_str(func_data.get("cfg") if isinstance(func_data, dict) else None, "logic_lsp_clangd_path", ""),
            utils.cfg_get_str(func_data.get("cfg") if isinstance(func_data, dict) else None, "logic_lsp_include_paths", ""),
            utils.cfg_get_str(func_data.get("cfg") if isinstance(func_data, dict) else None, "logic_lsp_defines", ""),
            utils.cfg_get_str(func_data.get("cfg") if isinstance(func_data, dict) else None, "logic_lsp_forced_includes", ""),
        ]
    )
    compile_hash = hashlib.sha256(compile_seed.encode("utf-8", errors="ignore")).hexdigest()[:12] if compile_seed else ""
    return "|".join([os.path.abspath(source_file or ""), func_name, prototype, str(body_lines), compile_hash, _FACT_SCHEMA_VERSION])


def _guess_function_range(func_data: dict[str, Any], source_file: str, body: str) -> SourceRange:
    legacy = legacy_backend()
    func_info = dict((func_data or {}).get("func_info") or {})
    prototype = utils._safe_strip(func_info.get("prototype"))
    func_name = utils._safe_strip(func_info.get("func_name"))
    code = ""
    try:
        code = legacy.load_c_file(source_file)
    except Exception:
        code = ""
    if code and func_name:
        lines = code.splitlines()
        start_idx = -1
        for idx, line in enumerate(lines):
            if prototype and prototype in line:
                start_idx = idx
                break
            if re.search(rf"\b{re.escape(func_name)}\s*\(", line):
                start_idx = idx
                break
        if start_idx >= 0:
            body_lines = max(1, len((body or "").splitlines()))
            return _range_for_lines(start_idx + 1, start_idx + body_lines + 2, lines[start_idx] if start_idx < len(lines) else "")
    body_lines = max(1, len((body or "").splitlines()))
    return _range_for_lines(1, body_lines, prototype or func_name)


def _collect_blocks(body: str) -> list[BlockFact]:
    legacy = legacy_backend()
    lines = legacy._join_c_line_continuations(body or "").splitlines()
    blocks: list[BlockFact] = []
    stack: list[dict[str, Any]] = []
    brace_depth = 0
    seq = 1

    def _close_blocks_for_line(line_no: int) -> None:
        while stack and brace_depth <= int(stack[-1].get("close_depth", 0) or 0):
            pos = int(stack.pop().get("index", -1) or -1)
            if 0 <= pos < len(blocks):
                blocks[pos].range.end_line = max(blocks[pos].range.start_line, line_no)
                blocks[pos].metadata["brace_depth_after"] = brace_depth

    for idx, raw in enumerate(lines, start=1):
        code = re.sub(r"//.*", "", raw).strip()
        code = re.sub(r"/\*.*?\*/", "", code).strip()
        if not code:
            continue
        leading_close_count = len(re.match(r"^\s*}*", code).group(0) or "")
        if leading_close_count:
            brace_depth = max(0, brace_depth - leading_close_count)
            _close_blocks_for_line(idx)
            code = code[leading_close_count:].strip()
            if not code:
                continue
        else:
            _close_blocks_for_line(max(1, idx - 1))
        kind = ""
        cond = ""
        header = code.lstrip()
        full_header, header_end = _extract_control_header(lines, idx, backend_module=legacy)
        full_header = full_header.lstrip() or header
        if re.match(r"^if\s*\(", header):
            kind = "if"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^else\s+if\s*\(", header):
            kind = "else_if"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^else\b", header):
            kind = "else"
        elif re.match(r"^for\s*\(", header):
            kind = "for"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^while\s*\(", header):
            kind = "while"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^switch\s*\(", header):
            kind = "switch"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^case\b", header):
            kind = "case"
            cond = re.sub(r"^case\s+", "", header).split(":", 1)[0].strip()
        elif re.match(r"^default\b", header):
            kind = "default"
        if kind:
            block_id = f"b{seq}"
            seq += 1
            parent = str(stack[-1].get("id") or "") if stack else ""
            current_depth = brace_depth
            if kind in {"else_if", "else"} and (not parent):
                previous = blocks[-1] if blocks else None
                if previous and previous.kind in {"if", "else_if"}:
                    parent = previous.parent
                    current_depth = int((previous.metadata or {}).get("brace_depth_before") or current_depth)
            blocks.append(
                BlockFact(
                    id=block_id,
                    kind=kind,
                    parent=parent,
                    condition=cond,
                    range=_range_for_lines(idx, max(idx, header_end), raw),
                    source="lsp" if kind in {"if", "else_if", "else", "for", "while", "switch", "case", "default"} else "structured",
                    confidence=0.95,
                    verified=True,
                    metadata={"brace_depth_before": current_depth},
                )
            )
            if kind not in {"case", "default"}:
                close_depth = current_depth if "{" in code else current_depth - 1
                stack.append({"id": block_id, "index": len(blocks) - 1, "close_depth": close_depth})
        brace_depth += code.count("{")
        brace_depth -= code.count("}")
        brace_depth = max(0, brace_depth)
        _close_blocks_for_line(idx)
    final_line = max(1, len(lines))
    while stack:
        pos = int(stack.pop().get("index", -1) or -1)
        if 0 <= pos < len(blocks):
            blocks[pos].range.end_line = max(blocks[pos].range.start_line, final_line)
            blocks[pos].metadata["brace_depth_after"] = brace_depth

    def _compute_end_line(start_line: int, start_depth: int) -> int:
        depth = max(0, int(start_depth or 0))
        saw_body = False
        for line_no in range(max(1, start_line), final_line + 1):
            raw_line = lines[line_no - 1]
            code_line = re.sub(r"//.*", "", raw_line)
            code_line = re.sub(r"/\*.*?\*/", "", code_line)
            depth += code_line.count("{")
            depth -= code_line.count("}")
            depth = max(0, depth)
            if depth > start_depth:
                saw_body = True
            if saw_body and depth <= start_depth:
                return line_no
        return final_line

    resolved = sorted(
        blocks,
        key=lambda item: (int(item.range.start_line or 0), int(re.sub(r"\D+", "", item.id or "0") or 0)),
    )
    for block in resolved:
        start_line = max(1, int(block.range.start_line or 0))
        start_depth = int((block.metadata or {}).get("brace_depth_before") or 0)
        block.range.end_line = max(start_line, _compute_end_line(start_line, start_depth))

    for idx, block in enumerate(resolved):
        best_parent = ""
        best_start = -1
        block_start = int(block.range.start_line or 0)
        for candidate in resolved[:idx]:
            cand_start = int(candidate.range.start_line or 0)
            cand_end = int(candidate.range.end_line or 0)
            if cand_start < block_start <= cand_end and cand_start > best_start:
                best_parent = candidate.id
                best_start = cand_start
        block.parent = best_parent
    return resolved


def _collect_calls(body: str, semantic_pack: dict[str, Any], source_file: str) -> list[CallFact]:
    legacy = legacy_backend()
    comment_map: dict[str, str] = {}
    try:
        func_list, _ = legacy.prepare_func_list_for_c_file(source_file, project_root="", cfg=None, prefilter=False)
    except Exception:
        func_list = []
    for item in func_list or []:
        fi = dict((item or {}).get("func_info") or {})
        ci = dict((item or {}).get("comment_info") or {})
        name = utils._safe_strip(fi.get("func_name"))
        desc = parse_utils.extract_effective_comment_desc(
            ci.get("raw") or ci.get("comment") or ci.get("block") or "",
            parsed_desc=utils._safe_strip(ci.get("desc")),
            func_name=name,
        )
        if name and desc:
            comment_map[name] = desc

    lines = legacy._join_c_line_continuations(body or "").splitlines()
    out: list[CallFact] = []
    seen: set[tuple[str, int]] = set()
    known_callees = set(str(x).strip() for x in (semantic_pack.get("callee_names") or []) if str(x).strip())
    for idx, raw in enumerate(lines, start=1):
        code = re.sub(r"//.*", "", raw)
        code = re.sub(r"/\*.*?\*/", "", code)
        if not code.strip():
            continue
        for match in _CALL_RE.finditer(code):
            callee = utils._safe_strip(match.group(1))
            if not callee or callee in legacy._C_KEYWORDS or callee in {"sizeof"}:
                continue
            if (callee, idx) in seen:
                continue
            seen.add((callee, idx))
            out.append(
                CallFact(
                    callee=callee,
                    call_text=utils._safe_strip(code),
                    signature=f"{callee}(...)",
                    definition_file=source_file if callee in known_callees else "",
                    definition_line=idx if callee in known_callees else 0,
                    definition_comment=comment_map.get(callee, ""),
                    range=_range_for_lines(idx, idx, raw),
                    source="callHierarchy" if callee in known_callees else "structured",
                    confidence=0.82 if callee in known_callees else 0.58,
                    verified=bool(callee in known_callees),
                )
            )
    return out


def _collect_members(body: str, type_map: dict[str, str]) -> list[MemberFact]:
    legacy = legacy_backend()
    out: list[MemberFact] = []
    seen: set[str] = set()
    for raw in legacy._join_c_line_continuations(body or "").splitlines():
        code, _ = legacy._split_code_and_comments_for_symbol(raw)
        stmt = utils._safe_strip(code)
        if not stmt:
            continue
        for match in _MEMBER_RE.finditer(stmt):
            base = utils._safe_strip(match.group("base"))
            member = utils._safe_strip(match.group("member"))
            key = f"{base}->{member}"
            if not base or not member or key in seen:
                continue
            seen.add(key)
            out.append(
                MemberFact(
                    base=base,
                    member=member,
                    owner_type=utils._safe_strip(type_map.get(base) or type_map.get(re.sub(r"\[[^\]]+\]", "", base))),
                    access_text=f"{base}->{member}",
                    source="typeDefinition",
                    confidence=0.72,
                    verified=bool(type_map.get(base) or type_map.get(re.sub(r"\[[^\]]+\]", "", base))),
                )
            )
    return out


def _collect_accesses(body: str) -> tuple[list[AccessFact], list[AccessFact]]:
    reads: list[AccessFact] = []
    writes: list[AccessFact] = []
    for item in _collect_code_statements(body):
        for code_stmt in _extract_inline_braced_statements(utils._safe_strip(item.get("code"))):
            stmt = _strip_case_label_from_statement(utils._safe_strip(code_stmt).rstrip(";"))
            if not stmt:
                continue
            match = _ASSIGN_RE.match(stmt)
            if not match:
                continue
            lhs = utils._safe_strip(match.group("lhs"))
            rhs = utils._safe_strip(match.group("rhs"))
            op = utils._safe_strip(match.group("op"))
            if not lhs or not rhs:
                continue
            if re.match(r"^(?:for|if|while|switch)\s*\(", lhs, flags=re.IGNORECASE):
                continue
            if _DECL_ASSIGN_LHS_RE.match(lhs):
                continue
            writes.append(
                AccessFact(
                    expr=stmt,
                    kind="write",
                    lhs=lhs,
                    rhs=rhs,
                    range=_range_for_lines(int(item.get("start_line") or 0), int(item.get("end_line") or 0), utils._safe_strip(item.get("raw"))),
                    source="references",
                    confidence=0.8,
                    verified=True,
                    metadata={"op": op} if op and op != "=" else {},
                )
            )
            reads.append(
                AccessFact(
                    expr=rhs,
                    kind="read",
                    lhs=lhs,
                    rhs=rhs,
                    range=_range_for_lines(int(item.get("start_line") or 0), int(item.get("end_line") or 0), utils._safe_strip(item.get("raw"))),
                    source="references",
                    confidence=0.8,
                    verified=True,
                )
            )
    return reads, writes


def _try_build_lsp_fact_pack(func_data: dict[str, Any], cfg: Optional[Any] = None, *, backend_module=None) -> dict[str, Any]:
    legacy = backend_module or legacy_backend()
    if not bool(utils.cfg_get_int(cfg, "logic_use_lsp", 1)):
        return {}
    file_context = dict((func_data or {}).get("file_context") or {})
    source_file = utils._safe_strip(file_context.get("source_file"))
    if not source_file or not os.path.exists(source_file):
        return {}
    try:
        from . import lsp_adapter as lsp_adapter_utils
        from . import lsp_gateway as lsp_gateway_utils
    except Exception:
        return {}
    gateway = lsp_gateway_utils.get_lsp_gateway(backend_module=legacy)
    raw_bundle = gateway.collect_function_bundle(func_data, cfg) or {}
    if not raw_bundle:
        return {}
    payload = lsp_adapter_utils.build_fact_pack_from_lsp(
        dict((func_data or {}).get("func_info") or {}),
        raw_bundle,
        utils._safe_text(raw_bundle.get("source_text") or ""),
        cfg,
    )
    if not isinstance(payload, dict):
        return {}
    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "provider": "lsp",
            "source_file": source_file,
            "file_mtime": _get_file_mtime(source_file),
            "fact_schema_version": _FACT_SCHEMA_VERSION,
        }
    )
    payload["metadata"] = metadata
    return payload


def _try_build_fallback_fact_pack(func_data: dict[str, Any], cfg: Optional[Any] = None, *, backend_module=None) -> dict[str, Any]:
    legacy = backend_module or legacy_backend()
    func_info = dict((func_data or {}).get("func_info") or {})
    file_context = dict((func_data or {}).get("file_context") or {})
    body = utils._safe_text((func_data or {}).get("body"))
    source_file = utils._safe_strip(file_context.get("source_file"))
    func_name = utils._safe_strip(func_info.get("func_name"))
    if (not func_name) or (not body):
        return asdict(FunctionFactPack())

    semantic_pack = {}
    try:
        from .semantic_pack import build_function_semantic_pack

        semantic_pack = build_function_semantic_pack(func_data, cfg) or {}
    except Exception:
        semantic_pack = {}

    params = legacy.parse_params_from_prototype(func_info)
    local_vars = legacy.parse_local_variables_from_body(body)
    local_vars = legacy._filter_local_vars_against_params(local_vars, params, cfg=cfg, func_name=func_name)
    type_map = {
        utils._safe_strip((item or {}).get("name")): utils._safe_strip((item or {}).get("type"))
        for item in list(params or []) + list(local_vars or [])
        if utils._safe_strip((item or {}).get("name"))
    }
    pack = FunctionFactPack(
        function=FunctionFact(
            name=func_name,
            signature=utils._safe_strip(func_info.get("prototype")),
            range=_guess_function_range(func_data, source_file, body),
            source="structured",
            confidence=0.88,
            verified=bool(source_file),
        ),
        blocks=_collect_blocks(body),
        locals=[
            LocalFact(
                name=utils._safe_strip((item or {}).get("name")),
                decl_type=utils._safe_strip((item or {}).get("type")),
                scope="local",
                decl_range=_range_for_lines(0, 0),
                source="documentSymbol",
                confidence=0.8,
                verified=True,
            )
            for item in (local_vars or [])
            if utils._safe_strip((item or {}).get("name"))
        ],
        calls=_collect_calls(body, semantic_pack, source_file),
        members=_collect_members(body, type_map),
        metadata={
            "provider": utils.cfg_get_str(cfg, "semantic_provider", "structured"),
            "source_file": source_file,
            "file_mtime": _get_file_mtime(source_file),
            "fact_schema_version": _FACT_SCHEMA_VERSION,
        },
    )
    pack.reads, pack.writes = _collect_accesses(body)
    _offset_fact_ranges_to_function_lines(pack)
    return asdict(pack)


def _assess_lsp_quality(payload: dict[str, Any]) -> float:
    """评估 LSP 返回数据的质量 (0.0 ~ 1.0)。"""
    score = 0.5
    blocks = payload.get("blocks") or []
    calls = payload.get("calls") or []
    members = payload.get("members") or []
    locals_ = payload.get("locals") or []
    if blocks:
        score += 0.15
    if calls and any(c.get("signature") for c in calls if isinstance(c, dict)):
        score += 0.15
    if members and any(m.get("owner_type") for m in members if isinstance(m, dict)):
        score += 0.1
    if locals_ and any(l.get("decl_type") for l in locals_ if isinstance(l, dict)):
        score += 0.1
    return min(score, 1.0)


def _payload_misses_obvious_body_structure(payload: dict[str, Any], body: str) -> bool:
    text_value = str(body or "")
    if not text_value.strip():
        return False
    has_control = bool(re.search(r"\b(?:if|for|while|switch)\s*\(", text_value))
    has_assignment = bool(re.search(r"(?<![=!<>])=(?![=])", text_value))
    has_call = bool(re.search(r"\b[A-Za-z_]\w*\s*\(", text_value))
    if not (has_control or has_assignment or has_call):
        return False
    blocks = payload.get("blocks") or []
    writes = payload.get("writes") or []
    calls = payload.get("calls") or []
    if has_control and blocks:
        return False
    if has_assignment and writes:
        return False
    if has_call and calls:
        return False
    return not (blocks or writes or calls)


def build_function_fact_pack(func_data: dict[str, Any], cfg: Optional[Any] = None, *, backend_module=None) -> dict[str, Any]:
    legacy = backend_module or legacy_backend()
    func_info = dict((func_data or {}).get("func_info") or {})
    file_context = dict((func_data or {}).get("file_context") or {})
    body = utils._safe_text((func_data or {}).get("body"))
    source_file = utils._safe_strip(file_context.get("source_file"))
    func_name = utils._safe_strip(func_info.get("func_name"))
    if (not func_name) or (not body):
        return asdict(FunctionFactPack())

    cache_key = _make_cache_key({**dict(func_data or {}), "cfg": cfg}, source_file)
    cache_mtime = _get_file_mtime(source_file)
    cached = _FACT_CACHE.get(cache_key)
    if cached and cached[0] == cache_mtime:
        return dict(cached[1] or {})
    payload = _try_build_lsp_fact_pack(func_data, cfg, backend_module=legacy)
    if payload:
        lsp_quality = _assess_lsp_quality(payload)
        misses_structure = _payload_misses_obvious_body_structure(payload, body)
        if lsp_quality < 0.3 or misses_structure:
            fallback = _try_build_fallback_fact_pack(func_data, cfg, backend_module=legacy)
            if misses_structure or _assess_lsp_quality(fallback) > lsp_quality:
                payload = fallback
                payload.setdefault("metadata", {})["lsp_degraded"] = True
                reason = "结构事实缺失" if misses_structure else f"数据质量低({lsp_quality:.0%})"
                utils.vlog(cfg, f"[LSP] {func_name} {reason}，已选择纯规则解析")
    if not payload:
        payload = _try_build_fallback_fact_pack(func_data, cfg, backend_module=legacy)
        payload.setdefault("metadata", {})["lsp_degraded"] = True
        utils.vlog(cfg, f"[LSP] {func_name} clangd 不可用，已回退到纯规则解析")
    if len(_FACT_CACHE) >= _FACT_CACHE_MAX:
        oldest_key = next(iter(_FACT_CACHE))
        del _FACT_CACHE[oldest_key]
    _FACT_CACHE[cache_key] = (cache_mtime, payload)
    return payload


__all__ = ["build_function_fact_pack", "_try_build_fallback_fact_pack", "_try_build_lsp_fact_pack"]
