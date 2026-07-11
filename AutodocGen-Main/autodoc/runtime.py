"""Runtime/context helpers for the modular AutoDocGen pipeline."""

from __future__ import annotations

import copy
from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import utils as utils_module
from . import utils
from .models import (
    AiConfig,
    AppConfig,
    GenerationOptions,
    ProjectResumeState,
    RuntimeContext,
    RuntimeState,
    SingleFileResumeState,
    UiHooks,
)


def build_generation_options(cfg: Any, resume_state: Optional[dict[str, Any]] = None) -> GenerationOptions:
    project_file_order = getattr(cfg, "project_file_order", None)
    if isinstance(project_file_order, dict):
        project_file_order = copy.deepcopy(project_file_order)
    else:
        project_file_order = None
    symbol_dict_overrides = getattr(cfg, "symbol_dict_overrides", None)
    if isinstance(symbol_dict_overrides, dict):
        symbol_dict_overrides = dict(symbol_dict_overrides)
    else:
        symbol_dict_overrides = None
    resume_payload = dict(resume_state or {})
    return GenerationOptions(
        only_with_comment=bool(getattr(cfg, "only_with_comment", False)),
        open_after_done=bool(getattr(cfg, "open_after_done", False)),
        prefilter_project_files=bool(getattr(cfg, "prefilter_project_files", True)),
        project_file_order=project_file_order,
        symbol_dict_overrides=symbol_dict_overrides,
        resume_state=resume_payload,
        continuing=bool(resume_payload),
    )


def normalize_single_file_resume_state(resume_state: Optional[dict[str, Any]]) -> SingleFileResumeState:
    payload = dict(resume_state or {})
    return SingleFileResumeState(
        func_pos=max(1, int(payload.get("func_pos", 1))),
        func_index=max(1, int(payload.get("func_index", 1))),
    )


def normalize_project_resume_state(resume_state: Optional[dict[str, Any]]) -> ProjectResumeState:
    payload = dict(resume_state or {})
    module_files = [
        str(path).strip()
        for path in (payload.get("module_files") or [])
        if path is not None and str(path).strip()
    ]
    return ProjectResumeState(
        layer_index=max(0, int(payload.get("layer_index", 0))),
        file_index=max(0, int(payload.get("file_index", 0))),
        func_pos=max(1, int(payload.get("func_pos", 1))),
        func_index=max(1, int(payload.get("func_index", 1))),
        module_counter=max(1, int(payload.get("module_counter", 1))),
        layer_started=bool(payload.get("layer_started", False)),
        module_started=bool(payload.get("module_started", False)),
        module_id=payload.get("module_id"),
        module_files=module_files,
        file=str(payload.get("file") or "").strip(),
        func_name=str(payload.get("func_name") or "").strip(),
    )


def split_legacy_config(cfg: Any, resume_state: Optional[dict[str, Any]] = None) -> RuntimeContext:
    legacy = legacy_backend()
    project_root = utils._safe_strip(getattr(cfg, "project_root", ""))
    extra_params = dict(getattr(cfg, "extra_params", {}) or {})
    generation = build_generation_options(cfg, resume_state=resume_state)
    runtime = RuntimeState(
        project_root=project_root,
        symbol_memory_path=utils._safe_strip(getattr(cfg, "symbol_memory_path", ""))
        or legacy._default_project_symbol_memory_path(project_root)
        if project_root
        else utils._safe_strip(getattr(cfg, "symbol_memory_path", "")),
        title_index_path=legacy._default_project_title_index_path(project_root) if project_root else "",
        symbol_index_path=legacy._default_project_symbol_index_path(project_root) if project_root else "",
        semantic_index_path=legacy._default_project_semantic_index_path(project_root) if project_root else "",
        naming_index_refresh=utils.cfg_get_str(cfg, "naming_index_refresh", "auto"),
        semantic_provider=utils.cfg_get_str(cfg, "semantic_provider", "structured") or "structured",
        metadata={"extra_params": extra_params},
    )
    app = AppConfig(
        section_prefix=utils._safe_strip(getattr(cfg, "section_prefix", "")),
        req_id_prefix=utils._safe_strip(getattr(cfg, "req_id_prefix", "")),
        project_root=project_root,
        template_path=utils._safe_strip(getattr(cfg, "template_path", "")),
        include_locals=bool(getattr(cfg, "include_locals", True)),
        include_logic=bool(getattr(cfg, "include_logic", True)),
        include_flowchart=bool(getattr(cfg, "include_flowchart", True)),
        ai_assist=bool(getattr(cfg, "ai_assist", False)),
        ai_mode=int(getattr(cfg, "ai_mode", 0) or 0),
        extra_params=extra_params,
    )
    ai = AiConfig(
        provider=utils._safe_strip(getattr(cfg, "ai_provider", "")),
        model=utils._safe_strip(getattr(cfg, "ai_model", "")),
        api_key=utils._safe_strip(getattr(cfg, "ai_api_key", "")),
        api_url=utils._safe_strip(getattr(cfg, "ai_url", "")),
        temperature=float(getattr(cfg, "ai_temperature", 0.0) or 0.0),
        profile=utils._safe_strip(getattr(cfg, "ai_profile", ""))
        or utils.cfg_get_str(cfg, "ai_profile", ""),
        naming_authority=utils.cfg_get_str(cfg, "naming_authority", "ai_first") or "ai_first",
    )
    ui = UiHooks(
        log=getattr(cfg, "log_callback", None),
        event=getattr(cfg, "gui_event_callback", None),
        stop_requested=getattr(cfg, "stop_requested_callback", None),
    )
    return RuntimeContext(app=app, ai=ai, runtime=runtime, ui=ui, generation=generation, legacy_cfg=cfg)


def ensure_project_runtime(
    cfg: Any,
    project_root: Optional[str] = None,
    resume_state: Optional[dict[str, Any]] = None,
) -> RuntimeContext:
    legacy = legacy_backend()
    if project_root:
        setattr(cfg, "project_root", project_root)
    ctx = split_legacy_config(cfg, resume_state=resume_state)
    if ctx.runtime.project_root:
        legacy.init_project_symbol_memory(
            ctx.runtime.project_root,
            cfg,
            overrides=ctx.generation.symbol_dict_overrides,
        )
        legacy.init_project_naming_indexes(ctx.runtime.project_root, cfg)
        legacy.init_project_semantic_index(ctx.runtime.project_root, cfg)
    return ctx


def cfg_get_int(cfg: Any, key: str, default: int) -> int:
    return utils.cfg_get_int(cfg, key, default)


def cfg_get_float(cfg: Any, key: str, default: float) -> float:
    return utils.cfg_get_float(cfg, key, default)


def cfg_get_str(cfg: Any, key: str, default: str) -> str:
    return utils.cfg_get_str(cfg, key, default)


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "AiConfig",
    "AppConfig",
    "GenerationOptions",
    "ProjectResumeState",
    "RuntimeContext",
    "RuntimeState",
    "SingleFileResumeState",
    "UiHooks",
    "build_generation_options",
    "cfg_get_float",
    "cfg_get_int",
    "cfg_get_str",
    "ensure_project_runtime",
    "normalize_project_resume_state",
    "normalize_single_file_resume_state",
    "split_legacy_config",
]
