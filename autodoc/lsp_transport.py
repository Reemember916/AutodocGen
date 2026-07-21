"""Minimal JSON-RPC over stdio transport for local clangd sessions."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from queue import Queue
from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import utils as utils_module


class LspStdioTransport:
    """Thin stdio JSON-RPC client used by the gateway."""

    def __init__(
        self,
        cmd: list[str],
        *,
        cwd: str = "",
        env: Optional[dict[str, str]] = None,
        backend_module=None,
    ) -> None:
        self._backend = backend_module or legacy_backend()
        self._cmd = list(cmd or [])
        self._cwd = cwd or None
        self._env = dict(env or {}) or None
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._lock = threading.Lock()
        self._pending: dict[int, Queue[Any]] = {}
        self._seq = 0
        self._closed = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._stderr_reader: Optional[threading.Thread] = None
        self._stderr_lines: list[str] = []

    @property
    def alive(self) -> bool:
        return bool(self._proc is not None and self._proc.poll() is None and not self._closed.is_set())

    @property
    def stderr_tail(self) -> list[str]:
        return list(self._stderr_lines[-12:])

    def start(self) -> bool:
        if self.alive:
            return True
        if not self._cmd:
            return False
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                cwd=self._cwd,
                env=self._env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except Exception:
            self._proc = None
            return False
        self._closed.clear()
        self._reader = threading.Thread(target=self._read_stdout_loop, name="lsp-stdout", daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr_loop, name="lsp-stderr", daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        return True

    def request(self, method: str, params: Optional[dict[str, Any]] = None, timeout_ms: int = 2000) -> dict[str, Any]:
        if not self.start():
            return {"ok": False, "error": "transport_not_started", "result": None}
        req_id = self._next_id()
        queue: Queue[Any] = Queue(maxsize=1)
        self._pending[req_id] = queue
        payload = {"jsonrpc": "2.0", "id": req_id, "method": str(method or ""), "params": params or {}}
        if not self._send(payload):
            self._pending.pop(req_id, None)
            return {"ok": False, "error": "send_failed", "result": None}
        try:
            result = queue.get(timeout=max(0.01, float(timeout_ms or 0) / 1000.0))
        except Exception:
            self._pending.pop(req_id, None)
            return {"ok": False, "error": "timeout", "result": None}
        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid_response", "result": None}
        if result.get("error") is not None:
            return {"ok": False, "error": result.get("error"), "result": result.get("result")}
        return {"ok": True, "error": None, "result": result.get("result")}

    def notify(self, method: str, params: Optional[dict[str, Any]] = None) -> bool:
        if not self.start():
            return False
        return self._send({"jsonrpc": "2.0", "method": str(method or ""), "params": params or {}})

    def close(self) -> None:
        self._closed.set()
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        for queue in list(self._pending.values()):
            try:
                queue.put_nowait({"error": "transport_closed", "result": None})
            except Exception:
                pass
        self._pending.clear()

    def _next_id(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def _send(self, payload: dict[str, Any]) -> bool:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return False
        try:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
            with self._lock:
                proc.stdin.write(header)
                proc.stdin.write(raw)
                proc.stdin.flush()
            return True
        except Exception:
            return False

    def _read_stdout_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        stream = proc.stdout
        while not self._closed.is_set():
            try:
                header_len = self._read_content_length(stream)
                if header_len <= 0:
                    break
                body = stream.read(header_len)
                if not body:
                    break
                payload = json.loads(body.decode("utf-8", errors="replace"))
            except Exception:
                break
            self._dispatch(payload)
        self._closed.set()

    def _read_stderr_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        while not self._closed.is_set():
            try:
                line = proc.stderr.readline()
            except Exception:
                break
            if not line:
                break
            text = utils_module._safe_text(line.decode("utf-8", errors="replace"))
            if text:
                self._stderr_lines.append(text.rstrip())
                if len(self._stderr_lines) > 40:
                    self._stderr_lines = self._stderr_lines[-40:]

    def _read_content_length(self, stream) -> int:
        content_length = 0
        while True:
            line = stream.readline()
            if not line:
                return 0
            if line in (b"\r\n", b"\n"):
                break
            decoded = line.decode("ascii", errors="ignore").strip()
            if decoded.lower().startswith("content-length:"):
                try:
                    content_length = int(decoded.split(":", 1)[1].strip())
                except Exception:
                    content_length = 0
        return content_length

    def _dispatch(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        if "id" in payload and "method" not in payload:
            queue = self._pending.pop(int(payload.get("id") or 0), None)
            if queue is not None:
                try:
                    queue.put_nowait(payload)
                except Exception:
                    pass
            return
        if "id" in payload and "method" in payload:
            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {"code": -32601, "message": "client_method_not_supported"},
                }
            )


__all__ = ["LspStdioTransport"]
