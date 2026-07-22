import os
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from cli import _build_metadata, run_code_diff, run_diff
from diff.collect_changes import DEFAULT_FUZZY_MIN_SCORE
from tickets.tickets import write_ticket_template


class DocDiffApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DocDiff 更改单生成器")
        self.root.geometry("820x700")
        self.root.minsize(760, 600)

        self.old_var = tk.StringVar(value="12.docx")
        self.new_var = tk.StringVar(value="123.docx")
        self.out_var = tk.StringVar(value="更改单_测试版.docx")
        self.mode_var = tk.StringVar(value="docx")
        self.show_c_gap_marker_var = tk.BooleanVar(value=True)
        self.fuzzy_threshold_var = tk.StringVar(value=f"{DEFAULT_FUZZY_MIN_SCORE:.2f}")
        self.doc_no_var = tk.StringVar(value="")
        self.version_var = tk.StringVar(value="")
        self.author_var = tk.StringVar(value="")
        self.use_table_key_var = tk.BooleanVar(value=True)
        self.tickets_var = tk.StringVar(value="")
        self.ticket_prefix_var = tk.StringVar(value="")
        self.auto_match_tickets_var = tk.BooleanVar(value=False)

        self.old_label_var = tk.StringVar(value="旧版文档")
        self.new_label_var = tk.StringVar(value="新版文档")
        self.mode_text = {"docx": "文档更改单", "code": "代码更改单"}

        self._build_ui()

    def _build_ui(self) -> None:
        container = tk.Frame(self.root, padx=12, pady=10)
        container.pack(fill="both", expand=True)

        # ===== 模式选择 =====
        mode_row = tk.Frame(container)
        mode_row.pack(fill="x", pady=(0, 8))
        tk.Label(mode_row, text="模式", width=10, anchor="w").pack(side="left")
        mode_combo = ttk.Combobox(
            mode_row,
            state="readonly",
            width=20,
            textvariable=self.mode_var,
            values=["docx", "code"],
        )
        mode_combo.pack(side="left")
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_mode_change())

        # ===== 文件路径 =====
        path_group = tk.LabelFrame(container, text="文件路径", padx=8, pady=6)
        path_group.pack(fill="x", pady=(0, 6))
        self._build_path_row(
            path_group, self.old_label_var, self.old_var, self._pick_old
        )
        self._build_path_row(
            path_group, self.new_label_var, self.new_var, self._pick_new
        )
        self._build_path_row(path_group, "输出文档", self.out_var, self._pick_out)

        # ===== 问题单台账 =====
        ticket_group = tk.LabelFrame(container, text="问题单台账", padx=8, pady=6)
        ticket_group.pack(fill="x", pady=(0, 6))

        ticket_path_row = tk.Frame(ticket_group)
        ticket_path_row.pack(fill="x", pady=2)
        tk.Label(ticket_path_row, text="台账文件", width=10, anchor="w").pack(
            side="left"
        )
        tk.Entry(ticket_path_row, textvariable=self.tickets_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        tk.Button(
            ticket_path_row, text="浏览", width=8, command=self._pick_tickets
        ).pack(side="left")
        tk.Button(
            ticket_path_row,
            text="导出模板",
            width=8,
            command=self._export_ticket_template,
        ).pack(side="left", padx=(6, 0))

        ticket_prefix_row = tk.Frame(ticket_group)
        ticket_prefix_row.pack(fill="x", pady=2)
        tk.Label(ticket_prefix_row, text="编号前缀", width=10, anchor="w").pack(
            side="left"
        )
        tk.Entry(ticket_prefix_row, textvariable=self.ticket_prefix_var, width=18).pack(
            side="left"
        )
        tk.Label(
            ticket_prefix_row,
            text="（CSV 中已填完整编号则留空；仅缺号时自动生成）",
            anchor="w",
            fg="#555",
        ).pack(side="left", padx=(8, 0))

        self.auto_match_check = tk.Checkbutton(
            ticket_group,
            text="自动匹配问题单（默认规则；CLI 可用 --match-strategy rules|llm|hybrid）",
            variable=self.auto_match_tickets_var,
            anchor="w",
        )
        self.auto_match_check.pack(fill="x", pady=2)

        # ===== 文档设置（docx 模式） =====
        self.docx_group = tk.LabelFrame(container, text="文档设置", padx=8, pady=6)
        self.docx_group.pack(fill="x", pady=(0, 6))

        fuzzy_row = tk.Frame(self.docx_group)
        fuzzy_row.pack(fill="x", pady=2)
        tk.Label(fuzzy_row, text="Fuzzy阈值", width=10, anchor="w").pack(side="left")
        self.fuzzy_entry = tk.Entry(
            fuzzy_row, textvariable=self.fuzzy_threshold_var, width=8
        )
        self.fuzzy_entry.pack(side="left")
        tk.Label(
            fuzzy_row,
            text="（章节模糊配对，0~1，默认 0.72；越高越严）",
            anchor="w",
        ).pack(side="left", padx=(8, 0))

        meta_row = tk.Frame(self.docx_group)
        meta_row.pack(fill="x", pady=2)
        tk.Label(meta_row, text="文号", width=10, anchor="w").pack(side="left")
        self.doc_no_entry = tk.Entry(meta_row, textvariable=self.doc_no_var, width=18)
        self.doc_no_entry.pack(side="left")
        tk.Label(meta_row, text="版本", width=6, anchor="e").pack(
            side="left", padx=(12, 0)
        )
        self.version_entry = tk.Entry(meta_row, textvariable=self.version_var, width=12)
        self.version_entry.pack(side="left")
        tk.Label(meta_row, text="编制人", width=6, anchor="e").pack(
            side="left", padx=(12, 0)
        )
        self.author_entry = tk.Entry(meta_row, textvariable=self.author_var, width=12)
        self.author_entry.pack(side="left")

        self.table_key_check = tk.Checkbutton(
            self.docx_group,
            text="表格按主键列对齐（字段名/名称/ID 等）",
            variable=self.use_table_key_var,
            anchor="w",
        )
        self.table_key_check.pack(fill="x", pady=2)

        # ===== 代码设置（code 模式） =====
        self.code_group = tk.LabelFrame(container, text="代码设置", padx=8, pady=6)
        self.code_group.pack(fill="x", pady=(0, 6))

        self.c_gap_marker_check = tk.Checkbutton(
            self.code_group,
            text="C函数多段变更显示\u201c省略未改动片段\u201d分隔行",
            variable=self.show_c_gap_marker_var,
            anchor="w",
        )
        self.c_gap_marker_check.pack(fill="x", pady=2)

        # ===== 操作按钮 =====
        action = tk.Frame(container)
        action.pack(fill="x", pady=(4, 8))

        self.run_btn = tk.Button(action, text="开始生成", width=14, command=self._run)
        self.run_btn.pack(side="left")

        clear_btn = tk.Button(
            action, text="清空日志", width=14, command=self._clear_log
        )
        clear_btn.pack(side="left", padx=(8, 0))

        # ===== 运行日志 =====
        log_wrap = tk.LabelFrame(container, text="运行日志", padx=8, pady=8)
        log_wrap.pack(fill="both", expand=True, pady=(0, 4))

        self.log = ScrolledText(log_wrap, height=14, state="disabled")
        self.log.pack(fill="both", expand=True)

        self._on_mode_change()

    def _build_path_row(
        self, parent: tk.Widget, label, var: tk.StringVar, picker
    ) -> None:
        row = tk.Frame(parent)
        row.pack(fill="x", pady=4)

        text_var = label if isinstance(label, tk.StringVar) else None
        text = None if text_var is not None else str(label)
        tk.Label(row, text=text, textvariable=text_var, width=10, anchor="w").pack(
            side="left"
        )
        tk.Entry(row, textvariable=var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        tk.Button(row, text="浏览", width=10, command=picker).pack(side="left")

    def _on_mode_change(self) -> None:
        mode = self.mode_var.get()
        if mode == "code":
            self.old_label_var.set("旧版代码")
            self.new_label_var.set("新版代码")
            if self.out_var.get().strip() in {"", "更改单_测试版.docx"}:
                self.out_var.set("代码更改单.docx")
            self.docx_group.pack_forget()
            self.code_group.pack(fill="x", pady=(0, 6))
            self._append_log("已切换到代码更改单模式")
        else:
            self.old_label_var.set("旧版文档")
            self.new_label_var.set("新版文档")
            if self.out_var.get().strip() == "代码更改单.docx":
                self.out_var.set("更改单_测试版.docx")
            self.code_group.pack_forget()
            self.docx_group.pack(fill="x", pady=(0, 6))
            self._append_log("已切换到文档更改单模式")

    def _append_log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _append_log_threadsafe(self, msg: str) -> None:
        self.root.after(0, self._append_log, msg)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _pick_old(self) -> None:
        if self.mode_var.get() == "code":
            path = filedialog.askdirectory(title="选择旧版代码目录")
        else:
            path = filedialog.askopenfilename(
                title="选择旧版文档",
                filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")],
            )
        if path:
            self.old_var.set(path)

    def _pick_new(self) -> None:
        if self.mode_var.get() == "code":
            path = filedialog.askdirectory(title="选择新版代码目录")
        else:
            path = filedialog.askopenfilename(
                title="选择新版文档",
                filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")],
            )
        if path:
            self.new_var.set(path)

    def _pick_out(self) -> None:
        path = filedialog.asksaveasfilename(
            title="选择输出路径",
            defaultextension=".docx",
            filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")],
            initialfile=os.path.basename(self.out_var.get() or "更改单_测试版.docx"),
        )
        if path:
            self.out_var.set(path)

    def _pick_tickets(self) -> None:
        path = filedialog.askopenfilename(
            title="选择问题单台账",
            filetypes=[
                ("台账", "*.csv;*.json;*.xlsx;*.xlsm"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
                ("Excel", "*.xlsx;*.xlsm"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.tickets_var.set(path)

    def _export_ticket_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title="导出问题单模板",
            defaultextension=".csv",
            filetypes=[
                ("CSV（Excel可开）", "*.csv"),
                ("JSON", "*.json"),
                ("Excel", "*.xlsx"),
            ],
            initialfile="问题单台账.csv",
        )
        if not path:
            return
        try:
            prefix = (self.ticket_prefix_var.get() or "").strip() or "DFKS112-WT"
            write_ticket_template(path, ticket_prefix=prefix)
            self._append_log(f"问题单模板已导出：{path}（前缀 {prefix}）")
            messagebox.showinfo(
                "完成",
                f"已导出模板：\n{path}\n\n"
                f"编号示例：{prefix}-01、{prefix}-02\n"
                "请按列填写：序号、问题、问题单编号",
            )
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _parse_fuzzy_threshold(self) -> float:
        raw = (self.fuzzy_threshold_var.get() or "").strip()
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError("Fuzzy阈值须为 0~1 之间的数字") from exc
        if not 0.0 <= value <= 1.0:
            raise ValueError("Fuzzy阈值须在 0~1 之间")
        return value

    def _validate(self) -> bool:
        mode = self.mode_var.get()
        old_path = self.old_var.get().strip()
        new_path = self.new_var.get().strip()
        out_path = self.out_var.get().strip()
        tickets_path = self.tickets_var.get().strip()

        if mode == "docx":
            if not old_path or not os.path.isfile(old_path):
                messagebox.showerror("参数错误", "旧版文档路径无效，请选择 .docx 文件")
                return False
            if not new_path or not os.path.isfile(new_path):
                messagebox.showerror("参数错误", "新版文档路径无效，请选择 .docx 文件")
                return False
            try:
                self._parse_fuzzy_threshold()
            except ValueError as exc:
                messagebox.showerror("参数错误", str(exc))
                return False
        else:
            if not old_path or not os.path.exists(old_path):
                messagebox.showerror(
                    "参数错误", "旧版代码路径无效，请选择代码目录或文件"
                )
                return False
            if not new_path or not os.path.exists(new_path):
                messagebox.showerror(
                    "参数错误", "新版代码路径无效，请选择代码目录或文件"
                )
                return False
            if os.path.isfile(old_path) != os.path.isfile(new_path):
                messagebox.showerror(
                    "参数错误", "旧版与新版路径类型需一致（都为目录或都为文件）"
                )
                return False

        if tickets_path and not os.path.isfile(tickets_path):
            messagebox.showerror("参数错误", "问题单台账路径无效")
            return False

        if not out_path:
            messagebox.showerror("参数错误", "请填写输出文档路径")
            return False
        return True

    def _run(self) -> None:
        if not self._validate():
            return

        self.run_btn.configure(state="disabled")
        self._append_log(
            f"开始处理（{self.mode_text.get(self.mode_var.get(), self.mode_var.get())}）..."
        )

        mode = self.mode_var.get()
        old_path = self.old_var.get().strip()
        new_path = self.new_var.get().strip()
        out_path = self.out_var.get().strip()
        show_c_gap_marker = self.show_c_gap_marker_var.get()
        tickets_path = self.tickets_var.get().strip()
        ticket_prefix = self.ticket_prefix_var.get().strip()
        auto_match = self.auto_match_tickets_var.get()
        fuzzy_threshold = DEFAULT_FUZZY_MIN_SCORE
        metadata = None
        use_table_key = True
        if mode == "docx":
            fuzzy_threshold = self._parse_fuzzy_threshold()
            metadata = _build_metadata(
                old_path,
                new_path,
                doc_no=self.doc_no_var.get().strip(),
                version=self.version_var.get().strip(),
                author=self.author_var.get().strip(),
            )
            use_table_key = self.use_table_key_var.get()

        t = threading.Thread(
            target=self._run_worker,
            args=(
                mode,
                old_path,
                new_path,
                out_path,
                show_c_gap_marker,
                fuzzy_threshold,
                metadata,
                use_table_key,
                tickets_path,
                ticket_prefix,
                auto_match,
            ),
            daemon=True,
        )
        t.start()

    def _run_worker(
        self,
        mode: str,
        old_path: str,
        new_path: str,
        out_path: str,
        show_c_gap_marker: bool,
        fuzzy_threshold: float,
        metadata,
        use_table_key: bool,
        tickets_path: str,
        ticket_prefix: str,
        auto_match: bool,
    ) -> None:
        try:
            if mode == "code":
                run_code_diff(
                    old_path,
                    new_path,
                    out_path,
                    log=self._append_log_threadsafe,
                    show_c_gap_marker=show_c_gap_marker,
                    tickets_path=tickets_path,
                    ticket_prefix=ticket_prefix,
                    auto_match_tickets=auto_match,
                )
            else:
                run_diff(
                    old_path,
                    new_path,
                    out_path,
                    log=self._append_log_threadsafe,
                    fuzzy_min_score=fuzzy_threshold,
                    metadata=metadata,
                    use_table_key_column=use_table_key,
                    tickets_path=tickets_path,
                    ticket_prefix=ticket_prefix,
                    auto_match_tickets=auto_match,
                )
            self.root.after(
                0, lambda: messagebox.showinfo("完成", f"已生成更改单:\n{out_path}")
            )
        except Exception as exc:
            self._append_log_threadsafe(f"执行失败: {exc}")
            self._append_log_threadsafe(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("执行失败", str(exc)))
        finally:
            self.root.after(0, lambda: self.run_btn.configure(state="normal"))


def main() -> None:
    root = tk.Tk()
    DocDiffApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
