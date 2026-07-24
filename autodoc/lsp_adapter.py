"""Translate raw LSP bundle payloads into FunctionFactPack structures."""

from __future__ import annotations

from dataclasses import asdict
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


_ASSIGN_RE = re.compile(r"^(?P<lhs>.+?)(?P<op>\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=|(?<![=!<>])=(?![=]))(?P<rhs>.+)$")
_DECL_ASSIGN_LHS_RE = re.compile(
    r"^(?:(?:static|const|volatile|register|extern)\s+)*"
    r"(?:(?:unsigned|signed)\s+)?"
    r"(?:struct\s+[A-Za-z_]\w*|union\s+[A-Za-z_]\w*|enum\s+[A-Za-z_]\w*|[A-Za-z_]\w*)"
    r"(?:\s*\*+\s*|\s+)"
    r"[A-Za-z_]\w*(?:\s*\[[^\]]*\])?$"
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


def _line_range(start_line: int, end_line: int, text: str = "") -> SourceRange:
    return SourceRange(start_line=max(0, start_line), end_line=max(0, end_line), start_col=1, end_col=max(1, len(text or "")))


def _extract_control_header(lines: list[str], start_idx: int, end_idx: int) -> tuple[str, int]:
    collected: list[str] = []
    paren_depth = 0
    seen_open = False
    last_idx = start_idx
    for idx in range(start_idx, min(end_idx, len(lines)) + 1):
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
        last_idx = idx
        if "{" in code and (not seen_open or paren_depth <= 0):
            break
        if seen_open and paren_depth <= 0:
            break
        if not seen_open:
            break
    return " ".join(collected).strip(), last_idx


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


def _collect_code_statements(source_text: str, function_range: SourceRange) -> list[dict[str, Any]]:
    lines = source_text.splitlines()
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

    start = max(1, function_range.start_line)
    end = min(len(lines), function_range.end_line)
    for idx in range(start, end + 1):
        raw = lines[idx - 1]
        code, _ = parse_utils._split_code_and_comments_for_symbol(raw)
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
        _flush(max(start_line, end))
    return statements


def _flatten_document_symbols(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append(item)
        out.extend(_flatten_document_symbols(list(item.get("children") or [])))
    return out


def _convert_lsp_range(payload: dict[str, Any], text: str = "") -> SourceRange:
    start = dict((payload or {}).get("start") or {})
    end = dict((payload or {}).get("end") or {})
    return SourceRange(
        start_line=int(start.get("line", 0) or 0) + 1,
        end_line=int(end.get("line", 0) or 0) + 1,
        start_col=int(start.get("character", 0) or 0) + 1,
        end_col=int(end.get("character", max(1, len(text or ""))) or max(1, len(text or ""))) + 1,
    )


def _find_function_symbol(name: str, symbols: list[dict[str, Any]]) -> dict[str, Any]:
    target = str(name or "").strip()
    for item in _flatten_document_symbols(symbols):
        kind = int(item.get("kind", 0) or 0)
        if str(item.get("name") or "").strip() == target and kind in {6, 12}:
            return item
    return {}


def _find_function_end_line(lines: list[str], start_idx: int) -> int:
    """Find the closing brace of a function starting at *start_idx* (1-based)."""
    depth = 0
    started = False
    for idx in range(start_idx - 1, len(lines)):
        line = lines[idx]
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
                if started and depth == 0:
                    return idx + 1
    return min(len(lines), start_idx + 1)


def _guess_function_range(function_meta: dict[str, Any], symbols: list[dict[str, Any]], source_text: str) -> SourceRange:
    legacy = legacy_backend()
    func_name = utils._safe_strip(function_meta.get("name") or function_meta.get("func_name"))
    signature = utils._safe_strip(function_meta.get("signature") or function_meta.get("prototype"))
    match = _find_function_symbol(func_name, symbols)
    if match:
        return _convert_lsp_range(dict(match.get("range") or {}))
    lines = source_text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if signature and signature in line:
            return _line_range(idx, min(len(lines), idx + max(1, len((function_meta.get("body") or "").splitlines()) + 1)), line)
        if func_name and re.search(rf"\b{re.escape(func_name)}\s*\(", line):
            body_lines = len((function_meta.get("body") or "").splitlines())
            end_line = min(len(lines), idx + max(1, body_lines)) if body_lines else _find_function_end_line(lines, idx)
            return _line_range(idx, end_line, line)
    return _line_range(1, len(lines), signature or func_name)


def _scan_blocks(source_text: str, function_range: SourceRange) -> list[BlockFact]:
    lines = source_text.splitlines()
    start_line = max(1, function_range.start_line)
    end_line = max(start_line, function_range.end_line or len(lines))
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

    for idx in range(start_line, min(end_line, len(lines)) + 1):
        raw = lines[idx - 1]
        code = re.sub(r"//.*", "", raw).strip()
        code = re.sub(r"/\*.*?\*/", "", code).strip()
        if not code:
            continue
        leading_close_count = len(re.match(r"^}*", code).group(0) or "")
        if leading_close_count:
            brace_depth = max(0, brace_depth - leading_close_count)
            _close_blocks_for_line(idx)
            code = code[leading_close_count:].strip()
            if not code:
                continue
        else:
            _close_blocks_for_line(max(start_line, idx - 1))
        kind = ""
        cond = ""
        full_header, header_end = _extract_control_header(lines, idx, end_line)
        full_header = full_header or code
        if re.match(r"^if\s*\(", code):
            kind = "if"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^else\s+if\s*\(", code):
            kind = "else_if"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^else\b", code):
            kind = "else"
        elif re.match(r"^for\s*\(", code):
            kind = "for"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^while\s*\(", code):
            kind = "while"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^switch\s*\(", code):
            kind = "switch"
            cond = _extract_parenthesized_header_condition(full_header)
        elif re.match(r"^case\b", code):
            kind = "case"
            cond = re.sub(r"^case\s+", "", code).split(":", 1)[0].strip()
        elif re.match(r"^default\b", code):
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
                    range=_line_range(idx, max(idx, header_end), raw),
                    source="documentSymbol",
                    confidence=0.92,
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
    final_line = max(start_line, min(end_line, len(lines)))
    while stack:
        pos = int(stack.pop().get("index", -1) or -1)
        if 0 <= pos < len(blocks):
            blocks[pos].range.end_line = max(blocks[pos].range.start_line, final_line)
            blocks[pos].metadata["brace_depth_after"] = brace_depth

    def _compute_end_line(start_line2: int, start_depth: int) -> int:
        depth = max(0, int(start_depth or 0))
        saw_body = False
        for line_no in range(max(start_line, start_line2), final_line + 1):
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
        block_start = max(start_line, int(block.range.start_line or 0))
        start_depth = int((block.metadata or {}).get("brace_depth_before") or 0)
        block.range.end_line = max(block_start, _compute_end_line(block_start, start_depth))

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


def _collect_accesses(source_text: str, function_range: SourceRange) -> tuple[list[AccessFact], list[AccessFact]]:
    reads: list[AccessFact] = []
    writes: list[AccessFact] = []
    for item in _collect_code_statements(source_text, function_range):
        for code_stmt in _extract_inline_braced_statements(utils._safe_strip(item.get("code"))):
            code = _strip_case_label_from_statement(utils._safe_strip(code_stmt).rstrip(";"))
            if not code:
                continue
            match = _ASSIGN_RE.match(code)
            if not match:
                continue
            lhs = str(match.group("lhs") or "").strip()
            rhs = str(match.group("rhs") or "").strip()
            op = str(match.group("op") or "").strip()
            if not lhs or not rhs:
                continue
            if re.match(r"^(?:for|if|while|switch)\s*\(", lhs, flags=re.IGNORECASE):
                continue
            if _DECL_ASSIGN_LHS_RE.match(lhs):
                continue
            range_data = _line_range(int(item.get("start_line") or 0), int(item.get("end_line") or 0), utils._safe_strip(item.get("raw")))
            writes.append(AccessFact(expr=code, kind="write", lhs=lhs, rhs=rhs, range=range_data, source="references", confidence=0.84, verified=True, metadata={"op": op} if op and op != "=" else {}))
            reads.append(AccessFact(expr=rhs, kind="read", lhs=lhs, rhs=rhs, range=range_data, source="references", confidence=0.84, verified=True))
    return reads, writes


def build_fact_pack_from_lsp(
    function_meta: dict[str, Any],
    raw_bundle: dict[str, Any],
    source_text: str,
    cfg: Optional[Any] = None,
) -> dict[str, Any]:
    legacy = legacy_backend()
    symbols = list(raw_bundle.get("document_symbols") or [])
    function_range = _guess_function_range(function_meta, symbols, source_text)
    blocks = _scan_blocks(source_text, function_range)
    calls = []
    for item in list(raw_bundle.get("calls") or []):
        if not isinstance(item, dict):
            continue
        range_payload = dict(item.get("range") or {})
        hover = dict(item.get("hover") or {})
        definition = dict(item.get("definition") or {})
        call_hierarchy = dict(item.get("call_hierarchy") or {})
        references = item.get("references") or []
        has_references = isinstance(references, list) and len(references) > 0
        base_confidence = 0.86 if call_hierarchy else 0.78
        if has_references:
            base_confidence = min(base_confidence + 0.05, 0.99)
        calls.append(
            CallFact(
                callee=utils._safe_strip(item.get("callee")),
                call_text=utils._safe_strip(item.get("call_text")),
                signature=utils._safe_strip(item.get("signature") or hover.get("signature") or call_hierarchy.get("detail")),
                definition_file=utils._safe_strip(definition.get("uri") or definition.get("file")),
                definition_line=int(definition.get("line", 0) or 0),
                definition_comment=utils._safe_strip(hover.get("comment") or hover.get("detail")),
                range=_convert_lsp_range(range_payload, utils._safe_strip(item.get("call_text"))),
                source="callHierarchy" if call_hierarchy else ("references" if has_references else "definition"),
                confidence=base_confidence,
                verified=bool(definition or call_hierarchy or hover or has_references),
            )
        )
    members = []
    for item in list(raw_bundle.get("members") or []):
        if not isinstance(item, dict):
            continue
        members.append(
            MemberFact(
                base=utils._safe_strip(item.get("base")),
                member=utils._safe_strip(item.get("member")),
                owner_type=utils._safe_strip(item.get("owner_type")),
                access_text=utils._safe_strip(item.get("access_text")),
                source="typeDefinition" if utils._safe_strip(item.get("owner_type")) else "hover",
                confidence=0.86 if utils._safe_strip(item.get("owner_type")) else 0.72,
                verified=bool(utils._safe_strip(item.get("owner_type"))),
            )
        )
    locals_ = []
    for item in list(raw_bundle.get("locals") or []):
        if not isinstance(item, dict):
            continue
        locals_.append(
            LocalFact(
                name=utils._safe_strip(item.get("name")),
                decl_type=utils._safe_strip(item.get("decl_type")),
                scope="local",
                decl_range=_convert_lsp_range(dict(item.get("range") or {}), utils._safe_strip(item.get("decl_text"))),
                source="hover" if item.get("hover") else "documentSymbol",
                confidence=0.82 if item.get("hover") else 0.74,
                verified=bool(item.get("hover") or item.get("type_definition")),
            )
        )
    reads, writes = _collect_accesses(source_text, function_range)
    pack = FunctionFactPack(
        function=FunctionFact(
            name=utils._safe_strip(function_meta.get("name") or function_meta.get("func_name")),
            signature=utils._safe_strip(function_meta.get("signature") or function_meta.get("prototype")),
            range=function_range,
            source="documentSymbol",
            confidence=0.95,
            verified=bool(symbols),
        ),
        blocks=blocks,
        locals=locals_,
        calls=calls,
        members=members,
        reads=reads,
        writes=writes,
        metadata={
            "provider": "lsp",
            "clangd_version": utils._safe_strip(raw_bundle.get("clangd_version")),
            "compile_flags_hash": utils._safe_strip(raw_bundle.get("compile_flags_hash")),
        },
    )
    return asdict(pack)


__all__ = ["build_fact_pack_from_lsp"]
