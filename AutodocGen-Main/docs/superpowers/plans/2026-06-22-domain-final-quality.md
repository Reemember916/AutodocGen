# Domain Final Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the source-understanding pipeline rollout by covering Stage 5 domain/final-quality acceptance: deterministic domain rules remain evidence-based, PROJECT sample docs generate without regressions, and low-confidence/boilerplate output is made visible or repaired.

**Architecture:** Keep Stage 5 narrow. Stage 2 already introduced deterministic byte-mask/checksum rules. This plan adds final PROJECT quality regressions and fixes only observed evidence-backed gaps:

- Preserve `ii`/`jj` local labels from comments/fallbacks so loop indexes do not collapse in tables and logic.
- Suppress repeated top-level setup/default lines when a later line is the semantically meaningful loop-scoped reset.
- Run all three target sample functions as final verification.

---

## File Structure

- Modify: `tests/test_pipeline_quality_repairs.py`
  - Add final PROJECT-oriented regressions.
- Modify likely: `autodoc/logic.py`, `autodoc/parse.py`, or `autodoc/pipeline.py`
  - Only if regressions fail.

---

### Task 1: Add final PROJECT quality regressions

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] Add a parser/design regression that comments `/* 循环索引ii */` and `/* 循环索引jj */` keep distinguishable local names through `build_function_design_impl()` or the nearest design-text path.

Expected:

- `l_ii_u16` name contains `ii` or otherwise differs from `l_jj_u16`.
- `l_jj_u16` name contains `jj` or otherwise differs from `l_ii_u16`.

- [ ] Add a generated logic regression for Comm422-style setup/reset:

Input body should include:

```c
Uint16 l_headErrCnt_u16 = 0U;
for (l_ii_u16 = 0U; l_ii_u16 < l_count_u16; l_ii_u16++) {
    l_headErrCnt_u16 = 0U;
    if (l_headErrCnt_u16 == 0U) { l_rData_u16 = l_ii_u16; }
}
```

Expected:

- At most one top-level `帧头错误计数` setup/default line before the `FOR`.
- A `帧头错误计数` reset remains after the `FOR` line.

- [ ] Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "loop_index_labels or comm422_setup_reset" -v
```

Expected: current code may fail one or both; commit red tests if failing.

Commit:

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: capture final PROJECT quality gaps"
```

---

### Task 2: Fix final quality regressions narrowly

**Files:**
- Modify only the module needed by failing tests.

Potential fixes:

- If `循环索引ii/jj` are parsed but normalized away later, update output normalization/local-row construction to preserve high-confidence labels that include suffix evidence.
- If repeated setup lines come from declaration boilerplate, update cleanup to collapse repeated top-level default setup lines even when separated by other boilerplate declarations, but never remove indented/loop-scoped resets.

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "loop_index_labels or comm422_setup_reset" -v
```

Expected: PASS.

Commit:

```bash
git add autodoc tests/test_pipeline_quality_repairs.py
git commit -m "fix: preserve final PROJECT logic quality"
```

---

### Task 3: Final verification over all target samples

- [ ] Run focused regression suite:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "comment_normalizer or c_expr_renders or structured_condition_renders_byte_mask or comm422_frame_check_logic_uses or fdataaverage_design_locals_bind or empty_else_branch or no_bare_empty_else or duplicate_setup or loop_index_labels or comm422_setup_reset" -v
```

- [ ] Generate docs:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc -d /Users/ree/Downloads/PROJECT-2007-0613 -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Main.c --function TimeCountInit -o /tmp/autodoc_eval/TimeCountInit.final-source-understanding.docx --codegraph off --verbose && \
python3 AutoDocGen_V1.4.py doc -d /Users/ree/Downloads/PROJECT-2007-0613 -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/DataObtain/DataObtainAI.c --function FdataAverage -o /tmp/autodoc_eval/FdataAverage.final-source-understanding.docx --codegraph off --verbose && \
python3 AutoDocGen_V1.4.py doc -d /Users/ree/Downloads/PROJECT-2007-0613 -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Communication/Comm422.c --function Comm422FrameCheck -o /tmp/autodoc_eval/Comm422FrameCheck.final-source-understanding.docx --codegraph off --verbose
```

- [ ] Inspect generated docs. Expected:

- All three docs generated.
- `FdataAverage`: function description contains `浮点数求平均`; `l_min_f` is `最小值`, not maximum usage; no bare `ELSE` line.
- `Comm422FrameCheck`: function description contains valid-frame detection text; no `且 0xFF`; contains `低8位` and `补码校验和`; loop reset preserved.
- `TimeCountInit`: generated output is non-empty and no obvious regression such as `功能说明: 无。`.
- Worktree clean.

---

## Self-Review Notes

Stage 5 is not a broad domain-rule expansion. It only adds evidence-backed final-quality fixes discovered in PROJECT sample verification, while preserving existing deterministic bit-mask/checksum rules.
