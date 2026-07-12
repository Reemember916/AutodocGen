"""正向生成流水线总控脚本。

将 Markdown 需求文档 → HeaderFileIR → C 代码骨架 → 保护区无损合并 → 最终 C 文件。

使用方式:
    python tools/run_forward_pipeline.py                           # 运行自测试 Demo
    python tools/run_forward_pipeline.py <md_path> <target_c_path> # 生产模式
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.forward.extractor import MarkdownExtractor
from autodoc.forward.merger import UserCodeMerger
from autodoc.forward.generator import render_c_header


# ── 日志 ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


# ── 主控 ────────────────────────────────────────────────────────────


def run_pipeline(md_path: str, target_c_path: str) -> None:
    """执行正向生成流水线。

    参数
    ----
    md_path : str
        Markdown 需求文档路径
    target_c_path : str
        目标 C 头文件路径（存在则无损合并，不存在则全新生成）
    """
    extractor = MarkdownExtractor()
    merger = UserCodeMerger()

    # ── 第一步：Extract IR ──
    _log("第一步: 读取 Markdown 需求文档...")
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    header_ir = extractor.parse(md_content)
    func_count = len(header_ir.functions)
    _log(f"      成功提取需求 IR: {header_ir.file_name}, {func_count} 个函数")

    # ── 第二步：Read Old Code ──
    _log("第二步: 读取旧版本代码...")
    old_code = ""
    if os.path.exists(target_c_path):
        with open(target_c_path, "r", encoding="utf-8") as f:
            old_code = f.read()
        _log(f"      已读取旧代码: {len(old_code)} 字符")
    else:
        _log("      目标文件不存在，视为全新生成")

    # ── 第三步：Extract User Blocks ──
    _log("第三步: 提取用户手写保护区...")
    user_blocks = merger.extract(old_code)
    if user_blocks:
        _log(f"      提取到 {len(user_blocks)} 个用户代码块: {list(user_blocks.keys())}")
    else:
        _log("      未发现用户代码块（全新生成或旧代码无保护区）")

    # ── 第四步：Render Skeleton ──
    _log("第四步: 从 IR 渲染代码骨架...")
    skeleton = render_c_header(header_ir)
    _log(f"      骨架生成完成: {len(skeleton)} 字符")

    # ── 第五步：Merge ──
    _log("第五步: 保护区无损合并...")
    merged = merger.merge(skeleton, user_blocks)
    _log(f"      合并完成: {len(merged)} 字符")

    # ── 第六步：Save ──
    _log("第六步: 保存最终代码...")
    target_dir = os.path.dirname(target_c_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    with open(target_c_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(merged)
    _log(f"      已写入: {target_c_path}")
    _log("流水线完成!")


# ── 自测试 Demo ─────────────────────────────────────────────────────


def _run_demo() -> None:
    """端到端自测试：动态生成 Markdown 和旧代码，运行全流程并打印结果。"""
    print("=" * 60)
    print("  正向生成流水线 — 自测试 Demo")
    print("=" * 60)
    print()

    # 输出目录：自动在项目根创建 Generated/
    demo_out_dir = os.path.join(ROOT, "Generated")
    os.makedirs(demo_out_dir, exist_ok=True)
    md_path = os.path.join(demo_out_dir, "demo_requirement.md")
    h_path = os.path.join(demo_out_dir, "APP_Config.h")

    # ── 动态生成 Markdown 需求文档 ──
    _log("生成测试 Markdown 需求文档...")
    md_content = """## 模块: APP_Config.h

> 描述: 应用层配置头文件 — 燃油控制系统顶层接口

### 函数: Control_Refuel_Process

- 中文名: 加油控制主流程
- 描述: 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
- 返回值: uint16_t

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| Valve_Status | uint16_t | IN | 主副阀门的物理开关状态 |
| p_Fault_Code | uint16_t* | OUT | 传出参数：故障诊断码 |
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    _log(f"      已写入: {md_path}")

    # ── 动态生成旧版 C 代码（含手写保护区）──
    _log("生成测试旧版 C 代码...")
    old_c_code = """#ifndef _APP_CONFIG_H_
#define _APP_CONFIG_H_

/* 应用层配置头文件 — 燃油控制系统顶层接口 */

/*
 * [函数中文名] 加油控制主流程
 * [功能描述] 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
 * [输入参数说明] Valve_Status: 主副阀门的物理开关状态
 * [输出参数说明] p_Fault_Code: 传出参数：故障诊断码
 */
extern uint16_t Control_Refuel_Process(uint16_t Valve_Status, uint16_t * p_Fault_Code);

/* USER CODE BEGIN: Control_Refuel_Process */
// 旧的死区算法: return 0;
static uint16_t OLD_DEAD_ZONE(uint16_t input) {
    if (input < 10) return 0;
    return input;
}
/* USER CODE END: Control_Refuel_Process */

#endif /* _APP_CONFIG_H_ */
"""
    with open(h_path, "w", encoding="utf-8") as f:
        f.write(old_c_code)
    _log(f"      已写入旧版代码: {h_path}")

    print()

    # ── 运行流水线 ──
    run_pipeline(md_path, h_path)

    print()
    print("─" * 60)
    print(f"  最终生成的 {os.path.basename(h_path)} 内容:")
    print("─" * 60)
    with open(h_path, "r", encoding="utf-8") as f:
        print(f.read())
    print("─" * 60)
    print(f"  输出文件: {h_path}")
    print()

    _log("Demo 完成。")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        run_pipeline(sys.argv[1], sys.argv[2])
    else:
        _run_demo()