"""Incrementally modularized AutoDocGen package."""

# Do not import submodules here to avoid circular import issues.
# Use: import autodoc.logic, from autodoc.logic import xxx, etc.

__all__ = [
    "ai",
    "backend",
    "cli",
    "codegraph_adapter",
    "compile_db",
    "context_pack",
    "effects",
    "graph_visuals",
    "logic",
    "lsp_adapter",
    "lsp_facts",
    "lsp_gateway",
    "lsp_transport",
    "models",
    "naming",
    "naming_context",
    "parse",
    "pipeline",
    "render",
    "retry",
    "revision",
    "runtime",
    "scanner",
    "semantic",
    "semantic_pack",
    "semantic_registry",
    "term_checker",
    "text",
    "utils",
]
