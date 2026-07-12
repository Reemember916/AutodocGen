"""Review Hub — test launcher for ConsistencyReviewPanel + RoundTripPipelineHub.

Constructs a synthetic verdict dict (TIMEOUT 500 vs 1000 conflict,
forward/backward deltas) and opens the review panel wired to the
pipeline hub for physical file write-back.

Usage:
    python tools/open_review_hub.py
"""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.hub.review_panel import ConsistencyReviewPanel
from autodoc.hub.pipeline_hub import RoundTripPipelineHub

# Universal Qt import
_QtWidgets = None
for _mod in ("PySide6.QtWidgets", "PySide2.QtWidgets", "PyQt5.QtWidgets"):
    try:
        from importlib import import_module

        _QtWidgets = import_module(_mod)
        break
    except Exception:
        continue

if _QtWidgets is None:
    raise ImportError("No Qt bindings found. Install PySide6, PySide2, or PyQt5.")


# ── synthetic verdict ───────────────────────────────────────────────────

SYNTHETIC_VERDICT = {
    "FORWARD_CHANGES": [
        {
            "kind": "macro",
            "name": "BUF_SIZE",
            "doc": {
                "name": "BUF_SIZE",
                "value": "256",
                "description": "缓冲区大小",
            },
            "code": None,
        },
        {
            "kind": "function",
            "name": "init_buffer",
            "doc": {
                "name": "init_buffer",
                "chinese_name": "初始化缓冲区",
                "description": "分配并初始化环形缓冲区",
                "return_type": {
                    "base_type": "void",
                    "is_pointer": False,
                    "is_const": False,
                },
                "parameters": [
                    {
                        "name": "size",
                        "type_info": {
                            "base_type": "uint16_t",
                            "is_pointer": False,
                            "is_const": False,
                        },
                        "direction": "IN",
                        "business_meaning": "缓冲区大小",
                        "bit_fields": {},
                    }
                ],
                "user_code_block_id": "",
            },
            "code": None,
        },
    ],
    "BACKWARD_CHANGES": [
        {
            "kind": "macro",
            "name": "BAUD_RATE",
            "doc": None,
            "code": {
                "name": "BAUD_RATE",
                "value": "115200",
                "description": "串口波特率",
            },
        },
        {
            "kind": "function",
            "name": "send_frame",
            "doc": None,
            "code": {
                "name": "send_frame",
                "chinese_name": "发送数据帧",
                "description": "通过 RS422 发送一帧数据",
                "return_type": {
                    "base_type": "uint16_t",
                    "is_pointer": False,
                    "is_const": False,
                },
                "parameters": [
                    {
                        "name": "data",
                        "type_info": {
                            "base_type": "uint8_t",
                            "is_pointer": True,
                            "is_const": True,
                        },
                        "direction": "IN",
                        "business_meaning": "数据缓冲区",
                        "bit_fields": {},
                    }
                ],
                "user_code_block_id": "",
            },
        },
    ],
    "CONFLICTS": [
        {
            "kind": "macro",
            "name": "TIMEOUT",
            "doc": {
                "name": "TIMEOUT",
                "value": "500",
                "description": "超时阈值",
            },
            "code": {
                "name": "TIMEOUT",
                "value": "1000",
                "description": "超时阈值",
            },
        },
        {
            "kind": "function",
            "name": "Control_Process",
            "doc": {
                "name": "Control_Process",
                "chinese_name": "控制处理流程",
                "description": "doc 侧处理逻辑",
                "return_type": {
                    "base_type": "uint16_t",
                    "is_pointer": False,
                    "is_const": False,
                },
                "parameters": [
                    {
                        "name": "flag",
                        "type_info": {
                            "base_type": "uint16_t",
                            "is_pointer": False,
                            "is_const": False,
                        },
                        "direction": "IN",
                        "business_meaning": "控制标志位",
                        "bit_fields": {},
                    }
                ],
                "user_code_block_id": "",
            },
            "code": {
                "name": "Control_Process",
                "chinese_name": "控制处理流程（代码侧更新）",
                "description": "code 侧处理逻辑",
                "return_type": {
                    "base_type": "uint16_t",
                    "is_pointer": False,
                    "is_const": False,
                },
                "parameters": [
                    {
                        "name": "flag",
                        "type_info": {
                            "base_type": "uint16_t",
                            "is_pointer": False,
                            "is_const": False,
                        },
                        "direction": "IN",
                        "business_meaning": "控制标志位",
                        "bit_fields": {},
                    },
                    {
                        "name": "p_New_Fault",
                        "type_info": {
                            "base_type": "uint16_t",
                            "is_pointer": True,
                            "is_const": False,
                        },
                        "direction": "OUT",
                        "business_meaning": "新增故障码",
                        "bit_fields": {},
                    },
                ],
                "user_code_block_id": "",
            },
        },
    ],
}


def main() -> None:
    app = _QtWidgets.QApplication.instance()
    if app is None:
        app = _QtWidgets.QApplication(sys.argv)

    app.setApplicationName("AutoDocGen Review Hub")

    # ── Create temp files for physical write-back verification ──
    tmp_dir = tempfile.mkdtemp(prefix="autodoc_review_hub_")
    doc_path = os.path.join(tmp_dir, "demo_design.md")
    code_path = os.path.join(tmp_dir, "demo_code.h")

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("# 原始设计文档\n\n待同步...\n")
    with open(code_path, "w", encoding="utf-8") as f:
        f.write("/* 原始代码文件 */\n\n// 待同步...\n")

    print(f"[启动] 临时文件目录: {tmp_dir}")
    print(f"[启动] doc_path: {doc_path}")
    print(f"[启动] code_path: {code_path}")
    print()

    # ── Build panel + hub ──
    panel = ConsistencyReviewPanel()
    panel.load_verdict(SYNTHETIC_VERDICT)

    hub = RoundTripPipelineHub(
        panel=panel,
        doc_path=doc_path,
        code_path=code_path,
        ir_verdict=SYNTHETIC_VERDICT,
    )
    hub.connect_signals()

    win = _QtWidgets.QMainWindow()
    win.setWindowTitle("双向同步评审中心 — MVP-11 总控大合拢")
    win.resize(1100, 680)
    win.setCentralWidget(panel)
    win.show()

    print("[启动] 评审面板已显示，点击签批按钮将触发物理文件写回")
    print(f"[启动] 验证: 签批后检查 {tmp_dir} 下的文件内容")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()