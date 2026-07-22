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
        self._btn_repair = QtWidgets.QPushButton("应用修复到符号字典")
        self._btn_repair.setEnabled(False)
        self._btn_repair.setObjectName("open_term_table_btn")
        self._btn_repair.setToolTip("将 high/medium 建议写回 symbol_dictionary.json（可 dry-run 预览）")
        btn_layout.addWidget(self._btn_repair)
        layout.addLayout(btn_layout)

        # 初始状态
        self._report_data: dict = {}
        self._project_root: str = ""
        self._dict_path: str = ""
        self._btn_export.clicked.connect(self._on_export)
        self._btn_repair.clicked.connect(self._on_repair)

    def set_paths(self, *, project_root: str = "", dict_path: str = "") -> None:
        """Optional paths for apply-repair writeback."""
        self._project_root = str(project_root or "").strip()
        self._dict_path = str(dict_path or "").strip()

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
        """Apply high/medium suggestions into symbol dictionary / project memory."""
        if not self._report_data:
            return
        try:
            from autodoc.term_checker import apply_repair_from_report, build_repair_patch
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "无法加载修复模块", str(exc))
            return

        patch = build_repair_patch(self._report_data, severities=("high", "medium"))
        if not patch:
            QtWidgets.QMessageBox.information(self, "无需修复", "当前报告没有 high/medium 级别的可写回项。")
            return

        preview = "\n".join(f"  {k} → {v}" for k, v in list(patch.items())[:15])
        if len(patch) > 15:
            preview += f"\n  ... 共 {len(patch)} 项"

        import os

        dict_path = self._dict_path
        if not dict_path:
            candidates = []
            if self._project_root:
                candidates.append(os.path.join(self._project_root, "symbol_dictionary.json"))
            candidates.append(os.path.join(os.getcwd(), "symbol_dictionary.json"))
            for c in candidates:
                if c and os.path.isfile(c):
                    dict_path = c
                    break
            if not dict_path:
                dict_path = candidates[0] if candidates else "symbol_dictionary.json"

        memory_path = ""
        if self._project_root:
            memory_path = os.path.join(self._project_root, "autodoc_symbol_memory.json")

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("应用术语修复")
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setText(
            f"将把 {len(patch)} 个建议写回符号字典"
            f"{' 与项目记忆库' if memory_path else ''}。\n\n"
            f"字典：{dict_path}\n"
            f"{'记忆库：' + memory_path + chr(10) if memory_path else ''}\n"
            f"预览：\n{preview}"
        )
        dry_btn = msg.addButton("仅预览 (dry-run)", QtWidgets.QMessageBox.ActionRole)
        apply_btn = msg.addButton("写入", QtWidgets.QMessageBox.AcceptRole)
        msg.addButton("取消", QtWidgets.QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked not in (dry_btn, apply_btn):
            return
        dry_run = clicked is dry_btn
        try:
            result = apply_repair_from_report(
                self._report_data,
                dict_path=dict_path,
                memory_path=memory_path,
                dry_run=dry_run,
                backup=True,
                severities=("high", "medium"),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "修复失败", str(exc))
            return
        if dry_run:
            QtWidgets.QMessageBox.information(
                self,
                "Dry-run 结果",
                f"将应用 {result.applied_count} 项（未写盘）。\n字典：{dict_path}",
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "已写入",
                f"已应用 {result.applied_count} 项。\n"
                f"字典：{result.dict_path or dict_path}\n"
                f"{'记忆库：' + (result.memory_path or memory_path) if result.wrote_memory else ''}\n"
                f"{'备份：' + result.dict_backup if result.dict_backup else ''}".strip(),
            )
