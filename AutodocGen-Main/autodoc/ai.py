"""AI transport, prompt construction, and AI-first naming helpers."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shlex
import sys
import threading
import time
from collections import Counter, OrderedDict, defaultdict
from typing import Any, Optional, Sequence

from ._legacy_support import legacy_backend
from . import utils
from . import text as text_utils
from . import naming as naming_utils
from . import semantic as semantic_utils
from .semantic import get_semantic_provider


_CODEISH_RE = re.compile(
    r"(?:\bif\s*\(|\bfor\s*\(|\bwhile\s*\(|==|!=|>=|<=|&&|\|\||->|[A-Za-z_]\w*\s*\([^)]*\)|\[[^\]]+\]\s*=|=\s*[A-Za-z_]\w*\s*\()"
)
_AI_RESPONSE_CACHE_MAX = 512
_AI_RESPONSE_CACHE_LOCK = threading.Lock()
_AI_RESPONSE_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_AI_AUTH_CIRCUIT_LOCK = threading.Lock()
_AI_AUTH_CIRCUIT_OPEN_KEYS: set[str] = set()
_AI_HTTP_LOCAL = threading.local()
_CACHE_MISS = object()
_THINK_BLOCK_RE = re.compile(r"(?is)<think>.*?</think>\s*")
_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_HOST_LIKE_URL_RE = re.compile(r"^(?:localhost|[\w.-]+)(?::\d+)?(?:/.*)?$")
_AI_AUTH_FAILURE_STATUS_CODES = frozenset({401, 403})




def ai_context_scope(cfg: Optional[Any]) -> str:
    """Return the configured AI context scope.

    target_only is the safe default for single-function generation: AI may help the
    target function, but it must not pre-warm or recursively summarize unrelated
    project functions unless the caller explicitly widens the scope.
    """
    raw = ""
    try:
        extra = dict(getattr(cfg, "extra_params", {}) or {}) if cfg is not None else {}
        raw = utils._safe_strip(extra.get("ai_context_scope"))
    except Exception:
        raw = ""
    if not raw:
        raw = utils._safe_strip(getattr(cfg, "ai_context_scope", "")) if cfg is not None else ""
    value = raw.lower().replace("-", "_").strip()
    aliases = {
        "": "target_only",
        "target": "target_only",
        "target_only": "target_only",
        "local": "local_neighbors",
        "local_neighbor": "local_neighbors",
        "local_neighbors": "local_neighbors",
        "neighbor": "local_neighbors",
        "neighbors": "local_neighbors",
        "project": "project",
        "project_deep": "project",
        "deep": "project",
    }
    return aliases.get(value, "target_only")


def ai_allows_context_warmup(cfg: Optional[Any]) -> bool:
    return ai_context_scope(cfg) != "target_only"
def _apply_compat_request_headers(headers: dict[str, str], cfg: Optional[Any], *, backend_module=None) -> dict[str, str]:
    legacy = backend_module or legacy_backend()
    out = dict(headers or {})
    ua = ""
    referer = ""
    origin = ""
    try:
        extra = dict(getattr(cfg, "extra_params", {}) or {}) if cfg is not None else {}
        ua = utils._safe_strip(extra.get("ai_http_user_agent"))
        referer = utils._safe_strip(extra.get("ai_http_referer"))
        origin = utils._safe_strip(extra.get("ai_http_origin"))
    except Exception:
        ua = ""
        referer = ""
        origin = ""
    if ua:
        out["User-Agent"] = ua
    if referer:
        out["Referer"] = referer
    if origin:
        out["Origin"] = origin
    return out


def _resolve_backend_module(cfg: Any = None, runtime_module: Any = None):
    if runtime_module is not None:
        return runtime_module
    module_name = str(getattr(type(cfg), "__module__", "") or "")
    module = sys.modules.get(module_name)
    if module is not None and hasattr(module, "_safe_strip"):
        return module
    return legacy_backend()


def _get_requests_module(*, cfg: Any = None, backend_module: Any = None):
    backend = _resolve_backend_module(cfg, backend_module)
    return getattr(backend, "requests", None)


def _get_runtime_hook(runtime_module: Any, name: str, fallback: Any):
    hook = getattr(runtime_module, name, None) if runtime_module is not None else None
    if callable(hook):
        return hook
    return fallback


def _is_ai_auth_failure_status(status_code: Any) -> bool:
    try:
        return int(status_code) in _AI_AUTH_FAILURE_STATUS_CODES
    except Exception:
        return False


def _make_ai_auth_circuit_key(provider: str, url: str, model: str, wire_api: str, api_key: str) -> str:
    try:
        key_sha = hashlib.sha256((api_key or "").encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        key_sha = ""
    payload = {
        "provider": str(provider or "").strip().lower(),
        "url": str(url or "").strip(),
        "model": str(model or "").strip(),
        "wire_api": str(wire_api or "").strip().lower(),
        "api_key_sha256": key_sha,
    }
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        raw = repr(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _ai_auth_circuit_is_open(circuit_key: str) -> bool:
    if not circuit_key:
        return False
    with _AI_AUTH_CIRCUIT_LOCK:
        return circuit_key in _AI_AUTH_CIRCUIT_OPEN_KEYS


def _open_ai_auth_circuit(circuit_key: str) -> None:
    if not circuit_key:
        return
    with _AI_AUTH_CIRCUIT_LOCK:
        _AI_AUTH_CIRCUIT_OPEN_KEYS.add(circuit_key)


def _mark_ai_failure_state(cfg: Optional[Any], reason: str) -> None:
    try:
        setattr(cfg, "_ai_last_error", str(reason or "AI failed"))
        if getattr(cfg, "_in_func_context", False):
            setattr(cfg, "_current_func_ai_failed", True)
    except Exception:
        pass


def _mark_ai_auth_failure(cfg: Optional[Any], reason: str, *, circuit_key: str = "") -> None:
    _open_ai_auth_circuit(circuit_key)
    _mark_ai_failure_state(cfg, reason)
    try:
        setattr(cfg, "ai_circuit_break", True)
        if getattr(cfg, "_in_func_context", False):
            setattr(cfg, "_skip_ai_current_func", True)
    except Exception:
        pass
    if cfg is None:
        return
    already_reported = bool(getattr(cfg, "_ai_auth_failure_reported", False))
    try:
        setattr(cfg, "_ai_auth_failure_reported", True)
    except Exception:
        pass
    if not already_reported:
        try:
            utils.vlog(cfg, "AI 鉴权失败，已熔断后续 AI 调用：", reason)
        except Exception:
            pass
        utils.gui_event(cfg, {"type": "ai_circuit_break", "reason": reason, "category": "auth"})


def _skip_due_to_ai_auth_circuit(cfg: Optional[Any], circuit_key: str) -> bool:
    if not _ai_auth_circuit_is_open(circuit_key):
        return False
    _mark_ai_failure_state(cfg, "AI 鉴权失败，已跳过后续调用")
    try:
        setattr(cfg, "ai_circuit_break", True)
        if getattr(cfg, "_in_func_context", False):
            setattr(cfg, "_skip_ai_current_func", True)
    except Exception:
        pass
    return True


def _make_ai_cache_key(kind: str, prompt: str, cfg: Any, provider: str, url: str) -> str:
    try:
        prompt_sha = hashlib.sha256((prompt or "").encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        prompt_sha = ""
    payload = {
        "kind": str(kind or ""),
        "provider": str(provider or ""),
        "url": str(url or ""),
        "model": str(getattr(cfg, "ai_model", "") or ""),
        "temperature": float(getattr(cfg, "ai_temperature", 0.0) or 0.0),
        "top_p": float(getattr(cfg, "ai_top_p", 0.0) or 0.0),
        "max_tokens": int(getattr(cfg, "ai_max_tokens", 0) or 0),
        "num_ctx": int(getattr(cfg, "ai_num_ctx", 0) or 0),
        "cache_salt": str(getattr(cfg, "_ai_cache_salt", "") or ""),
        "prompt_len": len(prompt or ""),
        "prompt_sha256": prompt_sha,
    }
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        raw = repr(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _ai_cache_get(key: str, *, clone: bool) -> Any:
    if not key:
        return _CACHE_MISS
    with _AI_RESPONSE_CACHE_LOCK:
        value = _AI_RESPONSE_CACHE.get(key, _CACHE_MISS)
        if value is _CACHE_MISS:
            return _CACHE_MISS
        _AI_RESPONSE_CACHE.move_to_end(key)
    return copy.deepcopy(value) if clone else value


def _ai_cache_set(key: str, value: Any, *, clone: bool) -> None:
    if not key:
        return
    stored = copy.deepcopy(value) if clone else value
    with _AI_RESPONSE_CACHE_LOCK:
        _AI_RESPONSE_CACHE[key] = stored
        _AI_RESPONSE_CACHE.move_to_end(key)
        while len(_AI_RESPONSE_CACHE) > _AI_RESPONSE_CACHE_MAX:
            _AI_RESPONSE_CACHE.popitem(last=False)


def _clear_ai_runtime_state() -> None:
    with _AI_RESPONSE_CACHE_LOCK:
        _AI_RESPONSE_CACHE.clear()
    with _AI_AUTH_CIRCUIT_LOCK:
        _AI_AUTH_CIRCUIT_OPEN_KEYS.clear()
    legacy = legacy_backend()
    try:
        legacy.SESSION_SYMBOL_DICTIONARY.clear()
    except Exception:
        pass
    try:
        session = getattr(_AI_HTTP_LOCAL, "session", None)
        if session is not None:
            session.close()
    except Exception:
        pass
    try:
        _AI_HTTP_LOCAL.session = None
        _AI_HTTP_LOCAL.pool_size = 0
    except Exception:
        pass


def strip_think_blocks(text: str, *, backend_module: Any = None) -> str:
    """
    移除 deepseek-r1 / 部分本地模型返回的 <think>...</think> 思考内容，避免污染后续 JSON 解析与文本抽取。
    """
    backend = _resolve_backend_module(None, backend_module)
    value = utils._safe_text(text)
    if not value:
        return ""

    cleaned = _THINK_BLOCK_RE.sub("", value)
    cleaned = re.sub(r"(?is)<think>.*\Z", "", cleaned)
    return cleaned.strip()


def safe_json_loads(text: Any, *, backend_module: Any = None):
    backend = _resolve_backend_module(None, backend_module)
    if not isinstance(text, str):
        return None

    value = utils._safe_text(text)
    if not value:
        return None

    value = strip_think_blocks(value, backend_module=backend).strip()
    if value.startswith("```"):
        value = value.strip("`")
        value = value.replace("json", "")
        value = value.strip()

    try:
        return json.loads(value)
    except Exception:
        pass

    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", value)
    if not match:
        return None
    candidate = match.group(1).strip()
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)

    try:
        return json.loads(candidate)
    except Exception:
        pass

    try:
        return ast.literal_eval(candidate)
    except Exception:
        return None


def _looks_like_utf8_mojibake(text: str, *, backend_module: Any = None) -> bool:
    backend = _resolve_backend_module(None, backend_module)
    value = utils._safe_text(text)
    if not value:
        return False
    bad_markers = ("Ã", "Â", "Ð", "Ñ", "æ", "ç", "è", "é", "ä", "å", "ï", "ð")
    if not any(marker in value for marker in bad_markers):
        return False
    return not text_utils._contains_cjk(value)


def _repair_mojibake_text(text: Any, *, backend_module: Any = None) -> Any:
    backend = _resolve_backend_module(None, backend_module)
    if isinstance(text, str):
        value = text
        if not _looks_like_utf8_mojibake(value, backend_module=backend):
            return value
        for enc in ("latin-1", "cp1252"):
            try:
                fixed = value.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
            except Exception:
                continue
            if fixed and (text_utils._contains_cjk(fixed) or not _looks_like_utf8_mojibake(fixed, backend_module=backend)):
                return fixed
        return value
    if isinstance(text, list):
        return [_repair_mojibake_text(item, backend_module=backend) for item in text]
    if isinstance(text, dict):
        return {key: _repair_mojibake_text(value, backend_module=backend) for key, value in text.items()}
    return text


def _parse_response_json_robust(resp, *, backend_module: Any = None) -> Any:
    backend = _resolve_backend_module(None, backend_module)
    raw = b""
    try:
        raw = bytes(resp.content or b"")
    except Exception:
        raw = b""

    candidates: list[str] = []
    if raw:
        for enc in ("utf-8", "utf-8-sig", utils._safe_text(getattr(resp, "encoding", "")), "gb18030", "gbk", "latin-1"):
            encoding = utils._safe_text(enc).strip()
            if not encoding:
                continue
            try:
                decoded = raw.decode(encoding)
            except Exception:
                continue
            if decoded and decoded not in candidates:
                candidates.append(decoded)
    try:
        text = utils._safe_text(resp.text)
        if text and text not in candidates:
            candidates.append(text)
    except Exception:
        pass

    for text in candidates:
        payload = safe_json_loads(text, backend_module=backend)
        if isinstance(payload, (dict, list)):
            return _repair_mojibake_text(payload, backend_module=backend)

    payload = resp.json()
    return _repair_mojibake_text(payload, backend_module=backend)


def normalize_chat_completion_url(u: str, *, default_scheme: str = "http") -> str:
    """
    规范化 OpenAI 兼容的 chat/completions URL：
    - 允许填写 127.0.0.1:8317 / localhost:8317 / host:port/v1
    - 自动补协议头（默认 http://）
    - base URL 自动补到 /v1/chat/completions
    """
    value = str(u or "").strip().rstrip("/")
    if not value:
        return ""

    if (not _URL_SCHEME_RE.match(value)) and _HOST_LIKE_URL_RE.match(value):
        value = f"{default_scheme}://{value}"

    lower = value.lower()
    if lower.endswith("/v1/chat/completions") or lower.endswith("/api/v1/chat/completions"):
        return value
    if lower.endswith("/chat/completions"):
        return value
    if lower.endswith("/v1") or lower.endswith("/api/v1"):
        return value + "/chat/completions"

    if _URL_SCHEME_RE.match(value):
        scheme_idx = value.find("://")
        path_start = value.find("/", scheme_idx + 3)
        if path_start == -1:
            return value + "/v1/chat/completions"

    return value


def normalize_api_url(u: str, wire_api: str = "chat_completions", *, default_scheme: str = "http") -> str:
    value = str(u or "").strip().rstrip("/")
    if not value:
        return ""
    if (not _URL_SCHEME_RE.match(value)) and _HOST_LIKE_URL_RE.match(value):
        value = f"{default_scheme}://{value}"
    lower = value.lower()
    wire_api = _normalize_wire_api(wire_api)
    endpoint = {
        "chat_completions": "/v1/chat/completions",
        "responses": "/v1/responses",
        "completions": "/v1/completions",
        "anthropic_messages": "/v1/messages",
    }.get(wire_api, "/v1/chat/completions")
    versioned_suffix = {
        "chat_completions": "/chat/completions",
        "responses": "/responses",
        "completions": "/completions",
        "anthropic_messages": "/messages",
    }.get(wire_api, "/chat/completions")
    if lower.endswith(endpoint) or lower.endswith("/api" + endpoint):
        return value
    if wire_api == "chat_completions" and lower.endswith("/chat/completions"):
        return value
    if wire_api == "completions" and lower.endswith("/completions"):
        return value
    if lower.endswith("/v1") or lower.endswith("/api/v1"):
        return value + versioned_suffix
    if _URL_SCHEME_RE.match(value):
        scheme_idx = value.find("://")
        path_start = value.find("/", scheme_idx + 3)
        if path_start == -1:
            return value + endpoint
    return value


def _normalize_wire_api(value: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in ("responses", "response"):
        return "responses"
    if text in ("completions", "completion", "openai_completions"):
        return "completions"
    if text in ("anthropic_messages", "anthropic", "messages", "anthropic_messages_api"):
        return "anthropic_messages"
    return "chat_completions"


def _build_responses_request_data(cfg: Any, prompt: str) -> dict:
    model = normalize_model_name(cfg.ai_model or "")
    return {
        "model": model,
        "input": prompt,
        "max_output_tokens": getattr(cfg, "ai_max_tokens", 16384),
        "temperature": getattr(cfg, "ai_temperature", 0.1),
        "top_p": getattr(cfg, "ai_top_p", 0.5),
        "store": False,
    }


def _build_completions_request_data(cfg: Any, prompt: str, *, model: str = "") -> dict:
    return {
        "model": model or normalize_model_name(cfg.ai_model or ""),
        "prompt": prompt,
        "max_tokens": getattr(cfg, "ai_max_tokens", 16384),
        "temperature": getattr(cfg, "ai_temperature", 0.1),
        "top_p": getattr(cfg, "ai_top_p", 0.5),
    }



def _build_anthropic_messages_request_data(cfg: Any, prompt: str, *, model: str = "") -> dict:
    data = {
        "model": model or normalize_model_name(cfg.ai_model or ""),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": getattr(cfg, "ai_max_tokens", 16384),
        "temperature": getattr(cfg, "ai_temperature", 0.1),
    }
    return data

def _parse_anthropic_messages_output(js: dict) -> str:
    try:
        content = js.get("content", [])
        if not isinstance(content, list):
            return ""
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return utils._safe_text(block.get("text", ""))
        return ""
    except Exception:
        return ""

def _parse_responses_output(js: dict) -> str:
    try:
        output = js.get("output", [])
        if not output:
            return ""
        for item in output if isinstance(output, list) else [output]:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "output_text":
                        return block.get("text", "")
            elif isinstance(content, dict):
                return content.get("text", "")
        return ""
    except Exception:
        return ""


def _parse_chat_output(js: dict) -> str:
    try:
        choices = js.get("choices", [{}]) if isinstance(js, dict) else [{}]
        if not isinstance(choices, list) or not choices:
            choices = [{}]
        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
        if not isinstance(message, dict):
            message = {}
        return utils._safe_text(message.get("content", ""))
    except Exception:
        return ""


def _parse_completions_output(js: dict) -> str:
    try:
        choices = js.get("choices", [{}]) if isinstance(js, dict) else [{}]
        if not isinstance(choices, list) or not choices:
            choices = [{}]
        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        return utils._safe_text(first_choice.get("text", ""))
    except Exception:
        return ""

_MODEL_NAME_ALIASES = {
    # Qwen 系列（SiliconFlow / 阿里云）
    "qwen/qwen3-32b": "Qwen/Qwen3-32B",
    "qwen/qwen3-14b": "Qwen/Qwen3-14B",
    "qwen/qwen3-8b": "Qwen/Qwen3-8B",
    "qwen/qwen2.5-32b": "Qwen/Qwen2.5-32B-Instruct",
    "qwen/qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
    "qwen/qwen2.5-7b": "Qwen/Qwen2.5-7B-Instruct",
    "qwen3-32b": "Qwen/Qwen3-32B",
    "qwen3-14b": "Qwen/Qwen3-14B",
    "qwen2.5-32b": "Qwen/Qwen2.5-32B-Instruct",
    "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
    # 不存在的版本号修正
    "qwen/qwen3.6-27b": "Qwen/Qwen3-32B",
    "qwen3.6-27b": "Qwen/Qwen3-32B",
    # DeepSeek 系列
    "deepseek/deepseek-chat": "deepseek-ai/DeepSeek-V3",
    "deepseek-chat": "deepseek-ai/DeepSeek-V3",
    # GLM 系列
    "glm-4": "THUDM/glm-4-9b-chat",
}


def normalize_model_name(model: str, *, url: str = "") -> str:
    """
    规范化模型名称，修正常见的命名错误。

    Args:
        model: 用户输入的模型名称
        url: API base URL（用于判断平台）

    Returns:
        规范化后的模型名称
    """
    if not model:
        return model

    raw = str(model).strip()
    lower = raw.lower()
    url_lower = str(url or "").strip().lower()

    # DeepSeek 官方 API 使用 deepseek-chat / deepseek-reasoner / deepseek-v4-* 等原生名称。
    if "api.deepseek.com" in url_lower:
        return raw

    # 1. 精确匹配别名表
    if lower in _MODEL_NAME_ALIASES:
        return _MODEL_NAME_ALIASES[lower]

    # 2. 检查是否已经是正确格式（首字母大写）
    # 如果格式已经是 "Org/Model-Size" 形式，直接返回
    if "/" in raw and raw[0].isupper():
        return raw

    # 3. 尝试自动修正 "org/model" -> "Org/Model"
    if "/" in raw:
        parts = raw.split("/", 1)
        if len(parts) == 2:
            org, name = parts
            # 组织名首字母大写
            org_fixed = org.capitalize() if org else org
            # 模型名保持原样或首字母大写
            if name and name[0].islower():
                # 常见模式：qwen3-32b -> Qwen3-32B
                name_fixed = re.sub(r'\b([a-z])', lambda m: m.group(1).upper(), name)
            else:
                name_fixed = name
            return f"{org_fixed}/{name_fixed}"

    # 4. 无组织前缀，尝试匹配已知模型
    for alias, canonical in _MODEL_NAME_ALIASES.items():
        if "/" not in alias and lower == alias:
            return canonical

    # 5. 无法识别，返回原值
    return raw


def _get_http_session(cfg: Optional[Any] = None, *, backend_module: Any = None):
    requests_mod = _get_requests_module(cfg=cfg, backend_module=backend_module)
    if requests_mod is None:
        return None
    pool_size = max(4, int(getattr(cfg, "ai_workers", 1) or 1))
    session = getattr(_AI_HTTP_LOCAL, "session", None)
    current_pool_size = int(getattr(_AI_HTTP_LOCAL, "pool_size", 0) or 0)
    if session is not None and current_pool_size == pool_size:
        return session

    if session is not None:
        try:
            session.close()
        except Exception:
            pass

    session = requests_mod.Session()
    try:
        session.trust_env = False
    except Exception:
        pass
    try:
        from requests.adapters import HTTPAdapter

        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    except Exception:
        pass

    _AI_HTTP_LOCAL.session = session
    _AI_HTTP_LOCAL.pool_size = pool_size
    return session


def _normalize_proxy_url(raw: Any, *, backend_module: Any = None) -> str:
    backend = _resolve_backend_module(None, backend_module)
    text = utils._safe_strip(raw)
    if not text:
        return ""
    if "://" in text:
        return text
    return "http://" + text


def _default_proxy_candidate_ports(cfg: Optional[Any] = None, *, backend_module: Any = None) -> tuple[str, ...]:
    backend = _resolve_backend_module(cfg, backend_module)
    raw = utils.cfg_get_str(cfg, "proxy_candidate_ports", "7890,7897,7892,9090,8317")
    ports = tuple(
        item
        for item in (
            re.sub(r"[^\d]", "", utils._safe_strip(part))
            for part in str(raw or "").replace(";", ",").split(",")
        )
        if item
    )
    return ports or ("7890", "7897", "7892", "9090", "8317")


def _resolve_proxy_candidates(
    cfg: Optional[Any],
    *,
    provider: str = "",
    url: str = "",
    backend_module: Any = None,
) -> list[tuple[str, str]]:
    backend = _resolve_backend_module(cfg, backend_module)
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(proxy_value: Any, source: str) -> None:
        if source == "direct":
            key = "direct"
            proxy_url = ""
        else:
            proxy_url = _normalize_proxy_url(proxy_value, backend_module=backend)
            if not proxy_url:
                return
            key = proxy_url
        if key in seen:
            return
        seen.add(key)
        candidates.append((proxy_url, source))

    explicit = utils._safe_strip(getattr(cfg, "proxy", ""))
    if explicit:
        add(explicit, "config")

    if not bool(getattr(cfg, "no_proxy", False)):
        prefer_https = str(provider or "").strip().lower() == "openrouter" or str(url or "").strip().lower().startswith("https://")
        env_keys = (
            ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY")
            if prefer_https
            else ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
        )
        for key in env_keys:
            add(os.environ.get(key, ""), f"env:{key.lower()}")
        for port in _default_proxy_candidate_ports(cfg, backend_module=backend):
            add(f"http://127.0.0.1:{port}", f"auto_local:{port}")

    add("", "direct")
    return candidates


def _proxy_dict_for_request(proxy_url: str, *, backend_module: Any = None) -> dict[str, str]:
    target = _normalize_proxy_url(proxy_url, backend_module=backend_module)
    if not target:
        return {}
    return {"http": target, "https": target}


def _ai_retry_sleep_seconds(attempt: int, attempts: int, cfg: Any, *, backend_module: Any = None) -> float:
    if attempt >= attempts:
        return 0.0
    backend = _resolve_backend_module(cfg, backend_module)
    base = utils.cfg_get_float(cfg, "ai_retry_backoff", 1.5)
    if base <= 0:
        base = 1.5
    cap = max(base, utils.cfg_get_float(cfg, "ai_retry_backoff_max", 8.0))
    delay = min(cap, base * max(1, attempt))
    return max(0.0, float(delay))


def _build_curl_repro_command(url: str, headers: dict[str, Any], payload_path: str) -> str:
    parts = ["curl", "-sS", shlex.quote(str(url or ""))]
    for key, value in (headers or {}).items():
        parts.extend(["-H", shlex.quote(f"{key}: {value}")])
    parts.extend(["--data-binary", shlex.quote(f"@{payload_path}")])
    return " ".join(parts)


def _write_ai_repro_bundle(
    cfg: Optional[Any],
    *,
    provider: str,
    url: str,
    headers: dict[str, Any],
    data: dict[str, Any],
    prompt_sha: str,
    reason: str,
    tag: str,
    backend_module: Any = None,
) -> dict[str, str]:
    backend = _resolve_backend_module(cfg, backend_module)
    out: dict[str, str] = {}
    root = os.path.join(os.getcwd(), "ai_repro")
    try:
        os.makedirs(root, exist_ok=True)
        stem = f"{tag}_{(prompt_sha or 'nohash')[:12]}"
        payload_path = os.path.join(root, f"{stem}.json")
        meta_path = os.path.join(root, f"{stem}.meta.json")
        headers_for_curl = dict(headers or {})
        if "Authorization" in headers_for_curl:
            headers_for_curl["Authorization"] = "Bearer YOUR_API_KEY"
        with open(payload_path, "w", encoding="utf-8") as file_obj:
            json.dump(data or {}, file_obj, ensure_ascii=False, indent=2)
        curl_cmd = _build_curl_repro_command(url, headers_for_curl, payload_path)
        meta = {
            "provider": provider,
            "url": url,
            "reason": reason,
            "payload_path": payload_path,
            "curl": curl_cmd,
            "headers_redacted": headers_for_curl,
        }
        with open(meta_path, "w", encoding="utf-8") as file_obj:
            json.dump(meta, file_obj, ensure_ascii=False, indent=2)
        out = {
            "payload_path": payload_path,
            "meta_path": meta_path,
            "curl": curl_cmd,
        }
        try:
            utils.vlog(cfg, f"AI 失败复现文件已写入: {payload_path}")
            utils.vlog(cfg, f"复现命令见: {meta_path}")
        except Exception:
            pass
    except Exception as exc:
        try:
            utils.vlog(cfg, f"写入 AI 复现文件失败: {exc}")
        except Exception:
            pass
    return out


def _post_with_proxy_fallback(
    *,
    session: Any,
    url: str,
    data: dict[str, Any],
    headers: dict[str, str],
    timeout: Any,
    cfg: Optional[Any],
    provider: str,
    attempts: int,
    log_label: str,
    backend_module: Any = None,
) -> tuple[Any, str, dict[str, Any]]:
    """HTTP POST with stop-check polling to allow responsive cancellation.

    Uses threading to allow periodic stop signal checks during HTTP wait.
    The HTTP request runs in a thread; main thread polls for completion
    and stop signal every 0.5 seconds.
    """
    legacy = _resolve_backend_module(cfg, backend_module)
    requests_mod = _get_requests_module(cfg=cfg, backend_module=backend_module)
    last_reason = ""
    last_proxy_meta: dict[str, Any] = {"source": "", "url": ""}
    resolve_proxy_candidates = _get_runtime_hook(legacy, "_resolve_proxy_candidates", _resolve_proxy_candidates)
    proxy_dict_for_request = _get_runtime_hook(legacy, "_proxy_dict_for_request", _proxy_dict_for_request)
    retry_sleep_seconds = _get_runtime_hook(legacy, "_ai_retry_sleep_seconds", _ai_retry_sleep_seconds)
    proxy_candidates = resolve_proxy_candidates(cfg, provider=provider, url=url)

    for proxy_url, proxy_source in proxy_candidates:
        # 检查停止信号
        if utils.stop_requested(cfg):
            return None, "用户取消", dict(last_proxy_meta)
        proxies = proxy_dict_for_request(proxy_url)
        proxy_desc = proxy_url or "DIRECT"
        last_proxy_meta = {"source": proxy_source, "url": proxy_url}
        if proxy_url:
            utils.vlog(cfg, f"{log_label} 使用代理[{proxy_source}]: {proxy_url}")
        elif len(proxy_candidates) > 1:
            utils.vlog(cfg, f"{log_label} 代理候选已用尽，尝试直连")
        for attempt in range(1, attempts + 1):
            # 每次重试前检查停止信号
            if utils.stop_requested(cfg):
                return None, "用户取消", dict(last_proxy_meta)

            # 使用线程执行 HTTP 请求，允许在等待时检查停止信号
            result_container: dict[str, Any] = {"done": False, "resp": None, "exc": None}
            def _do_post():
                try:
                    if session is not None:
                        result_container["resp"] = session.post(url, json=data, headers=headers, timeout=timeout, proxies=proxies)
                    else:
                        result_container["resp"] = requests_mod.post(url, json=data, headers=headers, timeout=timeout, proxies=proxies)
                except Exception as e:
                    result_container["exc"] = e
                result_container["done"] = True

            post_thread = threading.Thread(target=_do_post, daemon=True)
            post_thread.start()

            # 每 0.5 秒检查一次完成状态和停止信号
            poll_interval = 0.5
            while not result_container["done"]:
                if utils.stop_requested(cfg):
                    # 用户取消，等待线程结束（最多 1 秒）后返回
                    post_thread.join(timeout=1.0)
                    return None, "用户取消", dict(last_proxy_meta)
                time.sleep(poll_interval)

            # 线程完成，检查结果
            if result_container["exc"] is not None:
                exc = result_container["exc"]
                last_reason = f"HTTP 调用失败[{proxy_desc}]: {exc}"
                utils.vlog(cfg, last_reason)
                if attempt < attempts:
                    # 检查停止信号
                    if utils.stop_requested(cfg):
                        return None, "用户取消", dict(last_proxy_meta)
                    utils.vlog(cfg, f"AI 重试 {attempt}/{attempts - 1} ...")
                    delay = retry_sleep_seconds(attempt, attempts, cfg)
                    if delay > 0:
                        # 在延迟期间也检查停止信号
                        chunks = int(delay / 0.5) + 1
                        for _ in range(chunks):
                            if utils.stop_requested(cfg):
                                return None, "用户取消", dict(last_proxy_meta)
                            time.sleep(0.5)
                    continue
                break
            else:
                return result_container["resp"], "", dict(last_proxy_meta)
    return None, last_reason, dict(last_proxy_meta)


def _get_ai_http_timeout(cfg: Any, provider: str, *, backend_module: Any = None) -> tuple[float, float]:
    legacy = _resolve_backend_module(cfg, backend_module)
    provider_name = (provider or "").strip().lower()
    default_connect = 10.0
    field_read = float(getattr(cfg, "ai_read_timeout", 0.0) or 0.0)
    default_read = field_read if field_read > 0 else (40.0 if provider_name == "local" else 60.0)
    connect = utils.cfg_get_float(cfg, "ai_connect_timeout", default_connect)
    read = utils.cfg_get_float(cfg, "ai_read_timeout", default_read)
    connect = max(1.0, float(connect or default_connect))
    read = max(5.0, float(read or default_read))
    return connect, read


def _clamp_score(value: Any, *, lo: float = 0.0, hi: float = 0.99) -> float:
    try:
        num = float(value or 0.0)
    except Exception:
        num = 0.0
    if num < lo:
        return lo
    if num > hi:
        return hi
    return num


def _repair_function_desc_by_domain(func_name: str, desc: str, *, current_desc: str = "") -> str:
    value = utils._safe_strip(desc)
    if not value:
        return ""
    ident = utils._safe_strip(func_name).lower()
    context = value + " " + utils._safe_strip(current_desc)
    if (
        re.search(r"write\s*(?:dis|disable)|writedis", ident)
        or "写禁止" in context
        or "写禁用" in context
    ):
        if re.search(r"(?:关闭|关).*写保护|写保护(?:关闭|失能)|写禁关", value):
            return "发送写禁止指令，禁止后续FLASH写入"
    if "spiflash" in ident and "datatrans" in ident:
        if "转换" in value:
            return "通过SPI接口完成FLASH数据交互传输"
    if "refuelstagepreset" in ident:
        return "根据加油模式和目标油箱发送开阀预位命令，并在阀位和泵低压检查后切换加油执行或故障结束状态"
    return value


def _calibrate_function_confidence(
    *,
    func_name: str,
    func_cn_name: str,
    desc: str,
    model_confidence: float,
    fallback_used: bool,
    examples: Sequence[dict[str, Any]],
) -> float:
    legacy = legacy_backend()
    title = utils._safe_strip(func_cn_name)
    desc_text = utils._safe_strip(desc)
    heuristic = 0.18
    if title and text_utils._contains_cjk(title):
        heuristic += 0.28
    compact_len = len(re.sub(r"\s+", "", title))
    if 4 <= compact_len <= 12:
        heuristic += 0.18
    elif compact_len and compact_len <= 16:
        heuristic += 0.10
    if title and not naming_utils.is_explanatory_title(title):
        heuristic += 0.18
    if desc_text and not _looks_like_codeish_description(desc_text):
        heuristic += 0.10
    if examples:
        heuristic += 0.05
        example_titles = {
            utils._safe_strip((item or {}).get("title"))
            for item in (examples or [])
            if utils._safe_strip((item or {}).get("title"))
        }
        if title and title in example_titles:
            heuristic += 0.04
    if fallback_used:
        heuristic -= 0.06
    if title and not text_utils._contains_cjk(title):
        heuristic -= 0.25
    if title and naming_utils.is_explanatory_title(title):
        heuristic -= 0.18
    heuristic = _clamp_score(heuristic)
    model = _clamp_score(model_confidence)
    if model > 0:
        return _clamp_score(model * 0.65 + heuristic * 0.35)
    return heuristic


def _calibrate_symbol_confidence(
    *,
    raw_ident: str,
    cn_name: str,
    usage: str,
    model_confidence: float,
    allow_refine_cn: bool,
    locked_cn: str,
    semantic_context: Optional[dict[str, Any]] = None,
) -> float:
    legacy = legacy_backend()
    name_text = utils._safe_strip(cn_name)
    usage_text = utils._safe_strip(usage)
    heuristic = 0.12
    if locked_cn and not name_text and usage_text:
        heuristic += 0.46
    if name_text:
        heuristic += 0.26
        if not naming_utils.is_generic_symbol_name(name_text):
            heuristic += 0.18
        if text_utils._contains_cjk(name_text):
            heuristic += 0.10
        if legacy._is_strict_symbol_candidate_rejected(name_text, raw_ident=raw_ident):
            heuristic -= 0.30
    if usage_text:
        heuristic += 0.12
        if not legacy._looks_like_generic_local_usage(usage_text):
            heuristic += 0.12
    producer_summary = dict((semantic_context or {}).get("producer_semantic_summary") or {})
    if producer_summary and usage_text:
        heuristic += 0.05
    if not allow_refine_cn and locked_cn and name_text:
        heuristic -= 0.08
    heuristic = _clamp_score(heuristic)
    model = _clamp_score(model_confidence)
    if model > 0:
        return _clamp_score(model * 0.60 + heuristic * 0.40)
    return heuristic


_LOW_VALUE_LOCAL_IDENT_SET = {
    "i", "j", "k", "ii", "jj", "kk",
    "idx", "index", "cnt", "count", "tick",
    "tmp", "temp", "ret", "res", "val", "data", "buf", "item", "flag",
}


def _normalize_local_ident_core(name: str, *, backend_module: Any = None) -> str:
    legacy = _resolve_backend_module(None, backend_module)
    value = utils._safe_strip(name).lower()
    if not value:
        return ""
    for prefix in ("l_", "ls_", "lp_", "lv_", "lt_", "li_", "lu_", "ll_", "tmp_", "local_"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    value = re.sub(r"_(?:u|i)(?:8|16|32|64|6)\b", "", value)
    value = re.sub(r"_(?:f|d|b|bool|ptr|pt|t)\b", "", value)
    return value.strip("_")


def _looks_like_low_value_local_ident(name: str, *, backend_module: Any = None) -> bool:
    core = _normalize_local_ident_core(name, backend_module=backend_module)
    if not core:
        return False
    if core in _LOW_VALUE_LOCAL_IDENT_SET:
        return True
    return bool(re.fullmatch(r"(?:i|j|k){1,2}", core))


def _local_has_strong_non_ai_signal(item: Optional[dict[str, Any]], *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    entry = dict(item or {})
    ident = utils._safe_strip(entry.get("name"))
    for text in (
        entry.get("locked_cn"),
        entry.get("profile_cn_candidate"),
        entry.get("cn_name"),
        entry.get("role_hint"),
        entry.get("comment_hint"),
    ):
        value = utils._safe_strip(text)
        if not value:
            continue
        if value == ident:
            continue
        if legacy._looks_like_generic_local_cn_name(value) or legacy._looks_like_low_quality_symbol_cn(value, raw_ident=ident):
            continue
        return True
    return False


def _should_track_local_ai_gap(item: Optional[dict[str, Any]], *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    entry = dict(item or {})
    ident = utils._safe_strip(entry.get("name"))
    if not ident:
        return False
    if (not legacy._local_var_needs_ai_upgrade(entry)) and (not bool(entry.get("allow_refine_cn"))):
        return False
    if _looks_like_low_value_local_ident(ident, backend_module=legacy) and (not _local_has_strong_non_ai_signal(entry, backend_module=legacy)):
        return False
    return True


def _should_request_local_ai_candidate(
    item: Optional[dict[str, Any]],
    *,
    evidence: Any = None,
    inference: Any = None,
    candidate_concepts: Optional[Sequence[str]] = None,
    semantic_context: Optional[dict[str, Any]] = None,
    retrieved_examples: Optional[Sequence[Any]] = None,
    backend_module: Any = None,
) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    entry = dict(item or {})
    ident = utils._safe_strip(entry.get("name"))
    if not _should_track_local_ai_gap(entry, backend_module=legacy):
        return False
    if not _looks_like_low_value_local_ident(ident, backend_module=legacy):
        return True
    if _local_has_strong_non_ai_signal(entry, backend_module=legacy):
        return True
    evidence_score = 0
    producer_call = utils._safe_strip(getattr(evidence, "producer_call", ""))
    producer_kind = utils._safe_strip(getattr(evidence, "producer_kind", ""))
    if producer_call or producer_kind:
        evidence_score += 2
    role = utils._safe_strip(getattr(inference, "role", ""))
    if role and role not in {"索引", "计数器", "标志", "中间量", "当前值", "上一周期值", "缓存值", "返回值"}:
        evidence_score += 1
    if list(candidate_concepts or []):
        evidence_score += 1
    semantic = dict(semantic_context or {})
    if semantic.get("producer_semantic_summary") or semantic.get("project_concepts") or semantic.get("retrieved_examples"):
        evidence_score += 1
    if list(retrieved_examples or []):
        evidence_score += 1
    return evidence_score >= 2


def _collect_local_ai_support_labels(
    item: Optional[dict[str, Any]],
    *,
    semantic_context: Optional[dict[str, Any]] = None,
    candidate_concepts: Optional[Sequence[str]] = None,
    retrieved_examples: Optional[Sequence[Any]] = None,
    backend_module: Any = None,
) -> list[str]:
    legacy = _resolve_backend_module(None, backend_module)
    entry = dict(item or {})
    labels: list[str] = []

    def append_label(value: Any) -> None:
        text = utils._safe_strip(value)
        if (
            (not text)
            or (text in labels)
            or legacy._looks_like_generic_local_cn_name(text)
            or legacy._looks_like_low_quality_symbol_cn(text, raw_ident=utils._safe_strip(entry.get("name")))
            or naming_utils.is_explanatory_title(text)
        ):
            return
        labels.append(text)

    def append_code_terms(value: Any, *, as_buffer: bool = False) -> None:
        text = utils._safe_strip(value)
        if not text:
            return
        guessed = utils._safe_strip(legacy._guess_cn_from_ident(text))
        guessed = re.sub(r"(?:读取|获取|取得|检查|校验|设置|写入|返回|计算|转换|更新|处理|函数)$", "", guessed)
        guessed = re.sub(r"^(?:读取|获取|取得|检查|校验|设置|写入|返回|计算|转换|更新|处理)", "", guessed)
        guessed = guessed.replace("函数", "")
        for term in ("状态", "模式", "故障", "错误", "有效", "指令", "命令", "输出", "输入", "结果", "位图", "标志"):
            if term in guessed:
                append_label(f"{term}缓存" if as_buffer and term not in {"输出", "输入"} else term)
                append_label(f"{term}值")
                if term in {"故障", "错误", "有效"}:
                    append_label(f"{term}标志")

    for key in ("locked_cn", "profile_cn_candidate", "role_hint", "comment_hint", "cn_name"):
        append_label(entry.get(key))
    for value in (candidate_concepts or []):
        append_label(value)
    semantic = dict(semantic_context or {})
    for key in ("project_terms", "project_concepts", "aliases"):
        values = semantic.get(key)
        if isinstance(values, (list, tuple)):
            for value in values:
                if isinstance(value, dict):
                    append_label(value.get("cn") or value.get("text") or value.get("name"))
                else:
                    append_label(value)
    producer_summary = dict(semantic.get("producer_semantic_summary") or {})
    for key in ("title", "role_summary", "desc", "summary", "usage"):
        append_label(producer_summary.get(key))
    for record in (retrieved_examples or []):
        if isinstance(record, dict):
            append_label(record.get("existing_cn"))
            append_label(record.get("title"))
    usage_summary = dict(entry.get("usage_summary") or {})
    for key in ("assigned_from", "conditions", "call_args", "returns", "bit_ops"):
        for value in list(usage_summary.get(key) or [])[:4]:
            append_code_terms(value, as_buffer=(key == "assigned_from"))
    for value in list(usage_summary.get("assigned_to") or [])[:4]:
        append_code_terms(value)
    for value in list(entry.get("local_window") or [])[:4]:
        append_code_terms(value, as_buffer=True)
    return labels[:12]


def _should_accept_local_ai_cn_result(
    raw_ident: str,
    *,
    item: Optional[dict[str, Any]] = None,
    candidate_cn: str,
    semantic_context: Optional[dict[str, Any]] = None,
    candidate_concepts: Optional[Sequence[str]] = None,
    retrieved_examples: Optional[Sequence[Any]] = None,
    backend_module: Any = None,
) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    ident = utils._safe_strip(raw_ident)
    candidate = utils._safe_strip(candidate_cn)
    if not candidate:
        return False
    if naming_utils.is_generic_symbol_name(candidate):
        return False
    if legacy._is_strict_symbol_candidate_rejected(candidate, raw_ident=ident):
        return False
    if legacy._looks_like_low_quality_symbol_cn(candidate, raw_ident=ident):
        return False
    decl_type = utils._safe_strip((item or {}).get("type")).lower()
    ident_lower = ident.lower()
    compact_candidate = re.sub(r"\s+", "", candidate)
    if any(token in decl_type for token in ("1553b", "pmfl", "revdef")) and re.search(r"\d{3}", decl_type + ident_lower):
        if ("打包" not in compact_candidate) and ("输出" not in compact_candidate) and ("数据字" not in compact_candidate):
            return False
    if "compat" in ident_lower:
        if any(token in compact_candidate for token in ("缓存值", "临时变量", "仲裁结果", "执行状态")):
            return False
    if ident_lower.endswith(("srcerr_u16", "modeerr_u16")) or ident_lower.endswith(("err_u16", "flag_u16")):
        if len(compact_candidate) >= 9 and (not compact_candidate.endswith(("标志", "错误", "状态", "结果"))):
            return False

    support_labels = _collect_local_ai_support_labels(
        item,
        semantic_context=semantic_context,
        candidate_concepts=candidate_concepts,
        retrieved_examples=retrieved_examples,
        backend_module=legacy,
    )
    coverage = legacy._candidate_ident_semantic_coverage(candidate, ident)
    support_score = 0
    exact_match = False
    partial_match = False
    for label in support_labels:
        compact_label = re.sub(r"\s+", "", utils._safe_strip(label))
        if not compact_label:
            continue
        if compact_candidate == compact_label:
            exact_match = True
            support_score += 3
            continue
        if compact_candidate in compact_label or compact_label in compact_candidate:
            partial_match = True
            support_score += 2
    semantic = dict(semantic_context or {})
    if dict(semantic.get("producer_semantic_summary") or {}):
        support_score += 1
    if list(candidate_concepts or []):
        support_score += 1
    if list(retrieved_examples or []):
        support_score += 1

    usage_summary = dict((item or {}).get("usage_summary") or {})
    strong_usage_support = bool(
        list(usage_summary.get("assigned_from") or [])
        and (
            list(usage_summary.get("assigned_to") or [])
            or list(usage_summary.get("conditions") or [])
            or list(usage_summary.get("call_args") or [])
            or list(usage_summary.get("returns") or [])
        )
        and (support_score >= 2)
    )

    if _looks_like_low_value_local_ident(ident, backend_module=legacy):
        return bool(exact_match or (support_score >= 4 and (coverage >= 1 or partial_match)))
    if exact_match:
        return True
    if coverage >= 2:
        return True
    if coverage >= 1 and (support_score >= 2 or partial_match):
        return True
    if strong_usage_support and partial_match:
        return True
    return support_score >= 4


def _safe_textish(value: Any) -> str:
    legacy = legacy_backend()
    if isinstance(value, str):
        return utils._safe_strip(value)
    if isinstance(value, (int, float)):
        return utils._safe_strip(value)
    if isinstance(value, list):
        parts = [_safe_textish(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "cond_cn", "cn", "desc", "usage"):
            if key in value:
                return _safe_textish(value.get(key))
        parts = [_safe_textish(item) for item in value.values()]
        return " ".join(part for part in parts if part)
    return ""


def _looks_like_codeish_description(text: str) -> bool:
    legacy = legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return False
    pseudo_checker = getattr(legacy, "_looks_like_pseudo_function_desc", None)
    if callable(pseudo_checker) and pseudo_checker(value):
        return True
    if _CODEISH_RE.search(value):
        return True
    if ";" in value or "{" in value or "}" in value:
        return True
    return False


def _compact_project_concepts(
    items: Sequence[dict[str, Any]],
    *,
    func_name: str = "",
    family_prefix: str = "",
    limit: int = 4,
) -> list[dict[str, Any]]:
    legacy = legacy_backend()
    func_text = utils._safe_strip(func_name)
    family_text = utils._safe_strip(family_prefix)
    selected: list[tuple[tuple[int, float, int, str], dict[str, Any]]] = []
    for raw in (items or ()):
        item = dict(raw or {})
        alias = utils._safe_strip(item.get("alias"))
        concept = utils._safe_strip(item.get("concept"))
        if not alias or not concept:
            continue
        is_primary = bool(item.get("is_primary")) or (alias and alias in func_text) or (family_text and alias == family_text)
        if (not is_primary) and float(item.get("confidence", 0.0) or 0.0) < 0.72:
            continue
        compact = {
            "alias": alias,
            "concept": concept,
            "confidence": float(item.get("confidence", 0.0) or 0.0),
        }
        score = (
            int(is_primary),
            compact["confidence"],
            int(item.get("evidence_count", 0) or 0),
            alias,
        )
        selected.append((score, compact))
    selected.sort(key=lambda pair: (-pair[0][0], -pair[0][1], -pair[0][2], pair[0][3]))
    return [item for _score, item in selected[:limit]]


def _sanitize_ai_desc(desc: str, body: str, glossary_terms=None) -> str:
    """Post-process AI-generated function description: scrub hallucinated numbers
    and macro expansions that cannot be found in the source body."""
    text = utils._safe_strip(desc)
    if not text:
        return desc
    body_nums = set(re.findall(r"\\b\\d+\\b", body or ""))
    body_idents = set(re.findall(r"\\b[A-Za-z_][A-Za-z0-9_]{3,}\\b", body or ""))

    def _strip_num(m):
        num = m.group(1)
        if num in body_nums:
            return m.group(0)
        return "循环"
    out = re.sub(r"(\\d+)\\s*倍", _strip_num, text)
    out = re.sub(r"(\\d+)\\s*次", _strip_num, out)

    def _fix_macro_split(m):
        full = m.group(0)
        if full in body or any(full in ident for ident in body_idents):
            return full
        return "扩展页"
    out = re.sub(r"COMM[A-Z]*bit\\d+", _fix_macro_split, out)
    return out


def _fallback_function_description(func_info: Optional[dict[str, Any]], body: str, *, current_desc: str = "") -> str:
    legacy = legacy_backend()
    current = utils._safe_strip(current_desc)
    if current and not _looks_like_codeish_description(current):
        return current
    func_name = utils._safe_strip((func_info or {}).get("func_name"))
    body_text = utils._safe_text(body)
    func_name_lower = func_name.lower()
    body_lower = body_text.lower()
    receive_markers = ("rx", "recv", "receive", "read", "unpack", "checksum", "msgcnt")
    monitor_markers = ("mon", "monitor", "fault", "status", "bitupdate", "recordfault", "updatestatus")
    if (
        any(token in func_name_lower for token in ("isr", "ack"))
        and ("pieack" in body_lower or "intclr" in body_lower)
    ):
        if "sci" in func_name_lower or "sciff" in body_lower:
            return "清除SCI接收FIFO中断标志并应答PIE控制器"
        return "清除中断标志并应答中断控制器"
    if any(token in func_name_lower for token in ("rx", "receive", "recv", "proc")) and any(token in body_lower for token in receive_markers):
        return "读取并校验输入数据，完成解包、状态刷新及异常处理"
    if any(token in func_name_lower for token in ("mon", "monitor", "status")) and any(token in body_lower for token in monitor_markers):
        return "汇总监测结果，更新状态标志、故障信息及相关记录"
    if any(token in body_lower for token in receive_markers):
        return "读取并校验输入数据，完成解包、状态刷新及异常处理"
    if any(token in body_lower for token in monitor_markers):
        return "汇总监测结果，更新状态标志、故障信息及相关记录"
    compact = legacy._extract_compact_function_title(current)
    if compact:
        return compact
    guessed = legacy._compose_short_function_title(func_name, current, "")
    if guessed:
        return guessed
    if func_name:
        return f"基于函数名 {func_name} 执行功能处理（描述信息不足，需人工补充）"
    return "执行功能处理（描述信息不足，需人工补充）"


def _infer_ai_profile_from_model_name(model_name: str) -> str:
    text = utils._safe_strip(model_name).lower()
    if not text:
        return ""
    if any(token in text for token in ("32b", "34b", "70b", "72b", "deepseekr1", "gpt-5", "gpt-4", "claude-3.7", "claude-4")):
        return "large"
    if any(token in text for token in ("7b", "8b", "mini", "small", "qwen-2.5-7b", "1.5b", "3b")):
        return "small"
    return ""


def _get_ai_capability_profile(cfg: Optional[Any]) -> str:
    legacy = legacy_backend()
    explicit = legacy._normalize_ai_profile_label(getattr(cfg, "ai_profile", ""))
    if explicit:
        return explicit
    explicit = legacy._normalize_ai_profile_label(utils.cfg_get_str(cfg, "ai_profile", ""))
    if explicit:
        return explicit
    inferred = _infer_ai_profile_from_model_name(getattr(cfg, "ai_model", ""))
    if inferred:
        return inferred
    return "small"


def _small_model_prompt_mode(cfg: Optional[Any], *, backend_module: Any = None) -> str:
    backend = _resolve_backend_module(cfg, backend_module)
    explicit = utils.cfg_get_str(cfg, "small_model_prompt_mode", "")
    if explicit:
        return explicit
    if _get_ai_capability_profile(cfg) == "small":
        return "strict_compact"
    return "default"


def _is_small_model_strict_mode(cfg: Optional[Any], *, backend_module: Any = None) -> bool:
    return _small_model_prompt_mode(cfg, backend_module=backend_module) == "strict_compact"


def _small_model_bool(cfg: Optional[Any], key: str, default: int, *, backend_module: Any = None) -> bool:
    backend = _resolve_backend_module(cfg, backend_module)
    return bool(utils.cfg_get_int(cfg, key, default))


def call_llm_json(
    prompt: str,
    cfg: Any,
    *,
    log_title: str = "LLM 输出(完整)",
    log_preview: bool = True,
    log_full_output: bool = True,
    _runtime_module: Any = None,
    **_ignored: Any,
):
    legacy = _resolve_backend_module(cfg, _runtime_module)
    make_ai_cache_key = _get_runtime_hook(_runtime_module, "_make_ai_cache_key", _make_ai_cache_key)
    ai_cache_get = _get_runtime_hook(_runtime_module, "_ai_cache_get", _ai_cache_get)
    ai_cache_set = _get_runtime_hook(_runtime_module, "_ai_cache_set", _ai_cache_set)
    if _runtime_module is not None and callable(getattr(_runtime_module, "_write_ai_repro_bundle", None)):
        write_ai_repro_bundle = _runtime_module._write_ai_repro_bundle
    else:
        write_ai_repro_bundle = lambda *args, **kwargs: _write_ai_repro_bundle(
            *args,
            backend_module=legacy,
            **kwargs,
        )
    requests_mod = _get_requests_module(cfg=cfg, backend_module=legacy)

    if not cfg.ai_assist:
        utils._set_last_llm_json_debug(cfg, {"error": "ai_disabled", "prompt_sha256": ""})
        return {}
    if getattr(cfg, "ai_circuit_break", False):
        utils._set_last_llm_json_debug(cfg, {"error": "ai_circuit_break", "prompt_sha256": ""})
        return {}
    if getattr(cfg, "_skip_ai_current_func", False):
        utils._set_last_llm_json_debug(cfg, {"error": "skip_current_func", "prompt_sha256": ""})
        return {}
    # 用户已取消时，短路后续所有 AI 调用
    if getattr(cfg, "_user_cancelled", False) or utils.stop_requested(cfg):
        utils._set_last_llm_json_debug(cfg, {"error": "user_cancelled", "prompt_sha256": ""})
        return {}
    if requests_mod is None:
        utils.vlog(cfg, "WARNING: requests 未安装，跳过 AI 调用")
        utils._set_last_llm_json_debug(cfg, {"error": "requests_missing", "prompt_sha256": ""})
        return {}

    provider = (cfg.ai_provider or "local").strip().lower()
    _ep_json = dict(getattr(cfg, "extra_params", {}) or {})
    wire_api = _normalize_wire_api(_ep_json.get("wire_api", "") or getattr(cfg, "wire_api", "") or "chat_completions")
    headers = {"Content-Type": "application/json"}
    api_key = utils._safe_strip(cfg.ai_api_key)
    url = utils._safe_strip(cfg.ai_api_base)

    if provider == "openrouter":
        if not url:
            url = "http://10.11.34.200:11434/v1/chat/completions"
        url = normalize_api_url(url, wire_api)
    else:
        if not url:
            utils.vlog(cfg, "ERROR: 需要配置 AI Base（例如 http://10.11.34.200:11434/v1）")
            return {}
        url = normalize_api_url(url, wire_api)

    if wire_api == "anthropic_messages":
        if api_key:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers = _apply_compat_request_headers(headers, cfg, backend_module=legacy)
    # 规范化模型名称，修正常见错误
    normalized_model = normalize_model_name(cfg.ai_model, url=url)
    if normalized_model != cfg.ai_model:
        utils.vlog(cfg, f"模型名称已修正: {cfg.ai_model} -> {normalized_model}")

    # 规范化模型名称，修正常见错误
    if wire_api == "responses":
        data = _build_responses_request_data(cfg, prompt)
    elif wire_api == "completions":
        data = _build_completions_request_data(cfg, prompt, model=normalized_model)
    elif wire_api == "anthropic_messages":
        data = _build_anthropic_messages_request_data(cfg, prompt, model=normalized_model)
    else:
        data = {
            "model": normalized_model,
            "temperature": cfg.ai_temperature,
            "top_p": cfg.ai_top_p,
            "max_tokens": cfg.ai_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if provider == "local" and getattr(cfg, "ai_num_ctx", 0):
            data["options"] = {"num_ctx": int(cfg.ai_num_ctx)}

    try:
        prompt_sha = hashlib.sha256((prompt or "").encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        prompt_sha = ""
    auth_circuit_key = _make_ai_auth_circuit_key(provider, url, normalized_model, wire_api, api_key)
    if _skip_due_to_ai_auth_circuit(cfg, auth_circuit_key):
        utils._set_last_llm_json_debug(cfg, {
            "provider": provider,
            "url": url,
            "prompt_sha256": prompt_sha,
            "from_cache": False,
            "error": "ai_auth_circuit_break",
        })
        return {}
    cache_key = make_ai_cache_key("json", prompt, cfg, provider, url)
    cached = ai_cache_get(cache_key, clone=True)
    if cached is not _CACHE_MISS:
        try:
            setattr(cfg, "_ai_last_error", "")
        except Exception:
            pass
        parsed_keys = tuple(str(k) for k in cached.keys()) if isinstance(cached, dict) else ()
        utils._set_last_llm_json_debug(cfg, {
            "provider": provider,
            "url": url,
            "prompt_sha256": prompt_sha,
            "from_cache": True,
            "parsed_type": type(cached).__name__,
            "parsed_keys": parsed_keys,
            "parsed_preview": utils._debug_preview_json(cached),
        })
        utils.vlog(cfg, f"AI 缓存命中 provider={provider}, model={cfg.ai_model}")
        return cached or {}
    utils.ai_debug_log(cfg, "llm_request", {
        "provider": provider,
        "url": url,
        "headers": utils._redact_headers(headers),
        "data_meta": {
            "model": data.get("model"),
            "temperature": data.get("temperature"),
            "top_p": data.get("top_p"),
            "max_tokens": data.get("max_tokens"),
            "has_options": bool(data.get("options")),
        },
        "prompt_len": len(prompt or ""),
        "prompt_sha256": prompt_sha,
        "prompt_head": utils._truncate_for_log(cfg, (prompt or "")[:4000]),
        "prompt_tail": utils._truncate_for_log(cfg, (prompt or "")[-4000:]),
    })

    utils.vlog(cfg, f"调用模型 provider={provider}, model={cfg.ai_model}")

    def _mark_ai_failure(reason: str) -> None:
        _mark_ai_failure_state(cfg, reason)

    def _handle_ai_failure(reason: str) -> dict[str, Any]:
        _mark_ai_failure(reason)
        policy = utils.cfg_get_str(
            cfg,
            "ai_fail_policy",
            str(getattr(cfg, "ai_fail_policy", "fallback") or "fallback"),
        ).strip().lower()
        if policy == "circuit_fallback":
            cfg.ai_circuit_break = True
            try:
                utils.vlog(cfg, "AI 失败，已熔断：后续将继续纯规则生成")
            except Exception:
                pass
            utils.gui_event(cfg, {"type": "ai_circuit_break", "reason": reason})
            return {}
        if policy == "skip_function" and getattr(cfg, "_in_func_context", False):
            try:
                setattr(cfg, "_skip_ai_current_func", True)
            except Exception:
                pass
            try:
                utils.vlog(cfg, "AI 失败，已跳过当前函数的后续 AI 调用：", reason)
            except Exception:
                pass
            utils.gui_event(cfg, {"type": "ai_skip_current_func", "reason": reason})
            return {}
        return {}

    attempts = 1 + max(
        0,
        int(utils.cfg_get_int(cfg, "ai_retry_times", int(getattr(cfg, "ai_retry_times", 0) or 0))),
    )
    if _runtime_module is not None and callable(getattr(_runtime_module, "_get_http_session", None)):
        session = _runtime_module._get_http_session(cfg)
    else:
        session = _get_http_session(cfg, backend_module=legacy)
    if _runtime_module is not None and callable(getattr(_runtime_module, "_get_ai_http_timeout", None)):
        timeout = _runtime_module._get_ai_http_timeout(cfg, provider)
    else:
        timeout = _get_ai_http_timeout(cfg, provider, backend_module=legacy)
    if _runtime_module is not None and callable(getattr(_runtime_module, "_post_with_proxy_fallback", None)):
        resp, transport_error, proxy_meta = _runtime_module._post_with_proxy_fallback(
            session=session,
            url=url,
            data=data,
            headers=headers,
            timeout=timeout,
            cfg=cfg,
            provider=provider,
            attempts=attempts,
            log_label="LLM JSON",
        )
    else:
        resp, transport_error, proxy_meta = _post_with_proxy_fallback(
            session=session,
            url=url,
            data=data,
            headers=headers,
            timeout=timeout,
            cfg=cfg,
            provider=provider,
            attempts=attempts,
            log_label="LLM JSON",
            backend_module=legacy,
        )
    if resp is None:
        # 用户取消时直接返回，不记录错误日志
        if transport_error == "用户取消":
            utils.vlog(cfg, "AI 调用已取消")
            try:
                setattr(cfg, "_user_cancelled", True)
            except Exception:
                pass
            return _handle_ai_failure("用户取消")
        last_reason = transport_error or "HTTP 调用失败"
        utils._set_last_llm_json_debug(cfg, {
            "provider": provider,
            "url": url,
            "prompt_sha256": prompt_sha,
            "from_cache": False,
            "error": last_reason,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        utils.ai_debug_log(cfg, "llm_http_error", {
            "provider": provider,
            "url": url,
            "error": last_reason,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        repro = write_ai_repro_bundle(
            cfg,
            provider=provider,
            url=url,
            headers=headers,
            data=data,
            prompt_sha=prompt_sha,
            reason=last_reason,
            tag="llm_json",
        )
        utils.write_error_log("llm_http_error", {
            "provider": provider,
            "url": url,
            "error": last_reason,
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            **repro,
        })
        return _handle_ai_failure(last_reason)

    for _attempt in range(1, 2):
        if resp.status_code >= 400:
            is_auth_failure = _is_ai_auth_failure_status(resp.status_code)
            last_reason = (
                f"LLM 鉴权失败: {resp.status_code}"
                if is_auth_failure
                else f"LLM 错误: {resp.status_code}"
            )
            utils.vlog(cfg, f"{last_reason} {resp.text[:200]}")
            utils._set_last_llm_json_debug(cfg, {
                "provider": provider,
                "url": url,
                "prompt_sha256": prompt_sha,
                "from_cache": False,
                "error": last_reason,
                "raw_content": utils._debug_preview_json(resp.text or "", max_len=2000),
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            })
            utils.ai_debug_log(cfg, "llm_http_non_200", {
                "provider": provider,
                "url": url,
                "status_code": resp.status_code,
                "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
                "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            })
            utils.write_error_log("llm_http_non_200", {
                "provider": provider,
                "url": url,
                "status_code": resp.status_code,
                "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
                "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
                "model": cfg.ai_model,
                "prompt_sha256": prompt_sha,
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
                **write_ai_repro_bundle(
                    cfg,
                    provider=provider,
                    url=url,
                    headers=headers,
                    data=data,
                    prompt_sha=prompt_sha,
                    reason=last_reason,
                    tag="llm_json",
                ),
            })
            if is_auth_failure:
                _mark_ai_auth_failure(cfg, last_reason, circuit_key=auth_circuit_key)
                return {}
            return _handle_ai_failure(last_reason)

        try:
            js = _parse_response_json_robust(resp, backend_module=legacy)
            break
        except Exception:
            last_reason = "响应 JSON 解析失败"
            utils.vlog(cfg, last_reason)
            utils._set_last_llm_json_debug(cfg, {
                "provider": provider,
                "url": url,
                "prompt_sha256": prompt_sha,
                "from_cache": False,
                "error": last_reason,
                "raw_content": utils._debug_preview_json(resp.text or "", max_len=2000),
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            })
            utils.ai_debug_log(cfg, "llm_response_json_parse_failed", {
                "provider": provider,
                "url": url,
                "status_code": resp.status_code,
                "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
                "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            })
            utils.write_error_log("llm_response_json_parse_failed", {
                "provider": provider,
                "url": url,
                "status_code": resp.status_code,
                "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
                "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
                "model": cfg.ai_model,
                "prompt_sha256": prompt_sha,
                "proxy_source": utils._safe_strip(proxy_meta.get("source")),
                "proxy_url": utils._safe_strip(proxy_meta.get("url")),
                **write_ai_repro_bundle(
                    cfg,
                    provider=provider,
                    url=url,
                    headers=headers,
                    data=data,
                    prompt_sha=prompt_sha,
                    reason=last_reason,
                    tag="llm_json",
                ),
            })
            return _handle_ai_failure(last_reason)

    try:
        setattr(cfg, "_ai_last_error", "")
    except Exception:
        pass

    if wire_api == "responses":
        content = _parse_responses_output(js)
    elif wire_api == "completions":
        content = _parse_completions_output(js)
    elif wire_api == "anthropic_messages":
        content = _parse_anthropic_messages_output(js)
    else:
        content = _parse_chat_output(js)

    if not content:
        utils._set_last_llm_json_debug(cfg, {
            "provider": provider,
            "url": url,
            "prompt_sha256": prompt_sha,
            "from_cache": False,
            "error": "empty_content",
            "parsed_type": type(js).__name__,
            "parsed_keys": tuple(str(k) for k in js.keys()) if isinstance(js, dict) else (),
            "parsed_preview": utils._debug_preview_json(js),
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        return {}

    raw = content
    content = strip_think_blocks(raw, backend_module=legacy)
    if raw != content:
        utils.vlog(cfg, "LLM 输出包含 <think>，已移除")

    parsed = safe_json_loads(content, backend_module=legacy)
    pretty_for_log = content
    if isinstance(parsed, (dict, list)):
        try:
            pretty_for_log = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pretty_for_log = content

    if log_preview:
        preview = (pretty_for_log[:200] or "").replace("\r", "").replace("\n", "\\n")
        utils.vlog(cfg, "LLM 输出(预览):", preview)

    if log_full_output:
        title = (log_title or "LLM 输出(完整)").strip()
        utils._tool_log_write_block(cfg, title, pretty_for_log)

    if parsed is None:
        utils._set_last_llm_json_debug(cfg, {
            "provider": provider,
            "url": url,
            "prompt_sha256": prompt_sha,
            "from_cache": False,
            "error": "content_parse_failed",
            "raw_content": utils._debug_preview_json(raw or "", max_len=2000),
            "content": utils._debug_preview_json(content or "", max_len=2000),
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        utils.ai_debug_log(cfg, "llm_content_parse_failed", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "content_head": utils._truncate_for_log(cfg, (content or "")[:20000]),
            "content_tail": utils._truncate_for_log(cfg, (content or "")[-20000:]),
            "raw_content_head": utils._truncate_for_log(cfg, (raw or "")[:20000]),
            "raw_content_tail": utils._truncate_for_log(cfg, (raw or "")[-20000:]),
        })
        utils.write_error_log("llm_content_parse_failed", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "content_head": utils._truncate_for_log(cfg, (content or "")[:20000]),
            "content_tail": utils._truncate_for_log(cfg, (content or "")[-20000:]),
            "raw_content_head": utils._truncate_for_log(cfg, (raw or "")[:20000]),
            "raw_content_tail": utils._truncate_for_log(cfg, (raw or "")[-20000:]),
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
        })
        return {}

    if not isinstance(parsed, (dict, list)):
        utils.ai_debug_log(cfg, "llm_content_unexpected_type", {
            "provider": provider,
            "url": url,
            "parsed_type": type(parsed).__name__,
            "parsed_preview": utils._truncate_for_log(cfg, repr(parsed)),
        })
        utils.write_error_log("llm_content_unexpected_type", {
            "provider": provider,
            "url": url,
            "parsed_type": type(parsed).__name__,
            "parsed_preview": utils._truncate_for_log(cfg, repr(parsed)),
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
        })
    utils._set_last_llm_json_debug(cfg, {
        "provider": provider,
        "url": url,
        "prompt_sha256": prompt_sha,
        "from_cache": False,
        "error": "",
        "raw_content": utils._debug_preview_json(raw or "", max_len=2000),
        "content": utils._debug_preview_json(content or "", max_len=2000),
        "parsed_type": type(parsed).__name__,
        "parsed_keys": tuple(str(k) for k in parsed.keys()) if isinstance(parsed, dict) else (),
        "parsed_preview": utils._debug_preview_json(parsed),
        "proxy_source": utils._safe_strip(proxy_meta.get("source")),
        "proxy_url": utils._safe_strip(proxy_meta.get("url")),
    })
    result = parsed or {}
    if isinstance(result, (dict, list)):
        ai_cache_set(cache_key, result, clone=True)
    return result


def call_llm_text(
    prompt: str,
    cfg: Any,
    *,
    _runtime_module: Any = None,
    **_ignored: Any,
) -> str:
    legacy = _resolve_backend_module(cfg, _runtime_module)
    make_ai_cache_key = _get_runtime_hook(_runtime_module, "_make_ai_cache_key", _make_ai_cache_key)
    ai_cache_get = _get_runtime_hook(_runtime_module, "_ai_cache_get", _ai_cache_get)
    ai_cache_set = _get_runtime_hook(_runtime_module, "_ai_cache_set", _ai_cache_set)
    if _runtime_module is not None and callable(getattr(_runtime_module, "_write_ai_repro_bundle", None)):
        write_ai_repro_bundle = _runtime_module._write_ai_repro_bundle
    else:
        write_ai_repro_bundle = lambda *args, **kwargs: _write_ai_repro_bundle(
            *args,
            backend_module=legacy,
            **kwargs,
        )
    requests_mod = _get_requests_module(cfg=cfg, backend_module=legacy)

    if not cfg.ai_assist:
        return ""
    if getattr(cfg, "ai_circuit_break", False):
        return ""
    if getattr(cfg, "_skip_ai_current_func", False):
        return ""
    # 用户已取消时，短路后续所有 AI 调用
    if getattr(cfg, "_user_cancelled", False) or utils.stop_requested(cfg):
        return ""
    if requests_mod is None:
        utils.vlog(cfg, "WARNING: requests 未安装，跳过 AI 调用")
        return ""

    provider = (cfg.ai_provider or "local").strip().lower()
    _ep_txt = dict(getattr(cfg, "extra_params", {}) or {})
    wire_api = _normalize_wire_api(_ep_txt.get("wire_api", "") or getattr(cfg, "wire_api", "") or "chat_completions")
    headers = {"Content-Type": "application/json"}
    api_key = utils._safe_strip(cfg.ai_api_key)
    url = utils._safe_strip(cfg.ai_api_base)

    if provider == "openrouter":
        if not url:
            url = "http://10.11.34.200:11434/v1/chat/completions"
        url = normalize_api_url(url, wire_api)
    else:
        if not url:
            utils.vlog(cfg, "ERROR: 需要配置 AI Base（例如 http://10.11.34.200:11434/v1）")
            return ""
        url = normalize_api_url(url, wire_api)
    if wire_api == "anthropic_messages":
        if api_key:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers = _apply_compat_request_headers(headers, cfg, backend_module=legacy)

    # 规范化模型名称，修正常见错误
    normalized_model = normalize_model_name(cfg.ai_model, url=url)
    if normalized_model != cfg.ai_model:
        utils.vlog(cfg, f"模型名称已修正: {cfg.ai_model} -> {normalized_model}")

    if wire_api == "responses":
        data = _build_responses_request_data(cfg, prompt)
    elif wire_api == "completions":
        data = _build_completions_request_data(cfg, prompt, model=normalized_model)
    elif wire_api == "anthropic_messages":
        data = _build_anthropic_messages_request_data(cfg, prompt, model=normalized_model)
    else:
        data = {
            "model": normalized_model,
            "temperature": cfg.ai_temperature,
            "top_p": cfg.ai_top_p,
            "max_tokens": cfg.ai_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    if provider == "local" and getattr(cfg, "ai_num_ctx", 0):
        data["options"] = {"num_ctx": int(cfg.ai_num_ctx)}
    try:
        prompt_sha = hashlib.sha256((prompt or "").encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        prompt_sha = ""
    auth_circuit_key = _make_ai_auth_circuit_key(provider, url, normalized_model, wire_api, api_key)
    if _skip_due_to_ai_auth_circuit(cfg, auth_circuit_key):
        return ""
    cache_key = make_ai_cache_key("text", prompt, cfg, provider, url)
    cached = ai_cache_get(cache_key, clone=False)
    if cached is not _CACHE_MISS:
        utils.vlog(cfg, f"AI 文本缓存命中 provider={provider}, model={cfg.ai_model}")
        return str(cached or "")
    utils.ai_debug_log(cfg, "llm_request_text", {
        "provider": provider,
        "url": url,
        "headers": utils._redact_headers(headers),
        "data_meta": {
            "model": data.get("model"),
            "temperature": data.get("temperature"),
            "top_p": data.get("top_p"),
            "max_tokens": data.get("max_tokens"),
            "has_options": bool(data.get("options")),
        },
        "prompt_len": len(prompt or ""),
        "prompt_sha256": prompt_sha,
        "prompt_head": utils._truncate_for_log(cfg, (prompt or "")[:4000]),
        "prompt_tail": utils._truncate_for_log(cfg, (prompt or "")[-4000:]),
    })

    utils.vlog(cfg, f"调用模型 provider={provider}, model={cfg.ai_model}")

    if _runtime_module is not None and callable(getattr(_runtime_module, "_get_http_session", None)):
        session = _runtime_module._get_http_session(cfg)
    else:
        session = _get_http_session(cfg, backend_module=legacy)
    if _runtime_module is not None and callable(getattr(_runtime_module, "_get_ai_http_timeout", None)):
        timeout = _runtime_module._get_ai_http_timeout(cfg, provider)
    else:
        timeout = _get_ai_http_timeout(cfg, provider, backend_module=legacy)
    attempts = 1 + max(
        0,
        int(utils.cfg_get_int(cfg, "ai_retry_times", int(getattr(cfg, "ai_retry_times", 0) or 0))),
    )
    if _runtime_module is not None and callable(getattr(_runtime_module, "_post_with_proxy_fallback", None)):
        resp, transport_error, proxy_meta = _runtime_module._post_with_proxy_fallback(
            session=session,
            url=url,
            data=data,
            headers=headers,
            timeout=timeout,
            cfg=cfg,
            provider=provider,
            attempts=attempts,
            log_label="LLM TEXT",
        )
    else:
        resp, transport_error, proxy_meta = _post_with_proxy_fallback(
            session=session,
            url=url,
            data=data,
            headers=headers,
            timeout=timeout,
            cfg=cfg,
            provider=provider,
            attempts=attempts,
            log_label="LLM TEXT",
            backend_module=legacy,
        )
    if resp is None:
        # 用户取消时直接返回，不记录错误日志
        if transport_error == "用户取消":
            utils.vlog(cfg, "AI 调用已取消")
            try:
                setattr(cfg, "_user_cancelled", True)
            except Exception:
                pass
            return ""
        utils.vlog(cfg, transport_error or "HTTP 调用失败")
        utils.ai_debug_log(cfg, "llm_http_error_text", {
            "provider": provider,
            "url": url,
            "error": transport_error,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        repro = write_ai_repro_bundle(
            cfg,
            provider=provider,
            url=url,
            headers=headers,
            data=data,
            prompt_sha=prompt_sha,
            reason=transport_error or "HTTP 调用失败",
            tag="llm_text",
        )
        utils.write_error_log("llm_http_error_text", {
            "provider": provider,
            "url": url,
            "error": transport_error or "HTTP 调用失败",
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            **repro,
        })
        return ""

    if resp.status_code >= 400:
        is_auth_failure = _is_ai_auth_failure_status(resp.status_code)
        last_reason = (
            f"LLM 鉴权失败: {resp.status_code}"
            if is_auth_failure
            else f"LLM 错误: {resp.status_code}"
        )
        utils.vlog(cfg, f"{last_reason} {resp.text[:200]}")
        utils.ai_debug_log(cfg, "llm_http_non_200_text", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
            "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        utils.write_error_log("llm_http_non_200_text", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
            "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            **write_ai_repro_bundle(
                cfg,
                provider=provider,
                url=url,
                headers=headers,
                data=data,
                prompt_sha=prompt_sha,
                reason=last_reason,
                tag="llm_text",
            ),
        })
        if is_auth_failure:
            _mark_ai_auth_failure(cfg, last_reason, circuit_key=auth_circuit_key)
        return ""

    try:
        js = _parse_response_json_robust(resp, backend_module=legacy)
    except Exception:
        utils.vlog(cfg, "响应 JSON 解析失败")
        utils.ai_debug_log(cfg, "llm_response_json_parse_failed_text", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
            "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
        })
        utils.write_error_log("llm_response_json_parse_failed_text", {
            "provider": provider,
            "url": url,
            "status_code": resp.status_code,
            "response_head": utils._truncate_for_log(cfg, (resp.text or "")[:20000]),
            "response_tail": utils._truncate_for_log(cfg, (resp.text or "")[-20000:]),
            "model": cfg.ai_model,
            "prompt_sha256": prompt_sha,
            "proxy_source": utils._safe_strip(proxy_meta.get("source")),
            "proxy_url": utils._safe_strip(proxy_meta.get("url")),
            **write_ai_repro_bundle(
                cfg,
                provider=provider,
                url=url,
                headers=headers,
                data=data,
                prompt_sha=prompt_sha,
                reason="响应 JSON 解析失败",
                tag="llm_text",
            ),
        })
        return ""

    if wire_api == "responses":
        content = _parse_responses_output(js)
    elif wire_api == "completions":
        content = _parse_completions_output(js)
    elif wire_api == "anthropic_messages":
        content = _parse_anthropic_messages_output(js)
    else:
        content = _parse_chat_output(js)
    if not content:
        return ""

    raw = content
    content = strip_think_blocks(raw, backend_module=legacy)
    if raw != content:
        utils.vlog(cfg, "LLM 输出包含 <think>，已移除")

    preview = (content[:200] or "").replace("\r", "").replace("\n", "\\n")
    utils.vlog(cfg, "LLM 输出(预览):", preview)
    utils._tool_log_write_block(cfg, "LLM 输出(完整)", content)
    utils.ai_debug_log(cfg, "llm_text_output", {
        "provider": provider,
        "url": url,
        "raw_head": utils._truncate_for_log(cfg, (raw or "")[:20000]),
        "raw_tail": utils._truncate_for_log(cfg, (raw or "")[-20000:]),
        "clean_head": utils._truncate_for_log(cfg, (content or "")[:20000]),
        "clean_tail": utils._truncate_for_log(cfg, (content or "")[-20000:]),
    })

    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^(json|text|txt)\s*", "", text, flags=re.I).strip()
        text = text.replace("```", "").strip()

    patterns = [
        r"^好的[，,。]?\s*我来.*?\n",
        r"^当然可以[，,。]?\s*",
        r"^下面是.*?\n",
        r"^根据你的要求.*?\n",
        r"^根据规则.*?\n",
        r"^解析如下.*?\n",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.I)

    text = text.strip()
    if text:
        ai_cache_set(cache_key, text, clone=False)

    return text


def _build_function_semantic_pack(func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
    provider = get_semantic_provider(cfg)
    return provider.build_function_pack(func_data, cfg)


def build_llm_evidence_pack(func_data: dict[str, Any], cfg: Optional[Any] = None, task: str = "func") -> dict[str, Any]:
    legacy = legacy_backend()
    from . import naming as naming_utils
    from . import lsp_facts as lsp_fact_utils
    from .context_pack import build_title_context_pack
    from .pipeline import build_logic_semantic_pack

    func_info = dict((func_data or {}).get("func_info") or {})
    comment_info = dict((func_data or {}).get("comment_info") or {})
    file_context = dict((func_data or {}).get("file_context") or {})
    body = utils._safe_text((func_data or {}).get("body"))
    semantic_pack = _build_function_semantic_pack(func_data, cfg) or {}
    try:
        title_context_pack = build_title_context_pack(func_data, cfg, semantic_pack=semantic_pack) or {}
    except Exception:
        title_context_pack = {}
    try:
        lsp_fact_pack = lsp_fact_utils.build_function_fact_pack(func_data, cfg) or {}
    except Exception:
        lsp_fact_pack = {}
    params = legacy.parse_params_from_prototype(func_info)
    local_vars = legacy.parse_local_variables_from_body(body)
    local_vars = legacy._filter_local_vars_against_params(local_vars, params, cfg=cfg, func_name=utils._safe_strip(func_info.get("func_name")))
    logic_semantic_pack = build_logic_semantic_pack(
        {
            "cfg": cfg,
            "body": body,
            "file_context": file_context,
            "local_vars": local_vars,
            "params": params,
            "in_map": legacy.parse_param_desc(utils._safe_strip(comment_info.get("input_desc")), strip_paren_content=True),
            "out_map": legacy.parse_param_desc(utils._safe_strip(comment_info.get("output_desc"))),
            "param_ai_name_map": {},
            "global_symbol_map": dict(file_context.get("symbol_map") or {}),
            "lsp_fact_pack": lsp_fact_pack,
        },
        backend_module=legacy,
    ) or {}

    verified_aliases = {}
    for item in list((semantic_pack.get("symbol_profiles") or []))[:12]:
        if not isinstance(item, dict):
            continue
        name = utils._safe_strip(item.get("name"))
        cn = utils._safe_strip(item.get("existing_cn"))
        if name and cn and name != cn:
            verified_aliases[name] = {"text": cn, "source": "symbol_index", "confidence": 0.9, "verified": True}
    for item in list((lsp_fact_pack.get("members") or []))[:12]:
        if not isinstance(item, dict):
            continue
        access_text = utils._safe_strip(item.get("access_text"))
        owner_type = utils._safe_strip(item.get("owner_type"))
        if access_text and owner_type and bool(item.get("verified")):
            verified_aliases.setdefault(
                access_text,
                {"text": owner_type, "source": utils._safe_strip(item.get("source") or "typeDefinition"), "confidence": float(item.get("confidence", 0.0) or 0.0), "verified": True},
            )

    authoritative_blocks = []
    for item in list((logic_semantic_pack.get("control_blocks") or lsp_fact_pack.get("blocks") or []))[:12]:
        if not isinstance(item, dict):
            continue
        authoritative_blocks.append(
            {
                "id": utils._safe_strip(item.get("id")),
                "kind": utils._safe_strip(item.get("kind")),
                "condition": utils._safe_strip(item.get("condition")),
                "parent": utils._safe_strip(item.get("parent")),
                "range": dict(item.get("range") or {}),
                "source": utils._safe_strip(item.get("source")),
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "verified": bool(item.get("verified")),
            }
        )
    high_conf_members = []
    for item in list((lsp_fact_pack.get("members") or []))[:16]:
        if not isinstance(item, dict):
            continue
        confidence = float(item.get("confidence", 0.0) or 0.0)
        verified = bool(item.get("verified"))
        if (not verified) and confidence < 0.75:
            continue
        high_conf_members.append(
            {
                "base": utils._safe_strip(item.get("base")),
                "member": utils._safe_strip(item.get("member")),
                "owner_type": utils._safe_strip(item.get("owner_type")),
                "access_text": utils._safe_strip(item.get("access_text")),
                "source": utils._safe_strip(item.get("source")),
                "confidence": confidence,
                "verified": verified,
            }
        )

    derived = {
        "role_summary": utils._safe_strip(semantic_pack.get("role_summary")),
        "semantic_registry": dict(logic_semantic_pack.get("semantic_registry") or {}),
        "control_skeleton": list(semantic_pack.get("control_skeleton") or [])[:10],
        "state_effects": list(semantic_pack.get("state_effects") or [])[:10],
        "callee_summaries": list(semantic_pack.get("callee_summaries") or [])[:6],
        "project_concepts": list(semantic_pack.get("project_concepts") or [])[:6],
        "title_examples": list(title_context_pack.get("retrieved_examples") or naming_utils.retrieve_function_title_context(func_data, cfg))[:4],
        "state_updates": list(logic_semantic_pack.get("state_updates") or [])[:16],
        "pattern_hits": list(logic_semantic_pack.get("pattern_hits") or [])[:16],
        "call_roles": list(logic_semantic_pack.get("call_roles") or [])[:12],
        "static_logic_skeleton": authoritative_blocks[:10],
        "entity_aliases": dict(list((logic_semantic_pack.get("entity_aliases") or {}).items())[:16]),
    }

    low_conf = {
        "body_preview": legacy._trim_body_for_ai(body, cfg, one_call=(task == "logic")),
        "weak_aliases": {
            utils._safe_strip(k): utils._safe_strip(v)
            for k, v in dict(file_context.get("symbol_map") or {}).items()
            if utils._safe_strip(k) and utils._safe_strip(v)
        },
        "bad_static_lines": list(logic_semantic_pack.get("bad_static_lines") or [])[:12],
        "guesses": {
            "provider": utils._safe_strip((lsp_fact_pack.get("metadata") or {}).get("provider")),
            "statement_count": int(logic_semantic_pack.get("statement_count", 0) or 0),
        },
    }
    return {
        "authoritative": {
            "function": {
                "name": utils._safe_strip(func_info.get("func_name")),
                "prototype": utils._safe_strip(func_info.get("prototype")),
                "ret_type": utils._safe_strip(func_info.get("ret_type")),
                "comment_info": {
                    "func_cn_name": utils._safe_strip(comment_info.get("func_cn_name")),
                    "desc": utils._safe_strip(comment_info.get("desc")),
                    "input_desc": utils._safe_strip(comment_info.get("input_desc")),
                    "output_desc": utils._safe_strip(comment_info.get("output_desc")),
                },
            },
            "control_blocks": authoritative_blocks,
            "function_range": dict((lsp_fact_pack.get("function") or {}).get("range") or {}),
            "semantic_pack_v2": {
                "version": int(logic_semantic_pack.get("semantic_pack_version") or 1),
                "quality_summary": dict(logic_semantic_pack.get("quality_summary") or {}),
                "resolver_stats": dict(logic_semantic_pack.get("resolver_stats") or {}),
            },
            "controlled_ai_contract": {
                "allowed_keys": list(CONTROLLED_AI_ALLOWED_KEYS),
                "facts_are_authoritative": True,
            },
        },
        "high_confidence": {
            "glossary": dict(file_context.get("glossary") or {}),
            "typedefs": list(file_context.get("typedefs") or [])[:8],
            "verified_aliases": verified_aliases,
            "members": high_conf_members,
            "entity_classes": dict(list((logic_semantic_pack.get("entity_classes") or {}).items())[:16]),
        },
        "derived": derived,
        "low_confidence": low_conf,
    }


def build_func_prompt(func_info, body, comment_info, cfg: Optional[Any] = None):
    legacy = legacy_backend()
    params = func_info.get("params_list", [])
    locals_ = func_info.get("locals_list", [])
    in_map = func_info.get("in_map", {})
    out_map = func_info.get("out_map", {})
    file_context = func_info.get("file_context", {}) or {}
    glossary = file_context.get("glossary") or legacy.DOMAIN_GLOSSARY
    from . import naming as naming_utils

    func_data = {
        "comment_info": dict(comment_info or {}),
        "func_info": dict(func_info or {}),
        "file_context": dict(file_context or {}),
        "body": body,
    }

    def usage_snippets(name, max_hits=3):
        return [f"{h['line']}: {h['code']}" for h in legacy.collect_usage_snippets(body, name, max_hits)]

    param_ctx = []
    for p in params:
        pname = p.get("name", "")
        param_ctx.append({
            "name": pname,
            "type": p.get("type", ""),
            "comment": (in_map.get(pname) or out_map.get(pname) or ""),
            "usage_examples": usage_snippets(pname),
        })

    local_ctx = []
    for v in locals_:
        vname = v.get("name", "")
        local_ctx.append({
            "name": vname,
            "type": v.get("type", ""),
            "cn_name": v.get("cn_name", ""),
            "usage": v.get("usage", ""),
            "usage_examples": usage_snippets(vname),
        })

    from .context_pack import build_title_context_pack

    semantic_pack: dict[str, Any] = {}
    title_context_pack: dict[str, Any] = {}
    try:
        semantic_pack = _build_function_semantic_pack(func_data, cfg) or {}
        title_context_pack = build_title_context_pack(func_data, cfg, semantic_pack=semantic_pack) or {}
    except Exception:
        semantic_pack = {}
        title_context_pack = {}
    title_examples = list(title_context_pack.get("retrieved_examples") or [])
    if not title_examples:
        title_examples = naming_utils.retrieve_function_title_context(func_data, cfg)
    relevant_project_concepts = _compact_project_concepts(
        list(semantic_pack.get("project_concepts") or []),
        func_name=utils._safe_strip(func_info.get("func_name")),
        family_prefix=utils._safe_strip(semantic_pack.get("family_prefix") or file_context.get("family_prefix")),
        limit=6,
    )

    evidence_pack = build_llm_evidence_pack(func_data, cfg, task="func")
    context = {
        "function": evidence_pack.get("authoritative", {}).get("function", {}),
        "params": param_ctx,
        "locals": local_ctx,
        "semantic_pack": {
            "role_summary": utils._safe_strip(semantic_pack.get("role_summary")),
            "control_skeleton": list(semantic_pack.get("control_skeleton") or [])[:10],
            "state_effects": list(semantic_pack.get("state_effects") or [])[:10],
            "callee_summaries": list(semantic_pack.get("callee_summaries") or [])[:6],
            "project_concepts": relevant_project_concepts,
        },
        "title_context_pack": {
            "function_identity": dict(title_context_pack.get("function_identity") or {}),
            "semantic_summary": dict(title_context_pack.get("semantic_summary") or {}),
            "retrieved_examples": title_examples,
        },
        "high_confidence": evidence_pack.get("high_confidence", {}),
        "derived": {
            "role_summary": derived_role if (derived_role := utils._safe_strip((evidence_pack.get("derived") or {}).get("role_summary"))) else utils._safe_strip(semantic_pack.get("role_summary")),
            "title_examples": title_examples,
            "project_concepts": relevant_project_concepts,
        },
        "body_preview": (evidence_pack.get("low_confidence") or {}).get("body_preview", legacy._trim_body_for_ai(body, cfg, one_call=False)),
        "remembered_terms": legacy._collect_preferred_symbol_names(
            [func_info.get("func_name", "")]
            + [p.get("name", "") for p in params]
            + [v.get("name", "") for v in locals_],
            limit=24,
        ),
    }

    return f"""你是嵌入式软件设计文档助手。根据上下文生成中文函数名和一句话功能说明。
