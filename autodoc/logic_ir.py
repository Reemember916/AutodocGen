"""系统唯一强类型语义中间层（Logic-IR）。

本模块定义了连接 C 源码分析与代码/文档生成的唯一语义基座。
所有上游（解析器、LSP、AI）输出必须转换为本模块的数据类；
所有下游（代码生成器、文档渲染器）仅消费本模块的数据类。

兼容 Windows 7 / Python 3.8+，使用 dataclasses 而非 Pydantic。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# ── 基础类型 ────────────────────────────────────────────────────────


@dataclass
class CTypeInfo:
    """C 语言类型信息。"""
    base_type: str = ""              # 如 "Uint16", "float", "void"
    is_pointer: bool = False
    is_const: bool = False


# ── 函数级 IR ───────────────────────────────────────────────────────


@dataclass
class ParameterIR:
    """函数参数语义描述。

    ``business_meaning`` 是防文档干瘪的核心字段——
    上游必须填入业务语义（如"燃油流量输入值"），不能仅留类型名。
    """
    name: str = ""
    type_info: CTypeInfo = field(default_factory=CTypeInfo)
    direction: str = "IN"            # IN / OUT / INOUT
    business_meaning: str = ""       # 业务语义（防文档干瘪）
    bit_fields: Dict[int, str] = field(default_factory=dict)  # 位域位号→中文名


@dataclass
class FunctionIR:
    """函数语义描述。"""
    name: str = ""
    chinese_name: str = ""
    description: str = ""
    return_type: CTypeInfo = field(default_factory=CTypeInfo)
    parameters: List[ParameterIR] = field(default_factory=list)
    user_code_block_id: str = ""     # 在生成的 .c 文件中锚定用户代码块


# ── 文件级 IR ───────────────────────────────────────────────────────


@dataclass
class MacroIR:
    """宏定义语义描述。"""
    name: str = ""
    value: str = ""
    description: str = ""


@dataclass
class HeaderFileIR:
    """C 头文件语义描述。"""
    file_name: str = ""
    brief_description: str = ""
    macros: List[MacroIR] = field(default_factory=list)
    functions: List[FunctionIR] = field(default_factory=list)

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


__all__ = [
    "CTypeInfo",
    "ParameterIR",
    "FunctionIR",
    "MacroIR",
    "HeaderFileIR",
]