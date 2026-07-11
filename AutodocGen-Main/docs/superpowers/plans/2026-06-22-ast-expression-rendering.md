# AST Expression Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small structured C expression rendering layer so AutoDocGen stops mistranslating byte masks such as `x & 0xFFU` as logical `且 0xFF` and improves PROJECT `Comm422FrameCheck` logic text.

**Architecture:** Add a focused `autodoc.c_expr` module with a lightweight expression IR and deterministic renderer. Wire it into the narrow logic paths that currently emit bad text: `_logic_cn_expr()`, structured condition rendering, raw assignment rendering, and fallback condition rendering. Keep scope small: do not replace full logic generation or implement full C type checking.

**Tech Stack:** Python 3, pytest, existing AutoDocGen modules (`autodoc.logic`, `autodoc.utils`). Optional Tree-sitter may be used when available, but this plan requires a deterministic fallback parser so tests pass without external parser availability.

---

## File Structure

- Create: `autodoc/c_expr.py`
  - Defines expression IR dataclasses and `parse_c_expression(expr_text)` / `render_expr_cn(expr, name_map, rules=None)`.
  - Handles only Stage 2 expression shapes: identifiers, literals, calls, subscripts, fields, unary ops, binary ops, parentheses.
  - Owns byte-mask and checksum rendering rules.
  - Must not import `autodoc.backend` to avoid circular imports.
- Modify: `autodoc/logic.py`
  - Use `c_expr` rendering in `_logic_cn_expr()` before string-based identifier replacement for supported expressions.
  - Use `c_expr` rendering in `_render_structured_condition_cn()` via its existing `_rule_cn()` path.
  - Use `c_expr` rendering in `fallback_logic_line()` for `if`/`while` conditions to prevent `&` becoming `且`.
  - Use `c_expr` rendering in `_render_raw_assignment_template()` / `_render_binary_assignment_text()` only for RHS expressions where it improves byte-mask/checksum text.
- Modify: `tests/test_pipeline_quality_repairs.py`
  - Add focused unit tests for expression rendering and logic output.
  - Add PROJECT-shaped `Comm422FrameCheck` regression that asserts no `且 0xFF` and contains low-eight-bit/checksum semantics.

---

### Task 1: Add failing expression-rendering tests

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Add imports for new expression API**

Add near existing imports:

```python
from autodoc.c_expr import parse_c_expression, render_expr_cn
```

- [ ] **Step 2: Add byte-mask expression tests**

Append near existing logic-expression tests:

```python
def test_c_expr_renders_low_byte_mask():
    expr = parse_c_expression("s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] & 0xFFU")

    rendered = render_expr_cn(
        expr,
        {
            "s_rs422CommBuff_t": "接收数据缓冲区",
            "v_commID_u16": "RS422通道ID",
            "commBuff_u16": "接收数据",
            "l_ii_u16": "候选帧起始索引",
        },
    )

    assert rendered.text
    assert "低8位" in rendered.text or "低 8 位" in rendered.text
    assert "候选帧起始索引" in rendered.text
    assert "且 0xFF" not in rendered.text


def test_c_expr_renders_twos_complement_checksum():
    expr = parse_c_expression("(((~l_sum_u16) + 1U) & 0xFFU)")

    rendered = render_expr_cn(expr, {"l_sum_u16": "数据和"})

    assert "补码校验和" in rendered.text
    assert "低8位" in rendered.text or "低 8 位" in rendered.text
    assert "&" not in rendered.text
```

- [ ] **Step 3: Add logic condition regression for byte masks**

Append:

```python
def test_structured_condition_renders_byte_mask_without_logical_and_text():
    cond, _ = _render_structured_condition_cn(
        "RS422_COMM_FRAME_HEAD_1 != (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] & 0xFFU)",
        (),
        {
            "RS422_COMM_FRAME_HEAD_1": "RS422第一帧头",
            "s_rs422CommBuff_t": "接收数据缓冲区",
            "v_commID_u16": "RS422通道ID",
            "commBuff_u16": "接收数据",
            "l_ii_u16": "候选帧起始索引",
        },
        GenConfig(ai_assist=False),
    )

    assert "RS422第一帧头" in cond
    assert "低8位" in cond or "低 8 位" in cond
    assert "候选帧起始索引" in cond
    assert "且 0xFF" not in cond
```

