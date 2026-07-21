from __future__ import annotations

import difflib
import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from diff.block_diff import diff_segments
from model.ast import Block, Segment


_PAREN_RE = re.compile(r"[（(]([^）)]+)[）)]")
_ZW_RE = re.compile(r"[​-‍﻿]")
# Word 脚注/尾注序号常贴在标题末尾（如「功能描述1」）；去掉 1~3 位尾随数字用于匹配。
_TRAILING_FOOTNOTE_RE = re.compile(r"(?<=[^\d\s])\d{1,3}$")

# 括号内稳定编号：D/R_…、SDD-001-003、REQ_12_3 等
_DOC_ID_SLASH_RE = re.compile(r"[A-Za-z]+/[A-Za-z0-9_./-]+")
_DOC_ID_SEP_RE = re.compile(r"[A-Za-z]{2,}[-_][A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+")
_DOC_ID_MIXED_RE = re.compile(r"[A-Za-z]{2,}\d[\w.-]*")

DEFAULT_FUZZY_MIN_SCORE = 0.72
_FUZZY_TITLE_WEIGHT = 0.55
_FUZZY_CONTENT_WEIGHT = 0.45
# 同父路径 fuzzy 加分，优先桶内配对
_SAME_PARENT_BONUS = 0.06


def _normalize_title(title: str) -> str:
    """匹配用标题归一化：去零宽字符、统一括号/空白、去掉尾随脚注数字。"""
    if not title:
        return ""
    s = _ZW_RE.sub("", str(title))
    s = s.replace("（", "(").replace("）", ")").replace("　", " ")
    s = " ".join(s.split()).strip()
    s = _TRAILING_FOOTNOTE_RE.sub("", s).strip()
    return s


def _normalize_key(key: str) -> str:
    if not key:
        return ""
    parts = [p.strip() for p in str(key).split(" > ")]
    return " > ".join(_normalize_title(p) for p in parts if p)


def _looks_like_doc_id(token: str) -> bool:
    t = (token or "").strip()
    if len(t) < 3:
        return False
    if _DOC_ID_SLASH_RE.search(t):
        return True
    if _DOC_ID_SEP_RE.fullmatch(t) or _DOC_ID_SEP_RE.search(t):
        # 整段像编号，或括号内容里嵌了编号
        if _DOC_ID_SEP_RE.search(t) and re.search(r"\d", t):
            return True
    if _DOC_ID_MIXED_RE.fullmatch(t) and re.search(r"[-_]", t):
        return True
    return False


def _extract_doc_id(title: str) -> Optional[str]:
    """
    从标题括号中抽取稳定编号，例如：
      IFBITStateUpdate（D/R_SDD01_001_003）
      状态机（SDD-001-003）
      接口处理（REQ_12_3）
    """
    if not title:
        return None
    candidates = _PAREN_RE.findall(title)
    for c in reversed(candidates):
        c = c.strip()
        if _looks_like_doc_id(c):
            # 优先返回括号内完整 token（已 strip）
            m = _DOC_ID_SLASH_RE.search(c)
            if m:
                return m.group(0).strip()
            m = _DOC_ID_SEP_RE.search(c)
            if m:
                return m.group(0).strip()
            return c
    return None


