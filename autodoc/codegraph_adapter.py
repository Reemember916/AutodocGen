"""CodeGraph CLI and SQLite integration helpers.

The CLI is used only to create/update the local index.  Once the index exists,
relationship reads go straight to the SQLite database so project generation does
not spawn a Node process for every function.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
import shutil
import sqlite3
import subprocess
from typing import Any, Iterable, Optional

from . import utils


CALL_EDGE_KINDS = ("calls", "references", "imports")


class CodeGraphError(RuntimeError):
    """Base CodeGraph integration error."""


class CodeGraphUnavailable(CodeGraphError):
    """Raised when CodeGraph is required but cannot be used."""


class CodeGraphCommandError(CodeGraphError):
    """Raised when a CodeGraph command fails or returns malformed data."""


@dataclass
class CodeGraphStatus:
    mode: str = "auto"
    enabled: bool = False
    available: bool = False
    executable: str = ""
    project_root: str = ""
    index_path: str = ""
    initialized: bool = False
    indexed: bool = False
    source: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extra(cfg: Optional[Any]) -> dict[str, Any]:
    return dict(getattr(cfg, "extra_params", {}) or {}) if cfg is not None else {}


def _cfg_value(cfg: Optional[Any], name: str, default: Any = "") -> Any:
    if cfg is not None and hasattr(cfg, name):
        value = getattr(cfg, name)
        if value not in (None, ""):
            return value
    extra = _extra(cfg)
    if name in extra:
        return extra.get(name)
    return default


def normalize_mode(value: Any) -> str:
    text = str(value or "auto").strip().lower()
    if text in {"0", "false", "no", "disabled", "disable", "off"}:
        return "off"
    if text in {"1", "true", "yes", "enabled", "enable", "on", "auto"}:
        return "auto"
    if text in {"force", "required", "require"}:
        return "force"
    return "auto"


def graph_mode_from_cfg(cfg: Optional[Any]) -> str:
    return normalize_mode(_cfg_value(cfg, "codegraph_mode", "auto"))


def auto_index_enabled(cfg: Optional[Any]) -> bool:
    value = _cfg_value(cfg, "codegraph_auto_index", "1")
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def resolve_executable(cfg: Optional[Any] = None) -> str:
    explicit = str(_cfg_value(cfg, "codegraph_path", "") or "").strip()
    if explicit:
        expanded = os.path.abspath(os.path.expanduser(explicit))
        return expanded if os.path.exists(expanded) else ""
    return shutil.which("codegraph") or ""


def get_index_db_path(project_root: str) -> str:
    return os.path.join(os.path.abspath(project_root), ".codegraph", "codegraph.db")


def _run_command(args: list[str], *, timeout: float, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def run_json_command(args: list[str], *, timeout: float = 60.0, cwd: Optional[str] = None) -> Any:
    proc = _run_command(args, timeout=timeout, cwd=cwd)
    if proc.returncode != 0:
        raise CodeGraphCommandError((proc.stderr or proc.stdout or "CodeGraph command failed").strip())
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        raise CodeGraphCommandError(f"CodeGraph returned invalid JSON: {exc}") from exc


def _timeout(cfg: Optional[Any], key: str, default: int) -> float:
    try:
        return float(_cfg_value(cfg, key, default) or default)
    except Exception:
        return float(default)


def prepare_project_index(project_root: str, cfg: Optional[Any] = None) -> CodeGraphStatus:
    root = os.path.abspath(project_root)
    mode = graph_mode_from_cfg(cfg)
    db_path = get_index_db_path(root)
    status = CodeGraphStatus(
        mode=mode,
        project_root=root,
        index_path=db_path,
        initialized=os.path.exists(db_path),
    )
    if mode == "off":
        status.message = "CodeGraph disabled"
        return status

    cached = getattr(cfg, "_codegraph_status", None) if cfg is not None else None
    if isinstance(cached, dict) and cached.get("project_root") == root and cached.get("mode") == mode:
        return CodeGraphStatus(**{k: cached.get(k) for k in CodeGraphStatus.__dataclass_fields__})

    exe = resolve_executable(cfg)
    status.executable = exe
    status.available = bool(exe)
    if not exe:
        status.message = "CodeGraph executable not found"
        if mode == "force":
            raise CodeGraphUnavailable(status.message)
        _store_status(cfg, status)
        return status

    try:
        if not os.path.exists(db_path):
            if not auto_index_enabled(cfg):
                status.message = "CodeGraph index is missing and auto-index is disabled"
                if mode == "force":
                    raise CodeGraphUnavailable(status.message)
                _store_status(cfg, status)
                return status
            proc = _run_command(
                [exe, "init", root, "-i"],
                timeout=_timeout(cfg, "codegraph_index_timeout_sec", 300),
                cwd=root,
            )
        else:
            proc = _run_command(
                [exe, "sync", root, "--quiet"],
                timeout=_timeout(cfg, "codegraph_sync_timeout_sec", 180),
                cwd=root,
            )
        if proc.returncode != 0:
            raise CodeGraphCommandError((proc.stderr or proc.stdout or "CodeGraph indexing failed").strip())
        status.initialized = os.path.exists(db_path)
        status.indexed = status.initialized
        status.enabled = status.initialized
        status.source = "codegraph"
        status.message = "CodeGraph index ready" if status.enabled else "CodeGraph index was not created"
    except Exception as exc:
        status.message = str(exc)
        if mode == "force":
            raise
    _store_status(cfg, status)
    return status


def _store_status(cfg: Optional[Any], status: CodeGraphStatus) -> None:
    if cfg is None:
        return
    try:
        cfg._codegraph_status = status.to_dict()
        cfg._codegraph_project_enabled = bool(status.enabled)
    except Exception:
        pass


class CodeGraphAdapter:
    def __init__(self, project_root: str, cfg: Optional[Any] = None):
        self.project_root = os.path.abspath(project_root)
        self.cfg = cfg
        self.status = prepare_project_index(self.project_root, cfg)
        self.db_path = get_index_db_path(self.project_root)

    def query(self, search: str, *, kind: str = "", limit: int = 10) -> Any:
        if not self.status.executable:
            raise CodeGraphUnavailable("CodeGraph executable not found")
        args = [self.status.executable, "query", search, "--path", self.project_root, "--limit", str(limit), "--json"]
        if kind:
            args.extend(["--kind", kind])
        return run_json_command(args, timeout=_timeout(self.cfg, "codegraph_query_timeout_sec", 60), cwd=self.project_root)

    def callers(self, symbol: str, *, limit: int = 20) -> Any:
        return self._graph_command("callers", symbol, "--limit", str(limit))

    def callees(self, symbol: str, *, limit: int = 20) -> Any:
        return self._graph_command("callees", symbol, "--limit", str(limit))

    def impact(self, symbol: str, *, depth: int = 2) -> Any:
        return self._graph_command("impact", symbol, "--depth", str(depth))

    def _graph_command(self, command: str, symbol: str, *extra_args: str) -> Any:
        if not self.status.executable:
            raise CodeGraphUnavailable("CodeGraph executable not found")
        args = [self.status.executable, command, symbol, "--path", self.project_root, *extra_args, "--json"]
        return run_json_command(args, timeout=_timeout(self.cfg, "codegraph_query_timeout_sec", 60), cwd=self.project_root)

    def enrich_entries(self, entries: Iterable[dict[str, Any]], *, depth: int = 2, max_nodes: int = 40) -> None:
        if not self.status.enabled or not os.path.exists(self.db_path):
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            for entry in entries:
                self._enrich_entry(conn, entry, depth=depth, max_nodes=max_nodes)
        finally:
            conn.close()

    def _enrich_entry(self, conn: sqlite3.Connection, entry: dict[str, Any], *, depth: int, max_nodes: int) -> None:
        func_info = dict((entry or {}).get("func_info") or {})
        file_context = dict((entry or {}).get("file_context") or {})
        name = utils._safe_strip(func_info.get("func_name"))
        source_file = utils._safe_strip(file_context.get("source_file"))
        if not name:
            return
        node = self._find_node(conn, name, source_file)
        status = self.status.to_dict()
        if not node:
            status["message"] = "CodeGraph node not found"
            file_context["codegraph_status"] = status
            entry["file_context"] = file_context
            return
        callers = self._neighbors(conn, node["id"], incoming=True, limit=max_nodes)
        callees = self._neighbors(conn, node["id"], incoming=False, limit=max_nodes)
        impact = self._impact(conn, node["id"], depth=max(1, int(depth or 1)), limit=max_nodes)
        caller_names = _unique([item.get("name", "") for item in callers])
        callee_names = _unique([item.get("name", "") for item in callees])
        if caller_names:
            file_context["caller_funcs"] = caller_names
        if callee_names:
            file_context["callee_funcs"] = callee_names
        file_context["codegraph_node"] = _public_node(node)
        file_context["codegraph_callers"] = callers
        file_context["codegraph_callees"] = callees
        file_context["codegraph_impact"] = impact
        file_context["codegraph_status"] = status
        entry["file_context"] = file_context

    def _find_node(self, conn: sqlite3.Connection, name: str, source_file: str) -> Optional[sqlite3.Row]:
        rel_path = ""
        if source_file:
            try:
                rel_path = os.path.relpath(os.path.abspath(source_file), self.project_root).replace(os.sep, "/")
            except Exception:
                rel_path = source_file.replace(os.sep, "/")
        rows = []
        if rel_path:
            rows = conn.execute(
                """
                SELECT * FROM nodes
                WHERE name = ? AND file_path = ? AND kind IN ('function', 'method')
                ORDER BY start_line ASC
                LIMIT 5
                """,
                (name, rel_path),
            ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT * FROM nodes
                WHERE name = ? AND kind IN ('function', 'method')
                ORDER BY CASE WHEN file_path = ? THEN 0 ELSE 1 END, start_line ASC
                LIMIT 5
                """,
                (name, rel_path),
            ).fetchall()
        return rows[0] if rows else None

    def _neighbors(self, conn: sqlite3.Connection, node_id: str, *, incoming: bool, limit: int) -> list[dict[str, Any]]:
        source_col, target_col = ("source", "target") if not incoming else ("target", "source")
        placeholders = ",".join("?" for _ in CALL_EDGE_KINDS)
        rows = conn.execute(
            f"""
            SELECT n.*, e.kind AS edge_kind, e.line AS edge_line, e.col AS edge_col, e.provenance AS edge_provenance
            FROM edges e
            JOIN nodes n ON n.id = e.{target_col}
            WHERE e.{source_col} = ? AND e.kind IN ({placeholders})
            ORDER BY n.file_path, n.start_line
            LIMIT ?
            """,
            (node_id, *CALL_EDGE_KINDS, max(1, int(limit or 1))),
        ).fetchall()
        return [_public_node(row) for row in rows]

    def _impact(self, conn: sqlite3.Connection, node_id: str, *, depth: int, limit: int) -> list[dict[str, Any]]:
        seen = {node_id}
        queue: list[tuple[str, int]] = [(node_id, 0)]
        out: list[dict[str, Any]] = []
        while queue and len(out) < limit:
            current, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue
            rows = conn.execute(
                """
                SELECT n.*, e.kind AS edge_kind, e.line AS edge_line, e.col AS edge_col, e.provenance AS edge_provenance
                FROM edges e
                JOIN nodes n ON n.id = e.source
                WHERE e.target = ? AND e.kind != 'contains'
                ORDER BY n.file_path, n.start_line
                LIMIT ?
                """,
                (current, max(1, int(limit or 1))),
            ).fetchall()
            for row in rows:
                row_id = row["id"]
                if row_id in seen:
                    continue
                seen.add(row_id)
                item = _public_node(row)
                item["depth"] = current_depth + 1
                out.append(item)
                queue.append((row_id, current_depth + 1))
                if len(out) >= limit:
                    break
        return out