上下文(JSON)：
{json.dumps(context, ensure_ascii=False, indent=2)}

规则：
1. 只使用上下文已有的术语/标识符（尤其是术语表 glossary），不要创造新缩写；不确定时在词尾标注\"(推测)\"。
2. `func_cn_name` 必须是适合章节标题的短名，不是功能说明句；优先 4~12 个字，结尾不加标点。
3. 标题格式统一为“对象/领域 + 动作”，动作词尽量放末尾；常用动作：初始化/获取/读取/更新/校验/判定/处理/上传/发送/接收/打包/解包/转换/滤波/采集。
4. `func_cn_name` 不要直接照抄 `desc`，避免输出“根据/遍历/读取/更新/判断...并...”这类整句说明。
   例如 `Comm429RxProcess` 应偏向“429接收处理”，`RedunTempGet` 应偏向“余度温度获取”，`IFBITStateUpdate` 应偏向“周期自检状态更新”。
5. 若功能描述本身已是紧凑短语，可在其基础上补足必要领域限定词，再作为 `func_cn_name`。
6. 保守命名优先；已有中文名/描述可直接沿用或在此基础上微调。
7. 若 remembered_terms 中已有某个标识符的中文名，必须优先沿用，不要另起新名。
8. 优先参考 semantic_pack 与 title_context_pack 提供的语义摘要、控制骨架、project_concepts 和检索样本；title_examples 只是最终风格参考。
9. `candidates` 给出 2~4 个短标题候选，按推荐顺序排列。
10. **严禁虚构**: 描述中出现的数字 (倍数/参数值/阈值) 必须能在源码或 glossary 中找到出处; 出现"X倍""Y次"等数字表述时, 若源码无此关系, 改为"多次""循环"等模糊表述或不写.
11. **严禁展开宏名**: 对于源码中以全大写+下划线形式出现的宏 (如 COMM_CCDL_RIU_EXT_PAGE1_ID), 不要按字母拆解为"COMMbit2"等错误展开, 保留原名或使用 glossary 中已存在的简短称呼.
12. **严禁新增功能**: 不要为函数添加源码未体现的"滤波""校验和计算""CRC""加密"等处理; 若不能确定, 用"处理"或省略.

