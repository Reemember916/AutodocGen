"""CLI entry point — argument parsing and main dispatch."""

from __future__ import annotations

import sys


def parse_args():
    from .backend import APP_NAME, APP_VERSION, DEFAULT_SECTION_PREFIX, DEFAULT_REQ_ID_PREFIX

    import argparse
    parser = argparse.ArgumentParser(description=f"CSCI 设计说明书生成工具 {APP_VERSION}")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    sub = parser.add_subparsers(dest="command")

    guip = sub.add_parser("gui", help="Launch GUI (Qt)")

    docp = sub.add_parser("doc", help="命令行生成文档")
    docp.add_argument("-f", "--c-file")
    docp.add_argument("-d", "--project-dir")
    docp.add_argument("-o", "--output", required=True)
    docp.add_argument("--function", default="", help="仅导出指定函数（需配合 --c-file）")
    docp.add_argument("--revision-profile", default="", help="函数级修订档案 JSON 路径")
    docp.add_argument("--section-prefix", default=DEFAULT_SECTION_PREFIX,
                      help="四级标题前缀，如 609_ 或 5.1.1.")
    docp.add_argument("--req-prefix", default=DEFAULT_REQ_ID_PREFIX,
                      help="需求ID前缀，如 D/R_SDD01_609")
    docp.add_argument("--verbose", action="store_true")
    docp.add_argument("--template", default="", help="可选：使用的模板 docx 路径")
    docp.add_argument("--ai-logic-policy", default="hybrid", choices=["hybrid", "ai_non_structured"],
                      help=argparse.SUPPRESS)
    docp.add_argument("--ai-context-scope", default="target_only", choices=["target_only", "target", "local_neighbors", "local", "project", "deep"],
                      help=argparse.SUPPRESS)
    docp.add_argument("--logic-no-comment", action="store_true",
                      help="逻辑语句忽略注释，仅按名称映射直译")
    docp.add_argument("--codegraph", default="auto", choices=["auto", "off", "force"],
                      help="CodeGraph 项目级调用图增强：auto=可用则启用，off=关闭，force=不可用则失败")
    docp.add_argument("--graph-output", default="off", choices=["off", "html", "word", "both"],
                      help="调用图谱输出位置")
    docp.add_argument("--graph-depth", type=int, default=2,
                      help="调用/影响图遍历深度")
    docp.add_argument("--graph-max-nodes", type=int, default=40,
                      help="单张调用图最大节点数")
    docp.add_argument("--review-output", default="off", choices=["off", "html"],
                      help="生成离线人工审查 HTML 包：off=关闭，html=输出 review_bundle.json + index.html")
    docp.add_argument("--review-dir", default="",
                      help="审查 HTML 包输出目录；默认使用 <输出文件名>_review")
    docp.add_argument("--review-decisions", default="",
                      help="人工审查页导出的 generation_review_decisions.json；仅应用已通过函数")
    docp.add_argument("--review-bundle", default="",
                      help="与审查决策对应的 review_bundle.json；默认自动发现")
    docp.add_argument("--allow-stale-review", action="store_true",
                      help="允许应用源码哈希已变化的审查决策（不建议）")

    reviewp = sub.add_parser("review-apply", help="将人工审查决策转换为 revision profile")
    reviewp.add_argument("--bundle", required=True, help="review_bundle.json 路径")
    reviewp.add_argument("--decisions", required=True, help="generation_review_decisions.json 路径")
    reviewp.add_argument("-o", "--output", required=True, help="输出 revision_profile.json 路径")
    reviewp.add_argument("--allow-stale", action="store_true", help="允许应用过期决策")

    termp = sub.add_parser("term-repair", help="根据一致性报告写回符号字典/记忆库")
    termp.add_argument("--report", required=True, help="consistency_report.json 路径")
    termp.add_argument("--dict", dest="dict_path", default="", help="symbol_dictionary.json 路径")
    termp.add_argument("--memory", dest="memory_path", default="", help="autodoc_symbol_memory.json 路径")
    termp.add_argument("--dry-run", action="store_true", help="只计算补丁，不写盘")
    termp.add_argument("--no-backup", action="store_true", help="写盘时不创建 .bak")
    termp.add_argument(
        "--severity",
        default="high,medium",
        help="应用的严重级别，逗号分隔（默认 high,medium）",
    )
    termp.add_argument("-o", "--output", default="", help="可选：写出 patch JSON 路径")

    retryp = sub.add_parser("retry", help="根据失败列表重建函数设计并写出 docx")
    retryp.add_argument("--failures", required=True, help="failures.json 路径")
    retryp.add_argument("-o", "--output", required=True, help="输出 docx 路径")
    retryp.add_argument("-f", "--c-file", default="", help="C 源文件（失败记录缺 body 时重解析）")
    retryp.add_argument("-d", "--project-dir", default="", help="工程根目录（可选）")
    retryp.add_argument("--merge", action="store_true", help="API 兼容标志（当前仍生成重试文档）")
    retryp.add_argument("--section-prefix", default=DEFAULT_SECTION_PREFIX)
    retryp.add_argument("--req-prefix", default=DEFAULT_REQ_ID_PREFIX)
    retryp.add_argument("--verbose", action="store_true")
    retryp.add_argument("--template", default="")

    return parser.parse_args()


