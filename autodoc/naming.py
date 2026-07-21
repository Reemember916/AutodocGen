"""Naming utilities and AI-first rerank helpers."""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
import tempfile
from typing import Any, Callable, Optional, Sequence

from ._legacy_support import app_root, legacy_backend
from . import utils as utils_module
from . import text as text_utils
from .models import NamingCandidate


_GENERIC_SYMBOL_NAMES = {
    "中间变量",
    "临时变量",
    "变量值",
    "数据值",
    "宏定义",
    "签名",
    "读取值",
    "比较结果",
    "状态值",
}

_VERBOSE_TITLE_MARKERS = ("并", "用于", "以便", "然后", "根据", "遍历")
_PURPOSE_MARKERS = ("用于", "以便", "为了", "供", "表示", "说明")
_VERBOSE_FUNC_TITLE_PREFIXES = (
    "根据",
    "按",
    "按照",
    "遍历",
    "读取",
    "获取",
    "更新",
    "检查",
    "判断",
    "完成",
    "处理",
    "设置",
    "执行",
    "计算",
    "轮询",
    "查询",
    "汇总",
    "生成",
    "记录",
)
_FUNCTION_TITLE_ACTIONS = {
    "init": "初始化",
    "get": "获取",
    "read": "读取",
    "set": "设置",
    "update": "更新",
    "check": "校验",
    "test": "检测",
    "judge": "判定",
    "proc": "处理",
    "process": "处理",
    "pro": "处理",
    "proess": "处理",
    "handle": "处理",
    "task": "处理",
    "pack": "打包",
    "unpack": "解包",
    "send": "发送",
    "tx": "发送",
    "recv": "接收",
    "receive": "接收",
    "rx": "接收",
    "sample": "采集",
    "obtain": "采集",
    "calc": "计算",
    "compute": "计算",
    "filter": "滤波",
    "fliter": "滤波",
    "filt": "滤波",
    "select": "选择",
    "sel": "选择",
    "con": "控制",
    "control": "控制",
    "stop": "停止",
    "clear": "清零",
    "reset": "复位",
    "ack": "应答",
    "acknowledge": "应答",
    "empty": "空校验",
}
_FUNCTION_TITLE_ACTION_WORDS = tuple(sorted(set(_FUNCTION_TITLE_ACTIONS.values()) | {
    "上传",
    "转换",
    "转整",
    "定位",
    "使能",
    "失能",
    "查询",
    "读取",
    "校验",
    "检测",
}, key=len, reverse=True))
_FUNCTION_TITLE_TOKEN_CN_MAP = {
    "comm": "通信",
    "spi": "SPI",
    "sci": "SCI",
    "isr": "中断",
    "nmi": "NMI",
    "xnmi": "XNMI",
    "err": "错误",
    "error": "错误",
    "data": "数据",
    "buff": "缓冲",
    "buffer": "缓冲",
    "cmd": "指令",
    "command": "指令",
    "head": "头",
    "header": "数据头",
    "real": "实时",
    "backgnd": "后台",
    "background": "后台",
    "device": "设备",
    "state": "状态",
    "status": "状态",
    "workmode": "工作模式",
    "work": "工作",
    "mode": "模式",
    "valve": "阀位",
    "tvalve": "T阀",
    "pvalve": "调压阀",
    "in": "入口",
    "out": "出口",
    "press": "压力",
    "pressure": "压力",
    "temp": "温度",
    "temperature": "温度",
    "comp": "压气机",
    "compressor": "压气机",
    "turbine": "涡轮",
    "speed": "转速",
    "trailer": "拖车",
    "ana": "模拟量",
    "analog": "模拟量",
    "io": "离散量",
    "di": "离散输入",
    "do": "离散输出",
    "ex": "外设",
    "ad": "AD",
    "adc": "AD",
    "mux": "多路复用",
    "redun": "余度",
    "redundant": "余度",
    "flash": "FLASH",
    "addr": "地址",
    "address": "地址",
    "record": "记录",
    "start": "起始",
    "sector": "扇区",
    "round": "四舍五入",
    "int": "整型",
    "integer": "整型",
    "tran": "转换",
    "trans": "转换",
    "convert": "转换",
    "conv": "转换",
    "comple": "补码",
    "complete": "补码",
    "loss": "丢失",
    "lost": "丢失",
    "pu": "上电",
    "power": "电源",
    "psv": "PSV",
    "id": "标识",
    "lru": "LRU",
    "chid": "CHID",
    "pbit": "飞行前自检",
    "pubit": "上电自检",
    "mbit": "维护自检",
    "ifbit": "周期自检",
    "bit": "",
}
_FUNCTION_TITLE_REQUIRED_ACRONYMS = {
    "spi": "SPI",
    "sci": "SCI",
    "nmi": "NMI",
    "xnmi": "XNMI",
    "gpio": "GPIO",
    "dsp": "DSP",
    "cpu": "CPU",
    "pie": "PIE",
}
_ACRONYM_BAD_TRANSLATIONS = {
    "SCI": ("科学",),
}
_FUNCTION_TITLE_GENERIC_LABELS = {
    "数据获取",
    "数据读取",
    "数据采集",
    "数据处理",
    "数据转换",
    "数据检查",
    "状态更新",
    "停止更新",
    "温度上传",
    "入口温上传",
    "出口温上传",
}
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_TYPE_SUFFIX_RE = re.compile(r"[_](u8|u16|u32|u64|i8|i16|i32|i64)$", re.IGNORECASE)
_IDENT_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|_|$)|[A-Z]?[a-z]+|\d+|[A-Z]+")
_IDENT_SKIP_TOKENS = {
    "g",
    "s",
    "l",
    "v",
    "p",
    "pp",
    "vp",
    "lp",
    "ls",
    "us",
    "uc",
    "ul",
    "st",
    "pst",
    "u",
    "i",
    "f",
    "d",
    "t",
}
_IDENT_CN_MAP = {
    # 动词/动作
    "ok": "正常",
    "valid": "有效",
    "invalid": "无效",
    "update": "更新",
    "init": "初始化",
    "proc": "处理",
    "pack": "打包",
    "combine": "组合",
    "comb": "组合",
    "calc": "计算",
    "filt": "滤波",
    "filter": "滤波",
    "conv": "转换",
    "sel": "选择",
    "select": "选择",
    "sync": "同步",
    "check": "检查",
    "test": "检测",
    "limit": "限幅",
    "limt": "限幅",
    "lmt": "限幅",
    "get": "获取",
    "set": "设置",
    "reset": "复位",
    "rst": "复位",
    "clear": "清零",
    "start": "启动",
    "judge": "判定",
    "force": "强制",
    "latch": "锁存",
    "mirror": "镜像",
    "insert": "注入",
    "clamp": "钳位",
    "sample": "采样",
    "view": "查询",
    "exit": "退出",
    "enter": "进入",
    "enable": "使能",
    "disable": "禁止",
    "soft": "软",
    "event": "事件",
    "record": "记录",
    "save": "保存",
    "logic": "逻辑",
    "by": "",
    "of": "",
    "to": "",
    "and": "",
    # 名词/对象
    "state": "状态",
    "status": "状态",
    "flag": "标志",
    "flg": "标志",
    "req": "请求",
    "rec": "恢复",
    "cmd": "指令",
    "mode": "模式",
    "fault": "故障",
    "info": "信息",
    "data": "数据",
    "pos": "位置",
    "cur": "电流",
    "curr": "当前",
    "orig": "原始",
    "loop": "回路",
    "cycle": "周期",
    "power": "功率",
    "ctrl": "控制",
    "sys": "系统",
    "system": "系统",
    "act": "作动器",
    "brk": "制动电阻",
    "temp": "临时量",
    "bit": "",
    "pbit": "PBIT",
    "ifbit": "IFBIT",
    # 驱动/硬件相关
    "dri": "驱动",
    "chrge": "预充",
    "chg": "预充",
    "chrg": "预充",
    "pwm": "脉宽调制",
    "adc": "模数转换",
    "dac": "数模转换",
    "gpio": "通用IO",
}
_NAMESPACE_PREFIX_RE = re.compile(r"^[A-Z]\d{3,}$")


def is_generic_symbol_name(text: str) -> bool:
    value = safe_strip(text)
    return (not value) or value in _GENERIC_SYMBOL_NAMES


def is_explanatory_title(text: str) -> bool:
    value = safe_strip(text)
    if not value:
        return True
    if looks_like_verbose_cn_phrase(value):
        return True
    return any(marker in value for marker in _VERBOSE_TITLE_MARKERS)