输出严格JSON，仅此：
{{
  "func_cn_name": "中文函数名（不确定时可带(推测)）",
  "desc": "一句话中文功能说明，不以句号结尾",
  "candidates": ["候选标题1", "候选标题2"],
  "pattern": "使用的命名模式摘要",
  "confidence": 0.0
}}"""


def build_func_title_prompt(func_info, body, comment_info, cfg: Optional[Any] = None):
    legacy = legacy_backend()
    file_context = func_info.get("file_context", {}) or {}
    glossary = file_context.get("glossary") or legacy.DOMAIN_GLOSSARY
    from . import naming as naming_utils

    func_data = {
        "comment_info": dict(comment_info or {}),
        "func_info": dict(func_info or {}),
        "file_context": dict(file_context or {}),
        "body": body,
    }
    from .context_pack import build_title_context_pack

    semantic_pack: dict[str, Any] = {}
    title_context_pack: dict[str, Any] = {}
    try:
        semantic_pack = _build_function_semantic_pack(func_data, cfg) or {}
        title_context_pack = build_title_context_pack(func_data, cfg, semantic_pack=semantic_pack) or {}
    except Exception:
        semantic_pack = {}
        title_context_pack = {}
    title_examples = list(title_context_pack.get("retrieved_examples") or [])
    if not title_examples:
        title_examples = naming_utils.retrieve_function_title_context(func_data, cfg)
    relevant_project_concepts = _compact_project_concepts(
        list(semantic_pack.get("project_concepts") or []),
        func_name=utils._safe_strip(func_info.get("func_name")),
        family_prefix=utils._safe_strip(semantic_pack.get("family_prefix") or file_context.get("family_prefix")),
        limit=4,
    )
    semantic_summary = {
        "func_name": utils._safe_strip(func_info.get("func_name")),
        "family_prefix": utils._safe_strip(semantic_pack.get("family_prefix") or file_context.get("family_prefix")),
        "action_suffix": utils._safe_strip(semantic_pack.get("action_suffix")),
        "current_title": utils._safe_strip((comment_info or {}).get("func_cn_name")),
        "current_desc": utils._safe_strip((comment_info or {}).get("desc")),
        "compact_desc_hint": legacy._extract_compact_function_title(utils._safe_strip((comment_info or {}).get("desc"))),
        "role_summary": utils._safe_strip(semantic_pack.get("role_summary") or (title_context_pack.get("semantic_summary") or {}).get("role_summary")),
        "state_effects": list(semantic_pack.get("state_effects") or [])[:4],
        "conditions": list(semantic_pack.get("conditions") or [])[:3],
        "callee_names": list(semantic_pack.get("callee_names") or [])[:4],
        "callee_summaries": list(semantic_pack.get("callee_summaries") or [])[:4],
        "macros": list(semantic_pack.get("macro_refs") or [])[:4],
        "project_terms": list(semantic_pack.get("project_terms") or [])[:6],
        "project_concepts": relevant_project_concepts,
    }
    prompt_glossary = legacy._filter_glossary_for_prompt(
        glossary,
        [
            utils._safe_strip(func_info.get("func_name")),
            json.dumps(semantic_summary, ensure_ascii=False),
            json.dumps(title_examples[:4], ensure_ascii=False),
        ],
        limit=8,
    )
    remembered_terms = legacy._collect_preferred_symbol_names([func_info.get("func_name", "")], limit=8)
    evidence_pack = build_llm_evidence_pack(func_data, cfg, task="title")
    context = {
        "function": semantic_summary,
        "authoritative": (evidence_pack.get("authoritative") or {}).get("function", {}),
        "examples": title_examples[:4],
        "glossary": prompt_glossary,
        "project_concepts": relevant_project_concepts,
        "remembered_terms": remembered_terms,
    }
    return f"""你只负责给 C 函数生成更像章节标题的中文短标题，并补一句简短说明。只输出 JSON。
