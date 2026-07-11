from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class Block:
    """最小语义单元"""
    text: str
    block_type: str            # "para" | "table"
    source: str                # "body" | "txbx" | "table"
    raw: object                # 原始 python-docx 对象（回溯用）
    path: tuple                # 稳定路径（section, segment, index）


@dataclass
class Segment:
    seg_id: str                # "_MAIN" | "a" | "b" | ...
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Section:
    level: int                 # 1~4
    title: str
    key: str                   # 稳定 key（H1>H2>H3>H4）
    segments: dict = field(default_factory=dict)


@dataclass
class DocumentAST:
    sections: List[Section] = field(default_factory=list)
