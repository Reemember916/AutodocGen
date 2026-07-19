from __future__ import annotations

from autodoc import pipeline, term_table
from autodoc._legacy_support import legacy_backend


def _entry(source_file: str, func_name: str, title: str = "状态更新") -> dict:
    return {
        "comment_info": {"func_cn_name": title, "desc": "更新状态"},
        "func_info": {"func_name": func_name, "prototype": f"void {func_name}(void)"},
        "body": "{}",
        "file_context": {"source_file": source_file},
    }


def test_project_title_registry_is_unique_and_order_independent():
    backend = legacy_backend()
    cfg = backend.GenConfig()
    first = _entry("/project/src/A.c", "UpdateA")
    second = _entry("/project/src/B.c", "UpdateB")

    pipeline.apply_project_function_title_registry([second, first], "/project", cfg)

    assert first["file_context"]["function_title"] == "状态更新"
    assert second["file_context"]["function_title"] == "状态更新（B）"
    assert first["comment_info"]["func_cn_name"] == "状态更新"
    assert second["comment_info"]["func_cn_name"] == "状态更新（B）"
    assert cfg.function_title_registry == {
        "src/A.c::UpdateA": "状态更新",
        "src/B.c::UpdateB": "状态更新（B）",
    }


def test_registry_uses_c_name_when_source_stem_is_also_ambiguous():
    backend = legacy_backend()
    cfg = backend.GenConfig()
    first = _entry("/project/a/State.c", "UpdateA")
    second = _entry("/project/b/State.c", "UpdateB")
    third = _entry("/project/c/State.c", "UpdateC")

    pipeline.apply_project_function_title_registry([first, second, third], "/project", cfg)

    assert first["file_context"]["function_title"] == "状态更新"
    assert second["file_context"]["function_title"] == "状态更新（State）"
    assert third["file_context"]["function_title"] == "状态更新（State_UpdateC）"


def test_module_table_and_design_title_use_registered_title():
    backend = legacy_backend()
    cfg = backend.GenConfig()
    entry = _entry("/project/src/B.c", "UpdateB")
    entry["file_context"]["function_title"] = "状态更新（B）"

    payload = pipeline.build_project_module_table_payload(
        [entry],
        module_id="CSC_001",
        module_display="控制",
        include_unit_func_table=True,
    )
    assert payload["entries"][0]["csu_name"] == "状态更新（B）"
    assert payload["unit_func_table"]["func_rows"][0]["name"] == "状态更新（B）"

    sections = pipeline.build_design_text_sections(
        {
            "comment_info": entry["comment_info"],
            "func_info": entry["func_info"],
            "body": "{}",
            "file_context": entry["file_context"],
            "raw_comment_desc": "更新状态",
        },
        "CSC_001",
        1,
        cfg,
    )
    assert sections["title_cn"] == "状态更新（B）"


def test_term_table_keeps_file_scoped_function_identity():
    backend = legacy_backend()
    cfg = backend.GenConfig()
    entry = _entry("/project/src/B.c", "UpdateB")
    entry["file_context"].update(
        {
            "function_title": "状态更新（B）",
            "function_title_key": "src/B.c::UpdateB",
        }
    )
    payload = {"version": 2, "functions": {}, "symbols": {}, "members": {}, "macros": {}}

    term_table._record_function_terms(payload, [entry], cfg=cfg)

    assert payload["functions"]["UpdateB"]["cn"] == "状态更新（B）"
    assert payload["functions"]["src/B.c::UpdateB"]["cn"] == "状态更新（B）"
    assert payload["functions"]["src/B.c::UpdateB"]["scope"] == "file"