上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

规则：
1. `func_cn_name` 必须是短标题，不是解释句，优先 4~12 个字。
2. 若 `current_title` 已存在，但更像说明句、过长、或不够像标题，应给出更短更稳的标题。
3. 优先沿用 examples 的风格；若是 IFBIT/Get/Check/Test/Update 类函数，标题要保留动作特征。
4. 标题格式统一为“对象/领域 + 动作”，动作词尽量放末尾；例如“429接收处理”“余度温度获取”“周期自检状态更新”。
5. 不要输出“根据/用于/以便/然后/并/遍历”这类说明式长句。
6. 不要发明上下文没有的领域词；必要时优先用 glossary 和 remembered_terms。
7. 若 callee_summaries 已显示当前函数主要围绕某类结果/状态/检测动作展开，标题应优先吸收该领域限定词。
8. `project_concepts` 是从当前项目自动抽取的“别名 -> 项目语义”证据层，只能在证据充分时吸收，不要机械逐字展开。
9. `candidates` 给 2~4 个候选，按推荐顺序排列。
10. **严禁虚构**: 描述中出现的数字 (倍数/参数值/阈值) 必须能在源码或 glossary 中找到出处; 出现"X倍""Y次"等数字表述时, 若源码无此关系, 改为"多次""循环"等模糊表述或不写.
11. **严禁展开宏名**: 对于源码中以全大写+下划线形式出现的宏 (如 COMM_CCDL_RIU_EXT_PAGE1_ID), 不要按字母拆解为"COMMbit2"等错误展开, 保留原名或使用 glossary 中已存在的简短称呼.
12. **严禁新增功能**: 不要为函数添加源码未体现的"滤波""校验和计算""CRC""加密"等处理; 若不能确定, 用"处理"或省略.

