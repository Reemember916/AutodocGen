# Review Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional read-only Review Workspace output: `review_bundle.json` plus offline `index.html`, without changing existing docx generation when disabled.

**Architecture:** Add a focused `autodoc.review_workspace` module that owns ReviewBundle data classes, JSON serialization, deterministic block IDs, HTML rendering, and atomic file writes. Pipeline code only collects review functions at existing `FunctionDesign` render points and flushes the bundle after docx save when review output is enabled. CLI exposes `--review-output {off,html}` and optional `--review-dir`.

**Tech Stack:** Python dataclasses, stdlib `json`/`html`/`hashlib`/`tempfile`, existing `GenConfig.extra_params`, existing `autodoc.pipeline` generation loops, pytest.

---

## File Structure

- Create `autodoc/review_workspace.py`
  - Owns review dataclasses, `to_dict()` conversion, stable block IDs, `build_review_function()`, `render_review_html()`, and `write_review_workspace()`.
- Modify `autodoc/pipeline.py`
  - Initializes transient review collection on `cfg`.
  - Appends a `ReviewFunction` after each `FunctionDesign` is produced.
  - Writes review output after `safe_save_docx()` in single-file, single-function, and project flows.
- Modify `autodoc/cli.py`
  - Adds `--review-output {off,html}` and `--review-dir` to `doc` command.
  - Stores values in `extra_params` and `GenConfig`.
- Modify `tests/test_pipeline_quality_repairs.py`
  - Adds focused unit/integration tests following existing test style.

---

### Task 1: ReviewBundle Model and HTML Renderer

**Files:**
- Create: `autodoc/review_workspace.py`
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Write failing unit tests for model serialization, stable IDs, and HTML escaping**

Append these tests near other utility-level tests in `tests/test_pipeline_quality_repairs.py`:

```python
def test_review_workspace_serializes_and_renders_escaped_html(tmp_path):
    from autodoc.review_workspace import (
        ReviewBlock,
        ReviewBundle,
        ReviewFunction,
        render_review_html,
        review_block_id,
        review_bundle_to_dict,
    )

    block_id = review_block_id("Comm422FrameCheck", "logic", 1)
    assert block_id == "Comm422FrameCheck.logic.001"

    bundle = ReviewBundle(
        schema_version=1,
        project_root="/project",
        output_docx="/project/out.docx",
        functions=(
            ReviewFunction(
                function_id="Comm422FrameCheck",
                name="Comm422FrameCheck",
                title="422 <Frame> & Check",
                source_file="Comm422.c",
                source_hash="abc123",
                blocks=(
                    ReviewBlock(
                        block_id=block_id,
                        function_id="Comm422FrameCheck",
                        kind="logic_line",
                        title="Logic <1>",
                        text="if (x < y) & dangerous <script>alert(1)</script>",
                        confidence=0.75,
                    ),
                ),
            ),
        ),
    )

    data = review_bundle_to_dict(bundle)
    assert data["schema_version"] == 1
    assert data["functions"][0]["blocks"][0]["block_id"] == block_id
    assert data["functions"][0]["blocks"][0]["confidence"] == 0.75

    html = render_review_html(bundle)
    assert "data-block-id=\"Comm422FrameCheck.logic.001\"" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "review_bundle.json" in html


def test_review_workspace_block_id_sanitizes_non_identifier_names():
    from autodoc.review_workspace import review_block_id

    assert review_block_id("模块/函数 名", "params.input", 12) == "_____.params.input.012"
    assert review_block_id("", "logic", 2) == "function.logic.002"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace" -v
```

Expected: FAIL because `autodoc.review_workspace` does not exist.

- [ ] **Step 3: Implement minimal `autodoc/review_workspace.py`**

Create the file with this implementation skeleton, keeping it stdlib-only:

