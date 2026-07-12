"""反向同步流水线总控脚本。

将 C 源码 → HeaderFileIR → 靶向更新 Markdown 需求文档参数表。

使用方式:
    python tools/run_backward_pipeline.py                           # 运行自测试 Demo
    python tools/run_backward_pipeline.py <c_path> <md_path>        # 生产模式
"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.backward.ast_extractor import CAsTExtractor
from autodoc.backward.md_patcher import MarkdownPatcher


# ── 日志 ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


# ── 主控 ────────────────────────────────────────────────────────────


def run_pipeline(c_path: str, md_path: str) -> str:
    """执行反向同步流水线。

    参数
    ----
    c_path : str
        C 头文件/源文件路径（含最新函数签名和注释）
    md_path : str
        原始 Markdown 需求文档路径（会被覆写）

    返回
    ----
    str
        更新后的 Markdown 完整文本
    """
    extractor = CAsTExtractor()
    patcher = MarkdownPatcher()

    # ── 第一步：Extract AST -> IR ──
    _log("第一步: 读取 C 源码并提取 AST IR...")
    with open(c_path, "r", encoding="utf-8") as f:
        c_code = f.read()
    file_name = os.path.basename(c_path)
    ir = extractor.extract_header(c_code, file_name)
    func_count = len(ir.functions)
    macro_count = len(ir.macros)
    _log(f"      成功提取 IR: {func_count} 个函数, {macro_count} 个宏")

    if func_count == 0:
        _log("      WARNING: 未提取到任何函数，跳过更新")
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    # ── 第二步：Read Old MD ──
    _log("第二步: 读取原始 Markdown 需求文档...")
    with open(md_path, "r", encoding="utf-8") as f:
        original_md = f.read()
    _log(f"      已读取: {len(original_md)} 字符")

    # ── 第三步：Patch MD ──
    _log("第三步: 靶向更新参数表...")
    patched_md = patcher.patch_header(original_md, ir)
    _log(f"      更新完成: {len(patched_md)} 字符")

    # ── 第四步：Save ──
    _log("第四步: 保存更新后的 Markdown...")
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(patched_md)
    _log(f"      已写入: {md_path}")
    _log("反向同步流水线完成!")

    return patched_md


# ── 自测试 Demo ─────────────────────────────────────────────────────


def _run_demo() -> None:
    """端到端自测试：动态生成旧 MD 和最新 C 代码，运行全流程并打印结果。"""
    print("=" * 60)
    print("  反向同步流水线 — 自测试 Demo")
    print("=" * 60)
    print()

    # 输出目录
    demo_out_dir = os.path.join(
        ROOT, "tests", "PROJECT-2007-0613", "Include", "Generated"
    )
    os.makedirs(demo_out_dir, exist_ok=True)
    md_path = os.path.join(demo_out_dir, "demo_design.md")
    c_path = os.path.join(demo_out_dir, "demo_code.h")

    # ── 动态生成旧版 Markdown 需求文档（仅 1 个参数）──
    _log("生成旧版 Markdown 需求文档...")
    old_md = """## 模块: Control_Module.h

> 描述: 控制模块接口头文件 — 飞行控制系统

### 函数: Control_Process

- 中文名: 控制处理流程
- 描述: 根据输入标志位执行控制逻辑，并通过指针参数输出结果
- 返回值: uint16_t

【人工备注】此处是工程师手写的业务背景说明：
本函数用于处理上层下发的控制指令，包含超时检测和异常上报逻辑。

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| flag | uint16_t | IN | 控制标志位（低 4 位为指令编码） |

【人工备注】表格结束后的补充说明：
p_out 指向的缓冲区必须由调用方预先分配，至少 4 字节。
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(old_md)
    _log(f"      已写入: {md_path}")

    # ── 动态生成工程师修改后的 C 代码（2 个参数，含军工规范注释）──
    _log("生成最新 C 头文件（含工程师新增参数和注释）...")
    new_c_code = """/*
 * Control_Module.h — 控制模块接口头文件
 */

/*
 * [函数中文名] 控制处理流程
 * [功能描述] 根据输入标志位执行控制逻辑，并通过指针参数输出结果
 * [输入参数说明]
 * - flag: [业务含义] 控制标志位（低 4 位为指令编码，高 4 位为优先级）
 * [输出参数说明]
 * - p_New_Fault: [业务含义] 新增故障码输出指针
 */
extern uint16_t Control_Process(uint16_t flag, uint16_t * p_New_Fault);
"""
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(new_c_code)
    _log(f"      已写入: {c_path}")

    print()

    # ── 运行流水线 ──
    run_pipeline(c_path, md_path)

    print()
    print("─" * 60)
    print("  更新后的 demo_design.md 内容:")
    print("─" * 60)
    with open(md_path, "r", encoding="utf-8") as f:
        print(f.read())
    print("─" * 60)
    print(f"  输出文件: {md_path}")
    print()

    _log("Demo 完成。")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        run_pipeline(sys.argv[1], sys.argv[2])
    else:
        _run_demo()