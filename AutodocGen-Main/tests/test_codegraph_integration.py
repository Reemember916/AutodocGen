import os
import sqlite3
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc import codegraph_adapter
from autodoc import graph_visuals
from autodoc.config import GenConfig


class Cfg:
    verbose = False
    extra_params = {
        "codegraph_mode": "auto",
        "graph_output": "both",
        "graph_depth": "2",
        "graph_max_nodes": "40",
        "codegraph_auto_index": "1",
    }


def test_codegraph_auto_missing_degrades(monkeypatch, tmp_path):
    cfg = Cfg()
    monkeypatch.setattr(codegraph_adapter.shutil, "which", lambda _name: None)

    status = codegraph_adapter.prepare_project_index(str(tmp_path), cfg)

    assert not status.enabled
    assert not status.available
    assert "not found" in status.message
    assert cfg._codegraph_project_enabled is False


def test_codegraph_force_missing_raises(monkeypatch, tmp_path):
    cfg = Cfg()
    cfg.extra_params = dict(cfg.extra_params, codegraph_mode="force")
    monkeypatch.setattr(codegraph_adapter.shutil, "which", lambda _name: None)

    with pytest.raises(codegraph_adapter.CodeGraphUnavailable):
        codegraph_adapter.prepare_project_index(str(tmp_path), cfg)


def test_run_json_command_parses_valid_json(monkeypatch):
    class Proc:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    monkeypatch.setattr(codegraph_adapter.subprocess, "run", lambda *a, **k: Proc())

    assert codegraph_adapter.run_json_command(["codegraph", "status", "--json"]) == {"ok": True}


def test_run_json_command_rejects_invalid_json(monkeypatch):
    class Proc:
        returncode = 0
        stdout = "not-json"
        stderr = ""

    monkeypatch.setattr(codegraph_adapter.subprocess, "run", lambda *a, **k: Proc())

    with pytest.raises(codegraph_adapter.CodeGraphCommandError):
        codegraph_adapter.run_json_command(["codegraph", "status", "--json"])


def test_codegraph_timeout_degrades_in_auto(monkeypatch, tmp_path):
    cfg = Cfg()
    fake_exe = tmp_path / "codegraph"
    fake_exe.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(codegraph_adapter, "resolve_executable", lambda _cfg=None: str(fake_exe))

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="codegraph", timeout=1)

    monkeypatch.setattr(codegraph_adapter, "_run_command", timeout)

    status = codegraph_adapter.prepare_project_index(str(tmp_path), cfg)

    assert not status.enabled
    assert "timed out" in status.message.lower()


def _create_codegraph_db(root):
    db_dir = root / ".codegraph"
    db_dir.mkdir()
    db_path = db_dir / "codegraph.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY,
            kind TEXT,
            name TEXT,
            qualified_name TEXT,
            file_path TEXT,
            language TEXT,
            start_line INTEGER,
            end_line INTEGER,
            start_column INTEGER,
            end_column INTEGER,
            signature TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE edges (
            source TEXT,
            target TEXT,
            kind TEXT,
            line INTEGER,
            col INTEGER,
            provenance TEXT
        )
        """
    )
    rows = [
        ("main", "function", "Main", "src/main.c::Main", "src/main.c", "c", 1, 5, 0, 0, "void Main(void)"),
        ("helper", "function", "Helper", "src/helper.c::Helper", "src/helper.c", "c", 3, 8, 0, 0, "void Helper(void)"),
        ("caller", "function", "Caller", "src/caller.c::Caller", "src/caller.c", "c", 4, 9, 0, 0, "void Caller(void)"),
    ]
    conn.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO edges VALUES (?,?,?,?,?,?)", ("main", "helper", "calls", 2, 1, "tree-sitter"))
    conn.execute("INSERT INTO edges VALUES (?,?,?,?,?,?)", ("caller", "main", "calls", 5, 1, "tree-sitter"))
    conn.commit()
    conn.close()
    return db_path


def test_enrich_function_entries_reads_codegraph_db(monkeypatch, tmp_path):
    db_path = _create_codegraph_db(tmp_path)
    cfg = Cfg()
    cfg._codegraph_project_enabled = True

    status = codegraph_adapter.CodeGraphStatus(
        mode="auto",
        enabled=True,
        available=True,
        executable="/bin/codegraph",
        project_root=str(tmp_path),
        index_path=str(db_path),
        initialized=True,
        indexed=True,
        source="codegraph",
        message="ready",
    )
    monkeypatch.setattr(codegraph_adapter, "prepare_project_index", lambda _root, _cfg=None: status)

    source_file = tmp_path / "src" / "main.c"
    source_file.parent.mkdir(exist_ok=True)
    entry = {
        "func_info": {"func_name": "Main"},
        "file_context": {"source_file": str(source_file)},
    }

    codegraph_adapter.enrich_function_entries([entry], str(tmp_path), cfg)

    ctx = entry["file_context"]
    assert ctx["caller_funcs"] == ["Caller"]
    assert ctx["callee_funcs"] == ["Helper"]
    assert ctx["codegraph_callers"][0]["filePath"] == "src/caller.c"
    assert ctx["codegraph_callees"][0]["filePath"] == "src/helper.c"
    assert ctx["codegraph_impact"][0]["name"] == "Caller"


def test_html_report_is_offline_and_searchable(tmp_path):
    cfg = Cfg()
    output = tmp_path / "out.docx"
    graph_visuals.configure_graph_output(cfg, str(output))
    payload = graph_visuals.build_function_graph_payload(
        {
            "func_info": {"func_name": "Main"},
            "file_context": {
                "source_file": str(tmp_path / "main.c"),
                "caller_funcs": ["Caller"],
                "callee_funcs": ["Helper"],
            },
        },
        cfg,
    )
    graph_visuals.append_payload(cfg, payload)

    html_path = graph_visuals.write_html_report(cfg, title="Demo")

    text = open(html_path, encoding="utf-8").read()
    assert "搜索函数" in text
    assert "Caller" in text
    assert "Helper" in text
    assert "https://" not in text
    assert "cdn" not in text.lower()


def test_graph_output_is_off_by_default(tmp_path):
    cfg = GenConfig()
    output = tmp_path / "out.docx"

    graph_visuals.configure_graph_output(cfg, str(output))
    graph_visuals.append_payload(
        cfg,
        {
            "id": "demo",
            "title": "Demo",
            "nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "edges": [{"source": "a", "target": "b", "kind": "calls"}],
        },
    )

    assert graph_visuals.graph_output_from_cfg(cfg) == "off"
    assert graph_visuals.write_html_report(cfg, title="Demo") == ""
    assert not (tmp_path / "out_graphs").exists()


def test_graph_output_can_be_enabled_explicitly_from_extra_params(tmp_path):
    cfg = GenConfig(extra_params={"graph_output": "html"})
    output = tmp_path / "out.docx"

    graph_visuals.configure_graph_output(cfg, str(output))
    graph_visuals.append_payload(
        cfg,
        {
            "id": "demo",
            "title": "Demo",
            "nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "edges": [{"source": "a", "target": "b", "kind": "calls"}],
        },
    )
    html_path = graph_visuals.write_html_report(cfg, title="Demo")

    assert html_path
    assert (tmp_path / "out_graphs" / "index.html").exists()