```python
"""Review workspace bundle and offline HTML rendering."""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
import hashlib
import html
import json
import os
import re
import tempfile
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReviewSourceRange:
    file: str = ""
    start_line: int = 0
    end_line: int = 0


@dataclass(frozen=True)
class ReviewEvidenceRef:
    kind: str
    ref_id: str = ""
    label: str = ""
    source_range: ReviewSourceRange = field(default_factory=ReviewSourceRange)
    confidence: float = 0.0


@dataclass(frozen=True)
class ReviewQualityFlag:
    code: str
    severity: str = "info"
    message: str = ""
    block_id: str = ""


@dataclass(frozen=True)
class ReviewBlock:
    block_id: str
    function_id: str
    kind: str
    title: str = ""
    text: str = ""
    rows: tuple[dict[str, str], ...] = ()
    source_range: ReviewSourceRange = field(default_factory=ReviewSourceRange)
    evidence: tuple[ReviewEvidenceRef, ...] = ()
    quality_flags: tuple[ReviewQualityFlag, ...] = ()
    confidence: float = 1.0
    editable: bool = True


@dataclass(frozen=True)
class ReviewFunction:
    function_id: str
    name: str
    title: str = ""
    source_file: str = ""
    source_hash: str = ""
    blocks: tuple[ReviewBlock, ...] = ()


@dataclass(frozen=True)
class ReviewBundle:
    schema_version: int = SCHEMA_VERSION
    project_root: str = ""
    output_docx: str = ""
    functions: tuple[ReviewFunction, ...] = ()
    quality_flags: tuple[ReviewQualityFlag, ...] = ()


def review_slug(value: str, *, fallback: str = "function") -> str:
    raw = str(value or "")
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
    return slug or fallback


def review_block_id(function_name: str, kind: str, index: int) -> str:
    func = review_slug(function_name)
    clean_kind = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(kind or "block")).strip("._-") or "block"
    return f"{func}.{clean_kind}.{max(0, int(index)):03d}"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in value.__dict__.items()}
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def review_bundle_to_dict(bundle: ReviewBundle) -> dict[str, Any]:
    data = _jsonable(bundle)
    return data if isinstance(data, dict) else {}


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _render_rows(rows: tuple[dict[str, str], ...]) -> str:
    if not rows:
        return ""
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    head = "".join(f"<th>{_esc(k)}</th>" for k in keys)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{_esc(row.get(k, ''))}</td>" for k in keys) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_review_html(bundle: ReviewBundle) -> str:
    functions = list(bundle.functions or ())
    nav = "".join(
        f"<li><a href=\"#{_esc(fn.function_id)}\">{_esc(fn.title or fn.name)}</a></li>"
        for fn in functions
    )
    sections: list[str] = []
    warnings: list[str] = []
    for fn in functions:
        blocks = []
        for block in fn.blocks or ():
            flags = "".join(f"<li>{_esc(flag.severity)}: {_esc(flag.message or flag.code)}</li>" for flag in block.quality_flags)
            if flags:
                warnings.append(f"<h4>{_esc(block.block_id)}</h4><ul>{flags}</ul>")
            rows = _render_rows(tuple(block.rows or ()))
            text = f"<p>{_esc(block.text)}</p>" if block.text else ""
            blocks.append(
                "<article class=\"block\" "
                f"data-block-id=\"{_esc(block.block_id)}\" "
                f"data-kind=\"{_esc(block.kind)}\">"
                f"<h3>{_esc(block.title or block.kind)}</h3>"
                f"{text}{rows}"
                f"<p class=\"meta\">confidence={_esc(block.confidence)} source={_esc(block.source_range.file)}:{_esc(block.source_range.start_line)}</p>"
                "</article>"
            )
        sections.append(
            f"<section id=\"{_esc(fn.function_id)}\"><h2>{_esc(fn.title or fn.name)}</h2>"
            f"<p class=\"meta\">{_esc(fn.source_file)} { _esc(fn.source_hash) }</p>"
            + "".join(blocks)
            + "</section>"
        )
    warning_html = "".join(warnings) or "<p>无质量警告。</p>"
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AutoDocGen Review Workspace</title>
<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #0f172a; background: #f8fafc; }
.layout { display: grid; grid-template-columns: 240px minmax(420px, 1fr) 320px; gap: 16px; padding: 16px; }
aside, main, .panel { background: white; border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px; }
.block { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin: 10px 0; }
.meta { color: #64748b; font-size: 12px; }
table { border-collapse: collapse; width: 100%; margin-top: 8px; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left; }
code { background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }
</style>
</head>
<body>
<div class="layout">
<aside><h1>Functions</h1><ul>""" + nav + """</ul><p><a href="review_bundle.json">review_bundle.json</a></p></aside>
<main><h1>Generated Design Blocks</h1>""" + "".join(sections) + """</main>
<div class="panel"><h1>Evidence / Warnings</h1>""" + warning_html + """</div>
</div>
</body>
</html>
"""
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace" -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit Task 1**

```bash
git add autodoc/review_workspace.py tests/test_pipeline_quality_repairs.py
git commit -m "feat: add review workspace model"
```

---

### Task 2: Build ReviewFunctions From Existing FunctionDesign

**Files:**
- Modify: `autodoc/review_workspace.py`
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Write failing test for `build_review_function()`**

Append:

```python
def test_build_review_function_creates_summary_table_and_logic_blocks():
    from autodoc.models import FunctionDesign, IoElement, LocalElement
    from autodoc.review_workspace import build_review_function

    design = FunctionDesign(
        title="帧检查",
        req_id="D/R_SDD01_001",
        prototype="Uint16 Comm422FrameCheck(Uint16 v_commID_u16)",
        description_lines=("检测接收缓冲区是否存在有效报文。",),
        io_elements=(IoElement("v_commID_u16", "通道号", "Uint16", "输入", "RS422 ID"),),
        local_elements=(LocalElement("l_ii_u16", "候选帧索引", "Uint16", "局部变量"),),
        logic_lines=("IF 通道号有效时", "遍历候选帧。"),
    )
    func_data = {
        "func_info": {"func_name": "Comm422FrameCheck", "prototype": design.prototype},
        "source_file": "Comm422.c",
        "body": "return 0;\n",
    }

    review_fn = build_review_function(design, func_data)

    assert review_fn.function_id == "Comm422FrameCheck"
    block_ids = [b.block_id for b in review_fn.blocks]
    assert "Comm422FrameCheck.summary.001" in block_ids
    assert "Comm422FrameCheck.prototype.001" in block_ids
    assert "Comm422FrameCheck.io.001" in block_ids
    assert "Comm422FrameCheck.locals.001" in block_ids
    assert "Comm422FrameCheck.logic.001" in block_ids
    assert "Comm422FrameCheck.logic.002" in block_ids
    logic_texts = [b.text for b in review_fn.blocks if b.kind == "logic_line"]
    assert logic_texts == ["IF 通道号有效时", "遍历候选帧。"]
    assert review_fn.source_hash
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "build_review_function" -v
```

Expected: FAIL because `build_review_function` is missing.

- [ ] **Step 3: Implement `build_review_function()`**

Add helpers to `autodoc/review_workspace.py`:

```python
def _safe_get(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _source_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _element_row(element: Any) -> dict[str, str]:
    return {
        "ident": str(_safe_get(element, "ident", "")),
        "name": str(_safe_get(element, "name", "")),
        "c_type": str(_safe_get(element, "c_type", "")),
        "direction": str(_safe_get(element, "direction", "")),
        "usage": str(_safe_get(element, "usage", "")),
    }


def build_review_function(design: Any, func_data: dict[str, Any] | None = None, cfg: Any = None) -> ReviewFunction:
    del cfg
    data = dict(func_data or {})
    func_info = data.get("func_info") or {}
    name = str(func_info.get("func_name") or _safe_get(design, "func_name", "") or _safe_get(design, "title", "") or "function")
    title = str(_safe_get(design, "title", "") or name)
    source_file = str(data.get("source_file") or (data.get("file_context") or {}).get("source_file") or "")
    body = str(data.get("body") or "")
    blocks: list[ReviewBlock] = []

    desc = "\n".join(str(x) for x in (_safe_get(design, "description_lines", ()) or ()) if str(x).strip())
    if desc or title:
        blocks.append(ReviewBlock(review_block_id(name, "summary", 1), name, "summary", title="功能说明", text=desc or title))

    prototype = str(_safe_get(design, "prototype", "") or func_info.get("prototype") or "")
    if prototype:
        blocks.append(ReviewBlock(review_block_id(name, "prototype", 1), name, "prototype", title="函数原型", text=prototype, editable=False))

    io_rows = tuple(_element_row(e) for e in (_safe_get(design, "io_elements", ()) or ()))
    if io_rows:
        blocks.append(ReviewBlock(review_block_id(name, "io", 1), name, "io_table", title="输入输出参数", rows=io_rows))

    local_rows = tuple(_element_row(e) for e in (_safe_get(design, "local_elements", ()) or ()))
    if local_rows:
        blocks.append(ReviewBlock(review_block_id(name, "locals", 1), name, "local_table", title="局部变量", rows=local_rows))

    return_desc = "\n".join(str(x) for x in (_safe_get(design, "return_desc_lines", ()) or ()) if str(x).strip())
    if return_desc:
        blocks.append(ReviewBlock(review_block_id(name, "return", 1), name, "return", title="返回值", text=return_desc))

    for idx, line in enumerate((_safe_get(design, "logic_lines", ()) or ()), start=1):
        text = str(line or "").strip()
        if text:
            blocks.append(ReviewBlock(review_block_id(name, "logic", idx), name, "logic_line", title=f"逻辑 {idx}", text=text))

    return ReviewFunction(
        function_id=review_slug(name),
        name=name,
        title=title,
        source_file=source_file,
        source_hash=_source_hash(body),
        blocks=tuple(blocks),
    )
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace or build_review_function" -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit Task 2**

```bash
git add autodoc/review_workspace.py tests/test_pipeline_quality_repairs.py
git commit -m "feat: build review functions from designs"
```

---

### Task 3: Write Review Workspace Files and Wire Pipeline Collection

**Files:**
- Modify: `autodoc/review_workspace.py`
- Modify: `autodoc/pipeline.py`
- Modify: `tests/test_pipeline_quality_repairs.py`

- [ ] **Step 1: Write failing tests for atomic file output and disabled-by-default config**

Append:

```python
def test_write_review_workspace_creates_json_and_html(tmp_path):
    import json
    from autodoc.review_workspace import ReviewBlock, ReviewBundle, ReviewFunction, write_review_workspace

    bundle = ReviewBundle(
        output_docx=str(tmp_path / "out.docx"),
        functions=(
            ReviewFunction(
                function_id="DemoFunc",
                name="DemoFunc",
                blocks=(ReviewBlock("DemoFunc.logic.001", "DemoFunc", "logic_line", text="执行处理"),),
            ),
        ),
    )

    out_dir = write_review_workspace(bundle, str(tmp_path / "review"))

    assert out_dir == str(tmp_path / "review")
    data = json.loads((tmp_path / "review" / "review_bundle.json").read_text(encoding="utf-8"))
    assert data["functions"][0]["function_id"] == "DemoFunc"
    assert "data-block-id=\"DemoFunc.logic.001\"" in (tmp_path / "review" / "index.html").read_text(encoding="utf-8")


def test_review_workspace_config_defaults_off():
    from autodoc.review_workspace import review_output_enabled, review_output_dir

    cfg = GenConfig(ai_assist=False)
    assert review_output_enabled(cfg) is False
    assert review_output_dir(cfg, "/tmp/out.docx").endswith("out_review")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "write_review_workspace or review_workspace_config" -v
```

Expected: FAIL because `write_review_workspace`, `review_output_enabled`, or `review_output_dir` are missing.

- [ ] **Step 3: Implement write/config helpers**

Add to `autodoc/review_workspace.py`:

```python
def _cfg_extra(cfg: Any) -> dict[str, Any]:
    extra = getattr(cfg, "extra_params", None)
    return extra if isinstance(extra, dict) else {}


def review_output_mode(cfg: Any) -> str:
    mode = str(_cfg_extra(cfg).get("review_output") or getattr(cfg, "review_output", "off") or "off").strip().lower()
    return mode if mode in {"off", "html"} else "off"


def review_output_enabled(cfg: Any) -> bool:
    return review_output_mode(cfg) == "html"


def review_output_dir(cfg: Any, output_docx: str) -> str:
    explicit = str(_cfg_extra(cfg).get("review_dir") or getattr(cfg, "review_dir", "") or "").strip()
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    base = os.path.splitext(os.path.abspath(str(output_docx or "review.docx")))[0]
    return base + "_review"


def _atomic_write_text(path: str, content: str) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def write_review_workspace(bundle: ReviewBundle, out_dir: str) -> str:
    target_dir = os.path.abspath(os.path.expanduser(str(out_dir or "")))
    if not target_dir:
        raise ValueError("review output directory is empty")
    os.makedirs(target_dir, exist_ok=True)
    data = json.dumps(review_bundle_to_dict(bundle), ensure_ascii=False, indent=2)
    _atomic_write_text(os.path.join(target_dir, "review_bundle.json"), data + "\n")
    _atomic_write_text(os.path.join(target_dir, "index.html"), render_review_html(bundle))
    return target_dir
```

- [ ] **Step 4: Wire pipeline collection narrowly**

In `autodoc/pipeline.py`, import/use the module inside functions to avoid startup coupling.

Add small helpers near other generation helpers:

```python
def _review_collection(cfg) -> list:
    items = getattr(cfg, "_review_workspace_functions", None)
    if not isinstance(items, list):
        items = []
        try:
            cfg._review_workspace_functions = items
        except Exception:
            pass
    return items


def _collect_review_function(cfg, design, task) -> None:
    try:
        from . import review_workspace
        if not review_workspace.review_output_enabled(cfg):
            return
        func_data = dict((task or {}).get("func_data") or {})
        func_data.setdefault("source_file", (task or {}).get("source_file", ""))
        _review_collection(cfg).append(review_workspace.build_review_function(design, func_data, cfg))
    except Exception as exc:
        backend = legacy_backend()
        backend.vlog(cfg, f"Review workspace collection skipped: {exc}")


def _write_review_workspace_if_enabled(cfg, output: str, *, project_root: str = "") -> None:
    from . import review_workspace
    if not review_workspace.review_output_enabled(cfg):
        return
    functions = tuple(getattr(cfg, "_review_workspace_functions", []) or ())
    bundle = review_workspace.ReviewBundle(
        project_root=str(project_root or ""),
        output_docx=str(output or ""),
        functions=functions,
    )
    out_dir = review_workspace.review_output_dir(cfg, output)
    review_workspace.write_review_workspace(bundle, out_dir)
    legacy_backend().vlog(cfg, f"Review workspace 已生成：{out_dir}")
```

Call `_collect_review_function(cfg, design, task)` in both `execute_project_module_tasks()` and `execute_single_file_tasks()` immediately after `render_module.render_function_design(doc, design, cfg)` succeeds.

Call `_write_review_workspace_if_enabled()` after each successful `safe_save_docx()` in:

- single-file generation save path around `pipeline.py:6261`
- single-function generation save path around `pipeline.py:6403`
- project generation save path around `pipeline.py:6944`

Use the known `source`, `project_root`, or `root_dir` argument as `project_root` when available.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace or build_review_function or write_review_workspace or review_workspace_config" -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit Task 3**

```bash
git add autodoc/review_workspace.py autodoc/pipeline.py tests/test_pipeline_quality_repairs.py
git commit -m "feat: write review workspace output"
```

---

### Task 4: CLI Flags and PROJECT Smoke Verification

**Files:**
- Modify: `autodoc/cli.py`
- Modify: `tests/test_pipeline_quality_repairs.py` if a unit-level CLI parser test is practical; otherwise use command verification.

- [ ] **Step 1: Write failing parser test for CLI review flags**

Append:

```python
def test_cli_doc_accepts_review_output_flags(monkeypatch):
    from autodoc.cli import parse_args

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "AutoDocGen_V1.4.py",
            "doc",
            "-f",
            "demo.c",
            "-o",
            "out.docx",
            "--review-output",
            "html",
            "--review-dir",
            "review-out",
        ],
    )
    args = parse_args()
    assert args.review_output == "html"
    assert args.review_dir == "review-out"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "cli_doc_accepts_review_output_flags" -v
```

Expected: FAIL because CLI flags are missing.

- [ ] **Step 3: Add CLI arguments and extra_params plumbing**

In `autodoc/cli.py`, add to `docp`:

```python
    docp.add_argument("--review-output", default="off", choices=["off", "html"],
                      help="生成离线人工审查 HTML 包：off=关闭，html=输出 review_bundle.json + index.html")
    docp.add_argument("--review-dir", default="",
                      help="审查 HTML 包输出目录；默认使用 <输出文件名>_review")
```

In `extra_params` creation, add:

```python
            "review_output": args.review_output,
            "review_dir": args.review_dir,
```

Do not add GUI settings in this task.

- [ ] **Step 4: Run parser test and focused suite**

Run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace or build_review_function or write_review_workspace or review_workspace_config or cli_doc_accepts_review_output_flags" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Run PROJECT smoke command with review output**

Run from repo root/worktree:

```bash
rm -rf /tmp/autodoc_review_smoke && mkdir -p /tmp/autodoc_review_smoke && \
python3 AutoDocGen_V1.4.py doc \
  -d /Users/ree/Downloads/PROJECT-2007-0613 \
  -f /Users/ree/Downloads/PROJECT-2007-0613/Src/Application/DataObtain/DataObtainAI.c \
  --function FdataAverage \
  -o /tmp/autodoc_review_smoke/FdataAverage.docx \
  --codegraph off \
  --review-output html \
  --review-dir /tmp/autodoc_review_smoke/review \
  --verbose
```

Expected:

- command exits 0
- `/tmp/autodoc_review_smoke/FdataAverage.docx` exists
- `/tmp/autodoc_review_smoke/review/review_bundle.json` exists
- `/tmp/autodoc_review_smoke/review/index.html` exists

Inspect with Python, not shell paging:

```bash
python3 - <<'PY'
import json, pathlib
root = pathlib.Path('/tmp/autodoc_review_smoke/review')
data = json.loads((root / 'review_bundle.json').read_text(encoding='utf-8'))
assert data['functions'][0]['name'] == 'FdataAverage'
blocks = data['functions'][0]['blocks']
assert any(b['kind'] == 'summary' for b in blocks)
assert any(b['kind'] == 'logic_line' for b in blocks)
html = (root / 'index.html').read_text(encoding='utf-8')
assert 'data-block-id=' in html
assert 'FdataAverage' in html
print('review smoke ok', len(blocks))
PY
```

Expected output includes `review smoke ok`.

- [ ] **Step 6: Commit Task 4**

```bash
git add autodoc/cli.py tests/test_pipeline_quality_repairs.py
git commit -m "feat: expose review workspace cli"
```

---

## Final Verification

After all tasks pass reviews, run:

```bash
python3 -m pytest tests/test_pipeline_quality_repairs.py -k "review_workspace or build_review_function or write_review_workspace or review_workspace_config or cli_doc_accepts_review_output_flags" -v
python3 -m pytest
```

Then run the PROJECT smoke command from Task 4 again.

## Self-Review Checklist

- Spec coverage: model, HTML renderer, config, CLI, pipeline write, PROJECT smoke all covered.
- No placeholders: every task includes exact files, test code, implementation direction, commands, expected output.
- Type consistency: `ReviewBundle`, `ReviewFunction`, `ReviewBlock`, `review_block_id`, `review_bundle_to_dict`, `render_review_html`, `write_review_workspace`, `review_output_enabled`, and `review_output_dir` are consistently named across tasks.
