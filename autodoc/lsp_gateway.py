"""Gateway that manages local clangd sessions for fact extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any, Optional
from urllib.parse import quote, unquote, urlsplit

from ._legacy_support import app_root, legacy_backend
from . import utils as utils_module
from .compile_db import ensure_compile_database
from .lsp_transport import LspStdioTransport


_EXTERNAL_SNAPSHOTS: dict[str, dict[str, Any]] = {}
_GATEWAYS: dict[str, "LspSession"] = {}
_LOCK = threading.Lock()


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _path_to_lsp_uri(path: str) -> str:
    """Return a file URI that clangd accepts on POSIX and Windows paths."""
    raw = utils_module._safe_strip(path)
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        return raw
    if raw.startswith("\\\\") or raw.startswith("//"):
        unc = raw.replace("\\", "/").lstrip("/")
        host, _, share_path = unc.partition("/")
        return f"file://{quote(host, safe='')}/{quote(share_path, safe='/')}" if host else f"file:///{quote(share_path, safe='/')}"
    if _WINDOWS_DRIVE_RE.match(raw):
        normalized = raw.replace("\\", "/")
        return "file:///" + quote(normalized, safe="/:")
    return Path(raw).resolve().as_uri()


def _lsp_uri_to_path(uri: str) -> str:
    raw = utils_module._safe_strip(uri)
    if not raw.lower().startswith("file://"):
        return raw
    parts = urlsplit(raw)
    path = unquote(parts.path or "")
    if parts.netloc:
        return f"//{parts.netloc}{path}"
    if re.match(r"^/[A-Za-z]:/", path):
        return path[1:]
    return path


@dataclass
class LspSession:
    project_root: str
    transport: LspStdioTransport
    compile_db: dict[str, Any] = field(default_factory=dict)
    clangd_path: str = ""
    clangd_version: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)
    opened_documents: dict[str, int] = field(default_factory=dict)
    last_used: float = field(default_factory=time.time)

    @property
    def alive(self) -> bool:
        return self.transport.alive


class LspGateway:
    def __init__(self, *, backend_module=None) -> None:
        self._backend = backend_module or legacy_backend()

    def ensure_ready(
        self,
        project_root: str,
        cfg: Optional[Any] = None,
        *,
        source_files: Optional[list[str]] = None,
    ) -> Optional[LspSession]:
        root = os.path.abspath(project_root or os.getcwd())
        with _LOCK:
            session = _GATEWAYS.get(root)
            if session and session.alive:
                if source_files and str((session.compile_db or {}).get("mode")) == "missing":
                    session.transport.close()
                    _GATEWAYS.pop(root, None)
                else:
                    session.last_used = time.time()
                    return session
            if session and not session.alive:
                _GATEWAYS.pop(root, None)
                utils_module.vlog(cfg, f"[LSP] clangd 进程已退出，尝试重启...")
        clangd_path = self._resolve_clangd_path(cfg)
        if not clangd_path:
            return None
        compile_db = ensure_compile_database(root, cfg, source_files=source_files)
        workdir = compile_db.get("directory") or root
        initialize: dict[str, Any] = {}
        transport: Optional[LspStdioTransport] = None
        launch_cmd = []
        for cmd in self._candidate_launch_commands(clangd_path, compile_db):
            candidate = LspStdioTransport(cmd, cwd=workdir, backend_module=self._backend)
            if not candidate.start():
                candidate.close()
                continue
            trial = candidate.request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": _path_to_lsp_uri(root),
                    "capabilities": {
                        "textDocument": {
                            "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                            "semanticTokens": {"requests": {"full": True}},
                        }
                    },
                    "workspaceFolders": [{"uri": _path_to_lsp_uri(root), "name": Path(root).name}],
                },
                timeout_ms=utils_module.cfg_get_int(cfg, "logic_lsp_initialize_timeout_ms", 8000),
            )
            if trial.get("ok"):
                transport = candidate
                initialize = trial
                launch_cmd = cmd
                break
            stderr_text = "\n".join(candidate.stderr_tail).lower()
            candidate.close()
            if ("unknown command line argument '--stdio'" in stderr_text) or ("did you mean '--sync'" in stderr_text):
                continue
        if transport is None:
            return None
        transport.notify("initialized", {})
        session = LspSession(
            project_root=root,
            transport=transport,
            compile_db=compile_db,
            clangd_path=clangd_path,
            clangd_version=utils_module._safe_strip((initialize.get("result") or {}).get("serverInfo", {}).get("version")),
            capabilities=dict((initialize.get("result") or {}).get("capabilities") or {}),
        )
        if launch_cmd:
            session.capabilities["_launch_cmd"] = list(launch_cmd)
        with _LOCK:
            _GATEWAYS[root] = session
        return session

    def _candidate_launch_commands(self, clangd_path: str, compile_db: Optional[dict[str, Any]] = None) -> list[list[str]]:
        compile_db_dir = utils_module._safe_strip((compile_db or {}).get("directory"))
        compile_db_flags = [f"--compile-commands-dir={compile_db_dir}"] if compile_db_dir else []
        supported = self._probe_clangd_flags(clangd_path)
        mem_flags: list[str] = []
        if "--malloc-trim" in supported:
            mem_flags.append("--malloc-trim")
        if "--pch-storage" in supported:
            mem_flags.append("--pch-storage=memory")
        base_flags = ["--background-index=false", "--clang-tidy=false"] + mem_flags
        base = [clangd_path] + compile_db_flags + base_flags
        cmds: list[list[str]] = []
        if "--stdio" in supported:
            cmds.append([clangd_path, "--stdio"] + compile_db_flags + base_flags)
        cmds.append(base)
        return cmds

    def _probe_clangd_flags(self, clangd_path: str) -> set[str]:
        cached = getattr(self, "_flag_cache", None)
        if cached and cached.get("path") == clangd_path:
            return cached["flags"]
        flags: set[str] = set()
        try:
            import subprocess
            out = subprocess.run(
                [clangd_path, "--help"],
                capture_output=True,
                timeout=5,
                encoding="utf-8",
                errors="ignore",
            )
            text = (out.stdout or "") + "\n" + (out.stderr or "")
            for token in ("--stdio", "--malloc-trim", "--pch-storage", "--background-index", "--clang-tidy", "--compile-commands-dir"):
                if token in text:
                    flags.add(token)
        except Exception:
            pass
        self._flag_cache = {"path": clangd_path, "flags": flags}
        return flags

    def collect_function_bundle(self, func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
        file_context = dict((func_data or {}).get("file_context") or {})
        source_file = utils_module._safe_strip(file_context.get("source_file"))
        if not source_file or not os.path.exists(source_file):
            return {}
        project_root = utils_module.cfg_get_str(cfg, "project_root", "") or os.path.dirname(source_file)
        session = self.ensure_ready(project_root, cfg, source_files=[source_file])
        if session is None:
            return {}
        source_text, version = self._resolve_document_text(source_file)
        if not source_text:
            source_text = self._backend.load_c_file(source_file)
        self._open_or_update_document(session, source_file, source_text, version)
        document_symbols = self._request(session, "textDocument/documentSymbol", {"textDocument": {"uri": _path_to_lsp_uri(source_file)}}, cfg)
        semantic_tokens = self._request(session, "textDocument/semanticTokens/full", {"textDocument": {"uri": _path_to_lsp_uri(source_file)}}, cfg)
        function_range = self._guess_function_range(func_data, source_text, document_symbols)
        func_name = utils_module._safe_strip(dict((func_data or {}).get("func_info") or {}).get("func_name"))
        calls = self._collect_call_sites(session, source_file, source_text, function_range, cfg, owner_func=func_name)
        members = self._collect_member_sites(session, source_file, source_text, function_range, cfg)
        locals_ = self._collect_local_sites(session, source_file, source_text, function_range, cfg)
        session.last_used = time.time()
        return {
            "source_text": source_text,
            "document_symbols": document_symbols,
            "semantic_tokens": semantic_tokens,
            "function_range": function_range,
            "calls": calls,
            "members": members,
            "locals": locals_,
            "compile_flags_hash": utils_module._safe_strip(session.compile_db.get("flags_hash")),
            "clangd_version": session.clangd_version,
        }

    def update_document_snapshot(self, source_file: str, text: str, version: int) -> None:
        register_external_snapshot(source_file, text, version)

    def shutdown_idle_sessions(self, idle_seconds: int = 120) -> None:
        now = time.time()
        with _LOCK:
            targets = [key for key, session in _GATEWAYS.items() if (not session.alive) or (now - session.last_used >= idle_seconds)]
            for key in targets:
                session = _GATEWAYS.pop(key, None)
                if session is not None:
                    session.transport.close()

    def shutdown(self) -> None:
        with _LOCK:
            sessions = list(_GATEWAYS.values())
            _GATEWAYS.clear()
        for session in sessions:
            session.transport.close()

    def _resolve_clangd_path(self, cfg: Optional[Any]) -> str:
        repo_root = Path(app_root())
        explicit = utils_module.cfg_get_str(cfg, "logic_lsp_clangd_path", "")
        if explicit:
            path = Path(explicit)
            if not path.is_absolute():
                path = repo_root / path
            if path.exists():
                return str(path.resolve())
        for rel in (
            "tools/clangd/win7/clangd.exe",
            "tools/clangd/win7/llvm/bin/clangd.exe",
            "tools/clangd/win7/bin/clangd.exe",
            "tools/clangd/clangd.exe",
            "tools/clangd/win7/clangd",
            "tools/clangd/clangd",
        ):
            candidate = repo_root / rel
            if candidate.exists():
                return str(candidate.resolve())
        system = shutil.which("clangd")
        if system:
            return system
        return ""

    def _resolve_document_text(self, source_file: str) -> tuple[str, int]:
        key = os.path.abspath(source_file)
        snapshot = dict(_EXTERNAL_SNAPSHOTS.get(key) or {})
        if snapshot:
            return utils_module._safe_text(snapshot.get("text")), int(snapshot.get("version", 1) or 1)
        try:
            return self._backend.load_c_file(source_file), 1
        except Exception:
            return "", 1

    def _open_or_update_document(self, session: LspSession, source_file: str, source_text: str, version: int) -> None:
        uri = _path_to_lsp_uri(source_file)
        current_version = session.opened_documents.get(uri)
        payload = {
            "textDocument": {
                "uri": uri,
                "languageId": "c",
                "version": int(version or 1),
                "text": source_text,
            }
        }
        if current_version is None:
            session.transport.notify("textDocument/didOpen", payload)
        else:
            session.transport.notify(
                "textDocument/didChange",
                {
                    "textDocument": {"uri": uri, "version": int(version or current_version + 1)},
                    "contentChanges": [{"text": source_text}],
                },
            )
        session.opened_documents[uri] = int(version or max(1, (current_version or 0) + 1))

    def _request(self, session: LspSession, method: str, params: dict[str, Any], cfg: Optional[Any]) -> Any:
        result = session.transport.request(method, params, timeout_ms=utils_module.cfg_get_int(cfg, "logic_lsp_request_timeout_ms", 2000))
        return result.get("result") if result.get("ok") else {}

    def _guess_function_range(self, func_data: dict[str, Any], source_text: str, symbols: Any) -> dict[str, int]:
        func_info = dict((func_data or {}).get("func_info") or {})
        func_name = utils_module._safe_strip(func_info.get("func_name"))
        flat = self._flatten_symbols(list(symbols or []))
        for item in flat:
            if utils_module._safe_strip(item.get("name")) == func_name and int(item.get("kind", 0) or 0) in {6, 12}:
                rng = dict(item.get("range") or {})
                return {
                    "start_line": int(dict(rng.get("start") or {}).get("line", 0) or 0) + 1,
                    "end_line": int(dict(rng.get("end") or {}).get("line", 0) or 0) + 1,
                }
        prototype = utils_module._safe_strip(func_info.get("prototype"))
        for idx, line in enumerate(source_text.splitlines(), start=1):
            if prototype and prototype in line:
                return {"start_line": idx, "end_line": min(len(source_text.splitlines()), idx + len((func_data.get("body") or "").splitlines()) + 1)}
            if func_name and re.search(rf"\b{re.escape(func_name)}\s*\(", line):
                return {"start_line": idx, "end_line": len(source_text.splitlines())}
        return {"start_line": 1, "end_line": len(source_text.splitlines())}

    def _flatten_symbols(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            out.append(item)
            out.extend(self._flatten_symbols(list(item.get("children") or [])))
        return out

    def _batch_query_hover_and_typedef(
        self,
        session: LspSession,
        source_file: str,
        positions: list[tuple[int, int]],
        cfg: Optional[Any],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """批量查询多个位置的 hover + typeDefinition，结果按位置缓存。"""
        cache: dict[tuple[int, int], dict[str, Any]] = {}
        seen: set[tuple[int, int]] = set()
        for lineno, charno in positions:
            key = (lineno, charno)
            if key in seen:
                continue
            seen.add(key)
            params = self._position_params(source_file, lineno, charno)
            hover = self._request(session, "textDocument/hover", params, cfg)
            type_definition = self._request(session, "textDocument/typeDefinition", params, cfg)
            cache[key] = {"hover": hover, "type_definition": type_definition}
        return cache

    def _collect_call_sites(
        self,
        session: LspSession,
        source_file: str,
        source_text: str,
        function_range: dict[str, int],
        cfg: Optional[Any],
        *,
        owner_func: str = "",
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        pattern = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
        for lineno, line in self._iter_function_lines(source_text, function_range):
            for match in pattern.finditer(line):
                callee = utils_module._safe_strip(match.group(1))
                if not callee or callee in self._backend._C_KEYWORDS or callee == "sizeof":
                    continue
                stripped = utils_module._safe_strip(line)
                if owner_func and callee == owner_func and lineno <= int(function_range.get("start_line", 0) or 0) + 1:
                    continue
                if self._looks_like_function_declaration(stripped, callee):
                    continue
                params = self._position_params(source_file, lineno, match.start(1))
                hover = self._request(session, "textDocument/hover", params, cfg)
                definition = self._request(session, "textDocument/definition", params, cfg)
                type_definition = self._request(session, "textDocument/typeDefinition", params, cfg)
                references = self._request(
                    session,
                    "textDocument/references",
                    dict(params, context={"includeDeclaration": False}),
                    cfg,
                )
                call_prepare = self._request(session, "textDocument/prepareCallHierarchy", params, cfg)
                outgoing = {}
                if isinstance(call_prepare, list) and call_prepare:
                    outgoing = self._request(session, "callHierarchy/outgoingCalls", {"item": call_prepare[0]}, cfg)
                hover_full = self._parse_hover_full(hover)
                out.append(
                    {
                        "callee": callee,
                        "call_text": utils_module._safe_strip(line).rstrip(";"),
                        "signature": self._safe_hover_signature(hover),
                        "range": {
                            "start": {"line": lineno - 1, "character": match.start(1)},
                            "end": {"line": lineno - 1, "character": match.end(1)},
                        },
                        "hover": {
                            "signature": self._safe_hover_signature(hover),
                            "detail": self._safe_hover_detail(hover),
                            "comment": self._safe_hover_comment(hover),
                            "return_type": hover_full.get("return_type", ""),
                            "params": hover_full.get("params", []),
                            "doc_comment": hover_full.get("doc_comment", ""),
                        },
                        "definition": self._normalize_location(definition),
                        "type_definition": self._normalize_location(type_definition),
                        "references": references if isinstance(references, list) else [],
                        "call_hierarchy": self._normalize_call_hierarchy(outgoing),
                    }
                )
        return out[:24]

    def _looks_like_function_declaration(self, line: str, callee: str) -> bool:
        text = utils_module._safe_strip(line)
        if not text or not callee:
            return False
        if text.endswith(";"):
            return False
        return bool(
            re.match(
                rf"^(?:[A-Za-z_]\w*|\*|\s)+\b{re.escape(callee)}\s*\([^;]*\)\s*(?:\{{)?$",
                text,
            )
        )

    def _collect_member_sites(self, session: LspSession, source_file: str, source_text: str, function_range: dict[str, int], cfg: Optional[Any]) -> list[dict[str, Any]]:
        pattern = re.compile(r"(?P<base>[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)\s*(?:\.|->)\s*(?P<member>[A-Za-z_]\w*)")
        hits: list[tuple[re.Match, int, str]] = []
        for lineno, line in self._iter_function_lines(source_text, function_range):
            for match in pattern.finditer(line):
                hits.append((match, lineno, line))
            if len(hits) >= 32:
                break

        positions = [(lineno, match.start("member")) for match, lineno, _ in hits]
        cache = self._batch_query_hover_and_typedef(session, source_file, positions, cfg)

        out: list[dict[str, Any]] = []
        for match, lineno, line in hits:
            cached = cache.get((lineno, match.start("member"))) or {}
            hover = cached.get("hover")
            type_definition = cached.get("type_definition")
            out.append(
                {
                    "base": utils_module._safe_strip(match.group("base")),
                    "member": utils_module._safe_strip(match.group("member")),
                    "access_text": utils_module._safe_strip(match.group(0)),
                    "owner_type": self._extract_owner_type(type_definition, hover),
                    "range": {
                        "start": {"line": lineno - 1, "character": match.start("member")},
                        "end": {"line": lineno - 1, "character": match.end("member")},
                    },
                    "hover": hover if isinstance(hover, dict) else {},
                    "type_definition": self._normalize_location(type_definition),
                }
            )
        return out[:32]

    def _collect_local_sites(self, session: LspSession, source_file: str, source_text: str, function_range: dict[str, int], cfg: Optional[Any]) -> list[dict[str, Any]]:
        decl_re = re.compile(r"^\s*(?:static\s+)?(?:const\s+)?(?P<type>[A-Za-z_]\w*(?:\s*[*]+)?)\s+(?P<name>[A-Za-z_]\w*)\b")
        seen: set[str] = set()
        hits: list[tuple[re.Match, int, str]] = []
        for lineno, line in self._iter_function_lines(source_text, function_range):
            match = decl_re.match(line)
            if not match:
                continue
            name = utils_module._safe_strip(match.group("name"))
            if not name or name in seen:
                continue
            seen.add(name)
            hits.append((match, lineno, line))
            if len(hits) >= 48:
                break

        positions = [(lineno, match.start("name")) for match, lineno, _ in hits]
        cache = self._batch_query_hover_and_typedef(session, source_file, positions, cfg)

        out: list[dict[str, Any]] = []
        for match, lineno, line in hits:
            cached = cache.get((lineno, match.start("name"))) or {}
            hover = cached.get("hover")
            type_definition = cached.get("type_definition")
            out.append(
                {
                    "name": utils_module._safe_strip(match.group("name")),
                    "decl_type": utils_module._safe_strip(match.group("type")),
                    "decl_text": utils_module._safe_strip(line).rstrip(";"),
                    "range": {
                        "start": {"line": lineno - 1, "character": match.start("name")},
                        "end": {"line": lineno - 1, "character": match.end("name")},
                    },
                    "hover": hover if isinstance(hover, dict) else {},
                    "type_definition": self._normalize_location(type_definition),
                }
            )
        return out[:48]

    def _iter_function_lines(self, source_text: str, function_range: dict[str, int]):
        lines = source_text.splitlines()
        start = max(1, int(function_range.get("start_line", 1) or 1))
        end = min(len(lines), max(start, int(function_range.get("end_line", len(lines)) or len(lines))))
        for lineno in range(start, end + 1):
            yield lineno, lines[lineno - 1]

    def _position_params(self, source_file: str, lineno: int, charno: int) -> dict[str, Any]:
        return {
            "textDocument": {"uri": _path_to_lsp_uri(source_file)},
            "position": {"line": max(0, lineno - 1), "character": max(0, charno)},
        }

    def _normalize_location(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            return {}
        target = dict(payload.get("targetUri") and {"uri": payload.get("targetUri"), "range": payload.get("targetRange")} or payload)
        uri = utils_module._safe_strip(target.get("uri"))
        range_payload = dict(target.get("range") or {})
        return {
            "uri": uri,
            "file": _lsp_uri_to_path(uri),
            "line": int(dict(range_payload.get("start") or {}).get("line", 0) or 0) + 1,
        }

    def _normalize_call_hierarchy(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, list) and payload:
            item = dict(payload[0] or {})
            return {"name": utils_module._safe_strip((item.get("to") or {}).get("name") or item.get("name")), "detail": utils_module._safe_strip((item.get("to") or {}).get("detail") or item.get("detail"))}
        return {}

    def _safe_hover_signature(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        contents = payload.get("contents")
        if isinstance(contents, dict):
            value = utils_module._safe_text(contents.get("value"))
            return value.splitlines()[0] if value else ""
        if isinstance(contents, list) and contents:
            first = contents[0]
            if isinstance(first, dict):
                value = utils_module._safe_text(first.get("value"))
                return value.splitlines()[0] if value else ""
            return utils_module._safe_text(first).splitlines()[0]
        return utils_module._safe_text(contents).splitlines()[0] if contents else ""

    def _safe_hover_detail(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        contents = payload.get("contents")
        if isinstance(contents, dict):
            return utils_module._safe_text(contents.get("value"))
        if isinstance(contents, list):
            return "\n".join(utils_module._safe_text((item or {}).get("value") if isinstance(item, dict) else item) for item in contents)
        return utils_module._safe_text(contents)

    def _safe_hover_comment(self, payload: Any) -> str:
        detail = self._safe_hover_detail(payload)
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        return lines[1] if len(lines) > 1 else ""

    def _extract_owner_type(self, type_definition: Any, hover: Any) -> str:
        normalized = self._normalize_location(type_definition)
        if normalized.get("file"):
            return Path(str(normalized.get("file"))).stem
        detail = self._safe_hover_detail(hover)
        for line in detail.splitlines():
            text = line.strip()
            if text.startswith("struct "):
                return text.split()[1].strip("{ ").rstrip("*")
        return ""

    def _parse_hover_full(self, payload: Any) -> dict[str, Any]:
        """解析完整 hover 信息，返回结构化数据。"""
        if not isinstance(payload, dict):
            return {"signature": "", "return_type": "", "params": [], "doc_comment": ""}
        detail = self._safe_hover_detail(payload)
        signature = self._safe_hover_signature(payload)
        return_type = ""
        params: list[str] = []
        doc_comment = ""

        if signature:
            match = re.match(r"^(\S+)\s+\w+\s*\(", signature)
            if match:
                return_type = match.group(1)

        if "(" in detail and ")" in detail:
            paren_start = detail.find("(")
            paren_end = -1
            depth = 0
            for i in range(paren_start, len(detail)):
                if detail[i] == "(":
                    depth += 1
                elif detail[i] == ")":
                    depth -= 1
                    if depth == 0:
                        paren_end = i
                        break
            if paren_start >= 0 and paren_end > paren_start:
                params_str = detail[paren_start + 1 : paren_end].strip()
                if params_str:
                    depth = 0
                    current = ""
                    for ch in params_str:
                        if ch == "(":
                            depth += 1
                            current += ch
                        elif ch == ")":
                            depth -= 1
                            current += ch
                        elif ch == "," and depth == 0:
                            params.append(current.strip())
                            current = ""
                        else:
                            current += ch
                    if current.strip():
                        params.append(current.strip())

        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                doc_comment = line.lstrip("/* ").rstrip(" */")
                break

        return {
            "signature": signature,
            "return_type": return_type,
            "params": params,
            "doc_comment": doc_comment,
        }


def register_external_snapshot(source_file: str, text: str, version: int, project_root: Optional[str] = None) -> None:
    key = os.path.abspath(source_file or "")
    if not key:
        return
    _EXTERNAL_SNAPSHOTS[key] = {
        "text": str(text or ""),
        "version": int(version or 1),
        "project_root": os.path.abspath(project_root) if project_root else "",
        "updated_at": time.time(),
    }


def get_lsp_gateway(*, backend_module=None) -> LspGateway:
    return LspGateway(backend_module=backend_module)


__all__ = ["LspGateway", "LspSession", "get_lsp_gateway", "register_external_snapshot"]
