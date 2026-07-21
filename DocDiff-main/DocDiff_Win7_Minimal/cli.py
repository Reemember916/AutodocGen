import argparse
import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from canonical.normalize import build_ast
from code_diff.collect_code_changes import collect_code_changes
from diff.collect_changes import (
    DEFAULT_FUZZY_MIN_SCORE,
    _extract_doc_id,
    build_match_report,
    collect_changes,
)
from render.change_order import changes_to_jsonable, render_change_order
from render.code_change_order import render_code_change_order
from tickets.tickets import apply_tickets_to_changes, load_tickets, write_ticket_template
from tickets.match import apply_matched_tickets, match_report
from tickets.strategy import MatchContext


def _ast_to_diagnostic(ast) -> dict:
    sections = []
    key_counts = {}
    doc_id_counts = {}

    for sec in getattr(ast, "sections", []) or []:
        key = getattr(sec, "key", "") or ""
        doc_id = _extract_doc_id(getattr(sec, "title", "") or "") or ""
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
        doc_id = _extract_doc_id(title) or ""
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


def dump_match_diagnostic(
    old_path: str,
    new_path: str,
    dump_path: str,
    fuzzy_min_score: float = DEFAULT_FUZZY_MIN_SCORE,
    log: Optional[Callable[[str], None]] = None,
) -> dict:
    logger = log or print
    logger("生成章节匹配诊断...")
    old_ast = build_ast(old_path)
    new_ast = build_ast(new_path)
    report = build_match_report(old_ast, new_ast, fuzzy_min_score=fuzzy_min_score)
    report["old_path"] = os.path.abspath(old_path)
    report["new_path"] = os.path.abspath(new_path)
    os.makedirs(os.path.dirname(os.path.abspath(dump_path)) or ".", exist_ok=True)
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger(
        f"匹配诊断已输出：{dump_path} "
        f"(pairs={report.get('pair_count')}, methods={report.get('method_counts')})"
    )
    return report


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


def _build_metadata(
    old_path: str,
    new_path: str,
    doc_no: str = "",
    version: str = "",
    author: str = "",
    date: str = "",
    security: str = "",
    remark: str = "",
) -> Dict[str, Any]:
    return {
        "doc_no": doc_no or "",
        "version": version or "",
        "author": author or "",
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "security": security or "",
        "remark": remark or "",
        "old_path": os.path.abspath(old_path) if old_path else "",
        "new_path": os.path.abspath(new_path) if new_path else "",
    }


