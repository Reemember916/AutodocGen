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


def review_function_key(bundle: ReviewBundle, fn: ReviewFunction) -> str:
    source = str(fn.source_file or "").strip()
    root = str(bundle.project_root or "").strip()
    if source and root:
        try:
            source_abs = os.path.normcase(os.path.abspath(os.path.expanduser(source)))
            root_abs = os.path.normcase(os.path.abspath(os.path.expanduser(root)))
            # Single-file generation historically stored the C file path as project_root.
            # Treat that as the parent directory so keys stay stable and matchable.
            if os.path.isfile(root_abs) or root_abs.lower().endswith((".c", ".h", ".cpp", ".cc", ".cxx")):
                root_abs = os.path.dirname(root_abs) or root_abs
            rel = os.path.relpath(source_abs, root_abs)
            if rel in ("", os.curdir):
                source = os.path.basename(source_abs) or source
            elif rel != os.pardir and not rel.startswith(os.pardir + os.sep):
                source = rel
        except (OSError, ValueError):
            pass
    source = source.replace(os.sep, "/").strip()
    if source in ("", ".", "./"):
        source = os.path.basename(str(fn.source_file or "").strip()) or "unknown"
    return f"{source}::{str(fn.name or fn.function_id or '').strip()}"


def review_bundle_fingerprint(bundle: ReviewBundle) -> str:
    items = [
        {"key": review_function_key(bundle, fn), "source_hash": str(fn.source_hash or "")}
        for fn in bundle.functions or ()
    ]
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


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


def review_bundle_from_dict(data: Any) -> ReviewBundle:
    """Build a typed review bundle from its serialized representation."""

    return _review_bundle_from_dict(data)


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


