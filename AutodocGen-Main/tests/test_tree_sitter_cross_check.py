import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc import parse


class Cfg:
    verbose = False
    extra_params = {"tree_sitter_cross_check": "1"}


def test_tree_sitter_extractor_finds_normal_function():
    funcs = parse._extract_tree_sitter_functions("int add(int a, int b) { return a + b; }\n")
    if not funcs:
        pytest.skip("tree-sitter C parser unavailable")

    assert funcs[0]["func_name"] == "add"
    assert funcs[0]["start_line"] == 1
    assert "add(int a, int b)" in funcs[0]["prototype"]


def test_cross_check_reports_missing_regex_function(monkeypatch):
    monkeypatch.setattr(
        parse,
        "_extract_tree_sitter_functions",
        lambda code: [{"func_name": "ts_only", "start_line": 1, "start": 0, "end": 10}],
    )

    messages = parse._cross_check_tree_sitter_functions("", [], Cfg())

    assert messages == ["[tree_sitter_cross_check] regex missed function: ts_only"]


def test_parse_base_keeps_regex_results_when_cross_check_fails(monkeypatch):
    def fail_extract(code):
        raise RuntimeError("boom")

    monkeypatch.setattr(parse, "_extract_tree_sitter_functions", fail_extract)

    results = parse._parse_c_file_base("int keep(void) { return 1; }\n", cfg=Cfg())

    assert len(results) == 1
    assert results[0]["func_info"]["func_name"] == "keep"