def run_diff(
    old_path: str,
    new_path: str,
    out_path: str,
    log: Optional[Callable[[str], None]] = None,
    fuzzy_min_score: float = DEFAULT_FUZZY_MIN_SCORE,
    dump_match: str = "",
    json_out: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    use_table_key_column: bool = True,
    problem_start: int = 1,
    tickets_path: str = "",
    tickets: Optional[Dict[int, Any]] = None,
    ticket_prefix: str = "",
    auto_match_tickets: bool = False,
    dump_ticket_match: str = "",
    match_strategy: str = "rules",
    llm_api_base: str = "",
    llm_api_key: str = "",
    llm_model: str = "",
) -> int:
    logger = log or print
    meta = metadata if metadata is not None else _build_metadata(old_path, new_path)

    ticket_map: Dict[int, Any] = dict(tickets or {})
    if tickets_path:
        loaded = load_tickets(tickets_path)
        ticket_map.update(loaded)
        logger(f"已加载问题单台账：{tickets_path}（{len(loaded)} 条）")
    if ticket_prefix:
        logger(f"问题单前缀：{ticket_prefix}（编号形如 {ticket_prefix}-01）")
    if auto_match_tickets and not ticket_map:
        logger("警告：已开 --auto-match-tickets 但未提供问题单台账，将跳过内容匹配")

    def _match_ctx() -> MatchContext:
        return MatchContext(
            llm_enabled=bool(llm_api_key or llm_api_base or match_strategy in {"llm", "hybrid"}),
            llm_api_base=llm_api_base or "",
            llm_api_key=llm_api_key or "",
            llm_model=llm_model or "gpt-4o-mini",
        )

    if _files_identical(old_path, new_path):
        logger("旧版与新版文档内容一致，跳过解析与对比")
        if dump_match:
            payload = {
                "old_path": os.path.abspath(old_path),
                "new_path": os.path.abspath(new_path),
                "identical_files": True,
                "pair_count": 0,
                "method_counts": {},
                "pairs": [],
                "unmatched_old": [],
                "unmatched_new": [],
            }
            os.makedirs(os.path.dirname(os.path.abspath(dump_match)) or ".", exist_ok=True)
            with open(dump_match, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger(f"匹配诊断已输出：{dump_match}")
        if json_out:
            os.makedirs(os.path.dirname(os.path.abspath(json_out)) or ".", exist_ok=True)
            with open(json_out, "w", encoding="utf-8") as f:
                json.dump({"changes": [], "metadata": meta, "tickets": []}, f, ensure_ascii=False, indent=2)
            logger(f"文档差异 JSON 已输出：{json_out}")
        logger("生成更改单...")
        render_change_order(
            [],
            out_path,
            metadata=meta,
            use_table_key_column=use_table_key_column,
            problem_start=problem_start,
            tickets=ticket_map,
        )
        logger(f"完成：{out_path}")
        return 0

    logger("构建旧版 AST...")
    old_ast = build_ast(old_path)

    logger("构建新版 AST...")
    new_ast = build_ast(new_path)

    if dump_match:
        report = build_match_report(old_ast, new_ast, fuzzy_min_score=fuzzy_min_score)
        report["old_path"] = os.path.abspath(old_path)
        report["new_path"] = os.path.abspath(new_path)
        os.makedirs(os.path.dirname(os.path.abspath(dump_match)) or ".", exist_ok=True)
        with open(dump_match, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger(
            f"匹配诊断已输出：{dump_match} "
            f"(methods={report.get('method_counts')})"
        )

    logger(f"对比差异（fuzzy阈值={fuzzy_min_score:.2f}）...")
    changes = collect_changes(old_ast, new_ast, fuzzy_min_score=fuzzy_min_score)
    if auto_match_tickets and ticket_map:
        mctx = _match_ctx()
        strat = (match_strategy or "rules").strip().lower()
        if dump_ticket_match:
            report = match_report(
                changes,
                ticket_map,
                match_strategy=strat,
                match_context=mctx,
            )
            report["mode"] = "docx"
            os.makedirs(os.path.dirname(os.path.abspath(dump_ticket_match)) or ".", exist_ok=True)
            with open(dump_ticket_match, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger(
                f"问题单匹配诊断已输出：{dump_ticket_match} "
                f"(strategy={strat}, matched={report.get('matched_count')}/{report.get('ticket_count')})"
            )
        changes = apply_matched_tickets(
            changes,
            ticket_map,
            problem_start=problem_start,
            ticket_prefix=ticket_prefix,
            reorder=True,
            match_strategy=strat,
            match_context=mctx,
        )
        linked = sum(
            1
            for c in changes
            if (c.get("ticket_match_method") or "none") not in {"", "none"}
        )
        logger(f"问题单自动匹配[{strat}]：{linked}/{len(changes)} 条")
    else:
        changes = apply_tickets_to_changes(
            changes,
            ticket_map,
            problem_start=problem_start,
            ticket_prefix=ticket_prefix,
        )
        linked = sum(1 for c in changes if (c.get("ticket_no") or "").strip())
        if ticket_map or ticket_prefix:
            logger(f"问题单已关联 {linked}/{len(changes)} 条（台账序号 / 前缀自动编号）")
    logger(f"检测到 {len(changes)} 处差异")

    if json_out:
        os.makedirs(os.path.dirname(os.path.abspath(json_out)) or ".", exist_ok=True)
        payload = {
            "metadata": meta,
            "change_count": len(changes),
            "changes": changes_to_jsonable(changes),
            "tickets": [
                {
                    "seq": t.seq,
                    "title": t.title,
                    "ticket_no": t.ticket_no,
                }
                if hasattr(t, "seq")
                else t
                for t in (
                    ticket_map[k] for k in sorted(ticket_map.keys())
                )
            ],
        }
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger(f"文档差异 JSON 已输出：{json_out}")

    logger("生成更改单...")
    render_change_order(
        changes,
        out_path,
        metadata=meta,
        use_table_key_column=use_table_key_column,
        problem_start=problem_start,
        tickets=ticket_map,
    )
    logger(f"完成：{out_path}")

    return len(changes)


def run_code_diff(
    old_path: str,
    new_path: str,
    out_path: str,
    log: Optional[Callable[[str], None]] = None,
    show_c_gap_marker: bool = True,
    json_out: str = "",
    problem_start: int = 1,
    tickets_path: str = "",
    tickets: Optional[Dict[int, Any]] = None,
    ticket_prefix: str = "",
    auto_match_tickets: bool = False,
    dump_ticket_match: str = "",
    match_strategy: str = "rules",
    llm_api_base: str = "",
    llm_api_key: str = "",
    llm_model: str = "",
) -> int:
    logger = log or print
    ticket_map: Dict[int, Any] = dict(tickets or {})
    if tickets_path:
        loaded = load_tickets(tickets_path)
        ticket_map.update(loaded)
        logger(f"已加载问题单台账：{tickets_path}（{len(loaded)} 条）")
    if ticket_prefix:
        logger(f"问题单前缀：{ticket_prefix}（编号形如 {ticket_prefix}-01）")

    def _match_ctx() -> MatchContext:
        return MatchContext(
            llm_enabled=bool(llm_api_key or llm_api_base or match_strategy in {"llm", "hybrid"}),
            llm_api_base=llm_api_base or "",
            llm_api_key=llm_api_key or "",
            llm_model=llm_model or "gpt-4o-mini",
        )

    logger("收集代码差异...")
    gap_marker = "... (省略未改动片段) ..." if show_c_gap_marker else ""
    changes = collect_code_changes(old_path, new_path, c_gap_marker=gap_marker)
    if auto_match_tickets and ticket_map:
        mctx = _match_ctx()
        strat = (match_strategy or "rules").strip().lower()
        if dump_ticket_match:
            report = match_report(
                changes,
                ticket_map,
                match_strategy=strat,
                match_context=mctx,
            )
            report["mode"] = "code"
            os.makedirs(os.path.dirname(os.path.abspath(dump_ticket_match)) or ".", exist_ok=True)
            with open(dump_ticket_match, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger(
                f"问题单匹配诊断已输出：{dump_ticket_match} "
                f"(strategy={strat}, matched={report.get('matched_count')}/{report.get('ticket_count')})"
            )
        changes = apply_matched_tickets(
            changes,
            ticket_map,
            problem_start=problem_start,
            ticket_prefix=ticket_prefix,
            reorder=True,
            match_strategy=strat,
            match_context=mctx,
        )
        linked = sum(
            1
            for c in changes
            if (c.get("ticket_match_method") or "none") not in {"", "none"}
        )
        logger(f"问题单自动匹配[{strat}]：{linked}/{len(changes)} 条")
    else:
        changes = apply_tickets_to_changes(
            changes,
            ticket_map,
            problem_start=problem_start,
            ticket_prefix=ticket_prefix,
        )
        linked = sum(1 for c in changes if (c.get("ticket_no") or "").strip())
        if ticket_map or ticket_prefix:
            logger(f"问题单已关联 {linked}/{len(changes)} 条（台账序号 / 前缀自动编号）")
    logger(f"检测到 {len(changes)} 处代码差异")

    if json_out:
        os.makedirs(os.path.dirname(os.path.abspath(json_out)) or ".", exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(changes, f, ensure_ascii=False, indent=2)
        logger(f"代码差异 JSON 已输出：{json_out}")

    logger("生成代码更改单...")
    render_code_change_order(
        changes,
        out_path,
        problem_start=problem_start,
        tickets=ticket_map,
    )
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
        "--dump-match",
        default="",
        help="docx 模式下输出章节匹配诊断 JSON（method/score/未匹配候选）",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=DEFAULT_FUZZY_MIN_SCORE,
        help=f"docx 章节 fuzzy 配对最低分（默认 {DEFAULT_FUZZY_MIN_SCORE}）",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="输出机器可读差异 JSON（docx/code 均支持）",
    )
    parser.add_argument("--doc-no", default="", help="docx 更改单文号（写入元数据区）")
    parser.add_argument("--version", default="", help="docx 更改单版本号")
    parser.add_argument("--author", default="", help="docx 更改单编制人")
    parser.add_argument("--date", default="", help="docx 更改单编制日期（默认今天 YYYY-MM-DD）")
    parser.add_argument("--security", default="", help="docx 更改单密级")
    parser.add_argument("--remark", default="", help="docx 更改单备注")
    parser.add_argument(
        "--problem-start",
        type=int,
        default=1,
        help="问题编号起始序号（默认 1，可用于续号）",
    )
    parser.add_argument(
        "--no-table-key",
        action="store_true",
        help="禁用表格主键列对齐，回退为整行序列 diff",
    )
    parser.add_argument(
        "--tickets",
        default="",
        help="问题单台账路径（.csv / .json / .xlsx），列：序号,问题,问题单编号（如 DFKS112-WT-01）",
    )
    parser.add_argument(
        "--ticket-prefix",
        default="",
        help="问题单前缀（项目型号-WT），如 DFKS112-WT；未填单号时自动生成 DFKS112-WT-01、02…",
    )
    parser.add_argument(
        "--auto-match-tickets",
        action="store_true",
        help="自动将问题单台账匹配到变更（需 --tickets）；默认 rules，可用 --match-strategy",
    )
    parser.add_argument(
        "--match-strategy",
        choices=["rules", "llm", "hybrid"],
        default="rules",
        help="匹配策略：rules=规则；llm=仅大模型；hybrid=规则优先再 LLM 补全",
    )
    parser.add_argument(
        "--llm-api-base",
        default="",
        help="OpenAI 兼容 API Base（默认环境变量 DOCDIFF_LLM_API_BASE / OPENAI_API_BASE）",
    )
    parser.add_argument(
        "--llm-api-key",
        default="",
        help="API Key（默认环境变量 DOCDIFF_LLM_API_KEY / OPENAI_API_KEY）",
    )
    parser.add_argument(
        "--llm-model",
        default="",
        help="模型名（默认 gpt-4o-mini 或 DOCDIFF_LLM_MODEL）",
    )
    parser.add_argument(
        "--dump-ticket-match",
        default="",
        help="输出问题单自动匹配诊断 JSON（需同时 --auto-match-tickets 与 --tickets）",
    )
    parser.add_argument(
        "--write-ticket-template",
        default="",
        help="写出问题单台账模板后退出（扩展名决定格式：.csv/.json/.xlsx）",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.write_ticket_template:
        path = write_ticket_template(
            args.write_ticket_template,
            ticket_prefix=args.ticket_prefix or "DFKS112-WT",
        )
        print(f"问题单模板已写出：{path}")
        return

    if args.mode == "docx":
        if args.dump_ast:
            dump_ast_diagnostic(args.old, args.new, args.dump_ast)
        meta = _build_metadata(
            args.old,
            args.new,
            doc_no=args.doc_no,
            version=args.version,
            author=args.author,
            date=args.date,
            security=args.security,
            remark=args.remark,
        )
        run_diff(
            args.old,
            args.new,
            args.out,
            fuzzy_min_score=args.fuzzy_threshold,
            dump_match=args.dump_match,
            json_out=args.json_out,
            metadata=meta,
            use_table_key_column=not args.no_table_key,
            problem_start=args.problem_start,
            tickets_path=args.tickets,
            ticket_prefix=args.ticket_prefix,
            auto_match_tickets=args.auto_match_tickets,
            dump_ticket_match=args.dump_ticket_match,
            match_strategy=args.match_strategy,
            llm_api_base=args.llm_api_base,
            llm_api_key=args.llm_api_key,
            llm_model=args.llm_model,
        )
    else:
        run_code_diff(
            args.old,
            args.new,
            args.out,
            show_c_gap_marker=not args.hide_c_gap_marker,
            json_out=args.json_out,
            problem_start=args.problem_start,
            tickets_path=args.tickets,
            ticket_prefix=args.ticket_prefix,
            auto_match_tickets=args.auto_match_tickets,
            dump_ticket_match=args.dump_ticket_match,
            match_strategy=args.match_strategy,
            llm_api_base=args.llm_api_base,
            llm_api_key=args.llm_api_key,
            llm_model=args.llm_model,
        )


if __name__ == "__main__":
    main()
