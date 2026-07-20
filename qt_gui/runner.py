from __future__ import annotations

import os
import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Optional

from qt_gui.settings_store import LOCAL_LLM_API_BASE, normalize_ai_mode


@dataclass(frozen=True)
class StepDef:
    step_id: str
    name: str
    parent_id: Optional[str] = None


@dataclass(frozen=True)
class TaskSpec:
    mode: str  # "single" | "project" | "export_func" | "term_table" | "retry"
    c_file: str
    project_dir: str
    output: str
    template_path: str
    project_file_order: Optional[dict[str, list[object]]] = None
    func_name: str = ""
    csu_id: str = ""
    old_code: str = ""
    new_code: str = ""
    old_doc: str = ""
    review_decisions: str = ""
    generation_review_decisions: str = ""
    doc_update_mode: str = "plan-only"
    docdiff_root: str = ""
    renumber_module_csu: bool = False
    failures: Optional[list] = None


class TaskWorkerBase:
    def __init__(self) -> None:
        self.stop_event = threading.Event()

    def request_stop(self) -> None:
        try:
            self.stop_event.set()
        except Exception:
            pass


def _safe_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


class GenerateWorker(TaskWorkerBase):
    def __init__(self, *, backend, task: TaskSpec, settings, resume_state: Optional[dict]):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings
        self.resume_state = resume_state

    def run(self, *, emit_step, emit_log, emit_output, emit_done, emit_detail=None):
        try:
            symbol_dict_overrides = {}
            emit_step("validate", "running")
            # 应用 GUI 术语表覆盖（例如 PBIT/IFBIT...），保证本次运行全局生效
            try:
                txt = str(getattr(self.settings, "domain_glossary_text", "") or "")
                overrides = self.backend.parse_domain_glossary_text(txt)
                self.backend.apply_domain_glossary_overrides(overrides)
            except Exception:
                pass
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                overrides = self.backend.parse_symbol_dictionary_text(txt)
                self.backend.apply_symbol_dictionary_overrides(overrides)
            except Exception:
                overrides = {}
            try:
                symbol_dict_overrides = overrides
            except Exception:
                symbol_dict_overrides = {}
            output = self.task.output.strip()
            if not output:
                raise ValueError("请指定输出路径")

            is_resume = bool(self.resume_state)
            output_norm = self.backend.normalize_docx_output_path(output, ensure_parent_dir=(not is_resume))
            if output_norm != output:
                output = output_norm
                emit_output(output_norm)

            if self.task.mode == "project":
                if not self.task.project_dir.strip():
                    raise ValueError("请选择工程目录")
                if not os.path.isdir(self.task.project_dir.strip()):
                    raise ValueError("工程目录不存在")
            else:
                if not self.task.c_file.strip():
                    raise ValueError("请选择 C 文件")
                if not os.path.isfile(self.task.c_file.strip()):
                    raise ValueError("C 文件不存在")

            emit_step("validate", "success")

            emit_step("config", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                symbol_dict_overrides = self.backend.parse_symbol_dictionary_text(txt)
            except Exception:
                symbol_dict_overrides = {}
            extra_params = dict(getattr(self.settings, "extra_params", None) or {})
            generation_decisions = str(self.task.generation_review_decisions or "").strip()
            if generation_decisions:
                if not os.path.isfile(generation_decisions):
                    raise ValueError("人工审查决策文件不存在")
                from autodoc.review_decisions import resolve_review_bundle_path, write_revision_profile_from_review

                review_dir = str(extra_params.get("review_dir") or "").strip()
                bundle_path = resolve_review_bundle_path(
                    generation_decisions,
                    explicit_bundle=str(extra_params.get("review_bundle") or "").strip(),
                    output_docx=output,
                    review_dir=review_dir,
                )
                review_profile = generation_decisions + ".revision_profile.json"
                profile = write_revision_profile_from_review(
                    bundle_path=bundle_path,
                    decisions_path=generation_decisions,
                    output_path=review_profile,
                )
                extra_params["revision_profile"] = review_profile
                emit_log(f"已应用人工审查决策：{len(profile.get('functions') or {})} 个已通过函数")

            cfg = self.backend.GenConfig(
                section_prefix=getattr(self.settings, "section_prefix", "5.1.1."),
                req_id_prefix=getattr(self.settings, "req_id_prefix", "D/R_SDD01_"),
                only_with_comment=bool(getattr(self.settings, "only_with_comment", False)),
                include_locals=bool(getattr(self.settings, "include_locals", True)),
                include_logic=bool(getattr(self.settings, "include_logic", True)),
                logic_use_comment=bool(getattr(self.settings, "logic_use_comment", True)),
                open_after_done=bool(getattr(self.settings, "open_after_done", False)),
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                ai_num_ctx=_safe_int(getattr(self.settings, "ai_num_ctx", 0), 0),
                ai_read_timeout=float(_safe_int(getattr(self.settings, "ai_read_timeout", 40), 40)),
                ai_workers=max(1, _safe_int(getattr(self.settings, "ai_workers", 2), 2)),
                ai_max_tokens=_safe_int(getattr(self.settings, "ai_max_tokens", 16384), 16384),
                proxy=(str(getattr(self.settings, "proxy", "") or "") if bool(getattr(self.settings, "use_proxy", False)) else ""),
                no_proxy=bool(getattr(self.settings, "no_proxy", False)),
                ai_logic_format="json",
                ai_logic_policy="hybrid",
                ai_one_call=False,
                auto_disable_large_one_call=True,
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                stop_event=self.stop_event,
                template_path=str(self.task.template_path or ""),
                force_ai=False,
                preprocess_workers=max(0, _safe_int(getattr(self.settings, "preprocess_workers", 0), 0)),
                log_every_n=max(1, _safe_int(getattr(self.settings, "log_every_n", 5), 5)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                incremental=bool(getattr(self.settings, "incremental", False)) and self.task.mode == "project",
                project_file_order=(self.task.project_file_order if self.task.mode == "project" else None),
                gui_event=(emit_detail if callable(emit_detail) else None),
                extra_params=extra_params,
                symbol_dict_overrides=symbol_dict_overrides,
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )
            emit_step("config", "success")

            emit_step("generate", "running")
            if self.task.mode == "project":
                self.backend.generate_design_doc_for_project(
                    self.task.project_dir.strip(),
                    output,
                    cfg,
                    resume_state=self.resume_state,
                )
            else:
                self.backend.generate_design_doc_from_file(
                    self.task.c_file.strip(),
                    output,
                    cfg,
                    resume_state=self.resume_state,
                )

            if self.backend.stop_requested(cfg):
                rs = getattr(cfg, "resume_state", None)
                if rs:
                    emit_step("generate", "stopped")
                    emit_done("已停止", rs, output)
                else:
                    emit_step("generate", "success")
                    emit_done("完成", None, output)
            else:
                emit_step("generate", "success")
                emit_done("完成", None, output)

        except Exception as e:
            try:
                rs = getattr(cfg, "resume_state", None) if self.stop_event.is_set() else None
            except Exception:
                rs = None
            emit_step("validate", "failed")
            emit_step("config", "failed")
            emit_step("generate", "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log("qt_gui_generate_failed", {"error": repr(e), "traceback": tb})
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"失败：{e}", rs, None)


class RetryFailedWorker(TaskWorkerBase):
    """Retry only failed functions via autodoc.retry (no full project rescan)."""

    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_output=None, emit_detail=None):
        _ = emit_detail
        try:
            emit_step("validate", "running")
            failures = list(self.task.failures or [])
            if not failures:
                raise ValueError("没有可重试的失败函数")
            output = (self.task.output or "").strip()
            if not output:
                raise ValueError("请指定输出路径")
            try:
                output = self.backend.normalize_docx_output_path(output, ensure_parent_dir=True)
            except Exception:
                pass
            if callable(emit_output):
                emit_output(output)
            emit_step("validate", "success")

            emit_step("config", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            extra_params = dict(getattr(self.settings, "extra_params", None) or {})
            cfg = self.backend.GenConfig(
                section_prefix=getattr(self.settings, "section_prefix", "5.1.1."),
                req_id_prefix=getattr(self.settings, "req_id_prefix", "D/R_SDD01_"),
                only_with_comment=bool(getattr(self.settings, "only_with_comment", False)),
                include_locals=bool(getattr(self.settings, "include_locals", True)),
                include_logic=bool(getattr(self.settings, "include_logic", True)),
                logic_use_comment=bool(getattr(self.settings, "logic_use_comment", True)),
                open_after_done=False,
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                stop_event=self.stop_event,
                template_path=str(self.task.template_path or ""),
                gui_event=(emit_detail if callable(emit_detail) else None),
                extra_params=extra_params,
            )
            emit_step("config", "success")

            emit_step("generate", "running")
            from autodoc.retry import run_retry_generation

            result = run_retry_generation(
                failures,
                output,
                cfg,
                c_file=str(self.task.c_file or "").strip(),
                project_dir=str(self.task.project_dir or "").strip(),
                merge=True,
                backend_module=self.backend,
            )
            for name in result.retried:
                emit_log(f"[retry] ok  {name}")
            for item in result.still_failed:
                emit_log(f"[retry] fail {item.get('func_name')}: {item.get('error_message')}")
            if result.ok:
                emit_step("generate", "success")
                emit_done(
                    f"失败函数重试完成：成功 {len(result.retried)}",
                    None,
                    result.output_path,
                )
            else:
                emit_step("generate", "failed")
                emit_done(
                    f"失败函数重试部分失败：成功 {len(result.retried)}，仍失败 {len(result.still_failed)}",
                    None,
                    result.output_path if result.retried else None,
                )
        except Exception as e:
            emit_step("validate", "failed")
            emit_step("config", "failed")
            emit_step("generate", "failed")
            tb = traceback.format_exc()
            emit_log(tb)
            emit_done(f"失败函数重试失败：{e}", None, None)


class UpdateCsuWorker(TaskWorkerBase):
    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_detail=None):
        try:
            emit_step("load_doc", "running")
            # 应用 GUI 术语表覆盖（CSU 更新也会用到中文名推断）
            try:
                txt = str(getattr(self.settings, "domain_glossary_text", "") or "")
                overrides = self.backend.parse_domain_glossary_text(txt)
                self.backend.apply_domain_glossary_overrides(overrides)
            except Exception:
                pass
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                overrides = self.backend.parse_symbol_dictionary_text(txt)
                self.backend.apply_symbol_dictionary_overrides(overrides)
            except Exception:
                pass
            out = (self.task.output or "").strip()
            if not out:
                raise ValueError("请先选择已生成的 Word 输出（.docx）。")
            out = self.backend.normalize_docx_output_path(out, ensure_parent_dir=False)
            if (not os.path.exists(out)) or (not os.path.isfile(out)):
                raise ValueError("未找到输出 docx 文件，请先生成文档或选择已有 docx。")
            if not out.lower().endswith(".docx"):
                raise ValueError("输出文件必须是 .docx")
            doc = self.backend.Document(out)
            emit_step("load_doc", "success")

            try:
                preprocess_workers = int(getattr(self.settings, "preprocess_workers", 0) or 0)
            except Exception:
                preprocess_workers = 0
            try:
                log_every_n = int(getattr(self.settings, "log_every_n", 5) or 5)
            except Exception:
                log_every_n = 5

            cfg = self.backend.GenConfig(
                verbose=False,
                gui_log=emit_log,
                preprocess_workers=max(0, int(preprocess_workers)),
                log_every_n=max(1, int(log_every_n)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                req_id_prefix=str(getattr(self.settings, "req_id_prefix", "D/R_SDD01_") or "D/R_SDD01_"),
                extra_params=getattr(self.settings, "extra_params", None),
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )

            emit_step("update_ids", "running")
            result = self.backend.update_csu_ids_in_design_chapter_by_headings(doc, cfg)
            emit_step("update_ids", "success")

            emit_step("unit_table", "running")
            unit_result = self.backend.update_software_unit_table_from_design_doc(
                doc,
                cfg,
                design_doc_path=out,
            )
            emit_step("unit_table", "success")

            emit_step("save_doc", "running")
            self.backend.safe_save_docx(doc, out)
            emit_step("save_doc", "success")
            emit_done(
                f"已更新 CSU 标识：模块 {result.get('modules', 0)} 个，模块表 {result.get('tables', 0)} 个，函数标题 {result.get('functions', 0)} 条；单元表 {unit_result.get('units', 0)} 条 -> {unit_result.get('unit_output', '')}",
                out,
            )

        except Exception as e:
            emit_step("load_doc", "failed")
            emit_step("update_ids", "failed")
            emit_step("unit_table", "failed")
            emit_step("save_doc", "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log(
                    "qt_gui_update_csu_failed",
                    {"output": self.task.output, "error": repr(e), "traceback": tb},
                )
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"更新 CSU 标识失败：{e}", None)


class TermTableWorker(TaskWorkerBase):
    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_detail=None):
        try:
            project_dir = (self.task.project_dir or "").strip()
            if not project_dir:
                raise ValueError("请选择工程目录")
            if not os.path.isdir(project_dir):
                raise ValueError("工程目录不存在")

            emit_step("scan", "running")
            try:
                txt = str(getattr(self.settings, "domain_glossary_text", "") or "")
                self.backend.apply_domain_glossary_overrides(self.backend.parse_domain_glossary_text(txt))
            except Exception:
                pass
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                self.backend.apply_symbol_dictionary_overrides(self.backend.parse_symbol_dictionary_text(txt))
            except Exception:
                pass

            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            cfg = self.backend.GenConfig(
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                ai_read_timeout=float(_safe_int(getattr(self.settings, "ai_read_timeout", 40), 40)),
                ai_workers=max(1, _safe_int(getattr(self.settings, "ai_workers", 1), 1)),
                ai_max_tokens=_safe_int(getattr(self.settings, "ai_max_tokens", 16384), 16384),
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                stop_event=self.stop_event,
                preprocess_workers=max(0, _safe_int(getattr(self.settings, "preprocess_workers", 0), 0)),
                log_every_n=max(1, _safe_int(getattr(self.settings, "log_every_n", 5), 5)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                extra_params=getattr(self.settings, "extra_params", None),
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )
            src_dir, app_files, mid_files, drv_files = self.backend.collect_project_c_files_by_layer(project_dir, cfg)
            ordered_files = list(app_files or []) + list(mid_files or []) + list(drv_files or [])
            emit_step("scan", "success")

            emit_step("prebuild", "running")
            prebuilt = self.backend.prebuild_project_symbol_db(project_dir, cfg=cfg)
            self.backend.merge_prebuilt_symbols_into_runtime(prebuilt)
            emit_step("prebuild", "success")

            emit_step("functions", "running")
            import autodoc.pipeline as pipeline_utils

            preprocessed = pipeline_utils.preprocess_project_files(
                ordered_files,
                project_root=project_dir,
                cfg=cfg,
                prefilter=bool(getattr(self.settings, "prefilter_project_files", True)),
                backend_module=self.backend,
            )
            func_entries = self.backend._flatten_preprocessed_func_entries(preprocessed)
            emit_step("functions", "success")

            emit_step("term_table", "running")
            table = self.backend.build_project_term_table(
                project_dir,
                cfg,
                prebuilt=prebuilt if isinstance(prebuilt, dict) else None,
                func_entries=func_entries,
                save=True,
            )
            total_terms = sum(len(table.get(section) or {}) for section in ("functions", "symbols", "members", "macros"))
            path = getattr(cfg, "term_table_path", "") or self.backend.default_term_table_path(project_dir)
            emit_log(f"[term_table] refreshed {total_terms} terms -> {path}")
            emit_step("term_table", "success")
            emit_done(f"术语表已刷新：{total_terms} 项", path)

        except Exception as e:
            for step_id in ("scan", "prebuild", "functions", "term_table"):
                emit_step(step_id, "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log(
                    "qt_gui_term_table_failed",
                    {"project_dir": self.task.project_dir, "error": repr(e), "traceback": tb},
                )
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"刷新术语表失败：{e}", None)


