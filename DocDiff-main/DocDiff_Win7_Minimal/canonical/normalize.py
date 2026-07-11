import re
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

from model.ast import DocumentAST, Section, Segment, Block
from extractor.reader import iter_blocks
from extractor.text_extract import extract_texts_from_p

SUB_RE = re.compile(r'^\s*([a-eａ-ｅ])[)\）\.、\s]')

FULL2HALF = {'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e'}


def _is_heading_para(p: Paragraph):
    """返回 (True/False, level or None)"""
    if not p.style:
        return False, None
    name = (p.style.name or "").strip().lower()

    for lv in (1, 2, 3, 4):
        if name in {f"heading {lv}", f"heading{lv}", f"标题{lv}", f"标题 {lv}"}:
            return True, lv

    # 自定义样式兼容：如 609_4 / 123_1
    raw_name = (p.style.name or "").strip()
    m_custom = re.match(r"^\d+[_-]([1-4])$", raw_name)
    if m_custom:
        return True, int(m_custom.group(1))

    # outlineLvl（兼容处理：避免直接访问 CT_PPr 动态属性导致 AttributeError）
    ppr = p._p.pPr
    if ppr is not None:
        try:
            nodes = ppr.xpath("./*[local-name()='outlineLvl']")
            if nodes:
                val = nodes[0].get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                if val is not None:
                    return True, int(val) + 1
        except Exception:
            pass

    return False, None


def _detect_sub_id(text: str):
    if not text:
        return None
    m = SUB_RE.match(text.strip())
    if not m:
        return None
    ch = m.group(1)
    return FULL2HALF.get(ch, ch)

def _is_para_in_table(p: Paragraph) -> bool:
    try:
        return bool(p._p.xpath("ancestor::*[local-name()='tbl']"))
    except Exception:
        return False


def _table_to_text(tbl: Table) -> str:
    lines = []
    for row in tbl.rows:
        cells = []
        for cell in row.cells:
            t = (cell.text or "").strip()
            t = " ".join(t.split())
            cells.append(t)
        lines.append("\t".join(cells).rstrip())
    return "\n".join(lines).strip()


def build_ast(doc_path: str) -> DocumentAST:
    doc = Document(doc_path)

    ast = DocumentAST()
    ctx = ["", "", ""]          # H1, H2, H3
    cur_section: Section = None
    pending_section = None
    cur_seg = "_MAIN"

    def ensure_seg(seg_id: str):
        cur_section.segments.setdefault(seg_id, Segment(seg_id))
        return cur_section.segments[seg_id]

    def start_section(level: int, title: str):
        nonlocal cur_section, pending_section, cur_seg
        key = " > ".join([x for x in ctx[: level - 1] if x] + [title])
        cur_section = Section(level=level, title=title, key=key, segments={})
        ast.sections.append(cur_section)
        pending_section = None
        cur_seg = "_MAIN"
        return cur_section

    def ensure_active_section():
        if cur_section is not None or pending_section is None:
            return cur_section
        return start_section(
            pending_section["level"],
            pending_section["title"],
        )

    for blk in iter_blocks(doc, recurse_table_cells=False):
        # ===================== Paragraph =====================
        if isinstance(blk, Paragraph):
            text = (blk.text or "").strip()
            # 含文本框时，合并主文本与文本框文本，避免遗漏流程图/图形中的文字变更。
            try:
                has_tbx = bool(blk._p.xpath(".//*[local-name()='txbxContent']"))
            except Exception:
                has_tbx = False

            if has_tbx:
                texts = [x.strip() for x in extract_texts_from_p(blk._p) if (x or "").strip()]
                if texts:
                    # 去重并保持顺序
                    merged = []
                    seen = set()
                    for t in texts:
                        if t not in seen:
                            merged.append(t)
                            seen.add(t)
                    text = "\n".join(merged)


            is_h, lv = _is_heading_para(blk)

            # --------- H1~H3 更新上下文 ---------
            if is_h and lv in (1, 2, 3):
                ctx[lv - 1] = text
                for i in range(lv, 3):
                    ctx[i] = ""
                cur_section = None
                pending_section = None
                cur_seg = "_MAIN"
                if lv == 3:
                    pending_section = {
                        "level": 3,
                        "title": text or "未命名 H3",
                    }
                continue

            # --------- H4：创建新 Section ---------
            if is_h and lv == 4:
                start_section(4, text or "未命名 H4")
                continue

            # --------- 普通段落：写入当前 section/segment ---------
            if not ensure_active_section():
                continue
            if _is_para_in_table(blk):
                continue

            # a~e 小节识别
            sub = _detect_sub_id(text)
            if sub:
                cur_seg = sub
            seg_obj = ensure_seg(cur_seg)
            seg_obj.blocks.append(
                Block(
                    text=text,
                    block_type="para",
                    source="body",
                    raw=blk,
                    path=(cur_section.key, cur_seg, len(seg_obj.blocks)),
                )
            )

        # ===================== Table =====================
        elif isinstance(blk, Table):
            if not cur_section:
                continue
            seg_obj = ensure_seg(cur_seg)
            seg_obj.blocks.append(
                Block(
                    text=_table_to_text(blk) or "[TABLE]",
                    block_type="table",
                    source="table",
                    raw=blk,
                    path=(cur_section.key, cur_seg, len(seg_obj.blocks))
                )
            )

    return ast