输出严格 JSON：
{{
  "func_cn_name": "中文短标题",
  "desc": "一句话说明，不加句号",
  "candidates": ["候选1", "候选2"],
  "pattern": "命名模式摘要",
  "confidence": 0.0
}}"""


def build_func_title_retry_prompt(func_info, body, comment_info, cfg: Optional[Any] = None):
    legacy = legacy_backend()
    file_context = func_info.get("file_context", {}) or {}
    glossary = file_context.get("glossary") or legacy.DOMAIN_GLOSSARY
    from . import naming as naming_utils

    func_data = {
        "comment_info": dict(comment_info or {}),
        "func_info": dict(func_info or {}),
        "file_context": dict(file_context or {}),
        "body": body,
    }
    from .context_pack import build_title_context_pack

    semantic_pack: dict[str, Any] = {}
    title_context_pack: dict[str, Any] = {}
    try:
        semantic_pack = _build_function_semantic_pack(func_data, cfg) or {}
        title_context_pack = build_title_context_pack(func_data, cfg, semantic_pack=semantic_pack) or {}
    except Exception:
        semantic_pack = {}
        title_context_pack = {}
    title_examples = list(title_context_pack.get("retrieved_examples") or [])
    if not title_examples:
        title_examples = naming_utils.retrieve_function_title_context(func_data, cfg)
    relevant_project_concepts = _compact_project_concepts(
        list(semantic_pack.get("project_concepts") or []),
        func_name=utils._safe_strip(func_info.get("func_name")),
        family_prefix=utils._safe_strip(semantic_pack.get("family_prefix") or file_context.get("family_prefix")),
        limit=3,
    )
    context = {
        "func_name": utils._safe_strip(func_info.get("func_name")),
        "current_title": utils._safe_strip((comment_info or {}).get("func_cn_name")),
        "current_desc": utils._safe_strip((comment_info or {}).get("desc")),
        "role_summary": utils._safe_strip(semantic_pack.get("role_summary") or (title_context_pack.get("semantic_summary") or {}).get("role_summary")),
        "examples": title_examples[:3],
        "project_concepts": relevant_project_concepts,
        "glossary": legacy._filter_glossary_for_prompt(
            glossary,
            [
                utils._safe_strip(func_info.get("func_name")),
                utils._safe_strip((comment_info or {}).get("desc")),
                json.dumps(relevant_project_concepts, ensure_ascii=False),
            ],
            limit=6,
        ),
    }
    return f"""你只输出一个更像章节标题的中文短标题 JSON，不要省略字段。
上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

硬性规则：
1. 必须输出非空 `func_cn_name`，长度优先 4~12 个字。
2. 不能写解释句，禁止“根据/用于/以便/然后/并/遍历/进行”。
3. 只能使用上下文已有术语；若没有更好答案，可直接返回 `current_title` 或从 `func_name` 保守翻译。
4. 若 `project_concepts` 有高置信度概念，可吸收其中领域词；没有证据不要强行展开缩写。
5. `candidates` 至少给 1 个候选。

输出严格 JSON：
{{
  "func_cn_name": "中文短标题",
  "desc": "一句话说明，不加句号",
  "candidates": ["候选1"],
  "pattern": "retry_title_only_prompt",
  "confidence": 0.0
}}"""


def build_local_naming_prompt(
    payload: Sequence[dict[str, Any]],
    *,
    func_cn_name: str,
    func_desc: str,
    function_semantic_summary: dict[str, Any],
    prompt_glossary: dict[str, str],
    remembered_terms: dict[str, str],
    cfg: Optional[Any] = None,
) -> str:
    legacy = legacy_backend()
    compact_payload = []
    for item in (payload or []):
        compact_payload.append({
            "name": utils._safe_strip((item or {}).get("name")),
            "type": utils._safe_strip((item or {}).get("type")),
            "locked_cn": utils._safe_strip((item or {}).get("locked_cn")),
            "current_cn": utils._safe_strip((item or {}).get("current_cn")),
            "allow_refine_cn": bool((item or {}).get("allow_refine_cn")),
            "role": utils._safe_strip((item or {}).get("role")),
            "role_hint": utils._safe_strip((item or {}).get("role_hint")),
            "usage_summary": dict((item or {}).get("usage_summary") or {}),
            "local_window": list((item or {}).get("local_window") or [])[:6],
            "context": legacy._trim_text_chars(utils._safe_strip((item or {}).get("context")), 220),
            "candidate_concepts": list((item or {}).get("candidate_concepts") or [])[:4],
            "symbol_profile": dict((item or {}).get("symbol_profile") or {}),
            "semantic_context": dict((item or {}).get("semantic_context") or {}),
            "retrieved_examples": list((item or {}).get("retrieved_examples") or [])[:4],
        })
    compact_json = json.dumps(compact_payload, ensure_ascii=False, separators=(",", ":"))
    pretty_json = json.dumps(compact_payload, ensure_ascii=False, indent=2)
    summary_json = json.dumps(function_semantic_summary, ensure_ascii=False, separators=(",", ":"))
    glossary_json = json.dumps(prompt_glossary, ensure_ascii=False, separators=(",", ":"))
    remembered_json = json.dumps(remembered_terms, ensure_ascii=False, separators=(",", ":"))
    return f"""你只负责给局部变量生成中文名称和简短用途。只输出 JSON。
函数中文名/说明：{func_cn_name or '(未提供)'} / {func_desc or '(未提供)'}
函数语义摘要：{summary_json}
术语：{glossary_json}
已确认术语：{remembered_json}
变量上下文：
{compact_json}
变量上下文（格式化）：
{pretty_json}

规则：
1. `cn_name` 要短、稳定、像术语，不要写成长句。
2. `usage` 只写动作或作用，优先 4~10 个字。
3. 若已有 `locked_cn`，必须保留原名，只补 `usage`；只有 `allow_refine_cn=true` 时才允许在 `current_cn` 基础上优化名称。
4. 优先参考 `usage_summary`、`local_window`、`semantic_context`、`producer_semantic_summary`、`project_concepts`、`candidate_concepts`、`retrieved_examples`，不要被宏定义名或英文缩写表面形式带偏。
5. 不要输出“宏定义/签名/读取/比较/存放/缓存/记录/数据值/状态值”这类泛化名称，除非上下文明确就是该概念。
6. 若变量来自某个 `producer_call`，且 `producer_semantic_summary` 提示该函数在项目中通常表示某类结果/状态/位图，应优先继承这种项目语义。
7. 不确定时 `cn_name` 可为空，但 `usage` 尽量给出动作短语。

输出严格 JSON：
{{
  "变量名1": {{"cn_name": "中文名称", "usage": "简短用途", "confidence": 0.0}},
  "变量名2": {{"cn_name": "中文名称", "usage": "简短用途", "confidence": 0.0}}
}}"""


def _build_symbol_usage_summary(body: str, symbol: str, *, backend_module: Any = None) -> dict[str, Any]:
    legacy = backend_module or legacy_backend()
    ident = utils._safe_strip(symbol)
    if not ident or not body:
        return {}
    ident_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(ident)}(?![A-Za-z0-9_])")
    summary: dict[str, Any] = {
        "assigned_from": [],
        "assigned_to": [],
        "conditions": [],
        "call_args": [],
        "returns": [],
        "increments": 0,
        "bit_ops": [],
    }

    def append_unique(key: str, value: str, limit: int = 5) -> None:
        text = utils._safe_strip(value)
        if not text:
            return
        values = list(summary.get(key) or [])
        if text not in values:
            values.append(text)
        summary[key] = values[:limit]

    for raw in legacy._join_c_line_continuations(body or "").splitlines():
        line = utils._safe_strip(raw)
        if not line or not ident_re.search(line) or line.startswith("//"):
            continue
        code = re.sub(r"//.*$", "", line).strip()
        code = re.sub(r"/\*.*?\*/", "", code).strip()
        if not code:
            continue
        if re.search(rf"\breturn\b[^;]*{re.escape(ident)}", code):
            append_unique("returns", code, limit=3)
        if re.match(r"^(?:if|else\s+if|while|for)\b", code):
            append_unique("conditions", code, limit=4)
        assign_match = re.match(r"(?P<lhs>.+?)\s*(?P<op>=|\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)\s*(?P<rhs>.+?);?$", code)
        if assign_match:
            lhs = utils._safe_strip(assign_match.group("lhs"))
            rhs = utils._safe_strip(assign_match.group("rhs"))
            op = utils._safe_strip(assign_match.group("op"))
            if ident_re.search(lhs):
                append_unique("assigned_from", rhs, limit=6)
                if op != "=":
                    append_unique("bit_ops" if op in {"&=", "|=", "^=", "<<=", ">>="} else "assigned_from", f"{op} {rhs}", limit=6)
            if ident_re.search(rhs):
                append_unique("assigned_to", lhs, limit=6)
        if re.search(rf"(?:\+\+{re.escape(ident)}|{re.escape(ident)}\+\+|--{re.escape(ident)}|{re.escape(ident)}--)", code):
            summary["increments"] = int(summary.get("increments") or 0) + 1
        for call in re.finditer(r"\b([A-Za-z_]\w*)\s*\(([^;{}]*)\)", code):
            func = call.group(1)
            if func in getattr(legacy, "_C_KEYWORDS", set()):
                continue
            args = call.group(2)
            if ident_re.search(args):
                append_unique("call_args", f"{func}({args})", limit=6)
    return {key: value for key, value in summary.items() if value not in ([], 0, "", None)}


def _extract_symbol_local_window(body: str, symbol: str, *, radius: int = 1, max_items: int = 6, backend_module: Any = None) -> list[str]:
    legacy = backend_module or legacy_backend()
    ident = utils._safe_strip(symbol)
    if not ident or not body:
        return []
    ident_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(ident)}(?![A-Za-z0-9_])")
    lines = legacy._join_c_line_continuations(body or "").splitlines()
    windows: list[str] = []
    seen: set[str] = set()
    for idx, raw in enumerate(lines):
        if not ident_re.search(raw or ""):
            continue
        start = max(0, idx - max(0, radius))
        end = min(len(lines), idx + max(0, radius) + 1)
        for line_no in range(start, end):
            text = utils._safe_strip(lines[line_no])
            if not text or text in seen:
                continue
            if len(text) > 180:
                text = text[:180] + "..."
            seen.add(text)
            windows.append(f"{line_no + 1}: {text}")
            if len(windows) >= max_items:
                return windows
    return windows


def build_symbol_prompt(symbol, vtype, body, func_cn_name: str = "", func_desc: str = "", *, backend_module: Any = None):
    legacy = backend_module or legacy_backend()
    snippets = legacy.collect_usage_snippets(body, symbol, 6)
    snippet_text = "\n".join([f"{hit['line']}: {hit['code']}" for hit in snippets]) or "(无明显片段)"
    usage_summary = _build_symbol_usage_summary(body, symbol, backend_module=legacy)
    local_window = _extract_symbol_local_window(body, symbol, backend_module=legacy)
    func_cn_name = func_cn_name or "(未提供)"
    func_desc = func_desc or "(未提供)"

    return f"""根据片段推断变量/参数的中文"名称"和"用途"，不确定时标注"(推测)"。只输出JSON：

标识: {symbol}
类型: {vtype}
函数中文名/功能说明: {func_cn_name} / {func_desc}
符号用法摘要: {json.dumps(usage_summary, ensure_ascii=False)}
局部邻近代码: {json.dumps(local_window, ensure_ascii=False)}
上下文片段:
{snippet_text}

输出JSON：
{{
  "cn_name": "中文名称，尽量短",
  "usage": "用途描述，10~20字内；不确定部分标注(推测)",
  "confidence": 0.0
}}
规则：
- 不要依据标识符的类型后缀（如 _u16/_u32/i16/i32 等）推断含义，后缀仅表示类型。
- 命名应与函数中文名/功能说明语义保持一致，避免无关的泛化。
仅JSON。"""


def ai_suggest_for_locals_batch(missing_vars, locals_all, body: str, cfg, func_cn_name: str = "", func_desc: str = "", glossary=None):
    legacy = legacy_backend()
    if not missing_vars:
        return {}

    def collect(name):
        hits = legacy.collect_usage_snippets(body, name, 4)
        return "\n".join([f"{h['line']}: {h['code']}" for h in hits]) or "(无明显片段)"

    type_map = {v["name"]: v.get("type", "") for v in locals_all if v.get("name")}
    local_lookup = {v["name"]: v for v in locals_all if v.get("name")}
    owner_meta = next((item for item in locals_all if utils._safe_strip((item or {}).get("owner_func"))), {}) or {}
    owner_semantic = semantic_utils.lightweight_semantic_record_from_body(
        func_name=utils._safe_strip(owner_meta.get("owner_func")),
        source_file=utils._safe_strip(owner_meta.get("source_file")),
        module_key=utils._safe_strip(owner_meta.get("module_key")),
        family_prefix=utils._safe_strip(owner_meta.get("family_prefix")),
        ret_type=utils._safe_strip(owner_meta.get("owner_ret_type")),
        comment_desc=utils._safe_strip(func_desc),
        body=body,
        cfg=cfg,
        backend_module=legacy,
    )
    function_semantic_pack: dict[str, Any] = {}
    function_semantic_summary: dict[str, Any] = {}
    from .context_pack import build_symbol_context_pack
    from . import naming as naming_utils

    try:
        function_semantic_pack = _build_function_semantic_pack(
            {
                "comment_info": {"func_cn_name": utils._safe_strip(func_cn_name), "desc": utils._safe_strip(func_desc)},
                "func_info": {"func_name": utils._safe_strip(owner_meta.get("owner_func")), "ret_type": utils._safe_strip(owner_meta.get("owner_ret_type"))},
                "file_context": {
                    "source_file": utils._safe_strip(owner_meta.get("source_file")),
                    "module_key": utils._safe_strip(owner_meta.get("module_key")),
                    "family_prefix": utils._safe_strip(owner_meta.get("family_prefix")),
                },
                "body": body,
            },
            cfg,
        ) or {}
    except Exception:
        function_semantic_pack = {}
    function_semantic_summary = {
        "func_name": utils._safe_strip(function_semantic_pack.get("func_name") or owner_meta.get("owner_func")),
        "module_key": utils._safe_strip(function_semantic_pack.get("module_key") or owner_meta.get("module_key")),
        "family_prefix": utils._safe_strip(function_semantic_pack.get("family_prefix") or owner_meta.get("family_prefix")),
        "role_summary": utils._safe_strip(function_semantic_pack.get("role_summary")),
        "comment_desc": utils._safe_strip(function_semantic_pack.get("comment_desc") or func_desc),
        "callee_names": list(function_semantic_pack.get("callee_names") or [])[:6],
        "callee_summaries": list(function_semantic_pack.get("callee_summaries") or [])[:4],
        "conditions": list(function_semantic_pack.get("conditions") or [])[:6],
        "state_effects": list(function_semantic_pack.get("state_effects") or [])[:6],
        "control_skeleton": list(function_semantic_pack.get("control_skeleton") or [])[:8],
        "project_terms": list(function_semantic_pack.get("project_terms") or [])[:6],
        "project_concepts": _compact_project_concepts(
            list(function_semantic_pack.get("project_concepts") or []),
            func_name=utils._safe_strip(function_semantic_pack.get("func_name") or owner_meta.get("owner_func")),
            family_prefix=utils._safe_strip(function_semantic_pack.get("family_prefix") or owner_meta.get("family_prefix")),
            limit=4,
        ),
    }
    payload = []
    for name in missing_vars:
        item = local_lookup.get(name) or {}
        allow_refine_cn = bool((item or {}).get("allow_refine_cn"))
        current_cn = utils._safe_strip(item.get("cn_name"))
        locked_cn = utils._safe_strip(item.get("locked_cn"))
        if (not allow_refine_cn) and (not locked_cn):
            locked_cn = current_cn
        role_hint = utils._safe_strip(item.get("role_hint") or item.get("comment_hint"))
        evidence = legacy.collect_symbol_evidence(
            name,
            kind="symbols",
            body=body,
            decl_type=type_map.get(name, ""),
            neighbor_symbols=[x for x in type_map.keys() if x != name],
            source_comment_hints=[role_hint, func_desc],
        )
        inference = semantic_utils.infer_symbol_semantics_rule(evidence, backend_module=legacy)
        candidate_concepts = list(semantic_utils.candidate_concepts_from_evidence(evidence, backend_module=legacy))
        symbol_query = {
            "symbol": name,
            "decl_type": type_map.get(name, ""),
            "role": utils._safe_strip(inference.role),
            "family_prefix": utils._safe_strip(item.get("family_prefix")),
            "module_key": utils._safe_strip(item.get("module_key")),
            "source_file": utils._safe_strip(item.get("source_file")),
            "scope": utils._safe_strip(item.get("scope")) or "local",
            "direction": utils._safe_strip(item.get("direction")) or "local",
            "producer_call": utils._safe_strip(evidence.producer_call),
            "producer_arg_tags": tuple(evidence.producer_arg_tags or ()),
            "consumer_patterns": tuple(evidence.consumer_patterns or ()),
            "paired_symbols": tuple(evidence.paired_symbols or ()),
            "usage_patterns": tuple(evidence.usage_patterns or ()),
            "neighbor_symbols": tuple(x for x in type_map.keys() if x != name),
            "owner_func": utils._safe_strip(item.get("owner_func")),
            "owner_ret_type": utils._safe_strip(item.get("owner_ret_type")),
            "comment_desc": utils._safe_strip(func_desc),
            "body": body,
            "owner_semantic": owner_semantic,
        }
        symbol_context_pack = {}
        try:
            symbol_context_pack = build_symbol_context_pack(symbol_query, cfg, semantic_pack=function_semantic_pack) or {}
        except Exception:
            symbol_context_pack = {}
        retrieved_examples = list(symbol_context_pack.get("retrieved_examples") or [])
        if not retrieved_examples:
            retrieved_examples = naming_utils.retrieve_symbol_context(symbol_query, cfg)
        usage_summary = _build_symbol_usage_summary(body, name, backend_module=legacy)
        local_window = _extract_symbol_local_window(body, name, backend_module=legacy)
        payload.append({
            "name": name,
            "type": type_map.get(name, ""),
            "context": collect(name),
            "locked_cn": locked_cn,
            "current_cn": current_cn,
            "allow_refine_cn": allow_refine_cn,
            "role_hint": role_hint,
            "role": utils._safe_strip(inference.role),
            "canonical_cn": legacy.resolve_canonical_symbol_name(name, kind="symbols", fallback="", allow_guess=False),
            "usage_summary": usage_summary,
            "local_window": local_window,
            "symbol_profile": {
                "producer_kind": utils._safe_strip(evidence.producer_kind),
                "producer_call": utils._safe_strip(evidence.producer_call),
                "producer_args": list(evidence.producer_args or ()),
                "producer_arg_tags": list(evidence.producer_arg_tags or ()),
                "consumer_patterns": list(evidence.consumer_patterns or ()),
                "paired_symbols": list(evidence.paired_symbols or ()),
                "normalized_comment_hint": utils._safe_strip(evidence.normalized_comment_hint),
            },
            "candidate_concepts": candidate_concepts,
            "semantic_context": symbol_context_pack,
            "retrieved_examples": retrieved_examples,
        })

    remembered_terms = legacy._collect_preferred_symbol_names(missing_vars, limit=24)
    prompt_glossary = legacy._filter_glossary_for_prompt(glossary, [body, func_cn_name, func_desc], limit=12)
    quality_feedback = utils._safe_strip(getattr(cfg, "_ai_quality_feedback", ""))
    quality_focus_symbols = list(getattr(cfg, "_ai_quality_focus_symbols", ()) or ())
    quality_block = ""
    if quality_feedback or quality_focus_symbols:
        lines = ["质量回归要求："]
        if quality_feedback:
            lines.append(f"- {quality_feedback}")
        if quality_focus_symbols:
            lines.append(f"- 本轮优先收口这些标识符：{json.dumps(quality_focus_symbols, ensure_ascii=False)}")
        quality_block = "\n" + "\n".join(lines) + "\n"
    compact_prompt = build_local_naming_prompt(
        payload,
        func_cn_name=func_cn_name,
        func_desc=func_desc,
        function_semantic_summary=function_semantic_summary,
        prompt_glossary=prompt_glossary,
        remembered_terms=remembered_terms,
        cfg=cfg,
    )
    if quality_block:
        compact_prompt = compact_prompt.replace("规则：", f"{quality_block}规则：", 1)
    payload_by_name = {
        utils._safe_strip((item or {}).get("name")): dict(item or {})
        for item in (payload or [])
        if utils._safe_strip((item or {}).get("name"))
    }
    if _is_small_model_strict_mode(cfg, backend_module=legacy):
        prompt = f"""只输出JSON映射。
规则:
1. 若 locked_cn 非空，必须原样保留，cn_name 可返回空字符串。
2. 优先补 usage，不确定时 cn_name 返回空字符串。
3. cn_name 必须是短中文名，不能含英文，不能写用途句。
4. usage 只写动作或作用，不写\"用于/以便/供\"。
5. role_hint 与 role 仅辅助理解，不要照抄上下文注释。
6. 优先参考 function_semantic、semantic_context、project_concepts、candidate_concepts 与 retrieved_examples 的既有命名风格。
7. 若 producer_semantic_summary 指向某个返回结果/状态/位图的函数语义，应优先吸收该函数的领域词。
8. 不要被宏定义名、读取/比较/签名 这类泛化词带偏，名称应贴合当前函数语义角色。{quality_block if quality_block else ''}
函数:{json.dumps({'func_cn_name': func_cn_name or '', 'func_desc': func_desc or ''}, ensure_ascii=False, separators=(',', ':'))}
函数语义:{json.dumps(function_semantic_summary, ensure_ascii=False, separators=(',', ':'))}
术语:{json.dumps(prompt_glossary, ensure_ascii=False, separators=(',', ':'))}
已确认:{json.dumps(remembered_terms, ensure_ascii=False, separators=(',', ':'))}
输入:{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}
输出:{{"变量名":{{"cn_name":"","usage":"","confidence":0.0}}}}"""
    else:
        prompt = f"""你是严谨的系统工程文档助手。请为下列C局部变量，根据上下文片段推断中文\"名称\"和\"用途\"，输出严格JSON映射。
规则：
- 不要根据标识符后缀（_u16/_u32/i16/i32 等类型后缀）推测含义；后缀仅表示类型。
- 优先贴合函数中文名/功能说明来命名，保持语义一致，避免无关泛化。
- 不确定处在词尾标注\"(推测)\"，用途10~20字内，言简意赅。
{f'- 术语表优先：{json.dumps(prompt_glossary, ensure_ascii=False)}' if prompt_glossary else ''}
- 若某项已有 locked_cn 或 remembered_terms 中已有中文名，必须直接沿用该中文名，只补用途，不得改名。
- 优先使用 function_semantic、semantic_context、producer_semantic_summary、project_concepts、candidate_concepts；若 comment_hint 与 producer_call/producer_arg_tags/consumer_patterns 冲突，优先相信后者。
- role、symbol_profile、semantic_context 与 retrieved_examples 仅作为命名参考，最终名称要短、稳定、像术语，不要写成长句。
- 不要把“宏定义/签名/读取/比较/状态值/数据值”这类泛化词直接当作最终中文名，除非上下文明确就是该概念。
{quality_block}

函数中文名/说明：{func_cn_name or '(未提供)'} / {func_desc or '(未提供)'}
函数语义摘要：{json.dumps(function_semantic_summary, ensure_ascii=False)}
已确认术语：{json.dumps(remembered_terms, ensure_ascii=False)}

输入数据(仅供参考)：
{json.dumps(payload, ensure_ascii=False, indent=2)}

