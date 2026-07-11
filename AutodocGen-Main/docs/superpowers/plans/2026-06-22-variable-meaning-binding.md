# Variable Meaning Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve local variable extraction so multi-variable declarations and compact identifier conventions bind the correct Chinese names/usages, especially `FdataAverage` locals (`l_min_f`, `l_max_f`, `l_sum_f`).

**Architecture:** Extend `autodoc.parse.parse_local_variables_from_body()` with a small declaration splitter that handles multiple declarators on one C declaration line and positionally binds split inline-comment labels. Keep the public list-of-dicts contract intact, adding optional source/confidence metadata fields for downstream use.

**Tech Stack:** Python 3, regex-based declaration parsing in `autodoc.parse`, pytest, existing `pipeline` local-data rendering.

---

## File Structure

- Modify: `autodoc/parse.py`
  - Add helpers to split top-level declarators by comma while respecting brackets/parentheses.
  - Add helpers to split compact comment labels such as `最小值，最大值` positionally.
  - Add fallback naming for `min/max/sum/cnt/index/ii/jj` when comments are absent or ambiguous.
  - Preserve existing return dict fields: `type`, `name`, `usage`, `cn_name`, `comment_cn_name`, `comment_hint`.
  - Add optional internal metadata: `name_source`, `name_confidence`.
- Modify: `tests/test_pipeline_quality_repairs.py`
  - Add focused parser tests and a `FdataAverage` local data regression through `build_function_design_impl()` or `prepare_design_context()`.

---

### Task 1: Add failing variable-binding tests

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Add parser tests for multi-variable comments**

Append near parser/local-var tests:

```python
def test_parse_local_variables_splits_multi_declarator_comment_labels():
    body = """
    float  l_min_f = 0.0,l_max_f = 0.0; /* 最小值，最大值 */
    double l_sum_f = 0.0; /* 数据和值 */
    """

    locals_ = backend.parse_local_variables_from_body(body)
    by_name = {item["name"]: item for item in locals_}

    assert by_name["l_min_f"]["cn_name"] == "最小值"
    assert by_name["l_min_f"].get("name_source") == "inline_comment_split"
    assert by_name["l_max_f"]["cn_name"] == "最大值"
    assert by_name["l_max_f"].get("name_source") == "inline_comment_split"
    assert by_name["l_sum_f"]["cn_name"] in {"数据和值", "累加和", "数据和"}


def test_parse_local_variables_falls_back_to_identifier_semantics():
    body = """
    Uint16 l_ii_u16 = 0U;
    Uint16 l_jj_u16 = 0U;
    Uint16 l_count_u16 = 0U;
    double l_sum_f = 0.0;
    """

    locals_ = backend.parse_local_variables_from_body(body)
    by_name = {item["name"]: item for item in locals_}

    assert by_name["l_ii_u16"]["cn_name"] in {"循环索引ii", "索引ii", "循环索引"}
    assert by_name["l_jj_u16"]["cn_name"] in {"循环索引jj", "索引jj", "循环索引"}
    assert by_name["l_count_u16"]["cn_name"] == "计数"
    assert by_name["l_sum_f"]["cn_name"] in {"累加和", "数据和", "数据和值"}
```

- [ ] **Step 2: Add FdataAverage design local table regression**

Append:

```python
def test_fdataaverage_design_locals_bind_min_and_max_correctly():
    body = """
    Uint16 l_ii_u16 = 0U; /* 循环索引 */
    float  l_min_f = 0.0,l_max_f = 0.0; /* 最小值，最大值 */
    double l_sum_f = 0.0; /* 数据和值 */
    float  l_fData_f = 0.0;  /* 平均值 */
    return l_fData_f;
    """
    func_data = {
        "comment_info": {"func_cn_name": "浮点数求平均", "desc": "浮点数求平均"},
        "func_info": {
            "func_name": "FdataAverage",
            "prototype": "float FdataAverage(float *v_pBuff_f, Uint16 v_len_16)",
            "ret_type": "float",
            "start": 1,
            "line_start": 1,
        },
        "body": body,
        "file_context": {"source_file": "", "symbol_map": {}, "glossary": {}},
    }

    design = build_function_design_impl(func_data, "D/R_SDD01", 1, GenConfig(ai_assist=False))
    locals_by_ident = {item.ident: item for item in (design.local_elements or ())}

    assert locals_by_ident["l_min_f"].name == "最小值"
    assert locals_by_ident["l_min_f"].usage != "最大值"
    assert locals_by_ident["l_max_f"].name == "最大值"
    assert locals_by_ident["l_sum_f"].name in {"数据和值", "累加和", "数据和"}
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "multi_declarator_comment_labels or identifier_semantics or fdataaverage_design_locals_bind" -v
```

Expected: FAIL because current parser only captures `l_min_f` from the multi-declarator line and/or misassigns usage.

