"""MVP 测试渲染器：从 HeaderFileIR 生成 C 头文件。

消费 ``autodoc.logic_ir`` 中定义的强类型语义中间层，
输出符合 GJB 注释规范的 C 头文件。
"""

from __future__ import annotations

import os
import sys
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.logic_ir import (
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
        # 严格四行注释头
        lines.append("/*")
        lines.append(f" * [函数中文名] {func.chinese_name}")

        # 功能描述
        desc = func.description.strip() if func.description else "（待补充）"
        lines.append(f" * [功能描述] {desc}")

        # 输入参数说明
        in_params = [p for p in func.parameters if p.direction in ("IN", "INOUT")]
        if in_params:
            in_desc_parts = []
            for p in in_params:
                meaning = p.business_meaning or f"（{p.name} 的业务含义待补充）"
                in_desc_parts.append(f"{p.name}: {meaning}")
            lines.append(f" * [输入参数说明] {'; '.join(in_desc_parts)}")
        else:
            lines.append(" * [输入参数说明] 无")

        # 输出参数说明
        out_params = [p for p in func.parameters if p.direction in ("OUT", "INOUT")]
        if out_params:
            out_desc_parts = []
            for p in out_params:
                meaning = p.business_meaning or f"（{p.name} 的业务含义待补充）"
                out_desc_parts.append(f"{p.name}: {meaning}")
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

    # ── 防卫宏闭合 ──
    lines.append(f"#endif /* {guard} */")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # ── 实例化 HeaderFileIR ──
    header_ir = HeaderFileIR(
        file_name="APP_Config.h",
        brief_description="应用层配置头文件 — 燃油控制系统顶层接口",
        macros=[
            MacroIR(
                name="FUEL_PUMP_CHANNEL_COUNT",
                value="4",
                description="燃油泵通道数",
            ),
            MacroIR(
                name="REFUEL_TIMEOUT_MS",
                value="30000",
                description="加油超时时间（毫秒）",
            ),
        ],
        functions=[
            FunctionIR(
                name="Control_Refuel_Process",
                chinese_name="加油控制主流程",
                description=(
                    "根据加油指令启动或停止加油泵，监控油量变化率，"
                    "超时或异常时自动切断燃油供给并上报故障码。"
                ),
                return_type=CTypeInfo(base_type="Uint16"),
                parameters=[
                    ParameterIR(
                        name="u16_refuel_cmd",
                        type_info=CTypeInfo(base_type="Uint16"),
                        direction="IN",
                        business_meaning="加油指令字（0x01=启动加油，0x00=停止加油）",
                    ),
                    ParameterIR(
                        name="u16_current_fuel_qty",
                        type_info=CTypeInfo(base_type="Uint16"),
                        direction="IN",
                        business_meaning="当前燃油量（kg）",
                    ),
                    ParameterIR(
                        name="u16_target_fuel_qty",
                        type_info=CTypeInfo(base_type="Uint16"),
                        direction="IN",
                        business_meaning="目标加油量（kg）",
                    ),
                    ParameterIR(
                        name="p_error_code",
                        type_info=CTypeInfo(base_type="Uint16", is_pointer=True),
                        direction="OUT",
                        business_meaning="故障码输出指针（0=正常，非0=故障编码）",
                    ),
                ],
            ),
        ],
    )

    # ── 渲染并打印 ──
    rendered = render_c_header(header_ir)
    print(rendered)

    # ── 写入文件 ──
    output_dir = os.path.join(
        ROOT, "tests", "PROJECT-2007-0613", "Include", "Generated"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "APP_Config.h")
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(rendered)
    print(f"\n[generate_mvp] 已写入: {output_path}")