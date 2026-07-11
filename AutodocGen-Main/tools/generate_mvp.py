"""MVP 测试渲染器：从 HeaderFileIR 生成 C 头文件。

消费 ``autodoc.forward.generator`` 中的 render_c_header 实现。
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.forward.generator import render_c_header
from autodoc.logic_ir import (
    CTypeInfo,
    ParameterIR,
    FunctionIR,
    MacroIR,
    HeaderFileIR,
)


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