"""Extract function call graph from C source via tree-sitter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import tree_sitter_c as tsc
from tree_sitter import Language, Parser

try:
    _LANG = Language(tsc.language())
    _PARSER = Parser(_LANG)
except Exception:
    _LANG = None
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


def _first_child_of_type(node, t: str):
    for c in node.children:
        if c.type == t:
            return c
    return None
