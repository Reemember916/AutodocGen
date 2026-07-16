"""Static AST Facts extractor — tree-sitter based C header analysis.

Consumes tree-sitter C AST and produces ``autodoc.logic_ir`` typed objects
(HeaderFileIR, FunctionIR, ParameterIR, MacroIR, CTypeInfo).

Compatible with Windows 7 / Python 3.8+, standard-library only beyond
``tree-sitter`` + ``tree-sitter-c``.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..logic_ir import (
    CTypeInfo,
    FunctionIR,
    HeaderFileIR,
    MacroIR,
    ParameterIR,
)

# ── Regex patterns for reverse-extracting structured comment fields ─────

_RE_CHINESE_NAME = re.compile(r"\[函数中文名\]\s*(.+?)(?:\s*\*\/|\s*$)", re.MULTILINE)
_RE_DESCRIPTION = re.compile(r"\[功能描述\]\s*(.+?)(?:\s*\*\/|\s*$)", re.MULTILINE)
_RE_PARAM_LINE = re.compile(
    r"^\s*\*\s*-\s*(\w+)\s*:\s*\[业务含义\]\s*(.+?)(?:\s*\*\/|\s*$)",
    re.MULTILINE,
)


# ── Helper: node text from byte buffer ──────────────────────────────────


def _node_text(source_bytes: bytes, node) -> str:
    try:
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


# ── Helper: preceding comment ────────────────────────────────────────────


def _preceding_comment(
    source_bytes: bytes, siblings: List, node_index: int
) -> str:
    """Walk backwards from ``node_index`` collecting consecutive comment
    siblings.  Stops at the first non-comment, non-whitespace sibling."""
    parts: List[str] = []
    for idx in range(node_index - 1, -1, -1):
        prev = siblings[idx]
        if prev.type == "comment":
            parts.insert(0, _node_text(source_bytes, prev))
        elif prev.type in ("\n", ")", ""):
            continue
        else:
            break
    return "\n".join(parts)


# ── Helper: extract comment fields ──────────────────────────────────────


def _extract_comment_fields(comment_text: str) -> dict:
    """Return a dict with keys ``chinese_name``, ``description``, and
    ``param_meanings`` (dict of param_name → business_meaning)."""
    result: dict = {
        "chinese_name": "",
        "description": "",
        "param_meanings": {},
    }

    m = _RE_CHINESE_NAME.search(comment_text)
    if m:
        result["chinese_name"] = m.group(1).strip()

    m = _RE_DESCRIPTION.search(comment_text)
    if m:
        result["description"] = m.group(1).strip()

    for m in _RE_PARAM_LINE.finditer(comment_text):
        param_name = m.group(1).strip()
        meaning = m.group(2).strip()
        if param_name and meaning:
            result["param_meanings"][param_name] = meaning

    return result


# ── Helper: extract return type from declaration node ────────────────────


def _extract_return_type(node) -> CTypeInfo:
    """Walk the ``declaration`` or ``function_definition`` node to build
    the return-type CTypeInfo.  Handles ``*`` pointers and ``const``."""
    is_const = False
    is_pointer = False
    base_type = "void"

    for child in node.children:
        if child.type == "type":
            base_type = _node_text(b"", child)  # fallback
            for c in child.children:
                if c.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                    base_type = _node_text(b"", c)
                elif c.type == "storage_class_specifier":
                    if _node_text(b"", c).strip() == "const":
                        is_const = True
        elif child.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
            base_type = _node_text(b"", child)
        elif child.type == "storage_class_specifier":
            if _node_text(b"", child).strip() == "const":
                is_const = True

    # Check if the declarator is a pointer_declarator
    declarator = _find_child(node, "function_declarator")
    if declarator is None:
        declarator = _find_child(node, "declarator")
    if declarator is not None:
        for c in declarator.children:
            if c.type == "pointer_declarator" or c.type == "pointer":
                is_pointer = True
                break

    return CTypeInfo(
        base_type=base_type,
        is_pointer=is_pointer,
        is_const=is_const,
    )


def _find_child(node, child_type: str):
    """Return the first direct child of *node* whose ``type`` equals
    *child_type*, or ``None``."""
    for c in node.children:
        if c.type == child_type:
            return c
    return None


# ── Helper: extract parameters from function_declarator ──────────────────


def _extract_parameters(
    func_decl_node, source_bytes: bytes, param_meanings: dict
) -> List[ParameterIR]:
    """Extract parameter list from a ``function_declarator`` node.

    Each ``parameter_declaration`` child is parsed for type, name, and
    pointer qualifier.  The *param_meanings* dict (from comment fields) is
    used to backfill ``business_meaning``.
    """
    params: List[ParameterIR] = []

    param_list = _find_child(func_decl_node, "parameter_list")
    if param_list is None:
        return params

    for child in param_list.children:
        if child.type != "parameter_declaration":
            continue

        p_type = ""
        p_name = ""
        p_is_pointer = False
        p_is_const = False

        for sub in child.children:
            if sub.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                p_type = _node_text(source_bytes, sub)
            elif sub.type == "pointer_declarator":
                p_is_pointer = True
                for sub2 in sub.children:
                    if sub2.type == "identifier":
                        p_name = _node_text(source_bytes, sub2)
            elif sub.type == "identifier":
                if not p_name:
                    p_name = _node_text(source_bytes, sub)
            elif sub.type == "type_qualifier":
                if _node_text(source_bytes, sub).strip() == "const":
                    p_is_const = True

        if not p_type:
            continue

        # C 语言约定: void 作为唯一参数表示"无参数"（如 Foo(void)）
        if p_type == "void" and not p_name:
            continue

        name = p_name if p_name else f"unnamed_{len(params)}"
        params.append(
            ParameterIR(
                name=name,
                type_info=CTypeInfo(
                    base_type=p_type,
                    is_pointer=p_is_pointer,
                    is_const=p_is_const,
                ),
                direction="IN",
                business_meaning=param_meanings.get(name, ""),
            )
        )

    return params


# ── Helper: extract macro ────────────────────────────────────────────────


def _extract_macro(preproc_node, source_bytes: bytes, description: str) -> Optional[MacroIR]:
    """Extract a MacroIR from a ``preproc_def`` node."""
    name = ""
    value = ""
    for child in preproc_node.children:
        if child.type == "identifier":
            name = _node_text(source_bytes, child)
        elif child.type == "preproc_arg":
            value = _node_text(source_bytes, child).strip()

    if not name:
        return None
    return MacroIR(name=name, value=value, description=description)


# ── Main extractor class ─────────────────────────────────────────────────


class CAsTExtractor:
    """Static facts extractor — tree-sitter C AST → HeaderFileIR.

    Usage::

        extractor = CAsTExtractor()
        ir = extractor.extract_header(c_code, "my_header.h")
    """

    def __init__(self) -> None:
        self._parser = self._init_parser()

    # ── parser initialisation ──────────────────────────────────────────

    @staticmethod
    def _init_parser():
        """Lazy-init the tree-sitter C parser; returns ``None`` on failure
        so that every public method can degrade gracefully."""
        try:
            import tree_sitter_c as tsc
            from tree_sitter import Language, Parser

            return Parser(Language(tsc.language()))
        except Exception:
            return None

    # ── public API ─────────────────────────────────────────────────────

    def extract_header(self, c_code: str, file_name: str) -> HeaderFileIR:
        """Parse *c_code* and return a complete ``HeaderFileIR``.

        Degrades gracefully: when tree-sitter is unavailable returns an
        empty ``HeaderFileIR`` with just the *file_name* set.
        """
        if self._parser is None:
            return HeaderFileIR(file_name=file_name)

        source_bytes = c_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        macros: List[MacroIR] = []
        functions: List[FunctionIR] = []

        # Collect all top-level siblings for preceding-comment lookups
        siblings = list(root.children)

        for idx, node in enumerate(siblings):
            if node.type == "preproc_def":
                desc = _preceding_comment(source_bytes, siblings, idx)
                macro = _extract_macro(node, source_bytes, desc)
                if macro is not None:
                    macros.append(macro)

            elif node.type == "declaration":
                # Check if this declaration contains a function declarator
                func_decl = _find_child(node, "function_declarator")
                if func_decl is None:
                    func_decl = _find_child(node, "declarator")
                    if func_decl is not None:
                        func_decl = _find_child(func_decl, "function_declarator")
                if func_decl is None:
                    continue

                # Name
                func_name = ""
                for c in func_decl.children:
                    if c.type == "identifier":
                        func_name = _node_text(source_bytes, c)
                        break
                    elif c.type == "pointer_declarator":
                        for c2 in c.children:
                            if c2.type == "identifier":
                                func_name = _node_text(source_bytes, c2)
                                break
                if not func_name:
                    continue

                # Preceding comment
                comment_text = _preceding_comment(source_bytes, siblings, idx)
                fields = _extract_comment_fields(comment_text)

                # Return type
                return_type = _extract_return_type(node)
                for c in node.children:
                    if c.type in ("primitive_type", "type_identifier", "sized_type_specifier"):
                        return_type = CTypeInfo(
                            base_type=_node_text(source_bytes, c),
                            is_pointer=False,
                            is_const=False,
                        )

                # Parameters
                params = _extract_parameters(
                    func_decl, source_bytes, fields["param_meanings"]
                )

                # Direction inference from comment
                for p in params:
                    if p.name in fields["param_meanings"]:
                        p.direction = "IN"
                if params and params[-1].type_info.is_pointer:
                    params[-1].direction = "OUT"

                functions.append(
                    FunctionIR(
                        name=func_name,
                        chinese_name=fields["chinese_name"],
                        description=fields["description"],
                        return_type=return_type,
                        parameters=params,
                    )
                )

        return HeaderFileIR(
            file_name=file_name,
            brief_description="",
            macros=macros,
            functions=functions,
        )