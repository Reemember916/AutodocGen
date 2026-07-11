"""Rich context builder for LLM-first function naming.

Constructs structured prompts that give the LLM enough information to
understand what a C function does and name it appropriately in Chinese.

Design principles:
- Pure functions, no mutable state
- Returns prompt strings; caller handles LLM invocation
- Degrades gracefully when partial context is missing
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Sequence

from ._legacy_support import legacy_backend


def _safe_strip(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


# ---- body key operations extraction ----

def extract_body_key_operations(
    body: str,
    name_map: Optional[dict[str, str]] = None,
    *,
    max_conditions: int = 5,
    max_callees: int = 8,
    max_members: int = 5,
    backend_module: Any = None,
) -> str:
    """Extract conditions, callees, and member accesses for LLM context."""
    backend = backend_module or legacy_backend()
    nm = name_map or {}
    lines: list[str] = []

    # Conditions
    try:
        conds = backend._collect_condition_signatures_from_body(body)
        for c in conds[:max_conditions]:
            text = _safe_strip(c)
            if text:
                lines.append(f"- if ({text})")
    except Exception:
        pass

    # Callees
    try:
        callees = backend._collect_callee_names_from_body(body)
        for callee in callees[:max_callees]:
            cn = _safe_strip(nm.get(callee, ""))
            if cn and cn != callee:
                lines.append(f"- 调用 {callee}({cn})")
            else:
                lines.append(f"- 调用 {callee}()")
    except Exception:
        pass

    # Member accesses
    try:
        members = backend._collect_member_access_signatures_from_body(body)
        for m in members[:max_members]:
            text = _safe_strip(m)
            if text:
                lines.append(f"- 访问 {text}")
    except Exception:
        pass

    return "\n".join(lines) if lines else ""


# ---- local variable context ----

def extract_local_var_context(
    body: str,
    func_info: dict[str, Any],
    *,
    max_vars: int = 10,
    backend_module: Any = None,
) -> str:
    """Extract local variable declarations for LLM context."""
    backend = backend_module or legacy_backend()
    try:
        local_vars = backend.parse_local_variables_from_body(body)
        params = backend.parse_params_from_prototype(func_info)
    except Exception:
        return ""

    param_names = {_safe_strip((p or {}).get("name")) for p in (params or [])}
    local_vars = [
        v for v in (local_vars or [])
        if _safe_strip((v or {}).get("name")) not in param_names
    ]

    lines: list[str] = []
    for v in local_vars[:max_vars]:
        name = _safe_strip((v or {}).get("name"))
        vtype = _safe_strip((v or {}).get("type"))
        cn = _safe_strip((v or {}).get("cn_name"))
        if name:
            if cn and cn != name:
                lines.append(f"- {name} ({vtype}) - {cn}")
            else:
                lines.append(f"- {name} ({vtype})")

    return "\n".join(lines) if lines else ""


# ---- callee context ----

def extract_callee_context(
    body: str,
    name_map: Optional[dict[str, str]] = None,
    *,
    max_callees: int = 8,
    backend_module: Any = None,
) -> str:
    """Extract callee calls with Chinese name annotations."""
    backend = backend_module or legacy_backend()
    nm = name_map or {}
    lines: list[str] = []
    try:
        callees = backend._collect_callee_names_from_body(body)
        for callee in callees[:max_callees]:
            cn = _safe_strip(nm.get(callee, ""))
            if cn and cn != callee:
                lines.append(f"- {callee} -> {cn}")
            else:
                lines.append(f"- {callee}")
    except Exception:
        pass
    return "\n".join(lines) if lines else ""


# ---- module context ----

def extract_module_context(
    source_file: str,
    *,
    backend_module: Any = None,
) -> str:
    """Get module-level description from file header comment."""
    backend = backend_module or legacy_backend()
    if not source_file:
        return ""
    try:
        code = backend.load_c_file(source_file)
        return _safe_strip(backend._extract_module_cn_from_header(code))
    except Exception:
        return ""


# ---- prompt builders ----

def build_body_summary_prompt(
    func_data: dict[str, Any],
    *,
    backend_module: Any = None,
) -> str:
    """Build the LLM prompt for generating a one-sentence function body summary.

    This is the lighter first LLM call that summarises what the function does.
    The result is cached and fed into the naming prompt as context.
    """
    backend = backend_module or legacy_backend()
    func_info = func_data.get("func_info") or {}
    comment_info = func_data.get("comment_info") or {}
    file_context = func_data.get("file_context") or {}
    body = func_data.get("body") or ""

    func_name = _safe_strip(func_info.get("func_name"))
    prototype = _safe_strip(func_info.get("prototype"))
    source_file = _safe_strip(file_context.get("source_file"))
    comment_desc = _safe_strip(comment_info.get("desc"))
    symbol_map = file_context.get("symbol_map") or {}
    func_cn_map = file_context.get("func_cn_map") or {}
    name_map = dict(symbol_map)
    name_map.update(func_cn_map)

    module_hint = extract_module_context(source_file, backend_module=backend)
    key_ops = extract_body_key_operations(body, name_map, backend_module=backend)
    local_vars = extract_local_var_context(body, func_info, backend_module=backend)

    lines = [
        "你是嵌入式C代码分析专家。请用一句话中文描述以下函数的核心功能（≤40字），",
        "聚焦于：它整体做了什么操作（不是某个特定模式下的行为）、处理了什么数据、产生了什么输出。",
        "注意：描述函数的通用功能，不要限定于特定的运行模式/状态/场景。",
        "",
        f"函数名: {func_name}",
        f"函数签名: {prototype}",
        f"所在文件: {source_file}",
    ]
    if module_hint:
        lines.append(f"模块描述: {module_hint}")
    if comment_desc:
        lines.append(f"C注释功能描述: {comment_desc}")

    if key_ops:
        lines.append(f"\n函数体关键操作:\n{key_ops}")

    if local_vars:
        lines.append(f"\n局部变量:\n{local_vars}")

    lines.append("\n只返回中文描述，不要解释。")
    return "\n".join(lines)


def build_naming_prompt(
    func_data: dict[str, Any],
    body_summary: str = "",
    *,
    backend_module: Any = None,
) -> str:
    """Build the LLM prompt for generating a Chinese function name.

    This is the main naming call. It includes the full rich context:
    function signature, body summary, module context, callees, parameters,
    local variables, and neighbour functions.
    """
    backend = backend_module or legacy_backend()
    func_info = func_data.get("func_info") or {}
    comment_info = func_data.get("comment_info") or {}
    file_context = func_data.get("file_context") or {}
    body = func_data.get("body") or ""

    func_name = _safe_strip(func_info.get("func_name"))
    prototype = _safe_strip(func_info.get("prototype"))
    source_file = _safe_strip(file_context.get("source_file"))
    module_key = _safe_strip(file_context.get("module_key"))
    comment_desc = _safe_strip(comment_info.get("desc"))
    comment_func_cn = _safe_strip(comment_info.get("func_cn_name"))
    ret_type = _safe_strip(func_info.get("ret_type"))
    symbol_map = file_context.get("symbol_map") or {}
    func_cn_map = file_context.get("func_cn_map") or {}
    name_map = dict(symbol_map)
    name_map.update(func_cn_map)

    module_hint = extract_module_context(source_file, backend_module=backend)
    callee_text = extract_callee_context(body, name_map, backend_module=backend)
    key_ops = extract_body_key_operations(body, name_map, backend_module=backend)
    local_vars = extract_local_var_context(body, func_info, backend_module=backend)

    # Parameters
    param_lines: list[str] = []
    try:
        params = backend.parse_params_from_prototype(func_info)
        for p in (params or []):
            pname = _safe_strip(p.get("name"))
            ptype = _safe_strip(p.get("type"))
            if pname:
                cn = _safe_strip(name_map.get(pname, ""))
                if cn and cn != pname:
                    param_lines.append(f"- {ptype} {pname} ({cn})")
                else:
                    param_lines.append(f"- {ptype} {pname}")
    except Exception:
        pass

    # Neighbours
    raw_neighbors = file_context.get("neighbor_func_names") or []
    if isinstance(raw_neighbors, str):
        raw_neighbors = [raw_neighbors]
    neighbors = [
        n for n in (_safe_strip(n) for n in (raw_neighbors or ()))
        if n and n != func_name
    ]

    lines = [
        "你是嵌入式C代码分析专家。请根据以下信息为此C函数生成简洁的中文名。",
        "",
        f"函数名: {func_name}",
        f"函数签名: {prototype}",
        f"所在文件: {source_file}",
    ]
    if module_key:
        lines.append(f"模块标识: {module_key}")
    if module_hint:
        lines.append(f"模块描述: {module_hint}")
    if comment_func_cn:
        lines.append(f"C注释函数中文名: {comment_func_cn}")
    if comment_desc:
        lines.append(f"C注释功能描述: {comment_desc}")
    if body_summary:
        lines.append(f"函数体摘要（可能不完整，仅供参考）: {body_summary}")

    if callee_text:
        lines.append(f"\n调用关系:\n{callee_text}")

    if param_lines:
        lines.append("\n参数:")
        lines.extend(param_lines)

    if ret_type and ret_type != "void":
        lines.append(f"\n返回值类型: {ret_type}")

    if key_ops:
        lines.append(f"\n函数体关键操作（以这些事实为准）:\n{key_ops}")

    if local_vars:
        lines.append(f"\n局部变量:\n{local_vars}")

    if neighbors:
        lines.append(f"\n同文件相邻函数: {', '.join(neighbors[:5])}")

    callers = list(file_context.get("caller_funcs") or [])
    if callers:
        lines.append(f"调用本函数的函数: {', '.join(callers[:8])}")
    callees = list(file_context.get("callee_funcs") or [])
    if callees:
        lines.append(f"本函数调用的函数: {', '.join(callees[:8])}")

    lines.extend([
        "",
        "命名规则（严格遵循）:",
        "1. 中文名 ≤12 字，不用空格和标点。但如果函数名中含数字或专有缩写（如1394、CCDL、KZZZ），必须保留，可放宽到 ≤16 字",
        "2. 格式统一为\"对象/领域 + 动作\"，动作词尽量放末尾；常用动作：初始化/获取/读取/更新/校验/判定/处理/上传/发送/接收/打包/解包/转换/滤波/采集",
        "   例如：\"429接收处理\"、\"余度温度获取\"、\"周期自检状态更新\"；不要写成\"读取429接收状态...\"这类说明句",
        "3. 优先从 C 注释和模块描述中推断领域术语。C 注释中的 func_cn_name 如有中文直接使用",
        "4. 函数体摘要可能不完整或偏窄。以\"关键操作\"为准交叉验证：",
        "   如果摘要描述的场景只覆盖部分关键操作，请忽略摘要的窄化，基于全部关键操作命名",
        "   例如：摘要说\"加油模式下写入故障标志\"，但关键操作涵盖多种故障类型 → 应为\"故障动作应用\"而非\"加油故障写入\"",
        "5. 函数名应反映整体功能，不限定于特定模式/状态/场景",
        "",
        '返回JSON: {"name": "中文函数名", "confidence": 0.0-1.0}',
    ])
    return "\n".join(lines)


# ---- response parsers ----

_JSON_BLOCK_RE = re.compile(r'\{[^{}]*"name"[^{}]*\}', re.DOTALL)


def parse_summary_response(text: str) -> str:
    """Parse the LLM response for body summary. Extracts the first line of CJK text."""
    value = _safe_strip(text)
    if not value:
        return ""
    # Strip markdown code fences
    value = re.sub(r"^```\w*\s*", "", value)
    value = re.sub(r"\s*```$", "", value)
    # Take first line with CJK
    for line in value.splitlines():
        stripped = line.strip()
        if _contains_cjk(stripped) and len(stripped) >= 3:
            return stripped[:80]
    return value[:80]


def parse_naming_response(text: str) -> dict[str, Any]:
    """Parse the LLM JSON response for naming. Returns {'name': str, 'confidence': float}."""
    value = _safe_strip(text)
    if not value:
        return {"name": "", "confidence": 0.0}

    # Try direct JSON parse
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict) and "name" in parsed:
            return {
                "name": _safe_strip(parsed.get("name", "")),
                "confidence": float(parsed.get("confidence", 0.0)),
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Try to find JSON block
    match = _JSON_BLOCK_RE.search(value)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "name" in parsed:
                return {
                    "name": _safe_strip(parsed.get("name", "")),
                    "confidence": float(parsed.get("confidence", 0.0)),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Fallback: take first CJK line
    for line in value.splitlines():
        stripped = line.strip()
        if _contains_cjk(stripped) and len(stripped) >= 2:
            return {"name": stripped[:30], "confidence": 0.5}

    return {"name": value[:30], "confidence": 0.0}


# ---- variable batch naming ----

def build_variable_batch_prompt(
    func_data: dict[str, Any],
    *,
    func_cn_name: str = "",
    body_summary: str = "",
    backend_module: Any = None,
) -> str:
    """Build the LLM prompt for batch-translating all variables to Chinese.

    Takes a function's data, its already-resolved Chinese name, and body
    summary, then asks the LLM to name every parameter and local variable
    in one call.

    Returns a prompt string. The expected LLM response is a JSON object
    mapping variable names to Chinese names.
    """
    backend = backend_module or legacy_backend()
    func_info = func_data.get("func_info") or {}
    body = func_data.get("body") or ""

    func_name = _safe_strip(func_info.get("func_name"))
    prototype = _safe_strip(func_info.get("prototype"))

    # Collect parameters
    param_lines: list[str] = []
    try:
        params = backend.parse_params_from_prototype(func_info)
        for p in (params or []):
            pname = _safe_strip(p.get("name"))
            ptype = _safe_strip(p.get("type"))
            if pname:
                param_lines.append(f"  {pname} ({ptype})")
    except Exception:
        pass

    # Collect local variables
    local_lines: list[str] = []
    try:
        local_vars = backend.parse_local_variables_from_body(body)
        param_names = {_safe_strip((p or {}).get("name")) for p in (params or [])}
        for v in local_vars:
            vname = _safe_strip((v or {}).get("name"))
            if not vname or vname in param_names:
                continue
            vtype = _safe_strip((v or {}).get("type"))
            cn = _safe_strip((v or {}).get("cn_name"))
            comment = _safe_strip((v or {}).get("comment_hint"))
            parts = [f"  {vname} ({vtype})"]
            if cn and cn != vname:
                parts.append(f"注释={cn}")
            if comment:
                parts.append(f"说明={comment}")
            local_lines.append(" ".join(parts))
    except Exception:
        pass

    if not param_lines and not local_lines:
        return ""

    lines = [
        "你是嵌入式C代码分析专家。请为以下函数的所有参数和局部变量生成简洁的中文名。",
        "",
        f"函数名: {func_name}",
        f"函数签名: {prototype}",
    ]
    if func_cn_name:
        lines.append(f"函数中文名: {func_cn_name}")
    if body_summary:
        lines.append(f"函数功能摘要: {body_summary}")

    if param_lines:
        lines.append("")
        lines.append("参数:")
        lines.extend(param_lines)

    if local_lines:
        lines.append("")
        lines.append("局部变量:")
        lines.extend(local_lines)

    body = func_data.get("body") or ""
    if body:
        snippet = body.strip()
        if len(snippet) > 1500:
            snippet = snippet[:1500] + "\n/* ... 截断 ... */"
        lines.extend(["", "函数体（用于推断变量用途）:", "```c", snippet, "```"])
    lines.extend([
        "",
        "命名规则（严格遵循）:",
        "1. 每个中文名 ≤10 字，不用空格和标点",
        "2. 格式为\"领域/对象+属性\"（如\"位置指令\"、\"故障标志\"、\"滤波输出\"）",
        "3. 类型后缀（_u8/_u16/_u32/_f）和作用域前缀（l_/g_/s_）不翻译",
        "4. 如果变量名中包含英文缩写（如CCDL、KZZZ、1394），必须保留",
        "5. 结合函数功能和变量在代码中的用途推断，不要只看变量名本身",
        "",
        '返回JSON，键为变量名，值为中文名。例如: {"l_cmd_f": "位置指令", "l_cnt_u16": "计数器"}',
    ])
    return "\n".join(lines)


def parse_variable_batch_response(text: str) -> dict[str, str]:
    """Parse the LLM JSON response for variable batch naming.

    Returns a dict mapping variable names to Chinese names.
    """
    value = _safe_strip(text)
    if not value:
        return {}

    # Strip markdown code fences
    value = re.sub(r"^```\w*\s*", "", value)
    value = re.sub(r"\s*```$", "", value)

    # Try direct JSON parse
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {
                str(k): _safe_strip(v)
                for k, v in parsed.items()
                if k and _contains_cjk(str(v)) and _safe_strip(v)
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Try to find JSON block (greedy for nested)
    brace_re = re.compile(r'\{[^{}]*\}', re.DOTALL)
    for match in brace_re.finditer(value):
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and any(_contains_cjk(str(v)) for v in parsed.values()):
                return {
                    str(k): _safe_strip(v)
                    for k, v in parsed.items()
                    if k and _contains_cjk(str(v)) and _safe_strip(v)
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return {}


# ---- summary cache (session + persistent) ----

_SUMMARY_CACHE: dict[str, str] = {}
_SUMMARY_CACHE_PATH: str = ""
_SUMMARY_CACHE_DIRTY: bool = False


def _make_summary_cache_key(func_name: str, source_file: str, body_sha: str) -> str:
    return f"{source_file}::{func_name}::{body_sha}"


def _default_summary_cache_path(project_root: str) -> str:
    """Get default path for summary cache file in project directory."""
    import os
    root = os.path.abspath(os.path.expanduser(str(project_root or "").strip())) if project_root else ""
    if not root:
        return os.path.abspath("autodoc_summary_cache.json")
    return os.path.join(root, "autodoc_summary_cache.json")


def load_summary_cache(project_root: str = "") -> None:
    """Load persisted summary cache from project directory."""
    global _SUMMARY_CACHE, _SUMMARY_CACHE_PATH, _SUMMARY_CACHE_DIRTY
    import json as _json
    path = _default_summary_cache_path(project_root)
    _SUMMARY_CACHE_PATH = path
    try:
        if path and __import__("os").path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                _SUMMARY_CACHE.update({str(k): str(v) for k, v in data.items() if k and v})
    except Exception:
        pass


def save_summary_cache() -> None:
    """Persist summary cache to project directory (atomic write)."""
    global _SUMMARY_CACHE, _SUMMARY_CACHE_PATH, _SUMMARY_CACHE_DIRTY
    if not _SUMMARY_CACHE_PATH:
        return
    import json as _json
    import os as _os
    import tempfile as _tempfile
    parent = _os.path.dirname(_SUMMARY_CACHE_PATH) or "."
    _os.makedirs(parent, exist_ok=True)
    try:
        fd, tmp = _tempfile.mkstemp(prefix=".autodoc_summary_cache_", suffix=".json", dir=parent)
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(dict(_SUMMARY_CACHE), f, ensure_ascii=False, indent=2)
        _os.replace(tmp, _SUMMARY_CACHE_PATH)
        _SUMMARY_CACHE_DIRTY = False
    except Exception:
        pass


def get_cached_summary(func_name: str, source_file: str, body: str) -> str:
    """Get cached body summary for a function."""
    import hashlib
    body_sha = hashlib.sha256((body or "").encode("utf-8", errors="ignore")).hexdigest()[:16]
    key = _make_summary_cache_key(func_name, source_file, body_sha)
    return _SUMMARY_CACHE.get(key, "")


def put_cached_summary(func_name: str, source_file: str, body: str, summary: str) -> None:
    """Cache a body summary."""
    global _SUMMARY_CACHE_DIRTY
    import hashlib
    body_sha = hashlib.sha256((body or "").encode("utf-8", errors="ignore")).hexdigest()[:16]
    key = _make_summary_cache_key(func_name, source_file, body_sha)
    existing = _SUMMARY_CACHE.get(key, "")
    new_val = _safe_strip(summary)
    if new_val and new_val != existing:
        _SUMMARY_CACHE[key] = new_val
        _SUMMARY_CACHE_DIRTY = True
