"""CCS .cproject -> compile_commands.json 转换工具。

用法:
    python tools/convert_ccs_to_compile_commands.py <project_root> [--output <path>]

示例:
    python tools/convert_ccs_to_compile_commands.py /path/to/project
    python tools/convert_ccs_to_compile_commands.py /path/to/project -o compile_commands.json

CCS .cproject 解析逻辑（``_resolve_ccs_option_value`` /
``_load_ccs_project_settings``）复用 ``autodoc.compile_db`` 中的共享实现，
避免代码重复。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.compile_db import _load_ccs_project_settings


def _collect_c_files(project_root: str) -> list[str]:
    root = Path(project_root)
    src_dirs = []
    for candidate in ("src", "Src", "SRC"):
        d = root / candidate
        if d.is_dir():
            src_dirs.append(d)
    if not src_dirs:
        src_dirs = [root]

    exclude_dirs = {".git", ".settings", "debug", "release", "__pycache__", "Debug", "Release"}
    c_files: list[str] = []

    for src_dir in src_dirs:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            for f in filenames:
                if f.lower().endswith(".c"):
                    c_files.append(os.path.join(dirpath, f))

    return sorted(set(c_files))


def _build_compile_commands(
    project_root: str,
    include_paths: list[str],
    defines: list[str],
    c_files: list[str],
) -> list[dict[str, Any]]:
    root = Path(project_root)
    entries: list[dict[str, Any]] = []

    include_flags: list[str] = []
    for p in include_paths:
        resolved = Path(p)
        if not resolved.is_absolute():
            resolved = root / p
        if resolved.exists():
            include_flags.extend(["-I", str(resolved.resolve())])

    define_flags: list[str] = []
    for d in defines:
        define_flags.append(f"-D{d}")

    for c_file in c_files:
        abs_path = str(Path(c_file).resolve())
        entry: dict[str, Any] = {
            "directory": str(root.resolve()),
            "file": abs_path,
            "arguments": ["clang", "-x", "c"]
                + define_flags
                + include_flags
                + [abs_path],
        }
        entries.append(entry)

    return entries


def main():
    parser = argparse.ArgumentParser(
        description="CCS .cproject -> compile_commands.json 转换工具"
    )
    parser.add_argument(
        "project_root",
        help="CCS 项目根目录（包含 .cproject 的目录）",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出路径（默认: <project_root>/compile_commands.json）",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(args.project_root)
    if not os.path.isdir(project_root):
        print(f"错误: 目录不存在: {project_root}", file=sys.stderr)
        sys.exit(1)

    cproject_path = os.path.join(project_root, ".cproject")
    if not os.path.isfile(cproject_path):
        print(f"错误: 未找到 {cproject_path}", file=sys.stderr)
        sys.exit(1)

    print(f"解析 .cproject: {cproject_path}")
    settings = _load_ccs_project_settings(project_root)
    if not settings["include_paths"] and not settings["defines"]:
        print("警告: .cproject 解析结果为空（可能解析失败）", file=sys.stderr)

    print(f"  include paths: {len(settings['include_paths'])}")
    for p in settings["include_paths"]:
        print(f"    - {p}")
    print(f"  defines: {len(settings['defines'])}")
    for d in settings["defines"]:
        print(f"    - {d}")

    c_files = _collect_c_files(project_root)
    print(f"  C 文件: {len(c_files)}")

    if not c_files:
        print("警告: 未找到任何 .c 文件", file=sys.stderr)

    entries = _build_compile_commands(
        project_root,
        settings["include_paths"],
        settings["defines"],
        c_files,
    )

    output_path = args.output
    if not output_path:
        output_path = os.path.join(project_root, "compile_commands.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\n已生成: {output_path} ({len(entries)} 个条目)")


if __name__ == "__main__":
    main()
