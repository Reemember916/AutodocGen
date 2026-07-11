import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.ai import (
    _build_completions_request_data,
    _clear_ai_runtime_state,
    _warmup_symbol_memory_once,
    ai_context_scope,
    call_llm_json,
    call_llm_text,
    _normalize_wire_api,
    _parse_completions_output,
    normalize_model_name,
    normalize_api_url,
)


class _FakeResp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeRuntime:
    requests = object()

    def __init__(self, status_code):
        self.status_code = status_code
        self.calls = 0

    def _get_http_session(self, cfg):
        return object()

    def _post_with_proxy_fallback(self, **kwargs):
        self.calls += 1
        return _FakeResp(self.status_code, "Authentication Fails"), "", {"source": "direct", "url": ""}

    def _write_ai_repro_bundle(self, *args, **kwargs):
        return {}


def _make_ai_cfg(**overrides):
    events = []
    cfg = SimpleNamespace(
        ai_assist=True,
        ai_provider="deepseek",
        ai_api_base="https://api.deepseek.com",
        ai_api_key="test-key",
        ai_model="deepseek-chat",
        ai_temperature=0.1,
        ai_top_p=0.9,
        ai_max_tokens=128,
        ai_num_ctx=0,
        ai_workers=1,
        ai_retry_times=0,
        ai_fail_policy="fallback",
        ai_circuit_break=False,
        extra_params={},
        verbose=False,
        gui_log=None,
        gui_event=events.append,
        stop_event=None,
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    cfg._events = events
    return cfg


def test_normalize_wire_api_accepts_completions_aliases():
    assert _normalize_wire_api("completions") == "completions"
    assert _normalize_wire_api("openai-completions") == "completions"
    assert _normalize_wire_api("responses") == "responses"


def test_normalize_api_url_appends_completions_for_plain_host():
    assert (
        normalize_api_url("https://example.com", "completions")
        == "https://example.com/v1/completions"
    )


def test_normalize_api_url_does_not_duplicate_v1_base():
    assert (
        normalize_api_url("https://api.deepseek.com/v1", "chat_completions")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    assert (
        normalize_api_url("https://api.example.com/api/v1", "responses")
        == "https://api.example.com/api/v1/responses"
    )


def test_normalize_api_url_keeps_custom_plan_endpoint():
    assert (
        normalize_api_url("https://ark.cn-beijing.volces.com/api/plan/v3", "completions")
        == "https://ark.cn-beijing.volces.com/api/plan/v3"
    )


def test_build_completions_request_data_uses_prompt_protocol():
    cfg = SimpleNamespace(
        ai_model="doubao-seed-2.0-code",
        ai_max_tokens=128,
        ai_temperature=0.1,
        ai_top_p=0.5,
    )
    data = _build_completions_request_data(cfg, "hello")

    assert data["model"] == "doubao-seed-2.0-code"
    assert data["prompt"] == "hello"
    assert data["max_tokens"] == 128
    assert "messages" not in data


def test_parse_completions_output_reads_text_choice():
    assert _parse_completions_output({"choices": [{"text": "OK"}]}) == "OK"


def test_normalize_model_name_keeps_deepseek_official_names():
    assert (
        normalize_model_name("deepseek-chat", url="https://api.deepseek.com/chat/completions")
        == "deepseek-chat"
    )


def test_call_llm_json_auth_error_trips_circuit_break():
    _clear_ai_runtime_state()
    cfg = _make_ai_cfg()
    runtime = _FakeRuntime(401)

    assert call_llm_json("{}", cfg, _runtime_module=runtime) == {}
    assert cfg.ai_circuit_break is True
    assert getattr(cfg, "_ai_last_error") == "LLM 鉴权失败: 401"
    assert [event["type"] for event in cfg._events] == ["ai_circuit_break"]

    assert call_llm_json("{}", cfg, _runtime_module=runtime) == {}
    assert runtime.calls == 1
    _clear_ai_runtime_state()


def test_call_llm_text_auth_error_trips_circuit_break():
    _clear_ai_runtime_state()
    cfg = _make_ai_cfg()
    runtime = _FakeRuntime(403)

    assert call_llm_text("hello", cfg, _runtime_module=runtime) == ""
    assert cfg.ai_circuit_break is True
    assert getattr(cfg, "_ai_last_error") == "LLM 鉴权失败: 403"

    assert call_llm_text("hello", cfg, _runtime_module=runtime) == ""
    assert runtime.calls == 1
    _clear_ai_runtime_state()


def test_auth_circuit_is_shared_across_new_cfg_objects():
    _clear_ai_runtime_state()
    cfg = _make_ai_cfg()
    runtime = _FakeRuntime(401)

    assert call_llm_json("{}", cfg, _runtime_module=runtime) == {}
    assert runtime.calls == 1

    next_cfg = _make_ai_cfg()
    next_runtime = _FakeRuntime(401)
    assert call_llm_text("hello", next_cfg, _runtime_module=next_runtime) == ""
    assert next_cfg.ai_circuit_break is True
    assert next_runtime.calls == 0
    _clear_ai_runtime_state()


def test_ai_context_scope_defaults_to_target_only():
    cfg = _make_ai_cfg()

    assert ai_context_scope(cfg) == "target_only"


def test_symbol_memory_warmup_skips_target_only_scope(monkeypatch):
    cfg = _make_ai_cfg()
    calls = []

    monkeypatch.setattr(
        "autodoc.ai._collect_symbol_memory_warmup_candidates",
        lambda *args, **kwargs: [{"name": "value", "kind": "local", "hits": 2, "types": [], "examples": ["value = value + 1;"]}],
    )

    class _Backend:
        DOMAIN_GLOSSARY = {}

        def _normalize_ai_var_keys(self, js, names, **kwargs):
            return js

        def _coerce_dict_keys(self, item, aliases):
            return item

        def _remember_ai_symbol(self, *args, **kwargs):
            calls.append((args, kwargs))

    _warmup_symbol_memory_once([{"body": "value = value + 1;"}], cfg, scope_label="single_file:x.c", backend_module=_Backend())

    assert calls == []


def test_project_naming_index_rebuild_uses_non_ai_worker_cfg(tmp_path, monkeypatch):
    from autodoc import backend, naming

    source = tmp_path / "x.c"
    source.write_text("""
/* demo */
void Demo(void)
{
    int value = 0;
}
""", encoding="utf-8")

    cfg = _make_ai_cfg()
    cfg.ai_assist = True

    def fail_rich_name(*args, **kwargs):
        raise AssertionError("naming index rebuild must not call AI rich naming")

    monkeypatch.setattr(naming, "get_function_chinese_name_rich", fail_rich_name)
    monkeypatch.setattr(backend, "_get_ordered_project_c_files", lambda project_root, worker_cfg: [str(source)])

    title_payload, symbol_payload = naming._rebuild_project_naming_indexes(str(tmp_path), cfg, backend_module=backend)

    assert title_payload["items"][0]["func_name"] == "Demo"
    assert symbol_payload["items"]
