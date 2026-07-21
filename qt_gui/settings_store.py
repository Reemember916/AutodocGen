from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


LOCAL_LLM_API_BASE = "10.11.34.200:11434/v1"

# 与 autodoc/utils.py 的 AI_API_KEY_ENV 保持一致；设置环境变量可覆盖 ini 明文 key。
_AI_API_KEY_ENV = "AUTODOCGEN_AI_API_KEY"


def _resolve_api_key(ini_value) -> str:
    """环境变量 AUTODOCGEN_AI_API_KEY 优先于 ini 明文 key，避免密钥泄露。"""
    env_val = os.environ.get(_AI_API_KEY_ENV, "").strip()
    if env_val:
        return env_val
    s = str(ini_value) if ini_value is not None else ""
    return s.strip()


def normalize_ai_mode(value) -> int:
    """Public AI mode is binary: 0 = off, 1 = enabled.

    Older configs may contain legacy non-zero values.  Treat every non-zero
    value as enabled so users migrate without losing provider/model settings.
    """
    try:
        raw = int(value)
    except Exception:
        raw = 0
    return 1 if raw > 0 else 0


@dataclass
class AppSettings:
    section_prefix: str = "5.1.1."
    req_id_prefix: str = "D/R_SDD01_"
    only_with_comment: bool = False
    include_locals: bool = True
    include_logic: bool = True
    logic_use_comment: bool = True
    open_after_done: bool = False

    ai_mode: int = 0
    ai_provider: str = "local"
    ai_model: str = ""
    ai_api_base: str = LOCAL_LLM_API_BASE
    ai_api_key: str = ""
    ai_num_ctx: int = 0
    ai_read_timeout: int = 40
    ai_workers: int = 1
    use_proxy: bool = False
    proxy: str = ""
    no_proxy: bool = True  # 默认禁用代理（不扫描本地代理端口）
    force_ai: bool = False
    verbose: bool = True
    ai_one_call: bool = False
    auto_disable_large_one_call: bool = True
    ai_logic_format: str = "json"
    ai_logic_policy: str = "hybrid"
    ai_max_tokens: int = 16384
    ai_context_scope: str = "target_only"

    prefilter_project_files: bool = True
    incremental: bool = False
    preprocess_workers: int = 0
    log_every_n: int = 5

    # 工程扫描/分层规则
    exclude_dirs: list[str] = field(default_factory=lambda: [".git", ".settings", ".launches", "debug", "release", "__pycache__"])
    mid_dir_keywords: list[str] = field(default_factory=lambda: ["common"])
    drv_dir_keywords: list[str] = field(default_factory=lambda: ["dspdriver"])

    # 术语表覆盖（每行 KEY=中文；也支持 JSON dict）
    domain_glossary_text: str = ""
    # 符号字典覆盖（用于局部变量/全局变量/结构体成员/函数/宏名一致化）
    symbol_dict_text: str = ""

    # 高级：AI JSON key/变量名容错参数（动态键值对）
    extra_params: dict[str, str] = field(
        default_factory=lambda: {
            "max_dist": "2",
            "min_ratio": "0.8",
            "ai_profile": "small_model",
            "ai_retry_times": "0",
            "ai_fail_policy": "fallback",
            "structured_cond_ai": "0",
            "ai_regression_rounds": "1",
            "ai_regression_force_one_call": "0",
            "ai_context_scope": "target_only",
            "codegraph_mode": "auto",
            "graph_output": "off",
            "graph_depth": "2",
            "graph_max_nodes": "40",
            "codegraph_auto_index": "1",
            "revision_profile": "",
        }
    )


def _preferred_settings_path() -> str:
    if getattr(sys, "frozen", False):
        # PyInstaller --onefile: exe 目录优先，找不到则 fallback 到 _MEIPASS
        exe_dir = os.path.dirname(sys.executable)
        exe_path = os.path.join(exe_dir, "autodocgen.ini")
        if os.path.exists(exe_path):
            return exe_path
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_path = os.path.join(meipass, "autodocgen.ini")
            if os.path.exists(meipass_path):
                return meipass_path
        return exe_path  # fallback: exe 目录（即使不存在，QSettings 会创建）
    base_dir = os.path.abspath(os.getcwd())
    return os.path.join(base_dir, "autodocgen.ini")


