"""Portable project semantic registry for logic and local naming hints.

The registry is intentionally rule-based: it recognizes reusable embedded-C
patterns and exposes conservative semantic labels for downstream LLM context.
"""

from __future__ import annotations

import re
from typing import Any

from ._legacy_support import legacy_backend
from . import utils
from . import parse as parse_utils


REGISTRY_VERSION = 1


def registry_snapshot() -> dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "entity_classes": [
            "pack_buffer",
            "compat_word",
            "mode_word",
            "error_flag",
            "convert_ratio",
            "snapshot_value",
            "counter_value",
            "validity_flag",
        ],
        "patterns": [
            "pack_buffer_fill",
            "result_surface_write",
            "compat_word_fill",
            "mode_word_sync",
            "error_flag_assign",
            "snapshot_compare",
            "filter_output",
            "counter_update",
            "validity_flag_assign",
        ],
    }


def _safe(value: Any) -> str:
    return utils._safe_strip(value)


def _lower(value: Any) -> str:
    return _safe(value).lower()


def _has_any(value: str, tokens: tuple[str, ...]) -> bool:
    return any(token in value for token in tokens)


_SHORT_LOOP_INDEX_RE = re.compile(r"(?:^|_)(?:ii|jj|kk)(?:_|$|\d)")


def _has_short_loop_index_token(ident: str) -> bool:
    """Detect the short loop-index tokens ``ii``/``jj``/``kk`` only as
    standalone tokens or with a numeric suffix.

    Substring matching on these tokens is unsafe: ``sciinfo`` contains
    ``ii``, ``aidxbuf`` contains ``ii`` at the boundary, etc.  The
    older behavior let them all be classified as loop indices, which
    then leaked "循环索引" into struct-field translations.
    """
    if not ident:
        return False
    return _SHORT_LOOP_INDEX_RE.search(ident) is not None


def _strip_local_affixes(name: str) -> str:
    ident = _lower(name)
    ident = re.sub(r"^(?:l|ls|lc|lp|s|g)_+", "", ident)
    ident = re.sub(r"_(?:u|i)?(?:8|16|32|64|6|f|t|p)$", "", ident)
    ident = re.sub(r"_(?:u|i)?(?:8|16|32|64|6)$", "", ident)
    return ident


def _domain_subject_label(ident: str) -> str:
    subject = ""
    if _has_any(ident, ("inlet", "letin", "ivalve", "invalve")):
        subject = "入口阀"
    elif _has_any(ident, ("eject", "evalve")):
        subject = "引射阀"
    elif _has_any(ident, ("temppress", "temp_press")):
        subject = "调温调压阀"
    elif _has_any(ident, ("tempval", "tvalve")):
        subject = "调温阀"
    elif _has_any(ident, ("pressval", "pvalve")):
        subject = "调压阀"
    elif "valve" in ident:
        subject = "活门"
    return subject


def infer_local_semantic_label(name: str, decl_type: str = "", usage: str = "") -> str:
    ident = _strip_local_affixes(name)
    decl = _lower(decl_type)
    usage_l = _lower(usage)
    if not ident:
        return ""
    is_last = ident.startswith(("last", "prev", "previous"))
    core = re.sub(r"^(?:last|prev|previous)_?", "", ident)
    side = ""
    if "left" in core or core.startswith("lp") or core.startswith("lft"):
        side = "左"
    elif "right" in core or core.startswith("rp") or core.startswith("rgt"):
        side = "右"

    def _with_last(label: str) -> str:
        if not label:
            return ""
        return f"上一周期{label}" if is_last else label

    if "mbitcmd" in core or ("mbit" in core and "cmd" in core):
        return _with_last("维护BIT执行命令")
    if "pzvalid" in core or ("pz" in core and "valid" in core):
        return _with_last("配置信息请求有效标志")
    if "prefuel" in core or ("pre" in core and "fuel" in core):
        prefix = f"{side}吊舱" if side else ""
        return _with_last(f"{prefix}预选油量")
    if "life" in core:
        prefix = f"{side}吊舱" if side else ""
        return _with_last(f"{prefix}寿命信息请求")
    if "oilreset" in core or ("oil" in core and "reset" in core):
        prefix = f"{side}吊舱" if side else ""
        return _with_last(f"{prefix}油量清零请求")
    if "fuelreset" in core or ("fuel" in core and "reset" in core):
        return _with_last("燃油复位请求")
    if "lowfuel" in core or ("low" in core and "fuel" in core):
        return _with_last("低油量标志")
    if core == "air" or core.endswith("air"):
        return _with_last("空地状态")
    subject = _domain_subject_label(ident)
    if "invalidconfirmed" in ident or ("invalid" in ident and "confirmed" in ident):
        if "otherchv" in ident:
            return "对端CHV无效确认"
        return "无效确认"
    if subject and "close" in ident and _has_any(ident, ("done", "finish", "complete")):
        return f"{subject}关闭完成标志"
    if subject and "close" in ident:
        return f"{subject}关闭指令标志"
    if "closedone" in ident or ("close" in ident and "done" in ident):
        return "活门全关完成标志"
    if _has_any(ident, ("done", "finish", "complete")) and _has_any(ident, ("flag", "flg", "state", "st")):
        return "完成标志"
    if "datastate" in ident or ("data" in ident and "state" in ident):
        if "left" in ident or ident.startswith("lft"):
            return "左侧数据状态"
        if "right" in ident or ident.startswith("rgt"):
            return "右侧数据状态"
        return "数据状态"
    if _has_any(ident, ("busy", "busyst")):
        return "忙状态"
    if _has_any(ident, ("state", "status")):
        return "状态"
    if _has_any(ident, ("flag", "flg")):
        return "标志"
    if _has_any(ident, ("time", "systime", "timer")) or "time" in decl or "时间" in usage_l:
        return "系统时间" if "sys" in ident or "系统" in usage_l else "时间值"
    if _has_any(ident, ("cnt", "count", "counter")) or "计数" in usage_l:
        return "计数值"
    if _has_any(ident, ("idx", "index")) or _has_short_loop_index_token(ident):
        return "循环索引"
    if _has_any(ident, ("buff", "buf", "buffer")):
        return "缓存数组" if "[" in decl or "数组" in usage_l else "缓存值"
    return ""


