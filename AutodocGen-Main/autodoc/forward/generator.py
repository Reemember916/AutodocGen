"""C 头文件代码生成器：从 HeaderFileIR 渲染 C 代码。

消费 ``autodoc.logic_ir`` 中定义的强类型语义中间层，
输出符合 GJB 注释规范的 C 头文件（含严格四行注释头）。
"""

from __future__ import annotations

from typing import List

from ..logic_ir import (
    CTypeInfo,
    ParameterIR,
    FunctionIR,
    MacroIR,
    HeaderFileIR,
)


def _type_to_c(type_info: CTypeInfo) -> str:
    """将 CTypeInfo 渲染为 C 类型声明文本。"""
    parts = []
    if type_info.is_const:
        parts.append("const ")
    parts.append(type_info.base_type)
    if type_info.is_pointer:
        parts.append(" *")
    return "".join(parts)


def _guard_macro(file_name: str) -> str:
    """生成防卫宏名称。"""
    cleaned = file_name.replace(".", "_").upper()
    return f"_{cleaned}_"


def render_c_header(ir: HeaderFileIR) -> str:
    """从 HeaderFileIR 渲染完整的 C 头文件字符串。

    渲染顺序：
    1. 防卫宏（#ifndef / #define）
    2. 宏定义
    3. 函数声明（带严格四行注释头）
    4. 防卫宏闭合（#endif）
    """
    lines: List[str] = []
    guard = _guard_macro(ir.file_name)

    # ── 防卫宏 ──
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")

    # ── 文件头注释 ──
    if ir.brief_description:
        for desc_line in ir.brief_description.strip().splitlines():
            lines.append(f"/* {desc_line.strip()} */")
        lines.append("")

    # ── 宏定义 ──
    if ir.macros:
        for macro in ir.macros:
            if macro.description:
                lines.append(f"/* {macro.description} */")
            lines.append(f"#define {macro.name} {macro.value}")
        lines.append("")

    # ── 函数声明 ──
    for func in ir.functions:
        lines.append("/*")
        lines.append(f" * [函数中文名] {func.chinese_name}")

        desc = func.description.strip() if func.description else "（待补充）"
        lines.append(f" * [功能描述] {desc}")

        # 输入参数说明
        in_params = [p for p in func.parameters if p.direction in ("IN", "INOUT")]
        if in_params:
            in_desc_parts = []
            for p in in_params:
                if p.business_meaning:
                    in_desc_parts.append(f"{p.name}: [业务含义] {p.business_meaning}")
                else:
                    in_desc_parts.append(f"{p.name}: [类型] {p.type_info.base_type}")
            lines.append(f" * [输入参数说明] {'; '.join(in_desc_parts)}")
        else:
            lines.append(" * [输入参数说明] 无")

        # 输出参数说明
        out_params = [p for p in func.parameters if p.direction in ("OUT", "INOUT")]
        if out_params:
            out_desc_parts = []
            for p in out_params:
                if p.business_meaning:
                    out_desc_parts.append(f"{p.name}: [业务含义] {p.business_meaning}")
                else:
                    out_desc_parts.append(f"{p.name}: [类型] {p.type_info.base_type}")
            lines.append(f" * [输出参数说明] {'; '.join(out_desc_parts)}")
        else:
            lines.append(" * [输出参数说明] 无")

        lines.append(" */")

        # 函数签名
        ret_type = _type_to_c(func.return_type)
        param_parts = []
        for p in func.parameters:
            p_type = _type_to_c(p.type_info)
            param_parts.append(f"{p_type} {p.name}")
        params_str = ", ".join(param_parts)
        signature = f"extern {ret_type} {func.name}({params_str});"
        lines.append(signature)
        lines.append("")

        # 保护区标签——工程师可在此标签后手写内联函数或辅助宏
        lines.append(f"/* USER CODE BEGIN: {func.name} */")
        lines.append(f"/* USER CODE END: {func.name} */")
        lines.append("")

    # ── 防卫宏闭合 ──
    lines.append(f"#endif /* {guard} */")
    lines.append("")

    return "\n".join(lines)


__all__ = ["render_c_header"]