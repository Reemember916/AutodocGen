"""Failed-function retry API for AutoDocGen backend.

UI can call ``run_retry_generation`` later; this module is CLI- and
test-first and does not import ``qt_gui``.

Contract for GUI (func_failure events)::

    failures = [
      {
        "func_name": "...",
        "file_path": "...",
        "error_type": "...",
        "error_message": "...",
        "task": { ... optional, may have stripped file_context ... },
      },
      ...
    ]

    from autodoc.retry import run_retry_generation
    result = run_retry_generation(
        failures=failures,
        output="out.docx",
        cfg=gen_config,
        c_file="path/to/file.c",      # or project_dir=
        merge=False,                  # True: overwrite output in place after rebuild
    )
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


def _safe_strip(value: Any) -> str:
    return str(value or "").strip()


def _cfg_get(cfg: Any, name: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(name, default)
    return getattr(cfg, name, default)


def load_failures(path: str) -> list[dict]:
    """Load failures list from JSON file (list or {failures: [...]})."""
    file_path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    with open(file_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("failures") or data.get("items") or []
        return [item for item in items if isinstance(item, dict)]
    return []


def normalize_failure_records(failures: Sequence[dict]) -> list[dict]:
    """Normalize heterogeneous failure payloads into a stable list of dicts."""
    out: list[dict] = []
    for raw in failures or []:
        if not isinstance(raw, dict):
            continue
        task = dict(raw.get("task") or {})
        func_data = dict(task.get("func_data") or {})
        func_info = dict(func_data.get("func_info") or {})
        func_name = (
            _safe_strip(raw.get("func_name"))
            or _safe_strip(task.get("func_name"))
            or _safe_strip(func_info.get("func_name"))
            or _safe_strip(func_data.get("func_name"))
        )
        file_path = (
            _safe_strip(raw.get("file_path"))
            or _safe_strip(raw.get("file"))
            or _safe_strip(task.get("source_file"))
            or _safe_strip(task.get("file"))
            or _safe_strip((func_data.get("file_context") or {}).get("source_file"))
        )
        if not func_name:
            continue
        body = _safe_strip(func_data.get("body"))
        has_body = bool(body)
        out.append(
            {
                "func_name": func_name,
                "file_path": file_path,
                "error_type": _safe_strip(raw.get("error_type")) or "unknown",
                "error_message": _safe_strip(raw.get("error_message")),
                "task": task,
                "has_body": has_body,
            }
        )
    return out


def _task_has_usable_func_data(task: dict) -> bool:
    func_data = dict((task or {}).get("func_data") or {})
    if not func_data:
        return False
    body = _safe_strip(func_data.get("body"))
    if not body:
        return False
    # Stripped file_context still OK for rebuild if body present
    return True


def _prepare_func_entries(source_file: str, cfg: Any, project_root: str = "") -> list[dict]:
    from . import parse as parse_utils

    try:
        func_list, _meta = parse_utils.prepare_func_list_for_c_file(
            source_file,
            project_root=project_root or "",
            cfg=cfg,
            prefilter=False,
        )
    except TypeError:
        # Older signature fallback via backend
        from ._legacy_support import legacy_backend

        backend = legacy_backend()
        func_list, _meta = backend.prepare_func_list_for_c_file(
            source_file, project_root=project_root or "", cfg=cfg, prefilter=False
        )
    return list(func_list or [])


def _find_func_data(entries: Sequence[dict], func_name: str) -> Optional[dict]:
    target = _safe_strip(func_name)
    if not target:
        return None
    for entry in entries:
        info = dict((entry or {}).get("func_info") or {})
        name = _safe_strip(info.get("func_name")) or _safe_strip((entry or {}).get("func_name"))
        if name == target:
            return dict(entry)
    # Case-insensitive fallback
    target_l = target.lower()
    for entry in entries:
        info = dict((entry or {}).get("func_info") or {})
        name = _safe_strip(info.get("func_name")) or _safe_strip((entry or {}).get("func_name"))
        if name.lower() == target_l:
            return dict(entry)
    return None


def rebuild_tasks_from_failures(
    failures: Sequence[dict],
    cfg: Any,
    *,
    c_file: str = "",
    project_dir: str = "",
    module_req_prefix: str = "",
) -> list[dict]:
    """
    Rebuild generation tasks from failure records.

    Strategy:
    1. Prefer embedded task.func_data when body is present.
    2. Otherwise re-parse C file (failure.file_path or c_file) and match by name.
    """
    normalized = normalize_failure_records(failures)
    prefix = _safe_strip(module_req_prefix) or _safe_strip(_cfg_get(cfg, "req_id_prefix", "D/R_SDD01_"))
    default_c = os.path.abspath(os.path.expanduser(c_file)) if c_file else ""
    root = os.path.abspath(os.path.expanduser(project_dir)) if project_dir else ""

    # Cache parse results per file
    parse_cache: dict[str, list[dict]] = {}
    tasks: list[dict] = []
    index = 1

    for failure in normalized:
        task = dict(failure.get("task") or {})
        func_name = failure["func_name"]
        source = (
            _safe_strip(task.get("source_file"))
            or failure["file_path"]
            or default_c
        )
        if source:
            source = os.path.abspath(os.path.expanduser(source))

        func_data = None
        if _task_has_usable_func_data(task):
            func_data = dict(task.get("func_data") or {})
            # Ensure source_file in file_context for downstream
            fc = dict(func_data.get("file_context") or {})
            if source and not fc.get("source_file"):
                fc["source_file"] = source
                func_data["file_context"] = fc
        else:
            if not source or not os.path.isfile(source):
                raise FileNotFoundError(
                    f"无法重建函数 {func_name}：缺少可用 body 且源文件不存在：{source or '(empty)'}"
                )
            if source not in parse_cache:
                parse_cache[source] = _prepare_func_entries(source, cfg, project_root=root)
            func_data = _find_func_data(parse_cache[source], func_name)
            if func_data is None:
                raise LookupError(f"源文件中未找到函数：{func_name} @ {source}")

        built = {
            "index": int(task.get("index") or index),
            "func_pos": int(task.get("func_pos") or index),
            "func_name": func_name,
            "source_file": source or default_c,
            "module_req_prefix": _safe_strip(task.get("module_req_prefix")) or prefix,
            "func_data": func_data,
            "retry_of": {
                "error_type": failure.get("error_type"),
                "error_message": failure.get("error_message"),
            },
        }
        tasks.append(built)
        index += 1
    return tasks


def filter_tasks_by_failures(
    all_tasks: Sequence[dict],
    failures: Sequence[dict],
) -> list[dict]:
    """Keep only tasks whose func_name appears in failures (optional helper)."""
    names = {f["func_name"] for f in normalize_failure_records(failures)}
    if not names:
        return []
    return [t for t in all_tasks if _safe_strip((t or {}).get("func_name")) in names]


@dataclass
class RetryResult:
    """Outcome of a retry batch."""

    ok: bool
    output_path: str
    retried: list[str] = field(default_factory=list)
    still_failed: list[dict] = field(default_factory=list)
    designs: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "output_path": self.output_path,
            "retried": list(self.retried),
            "still_failed": list(self.still_failed),
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


def _emit(cfg: Any, event: dict) -> None:
    try:
        from ._legacy_support import legacy_backend

        backend = legacy_backend()
        backend.gui_event(cfg, event)
    except Exception:
        pass


def run_retry_generation(
    failures: Sequence[dict],
    output: str,
    cfg: Any,
    *,
    c_file: str = "",
    project_dir: str = "",
    merge: bool = False,
    module_req_prefix: str = "",
    backend_module=None,
    render_module=None,
) -> RetryResult:
    """
    Rebuild designs for failed functions and write a docx.

    Parameters
    ----------
    failures :
        List of failure dicts (same shape as GUI ``func_failure`` / failures.json).
    output :
        Target .docx path.
    cfg :
        GenConfig-like object. AI should usually be off for deterministic tests.
    c_file / project_dir :
        Used when failure records lack file_path or body.
    merge :
        If True and output exists, still regenerate a fresh doc for the retry set
        (full document merge of arbitrary CSU sections is left to UI regen APIs).
        The flag is accepted for API compatibility; content is always the retry set.
    """
    from ._legacy_support import legacy_backend
    from . import pipeline as pipeline_utils

    backend = backend_module or legacy_backend()
    if render_module is None:
        from . import render as render_module

    out_path = os.path.abspath(os.path.expanduser(str(output or "").strip()))
    tasks = rebuild_tasks_from_failures(
        failures,
        cfg,
        c_file=c_file,
        project_dir=project_dir,
        module_req_prefix=module_req_prefix,
    )
    if not tasks:
        return RetryResult(ok=False, output_path=out_path, errors=["no retryable failures"])

    _emit(
        cfg,
        {
            "type": "retry_batch_start",
            "count": len(tasks),
            "functions": [t.get("func_name") for t in tasks],
            "output": out_path,
            "merge": bool(merge),
        },
    )

    try:
        out_path = backend.normalize_docx_output_path(out_path, ensure_parent_dir=True)
    except Exception as exc:
        return RetryResult(ok=False, output_path=out_path, errors=[f"invalid output: {exc}"])

    # merge flag reserved for UI in-place regen; retry always rebuilds a focused doc.
    _ = merge
    try:
        doc_state = render_module.init_generation_document(
            cfg,
            main_heading="失败函数重试",
            heading_level=1,
            backend_module=backend,
        )
        doc = doc_state["doc"] if isinstance(doc_state, dict) else doc_state
    except Exception:
        try:
            doc = render_module.init_document(cfg)
        except Exception:
            from docx import Document

            doc = Document()

    retried: list[str] = []
    still_failed: list[dict] = []
    designs: list[Any] = []
    errors: list[str] = []

    for task in tasks:
        name = _safe_strip(task.get("func_name"))
        try:
            design = pipeline_utils.run_function_design_task(task, cfg, backend_module=backend)
            render_module.render_function_design(doc, design, cfg)
            designs.append(design)
            retried.append(name)
            _emit(
                cfg,
                {
                    "type": "func_end",
                    "func_name": name,
                    "ok": True,
                    "retry": True,
                },
            )
        except Exception as exc:
            err = str(exc)
            errors.append(f"{name}: {err}")
            still_failed.append(
                {
                    "func_name": name,
                    "file_path": task.get("source_file"),
                    "error_type": type(exc).__name__,
                    "error_message": err[:200],
                    "task": {
                        "func_name": name,
                        "source_file": task.get("source_file"),
                        "index": task.get("index"),
                    },
                }
            )
            _emit(
                cfg,
                {
                    "type": "func_failure",
                    "func_name": name,
                    "file": task.get("source_file"),
                    "error_type": type(exc).__name__,
                    "error_message": err[:200],
                    "task": still_failed[-1].get("task"),
                },
            )

    try:
        if hasattr(backend, "safe_save_docx"):
            backend.safe_save_docx(doc, out_path)
        else:
            render_module.safe_save_docx(doc, out_path)
    except Exception:
        try:
            doc.save(out_path)
        except Exception as exc:
            errors.append(f"save failed: {exc}")
            _emit(
                cfg,
                {
                    "type": "retry_batch_end",
                    "ok": False,
                    "retried": retried,
                    "still_failed": still_failed,
                    "output": out_path,
                },
            )
            return RetryResult(
                ok=False,
                output_path=out_path,
                retried=retried,
                still_failed=still_failed,
                designs=designs,
                errors=errors,
            )

    ok = not still_failed and not errors
    _emit(
        cfg,
        {
            "type": "retry_batch_end",
            "ok": ok,
            "retried": retried,
            "still_failed": still_failed,
            "output": out_path,
        },
    )
    return RetryResult(
        ok=ok,
        output_path=out_path,
        retried=retried,
        still_failed=still_failed,
        designs=designs,
        errors=errors,
    )


__all__ = [
    "RetryResult",
    "load_failures",
    "normalize_failure_records",
    "rebuild_tasks_from_failures",
    "filter_tasks_by_failures",
    "run_retry_generation",
]