def lookup_var_role(ident: str) -> str:
    """Quick lookup: given a C identifier name, return a short role label
    that distinguishes loop counters from other variables.

    Returns one of:
        "loop_index" — for ii/jj/kk short tokens, idx/index patterns
        "state"     — state/status word
        "flag"      — flag/flg bit
        "time"      — timer/systime
        "count"     — cnt/count/counter
        "buffer"    — buff/buf/buffer
        "data"      — generic data/datax/info
        ""          — unknown / unclassified

    This is used by the docx quality scorer and the AI desc post-processor
    to detect when the LLM has mistranslated a loop counter into a
    domain noun like 扇区号 / 查询xxx.
    """
    if not ident:
        return ""
    ident_l = _lower(ident)
    if _has_short_loop_index_token(ident_l) or _has_any(ident_l, ("idx", "index")):
        return "loop_index"
    if _has_any(ident_l, ("state", "status")):
        return "state"
    if _has_any(ident_l, ("flag", "flg")):
        return "flag"
    if _has_any(ident_l, ("time", "systime", "timer")):
        return "time"
    if _has_any(ident_l, ("cnt", "count", "counter")):
        return "count"
    if _has_any(ident_l, ("buff", "buf", "buffer")):
        return "buffer"
    if _has_any(ident_l, ("data", "info")):
        return "data"
    return ""


def classify_entity(name: str, decl_type: str = "", usage: str = "") -> dict[str, Any]:
    ident = _lower(name)
    decl = _lower(decl_type)
    usage_l = _lower(usage)
    if not ident:
        return {}
    if "[" in ident and "]" in ident:
        match = re.match(r"\s*([a-z_]\w*)\s*\[", ident)
        if match:
            ident = match.group(1)

    packet_match = re.search(r"(?:pmfl|data)(\d{3})", ident) or re.search(r"(?:pmfl|data)(\d{3})", decl)
    if packet_match and _has_any(f"{ident} {decl}", ("1553b", "pmfl", "revdef", "data")):
        word_no = packet_match.group(1)
        return {"class": "pack_buffer", "label": f"{word_no}字打包缓存", "confidence": 0.9}

    if "mode" in ident and "compat" in ident:
        return {"class": "mode_word", "label": "模式源字", "confidence": 0.88}
    if "compat" in ident:
        if "act" in ident and "flt" in decl:
            return {"class": "compat_word", "label": "作动器故障兼容字", "confidence": 0.9}
        if "flt" in decl or "fault" in decl:
            return {"class": "compat_word", "label": "故障兼容字", "confidence": 0.84}
        return {"class": "compat_word", "label": "兼容字", "confidence": 0.78}

    if "modesrcerr" in ident:
        return {"class": "error_flag", "label": "模式源有效性错误标志", "confidence": 0.88}
    if ident.endswith("srcerr_u16") or "srcerr" in ident:
        return {"class": "error_flag", "label": "源有效性错误标志", "confidence": 0.86}
    if ident.endswith("modeerr_u16") or "modeerr" in ident:
        return {"class": "error_flag", "label": "模式错误标志", "confidence": 0.86}
    if _has_any(ident, ("valid", "vld", "validity")) and _has_any(ident, ("flag", "flg", "err")):
        return {"class": "validity_flag", "label": "有效性标志", "confidence": 0.76}

    if _has_any(ident, ("ratio", "scale")):
        return {"class": "convert_ratio", "label": "换算系数", "confidence": 0.82}
    if "gain" in ident:
        return {"class": "convert_ratio", "label": "增益系数", "confidence": 0.82}

    if ident.startswith("l_s_") or ident.startswith("s_last") or _has_any(ident, ("last", "prev", "snapshot")):
        return {"class": "snapshot_value", "label": "状态快照", "confidence": 0.78}
    if _has_any(ident, ("cnt", "count", "counter", "tick")) or "计数" in usage_l:
        return {"class": "counter_value", "label": "计数值", "confidence": 0.72}
    local_label = infer_local_semantic_label(ident, decl_type, usage)
    if local_label:
        local_class = "local_semantic"
        if local_label.endswith("标志"):
            local_class = "flag_value"
        elif "时间" in local_label:
            local_class = "time_value"
        elif "索引" in local_label:
            local_class = "index_value"
        elif "缓存" in local_label:
            local_class = "buffer_value"
        return {"class": local_class, "label": local_label, "confidence": 0.76}
    return {}


