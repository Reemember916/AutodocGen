# Logic Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce line-by-line noise in generated logic so PROJECT samples read like design intent: remove empty `ELSE` branches, suppress duplicate/boilerplate initialization text, and preserve meaningful loop-scoped resets.

**Architecture:** Add a narrow post-generation logic cleanup pass in `autodoc.logic` after existing line generation/validation. Do not rewrite the whole generator into a new IR in this stage; instead introduce small IR-like cleanup helpers operating on rendered logic lines with source-order evidence from the existing generator. This satisfies Stage 4 acceptance while keeping risk low.

**Tech Stack:** Python 3, pytest, existing `autodoc.logic.generate_logic_from_body()`, existing doc generation CLI.

---

## File Structure

- Modify: `autodoc/logic.py`
  - Add helper to remove empty `ELSE` branches while preserving the enclosing `END IF`.
  - Add helper to collapse repeated declaration/default initialization lines where the duplicate is boilerplate.
  - Keep loop-scoped resets such as `l_headErrCnt_u16 = 0U` inside the candidate loop.
- Modify: `tests/test_pipeline_quality_repairs.py`
  - Add focused tests for empty else removal, duplicate initialization collapse, and loop reset preservation.
  - Add regression over `FdataAverage`/`Comm422FrameCheck` logic fragments.

---

### Task 1: Add failing Stage 4 logic-cleanup tests

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Add empty else branch regression**

Append:

```python
def test_logic_cleanup_removes_empty_else_branch_from_no_deal_comment():
    body = """
    if (v_len_16 > 3U)
    {
        l_fData_f = v_pBuff_f[0];
    }
    else
    {
        /* no deal to do */
    }
    return l_fData_f;
    """

    logic_text, _ = logic_utils.generate_logic_from_body(
        body,
        [],
        GenConfig(ai_assist=False),
        name_map={"v_len_16": "长度", "l_fData_f": "平均值", "v_pBuff_f": "缓冲"},
    )

    lines = [line.strip() for line in logic_text.splitlines() if line.strip()]
    assert "ELSE" not in lines
    assert "END IF" in lines
```

- [ ] **Step 2: Add FdataAverage no bare ELSE regression**

Append:

```python
def test_fdataaverage_logic_contains_no_bare_empty_else_branch():
    body = """
    if (v_pBuff_f != NULL)
    {
        if (v_len_16 > 3U)
        {
            l_fData_f = v_pBuff_f[0];
        }
        else if (v_len_16 > 0U)
        {
            l_fData_f = v_pBuff_f[0];
        }
        else
        {
            /* no deal to do */
        }
    }
    return l_fData_f;
    """

    logic_text, _ = logic_utils.generate_logic_from_body(
        body,
        [],
        GenConfig(ai_assist=False),
        name_map={"v_pBuff_f": "缓冲", "v_len_16": "长度", "l_fData_f": "平均值"},
    )

    lines = [line.strip() for line in logic_text.splitlines() if line.strip()]
    assert "ELSE" not in lines
    assert any(line.startswith("ELSE IF") for line in lines)
```

- [ ] **Step 3: Add duplicate initialization collapse and loop reset preservation regression**

Append:

```python
def test_logic_cleanup_collapses_duplicate_setup_but_preserves_loop_reset():
    body = """
    Uint16 l_headErrCnt_u16 = 0U;
    l_headErrCnt_u16 = 0U;
    for (l_ii_u16 = 0U; l_ii_u16 < l_count_u16; l_ii_u16++)
    {
        l_headErrCnt_u16 = 0U;
        if (l_headErrCnt_u16 == 0U)
        {
            l_rData_u16 = 1U;
        }
    }
    return l_rData_u16;
    """

    logic_text, _ = logic_utils.generate_logic_from_body(
        body,
        [],
        GenConfig(ai_assist=False),
        name_map={
            "l_headErrCnt_u16": "帧头错误计数",
            "l_ii_u16": "候选帧起始索引",
            "l_count_u16": "候选帧数量",
            "l_rData_u16": "检测结果",
        },
    )

    lines = [line.strip() for line in logic_text.splitlines() if line.strip()]
    reset_lines = [line for line in lines if "帧头错误计数" in line and ("清零" in line or "设置" in line or "初始化" in line)]
    assert len(reset_lines) <= 2
    for_index = next(i for i, line in enumerate(lines) if line.startswith("FOR"))
    assert any("帧头错误计数" in line and ("清零" in line or "设置" in line or "初始化" in line) for line in lines[for_index + 1:])
```

