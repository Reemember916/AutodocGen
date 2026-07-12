"""Review Hub — test launcher for ConsistencyReviewPanel.

Constructs a synthetic verdict dict (TIMEOUT 500 vs 1000 conflict,
forward/backward deltas) and opens the review panel for end-to-end
visual inspection.

Usage:
    python tools/open_review_hub.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from autodoc.hub.review_panel import ConsistencyReviewPanel

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

    win = _QtWidgets.QMainWindow()
    win.resize(1100, 680)

    panel = ConsistencyReviewPanel()
    panel.load_verdict(SYNTHETIC_VERDICT)

    # Connect sign-off signals to console logging
    panel.accept_doc.connect(
        lambda name, data: print(f"[流水线] 批准文档更新 → 正向同步: {name}")
    )
    panel.accept_code.connect(
        lambda name, data: print(f"[流水线] 批准代码更新 → 反向同步: {name}")
    )
    panel.ignored.connect(
        lambda name, data: print(f"[流水线] 已忽略: {name}")
    )

    win.setCentralWidget(panel)
    win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()