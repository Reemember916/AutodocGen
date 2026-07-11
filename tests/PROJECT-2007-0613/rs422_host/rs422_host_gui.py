"""Tkinter maintenance RS422 host tool."""

from __future__ import annotations

import datetime as _dt
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import rs422_protocol as proto

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - depends on local environment
    serial = None
    list_ports = None


FIELD_LABELS = {
    "frame_id": "帧ID",
    "checksum": "校验",
    "valid_checksum": "校验通过",
    "frame_name": "帧名称",
    "tx_count": "发送计数",
    "system_time": "系统时间",
    "sys_state": "当前系统状态",
    "sys_state_last": "上一拍系统状态",
    "work_mode": "当前工作模式",
    "work_mode_last": "上一拍工作模式",
    "runtime_role": "控制权归属",
    "static_role": "静态主备身份",
    "control_output_valid": "控制输出有效",
    "control_output_state": "控制输出状态值",
    "local_chv_permit": "本端CHV允许",
    "local_chv_permit_value": "本端CHV资格值",
    "channel_2": "通道2",
    "my_channel_id": "本通道ID",
    "oil_mode": "空中加油模式",
    "con_func": "当前控制功能",
    "con_func_last": "上一拍控制功能",
    "maint_func": "维护功能",
    "chv_input": "CHV输入",
    "my_chv": "本端CHV回绕",
    "other_chv": "对端CHV输入",
    "wdv_normal": "WDV正常",
    "cpuv_normal": "CPUV正常",
    "latch_en": "锁存使能",
    "peer_alive": "对端在线",
    "peer_control_seen": "看到对端控制权",
    "condition_mask": "输出条件位图",
    "condition_role_master": "条件-本端主控",
    "condition_local_chv_permit": "条件-CHV资格",
    "condition_my_chv": "条件-CHV回绕",
    "condition_output_valid": "条件-输出有效",
    "diagnostic_peer_alive": "诊断-对端在线",
    "diagnostic_peer_control_seen": "诊断-对端持权",
    "air_oil_end_state": "加油结束状态",
    "local_preferred_master": "本地期望主通道",
    "peer_preferred_master": "对端期望主通道",
    "arbitrated_master": "仲裁主通道",
    "channel_type_code": "通道类型码",
    "pubit_key_fault": "PuBIT关键故障",
    "ifbit_level": "IFBIT等级",
    "mbit_level": "MBIT等级",
    "control_fault_mask": "控制故障位图",
    "control_comm_fault": "控制-通信故障",
    "control_measure_fault": "控制-测量故障",
    "control_imbalance_fault": "控制-不平衡故障",
    "control_has_fault": "控制-综合故障",
    "control_fault_reason": "控制故障原因码",
    "ifbit_signature": "IFBIT低32位签名",
    "mbit_signature_low16": "MBIT低16位签名",
    "source_word": "通信来源原始字",
    "riu_source": "RIU当前来源",
    "ccdl_source": "CCDL当前来源",
    "kzzz_source": "KZZZ当前来源",
    "riu_state": "RIU余度状态",
    "kzzz_left_state": "左KZZZ余度状态",
    "kzzz_right_state": "右KZZZ余度状态",
    "ccdl_state": "CCDL余度状态",
    "riu_heartbeat": "RIU心跳快照",
    "kzzz_left_snapshot": "左KZZZ快照",
    "kzzz_right_snapshot": "右KZZZ快照",
    "ccdl_peer_sys_state": "对端系统状态",
    "ccdl_peer_ch_type": "对端通道类型",
    "ccdl_peer_preferred_master": "对端期望主通道",
    "source_valid_mask": "来源有效位图",
    "riu_valid": "RIU有效",
    "kzzz_left_valid": "左KZZZ有效",
    "kzzz_right_valid": "右KZZZ有效",
    "ccdl_valid": "CCDL有效",
    "riu_source_invalid": "RIU选源无效",
    "ccdl_source_invalid": "CCDL选源无效",
    "kzzz_source_invalid": "KZZZ选源无效",
}

