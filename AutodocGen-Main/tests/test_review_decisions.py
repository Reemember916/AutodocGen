from __future__ import annotations

import json

import pytest

from autodoc.review_decisions import (
    bundle_fingerprint,
    review_decisions_to_revision_profile,
    write_revision_profile_from_review,
)
from autodoc.review_workspace import (
    ReviewBlock,
    ReviewBundle,
    ReviewFunction,
    render_review_html,
    review_bundle_to_dict,
    review_function_key,
)
from autodoc.revision import apply_revision_to_context, apply_revision_to_logic_lines


def _bundle() -> ReviewBundle:
    return ReviewBundle(
        project_root="/project",
        output_docx="/project/out.docx",
        functions=(
            ReviewFunction(
                function_id="DemoFunc",
                name="DemoFunc",
                title="演示函数",
                source_file="/project/Src/demo.c",
                source_hash="source-v1",
                blocks=(
                    ReviewBlock("DemoFunc.summary.001", "DemoFunc", "summary", text="旧说明"),
                    ReviewBlock("DemoFunc.prototype.001", "DemoFunc", "prototype", text="void DemoFunc(void)", editable=False),
                    ReviewBlock(
                        "DemoFunc.io.001",
                        "DemoFunc",
                        "io_table",
                        rows=({"ident": "value", "name": "值", "c_type": "Uint16", "direction": "输入", "usage": ""},),
                    ),
                    ReviewBlock(
                        "DemoFunc.locals.001",
                        "DemoFunc",
                        "local_table",
                        rows=({"ident": "result", "name": "结果", "c_type": "Uint16", "direction": "", "usage": "旧用途"},),
                    ),
                    ReviewBlock("DemoFunc.return.001", "DemoFunc", "return", text="旧返回值"),
                    ReviewBlock("DemoFunc.logic.001", "DemoFunc", "logic_line", text="待人工修改；"),
                ),
            ),
        ),
    )


def _approved_decisions(bundle: ReviewBundle) -> dict:
    fn = bundle.functions[0]
    key = review_function_key(bundle, fn)
    return {
        "schema_version": 1,
        "bundle_fingerprint": bundle_fingerprint(bundle),
        "functions": {
            key: {
                "source_file": fn.source_file,
                "function": fn.name,
                "source_hash": fn.source_hash,
                "status": "approved",
                "notes": "人工确认",
                "title": "人工标题",
                "description": "人工说明",
                "return_desc": "人工返回值",
                "io_elements": [{"ident": "value", "name": "输入值"}],
                "local_elements": [{"ident": "result", "name": "处理结果", "usage": "保存计算结果"}],
                "logic_lines": ["读取输入值", "写入处理结果"],
            }
        },
    }


def test_review_html_contains_interactive_controls_and_safe_embedded_json():
    bundle = _bundle()
    unsafe = ReviewBundle(
        project_root=bundle.project_root,
        output_docx=bundle.output_docx,
        functions=(
            ReviewFunction(
                **{
                    **bundle.functions[0].__dict__,
                    "title": "<script>alert(1)</script>",
                }
            ),
        ),
    )

    html = render_review_html(unsafe)

    assert 'id="searchInput"' in html
    assert 'id="statusControl"' in html
    assert 'id="exportBtn"' in html
    assert 'id="importFile"' in html
    assert "localStorage.setItem(storageKey" in html
    assert "bundle_fingerprint" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_approved_review_decision_converts_to_revision_profile_and_applies():
    bundle = _bundle()
    profile = review_decisions_to_revision_profile(bundle, _approved_decisions(bundle))
    patch = next(iter(profile["functions"].values()))

    assert patch["function_name"] == "人工标题"
    assert patch["description"] == "人工说明"
    assert patch["return_desc"] == "人工返回值"
    assert patch["locked_names"]["value"]["display"] == "输入值"
    assert patch["locked_names"]["result"]["usage"] == "保存计算结果"
    assert patch["logic_lines"] == ["读取输入值", "写入处理结果"]

    ctx = {"comment_info": {}, "local_vars": [{"name": "result"}]}
    apply_revision_to_context(ctx, patch)
    assert ctx["comment_info"]["func_cn_name"] == "人工标题"
    assert ctx["comment_info"]["return_desc"] == "人工返回值"
    assert ctx["local_vars"][0]["usage"] == "保存计算结果"
    assert apply_revision_to_logic_lines(("旧逻辑",), patch) == ("读取输入值；", "写入处理结果；")


def test_non_approved_decisions_are_not_applied():
    bundle = _bundle()
    decisions = _approved_decisions(bundle)
    next(iter(decisions["functions"].values()))["status"] = "needs_revision"

    profile = review_decisions_to_revision_profile(bundle, decisions)

    assert profile["functions"] == {}


def test_stale_review_decision_is_rejected():
    bundle = _bundle()
    decisions = _approved_decisions(bundle)
    next(iter(decisions["functions"].values()))["source_hash"] = "old-source"

    with pytest.raises(ValueError, match="源码已变化"):
        review_decisions_to_revision_profile(bundle, decisions)


def test_review_decision_files_write_revision_profile(tmp_path):
    bundle = _bundle()
    bundle_path = tmp_path / "review_bundle.json"
    decisions_path = tmp_path / "review_decisions.json"
    output_path = tmp_path / "revision_profile.json"
    bundle_path.write_text(json.dumps(review_bundle_to_dict(bundle), ensure_ascii=False), encoding="utf-8")
    decisions_path.write_text(json.dumps(_approved_decisions(bundle), ensure_ascii=False), encoding="utf-8")

    profile = write_revision_profile_from_review(
        bundle_path=str(bundle_path),
        decisions_path=str(decisions_path),
        output_path=str(output_path),
    )

    assert output_path.is_file()
    assert len(profile["functions"]) == 1


def test_single_file_review_key_matches_revision_lookup(tmp_path):
    """Single-file generation used to set project_root=source file and emit '.::Func' keys."""
    source = tmp_path / "demo.c"
    source.write_text("Uint16 DemoFunc(Uint16 value) { return value; }\n", encoding="utf-8")
    bundle = ReviewBundle(
        project_root=str(source),  # historical single-file bug shape
        output_docx=str(tmp_path / "out.docx"),
        functions=(
            ReviewFunction(
                function_id="DemoFunc",
                name="DemoFunc",
                title="Demo",
                source_file=str(source),
                source_hash="abc",
                blocks=(ReviewBlock("DemoFunc.summary.001", "DemoFunc", "summary", text="old"),),
            ),
        ),
    )
    key = review_function_key(bundle, bundle.functions[0])
    assert key == "demo.c::DemoFunc"
    assert not key.startswith(".::")

    decisions = {
        "schema_version": 1,
        "bundle_fingerprint": bundle_fingerprint(bundle),
        "functions": {
            key: {
                "source_file": str(source),
                "function": "DemoFunc",
                "source_hash": "abc",
                "status": "approved",
                "title": "人工标题",
                "description": "人工说明",
                "return_desc": "人工返回值",
                "logic_lines": ["读取输入；"],
            }
        },
    }
    profile = review_decisions_to_revision_profile(bundle, decisions)
    from autodoc.revision import find_function_patch

    patch = find_function_patch(profile, str(source), "DemoFunc")
    assert patch
    assert patch.get("function_name") == "人工标题"
    assert patch.get("return_desc") == "人工返回值"
