"""Design workspace: export/import generated designs for human or AI review.

After generation completes, the full design for every function is exported to a
JSON file that serves three purposes:
  1. Human review — edit names/usages/logic lines directly in JSON
  2. AI review   — feed LSP facts + code context to an auditor
  3. Round-trip  — convert approved edits back to revision_profile.json

Schema (v2):
  {
    "schema_version": 2,
    "project_root": "...",
    "generated_at": "ISO-8601",
    "output_docx": "...",
    "functions": {
      "file.c::funcName": {
        "source_file": "...",
        "func_name": "...",
        "req_id": "D/R_SDD01_001",
        "title": "...",
        "description": "...",
        "prototype": "...",
        "io_elements": [{"ident":"...","name":"...","c_type":"...","direction":"..."}],
        "local_elements": [{"ident":"...","name":"...","c_type":"...","usage":"..."}],
        "logic_lines": ["...", "..."],
        "lsp_facts": {"type_facts":{}, "member_facts":[], ...},
        "review_status": "pending",   # pending|approved|rejected
        "review_notes": "",
        "review_suggestions": []
      }
    }
  }
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Sequence


SCHEMA_VERSION = 2


def _safe_str(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _element_to_dict(elem: Any) -> dict[str, str]:
    """Convert IOElement/LocalDataElement to a plain dict."""
    if isinstance(elem, dict):
        return {
            "ident": _safe_str(elem.get("ident")),
            "name": _safe_str(elem.get("name")),
            "c_type": _safe_str(elem.get("c_type") or elem.get("type")),
            "direction": _safe_str(elem.get("direction")),
            "usage": _safe_str(elem.get("usage")),
        }
    if is_dataclass(elem):
        d = asdict(elem)
        return {k: _safe_str(v) for k, v in d.items()}
    return {}


def _design_to_function_entry(
    design: Any,
    task: dict[str, Any],
    lsp_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a FunctionDesign + task to a workspace function entry."""
    func_name = _safe_str(task.get("func_name")) or _safe_str(getattr(design, "title", ""))
    source_file = _safe_str(task.get("source_file"))
    func_key = f"{os.path.basename(source_file)}::{func_name}" if source_file else func_name

    io_elements = []
    for elem in (getattr(design, "io_elements", None) or []):
        d = _element_to_dict(elem)
        if d.get("ident") or d.get("name"):
            io_elements.append(d)

    local_elements = []
    for elem in (getattr(design, "local_elements", None) or []):
        d = _element_to_dict(elem)
        if d.get("ident") or d.get("name"):
            local_elements.append(d)

    desc_lines = getattr(design, "description_lines", None) or ()
    description = "\n".join(str(line) for line in desc_lines if str(line).strip())

    return {
        "source_file": source_file,
        "func_name": func_name,
        "req_id": _safe_str(getattr(design, "req_id", "")),
        "title": _safe_str(getattr(design, "title", "")),
        "description": description,
        "prototype": _safe_str(getattr(design, "prototype", "")),
        "io_elements": io_elements,
        "local_elements": local_elements,
        "logic_lines": [str(line) for line in (getattr(design, "logic_lines", None) or []) if str(line).strip()],
        "lsp_facts": dict(lsp_facts or {}),
        "review_status": "pending",
        "review_notes": "",
        "review_suggestions": [],
    }


def build_workspace_bundle(
    designs_with_tasks: Sequence[tuple[Any, dict[str, Any]]],
    *,
    project_root: str = "",
    output_docx: str = "",
    lsp_facts_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a workspace bundle dict from a list of (design, task) pairs."""
    functions: dict[str, dict[str, Any]] = {}
    lsp_map = lsp_facts_map or {}

    for design, task in designs_with_tasks:
        if design is None:
            continue
        entry = _design_to_function_entry(design, task)
        func_key = f"{os.path.basename(entry['source_file'])}::{entry['func_name']}" if entry["source_file"] else entry["func_name"]
        # Attach LSP facts if available
        lsp_key = f"{entry['source_file']}::{entry['func_name']}"
        entry["lsp_facts"] = lsp_map.get(lsp_key, {})
        functions[func_key] = entry

    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": _safe_str(project_root),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_docx": _safe_str(output_docx),
        "functions": functions,
    }


def write_workspace(bundle: dict[str, Any], path: str, *, merge_existing: bool = True) -> str:
    """Write workspace bundle to JSON, optionally merging with existing file.

    Merge preserves human edits (review_status, review_notes, review_suggestions)
    for functions that already exist in the existing workspace.
    """
    target = os.path.abspath(path)
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)

    if merge_existing and os.path.exists(target):
        try:
            with open(target, encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict) and existing.get("functions"):
                _merge_workspace(existing, bundle)
        except Exception:
            pass

    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


def _merge_workspace(existing: dict[str, Any], current: dict[str, Any]) -> None:
    """Merge: current (newly generated) overwrites design fields, but preserves
    human review edits from existing when the function still exists."""
    existing_funcs = existing.get("functions") or {}
    current_funcs = current.get("functions") or {}
    for key, new_entry in current_funcs.items():
        old_entry = existing_funcs.get(key)
        if not old_entry:
            continue
        # Preserve human edits
        for field in ("review_status", "review_notes", "review_suggestions"):
            if old_entry.get(field):
                new_entry[field] = old_entry[field]
        # If human modified title/description/logic, preserve those too
        # (detect by review_status == "approved")
        if old_entry.get("review_status") == "approved":
            for field in ("title", "description", "io_elements", "local_elements", "logic_lines"):
                if old_entry.get(field):
                    new_entry[field] = old_entry[field]


def load_workspace(path: str) -> dict[str, Any]:
    """Load a workspace JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def workspace_to_revision_profile(workspace: dict[str, Any]) -> dict[str, Any]:
    """Convert approved functions in a workspace to a revision_profile.

    Only functions with review_status == "approved" are included.
    The revision_profile format is consumed by autodoc/revision.py.
    """
    functions: dict[str, Any] = {}
    for key, entry in (workspace.get("functions") or {}).items():
        if entry.get("review_status") != "approved":
            continue
        source_file = _safe_str(entry.get("source_file"))
        func_name = _safe_str(entry.get("func_name"))

        patch: dict[str, Any] = {}

        # Title override
        title = _safe_str(entry.get("title"))
        if title:
            patch["function_name"] = title

        # Description override
        desc = _safe_str(entry.get("description"))
        if desc:
            patch["description"] = desc

        # Locked names: io_elements + local_elements
        locked: dict[str, dict[str, str]] = {}
        for elem in (entry.get("io_elements") or []):
            ident = _safe_str(elem.get("ident"))
            name = _safe_str(elem.get("name"))
            if ident and name:
                locked[ident] = {"display": name}
        for elem in (entry.get("local_elements") or []):
            ident = _safe_str(elem.get("ident"))
            name = _safe_str(elem.get("name"))
            usage = _safe_str(elem.get("usage"))
            if ident and name:
                locked[ident] = {"display": name}
                if usage:
                    locked[ident]["usage"] = usage
        if locked:
            patch["locked_names"] = locked

        # Logic line replacements
        logic_lines = entry.get("logic_lines") or []
        if logic_lines:
            patch["logic_lines"] = list(logic_lines)

        if patch:
            patch["function"] = func_name
            patch["file"] = source_file
            functions[key] = patch

    return {
        "functions": functions,
    }


__all__ = [
    "SCHEMA_VERSION",
    "build_workspace_bundle",
    "write_workspace",
    "load_workspace",
    "workspace_to_revision_profile",
]
