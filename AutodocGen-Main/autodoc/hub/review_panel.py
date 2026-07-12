"""Visual review panel — ConsistencyReviewPanel.

Three-layer structure:
1. Change-list tree (QTreeWidget) — categorised by verdict type.
2. Dual-pane diff (QTextEdit × 2) — doc vs code side-by-side.
3. Sign-off controls (QPushButton) — approve / reject / skip.

Compatible with Windows 7 / PyQt5 (the project's existing Qt binding).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from PyQt5 import QtCore, QtWidgets  # type: ignore


# ── colour constants ────────────────────────────────────────────────────

_COLOUR_FORWARD = "#dbeafe"    # blue-100
_COLOUR_BACKWARD = "#fef3c7"  # amber-100
_COLOUR_CONFLICT = "#fecaca"   # red-100
_COLOUR_ALIGNED = "#bbf7d0"   # green-100
_COLOUR_NONE = "#f1f5f9"      # slate-100

_LABEL_FORWARD = "→ 正向 (文档→代码)"
_LABEL_BACKWARD = "← 反向 (代码→文档)"
_LABEL_CONFLICT = "⚠ 冲突 (需人工签署)"
_LABEL_ALIGNED = "✓ 已对齐"


class ConsistencyReviewPanel(QtWidgets.QWidget):
    """Visual review and sign-off panel for the bidirectional diff resolver.

    Usage::

        panel = ConsistencyReviewPanel()
        panel.load_verdict(verdict_dict)
        panel.show()
    """

    # Signals emitted when the user clicks a sign-off button
    approved = QtCore.pyqtSignal(str, dict)   # item_name, item_dict
    rejected = QtCore.pyqtSignal(str, dict)   # item_name, item_dict
    skipped = QtCore.pyqtSignal(str, dict)    # item_name, item_dict

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._current_item: Optional[dict] = None
        self._setup_ui()

    # ── public API ──────────────────────────────────────────────────

    def load_verdict(self, verdict_dict: dict) -> None:
        """Load a verdict from ``BiDirectionalResolver.compare_ir()``.

        Populates the change tree with four top-level groups.
        """
        self._verdict = verdict_dict
        self._tree.clear()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["变更项", "状态"])

        groups = [
            ("FORWARD_CHANGES", "→ 正向 (文档→代码)", _COLOUR_FORWARD),
            ("BACKWARD_CHANGES", "← 反向 (代码→文档)", _COLOUR_BACKWARD),
            ("CONFLICTS", "⚠ 冲突 (需人工签署)", _COLOUR_CONFLICT),
            ("ALIGNED", "✓ 已对齐", _COLOUR_ALIGNED),
        ]

        for key, label, colour in groups:
            items = verdict_dict.get(key, [])
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
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Layer 1: Summary bar ──
        self._summary_bar = QtWidgets.QFrame()
        self._summary_bar.setObjectName("review_summary")
        summary_layout = QtWidgets.QHBoxLayout(self._summary_bar)
        summary_layout.setContentsMargins(8, 4, 8, 4)
        self._summary_label = QtWidgets.QLabel("就绪")
        self._summary_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        summary_layout.addWidget(self._summary_label)
        summary_layout.addStretch()
        layout.addWidget(self._summary_bar)

        # ── Layer 1: Change-list tree ──
        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(True)
        self._tree.setRootIsDecorated(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree, 3)

        # ── Layer 2: Dual-pane diff ──
        diff_label = QtWidgets.QLabel("变更详情对比")
        diff_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(diff_label)

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
        layout.addWidget(diff_splitter, 4)

        # ── Layer 3: Sign-off controls ──
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)

        self._btn_approve = QtWidgets.QPushButton("✓ 批准采纳")
        self._btn_approve.setStyleSheet(
            "background: #16a34a; color: white; font-weight: 600; "
            "padding: 8px 20px; border-radius: 8px; border: none;"
        )
        self._btn_approve.clicked.connect(self._on_approve)

        self._btn_reject = QtWidgets.QPushButton("✗ 驳回")
        self._btn_reject.setStyleSheet(
            "background: #dc2626; color: white; font-weight: 600; "
            "padding: 8px 20px; border-radius: 8px; border: none;"
        )
        self._btn_reject.clicked.connect(self._on_reject)

        self._btn_skip = QtWidgets.QPushButton("跳过")
        self._btn_skip.setStyleSheet(
            "background: #6b7280; color: white; font-weight: 600; "
            "padding: 8px 20px; border-radius: 8px; border: none;"
        )
        self._btn_skip.clicked.connect(self._on_skip)

        btn_layout.addWidget(self._btn_approve)
        btn_layout.addWidget(self._btn_reject)
        btn_layout.addWidget(self._btn_skip)
        btn_layout.addStretch()

        for btn in (self._btn_approve, self._btn_reject, self._btn_skip):
            btn.setEnabled(False)

        layout.addLayout(btn_layout)

    # ── internal slots ──────────────────────────────────────────────

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        """Show the doc/code side-by-side for the selected item."""
        data = item.data(0, QtCore.Qt.UserRole)
        if not data or "_group_key" in data:
            # Top-level group header — ignore
            self._doc_view.clear()
            self._code_view.clear()
            self._current_item = None
            for btn in (self._btn_approve, self._btn_reject, self._btn_skip):
                btn.setEnabled(False)
            return

        self._current_item = data
        self._populate_diff(data)

        # Enable sign-off buttons only for non-ALIGNED items
        group_key = item.text(1) if item.columnCount() > 1 else ""
        enabled = group_key != "ALIGNED"
        for btn in (self._btn_approve, self._btn_reject, self._btn_skip):
            btn.setEnabled(enabled)

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

    def _on_approve(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        print(f"[签批决策] 批准: {name}")
        self.approved.emit(name, self._current_item)

    def _on_reject(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        print(f"[签批决策] 驳回: {name}")
        self.rejected.emit(name, self._current_item)

    def _on_skip(self) -> None:
        if self._current_item is None:
            return
        name = self._current_item.get("name", "?")
        print(f"[签批决策] 跳过: {name}")
        self.skipped.emit(name, self._current_item)

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _update_summary(verdict_dict: dict) -> None:
        """Update the summary bar with counts."""
        fwd = len(verdict_dict.get("FORWARD_CHANGES", []))
        bwd = len(verdict_dict.get("BACKWARD_CHANGES", []))
        cnf = len(verdict_dict.get("CONFLICTS", []))
        aln = len(verdict_dict.get("ALIGNED", []))
        total = fwd + bwd + cnf + aln
        # Summary is updated by the caller via set_summary_text
        # This method is kept for internal use

    def set_summary_text(self, text: str) -> None:
        self._summary_label.setText(text)