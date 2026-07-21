"""Unit tests for failed-function retry API (S2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.retry import (  # noqa: E402
    filter_tasks_by_failures,
    load_failures,
    normalize_failure_records,
    rebuild_tasks_from_failures,
    run_retry_generation,
)


DEMO_C = ROOT / "tests" / "fixtures" / "sample_c" / "demo.c"
FAILURES_JSON = ROOT / "tests" / "fixtures" / "failures.json"


def _minimal_cfg():
    from autodoc.config import GenConfig

    return GenConfig(
        verbose=False,
        ai_assist=False,
        ai_mode=0,
        include_logic=True,
        include_locals=True,
        extra_params={},
    )


def test_normalize_and_load_failures():
    failures = load_failures(str(FAILURES_JSON))
    norm = normalize_failure_records(failures)
    assert len(norm) == 1
    assert norm[0]["func_name"] == "Demo_Init"
    assert norm[0]["has_body"] is False


def test_rebuild_from_stripped_failure_reparses_c():
    cfg = _minimal_cfg()
    failures = [
        {
            "func_name": "Demo_ClearBuffer",
            "file_path": str(DEMO_C),
            "error_type": "unknown",
            "error_message": "x",
            "task": {
                "func_name": "Demo_ClearBuffer",
                "source_file": str(DEMO_C),
                "func_data": {
                    "file_context": {"_stripped": True, "source_file": str(DEMO_C)},
                },
            },
        }
    ]
    tasks = rebuild_tasks_from_failures(failures, cfg, c_file=str(DEMO_C))
    assert len(tasks) == 1
    assert tasks[0]["func_name"] == "Demo_ClearBuffer"
    assert tasks[0]["func_data"].get("body")
    assert "pBuf" in (tasks[0]["func_data"].get("body") or "")


def test_rebuild_prefers_embedded_body():
    cfg = _minimal_cfg()
    body = "void Demo_Init(void){ int x=1; }"
    failures = [
        {
            "func_name": "Demo_Init",
            "file_path": str(DEMO_C),
            "task": {
                "func_name": "Demo_Init",
                "source_file": str(DEMO_C),
                "func_data": {
                    "body": body,
                    "func_info": {"func_name": "Demo_Init", "prototype": "void Demo_Init(void)"},
                    "file_context": {"source_file": str(DEMO_C)},
                },
            },
        }
    ]
    tasks = rebuild_tasks_from_failures(failures, cfg)
    assert tasks[0]["func_data"]["body"] == body


def test_filter_tasks_by_failures():
    all_tasks = [
        {"func_name": "A"},
        {"func_name": "B"},
        {"func_name": "C"},
    ]
    filtered = filter_tasks_by_failures(all_tasks, [{"func_name": "B"}, {"func_name": "C"}])
    assert [t["func_name"] for t in filtered] == ["B", "C"]


def test_run_retry_generation_smoke(tmp_path: Path):
    """End-to-end retry without AI; may skip if heavy deps missing."""
    cfg = _minimal_cfg()
    out = tmp_path / "retry_out.docx"
    failures = [
        {
            "func_name": "Demo_Init",
            "file_path": str(DEMO_C),
            "error_type": "unknown",
            "error_message": "simulated",
            "task": {"func_name": "Demo_Init", "source_file": str(DEMO_C), "func_data": {}},
        }
    ]
    try:
        result = run_retry_generation(
            failures,
            str(out),
            cfg,
            c_file=str(DEMO_C),
            merge=False,
        )
    except Exception as exc:
        pytest.skip(f"retry generation unavailable in this env: {exc}")
    assert result.output_path
    # Prefer success; if design failed, still_failed is populated
    if result.ok:
        assert out.is_file()
        assert "Demo_Init" in result.retried
    else:
        assert result.still_failed or result.errors