- [ ] **Step 4: Add generated logic regression for Comm422FrameCheck fragment**

Append:

```python
def test_comm422_frame_check_logic_uses_low_byte_and_checksum_language():
    body = """
    Uint16 l_ii_u16 = 0U;
    Uint16 l_jj_u16 = 0U;
    Uint16 l_sum_u16 = 0U;
    Uint16 l_rData_u16 = RS422_COMM_FRAM_NOT_EXIST;
    if (v_commID_u16 < COMM422_ID_NUM)
    {
        for (l_ii_u16 = 0U; l_ii_u16 < l_count_u16; l_ii_u16++)
        {
            if (RS422_COMM_FRAME_HEAD_1 != (s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16] & 0xFFU))
            {
                l_headErrCnt_u16 = l_headErrCnt_u16 + 1U;
            }
            l_sum_u16 = (((~l_sum_u16) + 1U) & 0xFFU);
        }
    }
    return l_rData_u16;
    """
    logic_text, _ = logic_utils.generate_logic_from_body(
        body,
        [],
        GenConfig(ai_assist=False),
        name_map={
            "v_commID_u16": "RS422通道ID",
            "COMM422_ID_NUM": "422通信数量",
            "RS422_COMM_FRAME_HEAD_1": "RS422第一帧头",
            "s_rs422CommBuff_t": "接收数据缓冲区",
            "commBuff_u16": "接收数据",
            "l_ii_u16": "候选帧起始索引",
            "l_count_u16": "候选帧数量",
            "l_sum_u16": "数据和",
            "l_rData_u16": "检测结果",
        },
    )

    assert "且 0xFF" not in logic_text
    assert "低8位" in logic_text or "低 8 位" in logic_text
    assert "补码校验和" in logic_text
```

- [ ] **Step 5: Run tests to verify they fail for missing module / bad rendering**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "c_expr_renders or structured_condition_renders_byte_mask or comm422_frame_check_logic_uses" -v
```

Expected: FAIL because `autodoc.c_expr` does not exist, or because current logic emits `且 0xFF` / raw `&`.

- [ ] **Step 6: Commit failing tests**

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: capture byte-mask expression rendering gaps"
```

---

### Task 2: Implement focused C expression IR and renderer

**Files:**
- Create: `autodoc/c_expr.py`

- [ ] **Step 1: Create expression module skeleton**

Create `autodoc/c_expr.py` with:

```python
"""Small C expression parser/renderer for design-document logic text."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Sequence


@dataclass(frozen=True)
class ExprIR:
    kind: str
    text: str = ""
    op: str = ""
    name: str = ""
    value: str = ""
    children: tuple["ExprIR", ...] = ()


@dataclass(frozen=True)
class RenderedExpr:
    text: str
    confidence: float = 1.0
    source: str = "rule"


def parse_c_expression(expr_text: str) -> Optional[ExprIR]:
    ...


def render_expr_cn(expr: Optional[ExprIR], name_map: Optional[dict[str, str]] = None, rules: object = None) -> RenderedExpr:
    ...
```

- [ ] **Step 2: Implement parser helpers**

Implement deterministic parser helpers in `c_expr.py`:

