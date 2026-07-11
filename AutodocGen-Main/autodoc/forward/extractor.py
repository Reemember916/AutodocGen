"""流程驱动：从 Markdown 需求文档反序列化为强类型语义中间层。

读取标准格式的 Markdown 需求文档，解析模块、函数、参数信息，
输出 ``HeaderFileIR`` / ``FunctionIR`` / ``ParameterIR`` 等
``autodoc.logic_ir`` 中定义的强类型对象。

兼容 Windows 7 / Python 3.8+，仅依赖标准库。
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..logic_ir import (
    CTypeInfo,
    ParameterIR,
    FunctionIR,
    MacroIR,
    HeaderFileIR,
)


# ── 正则表达式（预编译）─────────────────────────────────────────────

_MODULE_RE = re.compile(r"^##\s*模块:\s*(.+)$", re.MULTILINE)
_MODULE_DESC_RE = re.compile(r"^>\s*描述:\s*(.+)$", re.MULTILINE)

_FUNC_RE = re.compile(r"^###\s*函数:\s*([A-Za-z_]\w*)$", re.MULTILINE)
_FUNC_FIELD_RE = re.compile(r"^-\s*(中文名|描述|返回值)\s*:\s*(.+)$", re.MULTILINE)

_TABLE_HEADER_RE = re.compile(
    r"\|\s*参数名\s*\|\s*类型\s*\|\s*方向\s*\|\s*业务含义\s*\|"
)
_TABLE_SEP_RE = re.compile(r"^\|\s*-+\s*\|.*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(
    r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
)


# ── 类型解析 ────────────────────────────────────────────────────────


def _parse_type(raw: str) -> CTypeInfo:
    """将类型字符串（如 ``"uint16_t*"``）解析为 ``CTypeInfo``。

    处理 ``*``（指针）、``const``（常量）。"""
    text = raw.strip()
    is_const = False
    is_pointer = False

    # 去除 const 前缀
    if text.startswith("const "):
        is_const = True
        text = text[6:].strip()

    # 去除指针后缀
    if text.endswith("*"):
        is_pointer = True
        text = text[:-1].strip()

    return CTypeInfo(
        base_type=text.strip(),
        is_pointer=is_pointer,
        is_const=is_const,
    )


# ── 提取器 ──────────────────────────────────────────────────────────


class MarkdownExtractor:
    """Markdown 需求文档解析器。

    将标准格式的 Markdown 需求文档反序列化为 ``HeaderFileIR`` 对象。
    """

    def parse(self, md_content: str) -> HeaderFileIR:
        """解析 Markdown 内容，返回完整的 HeaderFileIR。

        参数
        ----
        md_content : str
            标准格式的 Markdown 需求文档全文

        返回
        ----
        HeaderFileIR
        """
        if not md_content:
            return HeaderFileIR()

        # ── 模块级信息 ──
        file_name = ""
        module_desc = ""

        m = _MODULE_RE.search(md_content)
        if m:
            file_name = m.group(1).strip()

        m = _MODULE_DESC_RE.search(md_content)
        if m:
            module_desc = m.group(1).strip()

        # ── 函数级解析 ──
        functions: List[FunctionIR] = []

        # 找到所有函数段落的起始位置
        func_matches = list(_FUNC_RE.finditer(md_content))
        for i, fm in enumerate(func_matches):
            func_name = fm.group(1).strip()
            func_start = fm.end()

            # 下一个函数段落开始处（或文末）
            if i + 1 < len(func_matches):
                func_end = func_matches[i + 1].start()
            else:
                func_end = len(md_content)

            func_section = md_content[func_start:func_end]
            func_ir = self._parse_function_section(func_name, func_section)
            if func_ir:
                functions.append(func_ir)

        return HeaderFileIR(
            file_name=file_name,
            brief_description=module_desc,
            macros=[],  # 宏定义暂不解析（后续扩展）
            functions=functions,
        )

    # ── 内部解析辅助 ──────────────────────────────────────────────

    def _parse_function_section(
        self,
        func_name: str,
        section: str,
    ) -> Optional[FunctionIR]:
        """解析单个函数段落。"""
        chinese_name = ""
        description = ""
        return_type = CTypeInfo(base_type="void")

        # 提取函数字段（中文名、描述、返回值）
        for m in _FUNC_FIELD_RE.finditer(section):
            key = m.group(1).strip()
            value = m.group(2).strip()
            if key == "中文名":
                chinese_name = value
            elif key == "描述":
                description = value
            elif key == "返回值":
                return_type = _parse_type(value)

        # 提取参数表
        parameters = self._parse_parameter_table(section)

        return FunctionIR(
            name=func_name,
            chinese_name=chinese_name,
            description=description,
            return_type=return_type,
            parameters=parameters,
        )

    def _parse_parameter_table(self, section: str) -> List[ParameterIR]:
        """从函数段落中提取参数表。

        定位 ``| 参数名 | 类型 | 方向 | 业务含义 |`` 表头，
        逐行解析后续表格行。
        """
        header_match = _TABLE_HEADER_RE.search(section)
        if not header_match:
            return []

        # 从表头位置开始，取后续内容
        after_header = section[header_match.end():]
        lines = after_header.splitlines()

        params: List[ParameterIR] = []
        in_table = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_table:
                    break  # 空行后停止
                continue

            # 跳过分隔行
            if _TABLE_SEP_RE.match(stripped):
                in_table = True
                continue

            if not in_table:
                continue

            # 不是表格行（不以 | 开头） → 表格结束
            if not stripped.startswith("|"):
                break

            row_match = _TABLE_ROW_RE.match(stripped)
            if not row_match:
                continue

            param_name = row_match.group(1).strip()
            param_type = row_match.group(2).strip()
            param_dir = row_match.group(3).strip().upper()
            param_meaning = row_match.group(4).strip()

            if not param_name:
                continue

            # 方向规范化
            if param_dir not in ("IN", "OUT", "INOUT"):
                param_dir = "IN"

            params.append(ParameterIR(
                name=param_name,
                type_info=_parse_type(param_type),
                direction=param_dir,
                business_meaning=param_meaning,
            ))

        return params