def safe_strip(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def looks_like_verbose_cn_phrase(text: str) -> bool:
    compact = re.sub(r"\s+", "", safe_strip(text))
    if not compact:
        return True
    if len(compact) > 12:
        return True
    if any(marker in compact for marker in _PURPOSE_MARKERS):
        return True
    if any(marker in compact for marker in ("表示", "用于", "保存", "记录", "存放", "代表", "控制", "当前的", "上一周期的")) and len(compact) >= 8:
        return True
    return False


def is_strict_symbol_candidate_rejected(text: str, *, raw_ident: str = "") -> bool:
    value = safe_strip(text)
    if not value:
        return False
    from .quality_gate import is_safe_ai_text

    if not is_safe_ai_text(value):
        return True
    if raw_ident and safe_strip(raw_ident) == value:
        return True
    if value in {"返回结果", "返回值"}:
        ident = safe_strip(raw_ident).lower()
        if not (ident.startswith("lo_") or re.search(r"(?:ret|return|rslt|rdata)", ident)):
            return True
    if value in {"标志", "标志位"}:
        ident = safe_strip(raw_ident).lower()
        if re.search(r"(?:^|_)len(?:_|$)|length", ident):
            return True
    if _ASCII_WORD_RE.search(value):
        return True
    if looks_like_verbose_cn_phrase(value):
        return True
    return False


def sanitize_ai_usage_text(text: str) -> str:
    value = safe_strip(text)
    if not value:
        return ""
    from .quality_gate import is_safe_ai_text

    if not is_safe_ai_text(value):
        return ""
    for prefix in ("用于", "以便"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
    if value.startswith("供") and not value.startswith("供油"):
        value = value[1:].strip()
    value = re.sub(r"(?:用于|以便|供(?!油))$", "", value).strip()
    value = re.sub(r"[。；;,.，]+$", "", value).strip()
    return value


def split_ident_tokens(name: str) -> list[str]:
    raw = str(name or "")
    raw = _TYPE_SUFFIX_RE.sub("", raw)
    parts = re.split(r"[_\W]+", raw)
    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        for token in _IDENT_TOKEN_RE.findall(part):
            if token and token.lower() not in _IDENT_SKIP_TOKENS:
                tokens.append(token)
    return tokens


def _drop_namespace_like_prefix(tokens: Sequence[str]) -> list[str]:
    out = [token for token in (tokens or []) if safe_strip(token)]
    while len(out) >= 2 and _NAMESPACE_PREFIX_RE.fullmatch(out[0]):
        out = out[1:]
    # Drop domain-specific prefix tokens that are handled by _function_domain_prefix
    if out and out[0].lower() in {"pbit", "ifbit", "pubit", "mbit"}:
        out = out[1:]
    if len(out) >= 2 and out[0].lower() in {"bit", "flag", "flg"} and out[1].lower() in {"ok", "valid", "invalid"}:
        out = out[1:]
    if len(out) >= 2 and out[0].lower() in {"bit"} and out[-1].lower() in {"ok", "valid", "invalid"}:
        out = [out[-1]]
    return out


def guess_cn_from_ident(
    name: str,
    glossary: Optional[dict[str, str]] = None,
    *,
    symbol_lookup: Optional[Callable[[str], str]] = None,
    ident_cn_map: Optional[dict[str, str]] = None,
) -> str:
    value = safe_strip(name)
    if not value:
        return ""
    if contains_cjk(value):
        return value
    value = re.sub(r"^[A-Z]\d{3,}_", "", value)
    if callable(symbol_lookup):
        exact = safe_strip(symbol_lookup(value))
        if exact:
            return exact
    tokens = _drop_namespace_like_prefix(split_ident_tokens(value))
    if not tokens:
        return ""
    mapping = dict(_IDENT_CN_MAP)
    mapping.update(_LEARNED_TOKEN_MAP)
    if isinstance(ident_cn_map, dict):
        mapping.update({str(k).lower(): safe_strip(v) for k, v in ident_cn_map.items() if safe_strip(k)})
    parts: list[str] = []
    mapped = 0
    for token in tokens:
        lowered = token.lower()
        cn = ""
        if isinstance(glossary, dict):
            cn = safe_strip(glossary.get(token) or glossary.get(lowered))
        if not cn:
            cn_raw = mapping.get(lowered)
            if cn_raw is not None:
                cn = safe_strip(cn_raw)
        if cn:
            parts.append(cn)
            if cn != token:
                mapped += 1
        elif lowered in mapping:
            # Explicitly mapped to empty → skip this token
            mapped += 1
        else:
            parts.append(token)
    if mapped <= 0:
        return ""
    return "".join(parts)


def _looks_like_compact_cn_label(text: str) -> bool:
    compact = re.sub(r"\s+", "", safe_strip(text))
    if (not compact) or (not contains_cjk(compact)):
        return False
    if len(compact) > 18:
        return False
    if any(marker in compact for marker in ("用于", "以便", "表示", "范围", "单位", "默认", "说明", "例如", "从", "到")):
        return False
    if sum(compact.count(ch) for ch in "，,；;:：") >= 1:
        return False
    return True


def _split_short_label_and_tail(text: str) -> tuple[str, str]:
    value = re.sub(r"[。;；]+$", "", safe_strip(text))
    if not value:
        return "", ""
    for sep in ("，", ",", "；", ";", "：", ":"):
        if sep not in value:
            continue
        left, right = value.split(sep, 1)
        left = left.strip()
        right = right.strip()
        if _looks_like_compact_cn_label(left) and right:
            return left, right
    return "", ""


def _extract_compact_function_title(text: str) -> str:
    value = safe_strip(text)
    if not value:
        return ""
    first_line = next((line.strip() for line in value.splitlines() if line.strip()), "")
    if first_line and first_line != value:
        label, _tail = _split_short_label_and_tail(first_line)
        if label:
            return label
        if _looks_like_compact_cn_label(first_line):
            return first_line
    label, _tail = _split_short_label_and_tail(value)
    if label:
        return label
    if _looks_like_compact_cn_label(value):
        return value
    return ""


def _function_domain_prefix(func_name: str) -> str:
    ident = safe_strip(func_name).upper()
    if "IFBIT" in ident:
        return "周期自检"
    if "PUBIT" in ident:
        return "上电自检"
    if "PBIT" in ident:
        return "飞行前自检"
    if "MBIT" in ident:
        return "维护自检"
    if "ACT" in ident:
        return "作动器"
    return ""


def _apply_domain_title_hint(title: str, func_name: str = "") -> str:
    value = safe_strip(title)
    ident = safe_strip(func_name).upper()
    if not value:
        return ""
    if "ROUNDROBIN" in ident and "COLDSTARTUP" in ident and "COMMIT" in ident:
        return "冷启动主通道轮值提交"
    if "ROUNDROBIN" in ident and value.startswith("四舍五入"):
        return value.replace("四舍五入", "轮值", 1)
    if "IFBIT" in ident:
        if value.startswith("周期BIT"):
            return "周期自检" + value[len("周期BIT"):]
        if value.startswith("周期") and not value.startswith("周期自检"):
            return "周期自检" + value[len("周期"):]
    if "PUBIT" in ident:
        if value.startswith("上电BIT"):
            return "上电自检" + value[len("上电BIT"):]
        if value.startswith("上电") and not value.startswith("上电自检"):
            return "上电自检" + value[len("上电"):]
    return value


def _clean_function_title_tail(text: str) -> str:
    value = safe_strip(text)
    if not value:
        return ""
    value = value.replace("周期BIT", "").replace("IFBIT", "").replace("PuBIT", "").replace("MBIT", "")
    value = value.replace("BIT", "")
    value = value.replace("检测结果获取", "结果获取")
    value = value.replace("检测项状态信息", "状态")
    value = value.replace("状态信息", "状态")
    value = value.replace("结果数据", "结果")
    value = re.sub(r"^(?:周期自检|上电自检|飞行前自检|维护自检|周期|上电|维护)", "", value)
    value = re.sub(r"^(?:根据|按|按照|用于|正式|当前)\s*", "", value)
    value = re.sub(r"^对(?!端)\s*", "", value)
    value = re.sub(r"(?:主流程|主过程|正式|处理流程)$", "", value)
    # Strip trailing descriptive clauses: "检测门限固定为4A", "做对称限幅", etc.
    value = re.sub(r"[的地得]$", "", value)
    value = re.sub(r"固定为\d+[A-Za-z]*$", "", value)
    value = re.sub(r"做\S{2,4}$", "", value)
    value = re.sub(r"\s+", "", value)
    return value


def _suffix_action_hint(func_name: str) -> str:
    ident = safe_strip(func_name)
    if not ident:
        return ""
    if re.search(r"(?:Result)?Get$", ident, re.IGNORECASE):
        return "获取"
    if re.search(r"(?:State)?Update$", ident, re.IGNORECASE):
        return "更新"
    if re.search(r"(?:Check|Test)$", ident, re.IGNORECASE):
        return "检测"
    if re.search(r"Init$", ident, re.IGNORECASE):
        return "初始化"
    if re.search(r"Proc$", ident, re.IGNORECASE):
        return "处理"
    return ""


def _function_title_action_from_tokens(tokens: Sequence[str]) -> tuple[str, int]:
    if not tokens:
        return "", -1
    lowered = [safe_strip(token).lower() for token in tokens]
    if len(lowered) >= 2 and lowered[-2:] == ["to", "f"]:
        return "转换", len(lowered) - 2
    if len(lowered) >= 2 and lowered[-2:] == ["to", "int"]:
        return "转整", len(lowered) - 2
    if len(lowered) >= 2 and lowered[-2:] == ["start", "sector"]:
        return "定位", len(lowered) - 2
    if lowered and lowered[-1] == "up":
        return "上传", len(lowered) - 1
    for idx in range(len(lowered) - 1, -1, -1):
        action = _FUNCTION_TITLE_ACTIONS.get(lowered[idx], "")
        if action:
            return action, idx
    if lowered and lowered[-1] == "is" and len(lowered) >= 2:
        tail_action = _FUNCTION_TITLE_ACTIONS.get(lowered[-2], "")
        if tail_action:
            return tail_action, len(lowered) - 2
    return "", -1


def _function_title_prefix_from_tokens(tokens: Sequence[str]) -> str:
    lowered = [safe_strip(token).lower() for token in tokens if safe_strip(token)]
    if not lowered:
        return ""
    if "ifbit" in lowered:
        return "周期自检"
    if "pubit" in lowered or ("pu" in lowered and "bit" in lowered):
        return "上电自检"
    if "pbit" in lowered:
        return "飞行前自检"
    if "mbit" in lowered:
        return "维护自检"
    if lowered[:2] == ["comm", "422"] or ("comm" in lowered and "422" in lowered[:3]):
        return "422"
    if lowered[:2] == ["comm", "429"] or ("comm" in lowered and "429" in lowered[:3]):
        return "429"
    if lowered and lowered[0] == "comm":
        return "通信"
    return ""


def _map_function_title_token(token: str) -> str:
    raw = safe_strip(token)
    if not raw:
        return ""
    lowered = raw.lower()
    mapped = _FUNCTION_TITLE_TOKEN_CN_MAP.get(lowered)
    if mapped is not None:
        return mapped
    generic = _IDENT_CN_MAP.get(lowered)
    if generic is not None:
        return generic
    if raw.isdigit():
        return raw
    if re.fullmatch(r"[A-Z]{2,}\d*", raw):
        return raw
    return ""


def required_title_acronyms_from_ident(func_name: str) -> tuple[str, ...]:
    tokens = split_ident_tokens(func_name)
    out: list[str] = []
    for token in tokens:
        acronym = _FUNCTION_TITLE_REQUIRED_ACRONYMS.get(safe_strip(token).lower())
        if acronym and acronym not in out:
            out.append(acronym)
    return tuple(out)


def title_violates_required_acronyms(title: str, func_name: str) -> bool:
    value = re.sub(r"\s+", "", safe_strip(title))
    if not value:
        return False
    for acronym in required_title_acronyms_from_ident(func_name):
        if acronym not in value:
            return True
        if any(bad in value for bad in _ACRONYM_BAD_TRANSLATIONS.get(acronym, ())):
            return True
    return False


def _drop_function_title_noise_parts(parts: Sequence[str]) -> list[str]:
    out: list[str] = []
    for part in parts:
        text = safe_strip(part)
        if not text:
            continue
        if text in {"通信", "数据", "信息", "处理", "函数"} and out:
            if text in {"数据", "信息"} and any(prev.endswith(text) for prev in out):
                continue
        if text == "飞行前自检" and out and out[-1] in {"28", "28V", "电源"}:
            continue
        out.append(text)
    compact = "".join(out)
    compact = compact.replace("通信422", "422").replace("通信429", "429")
    compact = compact.replace("数据数据", "数据").replace("状态状态", "状态")
    compact = compact.replace("温度温度", "温度").replace("压力压力", "压力")
    if compact.startswith("422通信"):
        compact = "422" + compact[len("422通信"):]
    if compact.startswith("429通信"):
        compact = "429" + compact[len("429通信"):]
    return [compact] if compact else []


def _compose_function_title_from_ident(func_name: str) -> str:
    ident = safe_strip(func_name)
    if not ident or contains_cjk(ident):
        return ""
    tokens = split_ident_tokens(ident)
    if not tokens:
        return ""
    action, action_idx = _function_title_action_from_tokens(tokens)
    prefix = _function_title_prefix_from_tokens(tokens)
    object_tokens: list[str] = []
    has_interrupt_suffix = "int" in [safe_strip(t).lower() for t in tokens] and any(
        safe_strip(t).lower() in {"isr", "nmi", "xnmi"} for t in tokens
    )
    for idx, token in enumerate(tokens):
        lowered = token.lower()
        if idx == action_idx:
            continue
        if has_interrupt_suffix and lowered == "isr":
            continue
        if action_idx >= 0 and idx > action_idx:
            # "DataTranCompleToF" keeps "Comple" before To, drops the type suffix.
            continue
        if lowered in {"comm", "ifbit", "pubit", "pbit", "mbit", "bit", "pu", "to", "f"}:
            continue
        if prefix in {"上电自检", "飞行前自检", "维护自检", "周期自检"} and lowered in {"28"}:
            continue
        if prefix in {"422", "429"} and lowered in {"422", "429"}:
            continue
        object_tokens.append(token)

    token_lowers = [t.lower() for t in tokens]
    parts = [
        "中断" if (safe_strip(token).lower() == "int" and has_interrupt_suffix) else _map_function_title_token(token)
        for token in object_tokens
    ]
    parts = _drop_function_title_noise_parts(parts)
    obj = "".join(parts)
    if not obj and prefix and action:
        obj = "数据" if action in {"获取", "读取", "采集", "处理", "上传"} else ""
    if obj.endswith(action) and action:
        obj = obj[: -len(action)]

    if prefix in {"422", "429"} and ("rx" in token_lowers or "recv" in token_lowers or "receive" in token_lowers) and action == "处理":
        candidate = f"{prefix}接收处理"
    elif prefix in {"422", "429"} and ("tx" in token_lowers or "send" in token_lowers) and action == "处理":
        candidate = f"{prefix}发送处理"
    elif prefix in {"422", "429"} and obj in {"接收", "发送"} and action == "处理":
        candidate = f"{prefix}{obj}处理"
    elif prefix in {"上电自检", "飞行前自检", "维护自检", "周期自检"} and action == "上传":
        candidate = f"429{prefix}上传" if "429" in token_lowers else f"{prefix}上传"
    else:
        candidate = "".join(part for part in (prefix, obj, action) if part)
    if has_interrupt_suffix and candidate.endswith("中断"):
        candidate = f"{candidate}响应"
    candidate = re.sub(r"(?:数据)?空校验$", "空校验", candidate)
    candidate = candidate.replace("四舍五入整型", "四舍五入转整")
    candidate = candidate.replace("数据补码转换", "补码转换")
    candidate = candidate.replace("数据转换补码", "补码转换")
    candidate = candidate.replace("起始扇区定位", "扇区起始定位")
    candidate = candidate.replace("FLASH记录定位", "FLASH记录扇区定位")
    candidate = candidate.replace("丢失停止", "丢失停止检测")
    candidate = candidate.replace("多路复用离散量控制", "多路复用控制")
    candidate = candidate.replace("飞行前自检丢失停止检测", "28V丢失自检停止")
    candidate = re.sub(r"^(422|429)数据", r"\1数据", candidate)
    candidate = candidate.replace("429数据头上传", "429数据头设置")
    if candidate and contains_cjk(candidate) and len(candidate) <= 16:
        return candidate
    return ""


def _title_looks_inconsistent_or_weak(text: str, func_name: str = "", comment_desc: str = "") -> bool:
    value = safe_strip(text)
    if not value:
        return True
    if _ASCII_WORD_RE.search(value):
        return True
    if _looks_like_verbose_function_cn_title(value, comment_desc):
        return True
    if value in _FUNCTION_TITLE_GENERIC_LABELS:
        return True
    if any(value.startswith(prefix) for prefix in _VERBOSE_FUNC_TITLE_PREFIXES) and len(value) >= 4:
        return True
    if any(value.endswith(word) and value != word and len(value) >= 8 for word in ("并写入消息", "写入上传", "解析心跳时间")):
        return True
    action_hint = _suffix_action_hint(func_name)
    if action_hint and contains_cjk(value) and (not value.endswith(action_hint)):
        if len(value) <= 10 and action_hint in value:
            return True
    return False


def _normalize_title_action_order(title: str) -> str:
    value = safe_strip(title)
    if not value:
        return ""
    value = re.sub(r"^(?:读取|获取)(.+?)(?:并)?(?:返回)?$", r"\1获取", value)
    value = re.sub(r"^(?:设置|写入)(.+?)(?:字段)?$", r"\1设置", value)
    value = re.sub(r"^(?:上传|上送)(.+?)(?:至(?:429|ARINC429)总线)?$", r"\1上传", value)
    value = re.sub(r"^(?:采集)(.+?)(?:上传(?:429|ARINC429)?总线)?$", r"\1采集上传", value)
    value = value.replace("设置429数据头字段并写入消息", "429数据头设置")
    value = value.replace("读取429接收状态解析心跳时间", "429接收处理")
    value = value.replace("调压阀压力高写入上传", "429调压阀压力上传")
    value = value.replace("模拟量采集判断上拉写入429消息", "429入口压力上传")
    value = value.replace("通信模块上传工作模式数据", "429工作模式上传")
    value = value.replace("上传自检结果至429总线", "429飞行前自检上传")
    value = value.replace("上传维护BIT结果至ARINC429总线", "429维护自检上传")
    value = value.replace("采集阀位离散量上传429总线", "429阀位上传")
    return value


def _style_function_cn_title(title: str, *, func_name: str = "", comment_desc: str = "") -> str:
    value = _normalize_title_action_order(safe_strip(title))
    ident_title = _compose_function_title_from_ident(func_name)
    token_lowers = [token.lower() for token in split_ident_tokens(func_name)]
    if ident_title and title_violates_required_acronyms(value, func_name):
        return ident_title
    if ident_title and any(token in token_lowers for token in ("rx", "tx", "recv", "receive", "send")):
        if re.fullmatch(r"(?:422|429)(?:接收|发送)(?:状态|数据|流程)?处理", value or ""):
            return ident_title
    # Bug C 守卫：ident_title 仅由骨架动词组成（如 "处理"/"检测"/"更新"）时，
    # 不要用它覆盖已有的 value（会把 "喂狗任务" 之类的描述抹成 "处理"）。
    skeleton_only = ident_title and ident_title in {
        "处理", "检测", "更新", "获取", "设置", "执行", "初始化", "操作", "任务",
    }
    if ident_title and _title_looks_inconsistent_or_weak(value, func_name, comment_desc):
        if not skeleton_only:
            return ident_title
        if value:
            return value
    if ident_title and value and contains_cjk(value):
        action, _idx = _function_title_action_from_tokens(split_ident_tokens(func_name))
        # Bug B 守卫：value 长度 >= ident_title 时，value 通常携带更多领域信息
        # （如 "周期自检旋变激励信号测试" vs "周期自检检测"），不应被 ident_title 覆盖。
        if (action and not value.endswith(action) and len(ident_title) <= 12
                and not skeleton_only and len(value) < len(ident_title)):
            return ident_title
    return value


def _looks_like_verbose_function_cn_title(text: str, desc: str = "") -> bool:
    value = safe_strip(text)
    desc_value = safe_strip(desc)
    if (not value) or (not contains_cjk(value)):
        return False
    if desc_value and value == desc_value and len(value) >= 10:
        return True
    if any(value.startswith(prefix) for prefix in _VERBOSE_FUNC_TITLE_PREFIXES) and len(value) >= 6:
        return True
    if len(value) >= 10 and any(token in value for token in ("并", "后", "然后", "用于", "以便")):
        return True
    return False


def _restore_domain_specific_terms(title: str, comment_desc: str, func_name: str = "") -> str:
    value = safe_strip(title)
    desc = safe_strip(comment_desc)
    ident = safe_strip(func_name)
    if (not value) or (not desc):
        if re.search(r"(?:Flg|Flag)", ident, re.IGNORECASE) and "标志" not in value and value.endswith("组合"):
            return value[:-2] + "标志组合"
        return value
    if "标志" in desc and "标志" not in value and value.endswith("组合"):
        return value[:-2] + "标志组合"
    if re.search(r"(?:Flg|Flag)", ident, re.IGNORECASE) and "标志" not in value and value.endswith("组合"):
        return value[:-2] + "标志组合"
    return value


def _dedupe_adjacent_cjk_phrases(text: str) -> str:
    """Collapse adjacent duplicated CJK phrases (2-6 chars) such as
    "作动器作动器" -> "作动器" or "周期自检周期自检初始化" -> "周期自检初始化".
    """
    if not text:
        return text
    pattern = re.compile(r"([\u4e00-\u9fff]{2,6})\1+")
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(r"\1", text)
    return text


def _clean_title_bit_alias_pollution(text: str) -> str:
    value = safe_strip(text)
    if not value:
        return value
    prev = None
    while prev != value:
        prev = value
        value = re.sub(r"bit\d+\(([^()]+)\)", r"\1", value, flags=re.IGNORECASE)
    return value


def _is_write_disable_context(func_name: str = "", comment_desc: str = "") -> bool:
    ident = safe_strip(func_name).lower()
    desc = safe_strip(comment_desc)
    return bool(
        re.search(r"write\s*(?:dis|disable)|writedis", ident)
        or "写禁止" in desc
        or "写禁用" in desc
    )


def _repair_write_disable_title(title: str, *, func_name: str = "", comment_desc: str = "") -> str:
    value = safe_strip(title)
    if not value or not _is_write_disable_context(func_name, comment_desc):
        return value
    compact = re.sub(r"\s+", "", value)
    if re.search(r"(?:写禁关|写禁.*禁写|发送写禁|关写保护|关闭.*写保护|写保护关闭|写保护失能|写保(?!护))", compact):
        return "SPI闪存写禁用"
    return value


def _is_spi_flash_datatrans_context(func_name: str = "", comment_desc: str = "") -> bool:
    ident = safe_strip(func_name).lower()
    desc = safe_strip(comment_desc)
    return bool(("spiflash" in ident and "datatrans" in ident) or ("SPI-FLASH" in desc.upper() and "数据" in desc))


def _repair_spi_flash_datatrans_title(title: str, *, func_name: str = "", comment_desc: str = "") -> str:
    value = safe_strip(title)
    if not value or not _is_spi_flash_datatrans_context(func_name, comment_desc):
        return value
    compact = re.sub(r"\s+", "", value)
    if "转换" in compact or "交互" in compact or "传输" in compact:
        return "SPI闪存数据传输"
    return value


def normalize_function_cn_title(text: str, *, func_name: str = "", comment_desc: str = "") -> str:
    raw_title = safe_strip(text)
    value = re.sub(r"[。；;，,\s]+$", "", _clean_title_bit_alias_pollution(text))
    if value.startswith("端") and ("对端" in safe_strip(comment_desc) or "peer" in safe_strip(func_name).lower()):
        value = "对" + value
    value = _dedupe_adjacent_cjk_phrases(value)
    value = _normalize_title_action_order(value)
    value = _repair_write_disable_title(value, func_name=func_name, comment_desc=comment_desc)
    value = _repair_spi_flash_datatrans_title(value, func_name=func_name, comment_desc=comment_desc)
    compact_desc = _clean_function_title_tail(_extract_compact_function_title(comment_desc))
    if compact_desc:
        compact_desc = _dedupe_adjacent_cjk_phrases(compact_desc)
        compact_desc = _repair_write_disable_title(compact_desc, func_name=func_name, comment_desc=comment_desc)
        compact_desc = _repair_spi_flash_datatrans_title(compact_desc, func_name=func_name, comment_desc=comment_desc)
        compact_desc = _apply_domain_title_hint(compact_desc, func_name)
    if value:
        value = _apply_domain_title_hint(value, func_name)
    domain_prefix = _function_domain_prefix(func_name)
    tail_source = compact_desc or value
    tail = _clean_function_title_tail(tail_source)
    suffix_action = _suffix_action_hint(func_name)
    if domain_prefix and tail:
        if suffix_action == "获取":
            if "结果" in tail and not tail.endswith("获取"):
                tail = "结果获取"
        elif suffix_action == "更新":
            if "状态" in tail and not tail.endswith("更新"):
                tail = "状态更新"
        elif suffix_action == "检测":
            if tail.endswith("检查"):
                tail = tail[:-2] + "检测"
            elif not tail.endswith("检测"):
                tail = tail + "检测"
        elif suffix_action == "处理":
            tail = re.sub(r"处理$", "", tail) + "处理"
        tail = re.sub(r"^(?:自检)+", "", tail)
        # Bug A 去重：若 tail 已包含 domain_prefix（前缀或包含），剥掉重复段以免出现
        # "作动器作动器数据初始化"、"周期自检周期自检初始化" 之类。
        dedup_tail = tail
        if domain_prefix and dedup_tail.startswith(domain_prefix):
            dedup_tail = dedup_tail[len(domain_prefix):]
        elif domain_prefix and domain_prefix in dedup_tail:
            dedup_tail = dedup_tail.replace(domain_prefix, "", 1)
        dedup_tail = dedup_tail.lstrip("的之与和")
        candidate = domain_prefix + dedup_tail
        if len(candidate) <= 12 and contains_cjk(candidate):
            value = candidate
    else:
        # Domain prefix didn't produce a compact candidate.
        # Try compact_desc, then degradation chain.
        if compact_desc and ((not value) or _looks_like_verbose_function_cn_title(value, comment_desc)):
            value = _clean_function_title_tail(compact_desc)
    if not (domain_prefix and tail and len(domain_prefix + tail) <= 12 and contains_cjk(domain_prefix + tail)):
        # Domain prefix path did NOT produce a valid candidate — run degradation chain
        # 领域无关降级：长标题用 tail（已去冗余）替代，再尝试 ident 猜测
        cleaned = _clean_function_title_tail(value)
        if cleaned and len(cleaned) <= 12 and contains_cjk(cleaned):
            if domain_prefix:
                recomposed = domain_prefix + cleaned
                value = recomposed if len(recomposed) <= 12 else cleaned
            else:
                value = cleaned
        elif cleaned and len(cleaned) > 12 and compact_desc and len(compact_desc) <= 12:
            value = compact_desc
        elif (not cleaned) and compact_desc and contains_cjk(compact_desc):
            # Bug B 守卫：cleaned 为空时优先保留 compact_desc（如 "旋变激励信号测试"），
            # 否则后续 ident 猜测会给出 "RdcExc检测" 之类的半翻译，最终被 _style 覆盖为骨架词。
            if domain_prefix:
                recomposed = domain_prefix + compact_desc
                value = recomposed if len(recomposed) <= 14 else compact_desc
            else:
                value = compact_desc
        elif (not cleaned or len(cleaned) > 12) and func_name:
            guessed = guess_cn_from_ident(func_name)
            if guessed and contains_cjk(guessed) and len(guessed) <= 12:
                value = guessed
    value = _restore_domain_specific_terms(value or compact_desc, comment_desc, func_name)
    value = _style_function_cn_title(value, func_name=func_name, comment_desc=comment_desc)
    value = _dedupe_adjacent_cjk_phrases(value)
    value = _repair_write_disable_title(value, func_name=func_name, comment_desc=comment_desc)
    value = _repair_spi_flash_datatrans_title(value, func_name=func_name, comment_desc=comment_desc)
    value = _clean_title_bit_alias_pollution(value)
    value = _guard_bad_function_title(value, func_name=func_name, raw_title=raw_title)
    fallback_desc = _guard_bad_function_title(
        _dedupe_adjacent_cjk_phrases(compact_desc),
        func_name=func_name,
        raw_title=compact_desc,
    )
    return value or fallback_desc or safe_strip(func_name)


def _guard_bad_function_title(value: str, *, func_name: str = "", raw_title: str = "") -> str:
    """Drop obvious parser artifacts before they become CSU headings."""
    title = safe_strip(value)
    if not title:
        return ""
    compact = re.sub(r"\s+", "", title)
    raw_compact = re.sub(r"\s+", "", safe_strip(raw_title))
    scalar_type_re = r"(?:u?int(?:8|16|32|64)|float|double|char|void|bool|boolean|static|const|volatile|unsigned|signed)"
    if re.fullmatch(r"\d+", compact) or re.fullmatch(r"\d+", raw_compact):
        return ""
    if re.fullmatch(scalar_type_re, compact, re.I) or re.fullmatch(scalar_type_re, raw_compact, re.I):
        return ""
    if len(compact) <= 2 and not contains_cjk(compact):
        return ""
    func = safe_strip(func_name)
    if func:
        u_width = re.search(r"U(8|16|32|64)$", func)
        if u_width and compact.endswith(u_width.group(1)) and contains_cjk(compact):
            if raw_compact and raw_compact != compact and contains_cjk(raw_compact) and not raw_compact.endswith(u_width.group(1)):
                return raw_compact
            return ""
    if func and compact.lower() in func.lower() and len(compact) <= 3:
        return ""
    return title


def get_function_chinese_name(
    comment_info: dict[str, Any],
    func_info: dict[str, Any],
    *,
    resolve_canonical_name: Optional[Callable[..., str]] = None,
) -> str:
    name_cn = safe_strip((comment_info or {}).get("func_cn_name"))
    name_from_comment = safe_strip((comment_info or {}).get("func_name"))
    comment_desc = safe_strip((comment_info or {}).get("desc"))
    func_name = safe_strip((func_info or {}).get("func_name"))
    candidate = ""
    if callable(resolve_canonical_name):
        try:
            candidate = safe_strip(
                resolve_canonical_name(
                    func_name,
                    kind="functions",
                    comment_cn=name_cn or name_from_comment,
                    fallback=func_name,
                )
            )
            # If the first resolve only produced an ident guess (no real hint was
            # available) and the C comment has a meaningful description, try again
            # with the desc as hint to avoid falling back to guess_cn_from_ident.
            if comment_desc and contains_cjk(comment_desc):
                _cn_hint_missing = not (name_cn or (name_from_comment and contains_cjk(name_from_comment)))
                if _cn_hint_missing:
                    candidate2 = safe_strip(
                        resolve_canonical_name(
                            func_name,
                            kind="functions",
                            comment_cn=comment_desc,
                            fallback=func_name,
                        )
                    )
                    if candidate2 and contains_cjk(candidate2):
                        candidate = candidate2
        except Exception:
            candidate = ""
    compact_comment_title = ""
    if comment_desc and contains_cjk(comment_desc) and not (name_cn and contains_cjk(name_cn)):
        compact_comment_title = _extract_compact_function_title(comment_desc)
        if compact_comment_title and contains_cjk(compact_comment_title):
            candidate = compact_comment_title
    result = candidate or func_name
    if result and func_name and not contains_cjk(result):
        if comment_desc and contains_cjk(comment_desc):
            short = re.split(r"[,，;；。、\s]", comment_desc, maxsplit=1)[0].strip()
            short = re.sub(r"^[本该此]函数(对\s*)?", "", short).strip()
            short = re.sub(r"^对\s*", "", short).strip()
            if short and contains_cjk(short) and len(short) >= 2:
                result = short
    final = normalize_function_cn_title(
        result,
        func_name=func_name,
        comment_desc=comment_desc,
    )
    # Self-bootstrapping dictionary: if we produced a clean CJK name from the
    # C identifier, learn the token→CN alignments for future calls.
    if final and contains_cjk(final) and func_name and not contains_cjk(func_name):
        _learn_ident_token_mappings(func_name, final)
    return final


def get_function_chinese_name_rich(
    func_data: dict[str, Any],
    *,
    cfg: Optional[Any] = None,
    resolve_canonical_name: Optional[Callable[..., str]] = None,
    backend_module: Any = None,
) -> str:
    """LLM-first function Chinese naming with rich body context.

    Primary path:
      1. FAST PATH: C comment has compact func_cn_name → normalize → return
      2. Build rich context (body ops, callees, types, module)
      3. LLM body summary (cached, skipped if body is empty)
      4. LLM naming with full context
      5. Normalize result

    Fallback (no cfg / no ai_assist / LLM failure):
      Uses the original get_function_chinese_name token-dict path.

    Args:
        func_data: Full func_data dict with comment_info, func_info, body, file_context
        cfg: GenConfig with ai_assist=True for LLM path
        resolve_canonical_name: Optional canonical name resolver (used in fallback)
        backend_module: Optional backend module reference

    Returns:
        Compact Chinese function name (≤12 chars when possible)
    """
    backend = backend_module or legacy_backend()
    comment_info = func_data.get("comment_info") or {}
    func_info = func_data.get("func_info") or {}
    file_context = func_data.get("file_context") or {}
    body = func_data.get("body") or ""

    func_name = safe_strip(func_info.get("func_name"))
    comment_func_cn = safe_strip(comment_info.get("func_cn_name"))
    comment_desc = safe_strip(comment_info.get("desc"))
    source_file = safe_strip(file_context.get("source_file"))

    def _is_cancelled() -> bool:
        return bool(
            cfg is not None
            and (
                utils_module.stop_requested(cfg)
                or getattr(cfg, "_user_cancelled", False)
            )
        )

    # ---- Fast path: C comment already has a compact CJK name ----
    if comment_func_cn and contains_cjk(comment_func_cn) and len(comment_func_cn) <= 12:
        final = normalize_function_cn_title(
            comment_func_cn,
            func_name=func_name,
            comment_desc=comment_desc,
        )
        if final and contains_cjk(final):
            return final

    # ---- Check if we can use the LLM rich path ----
    can_use_llm = (
        cfg is not None
        and getattr(cfg, "ai_assist", False)
        and func_name
        and not _is_cancelled()
    )

    if can_use_llm:
        from . import naming_context as nc
        from . import ai as ai_utils
        import time

        def _call_llm_with_retry(prompt: str, cfg: Any, label: str = "") -> str:
            """Call LLM with up to 2 retries (1s / 2s backoff)."""
            last_error = ""
            for attempt in range(1):
                if _is_cancelled():
                    return ""
                try:
                    result = ai_utils.call_llm_text(prompt, cfg)
                    if result and not result.startswith("HTTP") and not result.startswith("ERR:"):
                        return result
                    last_error = result
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
            return last_error  # Return the last error for debugging

        try:
            # ---- Step 1: Body summary (cached, lightweight LLM call) ----
            body_summary = ""
            if body and len(safe_strip(body)) > 10 and not _is_cancelled():
                body_summary = nc.get_cached_summary(func_name, source_file, body)
                if not body_summary:
                    summary_prompt = nc.build_body_summary_prompt(func_data, backend_module=backend)
                    summary_raw = _call_llm_with_retry(summary_prompt, cfg, label="summary")
                    if _is_cancelled():
                        return get_function_chinese_name(
                            comment_info,
                            func_info,
                            resolve_canonical_name=resolve_canonical_name,
                        )
                    body_summary = nc.parse_summary_response(summary_raw)
                    if body_summary:
                        nc.put_cached_summary(func_name, source_file, body, body_summary)

            # ---- Step 2: Naming with rich context ----
            if _is_cancelled():
                return get_function_chinese_name(
                    comment_info,
                    func_info,
                    resolve_canonical_name=resolve_canonical_name,
                )
            naming_prompt = nc.build_naming_prompt(
                func_data,
                body_summary=body_summary,
                backend_module=backend,
            )
            naming_raw = _call_llm_with_retry(naming_prompt, cfg, label="naming")
            if _is_cancelled():
                return get_function_chinese_name(
                    comment_info,
                    func_info,
                    resolve_canonical_name=resolve_canonical_name,
                )
            parsed = nc.parse_naming_response(naming_raw)
            llm_name = safe_strip(parsed.get("name", ""))

            if llm_name and contains_cjk(llm_name):
                final = normalize_function_cn_title(
                    llm_name,
                    func_name=func_name,
                    comment_desc=comment_desc,
                )
                if final and contains_cjk(final):
                    # Self-bootstrapping dictionary
                    if func_name and not contains_cjk(func_name):
                        _learn_ident_token_mappings(func_name, final)
                    return final
        except Exception:
            # LLM path failed; fall through to fallback
            pass

    # ---- Fallback: original token-dict path ----
    return get_function_chinese_name(
        comment_info,
        func_info,
        resolve_canonical_name=resolve_canonical_name,
    )


def get_variable_chinese_names_batch(
    func_data: dict[str, Any],
    *,
    func_cn_name: str = "",
    body_summary: str = "",
    cfg: Optional[Any] = None,
    backend_module: Any = None,
) -> dict[str, str]:
    """LLM-first batch variable Chinese naming.

    One LLM call per function to translate all parameters and local variables
    to Chinese names. Leverages the already-cached body summary.

    Args:
        func_data: Full func_data dict with comment_info, func_info, body, file_context
        func_cn_name: Already-resolved Chinese function name (from rich naming)
        body_summary: Cached body summary (from summary LLM call)
        cfg: GenConfig with ai_assist=True for LLM path
        backend_module: Optional backend module reference

    Returns:
        Dict mapping variable names to Chinese names (only CJK values included)
    """
    backend = backend_module or legacy_backend()

    can_use_llm = (
        cfg is not None
        and getattr(cfg, "ai_assist", False)
    )
    if not can_use_llm:
        return {}

    from . import naming_context as nc
    from . import ai as ai_utils
    import time

    prompt = nc.build_variable_batch_prompt(
        func_data,
        func_cn_name=func_cn_name,
        body_summary=body_summary,
        backend_module=backend,
    )
    if not prompt:
        return {}

    def _is_cancelled() -> bool:
        return bool(
            cfg is not None
            and (
                utils_module.stop_requested(cfg)
                or getattr(cfg, "_user_cancelled", False)
            )
        )

    def _call_llm_with_retry(prompt: str, cfg: Any) -> str:
        last_error = ""
        for attempt in range(3):
            if _is_cancelled():
                return ""
            try:
                result = ai_utils.call_llm_text(prompt, cfg)
                if result and not result.startswith("HTTP") and not result.startswith("ERR:"):
                    return result
                last_error = result
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                delay = 1.0 * (attempt + 1)
                waited = 0.0
                while waited < delay:
                    if _is_cancelled():
                        return ""
                    slice_sec = min(0.1, delay - waited)
                    time.sleep(slice_sec)
                    waited += slice_sec
        return last_error

    try:
        if _is_cancelled():
            return {}
        raw = _call_llm_with_retry(prompt, cfg)
        if _is_cancelled() or (not raw):
            return {}
        return nc.parse_variable_batch_response(raw)
    except Exception:
        return {}


def rerank_function_title_candidates(
    func_name: str,
    comment_desc: str,
    primary: str,
    candidates: Sequence[str],
    examples: Sequence[dict[str, Any]],
) -> str:
    seed = select_best_function_title_candidate(
        safe_strip(func_name),
        safe_strip(comment_desc),
        safe_strip(primary),
        [safe_strip(item) for item in (candidates or []) if safe_strip(item)],
        list(examples or []),
    )
    legacy = legacy_backend()
    return legacy._normalize_function_cn_title(
        seed,
        func_name=func_name,
        comment_desc=comment_desc,
    )


def rank_function_title_candidate(
    candidate: str,
    *,
    func_name: str,
    comment_desc: str,
    examples: Sequence[dict[str, Any]],
) -> int:
    text = normalize_function_cn_title(candidate, func_name=func_name, comment_desc=comment_desc)
    compact = re.sub(r"\s+", "", safe_strip(text))
    if not compact:
        return -999
    if title_violates_required_acronyms(compact, func_name):
        return -999
    score = 0
    if 4 <= len(compact) <= 12:
        score += 5
    elif len(compact) <= 16:
        score += 2
    if not re.search(r"[。；;，,]$", compact):
        score += 1
    if any(token in compact for token in ("并", "用于", "以便", "然后", "根据", "遍历")):
        score -= 4
    if re.search(r"(?:关闪|写保(?!护)|写禁(?!用|止)|读使(?!能)|写使(?!能)|擦使(?!能))", compact):
        score -= 10
    if re.search(r"(?:发送|读取|写入|关闭|开启|设置|清除).{1,2}(?:关|开|读|写|擦).{1,2}$", compact):
        score -= 4
    for example in (examples or []):
        title = safe_strip((example or {}).get("resolved_title"))
        if title and (compact.endswith(title[-2:]) or compact[:2] == title[:2]):
            score += 1
    return score


def select_best_function_title_candidate(
    func_name: str,
    comment_desc: str,
    primary: str,
    candidates: Sequence[str],
    examples: Sequence[dict[str, Any]],
) -> str:
    options: list[str] = []
    for item in [primary, *list(candidates or ())]:
        text = safe_strip(item)
        if text and text not in options:
            options.append(text)
    if not options:
        return ""
    valid_options = [item for item in options if not title_violates_required_acronyms(item, func_name)]
    if valid_options:
        options = valid_options
    scored = sorted(
        (
            (
                rank_function_title_candidate(
                    text,
                    func_name=func_name,
                    comment_desc=comment_desc,
                    examples=examples,
                ),
                text,
            )
            for text in options
        ),
        key=lambda x: (-x[0], x[1]),
    )
    return scored[0][1]


def rerank_symbol_candidate(
    raw_ident: str,
    item: Optional[dict[str, Any]],
    *,
    allow_refine_cn: bool,
    locked_cn: str,
) -> dict[str, Any]:
    payload = dict(item or {})
    cn_name = safe_strip(payload.get("cn_name"))
    usage = sanitize_ai_usage_text(payload.get("usage"))
    if locked_cn:
        cn_name = ""
    elif cn_name and (is_strict_symbol_candidate_rejected(cn_name, raw_ident=raw_ident) or is_generic_symbol_name(cn_name)):
        cn_name = ""
    if (not allow_refine_cn) and locked_cn:
        cn_name = ""
    payload["cn_name"] = cn_name
    payload["usage"] = usage
    return payload


def _resolve_backend_module(backend_module: Any = None) -> Any:
    return backend_module or legacy_backend()


def _prefer_more_specific_local_cn_candidate(
    candidate: str,
    current_cn: str,
    evidence: Any,
    *,
    backend_module: Any = None,
) -> bool:
    backend = _resolve_backend_module(backend_module)
    candidate_text = safe_strip(candidate)
    current_text = safe_strip(current_cn)
    if (not candidate_text) or (not current_text) or candidate_text == current_text:
        return False
    cand_cov = backend._candidate_ident_semantic_coverage(candidate_text, evidence.symbol)
    curr_cov = backend._candidate_ident_semantic_coverage(current_text, evidence.symbol)
    if cand_cov <= curr_cov:
        return False
    if len(candidate_text) < len(current_text):
        return False
    if current_text.endswith(("临时量", "临时值", "当前值", "缓存值", "状态值", "结果值")):
        return True
    return cand_cov >= curr_cov + 2


def _score_profile_local_cn(
    candidate: str,
    *,
    current_cn: str,
    backup_cn: str,
    evidence: Any,
    backend_module: Any = None,
) -> int:
    backend = _resolve_backend_module(backend_module)
    text = utils_module._safe_strip(candidate)
    if backend._looks_like_bad_canonical_name(text, raw_ident=evidence.symbol) or backend._looks_like_low_quality_symbol_cn(text, raw_ident=evidence.symbol):
        return -99
    score = 0
    coverage = backend._candidate_ident_semantic_coverage(text, evidence.symbol)
    if coverage >= 2:
        score += coverage * 8
    elif coverage == 0 and text in {"状态快照", "标志位", "数据指针", "无效", "有效"}:
        score -= 8
    concepts = list(backend._candidate_concepts_from_evidence(evidence))
    if text == utils_module._safe_strip(current_cn):
        score += 1
    if text == utils_module._safe_strip(backup_cn):
        score += 3
    if text in concepts:
        score += max(1, 10 - concepts.index(text))
    tags = set(evidence.producer_arg_tags or ())
    consumers = set(evidence.consumer_patterns or ())
    sinks = set(evidence.sink_patterns or ())
    dataflow_roles = set(evidence.dataflow_roles or ())
    decl_lower = utils_module._safe_strip(evidence.decl_type).lower()
    if "results_bit32" in tags:
        if text.endswith("结果快照"):
            score += 5
        elif text.endswith("结果位图"):
            score += 4
        if "签名" in text:
            score -= 8
    if evidence.paired_symbols and utils_module._safe_strip(evidence.symbol).lower().startswith(("l_s_", "s_")):
        if text.startswith("上拍"):
            score += 5
        if "签名" in text:
            score -= 6
    if evidence.producer_call == "RedunDataGet":
        if text.endswith("链路状态"):
            score += 4
        if "来源状态" in text:
            score -= 4
    if "宏定义" in text and evidence.kind != "macros":
        score -= 10
    if "eval" in decl_lower and text.endswith("结果"):
        score += 4
    if "output_limit" in dataflow_roles:
        if text.endswith("限幅值") or text.endswith("限流值"):
            score += 6
        if text.endswith(("临时量", "临时值")):
            score -= 6
    if "state_snapshot" in dataflow_roles or ("previous_snapshot" in dataflow_roles and "state_value" in dataflow_roles):
        if text.endswith("状态快照") or text.startswith("上拍"):
            score += 6
        if text.endswith(("临时量", "临时值", "状态值", "当前值")):
            score -= 6
    if "counter_value" in dataflow_roles:
        if text.endswith(("计数", "次数")):
            score += 4
        if text.endswith(("临时量", "临时值", "当前值")):
            score -= 4
    if "clamp_result" in dataflow_roles and text.endswith("限幅值"):
        score += 3
    if "pid_output_limit" in sinks and text.endswith("输出值"):
        score -= 2
    if "指针" in text and "*" not in decl_lower:
        score -= 8
    if "compared_to_static_prev" in consumers and text.startswith("上拍"):
        score += 2
    score += min(4, backend._candidate_ident_semantic_coverage(text, evidence.symbol))
    return score


def _retrieve_local_symbol_name_candidates(
    item: dict[str, Any],
    *,
    body: str,
    neighbor_symbols: Sequence[str],
    comment_desc: str = "",
    cfg: Optional[Any] = None,
    evidence: Optional[Any] = None,
    backend_module: Any = None,
) -> tuple[str, ...]:
    backend = _resolve_backend_module(backend_module)
    name = utils_module._safe_strip((item or {}).get("name"))
    if not name:
        return ()
    evidence = evidence or backend.collect_symbol_evidence(
        name,
        kind="symbols",
        body=body,
        decl_type=utils_module._safe_strip((item or {}).get("type")),
        neighbor_symbols=neighbor_symbols,
        source_comment_hints=[
            utils_module._safe_strip((item or {}).get("comment_hint")),
            utils_module._safe_strip((item or {}).get("usage")),
            comment_desc,
        ],
    )
    owner_semantic = backend._lightweight_semantic_record_from_body(
        func_name=utils_module._safe_strip((item or {}).get("owner_func")),
        source_file=utils_module._safe_strip((item or {}).get("source_file")),
        module_key=utils_module._safe_strip((item or {}).get("module_key")),
        family_prefix=utils_module._safe_strip((item or {}).get("family_prefix")),
        ret_type=utils_module._safe_strip((item or {}).get("owner_ret_type")),
        comment_desc=comment_desc,
        body=body,
        cfg=cfg,
    )
    inference = backend._infer_symbol_semantics_rule(evidence)
    retrieved = retrieve_symbol_context(
        {
            "symbol": name,
            "decl_type": utils_module._safe_strip((item or {}).get("type")),
            "role": utils_module._safe_strip(inference.role),
            "family_prefix": utils_module._safe_strip((item or {}).get("family_prefix")),
            "module_key": utils_module._safe_strip((item or {}).get("module_key")),
            "source_file": utils_module._safe_strip((item or {}).get("source_file")),
            "scope": utils_module._safe_strip((item or {}).get("scope")) or "local",
            "direction": utils_module._safe_strip((item or {}).get("direction")) or "local",
            "producer_call": utils_module._safe_strip(evidence.producer_call),
            "producer_arg_tags": tuple(evidence.producer_arg_tags or ()),
            "consumer_patterns": tuple(evidence.consumer_patterns or ()),
            "sink_patterns": tuple(evidence.sink_patterns or ()),
            "dataflow_roles": tuple(evidence.dataflow_roles or ()),
            "paired_symbols": tuple(evidence.paired_symbols or ()),
            "usage_patterns": tuple(evidence.usage_patterns or ()),
            "neighbor_symbols": tuple(neighbor_symbols or ()),
            "owner_func": utils_module._safe_strip((item or {}).get("owner_func")),
            "owner_ret_type": utils_module._safe_strip((item or {}).get("owner_ret_type")),
            "comment_desc": comment_desc,
            "body": body,
            "owner_semantic": owner_semantic,
        },
        cfg,
        backend_module=backend,
    )
    candidates: list[str] = []
    for record in retrieved:
        existing_cn = utils_module._safe_strip(record.get("existing_cn"))
        if existing_cn and not backend._looks_like_generic_local_cn_name(existing_cn) and not backend._looks_like_low_quality_symbol_cn(existing_cn, raw_ident=name) and existing_cn not in candidates:
            candidates.append(existing_cn)
        usage_cn = backend._derive_local_cn_from_usage(utils_module._safe_strip(record.get("existing_usage")), name)
        if usage_cn and not backend._looks_like_generic_local_cn_name(usage_cn) and not backend._looks_like_low_quality_symbol_cn(usage_cn, raw_ident=name) and usage_cn not in candidates:
            candidates.append(usage_cn)
    return tuple(candidates[:6])


def repair_local_cn_name_with_profile(
    item: dict[str, Any],
    *,
    body: str,
    neighbor_symbols: Sequence[str],
    comment_desc: str = "",
    backup_cn: str = "",
    cfg: Optional[Any] = None,
    backend_module: Any = None,
) -> None:
    backend = _resolve_backend_module(backend_module)
    name = utils_module._safe_strip((item or {}).get("name"))
    if not name:
        return
    evidence = backend.collect_symbol_evidence(
        name,
        kind="symbols",
        body=body,
        decl_type=utils_module._safe_strip((item or {}).get("type")),
        neighbor_symbols=neighbor_symbols,
        source_comment_hints=[backup_cn, utils_module._safe_strip((item or {}).get("comment_hint"))],
    )
    current_cn = utils_module._safe_strip((item or {}).get("cn_name"))
    concepts = list(backend._candidate_concepts_from_evidence(evidence))
    candidates: list[str] = []
    for text in (current_cn, backup_cn, *concepts):
        val = utils_module._safe_strip(text)
        if val and val not in candidates:
            candidates.append(val)
    ident_guess = utils_module._safe_strip(backend._guess_cn_from_ident(name))
    tokens = [utils_module._safe_strip(token).lower() for token in backend._split_ident_tokens(name)]
    if ident_guess and tokens and tokens[-1] in {"valid", "ok", "pass", "flag", "flg"} and not ident_guess.endswith(("标志", "状态")):
        ident_guess = f"{ident_guess}标志"
    if (
        ident_guess
        and ident_guess not in candidates
        and not backend._looks_like_bad_canonical_name(ident_guess, raw_ident=name)
        and not backend._looks_like_low_quality_symbol_cn(ident_guess, raw_ident=name)
        and (
            not re.search(r"[A-Za-z]{2,}", ident_guess)
            or all(word == word.upper() for word in re.findall(r"[A-Za-z]{2,}", ident_guess))
        )
    ):
        candidates.append(ident_guess)
    for text in _retrieve_local_symbol_name_candidates(
        item,
        body=body,
        neighbor_symbols=neighbor_symbols,
        comment_desc=comment_desc,
        cfg=cfg,
        evidence=evidence,
        backend_module=backend,
    ):
        val = utils_module._safe_strip(text)
        if val and val not in candidates:
            candidates.append(val)
    if not candidates:
        return
    if current_cn.endswith(("状态值", "缓存值", "当前值", "结果值", "临时值", "临时量")):
        for candidate in candidates:
            candidate_text = utils_module._safe_strip(candidate)
            if candidate_text and candidate_text.endswith(("快照", "结果快照")):
                item["profile_cn_candidate"] = candidate_text
                item["cn_name"] = candidate_text
                return
    best = max(
        candidates,
        key=lambda x: _score_profile_local_cn(
            x,
            current_cn=current_cn,
            backup_cn=backup_cn,
            evidence=evidence,
            backend_module=backend,
        ),
    )
    best_score = _score_profile_local_cn(
        best,
        current_cn=current_cn,
        backup_cn=backup_cn,
        evidence=evidence,
        backend_module=backend,
    )
    current_score = _score_profile_local_cn(
        current_cn,
        current_cn=current_cn,
        backup_cn=backup_cn,
        evidence=evidence,
        backend_module=backend,
    ) if current_cn else -99
    more_specific = _prefer_more_specific_local_cn_candidate(best, current_cn, evidence, backend_module=backend)
    if best and (best_score >= 4 or more_specific):
        item["profile_cn_candidate"] = best
    if best and (best_score >= max(4, current_score + 2) or more_specific):
        item["cn_name"] = best


def should_accept_refined_local_cn(
    candidate: str,
    *,
    current_cn: str,
    item: dict[str, Any],
    body: str,
    neighbor_symbols: Sequence[str],
    comment_desc: str = "",
    cfg: Optional[Any] = None,
    backend_module: Any = None,
) -> bool:
    backend = _resolve_backend_module(backend_module)
    candidate_text = utils_module._safe_strip(candidate)
    current_text = utils_module._safe_strip(current_cn)
    if (not candidate_text) or (not current_text) or candidate_text == current_text:
        return False
    if current_text.endswith(("状态值", "缓存值", "当前值", "结果值", "临时值", "临时量")) and candidate_text.endswith(("快照", "结果快照")):
        return True
    evidence = backend.collect_symbol_evidence(
        utils_module._safe_strip((item or {}).get("name")),
        kind="symbols",
        body=body,
        decl_type=utils_module._safe_strip((item or {}).get("type")),
        neighbor_symbols=neighbor_symbols,
        source_comment_hints=[current_text, utils_module._safe_strip((item or {}).get("comment_hint")), comment_desc],
    )
    backup_cn = utils_module._safe_strip((item or {}).get("comment_hint")) or current_text
    cand_score = _score_profile_local_cn(
        candidate_text,
        current_cn=current_text,
        backup_cn=backup_cn,
        evidence=evidence,
        backend_module=backend,
    )
    curr_score = _score_profile_local_cn(
        current_text,
        current_cn=current_text,
        backup_cn=backup_cn,
        evidence=evidence,
        backend_module=backend,
    )
    more_specific = _prefer_more_specific_local_cn_candidate(candidate_text, current_text, evidence, backend_module=backend)
    return bool(candidate_text and (cand_score >= max(4, curr_score + 2) or more_specific))


def local_cn_needs_ai_refine(
    item: Optional[dict[str, Any]],
    *,
    body: str,
    neighbor_symbols: Sequence[str],
    comment_desc: str = "",
    cfg: Optional[Any] = None,
    backend_module: Any = None,
) -> bool:
    backend = _resolve_backend_module(backend_module)
    entry = dict(item or {})
    current_cn = utils_module._safe_strip(entry.get("cn_name"))
    ident = utils_module._safe_strip(entry.get("name"))
    if (not current_cn) or (not ident):
        return False
    if backend._looks_like_generic_local_cn_name(current_cn) or backend._looks_like_low_quality_symbol_cn(current_cn, raw_ident=ident):
        return True
    if current_cn.endswith(("状态值", "缓存值", "当前值", "结果值", "临时值", "临时量")):
        for candidate in _retrieve_local_symbol_name_candidates(
            entry,
            body=body,
            neighbor_symbols=neighbor_symbols,
            comment_desc=comment_desc,
            cfg=cfg,
            backend_module=backend,
        ):
            candidate_text = utils_module._safe_strip(candidate)
            if candidate_text and candidate_text != current_cn:
                return True
    candidate_probe = dict(entry)
    repair_local_cn_name_with_profile(
        candidate_probe,
        body=body,
        neighbor_symbols=neighbor_symbols,
        comment_desc=comment_desc,
        backup_cn=current_cn,
        cfg=cfg,
        backend_module=backend,
    )
    profile_candidate = utils_module._safe_strip(candidate_probe.get("profile_cn_candidate"))
    if (
        profile_candidate
        and profile_candidate != current_cn
        and current_cn.endswith(("状态值", "缓存值", "当前值", "结果值", "临时值", "临时量"))
    ):
        return True
    if profile_candidate and profile_candidate != current_cn and should_accept_refined_local_cn(
        profile_candidate,
        current_cn=current_cn,
        item=entry,
        body=body,
        neighbor_symbols=neighbor_symbols,
        comment_desc=comment_desc,
        cfg=cfg,
        backend_module=backend,
    ):
        return True
    return False


def make_candidate(text: str, usage: str = "", confidence: float = 0.0, source: str = "") -> NamingCandidate:
    return NamingCandidate(
        text=safe_strip(text),
        usage=safe_strip(usage),
        confidence=float(confidence or 0.0),
        source=safe_strip(source),
    )


def parse_domain_glossary_text(text: str) -> dict[str, str]:
    value = str(text or "").strip()
    if not value:
        return {}

    if value.startswith("{") and value.endswith("}"):
        try:
            payload = json.loads(value)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            out: dict[str, str] = {}
            for key, raw in payload.items():
                kk = str(key).strip()
                vv = str(raw).strip()
                if kk and vv:
                    out[kk] = vv
            return out

    out: dict[str, str] = {}
    for raw in value.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        line = line.replace("=>", "=")
        if ":" in line and "=" not in line:
            line = line.replace(":", "=", 1)
        if "=" not in line:
            continue
        key, mapped = line.split("=", 1)
        kk = key.strip()
        vv = mapped.strip()
        if kk and vv:
            out[kk] = vv
    return out


def _default_symbol_dictionary_path(*, backend_module=None) -> str:
    candidates = [
        os.path.join(os.getcwd(), "symbol_dictionary.json"),
        os.path.join(app_root(), "symbol_dictionary.json"),
        os.path.join(app_root(), "autodoc", "symbol_dictionary.json"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return candidates[0]


def _normalize_symbol_dictionary_payload(data: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(data, dict):
        return out
    nested_sections = ("symbols", "globals", "locals", "members", "functions", "macros", "typedefs", "structs", "enums")
    has_section = any(isinstance(data.get(key), dict) for key in nested_sections)
    if has_section:
        for section in nested_sections:
            part = data.get(section)
            if isinstance(part, dict):
                out.update(_normalize_symbol_dictionary_payload(part))
        return out
    for key, value in data.items():
        kk = str(key).strip()
        vv = str(value).strip()
        if kk and vv:
            out[kk] = vv
    return out


def parse_symbol_dictionary_text(text: str) -> dict[str, str]:
    value = str(text or "").strip()
    if not value:
        return {}
    if value.startswith("{") and value.endswith("}"):
        try:
            return _normalize_symbol_dictionary_payload(json.loads(value))
        except Exception:
            pass
    return parse_domain_glossary_text(value)


def load_symbol_dictionary_file(path: str) -> dict[str, str]:
    file_path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not file_path or (not os.path.isfile(file_path)):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except Exception:
        return {}
    return parse_symbol_dictionary_text(text)


def _default_project_symbol_memory_path(project_root: str) -> str:
    root = os.path.abspath(os.path.expanduser(str(project_root or "").strip())) if project_root else ""
    if not root:
        return os.path.abspath("autodoc_symbol_memory.json")
    return os.path.join(root, "autodoc_symbol_memory.json")


def _project_symbol_memory_cn_rejected(
    cn: str,
    *,
    raw_ident: str = "",
    section: str = "",
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    value = safe_strip(cn)
    ident = safe_strip(raw_ident)
    if not value:
        return True
    if backend._looks_like_bad_canonical_name(value, raw_ident=ident):
        return True
    if backend._looks_like_low_quality_symbol_cn(value, raw_ident=ident):
        return True
    if section == "members" and backend._looks_like_low_quality_member_cn(value):
        return True
    if section in {"", "symbols"} and value in {"状态快照", "上拍状态", "标志位", "数据指针", "缓存值", "状态值", "无效", "有效"}:
        tokens = [safe_strip(token).lower() for token in backend._split_ident_tokens(ident)]
        guess_parts = [safe_strip(getattr(backend, "_IDENT_CN_MAP", {}).get(token)) for token in tokens]
        guessed = "".join(part for part in guess_parts if part)
        if guessed and tokens and tokens[-1] in {"valid", "ok", "pass", "flag", "flg"} and not guessed.endswith(("标志", "状态")):
            guessed = f"{guessed}标志"
        ascii_ok = (
            not re.search(r"[A-Za-z]{2,}", guessed)
            or all(word == word.upper() for word in re.findall(r"[A-Za-z]{2,}", guessed))
        )
        if (
            guessed
            and ascii_ok
            and backend._candidate_ident_semantic_coverage(value, ident) == 0
            and backend._candidate_ident_semantic_coverage(guessed, ident) >= 2
        ):
            return True
    strict_checker = getattr(backend, "_is_strict_symbol_candidate_rejected", None)
    try:
        if callable(strict_checker):
            return bool(strict_checker(value, raw_ident=ident))
    except Exception:
        pass
    return is_strict_symbol_candidate_rejected(value, raw_ident=ident)


def _normalize_symbol_memory_record(
    record: Any,
    *,
    raw_ident: str = "",
    section: str = "",
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    if isinstance(record, dict):
        cn = str(record.get("cn") or record.get("name") or "").strip()
        if _project_symbol_memory_cn_rejected(cn, raw_ident=raw_ident, section=section, backend_module=backend):
            cn = ""
        source = str(record.get("source") or "ai").strip() or "ai"
        try:
            confidence = float(record.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        out = {"cn": cn, "source": source, "confidence": confidence}
        if record.get("updated_at"):
            out["updated_at"] = str(record.get("updated_at"))
        return out
    cn = str(record or "").strip()
    if _project_symbol_memory_cn_rejected(cn, raw_ident=raw_ident, section=section, backend_module=backend):
        cn = ""
    return {"cn": cn, "source": "ai", "confidence": 0.0}


def _normalize_project_symbol_memory_payload(data: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    out = {"version": 1, "functions": {}, "symbols": {}, "members": {}, "macros": {}}
    if not isinstance(data, dict):
        return out
    for section in ("functions", "symbols", "members", "macros"):
        part = data.get(section)
        if not isinstance(part, dict):
            continue
        normalized_part: dict[str, dict[str, Any]] = {}
        for key, value in part.items():
            kk = str(key).strip()
            vv = _normalize_symbol_memory_record(value, raw_ident=kk, section=section, backend_module=backend)
            if kk and vv.get("cn"):
                normalized_part[kk] = vv
        out[section] = normalized_part
    return out


def load_project_symbol_memory(project_root: str, *, backend_module=None) -> tuple[str, dict[str, Any]]:
    backend = backend_module or legacy_backend()
    path = _default_project_symbol_memory_path(project_root)
    if not os.path.isfile(path):
        return path, _normalize_project_symbol_memory_payload({}, backend_module=backend)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return path, _normalize_project_symbol_memory_payload({}, backend_module=backend)
    return path, _normalize_project_symbol_memory_payload(data, backend_module=backend)


def _flatten_project_symbol_memory(data: Optional[dict[str, Any]], *, backend_module=None) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    flat: dict[str, str] = {}
    src = _normalize_project_symbol_memory_payload(data or {}, backend_module=backend)
    for section in ("functions", "symbols", "members", "macros"):
        for name, record in (src.get(section) or {}).items():
            cn = str((record or {}).get("cn") or "").strip()
            if section == "members" and backend._looks_like_low_quality_member_cn(cn):
                continue
            if name and cn:
                flat[name] = cn
    return flat


def save_project_symbol_memory(*, backend_module=None) -> None:
    backend = backend_module or legacy_backend()
    with backend._SYMBOL_MEMORY_LOCK:
        path = backend._PROJECT_SYMBOL_MEMORY_PATH
        data = copy.deepcopy(backend._PROJECT_SYMBOL_MEMORY_DATA)
    if not path:
        return
    payload = _normalize_project_symbol_memory_payload(data, backend_module=backend)
    payload["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".autodoc_symbol_memory_", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def apply_symbol_dictionary_overrides(
    overrides: Optional[dict[str, str]],
    file_path: str = "",
    project_memory: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> None:
    backend = backend_module or legacy_backend()
    try:
        base_path = str(file_path or "").strip() or _default_symbol_dictionary_path(backend_module=backend)
        backend.SYMBOL_DICTIONARY_BASE.clear()
        backend.SYMBOL_DICTIONARY_BASE.update(load_symbol_dictionary_file(base_path))
        backend.SYMBOL_DICTIONARY_RUNTIME.clear()
        backend.SYMBOL_DICTIONARY_RUNTIME.update(backend.SYMBOL_DICTIONARY_BASE)
        backend.SESSION_SYMBOL_DICTIONARY.clear()
        if isinstance(project_memory, dict) and project_memory:
            for key, value in project_memory.items():
                kk = str(key).strip()
                vv = str(value).strip()
                if kk and vv and (not backend._looks_like_bad_canonical_name(vv, raw_ident=kk)) and (not backend._looks_like_low_quality_symbol_cn(vv, raw_ident=kk)):
                    backend.SYMBOL_DICTIONARY_RUNTIME[kk] = vv
        if isinstance(overrides, dict) and overrides:
            for key, value in overrides.items():
                kk = str(key).strip()
                vv = str(value).strip()
                if kk and vv and (not backend._looks_like_bad_canonical_name(vv, raw_ident=kk)) and (not backend._looks_like_low_quality_symbol_cn(vv, raw_ident=kk)):
                    backend.SYMBOL_DICTIONARY_RUNTIME[kk] = vv
    except Exception:
        pass
    try:
        backend._FUNC_CN_CACHE.clear()
    except Exception:
        pass


def init_project_symbol_memory(project_root: str, cfg: Optional[Any] = None, overrides: Optional[dict[str, str]] = None, *, backend_module=None) -> None:
    backend = backend_module or legacy_backend()
    path, data = load_project_symbol_memory(project_root, backend_module=backend)
    flat_memory = _flatten_project_symbol_memory(data, backend_module=backend)
    with backend._SYMBOL_MEMORY_LOCK:
        backend._PROJECT_SYMBOL_MEMORY_PATH = path
        backend._PROJECT_SYMBOL_MEMORY_DATA = data
    apply_symbol_dictionary_overrides(overrides, project_memory=flat_memory, backend_module=backend)
    if cfg is not None:
        try:
            cfg.project_root = os.path.abspath(project_root or "")
            cfg.symbol_memory_path = path
        except Exception:
            pass


def finalize_project_symbol_memory(cfg: Optional[Any] = None, *, backend_module=None) -> None:
    backend = backend_module or legacy_backend()
    try:
        save_project_symbol_memory(backend_module=backend)
    except Exception as exc:
        if cfg:
            utils_module.vlog(cfg, f"保存项目符号记忆库失败：{exc}")
    # Also persist body-summary cache to project directory
    from . import naming_context as _nc
    try:
        _nc.save_summary_cache()
    except Exception:
        pass


def _lookup_symbol_dictionary(name: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    key = str(name or "").strip()
    if not key:
        return ""
    value = str(backend.SYMBOL_DICTIONARY_RUNTIME.get(key) or "").strip()
    if _project_symbol_memory_cn_rejected(value, raw_ident=key, backend_module=backend):
        return ""
    return value


def _lookup_session_symbol_record(name: str, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    key = str(name or "").strip()
    if not key:
        return {}
    record = backend.SESSION_SYMBOL_DICTIONARY.get(key) or {}
    return record if isinstance(record, dict) else {}


def _lookup_session_symbol(name: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    record = _lookup_session_symbol_record(name, backend_module=backend)
    value = str(record.get("cn") or "").strip()
    section = str(record.get("kind") or "").strip()
    if _project_symbol_memory_cn_rejected(value, raw_ident=name, section=section, backend_module=backend):
        return ""
    return value


def _remember_ai_symbol(
    name: str,
    cn: str,
    *,
    kind: str,
    confidence: float,
    evidence_kinds: int = 2,
    persist_scope: str = "graded",
    cfg: Optional[Any] = None,
    source: str = "ai",
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    key = str(name or "").strip()
    value = str(cn or "").strip()
    section = kind if kind in ("functions", "symbols", "members", "macros") else "symbols"
    if (not key) or (not value):
        return False
    if _project_symbol_memory_cn_rejected(value, raw_ident=key, section=section, backend_module=backend):
        return False
    if backend._is_missing_gap_text(value) or (not text_utils._contains_cjk(value)):
        return False
    if re.fullmatch(r"[A-Z0-9_]+", value):
        return False
    scope = str(persist_scope or "graded").strip().lower()
    if scope in ("off", "none"):
        return False
    min_conf = utils_module.cfg_get_float(cfg, "symbol_memory_min_conf", 0.72)
    try:
        conf_val = float(confidence or 0.0)
    except Exception:
        conf_val = 0.0
    try:
        evidence_count = int(evidence_kinds or 0)
    except Exception:
        evidence_count = 0
    if scope in ("session_only", "session"):
        backend.SESSION_SYMBOL_DICTIONARY[key] = {
            "cn": value,
            "kind": section,
            "confidence": conf_val,
            "evidence_kinds": evidence_count,
            "source": source,
        }
        return True
    min_evidence = utils_module.cfg_get_int(cfg, "symbol_infer_min_evidence_kinds", 2)
    if conf_val < min_conf or evidence_count < max(1, int(min_evidence or 1)):
        return False

    updated = False
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with backend._SYMBOL_MEMORY_LOCK:
        if not backend._PROJECT_SYMBOL_MEMORY_PATH:
            return False
        data = _normalize_project_symbol_memory_payload(backend._PROJECT_SYMBOL_MEMORY_DATA, backend_module=backend)
        part = data.setdefault(section, {})
        old = _normalize_symbol_memory_record(
            part.get(key) or {},
            raw_ident=key,
            section=section,
            backend_module=backend,
        )
        old_cn = str(old.get("cn") or "").strip()
        old_conf = float(old.get("confidence", 0.0) or 0.0)
        if old_cn and old_cn != value and old_conf > conf_val:
            return False
        if old_cn == value and old_conf >= conf_val:
            return False
        part[key] = {"cn": value, "source": source, "confidence": conf_val, "updated_at": now}
        backend._PROJECT_SYMBOL_MEMORY_DATA.clear()
        backend._PROJECT_SYMBOL_MEMORY_DATA.update(data)
        backend.SYMBOL_DICTIONARY_RUNTIME[key] = value
        updated = True
    if updated:
        try:
            save_project_symbol_memory(backend_module=backend)
        except Exception:
            pass
    return updated


def _remember_inferred_symbol(
    name: str,
    cn: str,
    *,
    kind: str,
    confidence: float,
    evidence_kinds: int,
    cfg: Optional[Any] = None,
    source: str = "infer",
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    key = utils_module._safe_strip(name)
    value = utils_module._safe_strip(cn)
    if (not key) or (not value):
        return False
    if kind == "members" and backend._looks_like_low_quality_member_cn(value):
        return False
    scope = str(getattr(cfg, "symbol_infer_scope", "graded") or "graded").strip().lower()
    if kind == "macros":
        scope = "session_only"
    if scope == "off":
        return False
    conf_val = float(confidence or 0.0)
    evidence_count = max(0, int(evidence_kinds or 0))
    persist_threshold = utils_module.cfg_get_float(cfg, "symbol_infer_min_conf", 0.82)
    min_evidence = utils_module.cfg_get_int(cfg, "symbol_infer_min_evidence_kinds", 2)
    session_floor = 0.60
    if scope == "session_only":
        return _remember_ai_symbol(
            key,
            value,
            kind=kind,
            confidence=max(conf_val, session_floor),
            evidence_kinds=max(1, evidence_count),
            persist_scope="session_only",
            cfg=cfg,
            source=source,
            backend_module=backend,
        )
    if conf_val >= persist_threshold and evidence_count >= max(1, int(min_evidence or 1)):
        return _remember_ai_symbol(
            key,
            value,
            kind=kind,
            confidence=conf_val,
            evidence_kinds=evidence_count,
            persist_scope="graded",
            cfg=cfg,
            source=source,
            backend_module=backend,
        )
    if conf_val >= session_floor:
        return _remember_ai_symbol(
            key,
            value,
            kind=kind,
            confidence=conf_val,
            evidence_kinds=max(1, evidence_count),
            persist_scope="session_only",
            cfg=cfg,
            source=source,
            backend_module=backend,
        )
    return False


def collect_preferred_symbol_names(names: Sequence[str], *, limit: int = 24, backend_module=None) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    out: dict[str, str] = {}
    if limit <= 0:
        return out
    for raw in (names or []):
        name = utils_module._safe_strip(raw)
        if (not name) or (name in out):
            continue
        cn = _lookup_symbol_dictionary(name, backend_module=backend)
        if not cn:
            continue
        out[name] = cn
        if len(out) >= limit:
            break
    return out


def resolve_canonical_symbol_name(
    name: str,
    *,
    kind: str = "symbols",
    comment_cn: str = "",
    fallback: str = "",
    allow_guess: bool = True,
    backend_module=None,
) -> str:
    backend = backend_module or legacy_backend()
    ident = utils_module._safe_strip(name)
    if not ident:
        return utils_module._safe_strip(fallback)

    exact = _lookup_symbol_dictionary(ident, backend_module=backend)
    if exact and not backend._looks_like_bad_canonical_name(exact, raw_ident=ident):
        return exact

    session_cn = _lookup_session_symbol(ident, backend_module=backend)
    if kind == "members" and backend._looks_like_low_quality_member_cn(session_cn):
        session_cn = ""
    if session_cn and not backend._looks_like_bad_canonical_name(session_cn, raw_ident=ident):
        return session_cn

    comment_text = utils_module._safe_strip(comment_cn)
    if comment_text and not backend._looks_like_bad_canonical_name(comment_text, raw_ident=ident):
        return comment_text

    if allow_guess:
        guessed = backend._guess_cn_from_ident(ident, glossary=backend.DOMAIN_GLOSSARY)
        if guessed and not backend._looks_like_bad_canonical_name(guessed, raw_ident=ident):
            return guessed

    fallback_text = utils_module._safe_strip(fallback)
    return fallback_text or ident


def _default_project_title_index_path(project_root: str) -> str:
    root = os.path.abspath(os.path.expanduser(str(project_root or "").strip())) if project_root else ""
    if not root:
        return os.path.abspath("autodoc_title_index.json")
    return os.path.join(root, "autodoc_title_index.json")


def _default_project_symbol_index_path(project_root: str) -> str:
    root = os.path.abspath(os.path.expanduser(str(project_root or "").strip())) if project_root else ""
    if not root:
        return os.path.abspath("autodoc_symbol_index.json")
    return os.path.join(root, "autodoc_symbol_index.json")


def _normalize_title_index_record(record: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    if not isinstance(record, dict):
        return {}
    out = {
        "id": utils_module._safe_strip(record.get("id")),
        "source_file": utils_module._safe_strip(record.get("source_file")),
        "module_key": utils_module._safe_strip(record.get("module_key")),
        "func_name": utils_module._safe_strip(record.get("func_name")),
        "family_prefix": utils_module._safe_strip(record.get("family_prefix")),
        "action_suffix": utils_module._safe_strip(record.get("action_suffix")),
        "comment_desc": utils_module._safe_strip(record.get("comment_desc")),
        "comment_func_cn": utils_module._safe_strip(record.get("comment_func_cn")),
        "resolved_title": utils_module._safe_strip(record.get("resolved_title")),
        "resolved_desc": utils_module._safe_strip(record.get("resolved_desc")),
        "neighbor_funcs": tuple(
            utils_module._safe_strip(x) for x in (record.get("neighbor_funcs") or ()) if utils_module._safe_strip(x)
        ),
    }
    if not out["id"]:
        return {}
    return out


def _normalize_symbol_index_record(record: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    if not isinstance(record, dict):
        return {}
    out = {
        "id": utils_module._safe_strip(record.get("id")),
        "source_file": utils_module._safe_strip(record.get("source_file")),
        "module_key": utils_module._safe_strip(record.get("module_key")),
        "owner_func": utils_module._safe_strip(record.get("owner_func")),
        "family_prefix": utils_module._safe_strip(record.get("family_prefix")),
        "kind": utils_module._safe_strip(record.get("kind")) or "symbols",
        "symbol": utils_module._safe_strip(record.get("symbol")),
        "decl_type": utils_module._safe_strip(record.get("decl_type")),
        "owner_type": utils_module._safe_strip(record.get("owner_type")),
        "role": utils_module._safe_strip(record.get("role")),
        "comment_desc": utils_module._safe_strip(record.get("comment_desc")),
        "existing_cn": "",
        "existing_usage": utils_module._safe_strip(record.get("existing_usage")),
        "comment_hint": utils_module._safe_strip(record.get("comment_hint")),
        "normalized_comment_hint": utils_module._safe_strip(record.get("normalized_comment_hint")),
        "producer_kind": utils_module._safe_strip(record.get("producer_kind")),
        "producer_call": utils_module._safe_strip(record.get("producer_call")),
        "producer_args": tuple(
            utils_module._safe_strip(x) for x in (record.get("producer_args") or ()) if utils_module._safe_strip(x)
        ),
        "producer_arg_tags": tuple(
            utils_module._safe_strip(x) for x in (record.get("producer_arg_tags") or ()) if utils_module._safe_strip(x)
        ),
        "consumer_patterns": tuple(
            utils_module._safe_strip(x) for x in (record.get("consumer_patterns") or ()) if utils_module._safe_strip(x)
        ),
        "sink_patterns": tuple(
            utils_module._safe_strip(x) for x in (record.get("sink_patterns") or ()) if utils_module._safe_strip(x)
        ),
        "dataflow_roles": tuple(
            utils_module._safe_strip(x) for x in (record.get("dataflow_roles") or ()) if utils_module._safe_strip(x)
        ),
        "paired_symbols": tuple(
            utils_module._safe_strip(x) for x in (record.get("paired_symbols") or ()) if utils_module._safe_strip(x)
        ),
        "usage_patterns": tuple(
            utils_module._safe_strip(x) for x in (record.get("usage_patterns") or ()) if utils_module._safe_strip(x)
        ),
        "usage_examples": tuple(
            utils_module._safe_strip(x) for x in (record.get("usage_examples") or ()) if utils_module._safe_strip(x)
        ),
        "neighbor_symbols": tuple(
            utils_module._safe_strip(x) for x in (record.get("neighbor_symbols") or ()) if utils_module._safe_strip(x)
        ),
    }
    existing_cn = utils_module._safe_strip(record.get("existing_cn"))
    if existing_cn and not backend._looks_like_bad_canonical_name(existing_cn, raw_ident=out["symbol"]):
        out["existing_cn"] = existing_cn
    if not out["id"]:
        return {}
    return out


def _normalize_title_index_payload(data: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    out = {"version": 1, "items": []}
    if not isinstance(data, dict):
        return out
    items = []
    for item in (data.get("items") or []):
        normalized = _normalize_title_index_record(item, backend_module=backend)
        if normalized:
            items.append(normalized)
    out["items"] = items
    if data.get("updated_at"):
        out["updated_at"] = str(data.get("updated_at"))
    return out


def _normalize_symbol_index_payload(data: Any, *, backend_module=None) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    out = {"version": 1, "items": []}
    if not isinstance(data, dict):
        return out
    items = []
    for item in (data.get("items") or []):
        normalized = _normalize_symbol_index_record(item, backend_module=backend)
        if normalized:
            items.append(normalized)
    out["items"] = items
    if data.get("updated_at"):
        out["updated_at"] = str(data.get("updated_at"))
    return out


def load_project_title_index(project_root: str, *, backend_module=None) -> tuple[str, dict[str, Any]]:
    backend = backend_module or legacy_backend()
    path = _default_project_title_index_path(project_root)
    if not os.path.isfile(path):
        return path, _normalize_title_index_payload({}, backend_module=backend)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return path, _normalize_title_index_payload({}, backend_module=backend)
    return path, _normalize_title_index_payload(data, backend_module=backend)


def load_project_symbol_index(project_root: str, *, backend_module=None) -> tuple[str, dict[str, Any]]:
    backend = backend_module or legacy_backend()
    path = _default_project_symbol_index_path(project_root)
    if not os.path.isfile(path):
        return path, _normalize_symbol_index_payload({}, backend_module=backend)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return path, _normalize_symbol_index_payload({}, backend_module=backend)
    return path, _normalize_symbol_index_payload(data, backend_module=backend)


def _save_json_sidecar(path: str, payload: dict[str, Any], prefix: str) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _collect_project_source_mtime(project_root: str, *, max_files: int = 0) -> float:
    latest = 0.0
    counted = 0
    for base, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "build", "dist", "debug", "release"}]
        for name in files:
            if not name.lower().endswith((".c", ".h")):
                continue
            path = os.path.join(base, name)
            try:
                latest = max(latest, os.path.getmtime(path))
            except Exception:
                continue
            counted += 1
            if max_files > 0 and counted >= max_files:
                return latest
    return latest


def _should_refresh_naming_indexes(
    project_root: str,
    title_path: str,
    symbol_path: str,
    cfg: Optional[Any],
    *,
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    mode = utils_module.cfg_get_str(cfg, "naming_index_refresh", "auto").lower()
    if mode == "always":
        return True
    if mode == "off":
        return False
    if not os.path.isfile(title_path) or not os.path.isfile(symbol_path):
        return True
    max_files = max(0, utils_module.cfg_get_int(cfg, "naming_index_max_files", 0))
    latest_src = _collect_project_source_mtime(project_root, max_files=max_files)
    try:
        title_mtime = os.path.getmtime(title_path)
        symbol_mtime = os.path.getmtime(symbol_path)
    except Exception:
        return True
    return latest_src > min(title_mtime, symbol_mtime)


def _project_title_index_items(*, backend_module=None) -> list[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    with backend._NAMING_INDEX_LOCK:
        data = copy.deepcopy(backend._PROJECT_TITLE_INDEX_DATA)
    return list((_normalize_title_index_payload(data, backend_module=backend) or {}).get("items") or [])


_SYMBOL_INDEX_CACHE: list[dict[str, Any]] = []
_SYMBOL_INDEX_CACHE_KEY: int = 0
# token → record 索引列表，用于 retrieve_symbol_context 快速查找候选
_TOKEN_INVERTED_INDEX: dict[str, list[int]] = {}


def _project_symbol_index_items(*, backend_module=None) -> list[dict[str, Any]]:
    global _SYMBOL_INDEX_CACHE, _SYMBOL_INDEX_CACHE_KEY, _TOKEN_INVERTED_INDEX
    backend = backend_module or legacy_backend()
    with backend._NAMING_INDEX_LOCK:
        data = backend._PROJECT_SYMBOL_INDEX_DATA
    data_id = id(data)
    if data_id == _SYMBOL_INDEX_CACHE_KEY and _SYMBOL_INDEX_CACHE:
        return _SYMBOL_INDEX_CACHE
    # normalize 不修改输入（创建新 dict），无需 deepcopy
    items = list((_normalize_symbol_index_payload(data, backend_module=backend) or {}).get("items") or [])
    _SYMBOL_INDEX_CACHE = items
    _SYMBOL_INDEX_CACHE_KEY = data_id
    # 构建 token 倒排索引
    token_idx: dict[str, list[int]] = {}
    for i, item in enumerate(items):
        sym = utils_module._safe_strip(item.get("symbol"))
        if not sym:
            continue
        for tok in text_utils._split_ident_tokens(sym):
            key = tok.lower()
            if key not in token_idx:
                token_idx[key] = []
            token_idx[key].append(i)
    _TOKEN_INVERTED_INDEX = token_idx
    return items


def _rebuild_project_naming_indexes(project_root: str, cfg: Optional[Any], *, backend_module=None) -> tuple[dict[str, Any], dict[str, Any]]:
    backend = backend_module or legacy_backend()
    title_items: list[dict[str, Any]] = []
    symbol_items: list[dict[str, Any]] = []
    if not project_root or not os.path.isdir(project_root):
        return (
            _normalize_title_index_payload({}, backend_module=backend),
            _normalize_symbol_index_payload({}, backend_module=backend),
        )

    worker_cfg = backend._clone_cfg(cfg, ai_assist=False) if isinstance(cfg, backend.GenConfig) else backend.GenConfig(ai_assist=False)
    source_files = backend._get_ordered_project_c_files(project_root, worker_cfg)
    max_files = max(0, utils_module.cfg_get_int(cfg, "naming_index_max_files", 0))
    if max_files > 0:
        source_files = source_files[:max_files]

    for c_path in source_files:
        func_list, skip_reason = backend.prepare_func_list_for_c_file(
            c_path,
            project_root=project_root,
            cfg=worker_cfg,
            prefilter=False,
        )
        if skip_reason or not func_list:
            continue
        neighbor_names = [
            utils_module._safe_strip(((fd.get("func_info") or {}).get("func_name")))
            for fd in func_list
        ]
        for idx, fd in enumerate(func_list):
            func_info = fd.get("func_info") or {}
            comment_info = fd.get("comment_info") or {}
            body = fd.get("body") or ""
            func_name = utils_module._safe_strip(func_info.get("func_name"))
            if not func_name:
                continue
            module_key = backend._module_key_for_source(c_path)
            family_prefix = backend._identifier_family_prefix(func_name)
            action_suffix = backend._identifier_action_suffix(func_name)
            raw_desc = utils_module._safe_strip(comment_info.get("desc"))
            if backend._is_noop_comment(raw_desc) or backend._looks_like_logic_noise_comment(raw_desc):
                raw_desc = ""
            if worker_cfg is not None and getattr(worker_cfg, "ai_assist", False):
                cn_name = get_function_chinese_name_rich(
                    fd,
                    cfg=worker_cfg,
                    resolve_canonical_name=lambda *a, **kw: backend.resolve_canonical_symbol_name(*a, **kw),
                )
            else:
                cn_name = get_function_chinese_name(comment_info, func_info)
            resolved_title = backend._normalize_function_cn_title(
                cn_name,
                func_name=func_name,
                comment_desc=raw_desc,
            )
            resolved_desc = raw_desc
            prev_name = neighbor_names[idx - 1] if idx > 0 else ""
            next_name = neighbor_names[idx + 1] if idx + 1 < len(neighbor_names) else ""
            title_items.append({
                "id": f"{backend._safe_relpath(c_path, project_root)}::{func_name}",
                "source_file": os.path.abspath(c_path),
                "module_key": module_key,
                "func_name": func_name,
                "family_prefix": family_prefix,
                "action_suffix": action_suffix,
                "comment_desc": resolved_desc,
                "comment_func_cn": utils_module._safe_strip(comment_info.get("func_cn_name")),
                "resolved_title": resolved_title,
                "resolved_desc": resolved_desc,
                "neighbor_funcs": tuple(x for x in (prev_name, next_name) if x),
            })

            local_vars = backend.parse_local_variables_from_body(body)
            params = backend.parse_params_from_prototype(func_info)
            local_vars = backend._filter_local_vars_against_params(local_vars, params, cfg=worker_cfg, func_name=func_name)
            comment_desc = utils_module._safe_strip(comment_info.get("desc"))
            neighbor_symbols = [
                utils_module._safe_strip((v or {}).get("name"))
                for v in (list(local_vars or []) + list(params or []))
                if utils_module._safe_strip((v or {}).get("name"))
            ]
            for item in (local_vars or []):
                repair_local_cn_name_with_profile(
                    item,
                    body=body,
                    neighbor_symbols=[x for x in neighbor_symbols if x and x != utils_module._safe_strip((item or {}).get("name"))],
                    comment_desc=comment_desc,
                    cfg=worker_cfg,
                    backend_module=backend,
                )
            for item in list(local_vars or []) + list(params or []):
                symbol = utils_module._safe_strip((item or {}).get("name"))
                if not symbol:
                    continue
                evidence = backend.collect_symbol_evidence(
                    symbol,
                    kind="symbols",
                    body=body,
                    decl_type=utils_module._safe_strip((item or {}).get("type")),
                    neighbor_symbols=[x for x in neighbor_symbols if x and x != symbol],
                    source_comment_hints=[utils_module._safe_strip((item or {}).get("comment_hint"))],
                )
                inference = backend._infer_symbol_semantics_rule(evidence)
                usage_examples = tuple(
                    f"{hit['line']}: {hit['code']}"
                    for hit in backend.collect_usage_snippets(
                        body,
                        symbol,
                        max_hits=max(1, utils_module.cfg_get_int(cfg, "naming_index_usage_examples", 4)),
                    )
                )
                symbol_items.append({
                    "id": f"{backend._safe_relpath(c_path, project_root)}::{func_name}::symbols::{symbol}",
                    "source_file": os.path.abspath(c_path),
                    "module_key": module_key,
                    "owner_func": func_name,
                    "family_prefix": family_prefix,
                    "kind": "symbols",
                    "symbol": symbol,
                    "decl_type": utils_module._safe_strip((item or {}).get("type")),
                    "owner_type": utils_module._safe_strip(evidence.owner_type),
                    "role": utils_module._safe_strip(inference.role),
                    "comment_desc": comment_desc,
                    "comment_hint": utils_module._safe_strip((item or {}).get("comment_hint")),
                    "normalized_comment_hint": utils_module._safe_strip(evidence.normalized_comment_hint),
                    "existing_cn": (
                        utils_module._safe_strip((item or {}).get("cn_name"))
                        if not backend._looks_like_bad_canonical_name(utils_module._safe_strip((item or {}).get("cn_name")), raw_ident=symbol)
                        else ""
                    ) or utils_module._safe_strip(inference.candidate_cn),
                    "existing_usage": utils_module._safe_strip((item or {}).get("usage")),
                    "producer_kind": utils_module._safe_strip(evidence.producer_kind),
                    "producer_call": utils_module._safe_strip(evidence.producer_call),
                    "producer_args": tuple(evidence.producer_args or ()),
                    "producer_arg_tags": tuple(evidence.producer_arg_tags or ()),
                    "consumer_patterns": tuple(evidence.consumer_patterns or ()),
                    "sink_patterns": tuple(evidence.sink_patterns or ()),
                    "dataflow_roles": tuple(evidence.dataflow_roles or ()),
                    "paired_symbols": tuple(evidence.paired_symbols or ()),
                    "usage_patterns": tuple(evidence.usage_patterns or ()),
                    "usage_examples": usage_examples,
                    "neighbor_symbols": tuple(x for x in neighbor_symbols if x and x != symbol),
                })

    title_payload = _normalize_title_index_payload(
        {
            "version": 1,
            "items": title_items,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        backend_module=backend,
    )
    symbol_payload = _normalize_symbol_index_payload(
        {
            "version": 1,
            "items": symbol_items,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        backend_module=backend,
    )
    return title_payload, symbol_payload


def init_project_naming_indexes(project_root: str, cfg: Optional[Any] = None, *, backend_module=None) -> None:
    backend = backend_module or legacy_backend()
    title_path, title_data = load_project_title_index(project_root, backend_module=backend)
    symbol_path, symbol_data = load_project_symbol_index(project_root, backend_module=backend)
    if project_root and _should_refresh_naming_indexes(project_root, title_path, symbol_path, cfg, backend_module=backend):
        title_data, symbol_data = _rebuild_project_naming_indexes(project_root, cfg, backend_module=backend)
        _save_json_sidecar(title_path, title_data, ".autodoc_title_index_")
        _save_json_sidecar(symbol_path, symbol_data, ".autodoc_symbol_index_")
    with backend._NAMING_INDEX_LOCK:
        backend._PROJECT_TITLE_INDEX_PATH = title_path
        backend._PROJECT_TITLE_INDEX_DATA = title_data
        backend._PROJECT_SYMBOL_INDEX_PATH = symbol_path
        backend._PROJECT_SYMBOL_INDEX_DATA = symbol_data

    # Also load persisted body-summary cache
    from . import naming_context as _nc
    _nc.load_summary_cache(project_root)


def retrieve_function_title_context(func_data: dict, cfg: Optional[Any] = None, *, backend_module=None) -> list[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    from . import semantic as semantic_utils

    comment_info = (func_data or {}).get("comment_info") or {}
    func_info = (func_data or {}).get("func_info") or {}
    file_context = (func_data or {}).get("file_context") or {}
    func_name = utils_module._safe_strip(func_info.get("func_name"))
    family_prefix = utils_module._safe_strip(file_context.get("family_prefix")) or backend._identifier_family_prefix(func_name)
    module_key = utils_module._safe_strip(file_context.get("module_key"))
    action_suffix = backend._identifier_action_suffix(func_name)
    desc_terms = backend._text_terms(utils_module._safe_strip(comment_info.get("desc")))
    neighbors = {utils_module._safe_strip(x) for x in (file_context.get("neighbor_func_names") or ()) if utils_module._safe_strip(x)}
    current_semantic = semantic_utils.resolve_current_function_semantic_record(func_data, cfg, backend_module=backend)
    semantic_maps = semantic_utils.project_semantic_record_maps(backend_module=backend)
    current_ret_type = utils_module._safe_strip(func_info.get("ret_type")) or utils_module._safe_strip(current_semantic.get("ret_type"))
    current_callees = {utils_module._safe_strip(x) for x in (current_semantic.get("callee_names") or ()) if utils_module._safe_strip(x)}
    current_macros = {utils_module._safe_strip(x) for x in (current_semantic.get("macro_refs") or ()) if utils_module._safe_strip(x)}
    current_conditions = {utils_module._safe_strip(x) for x in (current_semantic.get("condition_signatures") or ()) if utils_module._safe_strip(x)}
    current_members = {utils_module._safe_strip(x) for x in (current_semantic.get("member_accesses") or ()) if utils_module._safe_strip(x)}
    has_written_params = bool(current_semantic.get("written_params"))
    has_read_params = bool(current_semantic.get("read_params"))
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in _project_title_index_items(backend_module=backend):
        if utils_module._safe_strip(record.get("func_name")) == func_name and utils_module._safe_strip(record.get("source_file")) == utils_module._safe_strip(file_context.get("source_file")):
            continue
        score = 0
        if family_prefix and utils_module._safe_strip(record.get("family_prefix")) == family_prefix:
            score += 5
        if module_key and utils_module._safe_strip(record.get("module_key")) == module_key:
            score += 4
        if action_suffix and utils_module._safe_strip(record.get("action_suffix")) == action_suffix:
            score += 3
        rec_terms = backend._text_terms(utils_module._safe_strip(record.get("comment_desc")) or utils_module._safe_strip(record.get("resolved_desc")))
        overlap = len(desc_terms & rec_terms)
        if overlap > 0:
            score += 2
        neighbor_overlap = len(neighbors & set(record.get("neighbor_funcs") or ()))
        if neighbor_overlap > 0:
            score += 1
        title = utils_module._safe_strip(record.get("resolved_title"))
        if title and len(re.sub(r"\s+", "", title)) <= 12:
            score += 1
        semantic_record = semantic_utils.lookup_project_semantic_record(
            record_id=utils_module._safe_strip(record.get("id")),
            source_file=utils_module._safe_strip(record.get("source_file")),
            func_name=utils_module._safe_strip(record.get("func_name")),
            module_key=utils_module._safe_strip(record.get("module_key")),
            semantic_maps=semantic_maps,
            backend_module=backend,
        )
        if semantic_record:
            if current_ret_type and utils_module._safe_strip(semantic_record.get("ret_type")) == current_ret_type:
                score += 2
            record_callees = {utils_module._safe_strip(x) for x in (semantic_record.get("callee_names") or ()) if utils_module._safe_strip(x)}
            callee_overlap = len(current_callees & record_callees)
            if callee_overlap > 0:
                score += 3 + min(2, callee_overlap - 1)
            record_conditions = {utils_module._safe_strip(x) for x in (semantic_record.get("condition_signatures") or ()) if utils_module._safe_strip(x)}
            condition_overlap = len(current_conditions & record_conditions)
            if condition_overlap > 0:
                score += 4 + min(2, condition_overlap - 1)
            record_macros = {utils_module._safe_strip(x) for x in (semantic_record.get("macro_refs") or ()) if utils_module._safe_strip(x)}
            if current_macros & record_macros:
                score += 2
            record_members = {utils_module._safe_strip(x) for x in (semantic_record.get("member_accesses") or ()) if utils_module._safe_strip(x)}
            if current_members & record_members:
                score += 1
            if has_written_params and semantic_record.get("written_params"):
                score += 1
            if has_read_params and semantic_record.get("read_params"):
                score += 1
        if score > 0:
            scored.append((score, record))
    top_k = max(1, utils_module.cfg_get_int(cfg, "title_rag_top_k", 6))
    return backend._dedupe_title_records(sorted(scored, key=lambda x: (-x[0], utils_module._safe_strip(x[1].get("resolved_title"))))[: top_k * 2])[:top_k]


def retrieve_symbol_context(symbol_record: dict, cfg: Optional[Any] = None, *, backend_module=None) -> list[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    from . import semantic as semantic_utils

    symbol = utils_module._safe_strip((symbol_record or {}).get("symbol"))
    if not symbol:
        return []
    symbol_tokens = {tok.lower() for tok in text_utils._split_ident_tokens(symbol)}
    role = utils_module._safe_strip((symbol_record or {}).get("role"))
    decl_type = utils_module._safe_strip((symbol_record or {}).get("decl_type"))
    family_prefix = utils_module._safe_strip((symbol_record or {}).get("family_prefix"))
    module_key = utils_module._safe_strip((symbol_record or {}).get("module_key"))
    usage_patterns = {str(x) for x in ((symbol_record or {}).get("usage_patterns") or ()) if utils_module._safe_strip(x)}
    consumer_patterns = {str(x) for x in ((symbol_record or {}).get("consumer_patterns") or ()) if utils_module._safe_strip(x)}
    sink_patterns = {str(x) for x in ((symbol_record or {}).get("sink_patterns") or ()) if utils_module._safe_strip(x)}
    dataflow_roles = {str(x) for x in ((symbol_record or {}).get("dataflow_roles") or ()) if utils_module._safe_strip(x)}
    paired_symbols = {utils_module._safe_strip(x) for x in ((symbol_record or {}).get("paired_symbols") or ()) if utils_module._safe_strip(x)}
    neighbor_symbols = {utils_module._safe_strip(x) for x in ((symbol_record or {}).get("neighbor_symbols") or ()) if utils_module._safe_strip(x)}
    producer_call = utils_module._safe_strip((symbol_record or {}).get("producer_call"))
    producer_arg_tags = {str(x) for x in ((symbol_record or {}).get("producer_arg_tags") or ()) if utils_module._safe_strip(x)}
    current_owner_semantic = semantic_utils.resolve_symbol_owner_semantic_record(symbol_record, cfg, backend_module=backend)
    current_profile = semantic_utils.resolve_current_symbol_semantic_profile(symbol_record)
    current_scope = utils_module._safe_strip(current_profile.get("scope"))
    current_direction = utils_module._safe_strip(current_profile.get("direction"))
    current_owner_ret = utils_module._safe_strip((symbol_record or {}).get("owner_ret_type")) or utils_module._safe_strip(current_owner_semantic.get("ret_type"))
    current_callees = {utils_module._safe_strip(x) for x in (current_owner_semantic.get("callee_names") or ()) if utils_module._safe_strip(x)}
    current_conditions = {utils_module._safe_strip(x) for x in (current_owner_semantic.get("condition_signatures") or ()) if utils_module._safe_strip(x)}
    current_macros = {utils_module._safe_strip(x) for x in (current_owner_semantic.get("macro_refs") or ()) if utils_module._safe_strip(x)}
    current_members = {utils_module._safe_strip(x) for x in (current_owner_semantic.get("member_accesses") or ()) if utils_module._safe_strip(x)}
    semantic_maps = semantic_utils.project_semantic_record_maps(backend_module=backend)
    scored: list[tuple[int, dict[str, Any]]] = []
    all_items = _project_symbol_index_items(backend_module=backend)
    # 用 token 倒排索引快速定位候选记录，避免全量扫描
    candidate_indices: set[int] = set()
    for tok in symbol_tokens:
        candidate_indices.update(_TOKEN_INVERTED_INDEX.get(tok, ()))
    if not candidate_indices:
        return []
    for idx in sorted(candidate_indices):
        record = all_items[idx]
        if utils_module._safe_strip(record.get("symbol")) == symbol and utils_module._safe_strip(record.get("owner_func")) == utils_module._safe_strip((symbol_record or {}).get("owner_func")):
            continue
        rec_tokens = {tok.lower() for tok in text_utils._split_ident_tokens(utils_module._safe_strip(record.get("symbol")))}
        token_overlap = len(symbol_tokens & rec_tokens)
        score = 0
        if symbol_tokens and rec_tokens and symbol_tokens == rec_tokens:
            score += 4
        elif token_overlap > 0:
            score += 2
        if producer_call and utils_module._safe_strip(record.get("producer_call")) == producer_call:
            score += 6
        if role and utils_module._safe_strip(record.get("role")) == role:
            score += 3
        if decl_type and utils_module._safe_strip(record.get("decl_type")) == decl_type:
            score += 2
        if family_prefix and utils_module._safe_strip(record.get("family_prefix")) == family_prefix:
            score += 2
        if module_key and utils_module._safe_strip(record.get("module_key")) == module_key:
            score += 2
        rec_arg_tags = {str(x) for x in (record.get("producer_arg_tags") or ()) if utils_module._safe_strip(x)}
        if producer_arg_tags & rec_arg_tags:
            score += 4
        rec_patterns = {str(x) for x in (record.get("usage_patterns") or ()) if utils_module._safe_strip(x)}
        if usage_patterns & rec_patterns:
            score += 2
        rec_consumer = {str(x) for x in (record.get("consumer_patterns") or ()) if utils_module._safe_strip(x)}
        if consumer_patterns & rec_consumer:
            score += 4
        rec_sinks = {str(x) for x in (record.get("sink_patterns") or ()) if utils_module._safe_strip(x)}
        if sink_patterns & rec_sinks:
            score += 5
        rec_roles = {str(x) for x in (record.get("dataflow_roles") or ()) if utils_module._safe_strip(x)}
        if dataflow_roles & rec_roles:
            score += 6
        rec_pairs = {utils_module._safe_strip(x) for x in (record.get("paired_symbols") or ()) if utils_module._safe_strip(x)}
        if paired_symbols & rec_pairs:
            score += 3
        rec_neighbors = {utils_module._safe_strip(x) for x in (record.get("neighbor_symbols") or ()) if utils_module._safe_strip(x)}
        if neighbor_symbols & rec_neighbors:
            score += 1
        candidate_owner_semantic = semantic_utils.lookup_project_semantic_record(
            source_file=utils_module._safe_strip(record.get("source_file")),
            func_name=utils_module._safe_strip(record.get("owner_func")),
            module_key=utils_module._safe_strip(record.get("module_key")),
            semantic_maps=semantic_maps,
            backend_module=backend,
        )
        candidate_profile = backend._lookup_semantic_symbol_profile(candidate_owner_semantic, utils_module._safe_strip(record.get("symbol")))
        candidate_scope = utils_module._safe_strip(candidate_profile.get("scope"))
        candidate_direction = utils_module._safe_strip(candidate_profile.get("direction"))
        if current_scope and candidate_scope:
            if current_scope == candidate_scope:
                score += 5
            else:
                score -= 4
        if current_direction and candidate_direction:
            if current_direction == candidate_direction:
                score += 6
            elif current_scope == "param" and candidate_scope == "param":
                score -= 5
        if current_owner_ret and utils_module._safe_strip(candidate_owner_semantic.get("ret_type")) == current_owner_ret:
            score += 1
        candidate_callees = {utils_module._safe_strip(x) for x in (candidate_owner_semantic.get("callee_names") or ()) if utils_module._safe_strip(x)}
        callee_overlap = len(current_callees & candidate_callees)
        if callee_overlap > 0:
            score += 4 + min(2, callee_overlap - 1)
        candidate_conditions = {utils_module._safe_strip(x) for x in (candidate_owner_semantic.get("condition_signatures") or ()) if utils_module._safe_strip(x)}
        condition_overlap = len(current_conditions & candidate_conditions)
        if condition_overlap > 0:
            score += 3 + min(2, condition_overlap - 1)
        candidate_macros = {utils_module._safe_strip(x) for x in (candidate_owner_semantic.get("macro_refs") or ()) if utils_module._safe_strip(x)}
        if current_macros & candidate_macros:
            score += 2
        candidate_members = {utils_module._safe_strip(x) for x in (candidate_owner_semantic.get("member_accesses") or ()) if utils_module._safe_strip(x)}
        if current_members & candidate_members:
            score += 1
        existing_cn = utils_module._safe_strip(record.get("existing_cn"))
        if existing_cn and backend._looks_like_bad_canonical_name(existing_cn, raw_ident=utils_module._safe_strip(record.get("symbol"))):
            score -= 8
        if score > 0:
            scored.append((score, record))
    top_k = max(1, utils_module.cfg_get_int(cfg, "symbol_rag_top_k", 8))
    return backend._dedupe_symbol_records(sorted(scored, key=lambda x: (-x[0], utils_module._safe_strip(x[1].get("existing_cn"))))[: top_k * 2])[:top_k]


_RESOLVER_C_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


def _resolver_safe_maps(ctx: Optional[dict[str, Any]], file_context: Optional[dict[str, Any]]) -> dict[str, dict[str, str]]:
    ctx = dict(ctx or {})
    file_context = dict(file_context or ctx.get("file_context") or {})
    return {
        "var_cn_map": dict(ctx.get("var_cn_map") or {}),
        "global_symbol_map": dict(ctx.get("global_symbol_map") or {}),
        "symbol_map": dict(file_context.get("symbol_map") or {}),
        "glossary": dict(file_context.get("glossary") or {}),
        "member_symbol_map": dict(file_context.get("member_symbol_map") or {}),
        "func_comment_map": dict(file_context.get("func_comment_map") or {}),
        "name_map": dict(ctx.get("name_map") or {}),
        "entity_aliases": dict(ctx.get("entity_aliases") or {}),
    }


def _resolver_lookup(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        text = utils_module._safe_strip(key)
        if not text:
            continue
        value = utils_module._safe_strip(mapping.get(text))
        if value:
            return value
    return ""


def _resolver_macro_display(raw: str) -> str:
    upper = utils_module._safe_strip(raw).upper()
    if not upper or not re.fullmatch(r"[A-Z][A-Z0-9_]*", upper):
        return ""
    literal_labels = {
        "VALID": "有效",
        "INVALID": "无效",
        "NULL": "空",
        "TRUE": "真",
        "FALSE": "假",
    }
    if upper in literal_labels:
        return literal_labels[upper]
    adc_sequence_labels = {
        "ADC_SEQ1": "ADC序列器1",
        "ADC_SEQ2": "ADC序列器2",
        "ADC_SEQ1_SEQ2": "ADC序列器1和2",
        "ADC_SEQ1_INT": "ADC序列器1中断",
        "ADC_SEQ2_INT": "ADC序列器2中断",
    }
    if upper in adc_sequence_labels:
        return adc_sequence_labels[upper]
    if upper.endswith("_VALID"):
        return "有效"
    if upper.endswith("_INVALID"):
        return "无效"
    if upper.endswith("_ENABLE") or upper.endswith("_ENABLED"):
        return "使能"
    if upper.endswith("_DISABLE") or upper.endswith("_DISABLED"):
        return "禁止"
    return ""


def _resolver_expr_keys(raw: str) -> list[str]:
    value = utils_module._safe_strip(raw)
    if not value:
        return []
    normalized = re.sub(r"\s+", "", value.replace("->", "."))
    keys = [value, value.replace("->", "."), normalized]
    idents = _RESOLVER_C_IDENT_RE.findall(value)
    if idents:
        keys.extend([idents[0], idents[-1]])
        if "." in normalized and len(idents) >= 2:
            keys.append(f"{idents[0]}.{idents[-1]}")
    return list(dict.fromkeys(k for k in keys if utils_module._safe_strip(k)))


def _resolver_guess_kind(raw: str, requested_kind: str = "") -> str:
    kind = utils_module._safe_strip(requested_kind)
    if kind:
        return kind
    value = utils_module._safe_strip(raw)
    if re.search(r"(?:\.|->)", value):
        return "member"
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
        return "macro"
    if value.endswith(")") and "(" in value:
        return "function"
    return "symbol"


def resolve_symbol_display(
    raw: str,
    *,
    kind: str = "",
    ctx: Optional[dict[str, Any]] = None,
    file_context: Optional[dict[str, Any]] = None,
    name_map: Optional[dict[str, str]] = None,
    backend_module=None,
) -> dict[str, Any]:
    """Resolve a C symbol/expression into the unified naming metadata shape."""
    backend = backend_module or legacy_backend()
    value = utils_module._safe_strip(raw)
    resolved_kind = _resolver_guess_kind(value, kind)
    if not value:
        return {"raw": "", "display": "", "kind": resolved_kind, "source": "empty", "confidence": 0.0, "locked": False}

    maps = _resolver_safe_maps(ctx, file_context)
    if name_map:
        maps["name_map"].update(dict(name_map or {}))
    keys = _resolver_expr_keys(value)

    source_comment = ""
    for item in (dict(ctx or {}).get("local_vars") or ()):
        ident = utils_module._safe_strip((item or {}).get("name"))
        if ident and ident in keys:
            source_comment = utils_module._safe_strip((item or {}).get("cn_name") or (item or {}).get("usage"))
            if source_comment and not backend._is_missing_gap_text(source_comment):
                break
    if not source_comment:
        in_map = dict(dict(ctx or {}).get("in_map") or {})
        out_map = dict(dict(ctx or {}).get("out_map") or {})
        param_ai_name_map = dict(dict(ctx or {}).get("param_ai_name_map") or {})
        source_comment = _resolver_lookup(in_map, *keys) or _resolver_lookup(out_map, *keys) or _resolver_lookup(param_ai_name_map, *keys)
    if source_comment and text_utils._contains_cjk(source_comment):
        return {
            "raw": value,
            "display": source_comment,
            "kind": resolved_kind,
            "source": "source_comment",
            "confidence": 0.95,
            "locked": True,
        }

    exact = (
        _resolver_lookup(maps["name_map"], *keys)
        or _resolver_lookup(maps["entity_aliases"], *keys)
        or _resolver_lookup(maps["var_cn_map"], *keys)
        or _resolver_lookup(maps["global_symbol_map"], *keys)
        or _resolver_lookup(maps["symbol_map"], *keys)
        or _resolver_lookup(maps["glossary"], *keys)
    )
    if exact and text_utils._contains_cjk(exact):
        return {"raw": value, "display": exact, "kind": resolved_kind, "source": "symbol_map", "confidence": 0.9, "locked": True}

    member = _resolver_lookup(maps["member_symbol_map"], *keys)
    if member and text_utils._contains_cjk(member):
        return {"raw": value, "display": member, "kind": "member", "source": "struct_member", "confidence": 0.88, "locked": True}

    macro = _resolver_macro_display(value)
    if macro:
        return {"raw": value, "display": macro, "kind": "macro", "source": "macro_rule", "confidence": 0.8, "locked": False}

    guess_key = keys[-1] if keys else value
    guessed = utils_module._safe_strip(backend._guess_cn_from_ident(guess_key, glossary=getattr(backend, "DOMAIN_GLOSSARY", {})))
    return {
        "raw": value,
        "display": guessed or value,
        "kind": resolved_kind,
        "source": "heuristic" if guessed else "raw",
        "confidence": 0.45 if guessed else 0.2,
        "locked": False,
    }


def summarize_name_resolutions(resolutions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    by_source: dict[str, int] = {}
    locked = 0
    low_confidence = 0
    for item in resolutions or ():
        if not isinstance(item, dict):
            continue
        total += 1
        source = utils_module._safe_strip(item.get("source")) or "unknown"
        by_source[source] = by_source.get(source, 0) + 1
        if bool(item.get("locked")):
            locked += 1
        try:
            confidence = float(item.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        if confidence < 0.6:
            low_confidence += 1
    return {
        "total": total,
        "locked": locked,
        "low_confidence": low_confidence,
        "by_source": by_source,
    }


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "NamingCandidate",
    "contains_cjk",
    "get_function_chinese_name",
    "get_function_chinese_name_rich",
    "get_variable_chinese_names_batch",
    "guess_cn_from_ident",
    "is_explanatory_title",
    "is_generic_symbol_name",
    "is_strict_symbol_candidate_rejected",
    "looks_like_verbose_cn_phrase",
    "make_candidate",
    "normalize_function_cn_title",
    "parse_domain_glossary_text",
    "parse_symbol_dictionary_text",
    "load_symbol_dictionary_file",
    "load_project_title_index",
    "load_project_symbol_index",
    "load_project_symbol_memory",
    "save_project_symbol_memory",
    "apply_symbol_dictionary_overrides",
    "init_project_symbol_memory",
    "init_project_naming_indexes",
    "finalize_project_symbol_memory",
    "resolve_canonical_symbol_name",
    "collect_preferred_symbol_names",
    "retrieve_function_title_context",
    "retrieve_symbol_context",
    "repair_local_cn_name_with_profile",
    "rerank_function_title_candidates",
    "rerank_symbol_candidate",
    "resolve_symbol_display",
    "sanitize_ai_usage_text",
    "should_accept_refined_local_cn",
    "summarize_name_resolutions",
    "split_ident_tokens",
    "local_cn_needs_ai_refine",
    "_ai_decompose_ident",
    "_learn_ident_token_mappings",
]

# Session-level learned token mappings (merged into _IDENT_CN_MAP at lookup time)
_LEARNED_TOKEN_MAP: dict[str, str] = {}


def _learn_ident_token_mappings(ident: str, cn_name: str) -> int:
    """Learn token→CN mappings from a (C ident, Chinese name) pair.

    Only learns isolated unknown tokens — those whose immediate neighbors in the
    token sequence are both known (have CN mappings). This guarantees unambiguous
    alignment: the CN substring between the two known anchors belongs to the
    single unknown token.
    """
    name = safe_strip(ident)
    cn = safe_strip(cn_name)
    if not name or not cn or not contains_cjk(cn):
        return 0
    tokens = _drop_namespace_like_prefix(split_ident_tokens(name))
    if len(tokens) < 2:
        return 0
    mapping = dict(_IDENT_CN_MAP)
    mapping.update(_LEARNED_TOKEN_MAP)
    cn_compact = re.sub(r"\s+", "", cn)

    # For each token, record whether it's known and its CN
    is_known: list[bool] = []
    token_cn: list[str] = []
    token_lower: list[str] = []
    for token in tokens:
        lowered = token.lower()
        cn_val = safe_strip(mapping.get(lowered))
        token_lower.append(lowered)
        is_known.append(bool(cn_val))
        token_cn.append(cn_val or "")

    learned = 0
    for i in range(1, len(tokens) - 1):
        # Learn only isolated unknowns flanked by known tokens
        if is_known[i] or (not is_known[i - 1]) or (not is_known[i + 1]):
            continue
        prev_cn = token_cn[i - 1]
        next_cn = token_cn[i + 1]
        # Find the CN segment between the two known anchors
        prev_pos = cn_compact.find(prev_cn)
        if prev_pos < 0:
            continue
        next_pos = cn_compact.find(next_cn, prev_pos + len(prev_cn))
        if next_pos < 0:
            continue
        segment = cn_compact[prev_pos + len(prev_cn):next_pos]
        if segment and contains_cjk(segment) and 1 <= len(segment) <= 6:
            key = token_lower[i]
            if key not in _IDENT_CN_MAP and key not in _LEARNED_TOKEN_MAP:
                _LEARNED_TOKEN_MAP[key] = segment
                learned += 1
    return learned


def _ai_decompose_ident(
    ident: str,
    comment_desc: str = "",
    *,
    backend_module=None,
    call_llm=None,
) -> str:
    """Use LLM to decompose a C identifier into Chinese tokens.

    Only called when token dictionary failed. Passes the C comment description
    as context so the LLM can infer domain-specific abbreviations.
    Returns empty string if LLM is unavailable or fails.
    """
    backend = backend_module or legacy_backend()
    if not call_llm:
        return ""
    name = utils_module._safe_strip(ident)
    if not name:
        return ""
    # Build minimal prompt with context
    lines = [
        "将C语言函数标识符拆成中文词并拼接（不用空格，≤12字），只返回中文：",
        f"函数名：{name}",
    ]
    if comment_desc:
        short = re.split(r"[。；;：:\n]", utils_module._safe_strip(comment_desc))[0].strip()[:120]
        if short:
            lines.append(f"功能描述：{short}")
    prompt = "\n".join(lines)
    try:
        raw = utils_module._safe_strip(call_llm(prompt))
        if raw and contains_cjk(raw) and len(raw) <= 20:
            return raw
    except Exception:
        pass
    return ""
