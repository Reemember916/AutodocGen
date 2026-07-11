from diff.block_diff import diff_segments
import re
from model.ast import Block, Segment


_PAREN_RE = re.compile(r"[（(]([^）)]+)[）)]")
_DOC_ID_RE = re.compile(r"[A-Za-z]+/[A-Za-z0-9_]+")


def _extract_doc_id(title: str):
    """
    Try to extract stable identifier like: D/R_SDD01_001_003
    from titles such as: IFBITStateUpdate（D/R_SDD01_001_003）
    """
    if not title:
        return None
    candidates = _PAREN_RE.findall(title)
    for c in reversed(candidates):
        c = c.strip()
        if _DOC_ID_RE.search(c):
            return c
    return None


def _build_section_index(sections):
    """
    Prefer matching H4 sections by stable doc-id in parentheses.
    If a doc-id is duplicated or missing, fall back to section.key.
    """
    ids = [_extract_doc_id(getattr(sec, "title", "")) for sec in sections]
    counts = {}
    for x in ids:
        if x:
            counts[x] = counts.get(x, 0) + 1

    by_ident = {}
    ordered_idents = []
    for sec, doc_id in zip(sections, ids):
        if doc_id and counts.get(doc_id) == 1:
            ident = f"uid:{doc_id}"
        else:
            ident = f"key:{sec.key}"
        by_ident[ident] = sec
        ordered_idents.append(ident)

    return by_ident, ordered_idents


def _segment_text(seg) -> str:
    if not seg:
        return ""
    parts = []
    for b in getattr(seg, "blocks", []) or []:
        t = (getattr(b, "text", "") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def collect_changes(old_ast, new_ast):
    changes = []

    old_map, old_order = _build_section_index(old_ast.sections)
    new_map, new_order = _build_section_index(new_ast.sections)

    all_keys = list(dict.fromkeys(old_order + new_order))

    for key in all_keys:
        old_sec = old_map.get(key)
        new_sec = new_map.get(key)

        display_key = (new_sec.key if new_sec else (old_sec.key if old_sec else key))

        # 章节标题变更（同一 doc-id / key 对齐后）也应输出为“修改”
        if old_sec and new_sec and (old_sec.title or "") != (new_sec.title or ""):
            old_title = old_sec.title or ""
            new_title = new_sec.title or ""
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
                }
            )

        old_segs = old_sec.segments if old_sec else {}
        new_segs = new_sec.segments if new_sec else {}

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
                    changes.append({
                        "type": change_type,
                        "key": display_key,
                        "seg": seg_id,
                        "old": old_seg,
                        "new": new_seg
                    })

            elif old_seg and not new_seg:
                changes.append({
                    "type": "删除",
                    "key": display_key,
                    "seg": seg_id,
                    "old": old_seg,
                    "new": None
                })

            elif new_seg and not old_seg:
                changes.append({
                    "type": "新增",
                    "key": display_key,
                    "seg": seg_id,
                    "old": None,
                    "new": new_seg
                })

    return changes