def local_name_hint(item: dict[str, Any]) -> str:
    meta = classify_entity(
        _safe((item or {}).get("name")),
        _safe((item or {}).get("type") or (item or {}).get("decl_type")),
        _safe((item or {}).get("usage")),
    )
    if _safe(meta.get("class")) in {"counter_value", "snapshot_value"}:
        return ""
    label = _safe(meta.get("label"))
    if label in {"状态", "标志", "时间值", "缓存值"}:
        return ""
    return label


def classify_state_update(lhs: str, rhs: str) -> str:
    lhs_s = _safe(lhs)
    rhs_s = _safe(rhs)
    lhs_l = lhs_s.lower()
    rhs_l = rhs_s.lower()
    rhs_compact = re.sub(r"\s+", "", rhs_s)
    if rhs_compact in {"0", "0U", "0UL", "0.0F", "0.0f"}:
        return "reset_or_clear"
    lhs_meta = classify_entity(lhs_s.split(".", 1)[0].split("->", 1)[0])
    lhs_class = _safe(lhs_meta.get("class"))
    if lhs_class == "pack_buffer" and ".bit_" in lhs_l:
        return "pack_buffer_fill"
    if lhs_class == "compat_word" and ".bit_" in lhs_l:
        return "compat_word_fill"
    if lhs_class == "mode_word":
        return "mode_word_sync"
    if lhs_class in {"error_flag", "validity_flag"}:
        return "error_flag_assign"
    if lhs_class == "counter_value":
        return "counter_update"
    if (".filtout_" in lhs_l or ".filtout_" in rhs_l) and re.search(r"\bl_data\d{3}_", f"{lhs_l} {rhs_l}"):
        return "result_surface_write"
    if _has_any(lhs_s, ("TxPack", "PackDat", "maint422TxPack", "toFpga")):
        return "pack_output"
    if _has_any(rhs_s, ("DataTrans", "PackUp", "*", "/", "+", "-")):
        return "feedback_compute"
    if "(" in rhs_s and ")" in rhs_s:
        return "control_compute"
    if "." in lhs_s or "->" in lhs_s:
        return "state_sync"
    return "control_compute"


