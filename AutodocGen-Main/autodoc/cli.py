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