class ExportFuncWorker(TaskWorkerBase):
    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_output, emit_done, emit_detail=None):
        try:
            symbol_dict_overrides = {}
            emit_step("validate", "running")
            # 应用 GUI 术语表/符号表覆盖，保持与整文生成一致
            try:
                txt = str(getattr(self.settings, "domain_glossary_text", "") or "")
                overrides = self.backend.parse_domain_glossary_text(txt)
                self.backend.apply_domain_glossary_overrides(overrides)
            except Exception:
                pass
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                overrides = self.backend.parse_symbol_dictionary_text(txt)
                self.backend.apply_symbol_dictionary_overrides(overrides)
            except Exception:
                overrides = {}
            try:
                symbol_dict_overrides = overrides
            except Exception:
                symbol_dict_overrides = {}
            output = (self.task.output or "").strip()
            if not output:
                raise ValueError("请指定输出路径")

            output_norm = self.backend.normalize_docx_output_path(output, ensure_parent_dir=True)
            if output_norm != output:
                output = output_norm
                emit_output(output_norm)

            if not self.task.c_file.strip():
                raise ValueError("请选择 C 文件")
            if not os.path.isfile(self.task.c_file.strip()):
                raise ValueError("C 文件不存在")
            if not (self.task.func_name or "").strip():
                raise ValueError("请选择要导出的函数")

            emit_step("validate", "success")

            emit_step("config", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                symbol_dict_overrides = self.backend.parse_symbol_dictionary_text(txt)
            except Exception:
                symbol_dict_overrides = {}
            cfg = self.backend.GenConfig(
                section_prefix=getattr(self.settings, "section_prefix", "5.1.1."),
                req_id_prefix=getattr(self.settings, "req_id_prefix", "D/R_SDD01_"),
                only_with_comment=bool(getattr(self.settings, "only_with_comment", False)),
                include_locals=bool(getattr(self.settings, "include_locals", True)),
                include_logic=bool(getattr(self.settings, "include_logic", True)),
                logic_use_comment=bool(getattr(self.settings, "logic_use_comment", True)),
                open_after_done=bool(getattr(self.settings, "open_after_done", False)),
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                ai_num_ctx=_safe_int(getattr(self.settings, "ai_num_ctx", 0), 0),
                ai_read_timeout=float(_safe_int(getattr(self.settings, "ai_read_timeout", 40), 40)),
                ai_workers=max(1, _safe_int(getattr(self.settings, "ai_workers", 2), 2)),
                ai_max_tokens=_safe_int(getattr(self.settings, "ai_max_tokens", 16384), 16384),
                proxy=(str(getattr(self.settings, "proxy", "") or "") if bool(getattr(self.settings, "use_proxy", False)) else ""),
                no_proxy=bool(getattr(self.settings, "no_proxy", False)),
                ai_logic_format="json",
                ai_logic_policy="hybrid",
                ai_one_call=False,
                auto_disable_large_one_call=True,
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                gui_event=(emit_detail if callable(emit_detail) else None),
                stop_event=self.stop_event,
                template_path=str(self.task.template_path or ""),
                force_ai=False,
                preprocess_workers=max(0, _safe_int(getattr(self.settings, "preprocess_workers", 0), 0)),
                log_every_n=max(1, _safe_int(getattr(self.settings, "log_every_n", 5), 5)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                extra_params=getattr(self.settings, "extra_params", None),
                symbol_dict_overrides=symbol_dict_overrides,
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )
            emit_step("config", "success")

            emit_step("generate", "running")
            self.backend.generate_design_doc_for_single_function(
                self.task.c_file.strip(),
                (self.task.func_name or "").strip(),
                output,
                cfg,
                project_root=(self.task.project_dir.strip() or None),
            )
            if self.backend.stop_requested(cfg):
                emit_step("generate", "stopped")
                emit_done("已停止", None, output)
            else:
                emit_step("generate", "success")
                emit_done("完成", None, output)

        except Exception as e:
            emit_step("validate", "failed")
            emit_step("config", "failed")
            emit_step("generate", "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log("qt_gui_export_func_failed", {"error": repr(e), "traceback": tb})
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"失败：{e}", None, None)


class RegenerateCsuWorker(TaskWorkerBase):
    """Worker that regenerates a single CSU in-place in an existing docx."""

    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_detail=None):
        try:
            emit_step("validate", "running")
            doc_path = (self.task.output or "").strip()
            if not doc_path:
                raise ValueError("请先选择已生成的 Word 输出（.docx）。")
            if not os.path.isfile(doc_path):
                raise ValueError(f"未找到文档：{doc_path}")
            c_file = (self.task.c_file or "").strip()
            if not c_file or not os.path.isfile(c_file):
                raise ValueError("请选择有效的 C 源文件。")
            func_name = (self.task.func_name or "").strip()
            if not func_name:
                raise ValueError("请选择要重新生成的函数。")
            csu_id = (self.task.csu_id or "").strip()
            if not csu_id:
                raise ValueError("请指定要替换的 CSU 标识。")
            emit_step("validate", "success")

            emit_step("config", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                symbol_dict_overrides = self.backend.parse_symbol_dictionary_text(txt)
            except Exception:
                symbol_dict_overrides = {}
            cfg = self.backend.GenConfig(
                section_prefix=getattr(self.settings, "section_prefix", "5.1.1."),
                req_id_prefix=getattr(self.settings, "req_id_prefix", "D/R_SDD01_"),
                only_with_comment=bool(getattr(self.settings, "only_with_comment", False)),
                include_locals=bool(getattr(self.settings, "include_locals", True)),
                include_logic=bool(getattr(self.settings, "include_logic", True)),
                logic_use_comment=bool(getattr(self.settings, "logic_use_comment", True)),
                open_after_done=False,
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                ai_num_ctx=_safe_int(getattr(self.settings, "ai_num_ctx", 0), 0),
                ai_read_timeout=float(_safe_int(getattr(self.settings, "ai_read_timeout", 40), 40)),
                ai_workers=max(1, _safe_int(getattr(self.settings, "ai_workers", 2), 2)),
                ai_max_tokens=_safe_int(getattr(self.settings, "ai_max_tokens", 16384), 16384),
                proxy=(str(getattr(self.settings, "proxy", "") or "") if bool(getattr(self.settings, "use_proxy", False)) else ""),
                no_proxy=bool(getattr(self.settings, "no_proxy", False)),
                ai_logic_format="json",
                ai_logic_policy="hybrid",
                ai_one_call=False,
                auto_disable_large_one_call=True,
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                stop_event=self.stop_event,
                template_path=str(self.task.template_path or ""),
                force_ai=False,
                preprocess_workers=max(0, _safe_int(getattr(self.settings, "preprocess_workers", 0), 0)),
                log_every_n=max(1, _safe_int(getattr(self.settings, "log_every_n", 5), 5)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                extra_params=getattr(self.settings, "extra_params", None),
                symbol_dict_overrides=symbol_dict_overrides,
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )
            emit_step("config", "success")

            emit_step("generate", "running")
            import autodoc.pipeline as pipeline_utils
            result = pipeline_utils.regenerate_csu_in_doc(
                doc_path=doc_path,
                source=c_file,
                func_name=func_name,
                csu_id=csu_id,
                cfg=cfg,
                project_root=(self.task.project_dir.strip() or None),
            )
            if not result.get("found"):
                emit_step("generate", "failed")
                emit_done(f"未在文档中找到 CSU：{csu_id}", None, doc_path)
                return
            emit_step("generate", "success")
            msg = f"已重新生成 CSU：{csu_id}（{result.get('new_title', '')}），替换 {result.get('replaced', 0)} 个元素"
            emit_done(msg, doc_path, doc_path)

        except Exception as e:
            emit_step("validate", "failed")
            emit_step("config", "failed")
            emit_step("generate", "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log("qt_gui_regen_csu_failed", {"error": repr(e), "traceback": tb})
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"重新生成 CSU 失败：{e}", None, None)


class RegenerateCsuBatchWorker(TaskWorkerBase):
    """Worker that regenerates multiple CSUs in-place, one by one."""

    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_detail=None):
        try:
            emit_step("validate", "running")
            doc_path = (self.task.output or "").strip()
            if not doc_path or not os.path.isfile(doc_path):
                raise ValueError("未找到文档。")
            c_file = (self.task.c_file or "").strip()
            if not c_file or not os.path.isfile(c_file):
                raise ValueError("未找到 C 源文件。")
            csu_pairs = getattr(self.task, "_csu_pairs", []) or []
            if not csu_pairs:
                raise ValueError("无 CSU 待生成。")
            emit_step("validate", "success")

            emit_step("config", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            try:
                txt = str(getattr(self.settings, "symbol_dict_text", "") or "")
                symbol_dict_overrides = self.backend.parse_symbol_dictionary_text(txt)
            except Exception:
                symbol_dict_overrides = {}
            cfg = self.backend.GenConfig(
                section_prefix=getattr(self.settings, "section_prefix", "5.1.1."),
                req_id_prefix=getattr(self.settings, "req_id_prefix", "D/R_SDD01_"),
                only_with_comment=bool(getattr(self.settings, "only_with_comment", False)),
                include_locals=bool(getattr(self.settings, "include_locals", True)),
                include_logic=bool(getattr(self.settings, "include_logic", True)),
                logic_use_comment=bool(getattr(self.settings, "logic_use_comment", True)),
                open_after_done=False,
                ai_assist=(ai_mode == 1),
                ai_mode=ai_mode,
                ai_provider=str(getattr(self.settings, "ai_provider", "local") or "local"),
                ai_model=str(getattr(self.settings, "ai_model", "") or ""),
                ai_api_base=str(getattr(self.settings, "ai_api_base", LOCAL_LLM_API_BASE) or LOCAL_LLM_API_BASE),
                ai_api_key=str(getattr(self.settings, "ai_api_key", "") or ""),
                ai_use_auth=bool(getattr(self.settings, "ai_api_key", "") or ""),
                ai_num_ctx=_safe_int(getattr(self.settings, "ai_num_ctx", 0), 0),
                ai_read_timeout=float(_safe_int(getattr(self.settings, "ai_read_timeout", 40), 40)),
                ai_workers=max(1, _safe_int(getattr(self.settings, "ai_workers", 2), 2)),
                ai_max_tokens=_safe_int(getattr(self.settings, "ai_max_tokens", 16384), 16384),
                proxy=(str(getattr(self.settings, "proxy", "") or "") if bool(getattr(self.settings, "use_proxy", False)) else ""),
                no_proxy=bool(getattr(self.settings, "no_proxy", False)),
                ai_logic_format="json",
                ai_logic_policy="hybrid",
                ai_one_call=False,
                auto_disable_large_one_call=True,
                verbose=bool(getattr(self.settings, "verbose", True)),
                gui_log=emit_log,
                stop_event=self.stop_event,
                template_path=str(self.task.template_path or ""),
                force_ai=False,
                preprocess_workers=max(0, _safe_int(getattr(self.settings, "preprocess_workers", 0), 0)),
                log_every_n=max(1, _safe_int(getattr(self.settings, "log_every_n", 5), 5)),
                prefilter_project_files=bool(getattr(self.settings, "prefilter_project_files", True)),
                extra_params=getattr(self.settings, "extra_params", None),
                symbol_dict_overrides=symbol_dict_overrides,
                exclude_dirs=tuple([x.strip() for x in (getattr(self.settings, "exclude_dirs", None) or []) if str(x).strip()]),
                mid_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "mid_dir_keywords", None) or []) if str(x).strip()]),
                drv_dir_keywords=tuple([x.strip() for x in (getattr(self.settings, "drv_dir_keywords", None) or []) if str(x).strip()]),
            )
            emit_step("config", "success")

            emit_step("generate", "running")
            import autodoc.pipeline as pipeline_utils
            from docx import Document as _Doc
            total = len(csu_pairs)
            ok = 0
            failed: list[str] = []

            # Open doc once, replace all CSUs, save once (atomic: no half-updated state).
            doc = _Doc(doc_path)
            for i, (func_name, csu_id) in enumerate(csu_pairs, start=1):
                if self.stop_event.is_set():
                    emit_log(f"已停止，完成 {ok}/{total}")
                    break
                emit_log(f"[{i}/{total}] 重新生成 {func_name} → {csu_id} …")
                try:
                    result = pipeline_utils.regenerate_csu_in_doc(
                        doc_path=doc_path,
                        source=c_file,
                        func_name=func_name,
                        csu_id=csu_id,
                        cfg=cfg,
                        project_root=(self.task.project_dir.strip() or None),
                        doc=doc,       # reuse open document
                        save=False,    # caller saves once at end
                    )
                    if result.get("found"):
                        ok += 1
                        emit_log(f"[{i}/{total}] ✓ {csu_id}（{result.get('new_title', '')}）替换 {result.get('replaced', 0)} 个元素")
                    else:
                        failed.append(f"{csu_id}（未找到）")
                        emit_log(f"[{i}/{total}] ✗ {csu_id} 未在文档中找到")
                except Exception as exc:
                    failed.append(f"{csu_id}（{func_name}: {exc}）")
                    emit_log(f"[{i}/{total}] ✗ {func_name} → {csu_id} 失败：{exc}")

            # Save once: all replacements are atomic.
            if ok > 0:
                self.backend.safe_save_docx(doc, doc_path)

            emit_step("generate", "success")
            summary = f"批量重新生成完成：{ok}/{total} 成功"
            if failed:
                summary += f"，{len(failed)} 个失败"
            emit_done(summary, doc_path, doc_path)

        except Exception as e:
            emit_step("validate", "failed")
            emit_step("config", "failed")
            emit_step("generate", "failed")
            tb = traceback.format_exc()
            try:
                self.backend.write_error_log("qt_gui_regen_csu_batch_failed", {"error": repr(e), "traceback": tb})
            except Exception:
                pass
            emit_log(tb)
            emit_done(f"批量重新生成 CSU 失败：{e}", None, None)


