# Comment Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the highest-visibility AutoDocGen production defect where function descriptions become `无。` even though nearby C comments contain usable descriptions.

**Architecture:** Add a focused `autodoc.comment_normalizer` module that parses block/line comment text into normalized fields with deterministic rules. Wire `autodoc.parse.parse_single_comment_block()` through the normalizer while preserving its existing dict contract, then add PROJECT-shaped regression tests for comment extraction and generated design text.

**Tech Stack:** Python 3, pytest, existing AutoDocGen modules (`autodoc.parse`, `autodoc.pipeline`, `autodoc.config`).

---

## File Structure

- Create: `autodoc/comment_normalizer.py`
  - Owns comment markup stripping, section-label detection, multi-line section collection, separator-block filtering, and normalized output dataclasses.
  - Must not import `autodoc.backend` to avoid circular imports.
- Modify: `autodoc/parse.py`
  - `parse_single_comment_block()` delegates to `comment_normalizer.normalize_comment_block()` and returns the same keys as today.
  - `extract_effective_comment_desc()` may use the normalized result for fallback behavior if needed.
- Modify: `tests/test_pipeline_quality_repairs.py`
  - Add focused unit tests for PROJECT-style comments.
  - Add a lightweight generated-text regression for `build_design_text_sections()` or `build_function_design_impl()` using static `func_data`.

---

### Task 1: Add failing comment normalizer tests

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Add imports for the new module contract**

Add this import near the existing parse imports:

```python
from autodoc.comment_normalizer import normalize_comment_block
```

- [ ] **Step 2: Add PROJECT comment extraction tests**

Append these tests near the existing parser/comment tests in `tests/test_pipeline_quality_repairs.py`:

```python
def test_comment_normalizer_extracts_project_same_line_fullwidth_desc():
    raw = """
    /**
     * 【函数名】:FdataAverage
     *
     * 【功能描述】浮点数求平均
     * 	 1、对一组浮点数，去除最大、最小值后，求平均值，当浮点数个数为零时，返回零；
     *   2、当浮点数个数大于零，小于三时，返回数组第一个数。
     *
     * 【输入参数说明】v_pBuff_f ---- 浮点数数组指针
     * 			   v_len_16  ---- 数据长度
     * 【输出参数说明】NONE
     * 【其他说明】       NONE
     * 【返回】:	数组中浮点数的平均值
     */
    """

    normalized = normalize_comment_block(raw)

    assert normalized.func_name == "FdataAverage"
    assert "浮点数求平均" in normalized.desc
    assert "去除最大、最小值" in normalized.desc
    assert "小于三时，返回数组第一个数" in normalized.desc
    assert "v_pBuff_f" in normalized.input_desc
    assert "v_len_16" in normalized.input_desc
    assert normalized.output_desc == "NONE"
    assert normalized.return_desc == "数组中浮点数的平均值"


def test_comment_normalizer_extracts_project_bracket_desc_following_line():
    raw = """
    /**
     *    [函数名]	 Comm422FrameCheck
     *
     *    [功能描述]
     *    			  检测对应通道接收缓冲区是否存在有效报文。
     *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
     *              	SCI_A_ID ---- SCIA接口
     *              	SCI_B_ID ---- SCIB接口
     *              	SCI_C_ID ---- SCIC接口
     *	  [输出参数说明] NONE
     *    [其他说明]	    NONE
     *    [返回]		 返回有效报文首数据在缓冲区中索引，无有效报文时，返回:RS422_COMM_FRAM_NOT_EXIST
     */
    """

    normalized = normalize_comment_block(raw)

    assert normalized.func_name == "Comm422FrameCheck"
    assert normalized.desc == "检测对应通道接收缓冲区是否存在有效报文。"
    assert "v_commID_u16" in normalized.input_desc
    assert "SCI_A_ID" in normalized.input_desc
    assert normalized.output_desc == "NONE"
    assert "有效报文首数据" in normalized.return_desc
    assert "RS422_COMM_FRAM_NOT_EXIST" in normalized.return_desc


def test_parse_single_comment_block_preserves_existing_dict_contract_with_normalized_desc():
    raw = """
    /**
     * 【函数名】:TimeCountInit
     *
     * 【功能描述】时间计数初始化
     * 【输入参数说明】NONE
     * 【输出参数说明】NONE
     * 【其他说明】       同步时间初始化为定时器1微秒值加上任务主周期时间，用于实现进入while周期后立刻执行一次同步！！！
     * 【返回】               NONE
     */
    """

    parsed = parse_single_comment_block(raw)

    assert set(parsed) == {
        "func_name",
        "func_cn_name",
        "desc",
        "input_desc",
        "output_desc",
        "other_desc",
        "return_desc",
    }
    assert parsed["func_name"] == "TimeCountInit"
    assert parsed["desc"] == "时间计数初始化"
    assert parsed["input_desc"] == "NONE"
    assert parsed["output_desc"] == "NONE"
    assert "同步时间初始化" in parsed["other_desc"]
    assert parsed["return_desc"] == "NONE"
```

