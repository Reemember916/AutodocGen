"""Normalize C function comment blocks into stable AutoDoc fields."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class CommentEvidence:
    field: str
    line_index: int
    text: str


@dataclass(frozen=True)
class NormalizedComment:
    func_name: str = ""
    func_cn_name: str = ""
    desc: str = ""
    input_desc: str = ""
    output_desc: str = ""
    other_desc: str = ""
    return_desc: str = ""
    evidence: tuple[CommentEvidence, ...] = ()

    def to_parse_dict(self) -> dict[str, str]:
        return {
            "func_name": self.func_name,
            "func_cn_name": self.func_cn_name,
            "desc": self.desc,
            "input_desc": self.input_desc,
            "output_desc": self.output_desc,
            "other_desc": self.other_desc,
            "return_desc": self.return_desc,
        }


_LABEL_TO_FIELD = {
    "函数名": "func_name",
    "函数名称": "func_name",
    "函数中文名": "func_cn_name",
    "功能描述": "desc",
    "功能说明": "desc",
    "功能": "desc",
    "输入参数说明": "input_desc",
    "输入参数": "input_desc",
    "输出参数说明": "output_desc",
    "输出参数": "output_desc",
    "其他说明": "other_desc",
    "返回": "return_desc",
    "返回值": "return_desc",
    "返回数据": "return_desc",
}

_LABEL_NAMES = "函数名|函数名称|函数中文名|功能描述|功能说明|功能|输入参数说明|输入参数|输出参数说明|输出参数|其他说明|返回值?|返回数据"
_LABEL_RE = re.compile(
    rf"^\s*(?:\[(?P<bracket>{_LABEL_NAMES})\]|【(?P<fullwidth>{_LABEL_NAMES})】|(?P<plain>{_LABEL_NAMES})(?=\s*(?:[:：]|$)))\s*[:：]?\s*(?P<rest>.*)$"
)
_DECORATION_RE = re.compile(r"^[\s/*\-_=#]{3,}$")
_COMMENT_START_RE = re.compile(r"^\s*/\*+")
_COMMENT_END_RE = re.compile(r"\*/\s*$")
_LEADING_STAR_RE = re.compile(r"^\s*\*+\s?")
_SECTION_STOP_RE = re.compile(rf"^\s*(?:\[(?:{_LABEL_NAMES})\]|【(?:{_LABEL_NAMES})】|(?:{_LABEL_NAMES})(?=\s*(?:[:：]|$)))")


def _clean_line(raw: object) -> str:
    text = str(raw or "").rstrip("\r\n")
    text = _COMMENT_START_RE.sub("", text)
    text = _COMMENT_END_RE.sub("", text)
    text = _LEADING_STAR_RE.sub("", text)
    return text.strip()


def _is_decoration(line: str) -> bool:
    text = str(line or "").strip()
    return not text or bool(_DECORATION_RE.fullmatch(text))


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", "", str(label or "").strip())


def _clean_section_lines(lines: Iterable[str]) -> str:
    cleaned = [str(line or "").strip() for line in lines]
    while cleaned and _is_decoration(cleaned[0]):
        cleaned.pop(0)
    while cleaned and _is_decoration(cleaned[-1]):
        cleaned.pop()
    return "\n".join(line for line in cleaned if line.strip()).strip().lstrip("：:").strip()


def _fallback_free_text(lines: list[str]) -> tuple[str, str]:
    func_name = ""
    desc = ""
    for line in lines:
        stripped = line.strip().strip("-=:;,. ")
        if not stripped or _is_decoration(stripped):
            continue
        if re.match(r"^\d+\s*[)\.、:：-]", stripped):
            continue
        if re.match(r"^[A-Za-z_]\w*\s*:?\s*$", stripped):
            func_name = stripped.rstrip(":：").strip()
            continue
        desc = stripped.rstrip("：:").strip()
        break
    return func_name, desc


def normalize_comment_block(raw: object) -> NormalizedComment:
    raw_text = str(raw or "")
    lines = [_clean_line(line) for line in raw_text.splitlines()]
    sections: dict[str, list[str]] = {}
    evidence: list[CommentEvidence] = []
    current_field = ""

    for idx, line in enumerate(lines):
        if _is_decoration(line):
            continue
        match = _LABEL_RE.match(line)
        if match:
            label = _normalize_label(match.group("bracket") or match.group("fullwidth") or match.group("plain") or "")
            field = _LABEL_TO_FIELD.get(label, "")
            current_field = field
            if not field:
                continue
            sections.setdefault(field, [])
            rest = str(match.group("rest") or "").strip().lstrip("：:").strip()
            if rest:
                sections[field].append(rest)
                evidence.append(CommentEvidence(field, idx, rest))
            continue
        if current_field:
            if _SECTION_STOP_RE.match(line):
                current_field = ""
                continue
            sections.setdefault(current_field, []).append(line)
            if line.strip():
                evidence.append(CommentEvidence(current_field, idx, line.strip()))

    values = {field: _clean_section_lines(chunks) for field, chunks in sections.items()}
    if not any(values.values()):
        func_name, desc = _fallback_free_text(lines)
        values = {"func_name": func_name, "desc": desc}

    func_name = values.get("func_name", "").splitlines()[0].strip().rstrip(":：") if values.get("func_name") else ""
    return NormalizedComment(
        func_name=func_name,
        func_cn_name=values.get("func_cn_name", ""),
        desc=values.get("desc", ""),
        input_desc=values.get("input_desc", ""),
        output_desc=values.get("output_desc", ""),
        other_desc=values.get("other_desc", ""),
        return_desc=values.get("return_desc", ""),
        evidence=tuple(evidence),
    )