def _public_node(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": utils._safe_strip(data.get("id")),
        "name": utils._safe_strip(data.get("name")),
        "kind": utils._safe_strip(data.get("kind")),
        "qualifiedName": utils._safe_strip(data.get("qualified_name")),
        "filePath": utils._safe_strip(data.get("file_path")),
        "startLine": int(data.get("start_line") or 0),
        "endLine": int(data.get("end_line") or 0),
        "signature": utils._safe_strip(data.get("signature")),
        "edgeKind": utils._safe_strip(data.get("edge_kind")),
        "edgeLine": int(data.get("edge_line") or 0),
        "edgeProvenance": utils._safe_strip(data.get("edge_provenance")),
    }


def _unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = utils._safe_strip(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def enrich_function_entries(entries: Iterable[dict[str, Any]], project_root: str, cfg: Optional[Any] = None) -> dict[str, Any]:
    if cfg is not None and not bool(getattr(cfg, "_codegraph_project_enabled", False)):
        return dict(getattr(cfg, "_codegraph_status", {}) or {})
    adapter = CodeGraphAdapter(project_root, cfg)
    if not adapter.status.enabled:
        return adapter.status.to_dict()
    depth = int(_cfg_value(cfg, "graph_depth", 2) or 2)
    max_nodes = int(_cfg_value(cfg, "graph_max_nodes", 40) or 40)
    adapter.enrich_entries(entries, depth=depth, max_nodes=max_nodes)
    return adapter.status.to_dict()


__all__ = [
    "CodeGraphAdapter",
    "CodeGraphCommandError",
    "CodeGraphError",
    "CodeGraphStatus",
    "CodeGraphUnavailable",
    "enrich_function_entries",
    "get_index_db_path",
    "graph_mode_from_cfg",
    "prepare_project_index",
    "resolve_executable",
    "run_json_command",
]
