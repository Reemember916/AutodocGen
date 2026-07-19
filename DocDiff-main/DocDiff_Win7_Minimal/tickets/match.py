"""问题单 → 变更条目自动匹配（方案 A：先有问题单列表，再挂到 diff）。"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tickets.tickets import (
    DEFAULT_TICKET_SEQ_WIDTH,
    Ticket,
    ensure_ticket_no,
    format_ticket_no,
    normalize_ticket_prefix,
)


# 与 diff.collect_changes 中 doc-id 规则对齐（避免循环 import）
_PAREN_RE = re.compile(r"[（(]([^）)]+)[）)]")
_DOC_ID_SLASH_RE = re.compile(r"[A-Za-z]+/[A-Za-z0-9_./-]+")
_DOC_ID_SEP_RE = re.compile(r"[A-Za-z]{2,}[-_][A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+")
_C_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
_PATH_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:c|h|C|H)\b")

# 匹配分阈值：低于此分不自动挂接（留给序号兜底或未关联）
DEFAULT_MATCH_MIN_SCORE = 0.42


@dataclass
class MatchResult:
    change_index: int  # 0-based in changes list
    ticket_seq: int
    score: float
    reason: str


def _extract_doc_ids(text: str) -> List[str]:
    if not text:
        return []
    found: List[str] = []
    for c in _PAREN_RE.findall(text):
        c = c.strip()
        m = _DOC_ID_SLASH_RE.search(c)
        if m:
            found.append(m.group(0))
            continue
        m = _DOC_ID_SEP_RE.search(c)
        if m:
            found.append(m.group(0))
    # 正文中直接出现 D/R_xxx
    for m in _DOC_ID_SLASH_RE.finditer(text):
        found.append(m.group(0))
    for m in _DOC_ID_SEP_RE.finditer(text):
        tok = m.group(0)
        if re.search(r"\d", tok):
            found.append(tok)
    # 去重保序
    out, seen = [], set()
    for x in found:
        k = x.upper()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _segment_preview(ch: Mapping[str, Any], side: str = "old") -> str:
    """从 change 取可匹配文本。"""
    parts: List[str] = []
    key = str(ch.get("key") or "")
    seg = str(ch.get("seg") or "")
    if key:
        parts.append(key)
    if seg and seg not in {"_MAIN", "章节标题"}:
        parts.append(seg)

    # 文档：Segment 对象
    for side_key in ("old", "new") if side == "both" else (side,):
        obj = ch.get(side_key)
        if obj is None:
            continue
        if hasattr(obj, "blocks"):
            for b in getattr(obj, "blocks", []) or []:
                t = (getattr(b, "text", "") or "").strip()
                if t:
                    parts.append(t[:400])
        # 代码：字符串
    for k in ("old_text", "new_text", "old_preview", "new_preview"):
        t = ch.get(k)
        if t:
            parts.append(str(t)[:400])

    # ticket fields already on change
    for k in ("ticket_title",):
        if ch.get(k):
            parts.append(str(ch[k]))

    return "\n".join(parts)


def _change_fingerprint(ch: Mapping[str, Any]) -> Dict[str, Any]:
    """抽取变更侧可匹配特征。"""
    key = str(ch.get("key") or "")
    seg = str(ch.get("seg") or "")
    blob = _segment_preview(ch, side="both")
    text_all = f"{key}\n{seg}\n{blob}"

    doc_ids = _extract_doc_ids(text_all)
    # leaf title from key
    leaf = key.split(" > ")[-1] if key else ""
    paths = _PATH_RE.findall(text_all)
    # 函数名：代码 change 的 seg 常为函数名；也从文本抽 C 标识符
    idents = []
    if seg and re.match(r"^[A-Za-z_][A-Za-z0-9_]+$", seg) and seg not in {
        "_MAIN",
        "章节标题",
        "全局区域",
        "头文件",
    }:
        idents.append(seg)
    for m in _C_IDENT_RE.finditer(text_all):
        tok = m.group(0)
        if tok.lower() in {
            "int",
            "void",
            "char",
            "return",
            "if",
            "else",
            "for",
            "while",
            "switch",
            "case",
            "const",
            "static",
            "struct",
            "uint16",
            "uint32",
            "uint8",
            "true",
            "false",
            "null",
        }:
            continue
        if len(tok) >= 4:
            idents.append(tok)

    # 去重
    def uniq(xs):
        o, s = [], set()
        for x in xs:
            k = x if isinstance(x, str) else str(x)
            kl = k.lower()
            if kl not in s:
                s.add(kl)
                o.append(k)
        return o

    return {
        "key": key,
        "seg": seg,
        "leaf": leaf,
        "doc_ids": uniq(doc_ids),
        "paths": uniq(paths),
        "idents": uniq(idents)[:40],
        "blob": text_all[:2000],
    }


def _ticket_fingerprint(ticket: Ticket) -> Dict[str, Any]:
    title = ticket.display_title()
    no = ticket.display_no()
    text = f"{title}\n{no}"
    return {
        "title": title,
        "ticket_no": no,
        "doc_ids": _extract_doc_ids(text),
        "paths": _PATH_RE.findall(text),
        "idents": [
            m.group(0)
            for m in _C_IDENT_RE.finditer(title)
            if len(m.group(0)) >= 4
        ],
        "blob": text,
    }


def _score_pair(tf: Dict[str, Any], cf: Dict[str, Any]) -> Tuple[float, str]:
    """返回 (score 0~1, reason)。"""
    reasons: List[str] = []
    score = 0.0

    # 1) doc-id 精确（最强）
    t_ids = {x.upper() for x in tf.get("doc_ids") or []}
    c_ids = {x.upper() for x in cf.get("doc_ids") or []}
    common_ids = t_ids & c_ids
    if common_ids:
        score = max(score, 0.95)
        reasons.append(f"doc_id:{next(iter(common_ids))}")

    # 2) 路径
    t_paths = {x.replace("\\", "/").lower() for x in tf.get("paths") or []}
    c_paths = {x.replace("\\", "/").lower() for x in cf.get("paths") or []}
    # 也用 change.key 当路径
    if cf.get("key") and ("/" in cf["key"] or "\\" in cf["key"] or cf["key"].endswith((".c", ".h"))):
        c_paths.add(cf["key"].replace("\\", "/").lower())
    common_paths = t_paths & c_paths
    if common_paths:
        score = max(score, 0.88)
        reasons.append(f"path:{next(iter(common_paths))}")
    else:
        # 路径 basename
        t_base = {p.split("/")[-1] for p in t_paths}
        c_base = {p.split("/")[-1] for p in c_paths}
        if t_base & c_base:
            score = max(score, 0.80)
            reasons.append(f"file:{next(iter(t_base & c_base))}")

    # 3) 函数名 / 标识符
    t_idents = {x.lower() for x in tf.get("idents") or []}
    c_idents = {x.lower() for x in cf.get("idents") or []}
    if cf.get("seg"):
        c_idents.add(str(cf["seg"]).lower())
    common_id = t_idents & c_idents
    # 过滤太短
    common_id = {x for x in common_id if len(x) >= 4}
    if common_id:
        # 多个命中加分
        hit = sorted(common_id, key=len, reverse=True)[0]
        score = max(score, 0.82 if len(hit) >= 6 else 0.72)
        reasons.append(f"symbol:{hit}")

    # 4) 标题叶子 / 问题描述 子串
    title = (tf.get("title") or "").strip()
    leaf = (cf.get("leaf") or "").strip()
    key = (cf.get("key") or "").strip()
    if title and len(title) >= 2:
        # 问题描述出现在章节 key/leaf 中，或反过来
        if leaf and (title in leaf or leaf in title):
            score = max(score, 0.70)
            reasons.append("title⊂leaf")
        elif key and title in key:
            score = max(score, 0.68)
            reasons.append("title⊂key")
        else:
            # 去掉常见后缀词再比
            t_core = re.sub(r"(需求变更|变更|修改|冗余|删除|新增|问题)$", "", title).strip()
            if t_core and len(t_core) >= 2 and (t_core in key or t_core in leaf or t_core in (cf.get("blob") or "")):
                score = max(score, 0.62)
                reasons.append(f"keyword:{t_core[:20]}")

    # 5) 文本相似度（弱）
    if title and cf.get("blob"):
        a = re.sub(r"\s+", "", title.lower())
        b = re.sub(r"\s+", "", (cf["blob"] or "")[:500].lower())
        if a and b:
            r = difflib.SequenceMatcher(None, a, b[: max(len(a) * 3, 80)]).ratio()
            if r >= 0.55:
                score = max(score, 0.45 + 0.25 * r)
                reasons.append(f"sim:{r:.2f}")

    if not reasons:
        return 0.0, "none"
    return min(1.0, score), "+".join(reasons[:3])


def match_tickets_to_changes(
    changes: Sequence[Mapping[str, Any]],
    tickets: Mapping[int, Ticket],
    min_score: float = DEFAULT_MATCH_MIN_SCORE,
) -> List[MatchResult]:
    """一对一贪心匹配：高分优先。每个 ticket、每个 change 最多用一次。

    纯规则实现；若需 LLM/hybrid，请用 tickets.strategy.run_match_strategy。
    """
    if not changes or not tickets:
        return []

    change_fps = [_change_fingerprint(ch) for ch in changes]
    ticket_items = [(seq, tickets[seq], _ticket_fingerprint(tickets[seq])) for seq in sorted(tickets.keys())]

    candidates: List[Tuple[float, int, int, str]] = []  # score, change_idx, ticket_seq, reason
    for ci, cf in enumerate(change_fps):
        for seq, _t, tf in ticket_items:
            # 空描述且无单号特征 → 跳过内容匹配
            if not (tf.get("title") or tf.get("doc_ids") or tf.get("idents") or tf.get("paths")):
                continue
            sc, reason = _score_pair(tf, cf)
            if sc >= min_score:
                candidates.append((sc, ci, seq, reason))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_c, used_t = set(), set()
    results: List[MatchResult] = []
    for sc, ci, seq, reason in candidates:
        if ci in used_c or seq in used_t:
            continue
        used_c.add(ci)
        used_t.add(seq)
        results.append(MatchResult(change_index=ci, ticket_seq=seq, score=sc, reason=reason))
    return results


def apply_matched_tickets(
    changes: Sequence[dict],
    tickets: Mapping[int, Ticket],
    *,
    problem_start: int = 1,
    ticket_prefix: str = "",
    ticket_seq_width: int = DEFAULT_TICKET_SEQ_WIDTH,
    min_score: float = DEFAULT_MATCH_MIN_SCORE,
    reorder: bool = True,
    match_strategy: str = "rules",
    match_context: Any = None,
) -> List[dict]:
    """方案 A：用问题单台账内容匹配变更，再写入 ticket 字段。

    match_strategy:
      - rules: 仅规则（默认）
      - llm: 仅 LLM（需 API）
      - hybrid: 规则优先，未匹配再 LLM

    reorder=True（默认）：把成功匹配的变更按问题单序号排序，使「问题N」与台账序号一致。
    """
    changes_list = [dict(ch) for ch in (changes or [])]
    if not changes_list:
        return []

    prefix = normalize_ticket_prefix(ticket_prefix)
    width = max(1, int(ticket_seq_width or DEFAULT_TICKET_SEQ_WIDTH))

    strategy_name = (match_strategy or "rules").strip().lower()
    if strategy_name in {"rules", "rule", "auto", "default", ""}:
        matches = match_tickets_to_changes(changes_list, tickets, min_score=min_score)
        method_label = "auto"
    else:
        from tickets.strategy import MatchContext, run_match_strategy

        ctx = match_context
        if ctx is None:
            ctx = MatchContext(min_score=min_score)
        elif getattr(ctx, "min_score", None) is None:
            ctx.min_score = min_score
        matches = run_match_strategy(strategy_name, changes_list, tickets, ctx)
        method_label = strategy_name if strategy_name != "hybrid" else "hybrid"

    by_change = {m.change_index: m for m in matches}

    if reorder and matches:
        matched_order = sorted(matches, key=lambda m: (m.ticket_seq, m.change_index))
        matched_indices = [m.change_index for m in matched_order]
        unmatched_indices = [i for i in range(len(changes_list)) if i not in by_change]
        new_order = matched_indices + unmatched_indices
        ordered = [changes_list[i] for i in new_order]
        old_to_new = {old: new for new, old in enumerate(new_order)}
        by_change_new = {
            old_to_new[m.change_index]: m for m in matches if m.change_index in old_to_new
        }
    else:
        ordered = changes_list
        by_change_new = by_change

    start = max(1, int(problem_start or 1))
    out: List[dict] = []
    for offset, ch in enumerate(ordered):
        row = dict(ch)
        problem_index = start + offset
        row["problem_index"] = problem_index
        m = by_change_new.get(offset)
        if m is not None:
            t = tickets[m.ticket_seq]
            row["ticket_no"] = ensure_ticket_no(
                t.display_no(), m.ticket_seq, prefix=prefix, width=width
            )
            if not row["ticket_no"] and prefix:
                row["ticket_no"] = format_ticket_no(prefix, m.ticket_seq, width=width)
            elif not row["ticket_no"]:
                row["ticket_no"] = ensure_ticket_no(
                    t.display_no(), m.ticket_seq, prefix=prefix, width=width
                )
            row["ticket_title"] = t.display_title()
            row["ticket_seq"] = m.ticket_seq
            row["ticket_match_score"] = round(m.score, 4)
            row["ticket_match_reason"] = m.reason
            # 区分 llm / rules / hybrid
            if str(m.reason).startswith("llm"):
                row["ticket_match_method"] = "llm" if method_label != "hybrid" else "hybrid-llm"
            else:
                row["ticket_match_method"] = (
                    "auto" if method_label in {"auto", "rules"} else f"{method_label}-rules"
                )
        else:
            if prefix:
                row["ticket_no"] = format_ticket_no(prefix, problem_index, width=width)
            else:
                row.setdefault("ticket_no", "")
            row.setdefault("ticket_title", "")
            row["ticket_match_method"] = "none"
            row["ticket_match_score"] = 0.0
            row["ticket_match_reason"] = ""
        out.append(row)
    return out


def match_report(
    changes: Sequence[Mapping[str, Any]],
    tickets: Mapping[int, Ticket],
    min_score: float = DEFAULT_MATCH_MIN_SCORE,
    match_strategy: str = "rules",
    match_context: Any = None,
) -> dict:
    """诊断用：匹配结果摘要。"""
    strategy_name = (match_strategy or "rules").strip().lower()
    if strategy_name in {"rules", "rule", "auto", "default", ""}:
        matches = match_tickets_to_changes(changes, tickets, min_score=min_score)
        strategy_used = "rules"
    else:
        from tickets.strategy import MatchContext, run_match_strategy

        ctx = match_context or MatchContext(min_score=min_score)
        matches = run_match_strategy(strategy_name, changes, tickets, ctx)
        strategy_used = strategy_name

    matched_tickets = {m.ticket_seq for m in matches}
    matched_changes = {m.change_index for m in matches}
    return {
        "change_count": len(changes or []),
        "ticket_count": len(tickets or {}),
        "matched_count": len(matches),
        "min_score": min_score,
        "match_strategy": strategy_used,
        "matches": [
            {
                "change_index": m.change_index + 1,
                "ticket_seq": m.ticket_seq,
                "score": round(m.score, 4),
                "reason": m.reason,
                "ticket_no": tickets[m.ticket_seq].display_no() if m.ticket_seq in tickets else "",
                "ticket_title": tickets[m.ticket_seq].display_title() if m.ticket_seq in tickets else "",
                "change_key": (changes[m.change_index] or {}).get("key")
                if m.change_index < len(changes)
                else "",
                "change_seg": (changes[m.change_index] or {}).get("seg")
                if m.change_index < len(changes)
                else "",
            }
            for m in sorted(matches, key=lambda x: x.ticket_seq)
        ],
        "unmatched_tickets": [
            {
                "seq": seq,
                "title": tickets[seq].display_title(),
                "ticket_no": tickets[seq].display_no(),
            }
            for seq in sorted(tickets.keys())
            if seq not in matched_tickets
        ],
        "unmatched_change_indices": [
            i + 1 for i in range(len(changes or [])) if i not in matched_changes
        ],
    }