FRAME_NAME_LABELS = {
    "ID0 basic status": "ID0基础状态",
    "ID1 master arbitration": "ID1主备轮值诊断",
    "ID2 output authorization": "ID2输出授权诊断",
    "ID3 BIT fault summary": "ID3 BIT/故障摘要",
    "ID4 redundancy source": "ID4通信来源/余度来源",
    "ID5 RIU simulation status": "ID5 RIU模拟状态",
    "ID6 state condition injection": "ID6状态条件注入",
    "unknown": "未知帧",
}

STATE_VALUE_LABELS = {
    "sys_state": {0: "0 INIT", 1: "1 WORK", 2: "2 SAFETY", 3: "3 MAINTG", 4: "4 POWERDOWN"},
    "sys_state_last": {0: "0 INIT", 1: "1 WORK", 2: "2 SAFETY", 3: "3 MAINTG", 4: "4 POWERDOWN"},
    "work_mode": {
        0: "0 STANDBY",
        1: "1 LP_FIXEDWING",
        2: "2 RP_FIXEDWING",
        3: "3 LRP_FIXEDWING",
        4: "4 LP_HELI",
        5: "5 RP_HELI",
        6: "6 LRP_HELI",
        7: "7 RECEIVE",
    },
    "work_mode_last": {
        0: "0 STANDBY",
        1: "1 LP_FIXEDWING",
        2: "2 RP_FIXEDWING",
        3: "3 LRP_FIXEDWING",
        4: "4 LP_HELI",
        5: "5 RP_HELI",
        6: "6 LRP_HELI",
        7: "7 RECEIVE",
    },
    "con_func": {
        0: "0 STANDBY",
        1: "1 PRE_TASK_CHECK",
        2: "2 FUEL_PRESET",
        3: "3 REFUEL_PROCESS",
        4: "4 TASK_END",
        5: "5 MBIT",
    },
    "con_func_last": {
        0: "0 STANDBY",
        1: "1 PRE_TASK_CHECK",
        2: "2 FUEL_PRESET",
        3: "3 REFUEL_PROCESS",
        4: "4 TASK_END",
        5: "5 MBIT",
    },
}