def main():
    from .backend import (
        GenConfig,
        NoDataError,
        ToolError,
        ParseError,
        generate_design_doc_for_project,
        generate_design_doc_from_file,
        generate_design_doc_for_single_function,
    )

    # 无参数 → 自动进入 GUI 模式
    if len(sys.argv) == 1:
        _run_default_gui()
        return

    args = parse_args()
    if args.command == "gui":
        _run_default_gui()
        return

    if args.command == "review-apply":
        from .review_decisions import write_revision_profile_from_review

        profile = write_revision_profile_from_review(
            bundle_path=args.bundle,
            decisions_path=args.decisions,
            output_path=args.output,
            allow_stale=bool(args.allow_stale),
        )
        print(f"审查决策已转换：{args.output}")
        print(f"已通过函数：{len(profile.get('functions') or {})}")
        return

    if args.command == "term-repair":
        import json
        from .term_checker import apply_repair_from_report

        with open(args.report, "r", encoding="utf-8") as handle:
            report = json.load(handle)
        severities = tuple(
            s.strip() for s in str(args.severity or "").split(",") if s.strip()
        ) or ("high", "medium")
        if not args.dict_path and not args.memory_path and not args.dry_run:
            print("请指定 --dict 和/或 --memory，或使用 --dry-run", file=sys.stderr)
            raise SystemExit(2)
        result = apply_repair_from_report(
            report,
            dict_path=args.dict_path,
            memory_path=args.memory_path,
            dry_run=bool(args.dry_run),
            backup=(not bool(args.no_backup)),
            severities=severities,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print(f"补丁结果已写出：{args.output}")
        print(f"术语修复：applied={result.applied_count} dry_run={result.dry_run}")
        if result.wrote_dict:
            print(f"已更新字典：{result.dict_path}")
        if result.wrote_memory:
            print(f"已更新记忆库：{result.memory_path}")
        for key, value in list(result.patch.items())[:20]:
            print(f"  {key} -> {value}")
        if len(result.patch) > 20:
            print(f"  ... 共 {len(result.patch)} 项")
        return

    if args.command == "retry":
        from .retry import load_failures, run_retry_generation

        failures = load_failures(args.failures)
        cfg = GenConfig(
            verbose=bool(args.verbose),
            ai_assist=False,
            ai_mode=0,
            section_prefix=args.section_prefix,
            req_id_prefix=args.req_prefix,
            template_path=args.template or "",
            extra_params={},
        )
        result = run_retry_generation(
            failures,
            args.output,
            cfg,
            c_file=args.c_file or "",
            project_dir=args.project_dir or "",
            merge=bool(args.merge),
        )
        print(f"重试完成：ok={result.ok} output={result.output_path}")
        print(f"成功：{len(result.retried)} 失败：{len(result.still_failed)}")
        for name in result.retried:
            print(f"  ok  {name}")
        for item in result.still_failed:
            print(f"  fail {item.get('func_name')}: {item.get('error_message')}")
        if not result.ok:
            raise SystemExit(1)
        return

    if args.command == "doc":
        extra_params = {
            "codegraph_mode": args.codegraph,
            "graph_output": args.graph_output,
            "graph_depth": str(max(1, int(args.graph_depth or 2))),
            "graph_max_nodes": str(max(5, int(args.graph_max_nodes or 40))),
            "codegraph_auto_index": "1",
            "review_output": args.review_output,
            "review_dir": args.review_dir,
            "ai_context_scope": args.ai_context_scope,
        }
        if args.revision_profile:
            extra_params["revision_profile"] = args.revision_profile
        if args.review_decisions:
            from .review_decisions import resolve_review_bundle_path, write_revision_profile_from_review

            bundle_path = resolve_review_bundle_path(
                args.review_decisions,
                explicit_bundle=args.review_bundle,
                output_docx=args.output,
                review_dir=args.review_dir,
            )
            review_profile = str(args.output) + ".review_profile.json"
            write_revision_profile_from_review(
                bundle_path=bundle_path,
                decisions_path=args.review_decisions,
                output_path=review_profile,
                allow_stale=bool(args.allow_stale_review),
            )
            extra_params["revision_profile"] = review_profile
            print(f"已加载人工审查决策：{args.review_decisions}")
        cfg = GenConfig(
            verbose=args.verbose,
            ai_assist=False,
            section_prefix=args.section_prefix,
            req_id_prefix=args.req_prefix,
            template_path=args.template,
            ai_logic_policy=getattr(args, "ai_logic_policy", "hybrid"),
            logic_use_comment=(not bool(getattr(args, "logic_no_comment", False))),
            codegraph_mode=args.codegraph,
            graph_output=args.graph_output,
            graph_depth=max(1, int(args.graph_depth or 2)),
            graph_max_nodes=max(5, int(args.graph_max_nodes or 40)),
            extra_params=extra_params,
        )
        try:
            if args.function:
                if not args.c_file:
                    raise ParseError("--function 需配合 --c-file 使用")
                generate_design_doc_for_single_function(
                    args.c_file,
                    args.function,
                    args.output,
                    cfg,
                    project_root=(args.project_dir or None),
                )
            elif args.project_dir:
                generate_design_doc_for_project(args.project_dir, args.output, cfg)
            elif args.c_file:
                generate_design_doc_from_file(args.c_file, args.output, cfg)
            else:
                raise ParseError("缺少输入：请指定 --c-file 或 --project-dir")
            print(f"文档已生成：{args.output}")
        except NoDataError as e:
            print(f"无可生成数据：{e}", file=sys.stderr)
        except ToolError as e:
            print(f"生成失败：{e}", file=sys.stderr)
            raise SystemExit(1) from e
    else:
        _run_default_gui()


def _run_qt_gui_or_raise() -> None:
    from . import backend as _backend_mod
    from qt_gui.app import run_qt_gui
    run_qt_gui(backend=_backend_mod)


def _run_default_gui() -> None:
    _run_qt_gui_or_raise()


__all__ = ["parse_args", "main"]


if __name__ == "__main__":
    main()
