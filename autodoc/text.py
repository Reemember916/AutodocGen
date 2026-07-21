"""C source text processing helpers — line joining, CJK detection, ident splitting, body trimming."""

from __future__ import annotations

import re
from typing import Optional


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TYPE_SUFFIX_RE = re.compile(r"[_](u8|u16|u32|u64|i8|i16|i32|i64)$", re.IGNORECASE)
_IDENT_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_IDENT_SKIP_TOKENS = frozenset({
    "u8", "u16", "u32", "u64",
    "i8", "i16", "i32", "i64",
    "l", "g", "s", "v",
    "ls", "gs", "ss", "vs", "ps", "vp", "gp", "lp", "sp", "cp", "tp",
})


def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _split_ident_tokens(name: str) -> list[str]:
    raw = str(name or "")
    raw = _TYPE_SUFFIX_RE.sub("", raw)
    parts = re.split(r"[_\W]+", raw)
    tokens = []
    for part in parts:
        if not part:
            continue
        tokens.extend(_IDENT_TOKEN_RE.findall(part))
    return [t for t in tokens if t and t.lower() not in _IDENT_SKIP_TOKENS]


def trim_body(body: str, max_lines: int = 300) -> str:
    lines = body.splitlines()
    if len(lines) <= max_lines:
        return body
    head = "\n".join(lines[:max_lines // 2])
    tail = "\n".join(lines[-max_lines // 2:])
    return head + "\n/* ... 省略 ... */\n" + tail


_IDENT_CN_MAP = {
    "init": "初始化",
    "deinit": "反初始化",
    "reset": "复位",
    "start": "启动",
    "stop": "停止",
    "enable": "使能",
    "disable": "禁用",
    "open": "打开",
    "close": "关闭",
    "select": "选择",
    "get": "获取",
    "set": "设置",
    "read": "读取",
    "write": "写入",
    "erase": "擦除",
    "clear": "清除",
    "update": "更新",
    "check": "检查",
    "calc": "计算",
    "compute": "计算",
    "sum": "求和",
    "avg": "平均",
    "result": "结果",
    "status": "状态",
    "state": "状态",
    "flag": "标志",
    "type": "类型",
    "evt": "事件",
    "cmd": "指令",
    "ctrl": "控制",
    "control": "控制",
    "parameter": "参数",
    "parameters": "参数",
    "data": "数据",
    "len": "长度",
    "length": "长度",
    "max": "最大",
    "min": "最小",
    "empty": "空",
    "first": "起始",
    "last": "结束",
    "valid": "有效",
    "invalid": "无效",
    "bit": "位",
    "sector": "扇区",
    "info": "信息",
    "config": "配置",
    "cfg": "配置",
    "param": "参数",
    "req": "请求",
    "resp": "响应",
    "msg": "消息",
    "fault": "故障",
    "err": "故障",
    "logic": "逻辑",
    "active": "活动",
    "source": "来源",
    "filter": "滤波",
    "flt": "故障",
    "time": "时间",
    "tick": "节拍",
    "temp": "临时",
    "sen": "传感器",
    "count": "计数",
    "cnt": "计数",
    "idx": "索引",
    "rst": "复位",
    "frce": "强制",
    "force": "强制",
    "new": "新",
    "en": "使能",
    "vld": "有效",
    "sta": "状态",
    "mon": "监测",
    "prd": "周期",
    "delay": "延时",
    "real": "实际",
    "wow": "WOW",
    "rdy": "就绪",
    "task": "任务",
    "timer": "定时器",
    "cpu": "CPU",
    "dsp": "DSP",
    "fpga": "FPGA",
    "tx": "发送",
    "rx": "接收",
    "ssm": "SSM",
    "riu": "RIU",
    "gpio": "GPIO",
    "port": "端口",
    "ccdl": "CCDL",
    "kzzz": "KZZZ",
    "nvm": "NVM",
    "lru": "LRU",
    "vmc": "VMC",
    "svpc": "SVPC",
    "vpc": "VPC",
    "pack": "打包",
    "num": "数量",
    "results": "结果",
    "val": "值",
    "ii": "循环索引",
    "jj": "循环索引",
    "kk": "循环索引",
    "ok": "正常",
    "left": "左",
    "right": "右",
    "peer": "对端",
    "pass": "通过",
    "buff": "缓冲",
    "heart": "心跳",
    "key": "关键字",
    "remain": "剩余",
    "addr": "地址",
    "changed": "变化",
    "download": "下载",
    "para": "参数",
    "maint": "维护",
    "id": "标识",
    "func": "功能",
    "pre": "前值",
    "lo": "下",
    "hi": "上",
    "is": "",
    "h": "高",
    "cur": "电流",
    "vel": "速度",
    "limt": "限值",
    "lmt": "限值",
    "power": "功率",
    "duty": "占空比",
    "brk": "制动",
    "comb": "组合",
    "lck": "锁存",
    "phy": "物理",
    "ureg": "寄存器",
    "flash": "闪存",
    "mem": "内存",
    "buffer": "缓冲",
    "crc": "CRC",
    "pll": "PLL",
    "divide": "分频",
    "mulmax": "倍频最大值",
}


def _guess_cn_from_ident(name: str, glossary: Optional[dict[str, str]] = None) -> str:
    from . import naming as naming_utils
    from ._legacy_support import legacy_backend

    backend = legacy_backend()
    return naming_utils.guess_cn_from_ident(
        name,
        glossary=glossary,
        symbol_lookup=backend._lookup_symbol_dictionary,
        ident_cn_map=_IDENT_CN_MAP,
    )


__all__ = ["_contains_cjk", "_split_ident_tokens", "trim_body", "_IDENT_CN_MAP", "_guess_cn_from_ident"]
