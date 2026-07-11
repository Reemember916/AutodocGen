"""Extract struct/union member trees from C source via tree-sitter."""

from __future__ import annotations

import re
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
class StructMember:
    name: str
    type_name: str
    offset: int


@dataclass
class StructDef:
    name: str
    members: list[StructMember] = field(default_factory=list)


def _code(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _find_all(node, t: str) -> list:
    res = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type == t:
            res.append(cur)
        stack.extend(cur.children)
    return res


def extract_structs(source: str) -> dict[str, StructDef]:
    if _PARSER is None:
        return {}
    source_bytes = source if isinstance(source, bytes) else source.encode("utf-8")
    try:
        tree = _PARSER.parse(source_bytes)
    except Exception:
        return {}
    root = tree.root_node
    out: dict[str, StructDef] = {}

    struct_nodes = _find_all(root, "struct_specifier") + _find_all(root, "union_specifier")
    for sn in struct_nodes:
        name = ""
        fields = []
        for child in sn.children:
            if child.type == "type_identifier":
                name = _code(source_bytes, child)
            elif child.type == "field_declaration":
                field_type = ""
                field_name = ""
                for fc in child.children:
                    if fc.type in ("type_identifier", "primitive_type"):
                        field_type = _code(source_bytes, fc)
                    elif fc.type == "field_identifier":
                        field_name = _code(source_bytes, fc)
                if field_name:
                    fields.append(StructMember(field_name, field_type, child.start_byte))
        if name:
            out[name] = StructDef(name, fields)

    typedef_nodes = _find_all(root, "declaration")
    alias_map: dict[str, str] = {}
    for dn in typedef_nodes:
        text = _code(source_bytes, dn)
        m = re.match(r"typedef\s+(?:struct|union)\s+(\w+)\s+(\w+)\s*;", text)
        if m:
            struct_name, alias = m.group(1), m.group(2)
            if struct_name in out:
                alias_map[alias] = struct_name
    for alias, real in alias_map.items():
        out[alias] = out[real]

    return out


def build_member_symbol_map(source: str) -> dict[str, str]:
    structs = extract_structs(source)
    member_map: dict[str, str] = {}
    for sname, sdef in structs.items():
        for m in sdef.members:
            if m.name and m.name not in member_map:
                member_map[m.name] = m.type_name
    return member_map
