"""Extract function call graph from C source via tree-sitter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .tree_sitter_compat import create_c_parser

try:
    _PARSER = create_c_parser()
except Exception:
    _PARSER = None


@dataclass
class FuncDef:
    name: str
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)


@dataclass
class CallGraph:
    functions: dict[str, FuncDef] = field(default_factory=dict)

    def callers_of(self, name: str) -> list[str]:
        return [fn for fn, fd in self.functions.items() if name in fd.calls]


def _code(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _line(source_bytes: bytes, byte: int) -> int:
    return source_bytes[:byte].count(b"\n") + 1


def build_call_graph(source: str) -> Optional[CallGraph]:
    if _PARSER is None:
        return None
    source_bytes = source if isinstance(source, bytes) else source.encode("utf-8")
    try:
        tree = _PARSER.parse(source_bytes)
    except Exception:
        return None
    root = tree.root_node
    graph = CallGraph()

    def _find_by_type(node, t: str) -> list:
        out = []
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type == t:
                out.append(n)
            stack.extend(n.children)
        return out

    func_nodes = _find_by_type(root, "function_definition")
    for fn in func_nodes:
        fn_name_node = None
        declarator = _first_child_of_type(fn, "function_declarator")
        if declarator:
            fn_name_node = _first_child_of_type(declarator, "identifier")
        if fn_name_node is None:
            continue
        name = _code(source_bytes, fn_name_node)
        start_line = _line(source_bytes, fn.start_byte)
        end_line = _line(source_bytes, fn.end_byte)
        calls = []
        call_nodes = _find_by_type(fn, "call_expression")
        for cn in call_nodes:
            callee = _first_child_of_type(cn, "identifier")
            if callee:
                callee_name = _code(source_bytes, callee)
                if callee_name != name:
                    calls.append(callee_name)
        graph.functions[name] = FuncDef(name, start_line, end_line, calls)
    return graph


def flatten_call_tree(
    callees_map: dict[str, list[str]],
    entry: str,
    *,
    max_depth: int = 3,
    name_map: Optional[dict[str, str]] = None,
) -> list[tuple[str, str, str, str]]:
    """Flatten a call tree rooted at *entry* into 4-column rows.

    Each row is ``(level0, level1, level2, level3)`` where level0 is the
    entry function and subsequent columns are successive callee depths.
    Leaf positions are filled with ``"-"``.  *name_map* optionally maps
    C identifiers to display names (e.g. Chinese titles).
    """
    nm = name_map or {}

    def _label(ident: str) -> str:
        return nm.get(ident) or ident

    rows: list[tuple[str, str, str, str]] = []
    visited: set[str] = set()

    def _walk(node: str, depth: int, prefix: list[str]) -> None:
        if depth > max_depth or node in visited:
            return
        visited.add(node)
        children = list(dict.fromkeys(callees_map.get(node, [])))
        children = [c for c in children if c != node and c not in visited]
        if not children or depth == max_depth:
            cols = list(prefix) + [_label(node)]
            while len(cols) < 4:
                cols.append("-")
            rows.append(tuple(cols[:4]))  # type: ignore[arg-type]
            visited.discard(node)
            return
        for child in children:
            _walk(child, depth + 1, prefix + [_label(node)])
        visited.discard(node)

    _walk(entry, 0, [])
    return rows


def find_entry_functions(callees_map: dict[str, list[str]]) -> list[str]:
    """Return functions that are not called by any other function (roots)."""
    all_callees: set[str] = set()
    for calls in callees_map.values():
        all_callees.update(calls)
    return [fn for fn in callees_map if fn not in all_callees]


def build_project_callees_map(func_entries: list[dict]) -> dict[str, list[str]]:
    """Build a project-wide callees_map from preprocessed func_entries."""
    m: dict[str, list[str]] = {}
    for fd in func_entries or []:
        func_info = (fd or {}).get("func_info") or {}
        name = str(func_info.get("func_name") or "").strip()
        if not name:
            continue
        fc = (fd or {}).get("file_context") or {}
        callees = list(fc.get("callee_funcs") or [])
        if not callees:
            sr = (fd or {}).get("semantic_record") or {}
            callees = list(sr.get("callee_names") or [])
        m[name] = list(dict.fromkeys(c for c in callees if c and c != name))
    return m


def _first_child_of_type(node, t: str):
    for c in node.children:
        if c.type == t:
            return c
    return None
