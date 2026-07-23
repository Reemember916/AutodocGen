"""Tests for callgraph flatten_call_tree and render_static_call_relation_table."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.callgraph import flatten_call_tree, find_entry_functions, build_project_callees_map  # noqa: E402


CALLEES_MAP = {
    "main": ["DspInit", "WdgDisable", "WdgReset"],
    "DspInit": ["WdgDisable", "PllInit", "PeriphClkEn", "GpioInit"],
    "PllInit": ["PllMulCalc", "PllDivSel"],
    "GpioInit": ["GpioOutCfg", "GpioInCfg", "ExtIntCfg"],
    "WdgDisable": [],
    "WdgReset": [],
    "PeriphClkEn": [],
    "PllMulCalc": [],
    "PllDivSel": [],
    "GpioOutCfg": [],
    "GpioInCfg": [],
    "ExtIntCfg": [],
}

NAME_MAP = {
    "main": "主函数",
    "DspInit": "Dsp初始化",
    "WdgDisable": "看门狗禁用",
    "WdgReset": "看门狗复位",
    "PllInit": "PLL初始化",
    "PeriphClkEn": "外设时钟使能",
    "GpioInit": "GPIO初始化",
    "PllMulCalc": "PLL倍频系数计算",
    "PllDivSel": "PLL分频系数选择",
    "GpioOutCfg": "GPIO输出引脚配置",
    "GpioInCfg": "GPIO输入引脚配置",
    "ExtIntCfg": "外部引脚中断配置",
}


def test_flatten_basic():
    rows = flatten_call_tree(CALLEES_MAP, "main", max_depth=3, name_map=NAME_MAP)
    assert len(rows) > 0
    assert all(len(r) == 4 for r in rows)
    assert rows[0][0] == "主函数"


def test_flatten_leaf_dash():
    rows = flatten_call_tree(CALLEES_MAP, "main", max_depth=3, name_map=NAME_MAP)
    leaf_rows = [r for r in rows if r[1] == "看门狗禁用"]
    assert leaf_rows
    assert leaf_rows[0][2] == "-"
    assert leaf_rows[0][3] == "-"


def test_flatten_depth_limit():
    rows = flatten_call_tree(CALLEES_MAP, "main", max_depth=1, name_map=NAME_MAP)
    for r in rows:
        assert r[2] == "-"
        assert r[3] == "-"


def test_flatten_no_name_map():
    rows = flatten_call_tree(CALLEES_MAP, "main", max_depth=3)
    assert rows[0][0] == "main"
    assert any("DspInit" in r[1] for r in rows)


def test_find_entry_functions():
    entries = find_entry_functions(CALLEES_MAP)
    assert "main" in entries
    assert "DspInit" not in entries


def test_find_entry_no_roots():
    cyclic = {"a": ["b"], "b": ["a"]}
    entries = find_entry_functions(cyclic)
    assert entries == []


def test_build_project_callees_map():
    func_entries = [
        {
            "func_info": {"func_name": "main"},
            "file_context": {"callee_funcs": ["foo", "bar"]},
        },
        {
            "func_info": {"func_name": "foo"},
            "file_context": {"callee_funcs": []},
            "semantic_record": {"callee_names": ["baz"]},
        },
    ]
    m = build_project_callees_map(func_entries)
    assert m["main"] == ["foo", "bar"]
    assert m["foo"] == ["baz"]


def test_flatten_cycle_guard():
    cyclic = {"a": ["b"], "b": ["c"], "c": ["a"]}
    rows = flatten_call_tree(cyclic, "a", max_depth=3)
    assert len(rows) >= 1
    assert rows[0][0] == "a"


def test_flatten_empty():
    rows = flatten_call_tree({}, "main", max_depth=3)
    assert rows == [("main", "-", "-", "-")]
