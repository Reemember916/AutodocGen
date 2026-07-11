"""测试 autodoc.forward.extractor — Markdown 需求文档解析器。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.forward.extractor import MarkdownExtractor


class TestMarkdownExtractor(unittest.TestCase):
    """MarkdownExtractor 单元测试。"""

    def setUp(self):
        self.extractor = MarkdownExtractor()

    def test_parse_valid_markdown(self):
        """硬编码标准 Markdown 文本，断言解析结果正确。"""
        md_content = """## 模块: APP_Config.h

> 描述: 应用层配置头文件 — 燃油控制系统顶层接口

### 函数: Control_Refuel_Process

- 中文名: 加油控制主流程
- 描述: 根据加油指令启动或停止加油泵，监控油量变化率，超时或异常时自动切断燃油供给并上报故障码。
- 返回值: uint16_t

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| Valve_Status | uint16_t | IN | 主副阀门的物理开关状态 |
| p_Fault_Code | uint16_t* | OUT | 传出参数：故障诊断码 |
"""
        header_ir = self.extractor.parse(md_content)

        # ── 断言模块级信息 ──
        self.assertEqual(header_ir.file_name, "APP_Config.h")
        self.assertIn("燃油控制系统", header_ir.brief_description)

        # ── 断言函数数量 ──
        self.assertEqual(len(header_ir.functions), 1)

        func = header_ir.functions[0]

        # ── 断言函数基础信息 ──
        self.assertEqual(func.name, "Control_Refuel_Process")
        self.assertEqual(func.chinese_name, "加油控制主流程")
        self.assertIn("加油指令", func.description)
        self.assertEqual(func.return_type.base_type, "uint16_t")
        self.assertFalse(func.return_type.is_pointer)

        # ── 断言参数列表 ──
        self.assertEqual(len(func.parameters), 2)

        p1 = func.parameters[0]
        p2 = func.parameters[1]

        # 参数 1: Valve_Status, IN, uint16_t, 非指针
        self.assertEqual(p1.name, "Valve_Status")
        self.assertEqual(p1.direction, "IN")
        self.assertEqual(p1.type_info.base_type, "uint16_t")
        self.assertFalse(p1.type_info.is_pointer)
        self.assertIn("阀门", p1.business_meaning)

        # 参数 2: p_Fault_Code, OUT, uint16_t*, 指针
        self.assertEqual(p2.name, "p_Fault_Code")
        self.assertEqual(p2.direction, "OUT")
        self.assertEqual(p2.type_info.base_type, "uint16_t")
        self.assertTrue(p2.type_info.is_pointer)
        self.assertIn("故障诊断码", p2.business_meaning)

    def test_parse_empty_markdown(self):
        """空输入返回空 HeaderFileIR。"""
        header_ir = self.extractor.parse("")
        self.assertEqual(header_ir.file_name, "")
        self.assertEqual(len(header_ir.functions), 0)

    def test_parse_const_pointer(self):
        """const 指针类型正确解析。"""
        md_content = """## 模块: Test.h

> 描述: 测试模块

### 函数: Read_Sensor

- 中文名: 读取传感器
- 描述: 读取传感器数据
- 返回值: void

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| p_Buf | const uint16_t* | IN | 只读缓冲区指针 |
"""
        header_ir = self.extractor.parse(md_content)
        self.assertEqual(len(header_ir.functions), 1)
        func = header_ir.functions[0]
        self.assertEqual(len(func.parameters), 1)
        p = func.parameters[0]
        self.assertEqual(p.name, "p_Buf")
        self.assertTrue(p.type_info.is_const)
        self.assertTrue(p.type_info.is_pointer)
        self.assertEqual(p.type_info.base_type, "uint16_t")

    def test_parse_multiple_functions(self):
        """多函数文档正确解析。"""
        md_content = """## 模块: MultiFunc.h

> 描述: 多功能模块

### 函数: Init_System

- 中文名: 系统初始化
- 描述: 初始化所有硬件外设
- 返回值: void

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| mode | uint8_t | IN | 启动模式选择 |

### 函数: Get_Status

- 中文名: 获取状态
- 描述: 读取系统状态寄存器
- 返回值: uint16_t

| 参数名 | 类型 | 方向 | 业务含义 |
|---|---|---|---|
| p_Status | uint16_t* | OUT | 状态字输出指针 |
"""
        header_ir = self.extractor.parse(md_content)
        self.assertEqual(header_ir.file_name, "MultiFunc.h")
        self.assertEqual(len(header_ir.functions), 2)

        f1 = header_ir.functions[0]
        self.assertEqual(f1.name, "Init_System")
        self.assertEqual(len(f1.parameters), 1)

        f2 = header_ir.functions[1]
        self.assertEqual(f2.name, "Get_Status")
        self.assertEqual(len(f2.parameters), 1)

    def test_parse_no_parameters(self):
        """无参数表函数正确解析。"""
        md_content = """## 模块: NoParam.h

> 描述: 无参数模块

### 函数: Reset_Watchdog

- 中文名: 复位看门狗
- 描述: 清除看门狗计数器
- 返回值: void
"""
        header_ir = self.extractor.parse(md_content)
        self.assertEqual(len(header_ir.functions), 1)
        func = header_ir.functions[0]
        self.assertEqual(func.name, "Reset_Watchdog")
        self.assertEqual(len(func.parameters), 0)


if __name__ == "__main__":
    unittest.main()