输出严格JSON（仅此，不要包含解释）：
{{
  "变量名1": {{"cn_name": "中文名称", "usage": "用途描述", "confidence": 0.0}},
  "变量名2": {{...}}
}}"""
    js = call_llm_json(compact_prompt, cfg)
    if not isinstance(js, dict) or not js:
        js = call_llm_json(prompt, cfg)
    if not isinstance(js, dict):
        return {}
    js = legacy._normalize_ai_var_keys(
        js,
        missing_vars,
        max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
        min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
    )
    normalized = {}
    for name, item in js.items():
        if isinstance(item, dict):
            item = legacy._coerce_dict_keys(
                item,
                ("cn_name", "usage", "confidence"),
                aliases={
                    "name": "cn_name",
                    "cn": "cn_name",
                    "cname": "cn_name",
                    "cnname": "cn_name",
                    "purpose": "usage",
                    "desc": "usage",
                    "description": "usage",
                },
                max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
                min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
            )
        elif isinstance(item, str):
            item = {"cn_name": item}
        if isinstance(item, dict):
            allow_refine_cn = bool((local_lookup.get(name) or {}).get("allow_refine_cn"))
            locked_cn = utils._safe_strip((local_lookup.get(name) or {}).get("locked_cn"))
            if (not allow_refine_cn) and (not locked_cn):
                locked_cn = utils._safe_strip((local_lookup.get(name) or {}).get("cn_name"))
            item = naming_utils.rerank_symbol_candidate(name, item, allow_refine_cn=allow_refine_cn, locked_cn=locked_cn)
            accepted_cn = _should_accept_local_ai_cn_result(
                name,
                item={**dict(local_lookup.get(name) or {}), **dict(payload_by_name.get(name) or {})},
                candidate_cn=utils._safe_strip(item.get("cn_name")),
                semantic_context=dict((payload_by_name.get(name) or {}).get("semantic_context") or {}),
                candidate_concepts=list((payload_by_name.get(name) or {}).get("candidate_concepts") or []),
                retrieved_examples=list((payload_by_name.get(name) or {}).get("retrieved_examples") or []),
                backend_module=legacy,
            )
            if not accepted_cn:
                item["cn_name"] = ""
            model_conf = _clamp_score(item.get("confidence", 0.0))
            final_score = _calibrate_symbol_confidence(
                raw_ident=name,
                cn_name=utils._safe_strip(item.get("cn_name")),
                usage=utils._safe_strip(item.get("usage")),
                model_confidence=model_conf,
                allow_refine_cn=allow_refine_cn,
                locked_cn=locked_cn,
                semantic_context=dict((payload_by_name.get(name) or {}).get("semantic_context") or {}),
            )
            item["model_confidence"] = model_conf
            item["final_score"] = final_score
            item["confidence"] = final_score
        normalized[name] = item
        if isinstance(item, dict):
            legacy._remember_ai_symbol(
                name,
                utils._safe_strip(item.get("cn_name")),
                kind="symbols",
                confidence=float(item.get("final_score", item.get("confidence", 0.0)) or 0.0),
                cfg=cfg,
                source="ai_symbol",
            )
    return normalized


def ai_suggest_for_func(
    func_info,
    body,
    comment_info,
    cfg,
    params=None,
    locals_=None,
    in_map=None,
    out_map=None,
    file_context=None,
    _runtime_module: Any = None,
):
    legacy = _resolve_backend_module(cfg, _runtime_module)
    func_info_prompt = dict(func_info)
    func_info_prompt["params_list"] = params or []
    func_info_prompt["locals_list"] = locals_ or []
    func_info_prompt["in_map"] = in_map or {}
    func_info_prompt["out_map"] = out_map or {}
    func_info_prompt["file_context"] = file_context or {}

    call_json = getattr(_runtime_module, "call_llm_json", None) if _runtime_module is not None else None
    if not callable(call_json):
        def call_json(prompt: str, cfg_obj: Any, **kwargs: Any):
            return call_llm_json(prompt, cfg_obj, **kwargs)

    title_stage_debug = []
    prompt = build_func_title_prompt(func_info_prompt, body, comment_info, cfg)
    js = call_json(prompt, cfg)
    title_stage_debug.append(legacy._capture_title_call_debug(cfg, "compact_title_prompt", prompt, js))
    fallback_used = False
    retry_used = False
    if not isinstance(js, dict) or not any(utils._safe_strip((js or {}).get(key)) for key in ("func_cn_name", "desc", "pattern")):
        fallback_prompt = build_func_prompt(func_info_prompt, body, comment_info, cfg)
        js = call_json(fallback_prompt, cfg)
        title_stage_debug.append(legacy._capture_title_call_debug(cfg, "fallback_full_prompt", fallback_prompt, js))
        fallback_used = True
    if not isinstance(js, dict) or not any(utils._safe_strip((js or {}).get(key)) for key in ("func_cn_name", "candidates")):
        retry_prompt = build_func_title_retry_prompt(func_info_prompt, body, comment_info, cfg)
        retry_js = call_json(retry_prompt, cfg)
        title_stage_debug.append(legacy._capture_title_call_debug(cfg, "retry_title_only_prompt", retry_prompt, retry_js))
        if isinstance(retry_js, dict) and any(utils._safe_strip((retry_js or {}).get(key)) for key in ("func_cn_name", "candidates")):
            js = retry_js
            retry_used = True
    if not isinstance(js, dict):
        return {}
    js = legacy._unwrap_named_result_dict(
        js,
        ("func_cn_name", "desc", "confidence", "candidates", "pattern"),
        aliases={
            "func_cn": "func_cn_name",
            "func_name_cn": "func_cn_name",
            "func_desc": "desc",
            "function_desc": "desc",
            "description": "desc",
            "title_candidates": "candidates",
        },
    )
    js = legacy._coerce_dict_keys(
        js,
        ("func_cn_name", "desc", "confidence", "candidates", "pattern"),
        aliases={
            "func_cn": "func_cn_name",
            "func_name_cn": "func_cn_name",
            "func_desc": "desc",
            "function_desc": "desc",
            "description": "desc",
            "title_candidates": "candidates",
        },
        max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
        min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
    )
    model_conf = _clamp_score(js.get("confidence", 0))
    raw_func_cn_name = utils._safe_strip(js.get("func_cn_name"))
    func_cn_name = raw_func_cn_name
    desc = utils._safe_strip(js.get("desc"))
    if not desc or _looks_like_codeish_description(desc):
        desc = _fallback_function_description(func_info, body, current_desc=desc or utils._safe_strip(comment_info.get("desc")))
    # 后处理: 剔除 LLM 描述中无依据的数字/宏展开 (防幻觉)
    if desc:
        glossary = (file_context or {}).get("glossary") or legacy.DOMAIN_GLOSSARY
        glossary_terms = [str(item.get("concept") or item.get("alias") or "") for item in (glossary or []) if isinstance(item, dict)]
        desc = _sanitize_ai_desc(desc, body, glossary_terms=glossary_terms)
    glossary = (file_context or {}).get("glossary") or legacy.DOMAIN_GLOSSARY
    from . import naming as naming_utils

    retrieved_examples = naming_utils.retrieve_function_title_context(
        {
            "comment_info": dict(comment_info or {}),
            "func_info": dict(func_info or {}),
            "file_context": dict(file_context or {}),
            "body": body,
        },
        cfg,
    )
    if func_cn_name and not text_utils._contains_cjk(func_cn_name):
        guessed = legacy._guess_cn_from_ident(func_cn_name, glossary=glossary)
        if guessed:
            func_cn_name = guessed
    if not func_cn_name:
        guessed = legacy._guess_cn_from_ident(func_info.get("func_name", ""), glossary=glossary)
        if guessed:
            func_cn_name = guessed
    candidate_items = js.get("candidates") or []
    if not isinstance(candidate_items, list):
        candidate_items = []
    candidate_texts = [utils._safe_strip(x) for x in candidate_items if utils._safe_strip(x)]
    pre_rerank_func_cn_name = func_cn_name
    func_cn_name = naming_utils.rerank_function_title_candidates(
        utils._safe_strip(func_info.get("func_name")),
        utils._safe_strip(comment_info.get("desc")),
        func_cn_name,
        candidate_texts,
        retrieved_examples,
    )
    rerank_changed = utils._safe_strip(func_cn_name) != utils._safe_strip(pre_rerank_func_cn_name)
    final_score = _calibrate_function_confidence(
        func_name=utils._safe_strip(func_info.get("func_name")),
        func_cn_name=func_cn_name,
        desc=desc,
        model_confidence=model_conf,
        fallback_used=fallback_used,
        examples=retrieved_examples,
    )
    legacy._remember_ai_symbol(
        str(func_info.get("func_name") or ""),
        func_cn_name,
        kind="functions",
        confidence=final_score,
        cfg=cfg,
        source="ai_func",
    )
    setattr(
        cfg,
        "_current_func_title_debug",
        {
            "raw_func_cn_name": raw_func_cn_name,
            "pre_rerank_func_cn_name": pre_rerank_func_cn_name,
            "final_func_cn_name": func_cn_name,
            "candidates": tuple(candidate_texts),
            "pattern": utils._safe_strip(js.get("pattern")) or ("retry_title_only_prompt" if retry_used else ("fallback_full_prompt" if fallback_used else "compact_title_prompt")),
            "rerank_changed": bool(rerank_changed),
            "fallback_used": bool(fallback_used),
            "retry_used": bool(retry_used),
            "model_confidence": float(model_conf),
            "final_score": float(final_score),
            "stage_debug": tuple(title_stage_debug),
        },
    )
    return {
        "func_cn_name": func_cn_name,
        "desc": desc,
        "candidates": candidate_texts,
        "pattern": utils._safe_strip(js.get("pattern")) or ("retry_title_only_prompt" if retry_used else ("fallback_full_prompt" if fallback_used else "compact_title_prompt")),
        "raw_func_cn_name": raw_func_cn_name,
        "pre_rerank_func_cn_name": pre_rerank_func_cn_name,
        "rerank_changed": rerank_changed,
        "fallback_used": fallback_used,
        "retry_used": retry_used,
        "model_confidence": model_conf,
        "final_score": final_score,
        "confidence": final_score,
        "stage_debug": tuple(title_stage_debug),
    }


def detect_gaps(
    comment_info,
    locals_,
    params,
    in_map,
    out_map,
    func_info=None,
    cfg: Optional[Any] = None,
    logic_semantic_pack: Optional[dict[str, Any]] = None,
    body: str = "",
    _runtime_module: Any = None,
):
    legacy = _resolve_backend_module(cfg, _runtime_module)

    def is_missing_text(text: str) -> bool:
        if not text:
            return True
        value = str(text or "").strip()
        return value in ("NONE", "None", "none", "无", "待人工修改")

    desc = utils._safe_strip((comment_info or {}).get("desc"))
    func_cn = utils._safe_strip((comment_info or {}).get("func_cn_name"))

    need_func_desc = is_missing_text(desc)
    need_func_cn_name = is_missing_text(func_cn)
    need_func_cn_refine = bool(legacy._function_title_needs_ai_upgrade(comment_info, func_info))
    if (not need_func_cn_refine) and bool(legacy._should_force_ai_title_refine(cfg, comment_info, func_info)):
        need_func_cn_refine = True

    need_param_names = []
    for param in (params or []):
        name = str((param or {}).get("name") or "").strip()
        desc_cn = str((in_map or {}).get(name) or (out_map or {}).get(name) or "").strip()
        if is_missing_text(desc_cn):
            need_param_names.append(name)

    need_local_usages = []
    for item in (locals_ or []):
        if _should_track_local_ai_gap(item, backend_module=legacy):
            need_local_usages.append(str((item or {}).get("name") or "").strip())

    gaps = {
        "need_func_desc": need_func_desc,
        "need_func_cn_name": need_func_cn_name,
        "need_func_cn_refine": need_func_cn_refine,
        "need_param_names": need_param_names,
        "need_local_usages": need_local_usages,
    }
    semantic_pack = dict(logic_semantic_pack or {})
    bad_static_lines = list(semantic_pack.get("bad_static_lines") or [])
    block_count = len(semantic_pack.get("control_blocks") or [])
    update_count = len(semantic_pack.get("state_updates") or [])
    member_count = int(semantic_pack.get("member_access_count", 0) or 0)
    key_call_count = int(semantic_pack.get("key_call_count", 0) or 0)
    stmt_count = int(semantic_pack.get("statement_count", 0) or 0)
    title_plain_fallback = bool(desc) and (not utils._safe_strip((comment_info or {}).get("func_name"))) and (not utils._safe_strip((comment_info or {}).get("func_cn_name")))
    rewrite_votes = 0
    if block_count >= int(utils.cfg_get_int(cfg, "logic_semantic_rewrite_block_min", 3)):
        rewrite_votes += 1
    if update_count >= 6:
        rewrite_votes += 1
    if member_count >= 8:
        rewrite_votes += 1
    if key_call_count >= 2:
        rewrite_votes += 1
    if stmt_count >= int(utils.cfg_get_int(cfg, "logic_semantic_rewrite_stmt_min", 60)):
        rewrite_votes += 1
    if title_plain_fallback:
        rewrite_votes += 1
    need_func_semantic_rewrite = bool(bad_static_lines) or rewrite_votes >= 2
    gaps["need_func_semantic_rewrite"] = need_func_semantic_rewrite
    gaps["_stats"] = {
        "params_missing": len(need_param_names),
        "locals_missing": len(need_local_usages),
        "need_func_desc": need_func_desc,
        "need_func_cn_name": need_func_cn_name,
        "need_func_cn_refine": need_func_cn_refine,
        "need_func_semantic_rewrite": need_func_semantic_rewrite,
    }
    return gaps


def ai_suggest_for_locals_batch(
    missing_vars,
    locals_all,
    body: str,
    cfg,
    func_cn_name: str = "",
    func_desc: str = "",
    glossary=None,
    _runtime_module: Any = None,
):
    legacy = _resolve_backend_module(cfg, _runtime_module)
    call_json = getattr(_runtime_module, "call_llm_json", None) if _runtime_module is not None else None
    if not callable(call_json):
        def call_json(prompt: str, cfg_obj: Any, **kwargs: Any):
            return call_llm_json(prompt, cfg_obj, **kwargs)
    if not missing_vars:
        return {}

    def collect(name):
        hits = legacy.collect_usage_snippets(body, name, 4)
        return "\n".join([f"{h['line']}: {h['code']}" for h in hits]) or "(无明显片段)"

    type_map = {v["name"]: v.get("type", "") for v in locals_all if v.get("name")}
    local_lookup = {v["name"]: v for v in locals_all if v.get("name")}
    owner_meta = next((item for item in locals_all if utils._safe_strip((item or {}).get("owner_func"))), {}) or {}
    owner_semantic = semantic_utils.lightweight_semantic_record_from_body(
        func_name=utils._safe_strip(owner_meta.get("owner_func")),
        source_file=utils._safe_strip(owner_meta.get("source_file")),
        module_key=utils._safe_strip(owner_meta.get("module_key")),
        family_prefix=utils._safe_strip(owner_meta.get("family_prefix")),
        ret_type=utils._safe_strip(owner_meta.get("owner_ret_type")),
        comment_desc=utils._safe_strip(func_desc),
        body=body,
        cfg=cfg,
        backend_module=legacy,
    )
    function_semantic_pack: dict[str, Any] = {}
    function_semantic_summary: dict[str, Any] = {}
    from .context_pack import build_symbol_context_pack
    from . import naming as naming_utils

    try:
        function_semantic_pack = _build_function_semantic_pack(
            {
                "comment_info": {"func_cn_name": utils._safe_strip(func_cn_name), "desc": utils._safe_strip(func_desc)},
                "func_info": {"func_name": utils._safe_strip(owner_meta.get("owner_func")), "ret_type": utils._safe_strip(owner_meta.get("owner_ret_type"))},
                "file_context": {
                    "source_file": utils._safe_strip(owner_meta.get("source_file")),
                    "module_key": utils._safe_strip(owner_meta.get("module_key")),
                    "family_prefix": utils._safe_strip(owner_meta.get("family_prefix")),
                },
                "body": body,
            },
            cfg,
        ) or {}
    except Exception:
        function_semantic_pack = {}
    function_semantic_summary = {
        "func_name": utils._safe_strip(function_semantic_pack.get("func_name") or owner_meta.get("owner_func")),
        "module_key": utils._safe_strip(function_semantic_pack.get("module_key") or owner_meta.get("module_key")),
        "family_prefix": utils._safe_strip(function_semantic_pack.get("family_prefix") or owner_meta.get("family_prefix")),
        "role_summary": utils._safe_strip(function_semantic_pack.get("role_summary")),
        "comment_desc": utils._safe_strip(function_semantic_pack.get("comment_desc") or func_desc),
        "callee_names": list(function_semantic_pack.get("callee_names") or [])[:6],
        "callee_summaries": list(function_semantic_pack.get("callee_summaries") or [])[:4],
        "conditions": list(function_semantic_pack.get("conditions") or [])[:6],
        "state_effects": list(function_semantic_pack.get("state_effects") or [])[:6],
        "control_skeleton": list(function_semantic_pack.get("control_skeleton") or [])[:8],
        "project_terms": list(function_semantic_pack.get("project_terms") or [])[:6],
        "project_concepts": _compact_project_concepts(
            list(function_semantic_pack.get("project_concepts") or []),
            func_name=utils._safe_strip(function_semantic_pack.get("func_name") or owner_meta.get("owner_func")),
            family_prefix=utils._safe_strip(function_semantic_pack.get("family_prefix") or owner_meta.get("family_prefix")),
            limit=4,
        ),
    }
    regression_rename_set = set(getattr(cfg, "_ai_regression_allow_rename", set()) or set())
    payload = []
    for name in missing_vars:
        item = local_lookup.get(name) or {}
        # 回归轮对 focus_symbols 放开改名
        if name in regression_rename_set:
            allow_refine_cn = True
            locked_cn = ""
        else:
            allow_refine_cn = bool((item or {}).get("allow_refine_cn"))
            locked_cn = utils._safe_strip(item.get("locked_cn"))
            if (not allow_refine_cn) and (not locked_cn):
                locked_cn = utils._safe_strip(item.get("cn_name"))
        current_cn = utils._safe_strip(item.get("cn_name"))
        role_hint = utils._safe_strip(item.get("role_hint") or item.get("comment_hint"))
        evidence = legacy.collect_symbol_evidence(
            name,
            kind="symbols",
            body=body,
            decl_type=type_map.get(name, ""),
            neighbor_symbols=[x for x in type_map.keys() if x != name],
            source_comment_hints=[role_hint, func_desc],
        )
        inference = semantic_utils.infer_symbol_semantics_rule(evidence, backend_module=legacy)
        candidate_concepts = list(semantic_utils.candidate_concepts_from_evidence(evidence, backend_module=legacy))
        symbol_query = {
            "symbol": name,
            "decl_type": type_map.get(name, ""),
            "role": utils._safe_strip(inference.role),
            "family_prefix": utils._safe_strip(item.get("family_prefix")),
            "module_key": utils._safe_strip(item.get("module_key")),
            "source_file": utils._safe_strip(item.get("source_file")),
            "scope": utils._safe_strip(item.get("scope")) or "local",
            "direction": utils._safe_strip(item.get("direction")) or "local",
            "producer_call": utils._safe_strip(evidence.producer_call),
            "producer_arg_tags": tuple(evidence.producer_arg_tags or ()),
            "consumer_patterns": tuple(evidence.consumer_patterns or ()),
            "paired_symbols": tuple(evidence.paired_symbols or ()),
            "usage_patterns": tuple(evidence.usage_patterns or ()),
            "neighbor_symbols": tuple(x for x in type_map.keys() if x != name),
            "owner_func": utils._safe_strip(item.get("owner_func")),
            "owner_ret_type": utils._safe_strip(item.get("owner_ret_type")),
            "comment_desc": utils._safe_strip(func_desc),
            "body": body,
            "owner_semantic": owner_semantic,
        }
        symbol_context_pack = {}
        try:
            symbol_context_pack = build_symbol_context_pack(symbol_query, cfg, semantic_pack=function_semantic_pack) or {}
        except Exception:
            symbol_context_pack = {}
        retrieved_examples = list(symbol_context_pack.get("retrieved_examples") or [])
        if not retrieved_examples:
            retrieved_examples = naming_utils.retrieve_symbol_context(symbol_query, cfg)
        usage_summary = _build_symbol_usage_summary(body, name, backend_module=legacy)
        local_window = _extract_symbol_local_window(body, name, backend_module=legacy)
        if not _should_request_local_ai_candidate(
            {**dict(item or {}), "name": name, "locked_cn": locked_cn, "allow_refine_cn": allow_refine_cn},
            evidence=evidence,
            inference=inference,
            candidate_concepts=candidate_concepts,
            semantic_context=symbol_context_pack,
            retrieved_examples=retrieved_examples,
            backend_module=legacy,
        ):
            continue
        payload.append({
            "name": name,
            "type": type_map.get(name, ""),
            "context": collect(name),
            "locked_cn": locked_cn,
            "current_cn": current_cn,
            "allow_refine_cn": allow_refine_cn,
            "role_hint": role_hint,
            "role": utils._safe_strip(inference.role),
            "canonical_cn": legacy.resolve_canonical_symbol_name(name, kind="symbols", fallback="", allow_guess=False),
            "usage_summary": usage_summary,
            "local_window": local_window,
            "symbol_profile": {
                "producer_kind": utils._safe_strip(evidence.producer_kind),
                "producer_call": utils._safe_strip(evidence.producer_call),
                "producer_args": list(evidence.producer_args or ()),
                "producer_arg_tags": list(evidence.producer_arg_tags or ()),
                "consumer_patterns": list(evidence.consumer_patterns or ()),
                "paired_symbols": list(evidence.paired_symbols or ()),
                "normalized_comment_hint": utils._safe_strip(evidence.normalized_comment_hint),
            },
            "candidate_concepts": candidate_concepts,
            "semantic_context": symbol_context_pack,
            "retrieved_examples": retrieved_examples,
        })

    if not payload:
        return {}

    requested_names = [utils._safe_strip((item or {}).get("name")) for item in payload if utils._safe_strip((item or {}).get("name"))]
    remembered_terms = legacy._collect_preferred_symbol_names(missing_vars, limit=24)
    prompt_glossary = legacy._filter_glossary_for_prompt(glossary, [body, func_cn_name, func_desc], limit=12)
    quality_feedback = utils._safe_strip(getattr(cfg, "_ai_quality_feedback", ""))
    quality_focus_symbols = list(getattr(cfg, "_ai_quality_focus_symbols", ()) or ())
    quality_block = ""
    if quality_feedback or quality_focus_symbols:
        lines = ["质量回归要求："]
        if quality_feedback:
            lines.append(f"- {quality_feedback}")
        if quality_focus_symbols:
            lines.append(f"- 本轮优先收口这些标识符：{json.dumps(quality_focus_symbols, ensure_ascii=False)}")
        quality_block = "\n" + "\n".join(lines) + "\n"
    compact_prompt = build_local_naming_prompt(
        payload,
        func_cn_name=func_cn_name,
        func_desc=func_desc,
        function_semantic_summary=function_semantic_summary,
        prompt_glossary=prompt_glossary,
        remembered_terms=remembered_terms,
        cfg=cfg,
    )
    if quality_block:
        compact_prompt = compact_prompt.replace("规则：", f"{quality_block}规则：", 1)
    payload_by_name = {
        utils._safe_strip((item or {}).get("name")): dict(item or {})
        for item in (payload or [])
        if utils._safe_strip((item or {}).get("name"))
    }
    if _is_small_model_strict_mode(cfg, backend_module=legacy):
        prompt = f"""只输出JSON映射。
规则:
1. 若 locked_cn 非空，必须原样保留，cn_name 可返回空字符串。
2. 优先补 usage，不确定时 cn_name 返回空字符串。
3. cn_name 必须是短中文名，不能含英文，不能写用途句。
4. usage 只写动作或作用，不写\"用于/以便/供\"。
5. role_hint 与 role 仅辅助理解，不要照抄上下文注释。
6. 优先参考 function_semantic、semantic_context、project_concepts、candidate_concepts 与 retrieved_examples 的既有命名风格。
7. 若 producer_semantic_summary 指向某个返回结果/状态/位图的函数语义，应优先吸收该函数的领域词。
8. 不要被宏定义名、读取/比较/签名 这类泛化词带偏，名称应贴合当前函数语义角色。{quality_block if quality_block else ''}
函数:{json.dumps({'func_cn_name': func_cn_name or '', 'func_desc': func_desc or ''}, ensure_ascii=False, separators=(',', ':'))}
函数语义:{json.dumps(function_semantic_summary, ensure_ascii=False, separators=(',', ':'))}
术语:{json.dumps(prompt_glossary, ensure_ascii=False, separators=(',', ':'))}
已确认:{json.dumps(remembered_terms, ensure_ascii=False, separators=(',', ':'))}
输入:{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}
输出:{{"变量名":{{"cn_name":"","usage":"","confidence":0.0}}}}"""
    else:
        prompt = f"""你是严谨的系统工程文档助手。请为下列C局部变量，根据上下文片段推断中文\"名称\"和\"用途\"，输出严格JSON映射。
规则：
- 不要根据标识符后缀（_u16/_u32/i16/i32 等类型后缀）推测含义；后缀仅表示类型。
- 优先贴合函数中文名/功能说明来命名，保持语义一致，避免无关泛化。
- 不确定处在词尾标注\"(推测)\"，用途10~20字内，言简意赅。
{f'- 术语表优先：{json.dumps(prompt_glossary, ensure_ascii=False)}' if prompt_glossary else ''}
- 若某项已有 locked_cn 或 remembered_terms 中已有中文名，必须直接沿用该中文名，只补用途，不得改名。
- 优先使用 function_semantic、semantic_context、producer_semantic_summary、project_concepts、candidate_concepts；若 comment_hint 与 producer_call/producer_arg_tags/consumer_patterns 冲突，优先相信后者。
- role、symbol_profile、semantic_context 与 retrieved_examples 仅作为命名参考，最终名称要短、稳定、像术语，不要写成长句。
- 不要把“宏定义/签名/读取/比较/状态值/数据值”这类泛化词直接当作最终中文名，除非上下文明确就是该概念。
{quality_block}

