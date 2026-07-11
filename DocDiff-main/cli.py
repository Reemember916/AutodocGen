import argparse
import json
import os
from typing import Callable, Optional

from canonical.normalize import build_ast
from code_diff.collect_code_changes import collect_code_changes
from diff.collect_changes import collect_changes
from render.change_order import render_change_order
from render.code_change_order import render_code_change_order


def _extract_doc_id(title: str) -> str:
    import re

    if not title:
        return ""
    for candidate in reversed(re.findall(r"[（(]([^）)]+)[）)]", title)):
        if re.search(r"[A-Za-z]+/[A-Za-z0-9_]+", candidate):
            return candidate.strip()
    return ""


def _ast_to_diagnostic(ast) -> dict:
    sections = []
    key_counts = {}
    doc_id_counts = {}

    for sec in getattr(ast, "sections", []) or []:
        key = getattr(sec, "key", "") or ""
        doc_id = _extract_doc_id(getattr(sec, "title", "") or "")
        if key:
            key_counts[key] = key_counts.get(key, 0) + 1
        if doc_id:
            doc_id_counts[doc_id] = doc_id_counts.get(doc_id, 0) + 1

    for index, sec in enumerate(getattr(ast, "sections", []) or [], start=1):
        segs = getattr(sec, "segments", {}) or {}
        segments = []
        for seg_id, seg in segs.items():
            blocks = list(getattr(seg, "blocks", []) or [])
            segments.append({
                "seg_id": seg_id,
                "block_count": len(blocks),
                "block_types": [getattr(b, "block_type", "") for b in blocks],
                "text_preview": next(
                    (
                        (getattr(b, "text", "") or "").strip()[:120]
                        for b in blocks
                        if (getattr(b, "text", "") or "").strip()
                    ),
                    "",
                ),
            })

        title = getattr(sec, "title", "") or ""
        key = getattr(sec, "key", "") or ""
        doc_id = _extract_doc_id(title)
        sections.append({
            "index": index,
            "level": getattr(sec, "level", None),
            "title": title,
            "key": key,
            "doc_id": doc_id,
            "duplicate_key": bool(key and key_counts.get(key, 0) > 1),
            "duplicate_doc_id": bool(doc_id and doc_id_counts.get(doc_id, 0) > 1),
            "segment_count": len(segments),
            "segments": segments,
        })

    return {
        "section_count": len(sections),
        "duplicate_keys": sorted(k for k, v in key_counts.items() if v > 1),
        "duplicate_doc_ids": sorted(k for k, v in doc_id_counts.items() if v > 1),
        "sections": sections,
    }


def dump_ast_diagnostic(old_path: str, new_path: str, dump_path: str, log: Optional[Callable[[str], None]] = None) -> None:
    logger = log or print
    logger("生成 AST 诊断...")
    payload = {
        "old": {
            "path": os.path.abspath(old_path),
            "ast": _ast_to_diagnostic(build_ast(old_path)),
        },
        "new": {
            "path": os.path.abspath(new_path),
            "ast": _ast_to_diagnostic(build_ast(new_path)),
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(dump_path)) or ".", exist_ok=True)
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger(f"AST 诊断已输出：{dump_path}")


def _files_identical(path_a: str, path_b: str) -> bool:
    if not (os.path.isfile(path_a) and os.path.isfile(path_b)):
        return False
    st_a = os.stat(path_a)
    st_b = os.stat(path_b)
    if st_a.st_size != st_b.st_size:
        return False

    chunk = 1024 * 1024
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        while True:
            ba = fa.read(chunk)
            bb = fb.read(chunk)
            if ba != bb:
                return False
            if not ba:
                return True


def run_diff(old_path: str, new_path: str, out_path: str, log: Optional[Callable[[str], None]] = None) -> int:
    logger = log or print

    if _files_identical(old_path, new_path):
        logger("旧版与新版文档内容一致，跳过解析与对比")
        logger("生成更改单...")
        render_change_order([], out_path)
        logger(f"完成：{out_path}")
        return 0

    logger("构建旧版 AST...")
    old_ast = build_ast(old_path)

    logger("构建新版 AST...")
    new_ast = build_ast(new_path)

    logger("对比差异...")
    changes = collect_changes(old_ast, new_ast)
    logger(f"检测到 {len(changes)} 处差异")

    logger("生成更改单...")
    render_change_order(changes, out_path)
    logger(f"完成：{out_path}")

    return len(changes)


def run_code_diff(
    old_path: str,
    new_path: str,
    out_path: str,
    log: Optional[Callable[[str], None]] = None,
    show_c_gap_marker: bool = True,
    json_out: str = "",
) -> int:
    logger = log or print
    logger("收集代码差异...")
    gap_marker = "... (省略未改动片段) ..." if show_c_gap_marker else ""
    changes = collect_code_changes(old_path, new_path, c_gap_marker=gap_marker)
    logger(f"检测到 {len(changes)} 处代码差异")

    if json_out:
        os.makedirs(os.path.dirname(os.path.abspath(json_out)) or ".", exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(changes, f, ensure_ascii=False, indent=2)
        logger(f"代码差异 JSON 已输出：{json_out}")

    logger("生成代码更改单...")
    render_code_change_order(changes, out_path)
    logger(f"完成：{out_path}")
    return len(changes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DocDiff - Word 文档更改单生成")
    parser.add_argument("--mode", choices=["docx", "code"], default="docx", help="对比模式：docx 文档或 code 代码")
    parser.add_argument("--old", default="12.docx", help="旧版 docx 路径")
    parser.add_argument("--new", default="123.docx", help="新版 docx 路径")
    parser.add_argument("--out", default="更改单_测试版.docx", help="输出更改单路径")
    parser.add_argument(
        "--hide-c-gap-marker",
        action="store_true",
        help="code 模式下隐藏 .c 文件多段变更间的省略分隔行",
    )
    parser.add_argument(
        "--dump-ast",
        default="",
        help="docx 模式下输出 AST 诊断 JSON，用于排查标题/章节识别漏检",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="code 模式下输出机器可读代码差异 JSON",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.mode == "docx":
        if args.dump_ast:
            dump_ast_diagnostic(args.old, args.new, args.dump_ast)
        run_diff(args.old, args.new, args.out)
    else:
        run_code_diff(
            args.old,
            args.new,
            args.out,
            show_c_gap_marker=not args.hide_c_gap_marker,
            json_out=args.json_out,
        )


if __name__ == "__main__":
    main()
