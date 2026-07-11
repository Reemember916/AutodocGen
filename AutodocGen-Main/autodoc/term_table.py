"""Project-level terminology table for stable symbol naming."""

from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from typing import Any, Optional, Sequence

from ._legacy_support import legacy_backend
from . import utils as utils_module


TERM_TABLE_FILENAME = "autodoc_term_table.json"
TERM_TABLE_VERSION = 2


_SOURCE_RANK = {
    "manual_locked": 100,
    "manual": 95,
    "symbol_dict": 92,
    "comment_prebuild": 84,
    "comment_rule": 76,
    "symbol_memory": 68,
    "ai": 64,
    "ai_func": 64,
    "ai_symbol": 64,
    "rule_guess": 42,
    "unknown": 0,
}


_SECTION_BY_KIND = {
    "function": "functions",
    "functions": "functions",
    "macro": "macros",
    "macros": "macros",
    "member": "members",
    "members": "members",
    "symbol": "symbols",
    "symbols": "symbols",
    "local": "symbols",
    "global": "symbols",
    "param": "symbols",
    "params": "symbols",
}


def default_term_table_path(project_root: str) -> str:
    root = os.path.abspath(os.path.expanduser(str(project_root or "").strip())) if project_root else ""
    if not root:
        return os.path.abspath(TERM_TABLE_FILENAME)
    return os.path.join(root, TERM_TABLE_FILENAME)


