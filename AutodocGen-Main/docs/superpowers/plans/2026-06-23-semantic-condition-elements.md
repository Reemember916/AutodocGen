# Semantic Condition Elements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Use TDD. Do not run project-wide commands inside subagents.

**Goal:** Add the first semantic-element vertical slice for C condition rendering. AI must not write final logic text; rules render validated semantic fields into deterministic GJB-style phrases.

**Architecture:** Add `autodoc.semantic_elements` between expression parsing and logic rendering. It infers `ConditionSemantic` from supported C comparisons, renders short phrases such as `报文头低8位等于RS422帧头1`, and falls back to current logic rendering when unsupported.

## Task 1: Semantic condition model

**Files:** `autodoc/semantic_elements.py`, `tests/test_pipeline_quality_repairs.py`

- [ ] Add failing tests near existing condition renderer tests:
  - `infer_condition_semantic("RS422_COMM_FRAME_HEAD_1 == (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] & 0xFFU)", name_map)` returns `ConditionSemantic(left_label="报文头低8位", relation="equals", right_label="RS422帧头1")`.
  - `render_condition_semantic()` returns `报文头低8位等于RS422帧头1`.
  - `v_commID_u16 < COMM422_ID_NUM` renders `RS422通道号小于RS422通道数量`.
- [ ] Run RED: `python3 -m pytest tests/test_pipeline_quality_repairs.py -k "condition_semantic" -v`.
- [ ] Create `autodoc/semantic_elements.py` with frozen dataclasses:
  - `SemanticElement(kind, target_id, label, role, confidence, source, evidence_ids)`
  - `ConditionSemantic(left_label, relation, right_label, confidence, source, evidence_ids)`
- [ ] Implement `infer_condition_semantic(cond, name_map=None)`:
  - Use existing `logic._split_top_level_comparison()` and `_should_swap_condition_comparison_operands()` lazily inside functions to avoid top-level circular import.
  - Convert operators to relations: `== -> equals`, `!= -> not_equals`, `< -> less_than`, `<= -> less_equal`, `> -> greater_than`, `>= -> greater_equal`.
  - Render operands through `c_expr.parse_c_expression()` + `c_expr.render_expr_cn()`.
  - Normalize labels by removing spaces; preserve deterministic short labels.
  - Return `None` if unsupported or either side cannot be rendered.
- [ ] Implement `render_condition_semantic()` with fixed relation templates only.
- [ ] Run GREEN for the focused tests.

## Task 2: Wire semantic condition path into logic renderer

**Files:** `autodoc/logic.py`, `tests/test_pipeline_quality_repairs.py`

- [ ] Add integration tests for `_render_structured_condition_cn()`:
  - Byte-mask frame-header comparison returns `报文头低8位等于RS422帧头1` and not explanatory prose.
  - With `GenConfig(ai_assist=True, extra_params={"structured_cond_ai":"1", "lock_structured_conditions":"1"})`, AI helper is not called and the semantic rule output wins.
- [ ] Run RED for `condition_semantic or structured_condition` selected tests if needed.
- [ ] In `_render_structured_condition_cn()`, before legacy recursive rendering for comparison expressions, call `semantic_elements.infer_condition_semantic()` and `render_condition_semantic()`.
- [ ] Preserve existing fallback behavior for unsupported expressions, logical `&&/||`, function-call hints, and locked AI behavior.
- [ ] Run focused GREEN: `python3 -m pytest tests/test_pipeline_quality_repairs.py -k "condition_semantic or structured_condition" -v`.

## Task 3: PROJECT smoke and final verification

**Files:** tests only if regressions require targeted assertions.

- [ ] Run focused regression suite:
  - `python3 -m pytest tests/test_pipeline_quality_repairs.py -k "condition_semantic or structured_condition or byte_mask or comm422" -v`
- [ ] Generate PROJECT sample:
  - `python3 AutoDocGen_V1.4.py doc -d /Users/ree/Downloads/PROJECT-2007-0613 -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Communication/Comm422.c --function Comm422FrameCheck -o /tmp/autodoc_eval/Comm422FrameCheck.semantic-condition.docx --codegraph off --verbose`
- [ ] Inspect generated doc text and confirm frame-header conditions remain short GJB-style logic lines, not AI prose.
- [ ] Run full pytest before merge.

## Acceptance

- `autodoc.semantic_elements` exists and is independently unit-tested.
- `_render_structured_condition_cn()` uses semantic conditions for supported simple comparisons.
- AI never writes final condition text in this slice.
- Existing fallback paths remain intact.
- PROJECT `Comm422FrameCheck` output keeps concise `IF ... 时` style.
