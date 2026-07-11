"""Review workspace bundle and offline HTML rendering."""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, replace
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
    if not raw:
        return fallback
    slug = re.sub(r"[\u4e00-\u9fff]+|[^A-Za-z0-9_]", "_", raw)
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


def _review_source_range_from_dict(data: Any) -> ReviewSourceRange:
    item = data if isinstance(data, dict) else {}
    return ReviewSourceRange(
        file=str(item.get("file") or ""),
        start_line=int(item.get("start_line") or 0),
        end_line=int(item.get("end_line") or 0),
    )


def _review_quality_flag_from_dict(data: Any) -> ReviewQualityFlag:
    item = data if isinstance(data, dict) else {}
    return ReviewQualityFlag(
        code=str(item.get("code") or ""),
        severity=str(item.get("severity") or "info"),
        message=str(item.get("message") or ""),
        block_id=str(item.get("block_id") or ""),
    )


def _review_evidence_ref_from_dict(data: Any) -> ReviewEvidenceRef:
    item = data if isinstance(data, dict) else {}
    return ReviewEvidenceRef(
        kind=str(item.get("kind") or ""),
        ref_id=str(item.get("ref_id") or ""),
        label=str(item.get("label") or ""),
        source_range=_review_source_range_from_dict(item.get("source_range")),
        confidence=float(item.get("confidence") or 0.0),
    )


def _review_block_from_dict(data: Any) -> ReviewBlock:
    item = data if isinstance(data, dict) else {}
    rows = item.get("rows") if isinstance(item.get("rows"), list) else []
    return ReviewBlock(
        block_id=str(item.get("block_id") or ""),
        function_id=str(item.get("function_id") or ""),
        kind=str(item.get("kind") or ""),
        title=str(item.get("title") or ""),
        text=str(item.get("text") or ""),
        rows=tuple(dict(row) for row in rows if isinstance(row, dict)),
        source_range=_review_source_range_from_dict(item.get("source_range")),
        evidence=tuple(_review_evidence_ref_from_dict(x) for x in (item.get("evidence") or ()) if isinstance(x, dict)),
        quality_flags=tuple(_review_quality_flag_from_dict(x) for x in (item.get("quality_flags") or ()) if isinstance(x, dict)),
        confidence=float(item.get("confidence") if item.get("confidence") is not None else 1.0),
        editable=bool(item.get("editable") if item.get("editable") is not None else True),
    )


def _review_function_from_dict(data: Any) -> ReviewFunction:
    item = data if isinstance(data, dict) else {}
    return ReviewFunction(
        function_id=str(item.get("function_id") or ""),
        name=str(item.get("name") or ""),
        title=str(item.get("title") or ""),
        source_file=str(item.get("source_file") or ""),
        source_hash=str(item.get("source_hash") or ""),
        blocks=tuple(_review_block_from_dict(x) for x in (item.get("blocks") or ()) if isinstance(x, dict)),
    )


def _review_bundle_from_dict(data: Any) -> ReviewBundle:
    item = data if isinstance(data, dict) else {}
    return ReviewBundle(
        schema_version=int(item.get("schema_version") or SCHEMA_VERSION),
        project_root=str(item.get("project_root") or ""),
        output_docx=str(item.get("output_docx") or ""),
        functions=tuple(_review_function_from_dict(x) for x in (item.get("functions") or ()) if isinstance(x, dict)),
        quality_flags=tuple(_review_quality_flag_from_dict(x) for x in (item.get("quality_flags") or ()) if isinstance(x, dict)),
    )


def _function_identity(fn: ReviewFunction) -> tuple[str, str]:
    return (str(fn.source_file or ""), str(fn.name or fn.function_id or ""))


def _block_identity(block: ReviewBlock) -> tuple[str, str, str]:
    return (str(block.function_id or ""), str(block.block_id or ""), str(block.kind or ""))


def _dedupe_review_function_blocks(fn: ReviewFunction) -> ReviewFunction:
    by_key: dict[tuple[str, str, str], ReviewBlock] = {}
    order: list[tuple[str, str, str]] = []
    for block in fn.blocks or ():
        key = _block_identity(block)
        if key not in by_key:
            order.append(key)
        by_key[key] = block
    return replace(fn, blocks=tuple(by_key[key] for key in order))


