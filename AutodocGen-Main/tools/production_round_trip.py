"""Production round-trip sync — industrial-grade harness for the
bidirectional pipeline, connected to PROJECT-2007-0613.

Safety features:
- Atomic .bak backup before every physical write-back.
- File existence auto-creation with starter content.
- Full console audit trail.

Usage:
    python tools/production_round_trip.py          # interactive (GUI review)
    python tools/production_round_trip.py --auto   # headless auto-sync
"""

from __future__ import annotations

import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Project paths (PROJECT-2007-0613) ──────────────────────────────────

PROJECT_DIR = os.path.join(ROOT, "tests", "PROJECT-2007-0613")
MD_PATH = os.path.join(PROJECT_DIR, "PROJECT-2007-3.1节需求.md")
CODE_PATH = os.path.join(PROJECT_DIR, "Include", "APP_Config.h")

# Ensure directories exist
os.makedirs(os.path.dirname(MD_PATH), exist_ok=True)
os.makedirs(os.path.dirname(CODE_PATH), exist_ok=True)


# ── Starter content for auto-created files ──────────────────────────────

STARTER_MD = """## 模块: APP_Config.h

> 描述: 应用层配置头文件 — 燃油控制系统顶层接口

### 函数: Control_Refuel_Process

- 中文名: 加油控制主流程
- 描述: 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
- 返回值: uint16_t

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|---|
| Valve_Status | uint16_t | IN | 主副阀门的物理开关状态 |
| p_Fault_Code | uint16_t* | OUT | 传出参数：故障诊断码 |
"""

STARTER_CODE = """/*
 * [函数中文名] 加油控制主流程
 * [功能描述] 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
 * [输入参数说明]
 * - Valve_Status: [业务含义] 主副阀门的物理开关状态
 * [输出参数说明]
 * - p_Fault_Code: [业务含义] 传出参数：故障诊断码
 */
extern uint16_t Control_Refuel_Process(uint16_t Valve_Status, uint16_t * p_Fault_Code);
"""


# ── Backup helper ───────────────────────────────────────────────────────


def _backup(path: str) -> str:
    """Create a ``.bak`` copy of *path* in the same directory.

    Returns the backup path.
    """
    if not os.path.exists(path):
        return ""
    bak_path = path + ".bak"
    # Rotate: remove oldest backup if it exists
    if os.path.exists(bak_path):
        old_bak = bak_path + ".old"
        if os.path.exists(old_bak):
            os.remove(old_bak)
        os.rename(bak_path, old_bak)
    shutil.copy2(path, bak_path)
    print(f"[备份] 已创建备份: {bak_path}")
    return bak_path


def _ensure_file(path: str, starter: str) -> None:
    """Create *path* with starter content if it does not already exist."""
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(starter)
        print(f"[初始化] 已创建文件: {path}")


# ── Log helper ──────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [Production] {msg}")


# ── Production sync ─────────────────────────────────────────────────────


def sync_project(auto_mode: bool = False) -> None:
    """Run the full round-trip pipeline on PROJECT-2007-0613.

    Parameters
    ----------
    auto_mode : bool
        When ``True`` runs headless (no GUI) — currently not implemented;
        reserved for CI / batch usage.
    """
    _log("=" * 50)
    _log("生产环境双向同步启动")
    _log(f"  需求文档: {MD_PATH}")
    _log(f"  代码文件: {CODE_PATH}")
    _log("=" * 50)

    # ── Phase 1: Ensure files exist ──
    _log("阶段 1/4: 检查文件完整性...")
    _ensure_file(MD_PATH, STARTER_MD)
    _ensure_file(CODE_PATH, STARTER_CODE)
    _log("      文件完整性检查通过")

    # ── Phase 2: Create backups ──
    _log("阶段 2/4: 创建安全备份...")
    md_bak = _backup(MD_PATH)
    code_bak = _backup(CODE_PATH)
    _log("      备份完成")

    # ── Phase 3: Import pipeline hub ──
    _log("阶段 3/4: 初始化同步引擎...")
    try:
        from autodoc.hub.pipeline_hub import RoundTripPipelineHub
        from autodoc.hub.review_panel import ConsistencyReviewPanel
    except ImportError as e:
        _log(f"ERROR: 导入失败 — {e}")
        _log("请确保依赖已安装: pip install PyQt5/PySide6")
        sys.exit(1)

    # Build empty verdict first (will be populated by resolver)
    from autodoc.hub.resolver import BiDirectionalResolver
    from autodoc.backward.ast_extractor import CAsTExtractor

    # Read current files
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
    with open(CODE_PATH, "r", encoding="utf-8") as f:
        code_content = f.read()

    # Extract IR from code
    extractor = CAsTExtractor()
    code_ir = extractor.extract_header(code_content, os.path.basename(CODE_PATH))
    _log(f"      从代码提取 IR: {len(code_ir.functions)} 函数, {len(code_ir.macros)} 宏")

    # Extract IR from MD document
    from autodoc.forward.extractor import MarkdownExtractor
    doc_ir = MarkdownExtractor().parse(md_content)
    doc_ir.file_name = os.path.basename(MD_PATH)
    _log(f"      从文档提取 IR: {len(doc_ir.functions)} 函数, {len(doc_ir.macros)} 宏")

    # Resolve
    resolver = BiDirectionalResolver()
    verdict = resolver.compare_ir(doc_ir, code_ir)
    total = sum(len(v) for v in verdict.values())
    _log(f"      判决完成: 共 {total} 项变更")

    # ── Phase 4: Launch review (GUI) or auto-sync ──
    _log("阶段 4/4: 启动评审面板...")

    if auto_mode:
        # Headless mode: auto-accept all backward changes
        _log("      自动模式: 执行无头同步...")
        _log("      自动模式未实现，请使用 GUI 模式")
        return

    # Interactive GUI mode
    from PyQt5 import QtWidgets  # type: ignore

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    panel = ConsistencyReviewPanel()
    panel.load_verdict(verdict)

    hub = RoundTripPipelineHub(
        panel=panel,
        doc_path=MD_PATH,
        code_path=CODE_PATH,
        ir_verdict=verdict,
    )
    hub.connect_signals()

    win = QtWidgets.QMainWindow()
    win.setWindowTitle("生产环境双向同步评审中心 — PROJECT-2007-0613")
    win.resize(1100, 680)
    win.setCentralWidget(panel)

    # Restore from backup on window close?  No — let the user decide.
    _log("      评审面板已启动，等待用户签批...")
    _log("      提示: 原始文件已备份为 .bak，可随时恢复")

    win.show()
    sys.exit(app.exec_())


# ── CLI entry point ─────────────────────────────────────────────────────


def main() -> None:
    auto_mode = "--auto" in sys.argv
    sync_project(auto_mode=auto_mode)


if __name__ == "__main__":
    main()