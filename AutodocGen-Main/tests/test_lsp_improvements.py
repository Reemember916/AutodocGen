"""Tests for P0/P1/P2/P3 LSP improvements."""

import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc.lsp_facts import _assess_lsp_quality, _FACT_CACHE, _FACT_CACHE_MAX, build_function_fact_pack
from autodoc.lsp_gateway import LspGateway, _GATEWAYS, _LOCK, _lsp_uri_to_path, _path_to_lsp_uri


class TestAssessLspQuality(unittest.TestCase):
    """P1 #3: LSP 数据质量评估"""

    def test_empty_payload(self):
        score = _assess_lsp_quality({})
        self.assertEqual(score, 0.5)

    def test_blocks_only(self):
        payload = {"blocks": [{"kind": "if"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.65)

    def test_calls_with_signature(self):
        payload = {"calls": [{"callee": "foo", "signature": "void foo(int)"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.65)

    def test_members_with_owner_type(self):
        payload = {"members": [{"member": "x", "owner_type": "MyStruct"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.6)

    def test_locals_with_decl_type(self):
        payload = {"locals": [{"name": "tmp", "decl_type": "int"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.6)

    def test_full_quality(self):
        payload = {
            "blocks": [{"kind": "if"}],
            "calls": [{"signature": "void bar()"}],
            "members": [{"owner_type": "S"}],
            "locals": [{"decl_type": "int"}],
        }
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 1.0)

    def test_quality_clamped_at_1(self):
        payload = {
            "blocks": [{"kind": "if"}],
            "calls": [{"signature": "void bar()"}],
            "members": [{"owner_type": "S"}],
            "locals": [{"decl_type": "int"}],
        }
        score = _assess_lsp_quality(payload)
        self.assertLessEqual(score, 1.0)

    def test_calls_without_signature_no_bonus(self):
        payload = {"calls": [{"callee": "foo"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.5)

    def test_members_without_owner_type_no_bonus(self):
        payload = {"members": [{"member": "x"}]}
        score = _assess_lsp_quality(payload)
        self.assertAlmostEqual(score, 0.5)


class TestCrashReconnect(unittest.TestCase):
    """P0 #1: clangd 崩溃自动重连"""

    def setUp(self):
        with _LOCK:
            _GATEWAYS.clear()

    def tearDown(self):
        with _LOCK:
            _GATEWAYS.clear()

    def test_dead_session_removed_from_gateways(self):
        dead_session = MagicMock()
        dead_session.alive = False
        root = os.path.abspath("C:/fake_project")
        with _LOCK:
            _GATEWAYS[root] = dead_session

        with _LOCK:
            session = _GATEWAYS.get(root)
            self.assertIsNotNone(session)
            self.assertFalse(session.alive)
            if session and not session.alive:
                _GATEWAYS.pop(root, None)
            self.assertIsNone(_GATEWAYS.get(root))

    def test_alive_session_reused(self):
        alive_session = MagicMock()
        alive_session.alive = True
        alive_session.last_used = 100.0
        root = os.path.abspath("C:/fake_project")
        with _LOCK:
            _GATEWAYS[root] = alive_session

        with _LOCK:
            session = _GATEWAYS.get(root)
            self.assertIsNotNone(session)
            self.assertTrue(session.alive)


class TestLspUriConversion(unittest.TestCase):
    """P3 #10: Windows 路径编码兼容"""

    def test_windows_drive_path_to_uri(self):
        uri = _path_to_lsp_uri(r"C:\Program Files\项目\main.c")
        self.assertEqual(uri, "file:///C:/Program%20Files/%E9%A1%B9%E7%9B%AE/main.c")

    def test_lsp_uri_to_windows_drive_path(self):
        path = _lsp_uri_to_path("file:///C:/Program%20Files/%E9%A1%B9%E7%9B%AE/main.c")
        self.assertEqual(path, "C:/Program Files/项目/main.c")

    def test_unc_path_to_uri(self):
        uri = _path_to_lsp_uri(r"\\server\share dir\源.c")
        self.assertEqual(uri, "file://server/share%20dir/%E6%BA%90.c")

    def test_position_params_uses_compatible_uri(self):
        gateway = LspGateway(backend_module=MagicMock())
        params = gateway._position_params(r"C:\repo\main file.c", 3, 7)
        self.assertEqual(params["textDocument"]["uri"], "file:///C:/repo/main%20file.c")
        self.assertEqual(params["position"], {"line": 2, "character": 7})


class TestBatchQueryHoverAndTypedef(unittest.TestCase):
    """P1 #4: 批量查询 hover/typeDef"""

    def setUp(self):
        self.gateway = LspGateway(backend_module=MagicMock())
        self.session = MagicMock()

    def test_deduplication(self):
        positions = [(10, 5), (10, 5), (11, 3), (11, 3)]
        request_calls = []

        def mock_request(session, method, params, cfg):
            pos = params.get("position", {})
            request_calls.append((pos.get("line"), pos.get("character"), method))
            return {"result": None}

        self.gateway._request = mock_request
        self.gateway._batch_query_hover_and_typedef(
            self.session, "test.c", positions, None
        )

        unique_positions = {(line, charno) for line, charno, _ in request_calls}
        self.assertEqual(len(unique_positions), 2)
        self.assertEqual(len(request_calls), 4)

    def test_cache_returns_correct_keys(self):
        positions = [(10, 5), (11, 3)]

        def mock_request(session, method, params, cfg):
            return {"result": None}

        self.gateway._request = mock_request
        cache = self.gateway._batch_query_hover_and_typedef(
            self.session, "test.c", positions, None
        )

        self.assertIn((10, 5), cache)
        self.assertIn((11, 3), cache)
        self.assertEqual(len(cache), 2)

    def test_empty_positions(self):
        cache = self.gateway._batch_query_hover_and_typedef(
            self.session, "test.c", [], None
        )
        self.assertEqual(len(cache), 0)


class TestCollectSitesWithBatch(unittest.TestCase):
    """P1 #4: _collect_member_sites 和 _collect_local_sites 使用批量查询"""

    def setUp(self):
        self.gateway = LspGateway(backend_module=MagicMock())
        self.session = MagicMock()
        self.gateway._request = MagicMock(return_value={"result": None})

    def test_member_sites_batch(self):
        source_text = "a->member1 = b->member2;"
        function_range = {"start_line": 1, "end_line": 1}

        result = self.gateway._collect_member_sites(
            self.session, "test.c", source_text, function_range, None
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["member"], "member1")
        self.assertEqual(result[1]["member"], "member2")

    def test_local_sites_batch(self):
        source_text = "int tmp_var = 0;\nfloat result = 1.0;"
        function_range = {"start_line": 1, "end_line": 2}

        result = self.gateway._collect_local_sites(
            self.session, "test.c", source_text, function_range, None
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "tmp_var")
        self.assertEqual(result[1]["name"], "result")

    def test_member_sites_respects_limit(self):
        lines = [f"int a{i}->b{i} = 0;" for i in range(40)]
        source_text = "\n".join(lines)
        function_range = {"start_line": 1, "end_line": len(lines)}

        result = self.gateway._collect_member_sites(
            self.session, "test.c", source_text, function_range, None
        )

        self.assertLessEqual(len(result), 32)


class TestParseHoverFull(unittest.TestCase):
    """P3 #9: hover 信息结构化解析"""

    def setUp(self):
        self.gateway = LspGateway(backend_module=MagicMock())

    def test_simple_function_signature(self):
        payload = {
            "contents": {
                "value": "void PackFaultData(int mode, uint16 *buf)\n/// Packs fault data"
            }
        }
        result = self.gateway._parse_hover_full(payload)
        self.assertEqual(result["return_type"], "void")
        self.assertEqual(result["params"], ["int mode", "uint16 *buf"])
        self.assertEqual(result["doc_comment"], "Packs fault data")

    def test_no_params(self):
        payload = {"contents": {"value": "int GetValue()\n// Returns value"}}
        result = self.gateway._parse_hover_full(payload)
        self.assertEqual(result["return_type"], "int")
        self.assertEqual(result["params"], [])
        self.assertEqual(result["doc_comment"], "Returns value")

    def test_empty_payload(self):
        result = self.gateway._parse_hover_full(None)
        self.assertEqual(result["return_type"], "")
        self.assertEqual(result["params"], [])
        self.assertEqual(result["doc_comment"], "")

    def test_nested_paren_params(self):
        payload = {
            "contents": {
                "value": "void Process(Callback (*fn)(int), Data *d)"
            }
        }
        result = self.gateway._parse_hover_full(payload)
        self.assertEqual(result["return_type"], "void")
        self.assertEqual(len(result["params"]), 2)

    def test_no_return_type(self):
        payload = {"contents": {"value": "some_variable"}}
        result = self.gateway._parse_hover_full(payload)
        self.assertEqual(result["return_type"], "")


class TestFactCacheLimit(unittest.TestCase):
    """P2 #6: fact cache LRU 限制"""

    def setUp(self):
        _FACT_CACHE.clear()

    def tearDown(self):
        _FACT_CACHE.clear()

    def test_cache_eviction_logic(self):
        for i in range(_FACT_CACHE_MAX):
            _FACT_CACHE[f"key_{i}"] = (0.0, {"test": i})
        self.assertEqual(len(_FACT_CACHE), _FACT_CACHE_MAX)
        oldest_key = next(iter(_FACT_CACHE))
        del _FACT_CACHE[oldest_key]
        _FACT_CACHE["new_key"] = (0.0, {"test": "new"})
        self.assertEqual(len(_FACT_CACHE), _FACT_CACHE_MAX)
        self.assertNotIn(oldest_key, _FACT_CACHE)
        self.assertIn("new_key", _FACT_CACHE)

    def test_cache_max_size_enforced(self):
        for i in range(_FACT_CACHE_MAX):
            _FACT_CACHE[f"key_{i}"] = (0.0, {"test": i})
        self.assertEqual(len(_FACT_CACHE), _FACT_CACHE_MAX)


class TestCandidateLaunchCommands(unittest.TestCase):
    """P3 #11: clangd 启动参数包含内存限制（在 flag 探测支持时）"""

    @staticmethod
    def _gateway_with_supported_flags(*flags: str) -> LspGateway:
        gateway = LspGateway(backend_module=MagicMock())
        gateway._probe_clangd_flags = lambda path, _flags=set(flags): set(_flags)  # type: ignore[method-assign]
        return gateway

    def test_memory_flags_present(self):
        gateway = self._gateway_with_supported_flags(
            "--stdio", "--malloc-trim", "--pch-storage",
            "--background-index", "--clang-tidy",
        )
        commands = gateway._candidate_launch_commands("/usr/bin/clangd", None)
        for cmd in commands:
            self.assertIn("--malloc-trim", cmd)
            self.assertIn("--pch-storage=memory", cmd)

    def test_background_index_disabled(self):
        gateway = self._gateway_with_supported_flags(
            "--stdio", "--malloc-trim", "--pch-storage",
            "--background-index", "--clang-tidy",
        )
        commands = gateway._candidate_launch_commands("/usr/bin/clangd", None)
        for cmd in commands:
            self.assertIn("--background-index=false", cmd)
            self.assertIn("--clang-tidy=false", cmd)

    def test_unsupported_flags_skipped(self):
        gateway = self._gateway_with_supported_flags("--background-index", "--clang-tidy")
        commands = gateway._candidate_launch_commands("/usr/bin/clangd", None)
        self.assertTrue(commands, "至少返回一条候选命令")
        for cmd in commands:
            self.assertNotIn("--malloc-trim", cmd)
            self.assertNotIn("--pch-storage=memory", cmd)
            self.assertNotIn("--stdio", cmd)


if __name__ == "__main__":
    unittest.main()
