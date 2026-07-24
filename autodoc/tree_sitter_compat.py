"""Compatibility helpers for optional tree-sitter C parsing."""

from __future__ import annotations

_LANGUAGE_CACHE = []


def create_c_parser():
    """Return a C parser across tree-sitter 0.21 and newer bindings.

    The 0.21 grammar wheel exposes an integer language pointer and requires a
    language name. Newer wheels expose a capsule accepted as the sole argument.
    """
    import tree_sitter_c as tsc
    from tree_sitter import Language, Parser

    raw_language = tsc.language()
    try:
        language = Language(raw_language)
    except TypeError:
        language = Language(raw_language, "c")
    # tree-sitter 0.21 Parser does not retain a Python reference to Language.
    _LANGUAGE_CACHE.append(language)
    parser = Parser()
    try:
        parser.set_language(language)
    except AttributeError:
        parser.language = language
    return parser


__all__ = ["create_c_parser"]