函数中文名/说明：{func_cn_name or '(未提供)'} / {func_desc or '(未提供)'}
函数语义摘要：{json.dumps(function_semantic_summary, ensure_ascii=False)}
已确认术语：{json.dumps(remembered_terms, ensure_ascii=False)}

输入数据(仅供参考)：
{json.dumps(payload, ensure_ascii=False, indent=2)}

输出严格JSON（仅此，不要包含解释）：
{{
  "变量名1": {{"cn_name": "中文名称", "usage": "用途描述", "confidence": 0.0}},
  "变量名2": {{...}}
}}"""
    js = call_json(compact_prompt, cfg)
    if not isinstance(js, dict) or not js:
        js = call_json(prompt, cfg)
    if not isinstance(js, dict):
        return {}
    js = legacy._normalize_ai_var_keys(
        js,
        requested_names,
        max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
        min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
    )
    normalized = {}
    for name, item in js.items():
        if isinstance(item, dict):
            item = legacy._coerce_dict_keys(
                item,
                ("cn_name", "usage", "confidence"),
                aliases={
                    "name": "cn_name",
                    "cn": "cn_name",
                    "cname": "cn_name",
                    "cnname": "cn_name",
                    "purpose": "usage",
                    "desc": "usage",
                    "description": "usage",
                },
                max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
                min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
            )
        elif isinstance(item, str):
            item = {"cn_name": item}
        if isinstance(item, dict):
            allow_refine_cn = bool((local_lookup.get(name) or {}).get("allow_refine_cn"))
            locked_cn = utils._safe_strip((local_lookup.get(name) or {}).get("locked_cn"))
            if (not allow_refine_cn) and (not locked_cn):
                locked_cn = utils._safe_strip((local_lookup.get(name) or {}).get("cn_name"))
            item = naming_utils.rerank_symbol_candidate(name, item, allow_refine_cn=allow_refine_cn, locked_cn=locked_cn)
            accepted_cn = _should_accept_local_ai_cn_result(
                name,
                item={**dict(local_lookup.get(name) or {}), **dict(payload_by_name.get(name) or {})},
                candidate_cn=utils._safe_strip(item.get("cn_name")),
                semantic_context=dict((payload_by_name.get(name) or {}).get("semantic_context") or {}),
                candidate_concepts=list((payload_by_name.get(name) or {}).get("candidate_concepts") or []),
                retrieved_examples=list((payload_by_name.get(name) or {}).get("retrieved_examples") or []),
                backend_module=legacy,
            )
            if not accepted_cn:
                item["cn_name"] = ""
            model_conf = _clamp_score(item.get("confidence", 0.0))
            final_score = _calibrate_symbol_confidence(
                raw_ident=name,
                cn_name=utils._safe_strip(item.get("cn_name")),
                usage=utils._safe_strip(item.get("usage")),
                model_confidence=model_conf,
                allow_refine_cn=allow_refine_cn,
                locked_cn=locked_cn,
                semantic_context=dict((payload_by_name.get(name) or {}).get("semantic_context") or {}),
            )
            item["model_confidence"] = model_conf
            item["final_score"] = final_score
            item["confidence"] = final_score
        normalized[name] = item
        if isinstance(item, dict):
            legacy._remember_ai_symbol(
                name,
                utils._safe_strip(item.get("cn_name")),
                kind="symbols",
                confidence=float(item.get("final_score", item.get("confidence", 0.0)) or 0.0),
                cfg=cfg,
                source="ai_symbol",
            )
    return normalized


def enrich_with_ai(func_data: dict, cfg: Any, _runtime_module: Any = None):
    legacy = _resolve_backend_module(cfg, _runtime_module)
    parse_local_variables = _get_runtime_hook(_runtime_module, "parse_local_variables_from_body", legacy.parse_local_variables_from_body)
    parse_params = _get_runtime_hook(_runtime_module, "parse_params_from_prototype", legacy.parse_params_from_prototype)
    filter_locals_against_params = _get_runtime_hook(_runtime_module, "_filter_local_vars_against_params", legacy._filter_local_vars_against_params)
    infer_scope_symbol_names = _get_runtime_hook(_runtime_module, "infer_scope_symbol_names", legacy.infer_scope_symbol_names)

    detect_gaps_fn = getattr(_runtime_module, "detect_gaps", None) if _runtime_module is not None else None
    if not callable(detect_gaps_fn):
        def detect_gaps_fn(comment_info_obj, locals_obj, params_obj, in_map_obj, out_map_obj, func_info_obj=None, cfg_obj=None):
            return detect_gaps(
                comment_info_obj,
                locals_obj,
                params_obj,
                in_map_obj,
                out_map_obj,
                func_info=func_info_obj,
                cfg=cfg_obj,
                _runtime_module=_runtime_module,
            )

    ai_suggest_for_func_fn = getattr(_runtime_module, "ai_suggest_for_func", None) if _runtime_module is not None else None
    if not callable(ai_suggest_for_func_fn):
        def ai_suggest_for_func_fn(func_info_obj, body_obj, comment_info_obj, cfg_obj, **kwargs):
            return ai_suggest_for_func(
                func_info_obj,
                body_obj,
                comment_info_obj,
                cfg_obj,
                _runtime_module=_runtime_module,
                **kwargs,
            )

    ai_suggest_for_locals_batch_fn = getattr(_runtime_module, "ai_suggest_for_locals_batch", None) if _runtime_module is not None else None
    if not callable(ai_suggest_for_locals_batch_fn):
        def ai_suggest_for_locals_batch_fn(missing_vars_obj, locals_all_obj, body_obj, cfg_obj, **kwargs):
            return ai_suggest_for_locals_batch(
                missing_vars_obj,
                locals_all_obj,
                body_obj,
                cfg_obj,
                _runtime_module=_runtime_module,
                **kwargs,
            )

    comment_info = dict(func_data.get("comment_info") or {})
    func_info = dict(func_data.get("func_info") or {})
    body = func_data.get("body", "")
    file_context = dict(func_data.get("file_context") or {})
    family_prefix = utils._safe_strip(file_context.get("family_prefix")) or legacy._identifier_family_prefix(utils._safe_strip(func_info.get("func_name")))
    module_key = utils._safe_strip(file_context.get("module_key"))
    owner_func = utils._safe_strip(func_info.get("func_name"))
    source_file = utils._safe_strip(file_context.get("source_file"))
    owner_ret_type = utils._safe_strip(func_info.get("ret_type"))

    local_vars = parse_local_variables(body)
    params = parse_params(func_info)
    local_vars = filter_locals_against_params(
        local_vars,
        params,
        cfg=cfg,
        func_name=(func_info.get("func_name") or ""),
    )
    for item in local_vars:
        item["family_prefix"] = family_prefix
        item["module_key"] = module_key
        item["owner_func"] = owner_func
        item["source_file"] = source_file
        item["owner_ret_type"] = owner_ret_type
        item["scope"] = "local"
        item["direction"] = "local"
    neighbor_local_symbols = [
        utils._safe_strip((item or {}).get("name"))
        for item in (local_vars or [])
        if utils._safe_strip((item or {}).get("name"))
    ]
    for item in local_vars:
        item["allow_refine_cn"] = naming_utils.local_cn_needs_ai_refine(
            item,
            body=body,
            neighbor_symbols=[x for x in neighbor_local_symbols if x and x != utils._safe_strip((item or {}).get("name"))],
            comment_desc=utils._safe_strip((comment_info or {}).get("desc")),
            cfg=cfg,
            backend_module=legacy,
        )

    comment_local_backup: list[dict] = []
    comment_info_backup: dict = {}
    if cfg.ai_mode == 2:
        comment_info_backup = dict(comment_info)
        comment_info = {}
        for item in local_vars:
            comment_local_backup.append({
                "name": item.get("name", ""),
                "cn_name": item.get("cn_name", ""),
                "usage": item.get("usage", ""),
            })
            item["cn_name"] = ""
            item["usage"] = ""

    input_desc = utils._safe_strip(comment_info.get("input_desc"))
    output_desc = utils._safe_strip(comment_info.get("output_desc"))
    in_map = legacy.parse_param_desc(input_desc, strip_paren_content=True)
    out_map = legacy.parse_param_desc(output_desc)
    if cfg.ai_mode == 2 and not in_map and not out_map and comment_info_backup:
        in_map.update(legacy.parse_param_desc((comment_info_backup.get("input_desc") or ""), strip_paren_content=True))
        out_map.update(legacy.parse_param_desc((comment_info_backup.get("output_desc") or "")))
    param_ai_name_map = legacy._seed_symbol_memory_into_scope(
        comment_info,
        func_info,
        local_vars,
        params,
        in_map,
        out_map,
    )

    gaps = detect_gaps_fn(comment_info, local_vars, params, in_map, out_map, func_info, cfg)
    utils.vlog(cfg, f"AI Gaps for {func_info.get('func_name')}: {gaps['_stats']}")

    # 检查停止信号
    if utils.stop_requested(cfg) or getattr(cfg, "_user_cancelled", False):
        return local_vars, comment_info, param_ai_name_map

    if gaps["need_func_desc"] or gaps["need_func_cn_name"] or gaps.get("need_func_cn_refine"):
        sugg = ai_suggest_for_func_fn(
            func_info,
            body,
            comment_info,
            cfg,
            params=params,
            locals_=local_vars,
            in_map=in_map,
            out_map=out_map,
            file_context=file_context,
        )
        # AI 调用后再次检查取消
        if utils.stop_requested(cfg) or getattr(cfg, "_user_cancelled", False):
            return local_vars, comment_info, param_ai_name_map
        if sugg:
            original_desc_hint = utils._safe_strip((comment_info_backup or {}).get("desc") or (comment_info or {}).get("desc"))
            sugg["func_cn_name"] = legacy._normalize_function_cn_title(
                sugg.get("func_cn_name") or "",
                func_name=func_info.get("func_name", ""),
                comment_desc=original_desc_hint,
            )
            conf = sugg.get("confidence", 0.0)
            accept_low_conf_func = bool(cfg.ai_mode == 2 or _is_small_model_strict_mode(cfg, backend_module=legacy))
            if cfg.force_ai or conf >= cfg.ai_conf_func or accept_low_conf_func:
                current_title = utils._safe_strip(comment_info.get("func_cn_name"))

                retrieved_examples = naming_utils.retrieve_function_title_context(
                    {
                        "comment_info": dict(comment_info or {}),
                        "func_info": dict(func_info or {}),
                        "file_context": dict(file_context or {}),
                        "body": body,
                    },
                    cfg,
                )
                if gaps["need_func_cn_name"] and sugg["func_cn_name"]:
                    comment_info["func_cn_name"] = sugg["func_cn_name"]
                elif gaps.get("need_func_cn_refine") and sugg["func_cn_name"] and legacy._should_accept_refined_function_title(
                    current_title,
                    sugg["func_cn_name"],
                    func_name=utils._safe_strip(func_info.get("func_name")),
                    comment_desc=original_desc_hint,
                    examples=retrieved_examples,
                ):
                    comment_info["func_cn_name"] = sugg["func_cn_name"]
                if gaps["need_func_desc"] and sugg["desc"]:
                    comment_info["desc"] = _repair_function_desc_by_domain(
                        utils._safe_strip(func_info.get("func_name")),
                        sugg["desc"],
                        current_desc=original_desc_hint,
                    )

    # 检查停止信号
    if utils.stop_requested(cfg) or getattr(cfg, "_user_cancelled", False):
        return local_vars, comment_info, param_ai_name_map

    missing_locals = gaps["need_local_usages"]
    if missing_locals:
        sugg_locals = ai_suggest_for_locals_batch_fn(
            missing_locals,
            local_vars,
            body,
            cfg,
            func_cn_name=comment_info.get("func_cn_name", ""),
            func_desc=comment_info.get("desc", ""),
            glossary=file_context.get("glossary") or legacy.DOMAIN_GLOSSARY,
        )
        # AI 调用后再次检查取消
        if utils.stop_requested(cfg) or getattr(cfg, "_user_cancelled", False):
            return local_vars, comment_info, param_ai_name_map
        if sugg_locals:
            for item in local_vars:
                name = item["name"]
                if name in sugg_locals:
                    data = sugg_locals[name]
                    cn = utils._safe_strip(data.get("cn_name"))
                    usage = utils._safe_strip(data.get("usage"))
                    old_cn = utils._safe_strip(item.get("cn_name"))
                    if cn and legacy._is_strict_symbol_candidate_rejected(cn, raw_ident=name):
                        cn = ""
                    if cn and (legacy._is_missing_gap_text(old_cn) or legacy._looks_like_generic_local_cn_name(old_cn)):
                        item["cn_name"] = cn
                        legacy._remember_inferred_symbol(
                            name,
                            cn,
                            kind="symbols",
                            confidence=float(data.get("confidence", 0.72) or 0.72),
                            evidence_kinds=2,
                            cfg=cfg,
                            source="ai_local_batch",
                        )
                    elif cn and bool(item.get("allow_refine_cn")) and naming_utils.should_accept_refined_local_cn(
                        cn,
                        current_cn=old_cn,
                        item=item,
                        body=body,
                        neighbor_symbols=[x for x in neighbor_local_symbols if x and x != name],
                        comment_desc=utils._safe_strip((comment_info or {}).get("desc")),
                        cfg=cfg,
                        backend_module=legacy,
                    ):
                        item["cn_name"] = cn
                        legacy._remember_inferred_symbol(
                            name,
                            cn,
                            kind="symbols",
                            confidence=float(data.get("confidence", 0.72) or 0.72),
                            evidence_kinds=2,
                            cfg=cfg,
                            source="ai_local_batch_refine",
                        )
                    if usage and legacy._should_replace_local_usage_with_ai(item.get("usage"), old_cn or item.get("cn_name")):
                        item["usage"] = usage

    if comment_local_backup:
        backup_map = {item["name"]: item for item in comment_local_backup}
        for item in local_vars:
            name = item.get("name", "")
            if not name:
                continue
            backup = backup_map.get(name)
            if not backup:
                continue
            if not utils._safe_strip(item.get("cn_name")) and utils._safe_strip(backup.get("cn_name")):
                item["cn_name"] = backup["cn_name"]
            if not utils._safe_strip(item.get("usage")) and utils._safe_strip(backup.get("usage")):
                item["usage"] = backup["usage"]

    missing_params = gaps.get("need_param_names") or []
    if missing_params:
        param_entries = [{
            "name": param.get("name", ""),
            "type": param.get("type", ""),
            "usage": "",
            "cn_name": "",
            "family_prefix": family_prefix,
            "module_key": module_key,
            "owner_func": owner_func,
            "source_file": source_file,
            "owner_ret_type": owner_ret_type,
            "scope": "param",
            "direction": legacy._infer_param_direction_from_body(
                utils._safe_strip(param.get("name")),
                utils._safe_strip(param.get("type")),
                body,
            ),
        } for param in params]
        sugg_params = ai_suggest_for_locals_batch_fn(
            missing_params,
            param_entries,
            body,
            cfg,
            func_cn_name=comment_info.get("func_cn_name", ""),
            func_desc=comment_info.get("desc", ""),
            glossary=file_context.get("glossary") or legacy.DOMAIN_GLOSSARY,
        )
        if isinstance(sugg_params, dict):
            for name, item in sugg_params.items():
                cn = utils._safe_strip(item.get("cn_name"))
                if cn:
                    param_ai_name_map[name] = cn

    inferred_scope = infer_scope_symbol_names(
        local_vars,
        params,
        body=body,
        func_info=func_info,
        comment_info=comment_info,
        in_map=in_map,
        out_map=out_map,
        cfg=cfg,
    )
    for name, inference in inferred_scope.items():
        if inference.candidate_cn and name in in_map:
            param_ai_name_map[name] = inference.candidate_cn

    retry_local_names = [
        utils._safe_strip((item or {}).get("name"))
        for item in (local_vars or [])
        if utils._safe_strip((item or {}).get("name")) and _should_track_local_ai_gap(item, backend_module=legacy)
    ]
    if retry_local_names:
        neighbor_symbols = [str((item or {}).get("name") or "").strip() for item in (local_vars or []) if str((item or {}).get("name") or "").strip()]
        retry_sugg_locals = ai_suggest_for_locals_batch_fn(
            retry_local_names,
            local_vars,
            body,
            cfg,
            func_cn_name=comment_info.get("func_cn_name", ""),
            func_desc=comment_info.get("desc", ""),
            glossary=func_data.get("file_context", {}).get("glossary") or legacy.DOMAIN_GLOSSARY,
        )
        if isinstance(retry_sugg_locals, dict):
            for item in local_vars:
                name = utils._safe_strip(item.get("name"))
                if not name:
                    continue
                retry_item = retry_sugg_locals.get(name) or {}
                if not isinstance(retry_item, dict):
                    continue
                new_cn = utils._safe_strip(retry_item.get("cn_name"))
                new_usage = utils._safe_strip(retry_item.get("usage"))
                old_cn = utils._safe_strip(item.get("cn_name"))
                old_usage = utils._safe_strip(item.get("usage"))
                if new_cn and legacy._is_strict_symbol_candidate_rejected(new_cn, raw_ident=name):
                    new_cn = ""
                if new_cn and (legacy._is_missing_gap_text(old_cn) or legacy._looks_like_generic_local_cn_name(old_cn)):
                    item["cn_name"] = new_cn
                elif new_cn and bool(item.get("allow_refine_cn")) and naming_utils.should_accept_refined_local_cn(
                    new_cn,
                    current_cn=old_cn,
                    item=item,
                    body=body,
                    neighbor_symbols=[x for x in neighbor_symbols if x and x != name],
                    comment_desc=utils._safe_strip((comment_info or {}).get("desc")),
                    cfg=cfg,
                    backend_module=legacy,
                ):
                    item["cn_name"] = new_cn
                if new_usage and legacy._should_replace_local_usage_with_ai(old_usage, old_cn):
                    item["usage"] = new_usage
                final_cn = utils._safe_strip(item.get("cn_name"))
                comment_hint = utils._safe_strip(item.get("comment_hint"))
                if (legacy._is_missing_gap_text(final_cn) or legacy._looks_like_generic_local_cn_name(final_cn)) and legacy._looks_like_compact_cn_label(comment_hint):
                    item["cn_name"] = comment_hint

    backup_name_map = {
        str((item or {}).get("name") or "").strip(): str((item or {}).get("cn_name") or "").strip()
        for item in (comment_local_backup or [])
    }
    neighbor_symbols = [str((item or {}).get("name") or "").strip() for item in (local_vars or []) if str((item or {}).get("name") or "").strip()]
    for item in (local_vars or []):
        naming_utils.repair_local_cn_name_with_profile(
            item,
            body=body,
            neighbor_symbols=[x for x in neighbor_symbols if x and x != utils._safe_strip((item or {}).get("name"))],
            comment_desc=utils._safe_strip((comment_info or {}).get("desc")),
            backup_cn=backup_name_map.get(utils._safe_strip((item or {}).get("name")), ""),
            cfg=cfg,
            backend_module=legacy,
        )

    return local_vars, comment_info, param_ai_name_map


def _symbol_memory_kind_for_name(name: str, *, backend_module: Any = None) -> str:
    legacy = _resolve_backend_module(None, backend_module)
    ident = utils._safe_strip(name)
    if ident and re.fullmatch(r"[A-Z0-9_]+", ident):
        return "macros"
    return "symbols"


def _collect_unresolved_body_symbol_candidates(
    body: str,
    *,
    local_names: Optional[set[str]] = None,
    param_names: Optional[set[str]] = None,
    known_names: Optional[set[str]] = None,
    backend_module: Any = None,
) -> list[str]:
    legacy = _resolve_backend_module(None, backend_module)
    local_names = set(local_names or set())
    param_names = set(param_names or set())
    known_names = set(known_names or set())

    hits: list[str] = []
    lines = legacy._join_c_line_continuations(body or "").splitlines()
    for raw in lines:
        code, _comments = legacy._split_code_and_comments_for_symbol(raw)
        stmt = (code or "").strip()
        if not stmt or legacy.is_declaration_line(stmt):
            continue

        for match in legacy._C_IDENT_RE.finditer(stmt):
            name = match.group(0)
            if (
                (not name)
                or (name in legacy._C_KEYWORDS)
                or (name in local_names)
                or (name in param_names)
                or (name in known_names)
                or legacy._lookup_symbol_dictionary(name)
            ):
                continue
            if re.fullmatch(r"[A-Z0-9_]+", name):
                continue

            prev = stmt[:match.start()].rstrip()
            nxt = stmt[match.end():].lstrip()
            if prev.endswith(".") or prev.endswith("->"):
                continue
            if nxt.startswith("("):
                continue
            hits.append(name)
    return hits


def _collect_symbol_memory_warmup_candidates(
    func_entries: Sequence[dict],
    cfg: Optional[Any] = None,
    *,
    backend_module: Any = None,
) -> list[dict]:
    legacy = _resolve_backend_module(cfg, backend_module)
    max_candidates = max(1, int(utils.cfg_get_int(cfg, "symbol_memory_warmup_symbols", 24)))
    min_hits = max(1, int(utils.cfg_get_int(cfg, "symbol_memory_warmup_min_hits", 2)))

    counts: Counter[str] = Counter()
    snippets_map: dict[str, list[str]] = defaultdict(list)
    type_map: dict[str, set[str]] = defaultdict(set)

    for entry in (func_entries or []):
        body = utils._safe_text((entry or {}).get("body"))
        func_info = (entry or {}).get("func_info") or {}
        file_context = (entry or {}).get("file_context") or {}
        local_vars = legacy.parse_local_variables_from_body(body)
        params = legacy.parse_params_from_prototype(func_info)
        local_vars = legacy._filter_local_vars_against_params(local_vars, params)
        local_names = {
            utils._safe_strip((item or {}).get("name"))
            for item in (local_vars or [])
            if utils._safe_strip((item or {}).get("name"))
        }
        param_names = {
            utils._safe_strip((item or {}).get("name"))
            for item in (params or [])
            if utils._safe_strip((item or {}).get("name"))
        }
        known_names = {
            utils._safe_strip(name)
            for name in ((file_context.get("symbol_map") or {}).keys())
            if utils._safe_strip(name)
        }
        for item in list(local_vars or []) + list(params or []):
            name = utils._safe_strip((item or {}).get("name"))
            if (not name) or (not legacy._C_IDENT_RE.fullmatch(name)) or (name in legacy._C_KEYWORDS):
                continue
            if legacy._lookup_symbol_dictionary(name):
                continue
            counts[name] += 1
            vtype = utils._safe_strip((item or {}).get("type"))
            if vtype:
                type_map[name].add(vtype)
            for hit in legacy.collect_usage_snippets(body, name, 2):
                code = utils._safe_strip((hit or {}).get("code"))
                if code and code not in snippets_map[name]:
                    snippets_map[name].append(code)

        for name in _collect_unresolved_body_symbol_candidates(
            body,
            local_names=local_names,
            param_names=param_names,
            known_names=known_names,
            backend_module=legacy,
        ):
            counts[name] += 1
            for hit in legacy.collect_usage_snippets(body, name, 2):
                code = utils._safe_strip((hit or {}).get("code"))
                if code and code not in snippets_map[name]:
                    snippets_map[name].append(code)

    selected = []
    for name, hits in counts.most_common():
        if hits < min_hits:
            continue
        snippets = snippets_map.get(name) or []
        if not snippets:
            continue
        selected.append(
            {
                "name": name,
                "kind": _symbol_memory_kind_for_name(name, backend_module=legacy),
                "hits": int(hits),
                "types": sorted(type_map.get(name) or []),
                "examples": snippets[:4],
            }
        )
        if len(selected) >= max_candidates:
            break
    return selected


def _warmup_symbol_memory_once(
    func_entries: Sequence[dict],
    cfg: Any,
    *,
    scope_label: str,
    backend_module: Any = None,
) -> None:
    legacy = _resolve_backend_module(cfg, backend_module)
    call_llm_json_fn = getattr(backend_module, "call_llm_json", None) if backend_module is not None else None
    if not callable(call_llm_json_fn):
        call_llm_json_fn = call_llm_json
    if (not cfg) or (not getattr(cfg, "ai_assist", False)):
        return
    if not utils.cfg_get_int(cfg, "symbol_memory_warmup", 1):
        return
    if not ai_allows_context_warmup(cfg):
        utils.vlog(cfg, f"跳过项目符号记忆预热：AI 上下文范围为 {ai_context_scope(cfg)}")
        return
    if utils.stop_requested(cfg):
        return

    candidates = _collect_symbol_memory_warmup_candidates(func_entries, cfg, backend_module=legacy)
    if not candidates:
        return

    batch_size = max(4, int(utils.cfg_get_int(cfg, "symbol_memory_warmup_batch", 8)))
    glossary = legacy.DOMAIN_GLOSSARY
    utils.vlog(cfg, f"开始预热项目符号记忆：{scope_label}，候选 {len(candidates)} 个")
    for start in range(0, len(candidates), batch_size):
        if utils.stop_requested(cfg):
            break
        chunk = candidates[start:start + batch_size]
        prompt = f"""你是嵌入式软件术语整理助手。请根据 C 代码片段，为下面这些项目内高频符号生成稳定、保守的中文名称。
