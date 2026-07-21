"""Visual review panel — ConsistencyReviewPanel.

Three-zone layout:
1. [LEFT]  Change-list tree (QTreeWidget) — Conflicts / Forward / Backward.
2. [MIDDLE] Dual-pane diff (QTextEdit × 2) — doc-side vs code-side.
3. [RIGHT]  Sign-off controls (QPushButton) — accept doc / accept code / ignore.

Every sign-off button emits a typed Signal + prints a [DEBUG] line so
the pipeline hub can pick it up and perform physical file I/O.

Compatible with Windows 7, PySide2, PySide6, and PyQt5.
"""

from __future__ import annotations

import json
from typing import Any, Optional

# ── Universal Qt import (PySide2 / PySide6 / PyQt5) ──────────────────
_QT_CLASSES: Any = None
_QT_SIGNAL: Any = None

for _mod_name in ("PySide6", "PySide2", "PyQt5"):
    try:
        if _mod_name.startswith("PySide"):
            from importlib import import_module

            _qtc = import_module(f"{_mod_name}.QtCore")
            _qtw = import_module(f"{_mod_name}.QtWidgets")
            _qtg = import_module(f"{_mod_name}.QtGui")
            _QT_SIGNAL = _qtc.Signal
        else:
            import PyQt5.QtCore as _qtc  # type: ignore
            import PyQt5.QtGui as _qtg  # type: ignore
            import PyQt5.QtWidgets as _qtw  # type: ignore
            _QT_SIGNAL = _qtc.pyqtSignal

        _QT_CLASSES = (_qtc, _qtg, _qtw)
        break
    except Exception:
        continue

if _QT_CLASSES is None:
    raise ImportError(
        "No Qt bindings found. Install PySide6, PySide2, or PyQt5."
    )

QtCore, QtGui, QtWidgets = _QT_CLASSES

# Alias Signal to the binding-appropriate class
Signal = _QT_SIGNAL


# ── colour constants ────────────────────────────────────────────────────

_GROUP_LABELS = {
    "CONFLICTS":    "🔴 语义冲突 (Conflicts)",
    "FORWARD_CHANGES":  "🔵 正向变更 (Forward)",
    "BACKWARD_CHANGES": "🟢 逆向变更 (Backward)",
}


