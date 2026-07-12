"""Round-trip pipeline hub — connects the review panel signals to
physical file write-back operations.

Architecture::

    Resolver  ──→  ReviewPanel  ──→  PipelineHub  ──→  File I/O
                      │                    │
                      │  accept_doc_signal  │  _handle_write_back_c()
                      │  accept_code_signal │  _handle_write_back_md()
                      │  ignore_signal      │  _handle_ignore()
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Optional

# ── Universal Qt import ─────────────────────────────────────────────────
_QtWidgets = None
_QtCore = None

for _mod_name in ("PySide6", "PySide2", "PyQt5"):
    try:
        if _mod_name.startswith("PySide"):
            from importlib import import_module

            _QtCore = import_module(f"{_mod_name}.QtCore")
            _QtWidgets = import_module(f"{_mod_name}.QtWidgets")
        else:
            import PyQt5.QtCore as _QtCore  # type: ignore
            import PyQt5.QtWidgets as _QtWidgets  # type: ignore
        break
    except Exception:
        continue

if _QtWidgets is None:
    raise ImportError("No Qt bindings found. Install PySide6, PySide2, or PyQt5.")

QtCore = _QtCore
QtWidgets = _QtWidgets


# ── helpers ─────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [PipelineHub] {msg}")


def _force_process_events() -> None:
    """Force the Qt event loop to drain pending events, preventing GUI
    freeze during synchronous file I/O."""
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


# ── Pipeline hub ────────────────────────────────────────────────────────


class RoundTripPipelineHub:
    """Total-control hub that wires the review panel's signals to
    physical file write-back operations.

    Usage::

        hub = RoundTripPipelineHub(
            panel=review_panel,
            doc_path="path/to/design.md",
            code_path="path/to/source.h",
        )
        hub.connect_signals()
    """

    def __init__(
        self,
        panel,
        doc_path: str = "",
        code_path: str = "",
        ir_verdict: Optional[dict] = None,
    ) -> None:
        self.panel = panel
        self.doc_path = doc_path
        self.code_path = code_path
        self.ir_verdict = ir_verdict or {}

        self._pending_accept_doc: list = []
        self._pending_accept_code: list = []
        self._pending_ignored: list = []

    # ── signal wiring ───────────────────────────────────────────────

    def connect_signals(self) -> None:
        """Explicitly and hard-connect every panel signal to its
        physical write-back handler."""
        self.panel.accept_doc_signal.connect(self._handle_accept_doc)
        self.panel.accept_code_signal.connect(self._handle_accept_code)
        self.panel.ignore_signal.connect(self._handle_ignore)

        _log("信号已硬连接: accept_doc → _handle_accept_doc (正向→代码)")
        _log("信号已硬连接: accept_code → _handle_accept_code (反向→文档)")
        _log("信号已硬连接: ignore → _handle_ignore (跳过不处理)")

    # ── signal handlers (physical write-back) ───────────────────────

    def _handle_accept_doc(self, item_name: str) -> None:
        """User accepted doc-side change → forward sync to C code."""
        _log(f"收到签批: 接受文档更新 | 项: {item_name}")
        self._pending_accept_doc.append(item_name)

        # Locate the item in the verdict
        item_data = self._find_item(item_name)
        if item_data is None:
            _log(f"WARNING: 未在判决中找到项 '{item_name}'，跳过物理写回")
            return

        if self.code_path and os.path.exists(self.code_path):
            _force_process_events()
            _log(f"开始物理写回: 正向同步至代码文件 {self.code_path}")
            self._write_c_file(item_data)
            _force_process_events()
            _log(f"物理写回完成: {self.code_path}")
        else:
            _log(f"代码路径未设置或不存在，跳过写回: {self.code_path}")

    def _handle_accept_code(self, item_name: str) -> None:
        """User accepted code-side change → backward sync to MD doc."""
        _log(f"收到签批: 接受代码更新 | 项: {item_name}")
        self._pending_accept_code.append(item_name)

        item_data = self._find_item(item_name)
        if item_data is None:
            _log(f"WARNING: 未在判决中找到项 '{item_name}'，跳过物理写回")
            return

        if self.doc_path and os.path.exists(self.doc_path):
            _force_process_events()
            _log(f"开始物理写回: 反向同步至文档文件 {self.doc_path}")
            self._write_md_file(item_data)
            _force_process_events()
            _log(f"物理写回完成: {self.doc_path}")
        else:
            _log(f"文档路径未设置或不存在，跳过写回: {self.doc_path}")

    def _handle_ignore(self, item_name: str) -> None:
        """User chose to skip — no physical write-back."""
        _log(f"收到签批: 暂不处理 | 项: {item_name}")
        self._pending_ignored.append(item_name)
        _log(f"项 '{item_name}' 已暂存至忽略列表，未执行任何物理写回")

    # ── physical file I/O ───────────────────────────────────────────

    def _write_c_file(self, item_data: dict) -> None:
        """Write the doc-side IR data into the C source file.

        In a full implementation this would invoke the forward pipeline
        (generator.py + merger.py).  Here we append a log entry as a
        placeholder for the generated code skeleton.
        """
        if not self.code_path:
            return
        name = item_data.get("name", "unknown")
        kind = item_data.get("kind", "unknown")
        doc = item_data.get("doc", {})

        entry = (
            f"\n/* [PipelineHub] 正向同步: {kind} '{name}' "
            f"于 {time.strftime('%Y-%m-%d %H:%M:%S')} */\n"
        )
        _force_process_events()
        with open(self.code_path, "a", encoding="utf-8") as f:
            f.write(entry)
        _log(f"正向同步标记已写入代码文件: {name}")

    def _write_md_file(self, item_data: dict) -> None:
        """Write the code-side IR data into the Markdown document.

        In a full implementation this would invoke the backward pipeline
        (md_patcher.py).  Here we append a log entry as a placeholder.
        """
        if not self.doc_path:
            return
        name = item_data.get("name", "unknown")
        kind = item_data.get("kind", "unknown")
        code = item_data.get("code", {})

        entry = (
            f"\n<!-- [PipelineHub] 反向同步: {kind} '{name}' "
            f"于 {time.strftime('%Y-%m-%d %H:%M:%S')} -->\n"
        )
        _force_process_events()
        with open(self.doc_path, "a", encoding="utf-8") as f:
            f.write(entry)
        _log(f"反向同步标记已写入文档文件: {name}")

    # ── helpers ─────────────────────────────────────────────────────

    def _find_item(self, item_name: str) -> Optional[dict]:
        """Search all four verdict groups for an item by name."""
        for group_key in ("CONFLICTS", "FORWARD_CHANGES", "BACKWARD_CHANGES", "ALIGNED"):
            for item in self.ir_verdict.get(group_key, []):
                if item.get("name") == item_name:
                    return item
        return None

    def summary(self) -> str:
        return (
            f"PipelineHub: 待正向同步 {len(self._pending_accept_doc)} 项, "
            f"待反向同步 {len(self._pending_accept_code)} 项, "
            f"已忽略 {len(self._pending_ignored)} 项"
        )