- [ ] **Step 4: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "empty_else_branch or no_bare_empty_else or duplicate_setup" -v
```

Expected: FAIL because current logic leaves bare `ELSE` and repeats setup lines.

- [ ] **Step 5: Commit failing tests**

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: capture logic cleanup gaps"
```

---

### Task 2: Implement focused logic cleanup pass

**Files:**
- Modify: `autodoc/logic.py`

- [ ] **Step 1: Add helper to remove empty else branches**

Add near `_polish_logic_lines()` / validation helpers:

```python
def _remove_empty_else_branches(lines: Sequence[str]) -> list[str]:
    result: list[str] = []
    items = list(lines or [])
    idx = 0
    while idx < len(items):
        current = str(items[idx] or "")
        stripped = current.strip()
        if stripped == "ELSE":
            nxt = idx + 1
            while nxt < len(items) and not str(items[nxt] or "").strip():
                nxt += 1
            if nxt < len(items) and str(items[nxt] or "").strip() == "END IF":
                idx += 1
                continue
        result.append(current)
        idx += 1
    return result
```

This removes only the empty `ELSE` marker. It preserves the existing `END IF`, so `IF`/`ELSE IF` pairing stays valid.

- [ ] **Step 2: Add duplicate setup collapse helper**

Add:

```python
def _collapse_duplicate_setup_lines(lines: Sequence[str]) -> list[str]:
    result: list[str] = []
    last_global_setup: dict[str, int] = {}
    for raw in lines or []:
        line = str(raw or "")
        stripped = line.strip()
        is_setup = bool(re.match(r"^(?:设置|初始化|清零).+", stripped))
        target = ""
        if is_setup:
            target = re.sub(r"^(?:设置|初始化|清零)\s*", "", stripped)
            target = re.split(r"\s*[=＝]|为空|；|;", target, maxsplit=1)[0].strip()
        indent = len(line) - len(line.lstrip(" "))
        if is_setup and indent == 0 and target:
            previous = last_global_setup.get(target)
            if previous is not None and previous == len(result) - 1:
                result[-1] = line
                continue
            last_global_setup[target] = len(result)
        result.append(line)
    return result
```

Keep this conservative: collapse only adjacent top-level setup duplicates for the same target. Do not collapse indented loop-scoped resets.

- [ ] **Step 3: Wire cleanup pass into generated logic**

Find the final path in `generate_logic_from_body()` where steps are converted/polished/validated. After `_validate_control_blocks()` and before returning final text, apply:

```python
lines = _remove_empty_else_branches(lines)
lines = _collapse_duplicate_setup_lines(lines)
```

If the function uses a text string at that point, split into lines, apply, then join.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "empty_else_branch or no_bare_empty_else or duplicate_setup" -v
```

Expected: PASS.

- [ ] **Step 5: Commit implementation**

```bash
git add autodoc/logic.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: remove empty else and duplicate setup noise"
```

---

### Task 3: Verify PROJECT sample behavior

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused Stage 4 tests plus prior regressions**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "empty_else_branch or no_bare_empty_else or duplicate_setup or fdataaverage_design_locals_bind or comm422_frame_check_logic_uses" -v
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
  -o /tmp/autodoc_eval/FdataAverage.stage4-logic-cleanup.docx \
  --codegraph off --verbose
```

Expected:

- b) 功能说明 still contains `浮点数求平均`.
- d) local table keeps `l_min_f` as `最小值`, `l_max_f` as `最大值`.
- e) logic contains no bare line exactly `ELSE`.

- [ ] **Step 3: Generate Comm422FrameCheck docx**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Communication/Comm422.c \
  --function Comm422FrameCheck \
  -o /tmp/autodoc_eval/Comm422FrameCheck.stage4-logic-cleanup.docx \
  --codegraph off --verbose
```

Expected:

- b) 功能说明 contains `检测对应通道接收缓冲区是否存在有效报文`.
- logic still contains `低8位` and `补码校验和`.
- logic does not contain `且 0xFF`.
- loop-scoped reset of `帧头错误计数` remains inside/after the `FOR` block.

- [ ] **Step 4: Check worktree state**

Run:

```bash
git status --short --branch
```

Expected: clean.

---

## Self-Review Notes

Spec coverage:

- Covers Stage 4 acceptance cases: empty else removal, duplicate setup suppression, loop-scoped reset preservation.
- Does not create a full new logic IR class hierarchy. This is intentional: current generator already has block/line evidence, and this stage needs a conservative quality pass rather than a risky rewrite.
- Stage 5 domain-rule module remains separate.