def normalize_term_record(record: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    if not isinstance(record, dict):
        record = {"cn": str(record or "").strip()}
    ident = utils_module._safe_strip(record.get("ident") or record.get("symbol") or record.get("name"))
    cn = utils_module._safe_strip(record.get("cn") or record.get("cn_name") or record.get("title"))
    if cn and (
        backend._looks_like_bad_canonical_name(cn, raw_ident=ident)
        or backend._looks_like_low_quality_symbol_cn(cn, raw_ident=ident)
    ):
        cn = ""
    try:
        confidence = float(record.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    aliases = []
    for item in record.get("aliases") or ():
        text = utils_module._safe_strip(item)
        if text and text != cn and text not in aliases:
            aliases.append(text)
    candidates = []
    for item in record.get("candidates") or ():
        if not isinstance(item, dict):
            item = {"cn": item}
        cand_cn = utils_module._safe_strip(item.get("cn") or item.get("cn_name") or item.get("title"))
        if not cand_cn or cand_cn == cn:
            continue
        if backend._looks_like_bad_canonical_name(cand_cn, raw_ident=ident) or backend._looks_like_low_quality_symbol_cn(cand_cn, raw_ident=ident):
            continue
        try:
            cand_confidence = float(item.get("confidence", 0.0) or 0.0)
        except Exception:
            cand_confidence = 0.0
        cand_source = utils_module._safe_strip(item.get("source") or "unknown")
        candidates.append(
            {
                "cn": cand_cn,
                "source": cand_source,
                "confidence": cand_confidence,
                "source_rank": int(item.get("source_rank") or _SOURCE_RANK.get(cand_source, 0)),
                "evidence": list(item.get("evidence") or ())[:8] if isinstance(item.get("evidence"), list) else [],
                "updated_at": utils_module._safe_strip(item.get("updated_at")),
            }
        )
    candidates.sort(key=lambda item: (-int(item.get("source_rank") or 0), -float(item.get("confidence") or 0.0), item.get("cn") or ""))
    source = utils_module._safe_strip(record.get("source") or "unknown")
    try:
        source_rank = int(record.get("source_rank") if record.get("source_rank") is not None else _SOURCE_RANK.get(source, 0))
    except Exception:
        source_rank = _SOURCE_RANK.get(source, 0)
    out = {
        "ident": ident,
        "cn": cn,
        "kind": utils_module._safe_strip(record.get("kind") or "symbols"),
        "source": source,
        "source_rank": source_rank,
        "confidence": confidence,
        "scope": utils_module._safe_strip(record.get("scope") or "project"),
        "internal": bool(record.get("internal", False)),
        "usage": utils_module._safe_strip(record.get("usage")),
        "evidence": list(record.get("evidence") or ())[:8] if isinstance(record.get("evidence"), list) else [],
        "aliases": aliases,
        "candidates": candidates[:8],
        "locked": bool(record.get("locked", False)),
    }
    if record.get("updated_at"):
        out["updated_at"] = utils_module._safe_strip(record.get("updated_at"))
    if record.get("confirmed_at"):
        out["confirmed_at"] = utils_module._safe_strip(record.get("confirmed_at"))
    return out


def normalize_term_table_payload(data: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    out = {"version": TERM_TABLE_VERSION, "functions": {}, "symbols": {}, "members": {}, "macros": {}}
    if not isinstance(data, dict):
        return out
    for section in ("functions", "symbols", "members", "macros"):
        part = data.get(section)
        if not isinstance(part, dict):
            continue
        for key, record in part.items():
            ident = utils_module._safe_strip(key)
            normalized = normalize_term_record(record, backend_module=backend)
            if not normalized.get("ident"):
                normalized["ident"] = ident
            if ident and normalized.get("cn"):
                normalized["kind"] = section
                out[section][ident] = normalized
    return out


def load_term_table(project_root: str, *, backend_module=None) -> tuple[str, dict[str, Any]]:
    backend = backend_module or legacy_backend()
    path = default_term_table_path(project_root)
    if not os.path.isfile(path):
        return path, normalize_term_table_payload({}, backend_module=backend)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    return path, normalize_term_table_payload(data, backend_module=backend)


def save_term_table(path: str, payload: dict[str, Any], *, backend_module=None) -> None:
    backend = backend_module or legacy_backend()
    normalized = normalize_term_table_payload(payload, backend_module=backend)
    normalized["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".autodoc_term_table_", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def flatten_term_table(payload: Optional[dict[str, Any]], *, backend_module=None) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    table = normalize_term_table_payload(payload or {}, backend_module=backend)
    flat: dict[str, str] = {}
    for section in ("functions", "symbols", "members", "macros"):
        for ident, record in (table.get(section) or {}).items():
            cn = utils_module._safe_strip((record or {}).get("cn"))
            if ident and cn:
                flat[ident] = cn
    return flat


def merge_term_record(
    payload: dict[str, Any],
    ident: str,
    cn: str,
    *,
    kind: str,
    source: str,
    confidence: float,
    usage: str = "",
    scope: str = "project",
    internal: bool = False,
    evidence: Optional[Sequence[str]] = None,
    locked: bool = False,
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    key = utils_module._safe_strip(ident)
    value = utils_module._safe_strip(cn)
    if not key or not value:
        return False
    if backend._looks_like_bad_canonical_name(value, raw_ident=key) or backend._looks_like_low_quality_symbol_cn(value, raw_ident=key):
        return False
    section = _SECTION_BY_KIND.get(utils_module._safe_strip(kind).lower(), "symbols")
    part = payload.setdefault(section, {})
    old = normalize_term_record(part.get(key) or {}, backend_module=backend)
    old_cn = utils_module._safe_strip(old.get("cn"))
    old_conf = float(old.get("confidence", 0.0) or 0.0)
    new_conf = float(confidence or 0.0)
    new_source = utils_module._safe_strip(source) or "unknown"
    new_rank = _SOURCE_RANK.get(new_source, 0)
    old_rank = int(old.get("source_rank") or _SOURCE_RANK.get(utils_module._safe_strip(old.get("source") or "unknown"), 0))
    now = datetime.datetime.now().isoformat(timespec="seconds")

    def _add_candidate(record: dict[str, Any], candidate_cn: str) -> dict[str, Any]:
        normalized = normalize_term_record(record, backend_module=backend)
        candidates = list(normalized.get("candidates") or [])
        if candidate_cn and candidate_cn != normalized.get("cn") and all((item or {}).get("cn") != candidate_cn for item in candidates):
            candidates.append(
                {
                    "cn": candidate_cn,
                    "source": new_source,
                    "confidence": new_conf,
                    "source_rank": new_rank,
                    "evidence": [utils_module._safe_strip(x) for x in (evidence or ()) if utils_module._safe_strip(x)][:8],
                    "updated_at": now,
                }
            )
            candidates.sort(key=lambda item: (-int(item.get("source_rank") or 0), -float(item.get("confidence") or 0.0), item.get("cn") or ""))
            normalized["candidates"] = candidates[:8]
        return normalized

    if old.get("locked") and old_cn:
        if old_cn != value:
            part[key] = _add_candidate(old, value)
            return True
        return False
    if old_cn and old_cn != value and (old_rank > new_rank or (old_rank == new_rank and old_conf > new_conf)):
        part[key] = _add_candidate(old, value)
        aliases = list(part[key].get("aliases") or [])
        if value not in aliases and new_rank >= 80:
            aliases.append(value)
            part[key]["aliases"] = aliases[:8]
        return True
    aliases = list(old.get("aliases") or [])
    if old_cn and old_cn != value and old_cn not in aliases:
        aliases.append(old_cn)
    ev = []
    for item in list(old.get("evidence") or ()) + list(evidence or ()):
        text = utils_module._safe_strip(item)
        if text and text not in ev:
            ev.append(text)
    part[key] = {
        "ident": key,
        "cn": value,
        "kind": section,
        "source": new_source,
        "source_rank": new_rank,
        "confidence": max(old_conf if old_cn == value else 0.0, new_conf),
        "scope": utils_module._safe_strip(scope) or utils_module._safe_strip(old.get("scope")) or "project",
        "internal": bool(internal or old.get("internal", False)),
        "usage": utils_module._safe_strip(usage) or utils_module._safe_strip(old.get("usage")),
        "evidence": ev[:8],
        "aliases": aliases[:8],
        "candidates": list(old.get("candidates") or ())[:8],
        "locked": bool(locked or old.get("locked", False)),
        "updated_at": now,
    }
    if locked or old.get("locked", False):
        part[key]["confirmed_at"] = utils_module._safe_strip(old.get("confirmed_at")) or now
    return True


def _iter_project_c_files(project_root: str, *, cfg: Any = None, backend_module=None) -> list[str]:
    backend = backend_module or legacy_backend()
    src_dir, app_files, mid_files, drv_files = backend.collect_project_c_files_by_layer(project_root, cfg or backend.GenConfig(), backend_module=backend)
    return list(app_files or []) + list(mid_files or []) + list(drv_files or [])


def _record_prebuilt_symbols(payload: dict[str, Any], prebuilt: dict[str, dict[str, str]], *, backend_module=None) -> int:
    count = 0
    for section in ("macros", "members", "symbols"):
        for ident, cn in (prebuilt.get(section) or {}).items():
            if merge_term_record(
                payload,
                ident,
                cn,
                kind=section,
                source="comment_prebuild",
                confidence=0.92,
                evidence=[section],
                backend_module=backend_module,
            ):
                count += 1
    return count


def _record_function_terms(payload: dict[str, Any], func_entries: Sequence[dict], *, cfg: Any = None, backend_module=None) -> int:
    backend = backend_module or legacy_backend()
    count = 0
    for fd in func_entries or ():
        comment_info = (fd or {}).get("comment_info") or {}
        func_info = (fd or {}).get("func_info") or {}
        func_name = utils_module._safe_strip(func_info.get("func_name"))
        if not func_name:
            continue
        raw_desc = utils_module._safe_strip(comment_info.get("desc"))
        title = backend.get_function_chinese_name(comment_info, func_info)
        title = backend._normalize_function_cn_title(title, func_name=func_name, comment_desc=raw_desc)
        if merge_term_record(
            payload,
            func_name,
            title,
            kind="functions",
            source="comment_rule",
            confidence=0.84 if raw_desc else 0.72,
            usage=raw_desc,
            evidence=[raw_desc] if raw_desc else [],
            backend_module=backend,
        ):
            count += 1
        body = utils_module._safe_text((fd or {}).get("body"))
        params = backend.parse_params_from_prototype(func_info)
        locals_ = backend.parse_local_variables_from_body(body)
        locals_ = backend._filter_local_vars_against_params(locals_, params, cfg=cfg, func_name=func_name)
        scoped_items = [("param", item) for item in (params or ())] + [("local", item) for item in (locals_ or ())]
        for symbol_scope, item in scoped_items:
            ident = utils_module._safe_strip((item or {}).get("name"))
            if not ident:
                continue
            cn = backend.resolve_canonical_symbol_name(
                ident,
                kind="symbols",
                comment_cn=utils_module._safe_strip((item or {}).get("comment_hint")),
                fallback="",
                allow_guess=True,
            )
            if not cn or cn == ident:
                continue
            if merge_term_record(
                payload,
                ident,
                cn,
                kind="symbols",
                source="comment_rule",
                confidence=0.68,
                scope=symbol_scope,
                internal=True,
                usage=utils_module._safe_strip((item or {}).get("usage")),
                evidence=[func_name],
                backend_module=backend,
            ):
                count += 1
    return count


def build_project_term_table(
    project_root: str,
    cfg: Any = None,
    *,
    prebuilt: Optional[dict[str, dict[str, str]]] = None,
    func_entries: Optional[Sequence[dict]] = None,
    save: bool = True,
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    path, payload = load_term_table(project_root, backend_module=backend)
    payload["version"] = TERM_TABLE_VERSION
    if prebuilt:
        _record_prebuilt_symbols(payload, prebuilt, backend_module=backend)
    if func_entries is None:
        entries: list[dict] = []
        for c_path in _iter_project_c_files(project_root, cfg=cfg, backend_module=backend):
            if backend.stop_requested(cfg):
                break
            try:
                func_list, _ = backend.prepare_func_list_for_c_file(
                    c_path,
                    project_root=project_root,
                    cfg=cfg,
                    prefilter=True,
                )
            except Exception:
                continue
            entries.extend(func_list or [])
        func_entries = entries
    _record_function_terms(payload, func_entries or (), cfg=cfg, backend_module=backend)
    if getattr(cfg, "ai_assist", False) and utils_module.cfg_get_int(cfg, "term_table_ai_warmup", 1):
        backend._warmup_symbol_memory_once(func_entries or (), cfg, scope_label=f"term_table:{os.path.basename(os.path.abspath(project_root or ''))}")
        _, memory = backend.load_project_symbol_memory(project_root)
        for section in ("functions", "symbols", "members", "macros"):
            for ident, record in (memory.get(section) or {}).items():
                merge_term_record(
                    payload,
                    ident,
                    utils_module._safe_strip((record or {}).get("cn")),
                    kind=section,
                    source=utils_module._safe_strip((record or {}).get("source")) or "symbol_memory",
                    confidence=float((record or {}).get("confidence", 0.0) or 0.0),
                    backend_module=backend,
                )
    if save:
        save_term_table(path, payload, backend_module=backend)
    flat = flatten_term_table(payload, backend_module=backend)
    for ident, cn in flat.items():
        if ident and cn:
            backend.SYMBOL_DICTIONARY_RUNTIME[ident] = cn
    try:
        cfg.term_table_path = path
    except Exception:
        pass
    return normalize_term_table_payload(payload, backend_module=backend)


def apply_term_table_to_runtime(project_root: str, *, backend_module=None) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    _path, payload = load_term_table(project_root, backend_module=backend)
    flat = flatten_term_table(payload, backend_module=backend)
    backend.SYMBOL_DICTIONARY_RUNTIME.update(flat)
    return flat


def update_term_table_records(
    project_root: str,
    updates: Sequence[dict[str, Any]],
    *,
    save: bool = True,
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    path, payload = load_term_table(project_root, backend_module=backend)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for item in updates or ():
        if not isinstance(item, dict):
            continue
        ident = utils_module._safe_strip(item.get("ident"))
        section = _SECTION_BY_KIND.get(utils_module._safe_strip(item.get("kind")).lower(), utils_module._safe_strip(item.get("section")))
        if section not in ("functions", "symbols", "members", "macros") or not ident:
            continue
        part = payload.setdefault(section, {})
        record = normalize_term_record(part.get(ident) or {"ident": ident, "kind": section}, backend_module=backend)
        cn = utils_module._safe_strip(item.get("cn"))
        if cn:
            record["cn"] = cn
        record["ident"] = ident
        record["kind"] = section
        record["source"] = utils_module._safe_strip(item.get("source") or record.get("source") or "manual")
        record["source_rank"] = _SOURCE_RANK.get(record["source"], int(record.get("source_rank") or 0))
        try:
            record["confidence"] = float(item.get("confidence", record.get("confidence", 1.0)) or 0.0)
        except Exception:
            record["confidence"] = float(record.get("confidence", 1.0) or 1.0)
        if "usage" in item:
            record["usage"] = utils_module._safe_strip(item.get("usage"))
        if "locked" in item:
            record["locked"] = bool(item.get("locked"))
            if record["locked"]:
                record["source"] = "manual_locked"
                record["source_rank"] = _SOURCE_RANK["manual_locked"]
                record["confidence"] = max(float(record.get("confidence", 0.0) or 0.0), 1.0)
                record["confirmed_at"] = utils_module._safe_strip(record.get("confirmed_at")) or now
        record["updated_at"] = now
        part[ident] = record
    if save:
        save_term_table(path, payload, backend_module=backend)
    flat = flatten_term_table(payload, backend_module=backend)
    backend.SYMBOL_DICTIONARY_RUNTIME.update(flat)
    return normalize_term_table_payload(payload, backend_module=backend)


__all__ = [
    "TERM_TABLE_FILENAME",
    "apply_term_table_to_runtime",
    "build_project_term_table",
    "default_term_table_path",
    "flatten_term_table",
    "load_term_table",
    "merge_term_record",
    "normalize_term_record",
    "normalize_term_table_payload",
    "save_term_table",
    "update_term_table_records",
]
