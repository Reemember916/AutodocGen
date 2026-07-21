"""Helpers for preparing compile_commands.json for local clangd sessions."""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

from ._legacy_support import app_root, legacy_backend
from . import utils


def _split_cfg_items(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).replace("\r", "\n")
    out: list[str] = []
    for chunk in text.replace(";", "\n").splitlines():
        for piece in chunk.split(","):
            item = piece.strip()
            if item:
                out.append(item)
    return out


def _resolve_path(path_text: str, *, project_root: str = "") -> str:
    text = str(path_text or "").strip()
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        return str(path)
    repo_root = Path(app_root())
    candidates = [
        repo_root / text,
        Path(project_root or "") / text if project_root else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate.resolve())
    if project_root:
        return str((Path(project_root) / text).resolve())
    return str((repo_root / text).resolve())


def _build_cache_dir(project_root: str) -> str:
    seed = os.path.abspath(project_root or "")
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / "autodocgen_lsp" / digest
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _cfg_project_root(cfg: Optional[Any], *, fallback: str = "") -> str:
    legacy = legacy_backend()
    value = utils.cfg_get_str(cfg, "project_root", "")
    if value:
        return value
    attr = getattr(cfg, "project_root", "")
    return str(attr or fallback)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _resolve_ccs_option_value(raw: str, *, project_root: str = "", project_name: str = "") -> str:
    """解析 TI CCS .cproject 中的 Eclipse CDT 变量。

    共享实现：compile_db.py 运行时和 convert_ccs_to_compile_commands.py
    预处理工具均使用此函数，避免代码重复。
    """
    text = html.unescape(str(raw or "")).strip().strip('"')
    if not text:
        return ""
    if not project_name:
        project_name = Path(project_root).name if project_root else ""
    replacements = {
        "${ProjName}": project_name,
        "${PROJECT_ROOT}": project_root,
        "${workspace_loc:/${ProjName}}": project_root,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    if text.startswith("${workspace_loc:/${ProjName}/") and text.endswith("}"):
        inner = text[len("${workspace_loc:/${ProjName}/") : -1]
        text = str(Path(project_root) / inner)
    elif text.startswith("${workspace_loc:/") and text.endswith("}"):
        inner = text[len("${workspace_loc:/") : -1]
        if "/" in inner:
            _, rel = inner.split("/", 1)
            text = str(Path(project_root) / rel)
    return text


def _load_ccs_project_settings(project_root: str, *, project_name: str = "") -> dict[str, list[str]]:
    """从 TI CCS ``.cproject`` XML 提取 include paths 和 defines。

    共享实现：compile_db.py 运行时和 convert_ccs_to_compile_commands.py
    预处理工具均使用此函数。``project_name`` 可显式传入覆盖推断值。
    """
    root = Path(project_root or "")
    cproject = root / ".cproject"
    if not cproject.exists():
        return {"include_paths": [], "defines": []}
    try:
        tree = ET.parse(cproject)
    except Exception:
        return {"include_paths": [], "defines": []}
    if not project_name:
        project_name = root.name
    include_paths: list[str] = []
    defines: list[str] = []
    for option in tree.findall(".//option"):
        option_id = str(option.get("id") or "")
        super_class = str(option.get("superClass") or "")
        option_name = str(option.get("name") or "")
        marker = " ".join([option_id, super_class, option_name]).upper()
        if "INCLUDE_PATH" in marker:
            for item in option.findall("./listOptionValue"):
                value = _resolve_ccs_option_value(item.get("value"), project_root=project_root, project_name=project_name)
                if value and "${CG_TOOL_ROOT}" not in value:
                    include_paths.append(value)
        elif any(key in marker for key in ("DEFINE", "PREDEFINED_SYMBOL", "DEFINED_SYMBOL")):
            for item in option.findall("./listOptionValue"):
                value = _resolve_ccs_option_value(item.get("value"), project_root=project_root, project_name=project_name)
                if value:
                    defines.append(value)
            direct_value = _resolve_ccs_option_value(option.get("value"), project_root=project_root, project_name=project_name)
            if direct_value and direct_value not in {"true", "false"}:
                defines.append(direct_value)
    return {
        "include_paths": _dedupe_keep_order(include_paths),
        "defines": _dedupe_keep_order(defines),
    }


def _collect_effective_lsp_flags(project_root: str, cfg: Optional[Any] = None) -> dict[str, list[str]]:
    legacy = legacy_backend()
    ccs = _load_ccs_project_settings(project_root)
    include_paths = _dedupe_keep_order(
        _split_cfg_items(utils.cfg_get_str(cfg, "logic_lsp_include_paths", "")) + list(ccs.get("include_paths") or [])
    )
    defines = _dedupe_keep_order(
        _split_cfg_items(utils.cfg_get_str(cfg, "logic_lsp_defines", "")) + list(ccs.get("defines") or [])
    )
    forced_includes = _split_cfg_items(utils.cfg_get_str(cfg, "logic_lsp_forced_includes", ""))
    return {
        "include_paths": include_paths,
        "defines": defines,
        "forced_includes": _dedupe_keep_order(forced_includes),
    }


def find_compile_commands(project_root: str) -> str:
    root = Path(project_root or "")
    if not root:
        return ""
    for current in [root] + list(root.parents):
        candidate = current / "compile_commands.json"
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def build_fallback_compile_command(source_file: str, cfg: Optional[Any] = None) -> dict[str, Any]:
    source_path = Path(source_file).resolve()
    project_root = _cfg_project_root(cfg, fallback=str(source_path.parent))
    directory = str(source_path.parent)
    effective_flags = _collect_effective_lsp_flags(project_root, cfg)
    include_flags: list[str] = []
    for item in effective_flags.get("include_paths") or []:
        include_flags.extend(["-I", _resolve_path(item, project_root=project_root)])
    define_flags: list[str] = []
    for item in effective_flags.get("defines") or []:
        define_flags.append(f"-D{item}")
    force_include_flags: list[str] = []
    legacy = legacy_backend()
    compat_header = _resolve_path(
        utils.cfg_get_str(cfg, "logic_lsp_compat_header", "tools/lsp/project_compat.h"),
        project_root=project_root,
    )
    if compat_header:
        force_include_flags.extend(["-include", compat_header])
    for item in effective_flags.get("forced_includes") or []:
        resolved = _resolve_path(item, project_root=project_root)
        if resolved:
            force_include_flags.extend(["-include", resolved])
    argv = ["clang", "-x", "c"] + define_flags + include_flags + force_include_flags + [str(source_path)]
    return {
        "directory": directory,
        "file": str(source_path),
        "arguments": argv,
    }


def ensure_compile_database(
    project_root: str,
    cfg: Optional[Any] = None,
    *,
    source_files: Optional[list[str]] = None,
) -> dict[str, Any]:
    existing = find_compile_commands(project_root)
    if existing:
        try:
            payload = json.loads(Path(existing).read_text(encoding="utf-8"))
        except Exception:
            payload = []
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return {
            "path": existing,
            "directory": str(Path(existing).resolve().parent),
            "entries": list(payload or []),
            "flags_hash": hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest(),
            "mode": "existing",
        }
    files = [str(Path(item).resolve()) for item in list(source_files or []) if str(item or "").strip()]
    if not files:
        return {"path": "", "directory": "", "entries": [], "flags_hash": "", "mode": "missing"}
    entries = [build_fallback_compile_command(item, cfg) for item in files]
    out_dir = _build_cache_dir(project_root or os.path.dirname(files[0]))
    out_path = Path(out_dir) / "compile_commands.json"
    out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True)
    return {
        "path": str(out_path),
        "directory": out_dir,
        "entries": entries,
        "flags_hash": hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest(),
        "mode": "generated",
    }


__all__ = ["build_fallback_compile_command", "ensure_compile_database", "find_compile_commands"]
