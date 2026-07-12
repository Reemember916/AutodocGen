"""Review Hub — test launcher for ConsistencyReviewPanel.

Constructs a synthetic verdict dict (with TIMEOUT 500 vs 1000 conflict)
and opens the review panel for end-to-end visual inspection.

Usage:
    python tools/open_review_hub.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5 import QtCore, QtWidgets  # type: ignore

from autodoc.hub.review_panel import ConsistencyReviewPanel


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
                "return_type": {"base_type": "void", "is_pointer": False, "is_const": False},
                "parameters": [
                    {"name": "size", "type_info": {"base_type": "uint16_t", "is_pointer": False, "is_const": False}, "direction": "IN", "business_meaning": "缓冲区大小", "bit_fields": {}},
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
                "return_type": {"base_type": "uint16_t", "is_pointer": False, "is_const": False},
                "parameters": [
                    {"name": "data", "type_info": {"base_type": "uint8_t", "is_pointer": True, "is_const": True}, "direction": "IN", "business_meaning": "数据缓冲区", "bit_fields": {}},
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
                "return_type": {"base_type": "uint16_t", "is_pointer": False, "is_const": False},
                "parameters": [
                    {"name": "flag", "type_info": {"base_type": "uint16_t", "is_pointer": False, "is_const": False}, "direction": "IN", "business_meaning": "控制标志位", "bit_fields": {}},
                ],
                "user_code_block_id": "",
            },
            "code": {
                "name": "Control_Process",
                "chinese_name": "控制处理流程（代码侧更新）",
                "description": "code 侧处理逻辑",
                "return_type": {"base_type": "uint16_t", "is_pointer": False, "is_const": False},
                "parameters": [
                    {"name": "flag", "type_info": {"base_type": "uint16_t", "is_pointer": False, "is_const": False}, "direction": "IN", "business_meaning": "控制标志位", "bit_fields": {}},
                    {"name": "p_New_Fault", "type_info": {"base_type": "uint16_t", "is_pointer": True, "is_const": False}, "direction": "OUT", "business_meaning": "新增故障码", "bit_fields": {}},
                ],
                "user_code_block_id": "",
            },
        },
    ],
    "ALIGNED": [
        {
            "kind": "macro",
            "name": "MAX_RETRY",
            "doc": {
                "name": "MAX_RETRY",
                "value": "3",
                "description": "最大重试次数",
            },
            "code": {
                "name": "MAX_RETRY",
                "value": "3",
                "description": "最大重试次数",
            },
        },
    ],
}


def main() -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    app.setApplicationName("AutoDocGen Review Hub")

    win = QtWidgets.QMainWindow()
    win.setWindowTitle("双向同步评审中心 — Review Hub")
    win.resize(1000, 700)

    panel = ConsistencyReviewPanel()
    panel.load_verdict(SYNTHETIC_VERDICT)

    # Build summary line
    fwd = len(SYNTHETIC_VERDICT.get("FORWARD_CHANGES", []))
    bwd = len(SYNTHETIC_VERDICT.get("BACKWARD_CHANGES", []))
    cnf = len(SYNTHETIC_VERDICT.get("CONFLICTS", []))
    aln = len(SYNTHETIC_VERDICT.get("ALIGNED", []))
    panel.set_summary_text(
        f"正向 {fwd}  ·  反向 {bwd}  ·  ⚠冲突 {cnf}  ·  ✓已对齐 {aln}"
    )

    # Connect sign-off signals to console logging
    panel.approved.connect(lambda name, data: print(f"[流水线] 批准通过: {name}"))
    panel.rejected.connect(lambda name, data: print(f"[流水线] 驳回: {name}"))
    panel.skipped.connect(lambda name, data: print(f"[流水线] 跳过: {name}"))

    win.setCentralWidget(panel)
    win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()