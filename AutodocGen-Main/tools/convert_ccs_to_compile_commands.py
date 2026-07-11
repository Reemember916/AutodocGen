"""CCS .cproject -> compile_commands.json 转换工具。

用法:
    python tools/convert_ccs_to_compile_commands.py <project_root> [--output <path>]

示例:
    python tools/convert_ccs_to_compile_commands.py /path/to/project
    python tools/convert_ccs_to_compile_commands.py /path/to/project -o compile_commands.json
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _resolve_ccs_option_value(raw: str, *, project_root: str = "", project_name: str = "") -> str:
    text = html.unescape(str(raw or "")).strip().strip('"')
    if not text:
        return ""
    if not project_name:
        project_name = Path(project_root).name if project_root else ""
    replacements = {
        "${ProjName}": project_name,
        "${PROJECT_ROOT}": project_root,
        "${workspace_loc:/${ProjName}}": project_root,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    if text.startswith("${workspace_loc:/${ProjName}/") and text.endswith("}"):
        inner = text[len("${workspace_loc:/${ProjName}/") : -1]
        text = str(Path(project_root) / inner)
    elif text.startswith("${workspace_loc:/") and text.endswith("}"):
        inner = text[len("${workspace_loc:/") : -1]
        if "/" in inner:
            _, rel = inner.split("/", 1)
            text = str(Path(project_root) / rel)
    return text


def _load_ccs_project_settings(project_root: str) -> dict[str, list[str]]:
    root = Path(project_root or "")
    cproject = root / ".cproject"
    if not cproject.exists():
        print(f"错误: 未找到 {cproject}", file=sys.stderr)
        sys.exit(1)
    try:
        tree = ET.parse(cproject)
    except Exception as e:
        print(f"错误: 解析 .cproject 失败: {e}", file=sys.stderr)
        sys.exit(1)

    project_name = root.name
    include_paths: list[str] = []
    defines: list[str] = []

    for option in tree.findall(".//option"):
        option_id = str(option.get("id") or "")
        super_class = str(option.get("superClass") or "")
        option_name = str(option.get("name") or "")
        marker = " ".join([option_id, super_class, option_name]).upper()

        if "INCLUDE_PATH" in marker:
            for item in option.findall("./listOptionValue"):
                value = _resolve_ccs_option_value(
                    item.get("value"), project_root=project_root, project_name=project_name
                )
                if value and "${CG_TOOL_ROOT}" not in value:
                    include_paths.append(value)
        elif any(key in marker for key in ("DEFINE", "PREDEFINED_SYMBOL", "DEFINED_SYMBOL")):
            for item in option.findall("./listOptionValue"):
                value = _resolve_ccs_option_value(
                    item.get("value"), project_root=project_root, project_name=project_name
                )
                if value:
                    defines.append(value)
            direct_value = _resolve_ccs_option_value(
                option.get("value"), project_root=project_root, project_name=project_name
            )
            if direct_value and direct_value not in {"true", "false"}:
                defines.append(direct_value)

    seen_inc: set[str] = set()
    unique_inc: list[str] = []
    for p in include_paths:
        if p not in seen_inc:
            seen_inc.add(p)
            unique_inc.append(p)

    seen_def: set[str] = set()
    unique_def: list[str] = []
    for d in defines:
        if d not in seen_def:
            seen_def.add(d)
            unique_def.append(d)

    return {"include_paths": unique_inc, "defines": unique_def}


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

    print(f"解析 .cproject: {os.path.join(project_root, '.cproject')}")
    settings = _load_ccs_project_settings(project_root)

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
