"""Unit tests for evidence / logic_step shadow switches (S3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.pipeline import (  # noqa: E402
    evidence_output_enabled,
    logic_step_ir_enabled,
    resolve_evidence_report_path,
)
from autodoc.evidence.collector import (  # noqa: E402
    clear_recorded_evidence,
    get_recorded_evidence,
    record_function_evidence,
    write_evidence_report,
)


def _cfg(extra: dict):
    return SimpleNamespace(extra_params=extra)


def test_evidence_flag_off_by_default():
    assert evidence_output_enabled(_cfg({})) is False
    assert evidence_output_enabled(_cfg({"evidence_output": "off"})) is False
    assert evidence_output_enabled(_cfg({"evidence_output": "0"})) is False


def test_evidence_flag_on():
    assert evidence_output_enabled(_cfg({"evidence_output": "on"})) is True
    assert evidence_output_enabled(_cfg({"evidence_output": "1"})) is True
    assert evidence_output_enabled(_cfg({"evidence_output": "/tmp/custom.json"})) is True


def test_logic_step_defaults_with_evidence():
    assert logic_step_ir_enabled(_cfg({"evidence_output": "on"})) is True
    assert logic_step_ir_enabled(_cfg({"evidence_output": "on", "logic_step_ir": "off"})) is False
    assert logic_step_ir_enabled(_cfg({"evidence_output": "off", "logic_step_ir": "shadow"})) is True


def test_resolve_evidence_report_path(tmp_path: Path):
    out = str(tmp_path / "doc.docx")
    p = resolve_evidence_report_path(out, _cfg({"evidence_output": "on"}))
    assert p.endswith(os_sep_join(["doc_evidence", "evidence_report.json"])) or p.endswith(
        "doc_evidence" + __import__("os").sep + "evidence_report.json"
    )
    custom = resolve_evidence_report_path(out, _cfg({"evidence_output": str(tmp_path / "e.json")}))
    assert custom.endswith("e.json")
    custom_dir = resolve_evidence_report_path(out, _cfg({"evidence_output": str(tmp_path / "edir")}))
    assert custom_dir.endswith("evidence_report.json")


def os_sep_join(parts):
    import os

    return os.sep.join(parts)


def test_write_evidence_report_off_path_empty():
    assert resolve_evidence_report_path("a.docx", _cfg({})) == ""


def test_record_and_write_report(tmp_path: Path):
    clear_recorded_evidence()
    func_data = {
        "func_info": {"func_name": "Demo_Init", "prototype": "void Demo_Init(void)"},
        "body": "{\n  int x = 0;\n  if (x) { x = 1; }\n}\n",
        "local_vars": [{"name": "x", "type": "int"}],
        "params": [],
        "file_context": {"source_file": "demo.c"},
        "comment_info": {"desc": "init"},
    }
    steps = []
    try:
        from autodoc.logic_step_ir import build_logic_steps

        steps = build_logic_steps(func_data["body"], func_data["local_vars"], None, name_map={})
    except Exception:
        steps = []
    record_function_evidence(func_data, steps, name_map={"x": "变量x"})
    assert get_recorded_evidence()
    report_path = tmp_path / "sub" / "evidence_report.json"
    written = write_evidence_report(str(report_path))
    assert Path(written).is_file()
    payload = json.loads(Path(written).read_text(encoding="utf-8"))
    assert payload["entry_count"] >= 1
    assert payload["evidence"][0]["func_name"] == "Demo_Init"
    clear_recorded_evidence()
    assert get_recorded_evidence() == []