- [ ] **Step 4: Commit failing tests**

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: capture local variable binding gaps"
```

---

### Task 2: Implement multi-declarator parsing and positional comment binding

**Files:**
- Modify: `autodoc/parse.py`

- [ ] **Step 1: Add helper functions in `parse.py` near `parse_local_variables_from_body()`**

Add:

```python
def _split_top_level_commas(text: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    for idx, ch in enumerate(str(text or "")):
        if ch in "([{" :
            depth += 1
        elif ch in ")]}" :
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(text[start:idx].strip())
            start = idx + 1
    parts.append(str(text or "")[start:].strip())
    return [part for part in parts if part]
```

Use valid Python syntax; spaces before `:` are allowed but prefer normal style:

```python
        if ch in "([{":
```

Add:

```python
def _split_comment_labels_for_declarators(comment: str, count: int) -> list[str]:
    value = _clean_symbol_comment_text(comment)
    if not value or count <= 1:
        return []
    for sep in ("，", "、", "/", ","):
        if sep not in value:
            continue
        parts = [part.strip() for part in value.split(sep) if part.strip()]
        if len(parts) == count and all(_looks_like_compact_cn_label(part) for part in parts):
            return parts
    return []
```

Add:

```python
def _fallback_local_cn_from_ident(name: str) -> str:
    lower = utils_module._safe_strip(name).lower()
    if not lower:
        return ""
    if re.search(r"(?:^|_)min(?:_|$)", lower):
        return "最小值"
    if re.search(r"(?:^|_)max(?:_|$)", lower):
        return "最大值"
    if "sum" in lower:
        return "累加和"
    if "count" in lower or re.search(r"(?:^|_)cnt(?:_|$)", lower):
        return "计数"
    if re.search(r"(?:^|_)ii(?:_|$)", lower):
        return "循环索引ii"
    if re.search(r"(?:^|_)jj(?:_|$)", lower):
        return "循环索引jj"
    if "index" in lower or re.search(r"(?:^|_)idx(?:_|$)", lower):
        return "循环索引"
    return ""
```

- [ ] **Step 2: Replace single-declarator matching inside `parse_local_variables_from_body()`**

Keep existing simple behavior, but support multi-declarators.

Implementation requirements:

- Add `decl_head_re` that captures the C type prefix in `type` and all declarators before `;` in `decls`.
- In the existing line loop, replace `decl_re.match(stripped_code)` with `decl_head_re.match(stripped_code)`. Preserve the current skip behavior for apparent function-call statements and non-declarations.
- Split `match_head.group("decls")` with `_split_top_level_commas()`.
- Split the inline comment with `_split_comment_labels_for_declarators(cmt, len(declarators))`.
- For each declarator, extract the variable name with the existing pointer/array/init grammar.
- If comment labels are available, bind `comment_labels[idx]` to `cn_name`, set `comment_cn_name` to the same value, set `name_source="inline_comment_split"`, and set `name_confidence=0.95`.
- If no split labels are available, preserve the current `_split_cn_name_and_usage_from_comment()` and `comment_hint` behavior exactly, then try `backend._lookup_symbol_dictionary(v_name)`, then `_fallback_local_cn_from_ident(v_name)`.
- Append one variable dict per declarator with existing keys plus `name_source` and `name_confidence`.

Critical preservation:

- Single declaration with comment `/* 平均值 */` should keep existing comment-hint behavior unless fallback naming is better.
- Do not parse function calls/prototypes as declarations.
- Do not split initializer commas inside braces/parentheses/brackets.

- [ ] **Step 3: Run parser variable tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "multi_declarator_comment_labels or identifier_semantics" -v
```

Expected: PASS.

- [ ] **Step 4: Commit parser implementation**

```bash
git add autodoc/parse.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: bind local variable names from split comments"
```

---

### Task 3: Verify design local table integration

**Files:**
- Modify only if Task 2 missed pipeline integration.

- [ ] **Step 1: Run design local regression**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "fdataaverage_design_locals_bind" -v
```

Expected: PASS.

- [ ] **Step 2: If the design test fails due downstream repair overwriting names, fix the narrow repair path**

Likely locations:

- `autodoc/pipeline.py` local variable context/repair after `prepare_design_context()`.
- `autodoc/semantic_registry.py` only if semantic labels override higher-confidence comment names.

Fix rule:

- If local var has `name_source == "inline_comment_split"` and `name_confidence >= 0.9`, downstream repairs must not overwrite `cn_name`.

- [ ] **Step 3: Run combined Stage 3 tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "multi_declarator_comment_labels or identifier_semantics or fdataaverage_design_locals_bind" -v
```

Expected: PASS.

- [ ] **Step 4: Commit integration fix if any files changed**

If Task 2 commit already makes design test pass and no files changed, do not create an empty commit. Otherwise:

```bash
git add autodoc/parse.py autodoc/pipeline.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: preserve high-confidence local variable names"
```

---

### Task 4: Verify PROJECT FdataAverage sample output

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused Stage 3 tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "multi_declarator_comment_labels or identifier_semantics or fdataaverage_design_locals_bind or c_expr_renders or build_design_text_sections_uses" -v
```

Expected: PASS.

- [ ] **Step 2: Generate FdataAverage docx**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/DataObtain/DataObtainAI.c \
  --function FdataAverage \
  -o /tmp/autodoc_eval/FdataAverage.stage3-variable-binding.docx \
  --codegraph off --verbose
```

Expected: generation succeeds.

- [ ] **Step 3: Inspect generated local data table**

Use the harness Read tool on:

```text
/tmp/autodoc_eval/FdataAverage.stage3-variable-binding.docx
```

Expected:

- `l_min_f` row name is `最小值`.
- `l_min_f` row usage is not `最大值`.
- `l_max_f` appears and row name is `最大值`.
- `l_sum_f` row name is `数据和值`, `累加和`, or `数据和`.
- b) 功能说明 still contains `浮点数求平均`.

- [ ] **Step 4: Check worktree state**

Run:

```bash
git status --short --branch
```

Expected: clean.

---

## Self-Review Notes

Spec coverage:

- Covers Stage 3 multi-declarator parsing, split inline comments, identifier fallback, metadata, and FdataAverage acceptance.
- Does not implement Stage 4 empty-else/logic cleanup or Stage 5 domain rules.

No placeholders remain. Tasks are intentionally narrow and behavior-tested.
