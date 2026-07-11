import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import autodoc.backend as backend
import autodoc.pipeline as pipeline
from qt_gui.runner import GenerateWorker, TaskSpec
from qt_gui.settings_store import AppSettings, normalize_ai_mode


def test_autodoc_cli_module_entrypoint_runs_version():
    result = subprocess.run(
        [sys.executable, "-m", "autodoc.cli", "--version"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "AutoDocGen" in result.stdout


def test_genconfig_incremental_defaults_false():
    assert backend.GenConfig().incremental is False


def test_backend_project_generation_passes_cfg_incremental(monkeypatch):
    captured = {}

    def fake_run_project_generation(root_dir, output, cfg, **kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(pipeline, "run_project_generation", fake_run_project_generation)

    cfg = backend.GenConfig(incremental=True)
    assert backend.generate_design_doc_for_project("project", "out.docx", cfg) == "ok"
    assert captured["incremental"] is True


def test_generate_worker_passes_incremental_for_project(tmp_path):
    captured = {}

    class FakeBackend:
        GenConfig = backend.GenConfig

        @staticmethod
        def parse_domain_glossary_text(text):
            return {}

        @staticmethod
        def apply_domain_glossary_overrides(overrides):
            return None

        @staticmethod
        def parse_symbol_dictionary_text(text):
            return {}

        @staticmethod
        def apply_symbol_dictionary_overrides(overrides):
            return None

        @staticmethod
        def normalize_docx_output_path(output, ensure_parent_dir=True):
            return output

        @staticmethod
        def generate_design_doc_for_project(root_dir, output, cfg, resume_state=None):
            captured["cfg"] = cfg

        @staticmethod
        def stop_requested(cfg):
            return False

    settings = AppSettings(incremental=True)
    task = TaskSpec(
        mode="project",
        c_file="",
        project_dir=str(tmp_path),
        output=str(tmp_path / "out.docx"),
        template_path="",
    )
    worker = GenerateWorker(backend=FakeBackend(), task=task, settings=settings, resume_state=None)

    worker.run(
        emit_step=lambda *args: None,
        emit_log=lambda *args: None,
        emit_output=lambda *args: None,
        emit_done=lambda *args: None,
    )

    assert captured["cfg"].incremental is True


def test_public_ai_mode_normalization_is_binary():
    assert normalize_ai_mode(0) == 0
    assert normalize_ai_mode(1) == 1
    assert normalize_ai_mode(2) == 1
    assert normalize_ai_mode("2") == 1
    assert normalize_ai_mode("invalid") == 0


def test_generate_worker_collapses_legacy_ai_modes(tmp_path):
    captured = {}

    class FakeBackend:
        GenConfig = backend.GenConfig

        @staticmethod
        def parse_domain_glossary_text(text):
            return {}

        @staticmethod
        def apply_domain_glossary_overrides(overrides):
            return None

        @staticmethod
        def parse_symbol_dictionary_text(text):
            return {}

        @staticmethod
        def apply_symbol_dictionary_overrides(overrides):
            return None

        @staticmethod
        def normalize_docx_output_path(output, ensure_parent_dir=True):
            return output

        @staticmethod
        def generate_design_doc_for_project(root_dir, output, cfg, resume_state=None):
            captured["cfg"] = cfg

        @staticmethod
        def stop_requested(cfg):
            return False

    settings = AppSettings(
        ai_mode=2,
        force_ai=True,
        ai_one_call=True,
        auto_disable_large_one_call=False,
        ai_logic_policy="ai_non_structured",
    )
    task = TaskSpec(
        mode="project",
        c_file="",
        project_dir=str(tmp_path),
        output=str(tmp_path / "out.docx"),
        template_path="",
    )
    worker = GenerateWorker(backend=FakeBackend(), task=task, settings=settings, resume_state=None)

    worker.run(
        emit_step=lambda *args: None,
        emit_log=lambda *args: None,
        emit_output=lambda *args: None,
        emit_done=lambda *args: None,
    )

    cfg = captured["cfg"]
    assert cfg.ai_mode == 1
    assert cfg.ai_assist is True
    assert cfg.ai_logic_policy == "hybrid"
    assert cfg.ai_one_call is False
    assert cfg.auto_disable_large_one_call is True
    assert cfg.force_ai is False