class ConsistencyReviewPanel(QtWidgets.QWidget):
    """Visual review and sign-off panel for bidirectional IR diffs.

    Signals (connect these in the pipeline hub for physical I/O):
      accept_doc_signal(str)   — user chose "accept doc-side change"
      accept_code_signal(str)  — user chose "accept code-side change"
      ignore_signal(str)       — user chose "skip / ignore"
    """

    # ── typed signals (pipeline hub connects to these) ──────────────
    accept_doc_signal = Signal(str)    # emits item name
    accept_code_signal = Signal(str)   # emits item name
    ignore_signal = Signal(str)        # emits item name

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._current_item: Optional[dict] = None
        self._setup_ui()

    # ── public API ──────────────────────────────────────────────────

    def load_verdict(self, verdict_dict: dict) -> None:
        """Load a verdict from ``BiDirectionalResolver.compare_ir()``.

        Populates the change tree with three top-level groups:
        CONFLICTS, FORWARD_CHANGES, BACKWARD_CHANGES.
        """
        self._verdict = verdict_dict
        self._tree.clear()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["变更项", "来源"])

        group_keys = ["CONFLICTS", "FORWARD_CHANGES", "BACKWARD_CHANGES"]

        for key in group_keys:
            items = verdict_dict.get(key, [])
            label = _GROUP_LABELS.get(key, key)
            root = QtWidgets.QTreeWidgetItem([f"{label}  ({len(items)})", ""])
            root.setData(0, QtCore.Qt.UserRole, {"_group_key": key})
            for item in items:
                child = QtWidgets.QTreeWidgetItem(
                    [f"{item.get('kind', '?')}: {item.get('name', '?')}", key]
                )
                child.setData(0, QtCore.Qt.UserRole, item)
                root.addChild(child)
            self._tree.addTopLevelItem(root)
            root.setExpanded(True)

        self._update_summary(verdict_dict)

    # ── UI construction ─────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # ── Root layout: horizontal splitter ──
        root_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)
        root_layout.addWidget(root_splitter, 1)

        # ── [LEFT] Change-list tree ──
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_header = QtWidgets.QLabel("变更清单")
        left_header.setStyleSheet("font-weight: 700; font-size: 13px;")
        left_layout.addWidget(left_header)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        left_layout.addWidget(self._tree, 1)

        root_splitter.addWidget(left_panel)

        # ── [MIDDLE] Dual-pane diff ──
        middle_panel = QtWidgets.QWidget()
        middle_layout = QtWidgets.QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(4)

        diff_header = QtWidgets.QLabel("变更详情对比")
        diff_header.setStyleSheet("font-weight: 700; font-size: 13px;")
        middle_layout.addWidget(diff_header)

        diff_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        self._doc_view = QtWidgets.QTextEdit()
        self._doc_view.setReadOnly(True)
        self._doc_view.setPlaceholderText("文档侧 (doc_ir)")
        self._doc_view.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 12px;"
        )

        self._code_view = QtWidgets.QTextEdit()
        self._code_view.setReadOnly(True)
        self._code_view.setPlaceholderText("代码侧 (code_ir)")
        self._code_view.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 12px;"
        )

        diff_splitter.addWidget(self._doc_view)
        diff_splitter.addWidget(self._code_view)
        diff_splitter.setStretchFactor(0, 1)
        diff_splitter.setStretchFactor(1, 1)
        middle_layout.addWidget(diff_splitter, 1)

        root_splitter.addWidget(middle_panel)

        # ── [RIGHT] Sign-off controls ──
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(12)

        right_header = QtWidgets.QLabel("签批决策")
        right_header.setStyleSheet("font-weight: 700; font-size: 13px;")
        right_layout.addWidget(right_header)

        right_layout.addStretch(1)

        self._btn_accept_doc = QtWidgets.QPushButton("接受文档更新")
        self._btn_accept_doc.setToolTip("采纳文档侧的变更，同步到代码")
        self._btn_accept_doc.setStyleSheet(
            "background: #2563eb; color: white; font-weight: 600; "
            "padding: 10px 16px; border-radius: 8px; border: none;"
        )
        self._btn_accept_doc.clicked.connect(self._on_accept_doc)

        self._btn_accept_code = QtWidgets.QPushButton("接受代码更新")
        self._btn_accept_code.setToolTip("采纳代码侧的变更，同步到文档")
        self._btn_accept_code.setStyleSheet(
            "background: #16a34a; color: white; font-weight: 600; "
            "padding: 10px 16px; border-radius: 8px; border: none;"
        )
        self._btn_accept_code.clicked.connect(self._on_accept_code)

        self._btn_ignore = QtWidgets.QPushButton("暂不处理 / 忽略")
        self._btn_ignore.setToolTip("跳过此项，稍后处理")
        self._btn_ignore.setStyleSheet(
            "background: #6b7280; color: white; font-weight: 600; "
            "padding: 10px 16px; border-radius: 8px; border: none;"
        )
        self._btn_ignore.clicked.connect(self._on_ignore)

        right_layout.addWidget(self._btn_accept_doc)
        right_layout.addWidget(self._btn_accept_code)
        right_layout.addWidget(self._btn_ignore)

        right_layout.addStretch(2)

        root_splitter.addWidget(right_panel)

        root_splitter.setStretchFactor(0, 2)
        root_splitter.setStretchFactor(1, 3)
        root_splitter.setStretchFactor(2, 1)
        root_splitter.setSizes([280, 440, 160])

        for btn in (self._btn_accept_doc, self._btn_accept_code, self._btn_ignore):
            btn.setEnabled(False)

        # ── Status bar at bottom ──
        self._status_label = QtWidgets.QLabel("就绪 — 请从左侧选择变更项")
        self._status_label.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; "
            "border-radius: 6px; padding: 6px 10px; color: #475569;"
        )
        root_layout.addWidget(self._status_label)

    # ── internal slots ──────────────────────────────────────────────

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        """Show the doc/code side-by-side for the selected item."""
        data = item.data(0, QtCore.Qt.UserRole)
        if not data or "_group_key" in data:
            self._doc_view.clear()
            self._code_view.clear()
            self._current_item = None
            self._status_label.setText("就绪 — 请从左侧选择变更项")
            for btn in (self._btn_accept_doc, self._btn_accept_code, self._btn_ignore):
                btn.setEnabled(False)
            return

        self._current_item = data
        self._populate_diff(data)

        for btn in (self._btn_accept_doc, self._btn_accept_code, self._btn_ignore):
            btn.setEnabled(True)

        name = data.get("name", "?")
        kind = data.get("kind", "?")
        self._status_label.setText(f"已选中: {kind} '{name}' — 请选择签批决策")

    def _populate_diff(self, data: dict) -> None:
        """Render the doc and code snapshots into the two text views."""
        doc = data.get("doc")
        code = data.get("code")

        doc_text = (
            json.dumps(doc, ensure_ascii=False, indent=2)
            if doc is not None
            else "(不存在)"
        )
        code_text = (
            json.dumps(code, ensure_ascii=False, indent=2)
            if code is not None
            else "(不存在)"
        )

        self._doc_view.setPlainText(doc_text)
        self._code_view.setPlainText(code_text)

    # ── sign-off slots (emit typed signals + debug logs + GUI feedback) ─

    def _on_accept_doc(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        kind = self._current_item.get("kind", "?")
        print(f"[DEBUG] 按钮 [接受文档更新] 被点击，正在发射信号...")
        print(
            f"[签批决策] 接受文档更新 | {kind}: {name} | "
            f"将执行正向同步 (文档→代码)"
        )
        self._status_label.setText(f"✓ 已批准文档更新: {name}")
        if self.isVisible():
            QtWidgets.QMessageBox.information(
                self, "签批确认",
                f"已接受文档更新: {kind} '{name}'\n将执行正向同步 (文档→代码)"
            )
        self.accept_doc_signal.emit(name)

    def _on_accept_code(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        kind = self._current_item.get("kind", "?")
        print(f"[DEBUG] 按钮 [接受代码更新] 被点击，正在发射信号...")
        print(
            f"[签批决策] 接受代码更新 | {kind}: {name} | "
            f"将执行反向同步 (代码→文档)"
        )
        self._status_label.setText(f"✓ 已批准代码更新: {name}")
        if self.isVisible():
            QtWidgets.QMessageBox.information(
                self, "签批确认",
                f"已接受代码更新: {kind} '{name}'\n将执行反向同步 (代码→文档)"
            )
        self.accept_code_signal.emit(name)

    def _on_ignore(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        kind = self._current_item.get("kind", "?")
        print(f"[DEBUG] 按钮 [暂不处理/忽略] 被点击，正在发射信号...")
        print(
            f"[签批决策] 暂不处理 | {kind}: {name} | "
            f"已跳过，留待后续批次"
        )
        self._status_label.setText(f"○ 已忽略: {name}")
        self.ignore_signal.emit(name)

    # ── helpers ─────────────────────────────────────────────────────

    def _update_summary(self, verdict_dict: dict) -> None:
        fwd = len(verdict_dict.get("FORWARD_CHANGES", []))
        bwd = len(verdict_dict.get("BACKWARD_CHANGES", []))
        cnf = len(verdict_dict.get("CONFLICTS", []))
        total = fwd + bwd + cnf
        summary = f"共 {total} 项变更  ·  🔴冲突 {cnf}  ·  🔵正向 {fwd}  ·  🟢逆向 {bwd}"
        print(f"[ReviewPanel] 已加载判决: {summary}")

    def set_summary_text(self, text: str) -> None:
        """Set the window title summary (caller convenience)."""
        if self.isWindow():
            self.setWindowTitle(f"双向同步评审中心 — {text}")