规则：
- 只根据给定片段和术语表判断，不要创造上下文里不存在的新缩写。
- 名称要短，偏中性；不确定就返回空字符串，不要硬猜。
- 同一项目内命名要保持一致；若术语表已能覆盖，优先沿用术语表。
- 只输出 JSON，不要解释。

术语表：
{json.dumps(glossary, ensure_ascii=False)}

输入：
{json.dumps(chunk, ensure_ascii=False, indent=2)}

        输出格式：
{{
  "symbol_name": {{"cn_name": "中文名", "confidence": 0.0}}
}}"""
        try:
            if call_llm_json_fn is call_llm_json:
                js = call_llm_json_fn(prompt, cfg, _runtime_module=legacy)
            else:
                js = call_llm_json_fn(prompt, cfg)
        except Exception as exc:
            utils.vlog(cfg, f"符号记忆预热失败：{exc}")
            return
        if not isinstance(js, dict):
            continue
        js = legacy._normalize_ai_var_keys(
            js,
            [item["name"] for item in chunk],
            max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
            min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
        )
        item_map = {item["name"]: item for item in chunk}
        for name, item in js.items():
            if isinstance(item, dict):
                item = legacy._coerce_dict_keys(
                    item,
                    ("cn_name", "confidence"),
                    aliases={"name": "cn_name", "cn": "cn_name"},
                    max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
                    min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
                )
                cn = utils._safe_strip(item.get("cn_name"))
                conf = float(item.get("confidence", 0.0) or 0.0)
            else:
                cn = utils._safe_strip(item)
                conf = 0.0
            meta = item_map.get(name) or {}
            legacy._remember_ai_symbol(
                name,
                cn,
                kind=str(meta.get("kind") or "symbols"),
                confidence=conf,
                cfg=cfg,
                source="ai_symbol_warmup",
            )


def _flatten_preprocessed_func_entries(preprocessed: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for c_path, pre in (preprocessed or {}).items():
        func_list = (pre or {}).get("func_list") or []
        for fd in func_list:
            fd2 = dict(fd)
            fc = dict((fd.get("file_context") or {}))
            fc["source_file"] = c_path
            fd2["file_context"] = fc
            out.append(fd2)
    return out


def _normalize_local_usage(cfg: Any, usage_text: str, var_name: str, cn_name: str, *, backend_module: Any = None) -> str:
    legacy = _resolve_backend_module(cfg, backend_module)

    def fallback_usage() -> str:
        name_for_desc = cn_name or var_name
        if not name_for_desc:
            return ""
        if name_for_desc.endswith("计数器"):
            return f"累计{name_for_desc[:-3]}"
        if name_for_desc.endswith("计数"):
            return f"累计{name_for_desc[:-2]}"
        if name_for_desc.endswith(("临时量", "临时值")):
            return f"暂存{name_for_desc}"
        if name_for_desc.endswith("快照"):
            return f"记录{name_for_desc}"
        return f"存放{name_for_desc}"

    if (
        getattr(cfg, "ai_assist", False)
        and usage_text
        and ("待人工修改" not in usage_text)
        and (not _looks_like_generic_local_usage(usage_text, cn_name, backend_module=legacy))
        and (not _looks_like_too_generic_usage_text(usage_text, backend_module=legacy))
    ):
        return usage_text

    lowered = str(var_name or "").lower()
    if any(tag in lowered for tag in ("idx", "index")):
        if cn_name and not legacy._looks_like_generic_local_cn_name(cn_name):
            return fallback_usage()
        return "临时变量"
    if re.search(r"(^|_)(i|j|k|ii|jj|kk)(_|$)", lowered) is not None:
        return "临时变量"
    if (not usage_text) or ("待人工修改" in usage_text) or ("存放" in usage_text) or _looks_like_too_generic_usage_text(usage_text, backend_module=legacy):
        return fallback_usage()
    return usage_text


def _needs_ai_local_usage_refine(item: dict, *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    usage = utils._safe_strip((item or {}).get("usage"))
    if legacy._is_missing_gap_text(usage):
        return True
    return usage.startswith(("存放", "缓存", "记录")) or _looks_like_too_generic_usage_text(usage, backend_module=legacy)


def _should_replace_local_usage_with_ai(old_usage: str, cn_name: str = "", *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    usage = utils._safe_strip(old_usage)
    if legacy._is_missing_gap_text(usage):
        return True
    if _looks_like_generic_local_usage(usage, cn_name, backend_module=legacy):
        return True
    if usage.startswith(("存放", "缓存", "记录")):
        return True
    if _looks_like_too_generic_usage_text(usage, backend_module=legacy):
        return True
    return False


def _looks_like_generic_local_usage(text: str, cn_name: str = "", *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    usage = utils._safe_strip(text)
    if not usage:
        return True
    if ("." in usage) or ("->" in usage):
        return False
    display = utils._safe_strip(cn_name)
    if legacy._looks_like_generic_local_cn_name(usage):
        return True
    if display and legacy._looks_like_generic_local_cn_name(display):
        if usage in {f"存放{display}", f"缓存{display}", f"记录{display}"}:
            return True
    return usage in {
        "存放中间变量",
        "存放中间量",
        "存放临时变量",
        "存放临时",
        "缓存临时",
        "缓存缓存值",
        "存放缓存值",
        "存放当前值",
        "存放变量值",
        "存放数据值",
    }


def _looks_like_too_generic_usage_text(text: str, *, backend_module: Any = None) -> bool:
    legacy = _resolve_backend_module(None, backend_module)
    usage = re.sub(r"\s+", "", utils._safe_strip(text))
    if not usage:
        return True
    if usage in {"读取", "获取", "比较", "判断", "保存", "记录", "缓存", "签名"}:
        return True
    if usage in {"生成自检签名", "缓存签名", "保存签名", "获取结果", "读取链路状态"}:
        return True
    if usage in {"计数异常", "异常计数", "临时计算", "临时处理"}:
        return True
    if usage.endswith(("临时计算", "临时处理", "结果比较", "状态比较")):
        return True
    if "宏定义" in usage:
        return True
    return False


def _collect_function_quality_report(
    local_vars: Sequence[dict],
    params: Sequence[dict],
    in_map: dict[str, str],
    out_map: dict[str, str],
    param_ai_name_map: dict[str, str],
    logic_lines: Optional[Sequence[str]],
    name_map: Optional[dict[str, str]],
    inferences: Sequence[Any] = (),
    *,
    backend_module: Any = None,
) -> dict[str, Any]:
    legacy = _resolve_backend_module(None, backend_module)
    unresolved_locals: list[str] = []
    for item in (local_vars or []):
        name = utils._safe_strip((item or {}).get("name"))
        if not name:
            continue
        cn_name = utils._safe_strip((item or {}).get("cn_name"))
        usage = utils._safe_strip((item or {}).get("usage"))
        if any(legacy._is_resolved_symbol_text(name, text) for text in (cn_name, usage)):
            continue
        unresolved_locals.append(name)

    unresolved_params: list[str] = []
    for item in (params or []):
        name = utils._safe_strip((item or {}).get("name"))
        if not name:
            continue
        desc_cn = utils._safe_strip(
            legacy._lookup_symbol_dictionary(name)
            or (in_map or {}).get(name)
            or (out_map or {}).get(name)
            or (param_ai_name_map or {}).get(name)
            or ""
        )
        if legacy._is_resolved_symbol_text(name, desc_cn):
            continue
        unresolved_params.append(name)

    symbol_candidates: list[str] = []
    for item in (local_vars or []):
        name = utils._safe_strip((item or {}).get("name"))
        if name:
            symbol_candidates.append(name)
    for item in (params or []):
        name = utils._safe_strip((item or {}).get("name"))
        if name:
            symbol_candidates.append(name)
    for name in (name_map or {}).keys():
        ident = utils._safe_strip(name)
        if (not ident) or legacy._is_macro_identifier(ident):
            continue
        symbol_candidates.append(ident)

    unresolved_logic_symbols: list[str] = []
    for ident in dict.fromkeys(symbol_candidates):
        pattern = re.compile(rf"\b{re.escape(ident)}\b")
        if any(pattern.search(utils._safe_text(line)) for line in (logic_lines or ())):
            unresolved_logic_symbols.append(ident)

    generic_logic_count = 0
    for line in (logic_lines or ()):
        text = utils._safe_strip(line)
        if not text or legacy._is_control_logic_line(text):
            continue
        if any(phrase in text for phrase in legacy._GENERIC_LOGIC_PHRASES):
            generic_logic_count += 1

    comment_leak_count = 0
    for line in (logic_lines or ()):
        text = utils._safe_strip(line)
        if not text:
            continue
        if any(mark in text for mark in ("用于", "以便", "防止", "避免", "TODO", "FIXME", "TESTONLY", "修改记录", "发布日期")):
            comment_leak_count += 1

    symbol_names: dict[str, set[str]] = defaultdict(set)
    over_translation_count = 0
    bad_symbol_guess_count = 0
    for inf in (inferences or ()):
        if not isinstance(inf, legacy.SymbolInference):
            continue
        ident = utils._safe_strip(inf.symbol)
        cn = utils._safe_strip(inf.candidate_cn)
        if not ident or not cn:
            continue
        symbol_names[ident].add(cn)
        if float(inf.confidence or 0.0) < 0.60:
            over_translation_count += 1
        explicit = legacy._lookup_symbol_dictionary(ident)
        if explicit and explicit != cn and float(inf.confidence or 0.0) >= 0.82:
            bad_symbol_guess_count += 1
    term_drift_count = sum(1 for vals in symbol_names.values() if len(vals) >= 2)

    generic_call_count = 0
    if logic_lines:
        for line in logic_lines:
            text = line.strip()
            if "调用函数" in text or re.search(r"调用[A-Za-z_]\w*函数", text):
                generic_call_count += 1

    thin_logic = bool(logic_lines is not None and len(logic_lines) <= 1)
    return {
        "unresolved_locals": tuple(unresolved_locals[:12]),
        "unresolved_params": tuple(unresolved_params[:12]),
        "unresolved_logic_symbols": tuple(unresolved_logic_symbols[:16]),
        "generic_logic_count": int(generic_logic_count),
        "generic_call_count": int(generic_call_count),
        "comment_leak_count": int(comment_leak_count),
        "term_drift_count": int(term_drift_count),
        "over_translation_count": int(over_translation_count),
        "bad_symbol_guess_count": int(bad_symbol_guess_count),
        "thin_logic": thin_logic,
    }


CONTROLLED_AI_ALLOWED_KEYS = ("summary", "logic_line_suggestions", "name_suggestions", "risk_notes")


def _controlled_issue(code: str, message: str, *, severity: str = "error", source: str = "controlled_ai") -> dict[str, Any]:
    return {
        "code": utils._safe_strip(code),
        "severity": utils._safe_strip(severity) or "error",
        "message": utils._safe_strip(message),
        "source": utils._safe_strip(source),
    }


def _controlled_ai_known_names(semantic_pack: Optional[dict[str, Any]], locked_names: Optional[dict[str, str]]) -> set[str]:
    known = {utils._safe_strip(k) for k in dict(locked_names or {}).keys() if utils._safe_strip(k)}
    pack = dict(semantic_pack or {})
    for key in ("name_map", "entity_aliases"):
        known.update(utils._safe_strip(k) for k in dict(pack.get(key) or {}).keys() if utils._safe_strip(k))
    for group in ("control_blocks", "state_updates", "call_roles", "return_actions", "pattern_hits"):
        for item in pack.get(group) or ():
            if not isinstance(item, dict):
                continue
            for ref in item.get("name_refs") or ():
                if isinstance(ref, dict):
                    raw = utils._safe_strip(ref.get("raw"))
                    if raw:
                        known.add(raw)
    return known


def _normalize_controlled_logic_suggestions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        out = []
        for key, text in value.items():
            out.append({"idx": str(key), "text": utils._safe_strip(text)})
        return [item for item in out if item.get("text")]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                text = utils._safe_strip(item.get("text") or item.get("line") or item.get("suggestion"))
                if text:
                    normalized = dict(item)
                    normalized["text"] = text
                    out.append(normalized)
            else:
                text = utils._safe_strip(item)
                if text:
                    out.append({"text": text})
        return out
    text = utils._safe_strip(value)
    return [{"text": text}] if text else []


def _normalize_controlled_name_suggestions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [
            {"raw": utils._safe_strip(raw), "display": utils._safe_strip(display)}
            for raw, display in value.items()
            if utils._safe_strip(raw) and utils._safe_strip(display)
        ]
    if isinstance(value, list):
        out = []
        for item in value:
            if not isinstance(item, dict):
                continue
            raw = utils._safe_strip(item.get("raw") or item.get("name") or item.get("ident"))
            display = utils._safe_strip(item.get("display") or item.get("cn") or item.get("text"))
            if raw and display:
                normalized = dict(item)
                normalized["raw"] = raw
                normalized["display"] = display
                out.append(normalized)
        return out
    return []


def _controlled_ai_condition_by_line(semantic_pack: Optional[dict[str, Any]]) -> dict[int, str]:
    by_line: dict[int, str] = {}
    for item in (dict(semantic_pack or {}).get("control_blocks") or ()):
        if not isinstance(item, dict):
            continue
        condition = utils._safe_strip(item.get("condition"))
        try:
            line_no = int(dict(item.get("range") or {}).get("start_line") or 0)
        except Exception:
            line_no = 0
        if line_no > 0 and condition:
            by_line[line_no] = condition
    return by_line


def _controlled_suggestion_line_no(item: dict[str, Any]) -> int:
    for key in ("source_line", "start_line", "line", "idx"):
        try:
            value = int(str(item.get(key) or "0").strip())
        except Exception:
            value = 0
        if value > 0:
            return value
    return 0


def validate_controlled_ai_candidate(
    candidate: Any,
    *,
    semantic_pack: Optional[dict[str, Any]] = None,
    expected_outputs: Sequence[str] = (),
    locked_names: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Validate AI JSON as a candidate layer, never as authoritative facts."""
    issues: list[dict[str, Any]] = []
    if not isinstance(candidate, dict):
        return {
            "accepted": False,
            "candidate": {},
            "issues": (_controlled_issue("invalid_json", "AI 输出不是 JSON 对象"),),
        }
    extra_keys = sorted(set(candidate.keys()) - set(CONTROLLED_AI_ALLOWED_KEYS))
    for key in extra_keys:
        issues.append(_controlled_issue("unexpected_key", f"AI 输出包含未允许字段：{key}", severity="warning"))
    sanitized = {
        "summary": utils._safe_strip(candidate.get("summary")),
        "logic_line_suggestions": _normalize_controlled_logic_suggestions(candidate.get("logic_line_suggestions")),
        "name_suggestions": _normalize_controlled_name_suggestions(candidate.get("name_suggestions")),
        "risk_notes": [utils._safe_strip(x) for x in (candidate.get("risk_notes") or []) if utils._safe_strip(x)] if isinstance(candidate.get("risk_notes"), list) else [],
    }
    known_names = _controlled_ai_known_names(semantic_pack, locked_names)
    locked = {utils._safe_strip(k): utils._safe_strip(v) for k, v in dict(locked_names or {}).items() if utils._safe_strip(k)}
    for item in sanitized["name_suggestions"]:
        raw = utils._safe_strip(item.get("raw"))
        display = utils._safe_strip(item.get("display"))
        if raw in locked and locked[raw] and display and display != locked[raw]:
            issues.append(_controlled_issue("locked_name_override", f"AI 试图覆盖锁定名称 {raw}: {locked[raw]} -> {display}"))
        if raw and known_names and raw not in known_names and re.fullmatch(r"[A-Za-z_]\w*(?:\.\w+|->\w+)*", raw):
            issues.append(_controlled_issue("invented_name", f"AI 提出了语义事实包中不存在的名称：{raw}"))

    ignored_idents = {"IF", "ELSE", "END", "WHILE", "FOR", "SWITCH", "CASE", "DEFAULT", "TRUE", "FALSE", "NULL"}
    for item in sanitized["logic_line_suggestions"]:
        text = utils._safe_text(item.get("text"))
        for ident in re.findall(r"\b[A-Za-z_]\w*\b", text):
            if ident in ignored_idents or ident in known_names:
                continue
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", ident):
                continue
            issues.append(_controlled_issue("invented_logic_symbol", f"AI 逻辑建议中出现未知标识符：{ident}"))
            break

    condition_by_line = _controlled_ai_condition_by_line(semantic_pack)
    for item in sanitized["logic_line_suggestions"]:
        line_no = _controlled_suggestion_line_no(item)
        condition = condition_by_line.get(line_no, "")
        text = utils._safe_text(item.get("text"))
        if "!=" in condition and "等于" in text and "不等于" not in text:
            issues.append(_controlled_issue("condition_relation_flip", f"第 {line_no} 行条件疑似从不等于反转为等于"))
        if "==" in condition and "不等于" in text:
            issues.append(_controlled_issue("condition_relation_flip", f"第 {line_no} 行条件疑似从等于反转为不等于"))

    joined = json.dumps(sanitized, ensure_ascii=False)
    for ident in expected_outputs or ():
        raw = utils._safe_strip(ident)
        if raw and raw not in joined:
            issues.append(_controlled_issue("missing_expected_output", f"AI 候选未覆盖源码输出：{raw}"))

    accepted = not any((item.get("severity") or "error") == "error" for item in issues)
    return {
        "accepted": accepted,
        "candidate": sanitized if accepted else {},
        "issues": tuple(issues),
    }


def ai_refine_logic_unknowns(unknown_list, code_context: str, cfg):
    """Use AI to refine logic unknown entries."""
    from . import logic as logic_utils

    if not unknown_list:
        return {}

    ai_policy = (getattr(cfg, "ai_logic_policy", "hybrid") or "hybrid").strip().lower()

    # ---------- TEXT 模式：index: 描述 ----------
    if getattr(cfg, "ai_logic_format", "text") == "text":
        def _item_line(u: dict) -> str:
            idx = u.get("idx")
            code = (u.get("code") or "").strip()
            code_cn = (u.get("code_cn") or "").strip()
            if code_cn and code_cn != code:
                return f"{idx}: {code_cn}    // 原始: {code}"
            return f"{idx}: {code}"

        items_text = "\n".join(_item_line(u) for u in unknown_list)

        style_extra = ""
        if ai_policy == "ai_non_structured":
            style_extra = """
        风格要求（重要）：
        - 避免每行都用"设置/计算"，优先用更贴近动作的动词：获取/读取/写入/赋值/累加/清零/拷贝/更新/判断/调用。
        - 对类似 `x = Func(...)`：用"调用 Func(...) 获取 x / 读取 Func(...) 写入 x"。
        - 对数组读写：用"从…取出… / 写入…到…"而不是机械"设置"。
        """

        prompt = f"""
        你是C代码流程图助手。根据给定代码行，输出对应的中文流程描述。

        规则：
        1. IF(cond) → "IF cond_cn"
        2. ELSE IF(cond) → "ELSE IF cond_cn"
        3. FOR(...) → "FOR 遍历索引 i 小于 N"
        4. SWITCH(expr) → "SWITCH 根据 expr 分支处理"
        5. CASE X: → "CASE 分支 X"
        6. return val; → "返回 val"
        7. 赋值 a = b; → 用自然中文描述（尽量把 b 也写出来）
        8. 调用 f(...) → 优先识别 memset/memcpy 等语义：
           - memset(x,0,...) → "清零 x"
           - memcpy(dst,src,...) → "拷贝 src 到 dst"
           其他调用 → "调用函数 f"
        9. 其他语句 → "执行操作"

        防幻觉规则 (重要):
        - 严禁对源码中的全大写宏名 (如 COMM_CCDL_RIU_EXT_PAGE1_ID) 做字母拆解, 不要输出"COMMbit2""COMMbit"等无意义片段; 保持宏名原样或直接使用 "扩展页" 等通用名词.
        - 严禁编造源码没有的数字 (倍数/参数值/阈值), 出现"X倍""Y次"且 X 不在源码中时, 改为"循环"或省略.
        - 严禁给函数添加源码未体现的"滤波""校验和计算""CRC"等处理; 把握不准时用"处理"或"调用函数 f".

        比较符号翻译：
        == 等于； != 不等于； > 大于； < 小于； >= 大于等于； <= 小于等于；
        && → 且； || → 或。

        输出格式（严格，无其他说明）：
        index: 描述

        {style_extra}

        下面是需要转换的代码：
        {items_text}

        只输出转换后的行：
        index: 描述
        """
        text = call_llm_text(prompt, cfg) or ""
        result = {}

        # 解析 "index: 描述"
        for line in text.splitlines():
            m = re.match(r'\s*(\d+)\s*[:：]\s*(.+)', line)
            if m:
                idx, msg = m.groups()
                result[idx] = msg.strip()

        # fallback：用规则生成缺失的行
        for u in unknown_list:
            key = str(u["idx"])
            if key not in result or not result[key]:
                # 强制使用严格格式 fallback
                result[key] = logic_utils.fallback_logic_line(u["code"])

        return result

    # ---------- JSON 模式：{"0": "..."} ----------
    compact = [{
        "index": u["idx"],
        "code": u["code"],
        "code_cn": (u.get("code_cn") or "").strip(),
        "polish_only": bool(u.get("polish_only")),
        "comment_hints": list(u.get("comment_hints") or []),
    } for u in unknown_list]

    prompt = f"""你是一名嵌入式软件详细设计说明撰写助手。
    下面是一段 C 函数的代码（上下文）：
    {code_context}
    下面是需要你补全/润色的伪代码条目。
    请基于对应代码行、已有中文动作(code_cn)及上下文，写出简洁、准确的中文动作说明（不超过20字，不要主观臆测业务逻辑），不要带句号。
    对赋值语句避免机械重复"设置/更新变量"，优先用：写入/赋给/清零/置位/累加/清除位/拷贝/计算/获取。
    comment_hints 仅作为理解提示，history/debug/purpose 类提示不允许直接写入最终动作说明。
    polish_only=true 表示只能在 code_cn 的事实范围内改善措辞，不得改变控制结构、不得新增业务含义。

    只返回 JSON，不要解释。

    需要润色的条目：
    {json.dumps(compact, ensure_ascii=False, indent=2)}

    输出格式示例：
    {{
    "0": "读取系统状态数据",
    "5": "清零所有故障计数",
    "8": "更新全局故障处理等级"
    }}"""
    js = call_llm_json(prompt, cfg)
    result = {}

    if isinstance(js, dict):
        for k, v in js.items():
            if isinstance(v, str) and v.strip():
                result[str(k)] = v.strip()

    # JSON 模式下同样加 fallback，避免轻量模型 JSON 乱写
    for u in unknown_list:
        key = str(u["idx"])
        if key not in result or not result[key]:
            result[key] = logic_utils.fallback_logic_line(u["code"])

    return result


def ai_suggest_bundle_one_call(*args, **kwargs):
    return legacy_backend().ai_suggest_bundle_one_call(*args, **kwargs)


def enrich_with_ai_compat(*args, **kwargs):
    return legacy_backend().enrich_with_ai(*args, **kwargs)


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "_fallback_function_description",
    "_sanitize_ai_desc",
    "_collect_function_quality_report",
    "_collect_symbol_memory_warmup_candidates",
    "_collect_unresolved_body_symbol_candidates",
    "_flatten_preprocessed_func_entries",
    "_get_ai_capability_profile",
    "_looks_like_codeish_description",
    "_looks_like_generic_local_usage",
    "_looks_like_too_generic_usage_text",
    "_looks_like_utf8_mojibake",
    "_needs_ai_local_usage_refine",
    "_parse_response_json_robust",
    "_repair_mojibake_text",
    "_safe_textish",
    "_should_replace_local_usage_with_ai",
    "_symbol_memory_kind_for_name",
    "_warmup_symbol_memory_once",
    "ai_suggest_bundle_one_call",
    "ai_suggest_for_func",
    "ai_suggest_for_locals_batch",
    "build_func_prompt",
    "build_func_title_prompt",
    "build_local_naming_prompt",
    "call_llm_json",
    "call_llm_text",
    "detect_gaps",
    "enrich_with_ai",
    "normalize_chat_completion_url",
    "_normalize_local_usage",
    "safe_json_loads",
    "strip_think_blocks",
    "validate_controlled_ai_candidate",
]