def classify_call_role(callee: str, definition_comment: str = "") -> str:
    backend = legacy_backend()
    ident = _safe(callee)
    desc = _safe(definition_comment)
    lower = ident.lower()
    upper = ident.upper()
    desc_lower = desc.lower()
    if (
        desc_lower.startswith("provided by ")
        or desc_lower.startswith('provided by "')
        or desc.startswith("→")
        or parse_utils._looks_like_placeholder_desc(desc, func_name=ident)
        or backend._is_noop_comment(desc)
        or backend._looks_like_logic_noise_comment(desc)
    ):
        desc = ""
    if desc:
        compact = re.sub(r"[。；;]+$", "", desc)
        if compact and len(compact) <= 18 and "provided by" not in compact.lower():
            return compact

    direct_map = {
        "memset": "初始化内存区域",
        "actposloopcal": "位置环计算",
        "datatransftoint": "数值转换",
        "spiflashdatatrans": "SPI Flash数据传输",
        "spi_flash_datatrans": "执行SPI Flash数据传输",
        "spi_flash_cs_low": "拉低SPI Flash片选",
        "spi_flash_cs_high": "拉高SPI Flash片选",
        "nop": "等待片选建立/保持时序裕量",
        "digidatafilt": "数字滤波",
        "systemdataupdate": "系统数据更新",
        "sysfanctrl": "风扇控制",
        "sysmodeexitcheck": "模式退出检查",
        "sysstartjudge": "启动判定",
        "sysstatejudge": "判定系统状态",
        "sysstateprocess": "执行系统状态处理",
        "syscondataupdate": "更新系统控制运行数据",
        "sysworktimeupdate": "更新系统工作时间",
        "commdatasourceupdate": "更新通信数据来源",
        "comm429riurxstateget": "读取RIU429接收状态",
        "comm429kzzzrxstateget": "读取控制装置429接收状态",
        "comm429kzzzccdlextdataget": "读取KZZZ CCDL镜像数据",
        "comm429kzzzccdlextvalidget": "读取KZZZ CCDL镜像有效性",
        "workmodedataobtain": "获取工作模式数据",
        "airoilmodeupdate": "更新高低压加油模式",
        "standbyfuncupdate": "更新待机功能状态",
        "groundmaintstateupdate": "更新地面维护状态",
        "runtimeroleupdate": "更新运行期主备角色",
        "conoutstateupdate": "更新控制输出状态",
        "syscontrolout": "下发系统控制输出",
        "syscmdmodeset": "模式设置",
        "actposcmdselect": "位置指令选择",
        "pbitproc": "PBIT处理",
        "phmerasecmdproc": "擦除指令处理",
        "syschrgecycleproc": "充电周期处理",
        "controlfaultdebouncereset": "复位控制故障防抖状态",
        "controlmodedebouncereset": "复位控制模式防抖状态",
        "controlmodereentrylatchreset": "复位控制模式重入锁存状态",
        "chvcondataobtain": "采集CHV控制数据",
        "spedataget": "读取专项存储数据",
    }
    if lower in direct_map:
        return direct_map[lower]
    if lower in {"delayus", "delay_us"}:
        return "等待微秒延时"
    if lower in {"delayms", "delay_ms"}:
        return "等待毫秒延时"
    if lower.startswith("delay"):
        return "等待延时"
    if "spiflash" in lower and "datatrans" in lower:
        return "SPI Flash数据传输"
    if "spi_flash" in lower and "datatrans" in lower:
        return "执行SPI Flash数据传输"
    if "spi_flash_cs_low" in lower:
        return "拉低SPI Flash片选"
    if "spi_flash_cs_high" in lower:
        return "拉高SPI Flash片选"
    if lower == "systime" or lower.endswith("timeget"):
        return "读取系统时间"
    if lower.startswith("gpioclear") or lower.endswith("gpioclearnum"):
        return "清除GPIO输出"
    if lower.startswith("gpioset") or lower.endswith("gpiosetnum"):
        return "置位GPIO输出"
    if lower.startswith("gpiotoggle") or lower.endswith("gpiotogglenum"):
        return "翻转GPIO输出"
    if lower.startswith("gpioread"):
        return "读取GPIO输入"
    if lower in {"iodataget", "digidataget"} or lower.endswith("iodataget") or lower.endswith("digidataget"):
        return "读取离散量输入"
    if lower.endswith("resultget"):
        return "读取检测结果"
    if lower.endswith("stateget"):
        return "读取状态"
    if lower.endswith("modeget"):
        return "读取工作模式"
    if lower.endswith("dataget"):
        return "读取数据"
    if "pbit" in lower and "stateupdate" in lower:
        return "PBIT状态更新"
    if "ifbit" in lower and "stateupdate" in lower:
        return "IFBIT状态更新"
    if "pubit" in lower and "stateupdate" in lower:
        return "上电自检状态更新"
    if lower.endswith("stateupdate"):
        return "状态更新"
    if "write" in lower or lower.endswith("wr") or lower.endswith("write"):
        return "写入数据"
    if "sendword" in lower or "send" in lower:
        return "汇总故障输出"
    if "PACK" in upper:
        return "执行数据字打包"
    if "filt" in lower or "filter" in lower:
        return "执行数字滤波"
    if "trans" in lower or "convert" in lower:
        return "数值转换"
    if "init" in lower:
        return "初始化"
    if "update" in lower and "ifbit" in lower:
        return "更新周期自检状态"
    if any(token in lower for token in ("get", "read")):
        return "读取结果"
    if any(token in lower for token in ("calc", "cal", "pid", "fwd")):
        return "相关计算"
    if "check" in lower:
        return "状态检查"
    if "judge" in lower:
        return "条件判定"
    if "select" in lower:
        return "选择处理"
    if "set" in lower:
        return "设置处理"
    if "ctrl" in lower:
        return "控制处理"
    if any(token in lower for token in ("proc", "update", "logic", "state")):
        return "状态更新"
    return "相关处理"


__all__ = [name for name in globals() if not name.startswith("_")]