class Rs422HostApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PROJECT 维护422上位机")
        self.geometry("1100x720")
        self.minsize(980, 640)

        self.serial_port = None
        self.reader_thread: threading.Thread | None = None
        self.stop_reader = threading.Event()
        self.rx_queue: queue.Queue[bytes | Exception] = queue.Queue()
        self.rx_buffer = bytearray()
        self.frame_count = 0
        self.status_value_vars: dict[str, list[tk.StringVar]] = {}
        self.latest_fields: dict[str, object] = {}
        self.state_timeline: list[str] = []
        self.active_test: dict[str, object] | None = None
        self.test_after_id: str | None = None
        self.test_stable_hits = 0
        self.rx_sequence = 0
        self.base_tk_scaling = float(self.tk.call("tk", "scaling"))

        self._build_vars()
        self._build_ui()
        self.refresh_ports()
        self.after(80, self._poll_rx_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_vars(self) -> None:
        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")
        self.status_var = tk.StringVar(value="已关闭")
        self.manual_hex_var = tk.StringVar()
        self.ui_scale_var = tk.StringVar(value="100%")

        self.a429_info_var = tk.IntVar(value=0)
        self.flowb_info_var = tk.IntVar(value=0)
        self.a429_label_var = tk.StringVar(value="00")
        self.read_addr_var = tk.StringVar(value="000000")
        self.redundancy_var = tk.IntVar(value=0)
        self.software_var = tk.IntVar(value=0)
        self.analog_var = tk.IntVar(value=0)
        self.pump_var = tk.IntVar(value=0)

        self.maint_func_var = tk.StringVar(value="1 软件CRC")
        self.download_start_var = tk.StringVar(value="00000000")
        self.download_length_var = tk.StringVar(value="00000010")

        self.control_id_var = tk.StringVar(value="0 JYB1")
        self.control_data_var = tk.StringVar(value="0000")

        self.riu_object_var = tk.StringVar(value="1 固定翼")
        self.riu_mode_var = tk.StringVar(value="4 受油")
        self.riu_wheel_var = tk.StringVar(value="2 空中")
        self.riu_maint_cmd_var = tk.StringVar(value="00")
        self.riu_ctrl_cmd_var = tk.StringVar(value="0000")
        self.riu_prv_var = tk.StringVar(value="0.0")
        self.riu_lp_pfv_var = tk.StringVar(value="0.0")
        self.riu_rp_pfv_var = tk.StringVar(value="0.0")
        self.riu_total_fuel_var = tk.StringVar(value="120.0")
        self.riu_tank0_var = tk.StringVar(value="20.0")
        self.riu_tank1_var = tk.StringVar(value="20.0")
        self.riu_tank2_var = tk.StringVar(value="30.0")
        self.riu_tank3_var = tk.StringVar(value="30.0")
        self.riu_tank4_var = tk.StringVar(value="20.0")
        self.riu_density_var = tk.StringVar(value="0.800")
        self.riu_airspeed_var = tk.StringVar(value="450")
        self.riu_rcv_var = tk.StringVar(value="00")
        self.riu_valve1_var = tk.StringVar(value="00")
        self.riu_valve2_var = tk.StringVar(value="00")
        self.riu_pump_var = tk.StringVar(value="00")
        self.riu_hl_sensor_var = tk.StringVar(value="0000")
        self.riu_fault_var = tk.StringVar(value="0000")


        self.test_status_var = tk.StringVar(value="未运行")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="串口").grid(row=0, column=0, padx=(0, 6))
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=34)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(top, text="刷新", command=self.refresh_ports).grid(row=0, column=2, padx=(0, 6))

        ttk.Label(top, text="波特率").grid(row=0, column=3, padx=(0, 6))
        ttk.Entry(top, textvariable=self.baud_var, width=10).grid(row=0, column=4, padx=(0, 6))
        self.open_button = ttk.Button(top, text="打开", command=self.toggle_serial)
        self.open_button.grid(row=0, column=5, padx=(0, 6))
        ttk.Label(top, text="缩放").grid(row=0, column=6, padx=(4, 6))
        scale_combo = ttk.Combobox(top, textvariable=self.ui_scale_var, values=["90%", "100%", "110%", "125%"], width=6, state="readonly")
        scale_combo.grid(row=0, column=7, padx=(0, 6))
        scale_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_ui_scale())
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=8, sticky="e")

        if serial is None:
            ttk.Label(
                self,
                text="未安装 pyserial，真实串口功能不可用。请执行：python3 -m pip install pyserial",
                foreground="#a33",
                padding=(8, 0),
            ).grid(row=1, column=0, sticky="ew")

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)

        self._build_command_tabs(left)
        self._build_log_panel(right)

    def _build_command_tabs(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        tabs = ttk.Notebook(parent)
        tabs.grid(row=0, column=0, sticky="nsew")

        comm = ttk.Frame(tabs, padding=8)
        maint = ttk.Frame(tabs, padding=8)
        control = ttk.Frame(tabs, padding=8)
        manual = ttk.Frame(tabs, padding=8)
        test_case = ttk.Frame(tabs, padding=8)
        tabs.add(comm, text="通信状态")
        tabs.add(maint, text="维护功能")
        tabs.add(control, text="地面控制")
        tabs.add(test_case, text="测试用例")
        tabs.add(manual, text="手动帧")

        self._grid_spin(comm, "429信息ID", self.a429_info_var, 0, 0, 0, 7)
        self._grid_spin(comm, "流量盒ID", self.flowb_info_var, 1, 0, 0, 1)
        self._grid_entry(comm, "429标号 HEX", self.a429_label_var, 2)
        self._grid_entry(comm, "读取地址 HEX24", self.read_addr_var, 3)
        self._grid_spin(comm, "余度索引", self.redundancy_var, 4, 0, 0, 255)
        self._grid_spin(comm, "软件版本索引", self.software_var, 5, 0, 0, 255)
        self._grid_spin(comm, "模拟量索引", self.analog_var, 6, 0, 0, 255)
        self._grid_spin(comm, "泵控制器索引", self.pump_var, 7, 0, 0, 255)
        ttk.Button(comm, text="发送通信状态帧", command=self.send_comm_info).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        self._grid_combo(
            maint,
            "功能码",
            self.maint_func_var,
            0,
            [
                ("1 软件CRC", "1"),
                ("2 数据下载", "2"),
                ("3 信息擦除", "3"),
                ("4 PID参数调整", "4"),
            ],
        )
        self._grid_entry(maint, "下载起始地址 HEX32", self.download_start_var, 1)
        self._grid_entry(maint, "下载长度 HEX32", self.download_length_var, 2)
        ttk.Button(maint, text="发送维护功能帧", command=self.send_maint_func).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        self._grid_combo(
            control,
            "指令ID",
            self.control_id_var,
            0,
            [
                ("0 JYB1", "0"),
                ("1 JYB2", "1"),
                ("2 PQF", "2"),
                ("3 SOV", "3"),
                ("4 KZZZ", "4"),
            ],
        )
        self._grid_entry(control, "控制数据 HEX16", self.control_data_var, 1)
        ttk.Button(control, text="发送地面控制帧", command=self.send_ground_control).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        self._build_test_case_tab(test_case)

        manual.columnconfigure(0, weight=1)
        ttk.Label(manual, text="输入16字节上位机发送帧；程序会自动重写帧头和校验。").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(manual, textvariable=self.manual_hex_var).grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Button(manual, text="填充空白帧", command=self.fill_manual_frame).grid(
            row=2, column=0, sticky="ew"
        )
        ttk.Button(manual, text="发送手动帧", command=self.send_manual).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=2)

        bar = ttk.Frame(parent)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(bar, text="模拟ID0", command=lambda: self.simulate_rx(0)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID1", command=lambda: self.simulate_rx(1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID2", command=lambda: self.simulate_rx(2)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID3", command=lambda: self.simulate_rx(3)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID4", command=lambda: self.simulate_rx(4)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID5", command=lambda: self.simulate_rx(5)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="模拟ID6", command=lambda: self.simulate_rx(6)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="清空", command=self.clear_log).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="保存日志", command=self.save_log).pack(side=tk.RIGHT)

        self._build_status_tabs(parent)

        self.log = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("Menlo", 12))
        self.log.grid(row=2, column=0, sticky="nsew", pady=(8, 0))

    def _build_status_tabs(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent)
        tabs.grid(row=1, column=0, sticky="nsew")

        self._add_status_page(
            tabs,
            "控制总览",
            [
                "system_time",
                "sys_state",
                "work_mode",
                "con_func",
                "runtime_role",
                "static_role",
                "control_output_valid",
                "local_chv_permit",
                "channel_2",
                "chv_input",
                "air_oil_end_state",
            ],
        )
        self._add_status_page(
            tabs,
            "输出授权",
            [
                "my_channel_id",
                "local_chv_permit_value",
                "control_output_state",
                "peer_alive",
                "peer_control_seen",
                "condition_role_master",
                "condition_local_chv_permit",
                "condition_my_chv",
                "condition_output_valid",
                "diagnostic_peer_alive",
                "diagnostic_peer_control_seen",
                "condition_mask",
            ],
        )
        self._add_status_page(
            tabs,
            "BIT故障",
            [
                "pubit_key_fault",
                "ifbit_level",
                "mbit_level",
                "control_comm_fault",
                "control_measure_fault",
                "control_imbalance_fault",
                "control_has_fault",
                "control_fault_reason",
                "ifbit_signature",
                "mbit_signature_low16",
            ],
        )
        self._add_status_page(
            tabs,
            "余度来源",
            [
                "riu_source",
                "ccdl_source",
                "kzzz_source",
                "riu_state",
                "kzzz_left_state",
                "kzzz_right_state",
                "ccdl_state",
                "riu_valid",
                "kzzz_left_valid",
                "kzzz_right_valid",
                "ccdl_valid",
                "riu_source_invalid",
                "ccdl_source_invalid",
                "kzzz_source_invalid",
                "source_valid_mask",
            ],
        )
        self._add_status_page(
            tabs,
            "RIU模拟",
            [
            ],
        )
        self._add_status_page(
            tabs,
            "状态条件",
            [
            ],
        )

    def _add_status_page(self, tabs: ttk.Notebook, title: str, keys: list[str]) -> None:
        page = ttk.Frame(tabs, padding=8)
        tabs.add(page, text=title)
        page.columnconfigure(1, weight=1)
        page.columnconfigure(3, weight=1)

        for index, key in enumerate(keys):
            row = index // 2
            col = (index % 2) * 2
            value_var = tk.StringVar(value="-")
            ttk.Label(page, text=FIELD_LABELS.get(key, key)).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
            ttk.Label(page, textvariable=value_var).grid(row=row, column=col + 1, sticky="w", padx=(0, 16), pady=3)
            self.status_value_vars.setdefault(key, []).append(value_var)

    def _grid_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=20).grid(row=row, column=1, sticky="ew", pady=3)
        parent.columnconfigure(1, weight=1)

    def _grid_spin(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.IntVar,
        row: int,
        column: int,
        from_: int,
        to: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", pady=3)
        ttk.Spinbox(parent, textvariable=variable, from_=from_, to=to, width=8).grid(
            row=row, column=column + 1, sticky="ew", pady=3
        )
        parent.columnconfigure(column + 1, weight=1)

    def _grid_combo(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        options: list[tuple[str, str]],
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        combo = ttk.Combobox(parent, textvariable=variable, values=[item[0] for item in options], width=18)
        combo.grid(row=row, column=1, sticky="ew", pady=3)
        parent.columnconfigure(1, weight=1)

    def _make_scrollable_tab(self, tabs: ttk.Notebook, title: str) -> ttk.Frame:
        outer = ttk.Frame(tabs)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, padding=8)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        tabs.add(outer, text=title)
        return content

    def apply_ui_scale(self) -> None:
        text = self.ui_scale_var.get().replace("%", "")
        try:
            factor = int(text) / 100.0
        except ValueError:
            factor = 1.0
        self.tk.call("tk", "scaling", self.base_tk_scaling * factor)

    def _build_test_case_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(4, weight=1)

        ttk.Label(parent, text="用例会发送帧并等待DSP回传字段满足；连续3帧满足才判通过。").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(parent, textvariable=self.test_status_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 8))

        cases = [
            ("清场", "clear"),
            ("进安全态", "safety"),
            ("安全回工作", "recover_work"),
            ("进维护", "maint_enter"),
            ("维护退出", "maint_exit"),
            ("进掉电", "powerdown"),
            ("掉电恢复", "power_restore"),
            ("进入受油", "receive_enter"),
            ("受油释放回待机", "receive_release"),
        ]
        for index, (label, case_id) in enumerate(cases):
            ttk.Button(parent, text=label, command=lambda cid=case_id: self.run_test_case(cid)).grid(
                row=2 + index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=3
            )

        self.test_log = scrolledtext.ScrolledText(parent, height=10, wrap=tk.WORD)
        self.test_log.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(10, 0))

    def refresh_ports(self) -> None:
        if list_ports is None:
            self.port_combo["values"] = []
            self.open_button["state"] = tk.DISABLED
            return
        ports = [port.device for port in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def toggle_serial(self) -> None:
        if self.serial_port is None:
            self.open_serial()
        else:
            self.close_serial()

    def open_serial(self) -> None:
        if serial is None:
            messagebox.showerror("缺少 pyserial", "请安装 pyserial：python3 -m pip install pyserial")
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("未选择串口", "请先选择串口。")
            return
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=int(self.baud_var.get()),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
            )
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.serial_port = None
            messagebox.showerror("打开失败", str(exc))
            return

        self.stop_reader.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        self.open_button["text"] = "关闭"
        self.status_var.set(f"已打开 {port} 115200 8O1")
        self.append_log("信息", f"已打开 {port}")

    def close_serial(self) -> None:
        self.stop_reader.set()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=0.4)
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.serial_port = None
        self.open_button["text"] = "打开"
        self.status_var.set("已关闭")
        self.append_log("信息", "已关闭串口")

    def _reader_loop(self) -> None:
        while not self.stop_reader.is_set():
            try:
                if self.serial_port is None:
                    break
                data = self.serial_port.read(128)
                if data:
                    self.rx_queue.put(data)
            except Exception as exc:  # pragma: no cover - hardware dependent
                self.rx_queue.put(exc)
                break

    def _poll_rx_queue(self) -> None:
        while True:
            try:
                item = self.rx_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, Exception):
                self.append_log("错误", f"串口读取失败：{item}")
                self.close_serial()
            else:
                self.handle_rx(item)
        self.after(80, self._poll_rx_queue)

    def handle_rx(self, data: bytes) -> None:
        self.append_log("RX", proto.bytes_to_hex(data))
        self.rx_buffer.extend(data)
        for frame in proto.extract_dsp_frames(self.rx_buffer):
            level = "OK" if frame.valid_checksum else "BAD"
            self.append_log(level, self.format_parsed_frame(frame))
            if frame.valid_checksum:
                self.latest_fields.update(frame.fields)
                self.record_state_timeline(frame)
                self.update_status_panel(frame)

    def simulate_rx(self, frame_id: int) -> None:
        self.handle_rx(proto.make_simulated_dsp_frame(frame_id))

    def send_comm_info(self) -> None:
        try:
            frame = proto.make_host_frame(
                proto.CMD_COMM_INFO,
                self.next_frame_count(),
                payload={
                    "a429_info": self.a429_info_var.get(),
                    "flowb_info": self.flowb_info_var.get(),
                    "a429_label": self.hex_int(self.a429_label_var.get()),
                    "read_addr": self.hex_int(self.read_addr_var.get()),
                    "redundancy_info": self.redundancy_var.get(),
                    "software_info": self.software_var.get(),
                    "analog_info": self.analog_var.get(),
                    "pump_info": self.pump_var.get(),
                },
            )
            self.send_frame(frame)
        except Exception as exc:
            messagebox.showerror("构造失败", str(exc))

    def send_maint_func(self) -> None:
        try:
            frame = proto.make_host_frame(
                proto.CMD_MAINT_FUNC,
                self.next_frame_count(),
                payload={
                    "function": self.leading_int(self.maint_func_var.get()),
                    "download_start": self.hex_int(self.download_start_var.get()),
                    "download_length": self.hex_int(self.download_length_var.get()),
                },
            )
            self.send_frame(frame)
        except Exception as exc:
            messagebox.showerror("构造失败", str(exc))

    def send_ground_control(self) -> None:
        try:
            frame = proto.make_host_frame(
                proto.CMD_GROUND_CONTROL,
                self.next_frame_count(),
                payload={
                    "command_id": self.leading_int(self.control_id_var.get()),
                    "data": self.hex_int(self.control_data_var.get()),
                },
            )
            self.send_frame(frame)
        except Exception as exc:
            messagebox.showerror("构造失败", str(exc))

    def run_test_case(self, case_id: str) -> None:
        if self.test_after_id is not None:
            self.after_cancel(self.test_after_id)
            self.test_after_id = None
        cases = self.build_test_cases()
        test = cases.get(case_id)
        if test is None:
            messagebox.showerror("测试用例", f"未知用例：{case_id}")
            return

        self.active_test = {
            "name": test["name"],
            "stages": test["stages"],
            "stage_index": -1,
        }
        self.state_timeline.clear()
        self.test_log.delete("1.0", tk.END)
        self.append_test_log(f"START {test['name']}")
        self.start_next_test_stage()

    def build_test_cases(self) -> dict[str, dict[str, object]]:
        return {
            "clear": {
                "name": "清场",
                "stages": [
                    {"name": "发送清场帧", "actions": [self.test_action_clear], "expected": {}, "timeout_ms": 0},
                ],
            },
            "safety": {
                "name": "进安全态",
                "stages": [
                    {"name": "IFBIT一级故障", "actions": [self.test_action_trigger_safety], "expected": {"sys_state": 2}, "timeout_ms": 5000},
                ],
            },
            "recover_work": {
                "name": "安全回工作链",
                "stages": [
                    {"name": "进入安全态", "actions": [self.test_action_trigger_safety], "expected": {"sys_state": 2}, "timeout_ms": 5000},
                    {"name": "安全态进入维护", "actions": [self.test_action_maint_enter], "expected": {"sys_state": 3}, "timeout_ms": 8000},
                    {"name": "维护退出回工作", "actions": [self.test_action_maint_exit], "expected": {"sys_state": 1}, "timeout_ms": 8000},
                ],
            },
            "maint_enter": {
                "name": "进维护",
                "stages": [
                    {"name": "维护IO有效", "actions": [self.test_action_maint_enter], "expected": {"sys_state": 3}, "timeout_ms": 8000},
                ],
            },
            "maint_exit": {
                "name": "维护退出",
                "stages": [
                    {"name": "维护IO无效且BIT正常", "actions": [self.test_action_maint_exit], "expected": {"sys_state": 1}, "timeout_ms": 8000},
                ],
            },
            "powerdown": {
                "name": "进掉电",
                "stages": [
                    {"name": "28V掉电异常", "actions": [self.test_action_powerdown], "expected": {"sys_state": 4}, "timeout_ms": 5000},
                ],
            },
            "power_restore": {
                "name": "掉电恢复",
                "stages": [
                    {"name": "28V恢复正常", "actions": [self.test_action_power_restore], "expected": {"sys_state": {0, 1, 2}}, "timeout_ms": 8000},
                ],
            },
            "receive_enter": {
                "name": "进入受油",
                "stages": [
                    {"name": "RIU模拟受油指令", "actions": [self.test_action_receive_enter], "expected": {"work_mode": 7}, "timeout_ms": 8000},
                ],
            },
            "receive_release": {
                "name": "受油释放回待机",
                "stages": [
                    {"name": "RIU关断/关闭模拟", "actions": [self.test_action_receive_release], "expected": {"work_mode": 0, "con_func": 0}, "timeout_ms": 10000},
                ],
            },
        }

    def start_next_test_stage(self) -> None:
        if self.active_test is None:
            return
        stages = self.active_test["stages"]
        stage_index = int(self.active_test["stage_index"]) + 1
        if stage_index >= len(stages):
            name = str(self.active_test["name"])
            self.test_status_var.set(f"PASS {name}")
            self.append_test_log(f"PASS {name}")
            self.active_test = None
            return

        self.active_test["stage_index"] = stage_index
        stage = stages[stage_index]
        self.test_stable_hits = 0
        self.active_test["last_rx_sequence"] = self.rx_sequence
        self.active_test["deadline"] = time.monotonic() + (int(stage.get("timeout_ms", 5000)) / 1000.0)
        self.test_status_var.set(f"RUN {self.active_test['name']} / {stage['name']}")
        self.append_test_log(f"STAGE {stage['name']}")

        for action in stage.get("actions", []):
            action()

        if not stage.get("expected"):
            self.start_next_test_stage()
            return
        self.test_after_id = self.after(200, self.check_test_case)

    def check_test_case(self) -> None:
        self.test_after_id = None
        if self.active_test is None:
            return
        stages = self.active_test["stages"]
        stage = stages[int(self.active_test["stage_index"])]

        if time.monotonic() > float(self.active_test["deadline"]):
            self.fail_active_test(stage, "超时")
            return

        if self.rx_sequence != int(self.active_test.get("last_rx_sequence", -1)):
            self.active_test["last_rx_sequence"] = self.rx_sequence
            if self.expected_fields_match(stage["expected"]):
                self.test_stable_hits += 1
                self.append_test_log(f"HIT {stage['name']} {self.test_stable_hits}/3")
            else:
                self.test_stable_hits = 0

        if self.test_stable_hits >= 3:
            self.append_test_log(f"OK {stage['name']}")
            self.start_next_test_stage()
            return

        self.test_after_id = self.after(200, self.check_test_case)

    def fail_active_test(self, stage: dict[str, object], reason: str) -> None:
        if self.active_test is None:
            return
        name = str(self.active_test["name"])
        self.test_status_var.set(f"FAIL {name} / {stage['name']}：{reason}")
        self.append_test_log(f"FAIL {name} / {stage['name']}：{reason}")
        self.append_test_log(f"期望: {self.format_expected(stage['expected'])}")
        self.append_test_log(f"实际: {self.format_current_state()}")
        if self.state_timeline:
            self.append_test_log("最近状态:")
            for line in self.state_timeline[-20:]:
                self.append_test_log(f"  {line}")
        self.active_test = None

    def expected_fields_match(self, expected: dict[str, object]) -> bool:
        for key, expected_value in expected.items():
            actual = self.latest_fields.get(key)
            if isinstance(expected_value, set):
                if actual not in expected_value:
                    return False
            elif actual != expected_value:
                return False
        return True

    def test_action_clear(self) -> None:
        self.riu_mode_var.set("0 关断")






    def test_action_receive_enter(self) -> None:
        self.riu_object_var.set("1 固定翼")
        self.riu_mode_var.set("4 受油")
        self.riu_wheel_var.set("2 空中")

    def test_action_receive_release(self) -> None:
        self.riu_mode_var.set("0 关断")

    def record_state_timeline(self, frame: proto.ParsedFrame) -> None:
        if not any(key in frame.fields for key in ("sys_state", "work_mode", "con_func")):
            return
        line = f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {self.format_current_state()}"
        self.state_timeline.append(line)
        if len(self.state_timeline) > 100:
            del self.state_timeline[: len(self.state_timeline) - 100]

    def format_expected(self, expected: dict[str, object]) -> str:
        parts = []
        for key, value in expected.items():
            if isinstance(value, set):
                parts.append(f"{key} in {{{', '.join(self.format_value(key, item) for item in sorted(value))}}}")
            else:
                parts.append(f"{key}={self.format_value(key, value)}")
        return ", ".join(parts)

    def format_current_state(self) -> str:
        keys = ("sys_state", "work_mode", "con_func", "frame_name")
        return ", ".join(f"{key}={self.format_value(key, self.latest_fields.get(key, '-'))}" for key in keys)

    def append_test_log(self, text: str) -> None:
        stamp = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.test_log.insert(tk.END, f"[{stamp}] {text}\n")
        self.test_log.see(tk.END)

    def fill_manual_frame(self) -> None:
        frame = proto.make_host_frame(proto.CMD_COMM_INFO, self.frame_count)
        self.manual_hex_var.set(proto.bytes_to_hex(frame))

    def send_manual(self) -> None:
        try:
            frame = proto.make_manual_host_frame(proto.parse_hex_bytes(self.manual_hex_var.get()))
            self.send_frame(frame)
        except Exception as exc:
            messagebox.showerror("手动帧失败", str(exc))

    def send_frame(self, frame: bytes) -> None:
        if self.serial_port is None:
            self.append_log("TX*", f"{proto.bytes_to_hex(frame)}  （未发送：串口未打开）")
            return
        try:
            self.serial_port.write(frame)
            self.append_log("TX", proto.bytes_to_hex(frame))
        except Exception as exc:  # pragma: no cover - hardware dependent
            messagebox.showerror("发送失败", str(exc))

    def next_frame_count(self) -> int:
        value = self.frame_count
        self.frame_count = (self.frame_count + 1) & 0xFF
        return value

    def hex_int(self, text: str) -> int:
        return int(text.strip().replace("0x", "").replace("0X", "") or "0", 16)

    def leading_int(self, text: str) -> int:
        return int(text.strip().split()[0])

    def deciliter(self, text: str) -> int:
        return max(0, min(0xFFFF, int(float(text.strip() or "0") * 10.0)))

    def format_parsed_frame(self, frame: proto.ParsedFrame) -> str:
        fields = []
        for key, value in frame.fields.items():
            label = FIELD_LABELS.get(key, key)
            if key == "frame_name":
                value = FRAME_NAME_LABELS.get(str(value), value)
            fields.append(f"{label}={self.format_value(key, value)}")
        return f"{frame.hex}\n    " + ", ".join(fields)

    def update_status_panel(self, frame: proto.ParsedFrame) -> None:
        for key, value in frame.fields.items():
            if key not in self.status_value_vars:
                continue
            display = self.format_value(key, value)
            for value_var in self.status_value_vars[key]:
                value_var.set(display)

    def format_value(self, key: str, value: object) -> str:
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, int):
            if key in STATE_VALUE_LABELS and value in STATE_VALUE_LABELS[key]:
                return STATE_VALUE_LABELS[key][value]
            if key.endswith("_mask") or key.endswith("_signature") or key in {
                "checksum",
                "chv_input",
                "source_word",
                "source_valid_mask",
                "ifbit_signature",
                "mbit_signature_low16",
            }:
                width = 8 if key == "ifbit_signature" else 4 if key == "mbit_signature_low16" else 2
                return f"0x{value:0{width}X}"
            return str(value)
        return str(value)

    def append_log(self, level: str, text: str) -> None:
        stamp = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log.insert(tk.END, f"[{stamp}] {level}: {text}\n")
        self.log.see(tk.END)

    def clear_log(self) -> None:
        self.log.delete("1.0", tk.END)

    def save_log(self) -> None:
        default = f"rs422_host_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        path = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".log",
            initialfile=default,
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(self.log.get("1.0", tk.END), encoding="utf-8")

    def on_close(self) -> None:
        if self.serial_port is not None:
            self.close_serial()
        self.destroy()


def main() -> None:
    app = Rs422HostApp()
    app.mainloop()


if __name__ == "__main__":
    main()
