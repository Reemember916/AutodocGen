"""Term consistency panel for Qt GUI."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets


class ConsistencyPanel(QtWidgets.QWidget):
    """术语一致性检查结果面板。"""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题和评分
        header_layout = QtWidgets.QHBoxLayout()
        self._title_label = QtWidgets.QLabel("术语一致性检查")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        self._score_label = QtWidgets.QLabel("--/100")
        self._score_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self._score_label)
        layout.addLayout(header_layout)

        # 进度条
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        layout.addWidget(self._progress_bar)

        # 统计信息
        stats_layout = QtWidgets.QHBoxLayout()
        self._total_label = QtWidgets.QLabel("总符号: --")
        self._consistent_label = QtWidgets.QLabel("一致: --")
        self._inconsistent_label = QtWidgets.QLabel("不一致: --")
        self._conflict_label = QtWidgets.QLabel("字典冲突: --")
        for label in [self._total_label, self._consistent_label, self._inconsistent_label, self._conflict_label]:
            stats_layout.addWidget(label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 不一致详情列表
        self._detail_tree = QtWidgets.QTreeWidget()
        self._detail_tree.setHeaderLabels(["符号", "变体", "严重程度", "建议"])
        self._detail_tree.setRootIsDecorated(False)
        self._detail_tree.setAlternatingRowColors(True)
        self._detail_tree.setColumnWidth(0, 150)
        self._detail_tree.setColumnWidth(1, 250)
        self._detail_tree.setColumnWidth(2, 80)
        self._detail_tree.setColumnWidth(3, 200)
        layout.addWidget(self._detail_tree, 1)

        # 操作按钮
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        self._btn_export = QtWidgets.QPushButton("导出报告")
        self._btn_export.setEnabled(False)
        btn_layout.addWidget(self._btn_export)
        self._btn_repair = QtWidgets.QPushButton("应用修复")
        self._btn_repair.setEnabled(False)
        btn_layout.addWidget(self._btn_repair)
        layout.addLayout(btn_layout)

        # 初始状态
        self._report_data: dict = {}
        self._btn_export.clicked.connect(self._on_export)
        self._btn_repair.clicked.connect(self._on_repair)

    def update_report(self, report: dict) -> None:
        """更新一致性报告。"""
        self._report_data = report
        score = float(report.get("score", 0) or 0)
        total = int(report.get("total_symbols", 0) or 0)
        consistent = int(report.get("consistent_symbols", 0) or 0)
        inconsistencies = report.get("inconsistencies") or []
        conflicts = report.get("symbol_dict_conflicts") or []

        # 更新评分
        self._score_label.setText(f"{score:.1f}/100")
        if score >= 90:
            self._score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60;")
        elif score >= 70:
            self._score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12;")
        else:
            self._score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;")

        # 更新进度条
        self._progress_bar.setValue(int(score))
        if score >= 90:
            self._progress_bar.setStyleSheet("QProgressBar::chunk { background: #27ae60; }")
        elif score >= 70:
            self._progress_bar.setStyleSheet("QProgressBar::chunk { background: #f39c12; }")
        else:
            self._progress_bar.setStyleSheet("QProgressBar::chunk { background: #e74c3c; }")

        # 更新统计
        self._total_label.setText(f"总符号: {total}")
        self._consistent_label.setText(f"一致: {consistent}")
        self._inconsistent_label.setText(f"不一致: {len(inconsistencies)}")
        self._conflict_label.setText(f"字典冲突: {len(conflicts)}")

        # 更新详情列表
        self._detail_tree.clear()
        for inc in inconsistencies:
            item = QtWidgets.QTreeWidgetItem([
                str(inc.get("symbol", "")),
                ", ".join(inc.get("variants", [])),
                str(inc.get("severity", "")),
                str(inc.get("suggestion", "")),
            ])
            if inc.get("severity") == "high":
                item.setForeground(2, QtCore.Qt.red)
            elif inc.get("severity") == "medium":
                item.setForeground(2, QtCore.Qt.darkYellow)
            self._detail_tree.addTopLevelItem(item)

        for conflict in conflicts:
            item = QtWidgets.QTreeWidgetItem([
                str(conflict.get("symbol", "")),
                f"期望: {conflict.get('expected', '')}, 实际: {', '.join(conflict.get('actual', []))}",
                "字典冲突",
                str(conflict.get("expected", "")),
            ])
            item.setForeground(2, QtCore.Qt.red)
            self._detail_tree.addTopLevelItem(item)

        # 启用按钮
        self._btn_export.setEnabled(bool(inconsistencies or conflicts))
        self._btn_repair.setEnabled(bool(inconsistencies or conflicts))

    def clear(self) -> None:
        """清空报告。"""
        self._report_data = {}
        self._score_label.setText("--/100")
        self._score_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._progress_bar.setValue(0)
        self._total_label.setText("总符号: --")
        self._consistent_label.setText("一致: --")
        self._inconsistent_label.setText("不一致: --")
        self._conflict_label.setText("字典冲突: --")
        self._detail_tree.clear()
        self._btn_export.setEnabled(False)
        self._btn_repair.setEnabled(False)

    def _on_export(self) -> None:
        """导出报告。"""
        if not self._report_data:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出一致性报告", "consistency_report.json", "JSON (*.json)"
        )
        if not path:
            return
        import json
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._report_data, f, ensure_ascii=False, indent=2)
            QtWidgets.QMessageBox.information(self, "导出成功", f"报告已保存到：{path}")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "导出失败", str(exc))

    def _on_repair(self) -> None:
        """应用修复（占位）。"""
        QtWidgets.QMessageBox.information(
            self, "提示", "修复功能尚未实现。\n请根据建议手动更新符号字典。"
        )
