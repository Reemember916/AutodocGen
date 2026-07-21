"""Incremental generation support — change detection and cache management."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence


@dataclass
class FileFingerprint:
    """文件指纹，用于检测变更。"""

    path: str
    mtime: float
    size: int
    content_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "mtime": self.mtime,
            "size": self.size,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileFingerprint":
        return cls(
            path=data.get("path", ""),
            mtime=float(data.get("mtime", 0) or 0),
            size=int(data.get("size", 0) or 0),
            content_hash=data.get("content_hash", ""),
        )


@dataclass
class FunctionFingerprint:
    """函数指纹，用于检测函数级变更。"""

    func_name: str
    file_path: str
    line_start: int
    line_end: int
    signature_hash: str = ""
    body_hash: str = ""
    # 语句级指纹：源代码行号 -> hash
    statement_hashes: dict[int, str] = field(default_factory=dict)
    # 逻辑语句缓存：源代码行号 -> 生成的逻辑描述
    cached_logic_lines: dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "func_name": self.func_name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "signature_hash": self.signature_hash,
            "body_hash": self.body_hash,
            "statement_hashes": self.statement_hashes,
            "cached_logic_lines": self.cached_logic_lines,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FunctionFingerprint":
        return cls(
            func_name=data.get("func_name", ""),
            file_path=data.get("file_path", ""),
            line_start=int(data.get("line_start", 0) or 0),
            line_end=int(data.get("line_end", 0) or 0),
            signature_hash=data.get("signature_hash", ""),
            body_hash=data.get("body_hash", ""),
            statement_hashes=data.get("statement_hashes") or {},
            cached_logic_lines=data.get("cached_logic_lines") or {},
        )


@dataclass
class ConsistencyContext:
    """一致性上下文，用于保证增量生成的一致性。"""

    # 全局变量 -> 中文映射（必须一致）
    global_symbol_translations: dict[str, str] = field(default_factory=dict)
    # 函数名 -> 标题映射（必须一致）
    func_titles: dict[str, str] = field(default_factory=dict)
    # 全局术语使用频率
    global_term_frequency: dict[str, dict[str, int]] = field(default_factory=dict)
    # 文档版本
    doc_version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "global_symbol_translations": self.global_symbol_translations,
            "func_titles": self.func_titles,
            "global_term_frequency": self.global_term_frequency,
            "doc_version": self.doc_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsistencyContext":
        return cls(
            global_symbol_translations=data.get("global_symbol_translations") or {},
            func_titles=data.get("func_titles") or {},
            global_term_frequency=data.get("global_term_frequency") or {},
            doc_version=data.get("doc_version") or "1.0",
        )

    def is_global_symbol(self, symbol: str) -> bool:
        """判断是否为全局变量。"""
        if not symbol:
            return False
        # g_ 前缀为全局变量
        if symbol.startswith("g_"):
            return True
        # 无前缀或非 l_/v_/p_ 前缀也可能是全局
        if not any(symbol.startswith(p) for p in ("l_", "v_", "p_", "ls_", "gs_")):
            # 进一步检查：如果是结构体成员或宏定义，也算全局
            if "." in symbol or symbol.isupper():
                return True
        return False

    def record_global_translation(self, symbol: str, cn_name: str) -> None:
        """记录全局符号翻译。"""
        if not symbol or not cn_name:
            return
        if not self.is_global_symbol(symbol):
            return  # 只记录全局变量

        # 更新频率
        if symbol not in self.global_term_frequency:
            self.global_term_frequency[symbol] = {}
        self.global_term_frequency[symbol][cn_name] = self.global_term_frequency[symbol].get(cn_name, 0) + 1
        # 选择最常用的翻译
        most_common = max(self.global_term_frequency[symbol].items(), key=lambda x: x[1])[0]
        self.global_symbol_translations[symbol] = most_common

    def get_global_translation(self, symbol: str) -> Optional[str]:
        """获取全局符号的翻译。"""
        if self.is_global_symbol(symbol):
            return self.global_symbol_translations.get(symbol)
        return None  # 局部变量不返回约束

    def record_func_title(self, func_name: str, title: str) -> None:
        """记录函数标题。"""
        if func_name and title:
            self.func_titles[func_name] = title

    def get_func_title(self, func_name: str) -> Optional[str]:
        """获取函数标题。"""
        return self.func_titles.get(func_name)

    def bump_version(self) -> str:
        """升级文档版本号。"""
        try:
            major, minor = self.doc_version.split(".")
            self.doc_version = f"{major}.{int(minor) + 1}"
        except Exception:
            self.doc_version = "1.1"
        return self.doc_version


@dataclass
class IncrementalState:
    """增量生成状态。"""

    file_fingerprints: dict[str, FileFingerprint] = field(default_factory=dict)
    function_fingerprints: dict[str, FunctionFingerprint] = field(default_factory=dict)
    generated_designs: dict[str, dict] = field(default_factory=dict)  # func_key -> design dict
    consistency_context: ConsistencyContext = field(default_factory=ConsistencyContext)
    version: str = "2.0"  # 升级版本号

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "file_fingerprints": {k: v.to_dict() for k, v in self.file_fingerprints.items()},
            "function_fingerprints": {k: v.to_dict() for k, v in self.function_fingerprints.items()},
            "generated_designs": self.generated_designs,
            "consistency_context": self.consistency_context.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IncrementalState":
        state = cls()
        state.version = data.get("version", "1.0")
        state.file_fingerprints = {
            k: FileFingerprint.from_dict(v) for k, v in (data.get("file_fingerprints") or {}).items()
        }
        state.function_fingerprints = {
            k: FunctionFingerprint.from_dict(v) for k, v in (data.get("function_fingerprints") or {}).items()
        }
        state.generated_designs = data.get("generated_designs") or {}
        state.consistency_context = ConsistencyContext.from_dict(data.get("consistency_context") or {})
        return state

    def extract_consistency_from_designs(self) -> None:
        """从已有设计中提取一致性上下文（仅全局变量）。"""
        for func_key, design in self.generated_designs.items():
            # 提取函数标题
            func_name = design.get("func_name", "")
            title = design.get("title", "")
            if func_name and title:
                self.consistency_context.record_func_title(func_name, title)

            # 仅提取全局变量翻译（g_ 前缀或无局部前缀）
            for elem in design.get("io_elements") or []:
                ident = elem.get("ident", "")
                name = elem.get("name", "")
                if ident and name and self.consistency_context.is_global_symbol(ident):
                    self.consistency_context.record_global_translation(ident, name)

            # 局部变量不记录（不同函数可能含义不同）


def compute_file_fingerprint(file_path: str, *, compute_hash: bool = True) -> FileFingerprint:
    """计算文件指纹。"""
    path = Path(file_path)
    if not path.exists():
        return FileFingerprint(path=file_path, mtime=0, size=0)

    stat = path.stat()
    mtime = stat.st_mtime
    size = stat.st_size

    content_hash = ""
    if compute_hash:
        try:
            content = path.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            pass

    return FileFingerprint(
        path=str(path.resolve()),
        mtime=mtime,
        size=size,
        content_hash=content_hash,
    )


def compute_function_fingerprint(
    func_name: str,
    file_path: str,
    line_start: int,
    line_end: int,
    body: str,
    signature: str = "",
    *,
    compute_statement_hashes: bool = True,
) -> FunctionFingerprint:
    """计算函数指纹，包含语句级哈希。"""
    body_hash = ""
    statement_hashes: dict[int, str] = {}

    if body:
        body_hash = hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()[:16]

        # 计算语句级哈希
        if compute_statement_hashes:
            body_lines = body.splitlines()
            for i, line in enumerate(body_lines):
                stripped = line.strip()
                # 跳过空行和纯注释行
                if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                    continue
                # 跳过单独的 { 或 }
                if stripped in ("{", "}", "{", "}"):
                    continue
                # 计算语句哈希
                stmt_hash = hashlib.sha256(stripped.encode("utf-8", errors="ignore")).hexdigest()[:8]
                statement_hashes[line_start + i] = stmt_hash

    signature_hash = ""
    if signature:
        signature_hash = hashlib.sha256(signature.encode("utf-8", errors="ignore")).hexdigest()[:16]

    return FunctionFingerprint(
        func_name=func_name,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        signature_hash=signature_hash,
        body_hash=body_hash,
        statement_hashes=statement_hashes,
    )


def detect_file_changes(
    files: Sequence[str],
    previous_state: IncrementalState,
    *,
    use_hash: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """
    检测文件变更。

    Returns:
        (changed_files, new_files, deleted_files)
    """
    changed: list[str] = []
    new: list[str] = []
    deleted: list[str] = []

    current_files = set(str(Path(f).resolve()) for f in files)
    previous_files = set(previous_state.file_fingerprints.keys())

    # 新增文件
    for f in current_files - previous_files:
        new.append(f)

    # 删除文件
    for f in previous_files - current_files:
        deleted.append(f)

    # 检查现有文件是否变更
    for f in current_files & previous_files:
        current_fp = compute_file_fingerprint(f, compute_hash=use_hash)
        previous_fp = previous_state.file_fingerprints.get(f)

        if previous_fp is None:
            new.append(f)
        elif current_fp.mtime != previous_fp.mtime or current_fp.size != previous_fp.size:
            changed.append(f)
        elif use_hash and current_fp.content_hash != previous_fp.content_hash:
            changed.append(f)

    return changed, new, deleted


def detect_function_changes(
    func_data_list: Sequence[dict],
    previous_state: IncrementalState,
) -> tuple[list[str], list[str]]:
    """
    检测函数变更。

    Returns:
        (changed_func_keys, unchanged_func_keys)
    """
    changed: list[str] = []
    unchanged: list[str] = []

    for func_data in func_data_list or []:
        func_info = func_data.get("func_info") or {}
        func_name = func_info.get("func_name", "")
        file_path = func_data.get("source_file", "") or func_data.get("file_context", {}).get("source_file", "")
        line_start = int(func_info.get("line_start", 0) or 0)
        line_end = int(func_info.get("line_end", 0) or 0)
        body = func_data.get("body", "") or func_info.get("body", "")
        signature = func_info.get("prototype", "")

        func_key = f"{file_path}::{func_name}"

        current_fp = compute_function_fingerprint(
            func_name=func_name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            body=body,
            signature=signature,
        )

        previous_fp = previous_state.function_fingerprints.get(func_key)

        if previous_fp is None:
            changed.append(func_key)
        elif current_fp.body_hash != previous_fp.body_hash:
            changed.append(func_key)
        elif current_fp.signature_hash != previous_fp.signature_hash:
            changed.append(func_key)
        else:
            unchanged.append(func_key)

    return changed, unchanged


def detect_statement_changes(
    current_fp: FunctionFingerprint,
    previous_fp: FunctionFingerprint,
) -> tuple[set[int], set[int]]:
    """
    检测语句级变更。

    Args:
        current_fp: 当前函数指纹
        previous_fp: 之前的函数指纹

    Returns:
        (changed_line_numbers, unchanged_line_numbers)
    """
    changed_lines: set[int] = set()
    unchanged_lines: set[int] = set()

    current_hashes = current_fp.statement_hashes
    previous_hashes = previous_fp.statement_hashes

    # 所有语句行号
    all_lines = set(current_hashes.keys()) | set(previous_hashes.keys())

    for line_no in all_lines:
        current_hash = current_hashes.get(line_no)
        previous_hash = previous_hashes.get(line_no)

        if current_hash is None or previous_hash is None:
            # 新增或删除的语句
            changed_lines.add(line_no)
        elif current_hash != previous_hash:
            # 变更的语句
            changed_lines.add(line_no)
        else:
            # 未变更的语句
            unchanged_lines.add(line_no)

    return changed_lines, unchanged_lines


def merge_logic_lines_with_cache(
    new_logic_lines: Sequence[str],
    cached_logic_lines: dict[int, str],
    changed_lines: set[int],
    body_line_start: int,
    body: str,
) -> list[str]:
    """
    合并新生成的逻辑语句与缓存的未变更语句。

    Args:
        new_logic_lines: 新生成的逻辑语句列表
        cached_logic_lines: 缓存的逻辑语句 {源代码行号: 逻辑描述}
        changed_lines: 变更的源代码行号集合
        body_line_start: 函数体起始行号
        body: 函数体源代码

    Returns:
        合并后的逻辑语句列表
    """
    if not cached_logic_lines or not body:
        return list(new_logic_lines)

    # 构建源代码行号到逻辑语句的映射
    body_lines = body.splitlines()
    result_lines: list[str] = []

    # 简化策略：按顺序合并
    # 1. 对于变更的语句，使用新生成的描述
    # 2. 对于未变更的语句，优先使用缓存的描述

    new_idx = 0
    used_cache_keys: set[int] = set()

    for i, body_line in enumerate(body_lines):
        line_no = body_line_start + i
        stripped = body_line.strip()

        # 跳过空行、注释、括号
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if stripped in ("{", "}"):
            continue

        # 检查是否有缓存的逻辑描述
        if line_no not in changed_lines and line_no in cached_logic_lines:
            cached_desc = cached_logic_lines[line_no]
            if cached_desc and line_no not in used_cache_keys:
                result_lines.append(cached_desc)
                used_cache_keys.add(line_no)
                continue

        # 使用新生成的描述（如果有）
        if new_idx < len(new_logic_lines):
            result_lines.append(new_logic_lines[new_idx])
            new_idx += 1

    # 添加剩余的新生成描述
    while new_idx < len(new_logic_lines):
        result_lines.append(new_logic_lines[new_idx])
        new_idx += 1

    return result_lines


def build_statement_to_logic_map(
    logic_lines: Sequence[str],
    body: str,
    body_line_start: int,
) -> dict[int, str]:
    """
    构建源代码行号到逻辑语句的映射。

    Args:
        logic_lines: 逻辑语句列表
        body: 函数体源代码
        body_line_start: 函数体起始行号

    Returns:
        {源代码行号: 逻辑描述}
    """
    result: dict[int, str] = {}

    if not body or not logic_lines:
        return result

    body_lines = body.splitlines()
    logic_idx = 0

    for i, body_line in enumerate(body_lines):
        line_no = body_line_start + i
        stripped = body_line.strip()

        # 跳过空行、注释、括号
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if stripped in ("{", "}"):
            continue

        # 将逻辑语句映射到对应的源代码行
        if logic_idx < len(logic_lines):
            result[line_no] = logic_lines[logic_idx]
            logic_idx += 1

    return result


def load_incremental_state(project_root: str) -> IncrementalState:
    """加载增量状态。"""
    state_path = Path(project_root) / ".autodoc" / "incremental_state.json"
    if not state_path.exists():
        return IncrementalState()

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return IncrementalState.from_dict(data)
    except Exception:
        return IncrementalState()


def save_incremental_state(project_root: str, state: IncrementalState) -> None:
    """保存增量状态。"""
    state_path = Path(project_root) / ".autodoc" / "incremental_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        state_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def filter_tasks_for_incremental(
    tasks: Sequence[dict],
    previous_state: IncrementalState,
    *,
    force_all: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    过滤任务，分离需要生成和可跳过的任务。

    Returns:
        (tasks_to_generate, tasks_to_skip)
    """
    if force_all:
        return list(tasks), []

    to_generate: list[dict] = []
    to_skip: list[dict] = []

    for task in tasks or []:
        func_name = task.get("func_name", "")
        file_path = task.get("source_file", "")
        func_key = f"{file_path}::{func_name}"

        # 检查是否有缓存的生成结果
        cached_design = previous_state.generated_designs.get(func_key)
        if not cached_design:
            to_generate.append(task)
            continue

        # 检查函数是否变更
        body = task.get("body", "")
        signature = task.get("prototype", "")
        current_fp = compute_function_fingerprint(
            func_name=func_name,
            file_path=file_path,
            line_start=task.get("line_start", 0),
            line_end=task.get("line_end", 0),
            body=body,
            signature=signature,
        )

        previous_fp = previous_state.function_fingerprints.get(func_key)
        if previous_fp is None:
            to_generate.append(task)
        elif current_fp.body_hash != previous_fp.body_hash:
            to_generate.append(task)
        else:
            # 函数未变更，可以跳过
            task["_cached_design"] = cached_design
            to_skip.append(task)

    return to_generate, to_skip