def _safe_json_for_html(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _render_initial_function(fn: ReviewFunction | None) -> str:
    if fn is None:
        return '<div class="empty-state">无可审查函数</div>'
    blocks: list[str] = []
    for block in fn.blocks or ():
        rows = _render_rows(tuple(block.rows or ()))
        text = f"<p>{_esc(block.text)}</p>" if block.text else ""
        blocks.append(
            '<article class="review-block" '
            f'data-block-id="{_esc(block.block_id)}" data-kind="{_esc(block.kind)}">'
            f"<h3>{_esc(block.title or block.kind)}</h3>{text}{rows}</article>"
        )
    return (
        f'<header class="function-header"><h2>{_esc(fn.title or fn.name)}</h2>'
        f'<p class="meta">{_esc(fn.source_file)}</p></header>'
        + "".join(blocks)
    )


def render_review_html(bundle: ReviewBundle) -> str:
    functions = list(bundle.functions or ())
    data = review_bundle_to_dict(bundle)
    for raw_fn, fn in zip(data.get("functions") or (), functions):
        if isinstance(raw_fn, dict):
            raw_fn["review_key"] = review_function_key(bundle, fn)
    payload = {
        "schema_version": 1,
        "bundle_fingerprint": review_bundle_fingerprint(bundle),
        "bundle": data,
    }
    embedded = _safe_json_for_html(payload)
    initial = _render_initial_function(functions[0] if functions else None)
    bundle_warnings = "".join(
        f'<li>{_esc(flag.severity)}: {_esc(flag.message or flag.code)}</li>'
        for flag in bundle.quality_flags or ()
    ) or "<li>无质量警告</li>"
    template = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoDocGen Review Workspace</title>
<style>
:root { color-scheme: light; --ink:#17202a; --muted:#68727d; --line:#d6dadd; --soft:#f4f5f6; --panel:#ffffff; --focus:#1f6f5f; --ok:#246b45; --warn:#946200; --bad:#a33a35; }
* { box-sizing: border-box; letter-spacing: 0; }
html, body { margin: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--soft); }
button, input, select, textarea { font: inherit; color: inherit; letter-spacing: 0; }
button { cursor: pointer; }
.topbar { height: 58px; display:flex; align-items:center; gap:12px; padding:0 16px; background:#20262c; color:white; border-bottom:1px solid #11161a; }
.topbar h1 { margin:0; font-size:16px; font-weight:650; white-space:nowrap; }
.topbar .meta { color:#cbd1d6; margin-right:auto; }
.command { border:1px solid #68727d; background:#303840; color:white; border-radius:5px; padding:7px 10px; }
.command.primary { background:#23705f; border-color:#23705f; }
.workspace { height:calc(100vh - 58px); display:grid; grid-template-columns:minmax(250px, 310px) minmax(520px, 1fr) minmax(260px, 320px); }
.sidebar, .editor, .inspector { min-width:0; overflow:auto; background:var(--panel); }
.sidebar { border-right:1px solid var(--line); }
.editor { padding:20px 24px 60px; }
.inspector { border-left:1px solid var(--line); padding:16px; }
.filters { position:sticky; top:0; z-index:2; background:white; padding:14px; border-bottom:1px solid var(--line); }
.filters input, .filters select { width:100%; height:36px; border:1px solid #aeb5ba; border-radius:4px; padding:0 9px; margin-bottom:8px; background:white; }
.summary-strip { display:flex; flex-wrap:wrap; gap:5px; color:var(--muted); font-size:12px; }
.summary-strip span { padding:3px 6px; border:1px solid var(--line); border-radius:4px; background:var(--soft); }
.function-list { padding:8px; }
.function-item { width:100%; min-height:58px; text-align:left; border:1px solid transparent; border-bottom-color:#eceeef; background:white; padding:9px; display:grid; gap:4px; }
.function-item:hover { background:#f7f8f8; }
.function-item.active { border-color:#6c958c; background:#edf5f2; border-radius:5px; }
.function-row { display:flex; align-items:center; gap:8px; min-width:0; }
.function-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; font-weight:620; flex:1; }
.function-path { color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }
.status-dot { width:8px; height:8px; border-radius:50%; background:#aeb5ba; flex:0 0 auto; }
.status-dot.approved { background:var(--ok); }.status-dot.needs_revision { background:var(--warn); }.status-dot.rejected { background:var(--bad); }
.function-header { border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:18px; }
.function-header h2 { margin:0 0 7px; font-size:21px; }
.meta { color:var(--muted); font-size:12px; overflow-wrap:anywhere; }
.field { margin:0 0 18px; }
.field label, .review-block h3, .inspector h2, .inspector h3 { display:block; margin:0 0 7px; font-size:12px; font-weight:700; color:#39434c; }
.field input, .field textarea, .review-block textarea, .notes { width:100%; border:1px solid #aeb5ba; border-radius:4px; padding:9px 10px; background:white; }
.field input:focus, textarea:focus, select:focus { outline:2px solid #8eb8ae; outline-offset:1px; border-color:var(--focus); }
textarea { min-height:78px; resize:vertical; line-height:1.5; }
.logic-text { min-height:58px; }
.review-block { border-top:1px solid #e4e7e9; padding:15px 0 2px; margin:0; }
.review-block:first-of-type { border-top:0; }
pre.readonly { margin:0; padding:11px; overflow:auto; background:#f2f3f4; border:1px solid var(--line); border-radius:4px; white-space:pre-wrap; }
table { border-collapse:collapse; width:100%; margin-top:6px; font-size:12px; }
th, td { border:1px solid var(--line); padding:6px; text-align:left; vertical-align:top; }
th { background:#f1f2f3; }
td input { width:100%; min-width:90px; border:1px solid #b9c0c4; border-radius:3px; padding:6px; }
.status-control { display:grid; grid-template-columns:1fr 1fr; border:1px solid var(--line); border-radius:5px; overflow:hidden; margin-bottom:14px; }
.status-control button { min-height:36px; border:0; border-right:1px solid var(--line); border-bottom:1px solid var(--line); background:#f7f8f8; padding:6px; font-size:12px; }
.status-control button.active { background:#dcebe7; color:#174c40; font-weight:700; }
.status-control button[data-status="needs_revision"].active { background:#fff0c9; color:#684500; }
.status-control button[data-status="rejected"].active { background:#f8dddd; color:#722622; }
.inspector section { margin-bottom:20px; }
.inspector ul { margin:6px 0; padding-left:18px; font-size:12px; }
.inspector .secondary { width:100%; border:1px solid #aeb5ba; background:white; border-radius:4px; padding:7px; }
.warning { padding:9px; border-left:3px solid var(--warn); background:#fff8e6; font-size:12px; margin-bottom:8px; }
.empty-state { padding:40px 20px; color:var(--muted); text-align:center; }
.toast { position:fixed; right:18px; bottom:18px; max-width:420px; padding:10px 14px; background:#20262c; color:white; border-radius:5px; box-shadow:0 4px 14px #0003; z-index:10; }
.hidden { display:none !important; }
@media (max-width: 980px) { .workspace { grid-template-columns:240px minmax(480px,1fr); }.inspector { grid-column:1 / -1; border-left:0; border-top:1px solid var(--line); }.workspace { overflow:auto; }.sidebar,.editor,.inspector { overflow:visible; } }
@media (max-width: 700px) { .topbar { height:auto; min-height:58px; flex-wrap:wrap; padding:10px; }.topbar .meta { width:100%; order:2; }.workspace { height:auto; display:block; }.sidebar { max-height:360px; overflow:auto; }.editor { padding:16px; }.inspector { border-top:1px solid var(--line); }.command { min-height:36px; } }
</style>
</head>
<body>
<header class="topbar">
  <h1>AutoDocGen 人工审查</h1>
  <span class="meta" id="projectMeta"></span>
  <button class="command" id="importBtn" type="button">导入决策</button>
  <button class="command" id="approveCleanBtn" type="button">通过无警告项</button>
  <button class="command primary" id="exportBtn" type="button">导出决策</button>
  <input class="hidden" id="importFile" type="file" accept="application/json,.json">
</header>
<div class="workspace">
  <aside class="sidebar">
    <div class="filters">
      <input id="searchInput" type="search" placeholder="搜索函数或文件">
      <select id="statusFilter">
        <option value="all">全部函数</option>
        <option value="manual">待人工修改</option>
        <option value="pending">待审查</option>
        <option value="approved">已通过</option>
        <option value="needs_revision">待修改</option>
        <option value="rejected">已驳回</option>
      </select>
      <div class="summary-strip" id="summaryStrip"></div>
    </div>
    <div class="function-list" id="functionList"></div>
  </aside>
  <main class="editor" id="editor">__INITIAL__</main>
  <aside class="inspector">
    <section>
      <h2>审查状态</h2>
      <div class="status-control" id="statusControl">
        <button type="button" data-status="pending">待审查</button>
        <button type="button" data-status="approved">通过</button>
        <button type="button" data-status="needs_revision">待修改</button>
        <button type="button" data-status="rejected">驳回</button>
      </div>
      <label for="reviewNotes"><h3>审查备注</h3></label>
      <textarea class="notes" id="reviewNotes"></textarea>
    </section>
    <section>
      <h2>质量信息</h2>
      <div id="qualityPanel"><ul>__WARNINGS__</ul></div>
    </section>
    <section>
      <button class="secondary" id="resetCurrentBtn" type="button">撤销当前函数修改</button>
    </section>
    <section class="meta"><a href="review_bundle.json">review_bundle.json</a></section>
  </aside>
</div>
<div class="toast hidden" id="toast" role="status"></div>
<script id="reviewData" type="application/json">__DATA__</script>
<script>
(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('reviewData').textContent);
  const bundle = payload.bundle || {};
  const functions = Array.isArray(bundle.functions) ? bundle.functions : [];
  const byKey = Object.fromEntries(functions.map(fn => [fn.review_key, fn]));
  const storageKey = `autodoc-review-v1:${payload.bundle_fingerprint}`;
  const decisions = {};
  let selectedKey = functions[0]?.review_key || '';

  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const blocksOf = (fn, kind) => (fn?.blocks || []).filter(block => block.kind === kind);
  const baseline = fn => ({
    source_file: fn.source_file || '',
    function: fn.name || fn.function_id || '',
    source_hash: fn.source_hash || '',
    status: 'pending',
    notes: '',
    title: fn.title || fn.name || '',
    description: blocksOf(fn, 'summary')[0]?.text || '',
    return_desc: blocksOf(fn, 'return')[0]?.text || '',
    io_elements: structuredClone(blocksOf(fn, 'io_table')[0]?.rows || []),
    local_elements: structuredClone(blocksOf(fn, 'local_table')[0]?.rows || []),
    logic_lines: blocksOf(fn, 'logic_line').map(block => block.text || '')
  });
  const current = fn => decisions[fn.review_key] || baseline(fn);
  const ensure = fn => {
    if (!decisions[fn.review_key]) decisions[fn.review_key] = {...baseline(fn), touched:true};
    decisions[fn.review_key].touched = true;
    return decisions[fn.review_key];
  };
  const hasManual = fn => current(fn).logic_lines.some(line => String(line).includes('待人工修改'));
  const hasWarnings = fn => (fn.blocks || []).some(block => (block.quality_flags || []).length) || hasManual(fn);
  const shortPath = value => {
    const root = String(bundle.project_root || '').replace(/\\/g, '/').replace(/\/$/, '');
    const path = String(value || '').replace(/\\/g, '/');
    return root && path.startsWith(root + '/') ? path.slice(root.length + 1) : path;
  };

  function persist() {
    const data = {schema_version:1, bundle_fingerprint:payload.bundle_fingerprint, functions:decisions};
    try { localStorage.setItem(storageKey, JSON.stringify(data)); } catch (_) {}
  }
  function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (saved?.schema_version === 1 && saved.bundle_fingerprint === payload.bundle_fingerprint) {
        for (const [key, value] of Object.entries(saved.functions || {})) {
          if (byKey[key] && value && typeof value === 'object') decisions[key] = value;
        }
      }
    } catch (_) {}
  }
  function toast(message) {
    el('toast').textContent = message;
    el('toast').classList.remove('hidden');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => el('toast').classList.add('hidden'), 2400);
  }
  function statusCounts() {
    const counts = {pending:0, approved:0, needs_revision:0, rejected:0, manual:0};
    for (const fn of functions) {
      const status = current(fn).status || 'pending';
      counts[status] = (counts[status] || 0) + 1;
      if (hasManual(fn)) counts.manual += 1;
    }
    return counts;
  }
  function filteredFunctions() {
    const query = el('searchInput').value.trim().toLowerCase();
    const filter = el('statusFilter').value;
    return functions.filter(fn => {
      const decision = current(fn);
      if (filter === 'manual' && !hasManual(fn)) return false;
      if (!['all','manual'].includes(filter) && decision.status !== filter) return false;
      if (!query) return true;
      return [fn.name, fn.title, fn.source_file].some(value => String(value || '').toLowerCase().includes(query));
    });
  }
  function renderSummary() {
    const counts = statusCounts();
    el('summaryStrip').innerHTML = [
      `函数 ${functions.length}`,
      `待改 ${counts.manual}`,
      `通过 ${counts.approved}`,
      `待修改 ${counts.needs_revision}`,
      `驳回 ${counts.rejected}`
    ].map(text => `<span>${esc(text)}</span>`).join('');
  }
  function renderList() {
    const rows = filteredFunctions();
    el('functionList').innerHTML = rows.map(fn => {
      const decision = current(fn);
      return `<button type="button" class="function-item ${fn.review_key === selectedKey ? 'active' : ''}" data-function-key="${esc(fn.review_key)}">
        <span class="function-row"><span class="status-dot ${esc(decision.status)}"></span><span class="function-name">${esc(decision.title || fn.title || fn.name)}</span></span>
        <span class="function-path">${esc(shortPath(fn.source_file))}</span>
      </button>`;
    }).join('') || '<div class="empty-state">无匹配函数</div>';
  }
  function renderTable(rows, tableKind) {
    if (!rows.length) return '';
    const local = tableKind === 'local_elements';
    return `<table><thead><tr><th>标识符</th><th>中文名称</th><th>C 类型</th><th>方向</th>${local ? '<th>用途</th>' : ''}</tr></thead><tbody>` + rows.map((row, index) => `
      <tr><td>${esc(row.ident || '')}</td><td><input data-table="${tableKind}" data-row="${index}" data-col="name" value="${esc(row.name || '')}"></td><td>${esc(row.c_type || '')}</td><td>${esc(row.direction || '')}</td>${local ? `<td><input data-table="${tableKind}" data-row="${index}" data-col="usage" value="${esc(row.usage || '')}"></td>` : ''}</tr>`).join('') + '</tbody></table>';
  }
  function renderEditor() {
    const fn = byKey[selectedKey];
    if (!fn) { el('editor').innerHTML = '<div class="empty-state">选择函数开始审查</div>'; return; }
    const decision = current(fn);
    const blocks = fn.blocks || [];
    const content = blocks.map(block => {
      if (block.kind === 'summary') return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="summary"><h3>功能说明</h3><textarea data-field="description">${esc(decision.description)}</textarea></article>`;
      if (block.kind === 'prototype') return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="prototype"><h3>函数原型</h3><pre class="readonly">${esc(block.text || '')}</pre></article>`;
      if (block.kind === 'return') return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="return"><h3>返回值</h3><pre class="readonly">${esc(decision.return_desc)}</pre></article>`;
      if (block.kind === 'io_table') return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="io_table"><h3>输入输出参数</h3>${renderTable(decision.io_elements || [], 'io_elements')}</article>`;
      if (block.kind === 'local_table') return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="local_table"><h3>局部变量</h3>${renderTable(decision.local_elements || [], 'local_elements')}</article>`;
      if (block.kind === 'logic_line') {
        const logicBlocks = blocksOf(fn, 'logic_line');
        const index = logicBlocks.findIndex(item => item.block_id === block.block_id);
        return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="logic_line"><h3>${esc(block.title || `逻辑 ${index + 1}`)}</h3><textarea class="logic-text" data-logic-index="${index}">${esc(decision.logic_lines[index] || '')}</textarea></article>`;
      }
      return `<article class="review-block" data-block-id="${esc(block.block_id)}" data-kind="${esc(block.kind)}"><h3>${esc(block.title || block.kind)}</h3><pre class="readonly">${esc(block.text || '')}</pre></article>`;
    }).join('');
    el('editor').innerHTML = `<header class="function-header"><h2>${esc(fn.name || fn.function_id)}</h2><p class="meta">${esc(shortPath(fn.source_file))} · ${esc(fn.source_hash || '')}</p></header>
      <div class="field"><label for="titleInput">函数标题</label><input id="titleInput" data-field="title" value="${esc(decision.title || '')}"></div>${content}`;
  }
  function renderInspector() {
    const fn = byKey[selectedKey];
    if (!fn) return;
    const decision = current(fn);
    for (const button of el('statusControl').querySelectorAll('button')) button.classList.toggle('active', button.dataset.status === decision.status);
    el('reviewNotes').value = decision.notes || '';
    const flags = [...(bundle.quality_flags || []), ...(fn.blocks || []).flatMap(block => block.quality_flags || [])];
    const items = [];
    if (hasManual(fn)) items.push('<div class="warning">包含待人工修改逻辑</div>');
    for (const flag of flags) items.push(`<div class="warning"><strong>${esc(flag.severity || 'info')}</strong> ${esc(flag.message || flag.code || '')}</div>`);
    if (decision.stale) items.push('<div class="warning">源码哈希不一致，决策已过期</div>');
    el('qualityPanel').innerHTML = items.join('') || '<div class="meta">无质量警告</div>';
  }
  function renderAll() { renderSummary(); renderList(); renderEditor(); renderInspector(); }

  el('functionList').addEventListener('click', event => {
    const button = event.target.closest('[data-function-key]');
    if (!button) return;
    selectedKey = button.dataset.functionKey;
    renderAll();
  });
  for (const id of ['searchInput','statusFilter']) {
    el(id).addEventListener('input', () => { renderSummary(); renderList(); });
    el(id).addEventListener('change', () => { renderSummary(); renderList(); });
  }
  el('editor').addEventListener('input', event => {
    const fn = byKey[selectedKey];
    if (!fn) return;
    const decision = ensure(fn);
    const target = event.target;
    if (target.dataset.field) decision[target.dataset.field] = target.value;
    if (target.dataset.logicIndex !== undefined) decision.logic_lines[Number(target.dataset.logicIndex)] = target.value;
    if (target.dataset.table) {
      const rows = decision[target.dataset.table];
      const row = rows?.[Number(target.dataset.row)];
      if (row) row[target.dataset.col] = target.value;
    }
    persist();
  });
  el('editor').addEventListener('change', event => {
    if (event.target.dataset.field === 'title') { renderList(); renderSummary(); }
  });
  el('statusControl').addEventListener('click', event => {
    const button = event.target.closest('[data-status]');
    const fn = byKey[selectedKey];
    if (!button || !fn) return;
    ensure(fn).status = button.dataset.status;
    persist(); renderSummary(); renderList(); renderInspector();
  });
  el('reviewNotes').addEventListener('input', event => {
    const fn = byKey[selectedKey]; if (!fn) return;
    ensure(fn).notes = event.target.value; persist();
  });
  el('resetCurrentBtn').addEventListener('click', () => {
    if (!selectedKey) return;
    delete decisions[selectedKey]; persist(); renderAll(); toast('已撤销当前函数修改');
  });
  el('approveCleanBtn').addEventListener('click', () => {
    let count = 0;
    for (const fn of functions) {
      if (!hasWarnings(fn)) { ensure(fn).status = 'approved'; count += 1; }
    }
    persist(); renderAll(); toast(`已通过 ${count} 个无警告函数`);
  });
  function exportDecisions() {
    // Only export human-touched decisions (edited/status-changed/imported).
    // Untouched baseline functions stay out of the file.
    const clean = {};
    for (const [key, value] of Object.entries(decisions)) {
      if (!value || !value.touched) continue;
      const copy = structuredClone(value); delete copy.touched; delete copy.stale; clean[key] = copy;
    }
    const result = {
      schema_version:1,
      decision_kind:'generation_review',
      generated_at:new Date().toISOString(),
      source_bundle:'review_bundle.json',
      bundle_fingerprint:payload.bundle_fingerprint,
      project_root:bundle.project_root || '',
      output_docx:bundle.output_docx || '',
      functions:clean
    };
    const blob = new Blob([JSON.stringify(result, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'generation_review_decisions.json'; anchor.click(); URL.revokeObjectURL(url);
    toast(`已导出 ${Object.keys(clean).length} 个已修改函数决策`);
  }
  el('exportBtn').addEventListener('click', exportDecisions);
  el('importBtn').addEventListener('click', () => el('importFile').click());
  el('importFile').addEventListener('change', event => {
    const file = event.target.files?.[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const incoming = JSON.parse(String(reader.result || ''));
        if (incoming.schema_version !== 1 || typeof incoming.functions !== 'object') throw new Error('决策文件格式不正确');
        let count = 0;
        for (const [key, value] of Object.entries(incoming.functions || {})) {
          const fn = byKey[key]; if (!fn || !value || typeof value !== 'object') continue;
          decisions[key] = structuredClone(value);
          decisions[key].touched = true;
          decisions[key].stale = Boolean(value.source_hash && value.source_hash !== fn.source_hash);
          count += 1;
        }
        persist(); renderAll(); toast(`已导入 ${count} 个函数决策`);
      } catch (error) { toast(`导入失败：${error.message}`); }
      event.target.value = '';
    };
    reader.readAsText(file, 'utf-8');
  });

  restore();
  el('projectMeta').textContent = `${functions.length} 个函数 · ${bundle.project_root || ''}`;
  renderAll();
})();
</script>
</body>
</html>
"""
    return (
        template.replace("__INITIAL__", initial)
        .replace("__WARNINGS__", bundle_warnings)
        .replace("__DATA__", embedded)
    )


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
