from docx.document import Document as _Document
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl


def iter_blocks(parent, recurse_table_cells: bool = False):
    """
    递归遍历：Document / Cell / Table
    按文档出现顺序 yield Paragraph 或 Table
    """
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
        parent_obj = parent
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
        parent_obj = parent
    elif isinstance(parent, Table):
        parent_elm = parent._tbl
        parent_obj = parent
    else:
        raise TypeError(f"Unsupported parent type: {type(parent)}")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent_obj)

        elif isinstance(child, CT_Tbl):
            tbl = Table(child, parent_obj)
            yield tbl

            if recurse_table_cells:
                # 可选：继续深入 table 的每个 cell
                for row in tbl.rows:
                    for cell in row.cells:
                        for inner in iter_blocks(cell, recurse_table_cells=True):
                            yield inner
