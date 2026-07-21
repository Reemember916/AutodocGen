"""Unit tests for term-repair (S1)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.term_checker import (  # noqa: E402
    ConsistencyReport,
    TermInconsistency,
    apply_repair_from_report,
    apply_repair_to_symbol_dict,
    build_repair_patch,
    generate_repair_hints,
    report_from_dict,
    report_to_dict,
)


FIXTURE_REPORT = ROOT / "tests" / "fixtures" / "consistency_report.json"


def test_build_repair_patch_filters_low_severity():
    report = report_from_dict(json.loads(FIXTURE_REPORT.read_text(encoding="utf-8")))
    patch = build_repair_patch(report, severities=("high", "medium"))
    assert "pBuf" in patch
    assert patch["pBuf"] == "缓冲区指针"
    assert "status" in patch
    assert "tmp_u8" not in patch


def test_build_repair_patch_from_hints_only():
    hints = [
        {"symbol": "a", "suggested": "甲", "severity": "high"},
        {"symbol": "b", "suggested": "乙", "severity": "low"},
    ]
    patch = build_repair_patch(hints=hints, severities=("high",))
    assert patch == {"a": "甲"}


def test_dry_run_does_not_write(tmp_path: Path):
    dict_path = tmp_path / "symbol_dictionary.json"
    dict_path.write_text(json.dumps({"old": "旧值"}, ensure_ascii=False), encoding="utf-8")
    before = dict_path.read_text(encoding="utf-8")
    report = json.loads(FIXTURE_REPORT.read_text(encoding="utf-8"))
    result = apply_repair_from_report(
        report,
        dict_path=str(dict_path),
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.applied_count >= 1
    assert result.wrote_dict is False
    assert dict_path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "symbol_dictionary.json.bak").exists()


def test_write_merges_and_backup(tmp_path: Path):
    dict_path = tmp_path / "symbol_dictionary.json"
    dict_path.write_text(
        json.dumps({"keep": "保留", "pBuf": "旧缓冲"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    mem_path = tmp_path / "autodoc_symbol_memory.json"
    mem_path.write_text(json.dumps({"version": 1, "symbols": {}}, ensure_ascii=False), encoding="utf-8")
    report = json.loads(FIXTURE_REPORT.read_text(encoding="utf-8"))
    result = apply_repair_from_report(
        report,
        dict_path=str(dict_path),
        memory_path=str(mem_path),
        dry_run=False,
        backup=True,
        severities=("high", "medium"),
    )
    assert result.wrote_dict and result.wrote_memory
    assert result.dict_backup.endswith(".bak")
    data = json.loads(dict_path.read_text(encoding="utf-8"))
    assert data["keep"] == "保留"
    assert data["pBuf"] == "缓冲区指针"
    assert data["status"] == "状态"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    assert mem["symbols"]["pBuf"]["cn"] == "缓冲区指针"
    assert mem["symbols"]["pBuf"]["source"] == "term_repair"


def test_nested_symbol_dictionary_merge(tmp_path: Path):
    dict_path = tmp_path / "symbol_dictionary.json"
    dict_path.write_text(
        json.dumps(
            {"functions": {"Demo_Init": "初始化"}, "symbols": {"x": "原x"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = apply_repair_to_symbol_dict(
        {"x": "新x", "y": "新y"},
        dict_path=str(dict_path),
        dry_run=False,
        backup=False,
    )
    assert result.wrote_dict
    data = json.loads(dict_path.read_text(encoding="utf-8"))
    assert data["functions"]["Demo_Init"] == "初始化"
    assert data["symbols"]["x"] == "新x"
    assert data["symbols"]["y"] == "新y"


def test_report_roundtrip():
    report = ConsistencyReport(
        total_symbols=2,
        consistent_symbols=1,
        inconsistencies=[
            TermInconsistency(
                symbol="foo",
                variants=["甲", "乙"],
                locations=[],
                severity="high",
                suggestion="甲",
            )
        ],
        symbol_dict_conflicts=[],
        score=50.0,
    )
    payload = report_to_dict(report)
    back = report_from_dict(payload)
    assert back.total_symbols == 2
    assert back.inconsistencies[0].symbol == "foo"
    hints = generate_repair_hints(back)
    assert any(h["symbol"] == "foo" for h in hints)
