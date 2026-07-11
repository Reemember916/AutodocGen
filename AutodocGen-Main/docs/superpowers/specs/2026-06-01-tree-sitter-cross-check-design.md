# Tree-sitter Cross-check Design

Date: 2026-06-01

## Goal

Add a low-risk Tree-sitter cross-check for C function parsing. The existing regex parser remains the source of truth. Tree-sitter runs beside it and reports mismatches so parser gaps can be measured before replacing regex behavior.

## Current State

`autodoc.parse._parse_c_file_base()` strips inactive preprocessor regions, finds comments, then uses `find_function_prototypes()` and `extract_function_body()` to build function records.

`autodoc.callgraph` and `autodoc.struct_tree` already use `tree_sitter` and `tree_sitter_c`, so the dependency path exists.

The parser has no direct Tree-sitter function-definition extraction in `autodoc.parse`.

## Recommended Approach

Add a private Tree-sitter extraction path in `autodoc.parse`:

- `_extract_tree_sitter_functions(code)` returns lightweight function records.
- `_cross_check_tree_sitter_functions(regex_funcs, ts_funcs, cfg)` compares function names and line spans.
- `_parse_c_file_base(code, cfg=None)` calls the checker after regex function discovery.

The checker logs warnings only. It never changes `funcs`, comments, bodies, typedefs, macros, or generation output.

## Enablement

Cross-check is opt-in through `extra_params["tree_sitter_cross_check"] == "1"` or a direct config attribute with the same name.

Default behavior remains off to avoid noisy logs in normal runs.

## Logged Mismatches

The checker reports:

- Functions found by Tree-sitter but missing from regex.
- Functions found by regex but missing from Tree-sitter.
- Function span differences over a small threshold.

Logs go through existing `utils_module.vlog(cfg, ...)` so they respect verbose logging behavior.

## Error Handling

If Tree-sitter is unavailable, parsing fails, or node extraction hits an unexpected shape, the checker returns no results and the regex parser continues unchanged.

No exception from the cross-check may escape into document generation.

## Test Plan

Add focused parser tests:

- Tree-sitter extractor finds normal C functions.
- Cross-check reports missing functions when regex and Tree-sitter sets differ.
- `_parse_c_file_base()` still returns regex results when Tree-sitter fails or is unavailable.

## Scope Boundaries

This change does not replace regex parsing.

This change does not alter body extraction.

This change does not change comment association.

This change does not parse macros, typedefs, includes, or struct members with Tree-sitter.