def build_consistency_constraints(
    state: IncrementalState,
    symbols_to_check: Sequence[str],
) -> dict[str, str]:
    """
    构建一致性约束，仅针对全局变量。

    Args:
        state: 增量状态
        symbols_to_check: 需要检查的符号列表

    Returns:
        {global_symbol: preferred_cn_name} 约束字典（仅全局变量）
    """
    constraints: dict[str, str] = {}
    for symbol in symbols_to_check:
        # 仅对全局变量生成约束
        translation = state.consistency_context.get_global_translation(symbol)
        if translation:
            constraints[symbol] = translation
    return constraints


def detect_dependent_changes(
    changed_funcs: Sequence[str],
    all_func_data: Sequence[dict],
    previous_state: IncrementalState,
) -> set[str]:
    """
    检测依赖变更：如果被调用函数变更，调用者也需要重新生成。

    Args:
        changed_funcs: 已变更的函数名列表
        all_func_data: 所有函数数据
        previous_state: 之前的增量状态

    Returns:
        需要重新生成的函数键集合
    """
    dependent_funcs: set[str] = set()
    changed_set = set(changed_funcs)

    for func_data in all_func_data or []:
        func_info = func_data.get("func_info") or {}
        func_name = func_info.get("func_name", "")
        file_path = func_data.get("source_file", "") or func_data.get("file_context", {}).get("source_file", "")
        func_key = f"{file_path}::{func_name}"

        # 检查是否调用了变更的函数
        callees = func_data.get("callees") or func_info.get("callees") or []
        for callee in callees:
            callee_name = callee if isinstance(callee, str) else callee.get("name", "")
            if callee_name in changed_set:
                dependent_funcs.add(func_key)
                break

    return dependent_funcs


