from autodoc.render import _render_cache_key


def test_render_cache_key_is_stable_for_identical_render_inputs():
    first = _render_cache_key("src/comm.c", "CommDataPack", "void CommDataPack(void)", "通信数据打包")
    second = _render_cache_key("src/comm.c", "CommDataPack", "void CommDataPack(void)", "通信数据打包")

    assert first == second


def test_render_cache_key_changes_when_resolved_function_title_changes():
    legacy = _render_cache_key("src/comm.c", "CommDataPack", "void CommDataPack(void)", "通信数据打包")
    disambiguated = _render_cache_key(
        "src/comm.c",
        "CommDataPack",
        "void CommDataPack(void)",
        "通信数据打包（CommDataPack）",
    )

    assert legacy != disambiguated