class DocUpdateWorker(TaskWorkerBase):
    """Worker for incremental design-doc updates from old/new code trees."""

    def __init__(self, *, backend, task: TaskSpec, settings):
        super().__init__()
        self.backend = backend
        self.task = task
        self.settings = settings

    def run(self, *, emit_step, emit_log, emit_done, emit_output=None, emit_detail=None):
# emit_detail kept for _QtWorker signature compatibility (unused here).
        _ = emit_detail
        try:
            emit_step("validate", "running")
            old_code = (self.task.old_code or "").strip()
            new_code = (self.task.new_code or "").strip()
            old_doc = (self.task.old_doc or "").strip()
            out_doc = (self.task.output or "").strip()
            mode = (self.task.doc_update_mode or "plan-only").strip()
            review_decisions = (self.task.review_decisions or "").strip()
            docdiff_root = (self.task.docdiff_root or "").strip()

            if not old_code or not os.path.isdir(old_code):
                raise ValueError("请选择旧代码目录")
            if not new_code or not os.path.isdir(new_code):
                raise ValueError("请选择新代码目录")
            if not old_doc or not os.path.isfile(old_doc):
                raise ValueError("请选择旧 Word 文档")
            if not out_doc:
                raise ValueError("请指定输出 Word 文档（输出副本）")
            if not str(out_doc).lower().endswith(".docx"):
                raise ValueError("输出路径必须是 .docx 文件")
            if mode not in {"plan-only", "apply-safe", "apply-review"}:
                raise ValueError(f"文档更新模式无效：{mode or '(empty)'}")
            if mode == "apply-review" and (not review_decisions or not os.path.isfile(review_decisions)):
                raise ValueError("apply-review 需要选择 review_decisions.json")
            emit_step("validate", "success")

            # Ensure package root is importable when frozen/cwd differs.
            try:
                pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
                if pkg_root and pkg_root not in sys.path:
                    sys.path.insert(0, pkg_root)
            except Exception:
                pass

            from tools import update_doc_from_code_diff as updater

            old_code = updater._abs(old_code)
            new_code = updater._abs(new_code)
            old_doc = updater._abs(old_doc)
            out_doc = updater._abs(out_doc)
            docdiff_root = updater._abs(docdiff_root or updater._default_docdiff_root())
            if not docdiff_root or not os.path.isdir(docdiff_root):
                raise ValueError(f"DocDiff 目录不存在：{docdiff_root}")
            change_docx = updater._default_sidecar(out_doc, ".code_change.docx")
            change_json = updater._default_sidecar(out_doc, ".code_changes.json")
            plan_out = updater._default_sidecar(out_doc, ".update_plan.json")
            report_out = updater._default_sidecar(out_doc, ".update_report.md")
            review_html = updater._default_sidecar(out_doc, ".update_review.html")

            emit_step("diff", "running")
            updater._run_docdiff(
                docdiff_root=docdiff_root,
                old_code=old_code,
                new_code=new_code,
                change_docx=change_docx,
                change_json=change_json,
            )
            changes = updater._load_changes(change_json)
            emit_log(f"代码差异：{len(changes)} 项")
            emit_step("diff", "success")

            emit_step("plan", "running")
            csu_index = updater.build_csu_index(old_doc)
            alignment_index = updater.build_doc_code_alignment_index(old_doc, old_code)
            alignment_decisions = updater._load_alignment_decisions(review_decisions) if review_decisions and os.path.isfile(review_decisions) else []
            updater.apply_alignment_decisions(
                alignment_index,
                csu_index,
                alignment_decisions,
                code_roots=[old_code, new_code],
            )
            items = updater.classify_changes(changes, new_code=new_code, csu_index=csu_index)
            updater.attach_alignment_to_items(items, alignment_index)
            emit_log(f"更新计划：{len(items)} 项")
            emit_step("plan", "success")

            emit_step("apply", "running")
            ai_mode = normalize_ai_mode(getattr(self.settings, "ai_mode", 0))
            if mode == "apply-safe":
                updater.apply_safe_items(
                    items,
                    old_doc=old_doc,
                    out_doc=out_doc,
                    new_code=new_code,
                    ai_assist=(ai_mode == 1),
                    template_path=str(self.task.template_path or ""),
                )
            elif mode == "apply-review":
                updater.apply_safe_items(
                    items,
                    old_doc=old_doc,
                    out_doc=out_doc,
                    new_code=new_code,
                    ai_assist=(ai_mode == 1),
                    template_path=str(self.task.template_path or ""),
                )
                updater.apply_review_decisions(
                    items,
                    out_doc=out_doc,
                    new_code=new_code,
                    review_decisions=updater._load_review_decisions(review_decisions),
                    ai_assist=(ai_mode == 1),
                    template_path=str(self.task.template_path or ""),
                    renumber_module_csu=bool(self.task.renumber_module_csu),
                )
            emit_step("apply", "success")

            emit_step("report", "running")
            metadata = {
                "mode": mode,
                "old_code": old_code,
                "new_code": new_code,
                "old_doc": old_doc,
                "out_doc": out_doc,
                "docdiff_root": docdiff_root,
                "change_docx": change_docx,
                "change_json": change_json,
                "review_decisions": review_decisions,
                "renumber_module_csu": bool(self.task.renumber_module_csu),
                "alignment": {
                    "schema_version": updater.DOC_CODE_ALIGNMENT_SCHEMA,
                    "code_root": old_code,
                    "total_csu": len(alignment_index),
                    "matched_high": sum(1 for item in alignment_index.values() if item.get("status") == "matched_high"),
                    "manual_matched": sum(1 for item in alignment_index.values() if item.get("status") == "manual_matched"),
                    "ambiguous": sum(1 for item in alignment_index.values() if item.get("status") == "ambiguous"),
                    "unmatched": sum(1 for item in alignment_index.values() if item.get("status") in {"unmatched", "no_doc_function"}),
                },
            }
            updater.write_reports(
                items=items,
                plan_path=plan_out,
                report_path=report_out,
                metadata=metadata,
                alignment_index=alignment_index,
            )
            updater.write_review_html(plan_path=plan_out, review_html_path=review_html)
            emit_log(f"plan: {plan_out}")
            emit_log(f"report: {report_out}")
            emit_log(f"review_html: {review_html}")
            emit_step("report", "success")

            if callable(emit_output):
                emit_output(out_doc)
            emit_done("文档增量更新完成", None, out_doc)
        except Exception as e:
            for step_id in ("validate", "diff", "plan", "apply", "report"):
                try:
                    emit_step(step_id, "failed")
                except Exception:
                    pass
            tb = traceback.format_exc()
            emit_log(tb)
            emit_done(f"文档增量更新失败：{e}", None, None)