def apply_consistency_to_design(
    design: dict,
    constraints: dict[str, str],
) -> dict:
    """
    将一致性约束应用到设计结果（仅修正全局变量）。

    Args:
        design: 函数设计
        constraints: {global_symbol: preferred_cn_name} 约束

    Returns:
        修正后的设计
    """
    if not constraints:
        return design

    modified = dict(design)

    # 仅修正全局变量（g_ 前缀或无局部前缀）
    io_elements = list(modified.get("io_elements") or [])
    for elem in io_elements:
        ident = elem.get("ident", "")
        # 仅对全局变量应用约束
        if ident in constraints and (ident.startswith("g_") or not any(ident.startswith(p) for p in ("l_", "v_", "p_"))):
            elem["name"] = constraints[ident]
    modified["io_elements"] = io_elements

    # 局部变量不修正（不同函数可能含义不同）
    # local_elements 保持原样

    return modified


def update_state_with_new_designs(
    state: IncrementalState,
    new_designs: Sequence[dict],
    *,
    func_data_list: Optional[Sequence[dict]] = None,
) -> None:
    """
    用新生成的设计更新增量状态，包含语句级缓存。

    Args:
        state: 增量状态
        new_designs: 新生成的设计列表
        func_data_list: 函数数据列表（用于构建语句级缓存）
    """
    # 构建函数数据映射
    func_data_map: dict[str, dict] = {}
    for fd in func_data_list or []:
        finfo = fd.get("func_info") or {}
        fname = finfo.get("func_name", "") or fd.get("func_name", "")
        fpath = fd.get("source_file", "") or fd.get("file_context", {}).get("source_file", "")
        if fname and fpath:
            func_data_map[f"{fpath}::{fname}"] = fd

    for design in new_designs or []:
        func_name = design.get("func_name", "")
        file_path = design.get("source_file", "")
        func_key = f"{file_path}::{func_name}"

        # 更新设计缓存
        state.generated_designs[func_key] = design

        # 更新一致性上下文
        title = design.get("title", "")
        if func_name and title:
            state.consistency_context.record_func_title(func_name, title)

        # 仅记录全局变量翻译（局部变量不同函数可能含义不同）
        for elem in design.get("io_elements") or []:
            ident = elem.get("ident", "")
            name = elem.get("name", "")
            if ident and name and state.consistency_context.is_global_symbol(ident):
                state.consistency_context.record_global_translation(ident, name)

        # 更新语句级缓存
        func_data = func_data_map.get(func_key)
        if func_data:
            body = func_data.get("body", "") or func_data.get("func_info", {}).get("body", "")
            line_start = int(func_data.get("line_start", 0) or func_data.get("func_info", {}).get("line_start", 0) or 0)
            logic_lines = design.get("logic_lines") or ()

            if body and logic_lines:
                # 构建语句级缓存
                stmt_to_logic = build_statement_to_logic_map(
                    logic_lines, body, line_start
                )

                # 更新函数指纹中的语句缓存
                if func_key in state.function_fingerprints:
                    state.function_fingerprints[func_key].cached_logic_lines = stmt_to_logic
                else:
                    # 创建新的指纹
                    fp = compute_function_fingerprint(
                        func_name=func_name,
                        file_path=file_path,
                        line_start=line_start,
                        line_end=int(func_data.get("line_end", 0) or func_data.get("func_info", {}).get("line_end", 0) or 0),
                        body=body,
                        signature=func_data.get("prototype", "") or func_data.get("func_info", {}).get("prototype", ""),
                    )
                    fp.cached_logic_lines = stmt_to_logic
                    state.function_fingerprints[func_key] = fp

        # 局部变量不记录到一致性上下文


__all__ = [
    "FileFingerprint",
    "FunctionFingerprint",
    "ConsistencyContext",
    "IncrementalState",
    "compute_file_fingerprint",
    "compute_function_fingerprint",
    "detect_file_changes",
    "detect_function_changes",
    "detect_statement_changes",
    "merge_logic_lines_with_cache",
    "build_statement_to_logic_map",
    "load_incremental_state",
    "save_incremental_state",
    "filter_tasks_for_incremental",
    "build_consistency_constraints",
    "detect_dependent_changes",
    "apply_consistency_to_design",
    "update_state_with_new_designs",
]