```python
def _safe(text: object) -> str:
    return str(text or "").strip()


def _strip_outer_parens(text: str) -> str:
    value = _safe(text)
    for _ in range(8):
        if not (value.startswith("(") and value.endswith(")")):
            break
        depth = 0
        balanced_outer = True
        in_squote = False
        in_dquote = False
        escape = False
        for idx, ch in enumerate(value):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_squote:
                if ch == "'":
                    in_squote = False
                continue
            if in_dquote:
                if ch == '"':
                    in_dquote = False
                continue
            if ch == "'":
                in_squote = True
                continue
            if ch == '"':
                in_dquote = True
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(value) - 1:
                    balanced_outer = False
                    break
        if not balanced_outer:
            break
        value = value[1:-1].strip()
    return value


def _split_top_level_binary(expr: str, ops: Sequence[str]) -> Optional[tuple[str, str, str]]:
    value = _safe(expr)
    depth = 0
    in_squote = False
    in_dquote = False
    escape = False
    ordered_ops = sorted(ops, key=len, reverse=True)
    idx = 0
    while idx < len(value):
        ch = value[idx]
        if escape:
            escape = False
            idx += 1
            continue
        if ch == "\\":
            escape = True
            idx += 1
            continue
        if in_squote:
            if ch == "'":
                in_squote = False
            idx += 1
            continue
        if in_dquote:
            if ch == '"':
                in_dquote = False
            idx += 1
            continue
        if ch == "'":
            in_squote = True
            idx += 1
            continue
        if ch == '"':
            in_dquote = True
            idx += 1
            continue
        if ch in "([{" :
            depth += 1
            idx += 1
            continue
        if ch in ")]}" :
            depth = max(0, depth - 1)
            idx += 1
            continue
        if depth == 0:
            for op in ordered_ops:
                if value.startswith(op, idx):
                    lhs = _strip_outer_parens(value[:idx])
                    rhs = _strip_outer_parens(value[idx + len(op):])
                    if lhs and rhs:
                        return lhs, op, rhs
        idx += 1
    return None
```


- [ ] **Step 3: Implement parser and rendering rules**

Implement `parse_c_expression()` so it recognizes, in order:

```python
value = _strip_outer_parens(expr_text)
if top-level `&` split: ExprIR(kind="binary", op="&", children=(parse(left), parse(right)))
if top-level `+` split: ExprIR(kind="binary", op="+", children=(parse(left), parse(right)))
if unary `~`: ExprIR(kind="unary", op="~", children=(parse(rest),))
if call `Name(args...)`: ExprIR(kind="call", name=name, children=args)
if field/subscript chain: keep as ExprIR(kind="raw_ref", text=value)
if identifier: ExprIR(kind="identifier", name=value)
if literal: ExprIR(kind="literal", value=value)
else raw ExprIR(kind="raw", text=value)
```

Implement `render_expr_cn()` rules:

```python
_BYTE_MASK_RE = re.compile(r"^0[xX]0*FF(?:[uUlL]*)$")
_ONE_RE = re.compile(r"^1(?:[uUlL]*)$")

# binary &: right byte mask -> "<left>的低8位"
# binary &: left checksum pattern ((~sum)+1) and right byte mask -> "<sum>的低8位补码校验和"
# binary +: "<left>与<right>之和"
# unary ~: "<child>取反"
# raw_ref: render member/subscript chain preserving mapped base/member/index
# identifier: map via name_map else identifier
# literal: normalize suffix U/L away for numeric literals
# call: map function name via name_map else function name + "结果"
```

For raw reference rendering, implement enough to pass tests:

- Replace `->` with `.`.
- Split field/member segments by top-level `.`.
- Preserve subscript indexes by rendering each index expression.
- If base/member/index have entries in `name_map`, use mapped text.
- For `s_rs422CommBuff_t[v_commID_u16].commBuff_u16[l_ii_u16]`, output should include mapped base `接收数据缓冲区`, mapped channel/index `RS422通道ID`, mapped member `接收数据`, mapped candidate index `候选帧起始索引`.

- [ ] **Step 4: Run expression tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "c_expr_renders" -v
```

Expected: PASS for byte-mask/checksum expression tests.

- [ ] **Step 5: Commit expression module**

```bash
git add autodoc/c_expr.py tests/test_pipeline_quality_repairs.py
git commit -m "feat: add focused C expression renderer"
```

---

### Task 3: Wire expression renderer into logic condition/expression paths

**Files:**
- Modify: `autodoc/logic.py`
- Test: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Import expression renderer lazily or safely**

At top-level or inside helper functions, avoid circular imports. Preferred in `logic.py` near other imports:

```python
from . import c_expr as c_expr_utils
```

If top-level import causes circular issues, import inside helper:

```python
def _render_c_expr_cn(expr, name_map=None):
    try:
        from . import c_expr as c_expr_utils
    except Exception:
        return ""
    rendered = c_expr_utils.render_expr_cn(c_expr_utils.parse_c_expression(expr), name_map or {})
    return rendered.text