- [ ] **Step 3: Run the new tests and verify failure**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "comment_normalizer_extracts_project or parse_single_comment_block_preserves_existing_dict_contract" -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autodoc.comment_normalizer'` or equivalent import error.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: capture PROJECT comment normalization gaps"
```

---

### Task 2: Implement the comment normalizer module

**Files:**
- Create: `autodoc/comment_normalizer.py`

- [ ] **Step 1: Create the module with dataclasses and public API**

Create `autodoc/comment_normalizer.py` with this content:

```python
"""Normalize C function comment blocks into stable AutoDoc fields."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class CommentEvidence:
    field: str
    line_index: int
    text: str


@dataclass(frozen=True)
class NormalizedComment:
    func_name: str = ""
    func_cn_name: str = ""
    desc: str = ""
    input_desc: str = ""
    output_desc: str = ""
    other_desc: str = ""
    return_desc: str = ""
    evidence: tuple[CommentEvidence, ...] = ()

    def to_parse_dict(self) -> dict[str, str]:
        return {
            "func_name": self.func_name,
            "func_cn_name": self.func_cn_name,
            "desc": self.desc,
            "input_desc": self.input_desc,
            "output_desc": self.output_desc,
            "other_desc": self.other_desc,
            "return_desc": self.return_desc,
        }


_LABEL_TO_FIELD = {
    "函数名": "func_name",
    "函数名称": "func_name",
    "函数中文名": "func_cn_name",
    "功能描述": "desc",
    "功能说明": "desc",
    "功能": "desc",
    "说明": "desc",
    "输入参数说明": "input_desc",
    "输入参数": "input_desc",
    "输出参数说明": "output_desc",
    "输出参数": "output_desc",
    "其他说明": "other_desc",
    "返回": "return_desc",
    "返回值": "return_desc",
    "返回数据": "return_desc",
}

_LABEL_RE = re.compile(
    r"^\s*(?:\[(?P<bracket>[^\]]+)\]|【(?P<fullwidth>[^】]+)】|(?P<plain>函数名|函数名称|函数中文名|功能描述|功能说明|功能|说明|输入参数说明|输入参数|输出参数说明|输出参数|其他说明|返回值?|返回数据))\s*[:：]?\s*(?P<rest>.*)$"
)
_DECORATION_RE = re.compile(r"^[\s*/\*\-_=#]{3,}$")
_COMMENT_EDGE_RE = re.compile(r"^\s*/\*+|\*/\s*$")
_LEADING_STAR_RE = re.compile(r"^\s*\*+\s?")
_SECTION_STOP_RE = re.compile(
    r"^\s*(?:\[(?:函数名|函数名称|函数中文名|功能描述|功能说明|功能|说明|输入参数说明|输入参数|输出参数说明|输出参数|其他说明|返回值?|返回数据)\]|【(?:函数名|函数名称|函数中文名|功能描述|功能说明|功能|说明|输入参数说明|输入参数|输出参数说明|输出参数|其他说明|返回值?|返回数据)】)"
)


def _clean_line(raw: object) -> str:
    text = str(raw or "").rstrip("\r\n")
    text = _COMMENT_EDGE_RE.sub("", text).strip()
    text = _LEADING_STAR_RE.sub("", text).strip()
    return text


def _is_decoration(line: str) -> bool:
    text = str(line or "").strip()
    return not text or bool(_DECORATION_RE.fullmatch(text))


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", "", str(label or "").strip())


def _clean_section_lines(lines: Iterable[str]) -> str:
    cleaned = [str(line or "").strip() for line in lines]
    while cleaned and _is_decoration(cleaned[0]):
        cleaned.pop(0)
    while cleaned and _is_decoration(cleaned[-1]):
        cleaned.pop()
    return "\n".join(line for line in cleaned if line.strip()).strip().lstrip("：:").strip()


def _fallback_free_text(lines: list[str]) -> tuple[str, str]:
    func_name = ""
    desc = ""
    for line in lines:
        stripped = line.strip().strip("-=:;,. ")
        if not stripped or _is_decoration(stripped):
            continue
        if re.match(r"^\d+\s*[\)\.、:：-]", stripped):
            continue
        if re.match(r"^[A-Za-z_]\w*\s*:?\s*$", stripped):
            func_name = stripped.rstrip(":：").strip()
            continue
        desc = stripped.rstrip("：:").strip()
        break
    return func_name, desc


def normalize_comment_block(raw: object) -> NormalizedComment:
    raw_text = str(raw or "")
    lines = [_clean_line(line) for line in raw_text.splitlines()]
    sections: dict[str, list[str]] = {}
    evidence: list[CommentEvidence] = []
    current_field = ""

    for idx, line in enumerate(lines):
        if _is_decoration(line):
            continue
        match = _LABEL_RE.match(line)
        if match:
            label = _normalize_label(match.group("bracket") or match.group("fullwidth") or match.group("plain") or "")
            field = _LABEL_TO_FIELD.get(label, "")
            current_field = field
            if not field:
                continue
            sections.setdefault(field, [])
            rest = str(match.group("rest") or "").strip().lstrip("：:").strip()
            if rest:
                sections[field].append(rest)
                evidence.append(CommentEvidence(field, idx, rest))
            continue
        if current_field:
            if _SECTION_STOP_RE.match(line):
                current_field = ""
                continue
            sections.setdefault(current_field, []).append(line)
            if line.strip():
                evidence.append(CommentEvidence(current_field, idx, line.strip()))

    values = {field: _clean_section_lines(chunks) for field, chunks in sections.items()}
    if not any(values.values()):
        func_name, desc = _fallback_free_text(lines)
        values = {"func_name": func_name, "desc": desc}

    func_name = values.get("func_name", "").splitlines()[0].strip().rstrip(":：") if values.get("func_name") else ""
    return NormalizedComment(
        func_name=func_name,
        func_cn_name=values.get("func_cn_name", ""),
        desc=values.get("desc", ""),
        input_desc=values.get("input_desc", ""),
        output_desc=values.get("output_desc", ""),
        other_desc=values.get("other_desc", ""),
        return_desc=values.get("return_desc", ""),
        evidence=tuple(evidence),
    )
```

- [ ] **Step 2: Run comment normalizer tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "comment_normalizer_extracts_project" -v
```

Expected: PASS for the two `comment_normalizer_extracts_project_*` tests.

- [ ] **Step 3: Commit the new module**

```bash
git add autodoc/comment_normalizer.py
git commit -m "feat: add deterministic comment normalizer"
```

---

### Task 3: Wire parser comment blocks through the normalizer

**Files:**
- Modify: `autodoc/parse.py`
- Test: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Import the normalizer in parse.py**

Add this import near the existing imports at the top of `autodoc/parse.py`:

```python
from .comment_normalizer import normalize_comment_block
```

- [ ] **Step 2: Replace parse_single_comment_block implementation body**

Replace the body of `parse_single_comment_block(raw: str) -> dict` with:

```python
def parse_single_comment_block(raw: str) -> dict:
    normalized = normalize_comment_block(raw)
    return normalized.to_parse_dict()
```

Keep the function name and public return shape unchanged.

- [ ] **Step 3: Run parser contract tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "parse_single_comment_block_preserves_existing_dict_contract" -v
```

Expected: PASS.

- [ ] **Step 4: Run nearby existing parser/comment tests**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "comment or parse_single_comment_block or effective_comment_desc" -v
```

Expected: PASS. If failures reveal valid existing behavior, extend the normalizer to preserve that behavior instead of changing tests.

- [ ] **Step 5: Commit parser wiring**

```bash
git add autodoc/parse.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: normalize function comments before parsing"
```

---

### Task 4: Add design-text regression for PROJECT-shaped functions

**Files:**
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Add helper for static function design text sections**

Append this helper near `_base_ctx`:

```python
def _text_sections_for_comment_and_body(raw_comment, *, func_name="DemoFunc", prototype="void DemoFunc(void)", body=""):
    comment_info = parse_single_comment_block(raw_comment)
    ctx = _base_ctx(body=body)
    ctx["comment_info"] = comment_info
    ctx["func_info"] = {
        "ret_type": prototype.split()[0],
        "func_name": func_name,
        "prototype": prototype,
    }
    return build_design_text_sections(ctx, "D/R_SDD01", 1, GenConfig(ai_assist=False))
```

- [ ] **Step 2: Add FdataAverage generated-text regression**

Append this test:

```python
def test_build_design_text_sections_uses_fdataaverage_comment_description():
    raw = """
    /**
     * 【函数名】:FdataAverage
     *
     * 【功能描述】浮点数求平均
     * 	 1、对一组浮点数，去除最大、最小值后，求平均值，当浮点数个数为零时，返回零；
     *   2、当浮点数个数大于零，小于三时，返回数组第一个数。
     *
     * 【输入参数说明】v_pBuff_f ---- 浮点数数组指针
     * 			   v_len_16  ---- 数据长度
     * 【输出参数说明】NONE
     * 【返回】:	数组中浮点数的平均值
     */
    """

    sections = _text_sections_for_comment_and_body(
        raw,
        func_name="FdataAverage",
        prototype="float FdataAverage(float *v_pBuff_f, Uint16 v_len_16)",
    )

    desc = "\n".join(sections["description_lines"])
    assert "浮点数求平均" in desc
    assert "去除最大、最小值" in desc
    assert "小于三时" in desc
    assert desc != "无。"
```

- [ ] **Step 3: Add Comm422FrameCheck generated-text regression**

Append this test:

```python
def test_build_design_text_sections_uses_comm422_comment_description():
    raw = """
    /**
     *    [函数名]	 Comm422FrameCheck
     *
     *    [功能描述]
     *    			  检测对应通道接收缓冲区是否存在有效报文。
     *    [输入参数说明] v_commID_u16  ---- RS422通道ID，可能取值为:
     *              	SCI_A_ID ---- SCIA接口
     *              	SCI_B_ID ---- SCIB接口
     *              	SCI_C_ID ---- SCIC接口
     *	  [输出参数说明] NONE
     *    [返回]		 返回有效报文首数据在缓冲区中索引，无有效报文时，返回:RS422_COMM_FRAM_NOT_EXIST
     */
    """

    sections = _text_sections_for_comment_and_body(
        raw,
        func_name="Comm422FrameCheck",
        prototype="Uint16 Comm422FrameCheck(Uint16 v_commID_u16)",
    )

    desc = "\n".join(sections["description_lines"])
    assert desc == "检测对应通道接收缓冲区是否存在有效报文。"
    assert desc != "无。"
```

- [ ] **Step 4: Run generated-text regressions**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "build_design_text_sections_uses" -v
```

Expected: PASS.

- [ ] **Step 5: Commit regression tests**

```bash
git add tests/test_pipeline_quality_repairs.py
git commit -m "test: cover normalized descriptions in design text"
```

---

### Task 5: Run focused verification and sample generation

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused pytest checks**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py \
  -k "comment_normalizer or parse_single_comment_block_preserves_existing_dict_contract or build_design_text_sections_uses" -v
```

Expected: all selected tests PASS.

- [ ] **Step 2: Generate PROJECT FdataAverage sample docx**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/DataObtain/DataObtainAI.c \
  --function FdataAverage \
  -o /tmp/autodoc_eval/FdataAverage.after-comment-normalization.docx \
  --codegraph off --verbose
```

Expected: command exits 0 and prints `文档已生成：/tmp/autodoc_eval/FdataAverage.after-comment-normalization.docx`.

- [ ] **Step 3: Inspect generated FdataAverage doc text**

Use the harness Read tool on:

```text
/tmp/autodoc_eval/FdataAverage.after-comment-normalization.docx
```

Expected: the `b) 功能说明` section contains `浮点数求平均` and does not contain only `无。`.

- [ ] **Step 4: Generate PROJECT Comm422FrameCheck sample docx**

Run:

```bash
mkdir -p /tmp/autodoc_eval && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/Communication/Comm422.c \
  --function Comm422FrameCheck \
  -o /tmp/autodoc_eval/Comm422FrameCheck.after-comment-normalization.docx \
  --codegraph off --verbose
```

Expected: command exits 0 and prints `文档已生成：/tmp/autodoc_eval/Comm422FrameCheck.after-comment-normalization.docx`.

- [ ] **Step 5: Inspect generated Comm422FrameCheck doc text**

Use the harness Read tool on:

```text
/tmp/autodoc_eval/Comm422FrameCheck.after-comment-normalization.docx
```

Expected: the `b) 功能说明` section contains `检测对应通道接收缓冲区是否存在有效报文` and does not contain only `无。`.

- [ ] **Step 6: Commit verification notes only if code or tests changed after prior commits**

If there are uncommitted implementation/test changes, commit them:

```bash
git add autodoc/comment_normalizer.py autodoc/parse.py tests/test_pipeline_quality_repairs.py
git commit -m "fix: preserve PROJECT function descriptions"
```

If there are no uncommitted implementation/test changes, do not create an empty commit.

---

## Self-Review Notes

Spec coverage for this plan:

- Covers Stage 1 comment normalization completely.
- Covers PROJECT acceptance cases for `TimeCountInit`, `FdataAverage`, and `Comm422FrameCheck` descriptions.
- Does not implement Stage 2 expression rendering, Stage 3 variable binding, Stage 4 logic IR/noise reduction, or Stage 5 domain rules. Those are separate implementation plans because each is independently testable and higher-risk.

No placeholders remain in the task steps. Function names introduced in tests match the implementation API defined in Task 2.
