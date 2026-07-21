"""Bidirectional IR semantic diff resolver — BiDirectionalResolver.

Compares two ``HeaderFileIR`` snapshots (doc-side vs code-side) and
classifies every macro and function into one of four categories:

- ``FORWARD_CHANGES``   — doc has updates, code does not.
- ``BACKWARD_CHANGES``  — code has updates, doc does not.
- ``CONFLICTS``         — both sides modified the same item differently.
- ``ALIGNED``           — identical on both sides; no action required.

Compatible with Windows 7 / Python 3.8+, standard-library only.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from ..logic_ir import (
    CTypeInfo,
    FunctionIR,
    HeaderFileIR,
    MacroIR,
    ParameterIR,
)


# ── Deep equality helpers ───────────────────────────────────────────────


def _ctypeinfo_eq(a: CTypeInfo, b: CTypeInfo) -> bool:
    """Deep equality for CTypeInfo (all three fields)."""
    return (
        a.base_type == b.base_type
        and a.is_pointer == b.is_pointer
        and a.is_const == b.is_const
    )


def _parameter_eq(a: ParameterIR, b: ParameterIR) -> bool:
    """Deep equality for ParameterIR (name, type, direction, meaning)."""
    if a.name != b.name:
        return False
    if a.direction != b.direction:
        return False
    if a.business_meaning != b.business_meaning:
        return False
    if not _ctypeinfo_eq(a.type_info, b.type_info):
        return False
    if a.bit_fields != b.bit_fields:
        return False
    return True


def _function_signature_eq(a: FunctionIR, b: FunctionIR) -> bool:
    """Return True when two FunctionIR describe the same signature.

    Compares: name, chinese_name, description, return_type, and
    the full parameter list in order.
    """
    if a.name != b.name:
        return False
    if a.chinese_name != b.chinese_name:
        return False
    if a.description != b.description:
        return False
    if not _ctypeinfo_eq(a.return_type, b.return_type):
        return False
    if len(a.parameters) != len(b.parameters):
        return False
    for pa, pb in zip(a.parameters, b.parameters):
        if not _parameter_eq(pa, pb):
            return False
    return True


def _macro_eq(a: MacroIR, b: MacroIR) -> bool:
    """Return True when two MacroIR describe the same macro."""
    if a.name != b.name:
        return False
    if a.value != b.value:
        return False
    if a.description != b.description:
        return False
    return True


# ── Index builders ──────────────────────────────────────────────────────


def _index_macros(
    macros: List[MacroIR],
) -> Dict[str, MacroIR]:
    return {m.name: m for m in macros if m.name}


def _index_functions(
    functions: List[FunctionIR],
) -> Dict[str, FunctionIR]:
    return {f.name: f for f in functions if f.name}


# ── Resolver class ──────────────────────────────────────────────────────


class BiDirectionalResolver:
    """Semantic diff resolver for two HeaderFileIR snapshots.

    Usage::

        resolver = BiDirectionalResolver()
        verdict = resolver.compare_ir(doc_ir, code_ir)
        # verdict == {
        #     "FORWARD_CHANGES":  [...],
        #     "BACKWARD_CHANGES": [...],
        #     "CONFLICTS":        [...],
        #     "ALIGNED":          [...],
        # }
    """

    def compare_ir(
        self,
        doc_ir: HeaderFileIR,
        code_ir: HeaderFileIR,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Compare two IR snapshots and return a structured verdict.

        Returns a dict with four keys, each holding a list of
        result items.  Every item has at least the keys:

        - ``kind``: ``"macro"`` | ``"function"``
        - ``name``: identifier string
        - ``doc``: ``dict`` of the doc-side IR fields (or ``None``)
        - ``code``: ``dict`` of the code-side IR fields (or ``None``)
        """
        result: Dict[str, List[Dict[str, Any]]] = {
            "FORWARD_CHANGES": [],
            "BACKWARD_CHANGES": [],
            "CONFLICTS": [],
            "ALIGNED": [],
        }

        doc_macros = _index_macros(doc_ir.macros)
        code_macros = _index_macros(code_ir.macros)
        all_macro_names = sorted(set(doc_macros) | set(code_macros))

        for name in all_macro_names:
            dm = doc_macros.get(name)
            cm = code_macros.get(name)
            self._classify_macro(name, dm, cm, result)

        doc_funcs = _index_functions(doc_ir.functions)
        code_funcs = _index_functions(code_ir.functions)
        all_func_names = sorted(set(doc_funcs) | set(code_funcs))

        for name in all_func_names:
            df = doc_funcs.get(name)
            cf = code_funcs.get(name)
            self._classify_function(name, df, cf, result)

        return result

    # ── internal classifiers ─────────────────────────────────────────

    @staticmethod
    def _classify_macro(
        name: str,
        doc: MacroIR | None,
        code: MacroIR | None,
        result: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        doc_d = asdict(doc) if doc is not None else None
        code_d = asdict(code) if code is not None else None

        if doc is not None and code is not None:
            if _macro_eq(doc, code):
                result["ALIGNED"].append(
                    {"kind": "macro", "name": name, "doc": doc_d, "code": code_d}
                )
            else:
                result["CONFLICTS"].append(
                    {"kind": "macro", "name": name, "doc": doc_d, "code": code_d}
                )
        elif doc is not None and code is None:
            result["FORWARD_CHANGES"].append(
                {"kind": "macro", "name": name, "doc": doc_d, "code": None}
            )
        elif doc is None and code is not None:
            result["BACKWARD_CHANGES"].append(
                {"kind": "macro", "name": name, "doc": None, "code": code_d}
            )

    @staticmethod
    def _classify_function(
        name: str,
        doc: FunctionIR | None,
        code: FunctionIR | None,
        result: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        doc_d = asdict(doc) if doc is not None else None
        code_d = asdict(code) if code is not None else None

        if doc is not None and code is not None:
            if _function_signature_eq(doc, code):
                result["ALIGNED"].append(
                    {"kind": "function", "name": name, "doc": doc_d, "code": code_d}
                )
            else:
                result["CONFLICTS"].append(
                    {"kind": "function", "name": name, "doc": doc_d, "code": code_d}
                )
        elif doc is not None and code is None:
            result["FORWARD_CHANGES"].append(
                {"kind": "function", "name": name, "doc": doc_d, "code": None}
            )
        elif doc is None and code is not None:
            result["BACKWARD_CHANGES"].append(
                {"kind": "function", "name": name, "doc": None, "code": code_d}
            )