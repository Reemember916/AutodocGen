"""Round-trip pipeline hub — connects the review panel signals to
physical file write-back operations via the real forward/backward
pipelines.

Architecture::

    Resolver  ──→  ReviewPanel  ──→  PipelineHub  ──→  File I/O
                      │                    │
                      │  accept_doc_signal  │  _write_c_file()  ← forward pipeline
                      │  accept_code_signal │  _write_md_file() ← backward pipeline
                      │  ignore_signal      │  _handle_ignore()
"""

from __future__ import annotations

import json
import os
import shutil
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
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def _backup(path: str) -> str:
    if not os.path.exists(path):
        return ""
    bak_path = path + ".bak"
    if os.path.exists(bak_path):
        old_bak = bak_path + ".old"
        if os.path.exists(old_bak):
            os.remove(old_bak)
        os.rename(bak_path, old_bak)
    shutil.copy2(path, bak_path)
    _log(f"备份已创建: {bak_path}")
    return bak_path


# ── Pipeline hub ────────────────────────────────────────────────────────


class RoundTripPipelineHub:
    """Total-control hub that wires the review panel's signals to
    physical file write-back via the real forward/backward pipelines.

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
        self.panel.accept_doc_signal.connect(self._handle_accept_doc)
        self.panel.accept_code_signal.connect(self._handle_accept_code)
        self.panel.ignore_signal.connect(self._handle_ignore)

        _log("信号已硬连接: accept_doc → _handle_accept_doc (正向→代码)")
        _log("信号已硬连接: accept_code → _handle_accept_code (反向→文档)")
        _log("信号已硬连接: ignore → _handle_ignore (跳过不处理)")

    # ── signal handlers ─────────────────────────────────────────────

    def _handle_accept_doc(self, item_name: str) -> None:
        _log(f"收到签批: 接受文档更新 | 项: {item_name}")
        self._pending_accept_doc.append(item_name)
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
        _log(f"收到签批: 暂不处理 | 项: {item_name}")
        self._pending_ignored.append(item_name)
        _log(f"项 '{item_name}' 已暂存至忽略列表，未执行任何物理写回")

    # ── physical file I/O — backward pipeline (code → doc) ─────────

    def _write_md_file(self, item_data: dict) -> None:
        """Backward sync: re-extract code IR, patch the MD table in-place."""
        if not self.doc_path or not self.code_path:
            return
        name = item_data.get("name", "unknown")

        # 1. Backup
        _backup(self.doc_path)

        # 2. Extract IR from C code
        try:
            from autodoc.backward.ast_extractor import CAsTExtractor

            with open(self.code_path, "r", encoding="utf-8") as f:
                c_code = f.read()
            ir = CAsTExtractor().extract_header(
                c_code, os.path.basename(self.code_path)
            )
            _log(f"  AST 提取: {len(ir.functions)} 函数, {len(ir.macros)} 宏")
        except Exception as e:
            _log(f"  ERROR: AST 提取失败 — {e}")
            return

        # 3. Patch MD
        try:
            from autodoc.backward.md_patcher import MarkdownPatcher

            with open(self.doc_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            new_md = MarkdownPatcher().patch_header(md_content, ir)
            _log(
                f"  Markdown 靶向更新: {len(new_md)} 字符 "
                f"(原 {len(md_content)} 字符)"
            )
        except Exception as e:
            _log(f"  ERROR: Markdown 修补失败 — {e}")
            return

        # 4. Write back
        _force_process_events()
        with open(self.doc_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_md)
        _log(f"  反向同步完成: {name} 已注入 MD 文档")

    # ── physical file I/O — forward pipeline (doc → code) ──────────

    def _write_c_file(self, item_data: dict) -> None:
        """Forward sync: re-extract doc IR, generate C skeleton, merge
        user code blocks, write back."""
        if not self.doc_path or not self.code_path:
            return
        name = item_data.get("name", "unknown")

        # 1. Backup
        _backup(self.code_path)

        # 2. Extract IR from MD
        try:
            from autodoc.forward.extractor import MarkdownExtractor

            with open(self.doc_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            ir = MarkdownExtractor().parse(md_content)
            _log(
                f"  MD 提取: {len(ir.functions)} 函数, "
                f"{len(ir.macros)} 宏"
            )
        except Exception as e:
            _log(f"  ERROR: MD 提取失败 — {e}")
            return

        # 3. Generate C skeleton
        try:
            from autodoc.forward.generator import render_c_header

            skeleton = render_c_header(ir)
            _log(f"  C 骨架生成: {len(skeleton)} 字符")
        except Exception as e:
            _log(f"  ERROR: C 骨架生成失败 — {e}")
            return

        # 4. Merge user code blocks
        try:
            from autodoc.forward.merger import UserCodeMerger

            with open(self.code_path, "r", encoding="utf-8") as f:
                old_code = f.read()
            user_blocks = UserCodeMerger().extract(old_code)
            if user_blocks:
                _log(f"  提取到 {len(user_blocks)} 个用户保护区")
            merged = UserCodeMerger().merge(skeleton, user_blocks)
            _log(f"  合并完成: {len(merged)} 字符")
        except Exception as e:
            _log(f"  ERROR: 用户代码合并失败 — {e}")
            return

        # 5. Write back
        _force_process_events()
        with open(self.code_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(merged)
        _log(f"  正向同步完成: {name} 已注入 C 代码文件")

    # ── helpers ─────────────────────────────────────────────────────

    def _find_item(self, item_name: str) -> Optional[dict]:
        for group_key in (
            "CONFLICTS",
            "FORWARD_CHANGES",
            "BACKWARD_CHANGES",
            "ALIGNED",
        ):
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