```

- [ ] **Step 2: Add helper in `logic.py`**

Add near `_logic_cn_expr()`:

```python
def _render_supported_c_expr_cn(expr: str, name_map: Optional[dict[str, str]] = None) -> str:
    try:
        from . import c_expr as c_expr_utils
        parsed = c_expr_utils.parse_c_expression(expr)
        rendered = c_expr_utils.render_expr_cn(parsed, name_map or {})
        text = utils._safe_strip(rendered.text)
        if not text:
            return ""
        if text == utils._safe_strip(expr):
            return ""
        if "低8位" in text or "低 8 位" in text or "补码校验和" in text:
            return text
        return ""
    except Exception:
        return ""
```

This intentionally only returns Stage-2 high-value renderings so broad expression text does not churn.

- [ ] **Step 3: Wire `_logic_cn_expr()`**

In `_logic_cn_expr()` after cast stripping and before call/identifier fallback, add:

```python
    rendered_c_expr = _render_supported_c_expr_cn(value, name_map)
    if rendered_c_expr:
        return rendered_c_expr
```

- [ ] **Step 4: Wire `_render_structured_condition_cn()`**

Inside `_rule_cn(expr)`, before `call_label = ...`, add:

```python
        rendered_c_expr = _render_supported_c_expr_cn(expr_text, name_map)
        if rendered_c_expr:
            return rendered_c_expr
```

This makes comparisons render `(... & 0xFFU)` as low-byte text.

- [ ] **Step 5: Wire `fallback_logic_line()` condition rendering**

In the `if` and `while` branches, before replacing `&&`/`||` and single `&`, try structured condition rendering:

```python
        structured, _ = _render_structured_condition_cn(cond, (), name_map, None, backend_module=backend)
        if structured:
            return f"{'ELSE IF' if line.lstrip().startswith('else if') else 'IF'} {structured} 时"
```

For `while`, similarly:

```python
        structured, _ = _render_structured_condition_cn(cond_cn, (), name_map, None, backend_module=backend)
        if structured:
            return f"WHILE {structured} 时"
```

- [ ] **Step 6: Run logic tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "structured_condition_renders_byte_mask or comm422_frame_check_logic_uses" -v
```

Expected: PASS.

- [ ] **Step 7: Commit logic wiring**

```bash
git add autodoc/logic.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: render byte-mask expressions in logic text"
```

---

### Task 4: Verify PROJECT sample output for Stage 2

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused Stage 2 tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "c_expr_renders or structured_condition_renders_byte_mask or comm422_frame_check_logic_uses or build_design_text_sections_uses" -v
```

Expected: PASS.

- [ ] **Step 2: Generate PROJECT Comm422FrameCheck docx**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Communication/Comm422.c \
  --function Comm422FrameCheck \
  -o /tmp/autodoc_eval/Comm422FrameCheck.stage2-expression.docx \
  --codegraph off --verbose
```

Expected: command exits 0 and prints generated path.

- [ ] **Step 3: Inspect generated doc text**

Use the harness Read tool on:

```text
/tmp/autodoc_eval/Comm422FrameCheck.stage2-expression.docx
```

Expected:

- b) 功能说明 still contains `检测对应通道接收缓冲区是否存在有效报文`.
- e) 逻辑/流程图 does not contain `且 0xFF`.
- Logic contains `低8位` or `低 8 位`.
- Logic contains `补码校验和`.

- [ ] **Step 4: Generate PROJECT FdataAverage docx as non-regression**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/DataObtain/DataObtainAI.c \
  --function FdataAverage \
  -o /tmp/autodoc_eval/FdataAverage.stage2-expression.docx \
  --codegraph off --verbose
```

Expected: command exits 0 and b) 功能说明 still contains `浮点数求平均`.

- [ ] **Step 5: Do not commit if no files changed**

Check:

```bash
git status --short --branch
```

Expected: clean branch. If verification-only, no commit.

---

## Self-Review Notes

Spec coverage for this plan:

- Covers Stage 2 expression parser/rendering module.
- Covers byte-mask rendering, checksum rendering, index preservation, condition integration, and PROJECT `Comm422FrameCheck` sample verification.
- Does not implement Stage 3 variable binding, Stage 4 logic IR/noise reduction, or Stage 5 broader domain rules. Those remain separate plans.

No implementation placeholders remain. Known broad rewrites are explicitly avoided: `_render_supported_c_expr_cn()` only returns high-value Stage 2 renderings to avoid changing unrelated expression prose.