def merge_review_bundles(existing: ReviewBundle, current: ReviewBundle) -> ReviewBundle:
    by_key: dict[tuple[str, str], ReviewFunction] = {}
    order: list[tuple[str, str]] = []
    for fn in existing.functions or ():
        fn = disambiguate_review_function(_dedupe_review_function_blocks(fn), list(by_key.values()))
        key = _function_identity(fn)
        if key not in by_key:
            order.append(key)
        by_key[key] = fn
    for fn in current.functions or ():
        key = _function_identity(fn)
        fn = _dedupe_review_function_blocks(fn)
        if key in by_key:
            existing_fn = by_key[key]
            if str(existing_fn.function_id or "") != str(fn.function_id or ""):
                fn = rename_review_function_id(fn, str(existing_fn.function_id or ""))
        else:
            fn = disambiguate_review_function(fn, list(by_key.values()))
            key = _function_identity(fn)
            order.append(key)
        by_key[key] = fn
    return replace(current, functions=tuple(by_key[key] for key in order))


def _load_review_bundle_json(path: str) -> ReviewBundle | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _review_bundle_from_dict(json.load(f))
    except FileNotFoundError:
        return None


def rename_review_function_id(fn: ReviewFunction, function_id: str) -> ReviewFunction:
    old_id = str(fn.function_id or "")
    new_id = str(function_id or old_id or "function")
    blocks: list[ReviewBlock] = []
    for block in fn.blocks or ():
        block_id = str(block.block_id or "")
        if old_id and block_id.startswith(old_id + "."):
            block_id = new_id + block_id[len(old_id):]
        blocks.append(replace(block, function_id=new_id, block_id=block_id))
    return replace(fn, function_id=new_id, blocks=tuple(blocks))


def disambiguate_review_function(fn: ReviewFunction, existing: tuple[ReviewFunction, ...] | list[ReviewFunction]) -> ReviewFunction:
    fn_id = str(fn.function_id or "")
    fn_identity = _function_identity(fn)
    seen_ids = {str(item.function_id or "") for item in existing or ()}
    collision = any(str(item.function_id or "") == fn_id and _function_identity(item) != fn_identity for item in existing or ())
    if not collision:
        return fn
    source_base = os.path.splitext(os.path.basename(str(fn.source_file or "source")))[0]
    base = f"{fn_id}_{review_slug(source_base, fallback='source')}"
    candidate = base
    if candidate in seen_ids:
        candidate = f"{base}_{_source_hash(fn.source_file)[:8]}"
    index = 2
    while candidate in seen_ids:
        candidate = f"{base}_{index}"
        index += 1
    return rename_review_function_id(fn, candidate)


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
    for flag in bundle.quality_flags or ():
        warnings.append(f"<h4>{_esc(flag.block_id or flag.code)}</h4><ul><li>{_esc(flag.severity)}: {_esc(flag.message or flag.code)}</li></ul>")
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

    return_desc_lines = _safe_get(design, "return_desc_lines", ()) or ()
    return_desc = "\n".join(str(x) for x in return_desc_lines if str(x).strip())
    if not return_desc:
        comment_info = data.get("comment_info") or {}
        comment_return = _safe_get(comment_info, "return_desc", "")
        if isinstance(comment_return, (list, tuple)):
            return_desc = "\n".join(str(x) for x in comment_return if str(x).strip())
        elif str(comment_return).strip():
            return_desc = str(comment_return)
    if return_desc:
        blocks.append(ReviewBlock(review_block_id(name, "return", 1), name, "return", title="返回值", text=return_desc))

    for idx, line in enumerate((_safe_get(design, "logic_lines", ()) or ()), start=1):
        text = str(line or "")
        if text.strip():
            blocks.append(ReviewBlock(review_block_id(name, "logic", idx), name, "logic_line", title=f"逻辑 {idx}", text=text))

    return ReviewFunction(
        function_id=review_slug(name),
        name=name,
        title=title,
        source_file=source_file,
        source_hash=_source_hash(body),
        blocks=tuple(blocks),
    )


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


def write_review_workspace(bundle: ReviewBundle, out_dir: str, *, merge_existing: bool = False) -> str:
    target_dir = os.path.abspath(os.path.expanduser(str(out_dir or "")))
    if not target_dir:
        raise ValueError("review output directory is empty")
    os.makedirs(target_dir, exist_ok=True)
    existing = _load_review_bundle_json(os.path.join(target_dir, "review_bundle.json")) if merge_existing else None
    if existing is not None:
        bundle = merge_review_bundles(existing, bundle)
    else:
        bundle = replace(bundle, functions=tuple(_dedupe_review_function_blocks(fn) for fn in bundle.functions or ()))
    data = json.dumps(review_bundle_to_dict(bundle), ensure_ascii=False, indent=2)
    _atomic_write_text(os.path.join(target_dir, "review_bundle.json"), data + "\n")
    _atomic_write_text(os.path.join(target_dir, "index.html"), render_review_html(bundle))
    return target_dir
