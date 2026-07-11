import os
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from cli import run_code_diff, run_diff


class DocDiffApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DocDiff 更改单生成器")
        self.root.geometry("760x520")
        self.root.minsize(700, 460)

        self.old_var = tk.StringVar(value="12.docx")
        self.new_var = tk.StringVar(value="123.docx")
        self.out_var = tk.StringVar(value="更改单_测试版.docx")
        self.mode_var = tk.StringVar(value="docx")
        self.show_c_gap_marker_var = tk.BooleanVar(value=True)

        self.old_label_var = tk.StringVar(value="旧版文档")
        self.new_label_var = tk.StringVar(value="新版文档")
        self.mode_text = {"docx": "文档更改单", "code": "代码更改单"}

        self._build_ui()

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=12, pady=10)
        top.pack(fill="x")

        mode_row = tk.Frame(top)
        mode_row.pack(fill="x", pady=(0, 4))
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

        self._build_path_row(top, self.old_label_var, self.old_var, self._pick_old)
        self._build_path_row(top, self.new_label_var, self.new_var, self._pick_new)
        self._build_path_row(top, "输出文档", self.out_var, self._pick_out)

        opt_row = tk.Frame(top)
        opt_row.pack(fill="x", pady=(2, 0))
        self.c_gap_marker_check = tk.Checkbutton(
            opt_row,
            text="C函数多段变更显示“省略未改动片段”分隔行",
            variable=self.show_c_gap_marker_var,
            anchor="w",
        )
        self.c_gap_marker_check.pack(side="left")

        action = tk.Frame(top)
        action.pack(fill="x", pady=(8, 0))

        self.run_btn = tk.Button(action, text="开始生成", width=14, command=self._run)
        self.run_btn.pack(side="left")

        clear_btn = tk.Button(action, text="清空日志", width=14, command=self._clear_log)
        clear_btn.pack(side="left", padx=(8, 0))

        log_wrap = tk.LabelFrame(self.root, text="运行日志", padx=8, pady=8)
        log_wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log = ScrolledText(log_wrap, height=16, state="disabled")
        self.log.pack(fill="both", expand=True)

        self._on_mode_change()

    def _build_path_row(self, parent: tk.Widget, label, var: tk.StringVar, picker) -> None:
        row = tk.Frame(parent)
        row.pack(fill="x", pady=4)

        text_var = label if isinstance(label, tk.StringVar) else None
        text = None if text_var is not None else str(label)
        tk.Label(row, text=text, textvariable=text_var, width=10, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Button(row, text="浏览", width=10, command=picker).pack(side="left")

    def _on_mode_change(self) -> None:
        mode = self.mode_var.get()
        if mode == "code":
            self.old_label_var.set("旧版代码")
            self.new_label_var.set("新版代码")
            if self.out_var.get().strip() in {"", "更改单_测试版.docx"}:
                self.out_var.set("代码更改单.docx")
            self.c_gap_marker_check.configure(state="normal")
            self._append_log("已切换到代码更改单模式")
        else:
            self.old_label_var.set("旧版文档")
            self.new_label_var.set("新版文档")
            if self.out_var.get().strip() == "代码更改单.docx":
                self.out_var.set("更改单_测试版.docx")
            self.c_gap_marker_check.configure(state="disabled")
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
                title="选择旧版文档", filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")]
            )
        if path:
            self.old_var.set(path)

    def _pick_new(self) -> None:
        if self.mode_var.get() == "code":
            path = filedialog.askdirectory(title="选择新版代码目录")
        else:
            path = filedialog.askopenfilename(
                title="选择新版文档", filetypes=[("Word 文档", "*.docx"), ("所有文件", "*.*")]
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

    def _validate(self) -> bool:
        mode = self.mode_var.get()
        old_path = self.old_var.get().strip()
        new_path = self.new_var.get().strip()
        out_path = self.out_var.get().strip()

        if mode == "docx":
            if not old_path or not os.path.isfile(old_path):
                messagebox.showerror("参数错误", "旧版文档路径无效，请选择 .docx 文件")
                return False
            if not new_path or not os.path.isfile(new_path):
                messagebox.showerror("参数错误", "新版文档路径无效，请选择 .docx 文件")
                return False
        else:
            if not old_path or not os.path.exists(old_path):
                messagebox.showerror("参数错误", "旧版代码路径无效，请选择代码目录或文件")
                return False
            if not new_path or not os.path.exists(new_path):
                messagebox.showerror("参数错误", "新版代码路径无效，请选择代码目录或文件")
                return False
            if os.path.isfile(old_path) != os.path.isfile(new_path):
                messagebox.showerror("参数错误", "旧版与新版路径类型需一致（都为目录或都为文件）")
                return False

        if not out_path:
            messagebox.showerror("参数错误", "请填写输出文档路径")
            return False
        return True

    def _run(self) -> None:
        if not self._validate():
            return

        self.run_btn.configure(state="disabled")
        self._append_log(f"开始处理（{self.mode_text.get(self.mode_var.get(), self.mode_var.get())}）...")

        mode = self.mode_var.get()
        old_path = self.old_var.get().strip()
        new_path = self.new_var.get().strip()
        out_path = self.out_var.get().strip()
        show_c_gap_marker = self.show_c_gap_marker_var.get()

        t = threading.Thread(
            target=self._run_worker,
            args=(mode, old_path, new_path, out_path, show_c_gap_marker),
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
    ) -> None:
        try:
            if mode == "code":
                run_code_diff(
                    old_path,
                    new_path,
                    out_path,
                    log=self._append_log_threadsafe,
                    show_c_gap_marker=show_c_gap_marker,
                )
            else:
                run_diff(old_path, new_path, out_path, log=self._append_log_threadsafe)
            self.root.after(0, lambda: messagebox.showinfo("完成", f"已生成更改单:\n{out_path}"))
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
