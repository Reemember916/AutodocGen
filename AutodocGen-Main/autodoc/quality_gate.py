"""Shared structural quality gate for rendered design logic.

The gate is intentionally dependency-light so the generation pipeline and
standalone DOCX checker cannot silently diverge on what constitutes a hard
logic defect.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence


STRUCTURAL_LOGIC_CODES = frozenset({"logic_placeholder", "logic_truncated"})
_RAW_CONTROL_RE = re.compile(r"\b(?:if|for|while|switch)\s*\(", re.I)
_RAW_LOGICAL_RE = re.compile(r"&&|\|\|")
_RAW_BITWISE_RE = re.compile(r"(?<![&|])(?:&|\|)(?![&|])")
_DANGLING_OPERATOR_RE = re.compile(r"(?:&&|\|\||&|\|)\s*(?:[；;，,。.]|$)")
_PLACEHOLDER_RE = re.compile(r"执行操作\s*(?:[（(]|[:：])")
_BRACKET_PAIRS = {"(": ")", "（": "）", "[": "]", "［": "］", "{": "}", "｛": "｝"}
_CLOSING_BRACKETS = frozenset(_BRACKET_PAIRS.values())


def _has_unbalanced_brackets(text: str) -> bool:
    """Check ASCII/full-width bracket pairing without treating prose as C."""
    stack: list[str] = []
    for char in str(text or ""):
        if char in _BRACKET_PAIRS:
            stack.append(_BRACKET_PAIRS[char])
        elif char in _CLOSING_BRACKETS:
            if not stack or char != stack.pop():
                return True
    return bool(stack)


def has_structural_logic_error(issues: Sequence[Mapping[str, Any]] | None) -> bool:
    return any(
        str((item or {}).get("code") or "").strip() in STRUCTURAL_LOGIC_CODES
        and str((item or {}).get("severity") or "").strip().lower() == "error"
        for item in (issues or ())
    )


def _anchor_for_line(line_no: int, source_anchors: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    for anchor in source_anchors or ():
        try:
            if int((anchor or {}).get("idx") or 0) == line_no:
                return dict(anchor)
        except (TypeError, ValueError):
            continue
    return {}


def inspect_logic_lines(
    logic_lines: Optional[Sequence[str]],
    *,
    source_anchors: Sequence[Mapping[str, Any]] | None = None,
    source: str = "logic_lines",
) -> tuple[dict[str, Any], ...]:
    """Return blocking, line-addressable structural defects.

    Each result contains ``logic_line`` and ``logic_text`` in addition to the
    normal quality issue fields.  Callers may attach the returned
    ``source_anchor`` directly to review/audit metadata.
    """
    issues: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(logic_lines or (), start=1):
        text = str(raw_line or "").strip()
        if not text:
            continue
        code = ""
        message = ""
        if "待人工修改" in text:
            code = "logic_placeholder"
            message = "包含待人工修改占位"
        elif _PLACEHOLDER_RE.search(text):
            code = "logic_placeholder"
            message = "包含通用执行操作占位"
        elif (
            _RAW_CONTROL_RE.search(text)
            or _RAW_LOGICAL_RE.search(text)
            or _RAW_BITWISE_RE.search(text)
            or _DANGLING_OPERATOR_RE.search(text)
            or _has_unbalanced_brackets(text)
        ):
            code = "logic_truncated"
            message = "包含未完成或原始 C 表达式"
        if not code:
            continue
        issue = {
            "code": code,
            "severity": "error",
            "message": f"逻辑第 {line_no} 行{message}：{text[:96]}",
            "source": source,
            "logic_line": line_no,
            "logic_text": text,
        }
        anchor = _anchor_for_line(line_no, source_anchors)
        if anchor:
            issue["source_anchor"] = anchor
        issues.append(issue)
    return tuple(issues)


def is_safe_ai_text(text: Any) -> bool:
    """Reject AI field text that can corrupt a rendered logic sentence."""
    value = str(text or "").strip()
    if not value:
        return True
    return not bool(
        "待人工修改" in value
        or _PLACEHOLDER_RE.search(value)
        or
        _RAW_CONTROL_RE.search(value)
        or _RAW_LOGICAL_RE.search(value)
        or _RAW_BITWISE_RE.search(value)
        or _DANGLING_OPERATOR_RE.search(value)
        or _has_unbalanced_brackets(value)
        or any(ch in value for ch in "{}")
    )