class SettingsStore:
    def __init__(self) -> None:
        self._settings = self._create_qsettings()

    def load_window_layout(self, mode: str):
        mode = str(mode or "").strip().lower()
        if mode not in ("web", "default"):
            mode = "web"
        geo = self._settings.value(f"ui/layout_{mode}_geometry", None)
        state = self._settings.value(f"ui/layout_{mode}_state", None)
        return geo, state

    def save_window_layout(self, mode: str, *, geometry, state) -> None:
        mode = str(mode or "").strip().lower()
        if mode not in ("web", "default"):
            mode = "web"
        if geometry is not None:
            self._settings.setValue(f"ui/layout_{mode}_geometry", geometry)
        if state is not None:
            self._settings.setValue(f"ui/layout_{mode}_state", state)
        self._settings.sync()

    def _create_qsettings(self):
        from PyQt5 import QtCore

        path = _preferred_settings_path()
        try:
            with open(path, "a", encoding="utf-8"):
                pass
        except Exception:
            app_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)
            if not app_dir:
                app_dir = os.path.abspath(os.getcwd())
            os.makedirs(app_dir, exist_ok=True)
            path = os.path.join(app_dir, "autodocgen.ini")
        return QtCore.QSettings(path, QtCore.QSettings.IniFormat)

    def load(self) -> AppSettings:
        s = self._settings
        out = AppSettings()
        out.section_prefix = str(s.value("basic/section_prefix", out.section_prefix))
        out.req_id_prefix = str(s.value("basic/req_id_prefix", out.req_id_prefix))
        out.only_with_comment = bool(int(s.value("basic/only_with_comment", int(out.only_with_comment))))
        out.include_locals = bool(int(s.value("basic/include_locals", int(out.include_locals))))
        out.include_logic = bool(int(s.value("basic/include_logic", int(out.include_logic))))
        out.logic_use_comment = bool(int(s.value("basic/logic_use_comment", int(out.logic_use_comment))))
        out.open_after_done = bool(int(s.value("basic/open_after_done", int(out.open_after_done))))

        out.ai_mode = normalize_ai_mode(s.value("ai/ai_mode", out.ai_mode))
        out.ai_provider = str(s.value("ai/ai_provider", out.ai_provider))
        out.ai_model = str(s.value("ai/ai_model", out.ai_model))
        out.ai_api_base = str(s.value("ai/ai_api_base", out.ai_api_base))
        out.ai_api_key = _resolve_api_key(s.value("ai/ai_api_key", out.ai_api_key))
        out.ai_num_ctx = int(s.value("ai/ai_num_ctx", out.ai_num_ctx))
        out.ai_read_timeout = max(5, min(600, int(s.value("ai/ai_read_timeout", out.ai_read_timeout))))
        out.ai_workers = max(1, min(16, int(s.value("ai/ai_workers", out.ai_workers))))
        out.use_proxy = bool(int(s.value("ai/use_proxy", int(out.use_proxy))))
        out.proxy = str(s.value("ai/proxy", out.proxy))
        out.no_proxy = bool(int(s.value("ai/no_proxy", int(out.no_proxy))))
        out.force_ai = False
        out.verbose = bool(int(s.value("ai/verbose", int(out.verbose))))
        out.ai_one_call = False
        out.auto_disable_large_one_call = True
        out.ai_logic_format = "json"
        out.ai_logic_policy = "hybrid"
        out.ai_max_tokens = int(s.value("ai/ai_max_tokens", out.ai_max_tokens))

        out.prefilter_project_files = bool(int(s.value("perf/prefilter_project_files", int(out.prefilter_project_files))))
        out.incremental = bool(int(s.value("perf/incremental", int(out.incremental))))
        out.preprocess_workers = int(s.value("perf/preprocess_workers", out.preprocess_workers))
        out.log_every_n = int(s.value("perf/log_every_n", out.log_every_n))

        exclude_raw = str(s.value("project/exclude_dirs", "") or "")
        if exclude_raw.strip():
            out.exclude_dirs = [x.strip() for x in exclude_raw.replace(",", "\n").splitlines() if x.strip()]
        mid_raw = str(s.value("project/mid_dir_keywords", "") or "")
        if mid_raw.strip():
            out.mid_dir_keywords = [x.strip() for x in mid_raw.replace(",", "\n").splitlines() if x.strip()]
        drv_raw = str(s.value("project/drv_dir_keywords", "") or "")
        if drv_raw.strip():
            out.drv_dir_keywords = [x.strip() for x in drv_raw.replace(",", "\n").splitlines() if x.strip()]

        out.domain_glossary_text = str(s.value("basic/domain_glossary_text", out.domain_glossary_text) or "")
        out.symbol_dict_text = str(s.value("basic/symbol_dict_text", out.symbol_dict_text) or "")

        extra_json = str(s.value("advanced/extra_params_json", "") or "")
        if extra_json.strip():
            try:
                import json

                obj = json.loads(extra_json)
                if isinstance(obj, dict):
                    out.extra_params = {str(k): str(v) for k, v in obj.items()}
            except Exception:
                pass

        # Backward-compatible migration (old dedicated keys -> extra_params)
        try:
            if "ai_retry_times" not in out.extra_params:
                out.extra_params["ai_retry_times"] = str(int(s.value("ai/retry_times", 0) or 0))
            if "ai_fail_policy" not in out.extra_params:
                out.extra_params["ai_fail_policy"] = str(s.value("ai/fail_policy", "fallback") or "fallback")
        except Exception:
            pass
        for key, value in {
            "codegraph_mode": "auto",
            "graph_output": "off",
            "graph_depth": "2",
            "graph_max_nodes": "40",
            "codegraph_auto_index": "1",
            "revision_profile": "",
        }.items():
            out.extra_params.setdefault(key, value)
        return out

    def save(self, settings: AppSettings) -> None:
        s = self._settings
        s.setValue("basic/section_prefix", settings.section_prefix)
        s.setValue("basic/req_id_prefix", settings.req_id_prefix)
        s.setValue("basic/only_with_comment", int(bool(settings.only_with_comment)))
        s.setValue("basic/include_locals", int(bool(settings.include_locals)))
        s.setValue("basic/include_logic", int(bool(settings.include_logic)))
        s.setValue("basic/logic_use_comment", int(bool(settings.logic_use_comment)))
        s.setValue("basic/open_after_done", int(bool(settings.open_after_done)))

        s.setValue("ai/ai_mode", normalize_ai_mode(settings.ai_mode))
        s.setValue("ai/ai_provider", settings.ai_provider)
        s.setValue("ai/ai_model", settings.ai_model)
        s.setValue("ai/ai_api_base", settings.ai_api_base)
        s.setValue("ai/ai_api_key", settings.ai_api_key)
        s.setValue("ai/ai_num_ctx", int(settings.ai_num_ctx))
        s.setValue("ai/ai_read_timeout", int(settings.ai_read_timeout))
        s.setValue("ai/ai_workers", int(settings.ai_workers))
        s.setValue("ai/use_proxy", int(bool(settings.use_proxy)))
        s.setValue("ai/proxy", settings.proxy)
        s.setValue("ai/no_proxy", int(bool(settings.no_proxy)))
        s.setValue("ai/force_ai", 0)
        s.setValue("ai/verbose", int(bool(settings.verbose)))
        s.setValue("ai/ai_one_call", 0)
        s.setValue("ai/auto_disable_large_one_call", 1)
        s.setValue("ai/ai_logic_format", "json")
        s.setValue("ai/ai_logic_policy", "hybrid")
        s.setValue("ai/ai_max_tokens", int(settings.ai_max_tokens))

        s.setValue("perf/prefilter_project_files", int(bool(settings.prefilter_project_files)))
        s.setValue("perf/incremental", int(bool(settings.incremental)))
        s.setValue("perf/preprocess_workers", int(settings.preprocess_workers))
        s.setValue("perf/log_every_n", int(settings.log_every_n))

        s.setValue("project/exclude_dirs", "\n".join([str(x).strip() for x in (settings.exclude_dirs or []) if str(x).strip()]))
        s.setValue("project/mid_dir_keywords", "\n".join([str(x).strip() for x in (settings.mid_dir_keywords or []) if str(x).strip()]))
        s.setValue("project/drv_dir_keywords", "\n".join([str(x).strip() for x in (settings.drv_dir_keywords or []) if str(x).strip()]))

        s.setValue("basic/domain_glossary_text", str(settings.domain_glossary_text or ""))
        s.setValue("basic/symbol_dict_text", str(settings.symbol_dict_text or ""))

        # Deprecated: ai/retry_times and ai/fail_policy now live in extra_params only

        try:
            import json

            s.setValue("advanced/extra_params_json", json.dumps(settings.extra_params or {}, ensure_ascii=False))
        except Exception:
            s.setValue("advanced/extra_params_json", "{}")
        s.sync()

    def load_recent_inputs(self) -> dict[str, str]:
        s = self._settings
        return {
            "c_file": str(s.value("recent/c_file", "") or ""),
            "project_dir": str(s.value("recent/project_dir", "") or ""),
            "output": str(s.value("recent/output", "") or ""),
            "template": str(s.value("recent/template", "") or ""),
            "review_decisions": str(s.value("recent/review_decisions", "") or ""),
        }

    def save_recent_inputs(self, data: dict[str, str]) -> None:
        s = self._settings
        s.setValue("recent/c_file", str((data or {}).get("c_file") or ""))
        s.setValue("recent/project_dir", str((data or {}).get("project_dir") or ""))
        s.setValue("recent/output", str((data or {}).get("output") or ""))
        s.setValue("recent/template", str((data or {}).get("template") or ""))
        s.setValue("recent/review_decisions", str((data or {}).get("review_decisions") or ""))
        self.remember_recent_project(data)
        s.sync()

    def load_recent_projects(self) -> list[dict[str, str]]:
        raw = str(self._settings.value("recent/projects_json", "") or "")
        if not raw.strip():
            legacy = self.load_recent_inputs()
            return [legacy] if (legacy.get("project_dir") or legacy.get("c_file")) else []
        try:
            value = json.loads(raw)
        except Exception:
            return []
        if not isinstance(value, list):
            return []
        projects = []
        for item in value[:5]:
            if not isinstance(item, dict):
                continue
            normalized = {str(k): str(v or "") for k, v in item.items()}
            if normalized.get("project_dir") or normalized.get("c_file"):
                projects.append(normalized)
        return projects

    def remember_recent_project(self, data: dict[str, str]) -> None:
        item = {str(k): str(v or "") for k, v in (data or {}).items()}
        key = item.get("project_dir") or item.get("c_file")
        if not key:
            return
        item["last_used"] = datetime.now().isoformat(timespec="minutes")
        current = self.load_recent_projects()
        deduped = [
            record for record in current
            if (record.get("project_dir") or record.get("c_file")) != key
        ]
        self._settings.setValue(
            "recent/projects_json",
            json.dumps([item] + deduped[:4], ensure_ascii=False),
        )
