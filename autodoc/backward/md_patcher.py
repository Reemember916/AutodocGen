"""Targeted Markdown patcher — replaces parameter tables in-place.

Uses ``HeaderFileIR`` from ``autodoc.logic_ir`` to locate and substitute
only the parameter table within each ``### 函数:`` section, leaving all
human-written context (headers, descriptions, surrounding narrative)
absolutely untouched.

Compatible with Windows 7 / Python 3.8+, standard-library only.
"""

from __future__ import annotations

import re
from typing import List

from ..logic_ir import (
    CTypeInfo,
    FunctionIR,
    HeaderFileIR,
    ParameterIR,
)


# ── Regexes ─────────────────────────────────────────────────────────────

# Header of the parameter table we are looking for
_TABLE_HEADER_RE = re.compile(
    r"^\|\s*参数名\s*\|\s*类型\s*\|\s*方向\s*\|\s*业务含义\s*\|",
    re.MULTILINE,
)

# Separator row immediately below the header
_TABLE_SEP_RE = re.compile(r"^\|\s*-+\s*\|.*\|$", re.MULTILINE)

# A data row inside the table
_TABLE_ROW_RE = re.compile(
    r"^\|\s*.+?\s*\|\s*.+?\s*\|\s*.+?\s*\|\s*.+?\s*\|",
    re.MULTILINE,
)

# Function section heading
_FUNC_HEADING_RE = re.compile(
    r"^###\s*函数:\s*([A-Za-z_]\w*)\s*$",
    re.MULTILINE,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _type_to_md(type_info: CTypeInfo) -> str:
    """Render a CTypeInfo into the Markdown type string used in the table."""
    parts: List[str] = []
    if type_info.is_const:
        parts.append("const")
    parts.append(type_info.base_type)
    if type_info.is_pointer:
        parts.append("*")
    return " ".join(parts)


def _render_table(params: List[ParameterIR]) -> str:
    """Render a full Markdown parameter table from a list of ParameterIR.

    Returns the table header, separator, and one data row per parameter,
    *without* any trailing newline (the caller adds it when splicing).
    """
    lines: List[str] = []
    lines.append("| 参数名 | 类型 | 方向 | 业务含义 |")
    lines.append("|---|---|---|---|")
    for p in params:
        md_type = _type_to_md(p.type_info)
        meaning = p.business_meaning if p.business_meaning else "（待补充）"
        lines.append(f"| {p.name} | {md_type} | {p.direction} | {meaning} |")
    return "\n".join(lines)


def _find_func_section(md: str, func_name: str) -> int:
    """Return the byte/character offset of the ``### 函数: {func_name}``
    heading, or ``-1`` if not found."""
    for m in _FUNC_HEADING_RE.finditer(md):
        if m.group(1).strip() == func_name:
            return m.start()
    return -1


def _find_table_end(md: str, table_start: int) -> int:
    """Starting from *table_start*, find the end of the table (the offset
    just past the last ``|`` data row).  Returns the end offset; the
    caller preserves ``result[table_end:]`` as post-table context."""
    lines = md[table_start:].splitlines(keepends=True)
    end = table_start
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            # Still inside the table — advance past this row
            end += len(line)
        else:
            # First non-table line: stop here; this line is post-table
            # context and must be preserved by the caller.
            break
    return end


def _find_table_start(md: str, section_start: int) -> int:
    """Starting from *section_start*, find the first occurrence of the
    parameter table header.  Returns its offset, or ``-1``."""
    m = _TABLE_HEADER_RE.search(md, section_start)
    if m is None:
        return -1
    return m.start()


# ── Main patcher class ──────────────────────────────────────────────────


class MarkdownPatcher:
    """Targeted patcher that replaces parameter tables inside a Markdown
    document while preserving all human-written context.

    Usage::

        patcher = MarkdownPatcher()
        new_md = patcher.patch_header(old_md, updated_ir)
    """

    def patch_header(self, original_md: str, updated_ir: HeaderFileIR) -> str:
        """Patch the parameter tables inside *original_md* with fresh data
        from *updated_ir*.

        For each function in *updated_ir*:
        1. Locate the ``### 函数: {name}`` heading.
        2. Within that section, find the parameter table.
        3. Replace the old table with a new one rendered from the IR.
        4. Preserve all surrounding text.

        Returns the updated Markdown string.
        """
        if not original_md:
            return ""

        result = original_md

        for func in updated_ir.functions:
            if not func.name:
                continue

            section_start = _find_func_section(result, func.name)
            if section_start < 0:
                # Function heading not found — skip
                continue

            table_start = _find_table_start(result, section_start)
            if table_start < 0:
                # No existing table — append one after the function fields
                table_start = self._find_insertion_point(result, section_start)
                if table_start < 0:
                    continue
                # Insert a new table
                new_table = _render_table(func.parameters)
                result = (
                    result[:table_start]
                    + "\n"
                    + new_table
                    + "\n"
                    + result[table_start:]
                )
                continue

            table_end = _find_table_end(result, table_start)
            new_table = _render_table(func.parameters)

            result = result[:table_start] + new_table + result[table_end:]

        return result

    # ── internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _find_insertion_point(md: str, section_start: int) -> int:
        """Find where to insert a new table when none exists in the section.

        Walks forward from *section_start* looking for:
        1. The end of the ``- 返回值:`` line (preferred insertion point).
        2. If not found, the end of the function heading line.
        3. If neither works, the end of the section.

        Returns the insertion offset (end of the line to insert after).
        """
        lines = md[section_start:].splitlines(keepends=True)
        cumulative = section_start
        for line in lines:
            stripped = line.strip()
            # Insert after the last field line (- 中文名 / - 描述 / - 返回值)
            if stripped.startswith("- ") and ":" in stripped:
                cumulative += len(line)
                continue
            # Stop at the first blank line or heading after the fields
            if not stripped or stripped.startswith("#") or stripped.startswith("|"):
                return cumulative
            if stripped.startswith(">") or stripped.startswith("```"):
                return cumulative
            cumulative += len(line)
        return cumulative