import difflib
import re


_ZW_RE = re.compile(r"[​-‍﻿]")


def _normalize_compare_text(text: str) -> str:
    """轻量归一：零宽字符、全半角空白/括号、压缩空白。用于“无语义差异”判定。"""
    if not text:
        return ""
    s = _ZW_RE.sub("", str(text))
    s = s.replace("（", "(").replace("）", ")").replace("　", " ")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in s.split("\n")]
    return "\n".join(lines).strip()


def diff_segments(old_seg, new_seg, threshold=0.0):
    old_text = "\n".join(b.text for b in old_seg.blocks)
    new_text = "\n".join(b.text for b in new_seg.blocks)

    if old_text == new_text:
        return None

    # 仅全半角/空白/零宽差异 → 视为无变更
    if _normalize_compare_text(old_text) == _normalize_compare_text(new_text):
        return None

    r = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False).ratio()
    if 1 - r <= threshold:
        return None

    return {
        "type": "修改",
        "old": old_seg,
        "new": new_seg
    }
