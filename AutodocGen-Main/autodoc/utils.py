"""Shared utility helpers — safe conversions, config access, logging.

These functions are the most widely referenced across the autodoc package
(~70% of all legacy_backend() cross-module calls).  Extracting them here
cuts the dependency on the monolithic backend module.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .backend import GenConfig


# ── Safe value conversion ──────────────────────────────────────────

def _safe_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default


def _safe_strip(value: Any, *, default: str = "") -> str:
    return _safe_text(value, default=default).strip()


# ── Config parameter access ────────────────────────────────────────

def cfg_get_int(cfg: Optional["GenConfig"], key: str, default: int) -> int:
    if not cfg:
        return int(default)
    extra = getattr(cfg, "extra_params", None)
    if isinstance(extra, dict) and key in extra:
        try:
            return int(float(str(extra.get(key)).strip()))
        except Exception:
            return int(default)
    return int(default)


def cfg_get_float(cfg: Optional["GenConfig"], key: str, default: float) -> float:
    if not cfg:
        return float(default)
    extra = getattr(cfg, "extra_params", None)
    if isinstance(extra, dict) and key in extra:
        try:
            return float(str(extra.get(key)).strip())
        except Exception:
            return float(default)
    return float(default)


def cfg_get_str(cfg: Optional["GenConfig"], key: str, default: str) -> str:
    if not cfg:
        return str(default)
    extra = getattr(cfg, "extra_params", None)
    if isinstance(extra, dict) and key in extra:
        try:
            v = extra.get(key)
            s = str(v).strip()
            return s if s else str(default)
        except Exception:
            return str(default)
    return str(default)


# ── Logging ────────────────────────────────────────────────────────

def vlog(cfg: "GenConfig", *args):
    """Verbose log: console + file when verbose=True; GUI always gets it."""
    text = " ".join(str(a) for a in args)
    line = f"[AI] {text}"
    if cfg.verbose:
        try:
            print(line)
        except Exception:
            pass
        try:
            with open("tool.log", "a", encoding="utf-8") as f:
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{ts} {line}\n")
        except Exception:
            pass
    if callable(cfg.gui_log):
        try:
            cfg.gui_log(line)
        except Exception:
            pass


def should_log_step(cfg: "GenConfig", step: int) -> bool:
    n = int(getattr(cfg, "log_every_n", 1) or 1)
    if n <= 1:
        return True
    return step <= 1 or (step % n == 0)


def write_error_log(event: str, payload: dict) -> None:
    """Append a JSON-lines error record to error.log."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rec = {"ts": ts, "event": str(event), "payload": payload or {}}
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _tool_log_write_block(cfg: Optional["GenConfig"], title: str, body: str) -> None:
    """Write a labelled block to tool.log (no GUI)."""
    if not cfg or not getattr(cfg, "verbose", False):
        return
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("tool.log", "a", encoding="utf-8") as f:
            f.write(f"{ts} [AI] ---- {title} (BEGIN) ----\n")
            if body:
                s = str(body)
                f.write(s)
                if not s.endswith("\n"):
                    f.write("\n")
            f.write(f"{ts} [AI] ---- {title} (END) ----\n")
    except Exception:
        pass


def _truncate_for_log(cfg: Optional["GenConfig"], text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    if not cfg:
        return s
    n = int(getattr(cfg, "ai_debug_max_chars", 0) or 0)
    if n <= 0 or len(s) <= n:
        return s
    head = s[: max(0, n // 2)]
    tail = s[-max(0, n // 2) :]
    return head + "\n...[TRUNCATED]...\n" + tail


def _redact_headers(headers: dict) -> dict:
    out = {}
    for k, v in (headers or {}).items():
        if str(k).lower() == "authorization":
            out[k] = "Bearer ***REDACTED***"
        else:
            out[k] = v
    return out


def ai_debug_log(cfg: "GenConfig", event: str, payload: dict):
    """No-op — AI detailed logging removed."""
    return


def stop_requested(cfg: "GenConfig") -> bool:
    """Check whether a stop request has been signalled (GUI only)."""
    ev = getattr(cfg, "stop_event", None)
    return bool(ev and ev.is_set())


def gui_event(cfg: Optional["GenConfig"], payload: dict) -> None:
    """Send a structured event to the GUI (thread-safe callback)."""
    if not cfg:
        return
    cb = getattr(cfg, "gui_event", None)
    if not callable(cb):
        return
    try:
        cb(payload or {})
    except Exception:
        pass


# ── Debug helpers ──────────────────────────────────────────────────

def _debug_preview_json(value: Any, max_len: int = 2000) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        text = repr(value)
    text = str(text or "")
    if len(text) > max_len:
        return text[:max_len] + "...<truncated>"
    return text


def _set_last_llm_json_debug(cfg: Optional["GenConfig"], payload: Optional[dict[str, Any]]) -> None:
    try:
        setattr(cfg, "_last_llm_json_debug", dict(payload or {}))
    except Exception:
        pass


def _get_last_llm_json_debug(cfg: Optional["GenConfig"]) -> dict[str, Any]:
    raw = getattr(cfg, "_last_llm_json_debug", {}) if cfg is not None else {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


__all__ = [
    "_safe_text",
    "_safe_strip",
    "cfg_get_int",
    "cfg_get_float",
    "cfg_get_str",
    "vlog",
    "should_log_step",
    "write_error_log",
    "_tool_log_write_block",
    "_truncate_for_log",
    "_redact_headers",
    "ai_debug_log",
    "stop_requested",
    "gui_event",
    "_debug_preview_json",
    "_set_last_llm_json_debug",
    "_get_last_llm_json_debug",
]