def _segment_text(seg) -> str:
    if not seg:
        return ""
    parts = []
    for b in getattr(seg, "blocks", []) or []:
        t = (getattr(b, "text", "") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def _section_content_signature(sec) -> str:
    if not sec:
        return ""
    parts = []
    segs = getattr(sec, "segments", {}) or {}
    for seg_id in sorted(segs.keys()):
        seg = segs[seg_id]
        for b in getattr(seg, "blocks", []) or []:
            t = (getattr(b, "text", "") or "").strip()
            if t:
                parts.append(f"{seg_id}\t{t}")
    return "\n".join(parts)


def _text_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _title_similarity(a: str, b: str) -> float:
    return _text_ratio(_normalize_title(a or ""), _normalize_title(b or ""))


def _content_similarity(old_sec, new_sec) -> float:
    return _text_ratio(
        _section_content_signature(old_sec),
        _section_content_signature(new_sec),
    )


def _parent_bucket(key: str) -> str:
    parts = [p for p in (key or "").split(" > ") if p.strip()]
    if len(parts) <= 1:
        return ""
    return _normalize_key(" > ".join(parts[:-1]))


def _leaf_title(sec) -> str:
    key = getattr(sec, "key", "") or ""
    parts = [p for p in key.split(" > ") if p.strip()]
    if parts:
        return parts[-1]
    return getattr(sec, "title", "") or ""


def _pair_score(old_sec, new_sec) -> float:
    leaf_old = _leaf_title(old_sec)
    leaf_new = _leaf_title(new_sec)
    title_score = max(
        _title_similarity(getattr(old_sec, "title", "") or "", getattr(new_sec, "title", "") or ""),
        _title_similarity(leaf_old, leaf_new),
        _text_ratio(
            _normalize_key(getattr(old_sec, "key", "") or ""),
            _normalize_key(getattr(new_sec, "key", "") or ""),
        ),
    )
    content_score = _content_similarity(old_sec, new_sec)
    score = _FUZZY_TITLE_WEIGHT * title_score + _FUZZY_CONTENT_WEIGHT * content_score
    if _parent_bucket(getattr(old_sec, "key", "") or "") and (
        _parent_bucket(getattr(old_sec, "key", "") or "")
        == _parent_bucket(getattr(new_sec, "key", "") or "")
    ):
        score = min(1.0, score + _SAME_PARENT_BONUS)
    return score


def _unique_index_map(items: List[Tuple[str, int]]) -> Dict[str, int]:
    """items: (ident, index)；仅保留全局唯一的 ident。"""
    counts: Dict[str, int] = {}
    for ident, _ in items:
        if ident:
            counts[ident] = counts.get(ident, 0) + 1
    out: Dict[str, int] = {}
    for ident, idx in items:
        if ident and counts.get(ident) == 1:
            out[ident] = idx
    return out


def _best_unmatched_candidate(
    old_sec,
    unmatched_new: Sequence[int],
    new_list: Sequence,
    paired_new: set,
    min_score: float,
) -> Tuple[Optional[int], float]:
    best_j = None
    best_score = -1.0
    for j in unmatched_new:
        if j in paired_new:
            continue
        score = _pair_score(old_sec, new_list[j])
        if score > best_score:
            best_score = score
            best_j = j
    if best_j is not None and best_score >= min_score:
        return best_j, best_score
    return None, best_score if best_score >= 0 else 0.0


def build_section_pairs(
    old_sections,
    new_sections,
    fuzzy_min_score: float = DEFAULT_FUZZY_MIN_SCORE,
) -> List[Tuple[object, object, str, float]]:
    """
    多级章节对齐，返回 (old_sec|None, new_sec|None, match_method, score)。

    match_method:
      - uid: 括号内唯一 doc-id
      - uid_title: 重复 doc-id 时用归一化标题消歧
      - key: 归一化后的 section.key 唯一匹配
      - fuzzy: 标题+正文相似度
      - none: 真新增/删除
    """
    old_list = list(old_sections or [])
    new_list = list(new_sections or [])
    paired_old: set = set()
    paired_new: set = set()
    pairs: List[Tuple[object, object, str, float]] = []
    threshold = float(fuzzy_min_score)

    # Phase 1: 唯一 doc-id
    old_uid_items = []
    for i, sec in enumerate(old_list):
        did = _extract_doc_id(getattr(sec, "title", "") or "")
        if did:
            old_uid_items.append((did, i))
    new_uid_items = []
    for j, sec in enumerate(new_list):
        did = _extract_doc_id(getattr(sec, "title", "") or "")
        if did:
            new_uid_items.append((did, j))

    old_uid = _unique_index_map(old_uid_items)
    new_uid = _unique_index_map(new_uid_items)
    for did, i in old_uid.items():
        j = new_uid.get(did)
        if j is None or i in paired_old or j in paired_new:
            continue
        pairs.append((old_list[i], new_list[j], "uid", 1.0))
        paired_old.add(i)
        paired_new.add(j)

    # Phase 1b: 重复 doc-id → 同 id 组内按归一化标题 / 内容消歧
    old_by_did: Dict[str, List[int]] = defaultdict(list)
    for i, sec in enumerate(old_list):
        if i in paired_old:
            continue
        did = _extract_doc_id(getattr(sec, "title", "") or "")
        if did:
            old_by_did[did].append(i)
    new_by_did: Dict[str, List[int]] = defaultdict(list)
    for j, sec in enumerate(new_list):
        if j in paired_new:
            continue
        did = _extract_doc_id(getattr(sec, "title", "") or "")
        if did:
            new_by_did[did].append(j)

    for did in sorted(set(old_by_did) & set(new_by_did)):
        oi_list = [i for i in old_by_did[did] if i not in paired_old]
        nj_list = [j for j in new_by_did[did] if j not in paired_new]
        if not oi_list or not nj_list:
            continue

        # 先用归一化 leaf 标题唯一匹配
        old_leaf_items = [
            (_normalize_title(_leaf_title(old_list[i])), i) for i in oi_list
        ]
        new_leaf_items = [
            (_normalize_title(_leaf_title(new_list[j])), j) for j in nj_list
        ]
        old_leaves = _unique_index_map(old_leaf_items)
        new_leaves = _unique_index_map(new_leaf_items)
        for leaf, i in old_leaves.items():
            j = new_leaves.get(leaf)
            if j is None or i in paired_old or j in paired_new:
                continue
            pairs.append((old_list[i], new_list[j], "uid_title", 1.0))
            paired_old.add(i)
            paired_new.add(j)

        # 组内剩余：贪心相似度
        oi_rest = [i for i in oi_list if i not in paired_old]
        nj_rest = [j for j in nj_list if j not in paired_new]
        cand = []
        for i in oi_rest:
            for j in nj_rest:
                cand.append((_pair_score(old_list[i], new_list[j]), i, j))
        cand.sort(key=lambda x: (-x[0], x[1], x[2]))
        for score, i, j in cand:
            if i in paired_old or j in paired_new:
                continue
            if score < max(0.5, threshold - 0.1):
                continue
            pairs.append((old_list[i], new_list[j], "uid_title", score))
            paired_old.add(i)
            paired_new.add(j)

    # Phase 2: 归一化 key 唯一匹配（消化脚注数字、全半角、空白差异）
    old_key_items = []
    for i, sec in enumerate(old_list):
        if i in paired_old:
            continue
        nk = _normalize_key(getattr(sec, "key", "") or "")
        if nk:
            old_key_items.append((nk, i))
    new_key_items = []
    for j, sec in enumerate(new_list):
        if j in paired_new:
            continue
        nk = _normalize_key(getattr(sec, "key", "") or "")
        if nk:
            new_key_items.append((nk, j))

    old_keys = _unique_index_map(old_key_items)
    new_keys = _unique_index_map(new_key_items)
    for nk, i in old_keys.items():
        j = new_keys.get(nk)
        if j is None or i in paired_old or j in paired_new:
            continue
        pairs.append((old_list[i], new_list[j], "key", 1.0))
        paired_old.add(i)
        paired_new.add(j)

    # Phase 3: fuzzy（优先同父路径桶，再全局）
    unmatched_old = [i for i in range(len(old_list)) if i not in paired_old]
    unmatched_new = [j for j in range(len(new_list)) if j not in paired_new]

    def _bucket_indices(indices, side_list):
        buckets: Dict[str, List[int]] = defaultdict(list)
        for idx in indices:
            buckets[_parent_bucket(getattr(side_list[idx], "key", "") or "")].append(idx)
        return buckets

    old_buckets = _bucket_indices(unmatched_old, old_list)
    new_buckets = _bucket_indices(unmatched_new, new_list)

    candidates = []
    shared_parents = set(old_buckets) & set(new_buckets)
    for parent in shared_parents:
        for i in old_buckets[parent]:
            for j in new_buckets[parent]:
                score = _pair_score(old_list[i], new_list[j])
                if score >= threshold:
                    candidates.append((score, i, j))
    # 跨父路径补充（无同桶命中时仍可配）
    for i in unmatched_old:
        for j in unmatched_new:
            if _parent_bucket(getattr(old_list[i], "key", "") or "") == _parent_bucket(
                getattr(new_list[j], "key", "") or ""
            ):
                continue  # 已在同桶候选中
            score = _pair_score(old_list[i], new_list[j])
            if score >= threshold:
                candidates.append((score, i, j))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    for score, i, j in candidates:
        if i in paired_old or j in paired_new:
            continue
        pairs.append((old_list[i], new_list[j], "fuzzy", score))
        paired_old.add(i)
        paired_new.add(j)

    # 真删除 / 真新增
    for i, sec in enumerate(old_list):
        if i not in paired_old:
            pairs.append((sec, None, "none", 0.0))
            paired_old.add(i)
    for j, sec in enumerate(new_list):
        if j not in paired_new:
            pairs.append((None, sec, "none", 0.0))
            paired_new.add(j)

    return pairs


def _titles_meaningfully_differ(old_title: str, new_title: str) -> bool:
    """原文不同，且归一化后仍不同 → 才记「章节标题」变更（抑制脚注序号噪声）。"""
    old_title = old_title or ""
    new_title = new_title or ""
    if old_title == new_title:
        return False
    return _normalize_title(old_title) != _normalize_title(new_title)


def build_match_report(
    old_ast,
    new_ast,
    fuzzy_min_score: float = DEFAULT_FUZZY_MIN_SCORE,
) -> dict:
    """机器可读匹配报告，供 --dump-match / 验收使用。"""
    old_sections = list(getattr(old_ast, "sections", None) or [])
    new_sections = list(getattr(new_ast, "sections", None) or [])
    pairs = build_section_pairs(old_sections, new_sections, fuzzy_min_score=fuzzy_min_score)

    pair_rows = []
    method_counts: Dict[str, int] = defaultdict(int)
    unmatched_old = []
    unmatched_new = []

    for old_sec, new_sec, method, score in pairs:
        method_counts[method] += 1
        row = {
            "match_method": method,
            "score": round(float(score), 4),
            "old_title": getattr(old_sec, "title", None) if old_sec is not None else None,
            "new_title": getattr(new_sec, "title", None) if new_sec is not None else None,
            "old_key": getattr(old_sec, "key", None) if old_sec is not None else None,
            "new_key": getattr(new_sec, "key", None) if new_sec is not None else None,
            "old_doc_id": _extract_doc_id(getattr(old_sec, "title", "") or "") if old_sec else None,
            "new_doc_id": _extract_doc_id(getattr(new_sec, "title", "") or "") if new_sec else None,
        }
        pair_rows.append(row)

        if method == "none" and old_sec is not None and new_sec is None:
            # 最近候选，便于排查为何没配上
            cand_j, cand_score = _best_unmatched_candidate(
                old_sec,
                list(range(len(new_sections))),
                new_sections,
                set(),
                min_score=0.0,
            )
            nearest = None
            if cand_j is not None:
                nearest = {
                    "new_title": getattr(new_sections[cand_j], "title", ""),
                    "new_key": getattr(new_sections[cand_j], "key", ""),
                    "score": round(float(cand_score), 4),
                }
            unmatched_old.append(
                {
                    "title": getattr(old_sec, "title", ""),
                    "key": getattr(old_sec, "key", ""),
                    "doc_id": _extract_doc_id(getattr(old_sec, "title", "") or ""),
                    "nearest_new": nearest,
                }
            )
        if method == "none" and new_sec is not None and old_sec is None:
            unmatched_new.append(
                {
                    "title": getattr(new_sec, "title", ""),
                    "key": getattr(new_sec, "key", ""),
                    "doc_id": _extract_doc_id(getattr(new_sec, "title", "") or ""),
                }
            )

    return {
        "fuzzy_min_score": threshold if (threshold := float(fuzzy_min_score)) else DEFAULT_FUZZY_MIN_SCORE,
        "old_section_count": len(old_sections),
        "new_section_count": len(new_sections),
        "pair_count": len(pair_rows),
        "method_counts": dict(method_counts),
        "pairs": pair_rows,
        "unmatched_old": unmatched_old,
        "unmatched_new": unmatched_new,
    }


def collect_changes(
    old_ast,
    new_ast,
    fuzzy_min_score: float = DEFAULT_FUZZY_MIN_SCORE,
):
    changes = []

    pairs = build_section_pairs(
        getattr(old_ast, "sections", None),
        getattr(new_ast, "sections", None),
        fuzzy_min_score=fuzzy_min_score,
    )

    for old_sec, new_sec, match_method, match_score in pairs:
        display_key = (
            getattr(new_sec, "key", None)
            if new_sec is not None
            else (getattr(old_sec, "key", None) if old_sec is not None else "")
        ) or ""

        # 章节标题变更（对齐后）：忽略仅脚注数字等噪声差异
        if old_sec is not None and new_sec is not None:
            old_title = getattr(old_sec, "title", "") or ""
            new_title = getattr(new_sec, "title", "") or ""
            if _titles_meaningfully_differ(old_title, new_title):
                change_type = "修改"
                if old_title and not new_title:
                    change_type = "删除"
                elif new_title and not old_title:
                    change_type = "新增"

                old_title_seg = Segment(
                    seg_id="_TITLE",
                    blocks=[
                        Block(
                            text=old_title,
                            block_type="para",
                            source="body",
                            raw=None,
                            path=(display_key, "_TITLE", 0),
                        )
                    ],
                )
                new_title_seg = Segment(
                    seg_id="_TITLE",
                    blocks=[
                        Block(
                            text=new_title,
                            block_type="para",
                            source="body",
                            raw=None,
                            path=(display_key, "_TITLE", 0),
                        )
                    ],
                )
                changes.append(
                    {
                        "type": change_type,
                        "key": display_key,
                        "seg": "章节标题",
                        "old": old_title_seg,
                        "new": new_title_seg,
                        "match_method": match_method,
                        "match_score": match_score,
                    }
                )

        old_segs = getattr(old_sec, "segments", {}) if old_sec is not None else {}
        new_segs = getattr(new_sec, "segments", {}) if new_sec is not None else {}
        old_segs = old_segs or {}
        new_segs = new_segs or {}

        seg_ids = set(old_segs.keys()) | set(new_segs.keys())

        for seg_id in seg_ids:
            old_seg = old_segs.get(seg_id)
            new_seg = new_segs.get(seg_id)

            if old_seg and new_seg:
                diff = diff_segments(old_seg, new_seg)
                if diff:
                    old_txt = _segment_text(old_seg)
                    new_txt = _segment_text(new_seg)
                    change_type = "修改"
                    if old_txt and not new_txt:
                        change_type = "删除"
                    elif new_txt and not old_txt:
                        change_type = "新增"
                    changes.append(
                        {
                            "type": change_type,
                            "key": display_key,
                            "seg": seg_id,
                            "old": old_seg,
                            "new": new_seg,
                            "match_method": match_method,
                            "match_score": match_score,
                        }
                    )

            elif old_seg and not new_seg:
                changes.append(
                    {
                        "type": "删除",
                        "key": display_key,
                        "seg": seg_id,
                        "old": old_seg,
                        "new": None,
                        "match_method": match_method,
                        "match_score": match_score,
                    }
                )

            elif new_seg and not old_seg:
                changes.append(
                    {
                        "type": "新增",
                        "key": display_key,
                        "seg": seg_id,
                        "old": None,
                        "new": new_seg,
                        "match_method": match_method,
                        "match_score": match_score,
                    }
                )

    return changes
