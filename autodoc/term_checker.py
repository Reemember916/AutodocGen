"""Terminology consistency checker for generated documentation."""

from __future__ import annotations

import copy
import dataclasses
import datetime
import json
import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclasses.dataclass
class TermInconsistency:
    """Single inconsistency record."""

    symbol: str  # 原始标识符
    variants: list[str]  # 不同翻译
    locations: list[dict]  # 出现位置 [{file, func, context}]
    severity: str  # "high" | "medium" | "low"
    suggestion: str  # 建议使用的术语


@dataclasses.dataclass
class ConsistencyReport:
    """Full consistency check report."""

    total_symbols: int
    consistent_symbols: int
    inconsistencies: list[TermInconsistency]
    symbol_dict_conflicts: list[dict]
    score: float  # 0-100

    def summary(self) -> str:
        lines = [
            f"术语一致性报告",
            f"=" * 40,
            f"总符号数: {self.total_symbols}",
            f"一致符号: {self.consistent_symbols}",
            f"不一致项: {len(self.inconsistencies)}",
            f"符号字典冲突: {len(self.symbol_dict_conflicts)}",
            f"一致性评分: {self.score:.1f}/100",
        ]
        if self.inconsistencies:
            lines.append("\n不一致详情:")
            for inc in self.inconsistencies[:10]:
                lines.append(f"  [{inc.severity}] {inc.symbol}: {inc.variants}")
                lines.append(f"    建议: {inc.suggestion}")
        return "\n".join(lines)


def collect_term_mappings(
    designs: list[dict],
    *,
    symbol_dict: Optional[dict[str, str]] = None,
) -> dict[str, dict[str, list[dict]]]:
    """
    从生成结果中收集术语映射。

    Args:
        designs: 函数设计列表，每个包含 func_name, title, io_elements, local_elements, logic_lines
        symbol_dict: 已有符号字典

    Returns:
        {symbol: {"translations": [...], "locations": [...]}}
    """
    term_map: dict[str, dict[str, list]] = defaultdict(lambda: {"translations": [], "locations": []})

    for design in designs or []:
        func_name = design.get("func_name") or design.get("title", "")
        file_path = design.get("source_file", "")

        # 收集函数名
        if func_name:
            title = design.get("title", "")
            if title:
                term_map[func_name]["translations"].append(title)
                term_map[func_name]["locations"].append({
                    "file": file_path,
                    "func": func_name,
                    "context": "函数名",
                })

        # 收集参数名
        for elem in design.get("io_elements") or []:
            ident = elem.get("ident") or elem.get("name", "")
            name = elem.get("name", "")
            if ident and name:
                term_map[ident]["translations"].append(name)
                term_map[ident]["locations"].append({
                    "file": file_path,
                    "func": func_name,
                    "context": "参数",
                })

        # 收集局部变量名
        for elem in design.get("local_elements") or []:
            ident = elem.get("ident") or elem.get("name", "")
            name = elem.get("name", "")
            if ident and name:
                term_map[ident]["translations"].append(name)
                term_map[ident]["locations"].append({
                    "file": file_path,
                    "func": func_name,
                    "context": "局部变量",
                })

        # 收集逻辑流程中的术语
        for line in design.get("logic_lines") or []:
            _extract_symbols_from_logic(line, term_map, file_path, func_name)

    return dict(term_map)


def _extract_symbols_from_logic(
    line: str,
    term_map: dict,
    file_path: str,
    func_name: str,
) -> None:
    """从逻辑流程行中提取符号-术语映射。"""
    import re

    # 匹配 "标识符 -> 中文名" 或 "标识符: 中文名" 模式
    patterns = [
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*[→:]\s*([^→,\n]+)",
        r"将\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*写入",
        r"更新\s*([a-zA-Z_][a-zA-Z0-9_]*)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, line or ""):
            symbol = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            if rest:
                term_map[symbol]["translations"].append(rest.strip())
                term_map[symbol]["locations"].append({
                    "file": file_path,
                    "func": func_name,
                    "context": "逻辑流程",
                })


def check_consistency(
    term_map: dict[str, dict],
    *,
    symbol_dict: Optional[dict[str, str]] = None,
    ignore_variants: Optional[set[str]] = None,
) -> ConsistencyReport:
    """
    检查术语一致性。

    Args:
        term_map: collect_term_mappings 的输出
        symbol_dict: 已有符号字典
        ignore_variants: 忽略的变体（如"初始化"/"初始化处理"视为相同）

    Returns:
        ConsistencyReport
    """
    ignore_variants = ignore_variants or set()
    inconsistencies: list[TermInconsistency] = []
    symbol_dict_conflicts: list[dict] = []
    consistent_count = 0

    for symbol, data in term_map.items():
        translations = list(set(data["translations"]))
        locations = data["locations"]

        if len(translations) <= 1:
            consistent_count += 1
            continue

        # 检查是否只是忽略变体的差异
        normalized = set()
        for t in translations:
            norm = t.strip()
            for ignore in ignore_variants:
                norm = norm.replace(ignore, "")
            normalized.add(norm.strip())

        if len(normalized) <= 1:
            consistent_count += 1
            continue

        # 发现不一致
        severity = _classify_severity(symbol, translations)
        suggestion = _pick_best_translation(translations, symbol_dict, symbol)

        inconsistencies.append(TermInconsistency(
            symbol=symbol,
            variants=translations,
            locations=locations[:5],  # 只保留前5个位置
            severity=severity,
            suggestion=suggestion,
        ))

        # 检查与符号字典的冲突
        if symbol_dict and symbol in symbol_dict:
            expected = symbol_dict[symbol]
            if expected not in translations:
                symbol_dict_conflicts.append({
                    "symbol": symbol,
                    "expected": expected,
                    "actual": translations,
                })

    total = len(term_map)
    score = (consistent_count / total * 100) if total > 0 else 100.0

    return ConsistencyReport(
        total_symbols=total,
        consistent_symbols=consistent_count,
        inconsistencies=sorted(inconsistencies, key=lambda x: x.severity == "high", reverse=True),
        symbol_dict_conflicts=symbol_dict_conflicts,
        score=score,
    )


def _classify_severity(symbol: str, variants: list[str]) -> str:
    """分类不一致严重程度。"""
    # 类型后缀变量通常不重要
    if any(symbol.endswith(s) for s in ("_u8", "_u16", "_u32", "_i16", "_i32", "_f")):
        # 检查是否只是细微差异
        if len(variants) == 2:
            v1, v2 = variants[0], variants[1]
            if v1 in v2 or v2 in v1:
                return "low"
        return "medium"

    # 全局变量、函数名不一致严重
    if symbol.startswith("g_") or not symbol.startswith(("l_", "v_", "p_")):
        return "high"

    return "medium"


def _pick_best_translation(
    variants: list[str],
    symbol_dict: Optional[dict],
    symbol: str,
) -> str:
    """选择最佳翻译作为建议。"""
    # 优先使用符号字典
    if symbol_dict and symbol in symbol_dict:
        return symbol_dict[symbol]

    # 选择最长的（通常更具体）
    valid = [v for v in variants if v and not v.startswith("待人工")]
    if valid:
        return max(valid, key=len)

    return variants[0] if variants else ""


def generate_repair_hints(report: ConsistencyReport) -> list[dict]:
    """
    生成修复建议。

    Returns:
        [{"symbol": "...", "current": "...", "suggested": "...", "action": "rename"}]
    """
    hints = []

    for inc in report.inconsistencies:
        for variant in inc.variants:
            if variant != inc.suggestion:
                hints.append({
                    "symbol": inc.symbol,
                    "current": variant,
                    "suggested": inc.suggestion,
                    "action": "rename",
                    "severity": inc.severity,
                })

    for conflict in report.symbol_dict_conflicts:
        for actual in conflict["actual"]:
            hints.append({
                "symbol": conflict["symbol"],
                "current": actual,
                "suggested": conflict["expected"],
                "action": "align_with_dict",
                "severity": "high",
            })

    return hints


def report_to_dict(report: ConsistencyReport) -> dict:
    """Serialize ConsistencyReport for JSON / GUI / CLI."""
    return {
        "total_symbols": int(report.total_symbols),
        "consistent_symbols": int(report.consistent_symbols),
        "score": float(report.score),
        "inconsistencies": [
            {
                "symbol": inc.symbol,
                "variants": list(inc.variants),
                "locations": list(inc.locations),
                "severity": inc.severity,
                "suggestion": inc.suggestion,
            }
            for inc in (report.inconsistencies or [])
        ],
        "symbol_dict_conflicts": list(report.symbol_dict_conflicts or []),
        "hints": generate_repair_hints(report),
    }


def report_from_dict(data: Any) -> ConsistencyReport:
    """Build ConsistencyReport from dict (or pass-through if already a report)."""
    if isinstance(data, ConsistencyReport):
        return data
    payload = dict(data or {})
    inconsistencies: list[TermInconsistency] = []
    for item in payload.get("inconsistencies") or []:
        if not isinstance(item, dict):
            continue
        inconsistencies.append(
            TermInconsistency(
                symbol=str(item.get("symbol") or "").strip(),
                variants=list(item.get("variants") or []),
                locations=list(item.get("locations") or []),
                severity=str(item.get("severity") or "medium"),
                suggestion=str(item.get("suggestion") or "").strip(),
            )
        )
    return ConsistencyReport(
        total_symbols=int(payload.get("total_symbols") or 0),
        consistent_symbols=int(payload.get("consistent_symbols") or 0),
        inconsistencies=inconsistencies,
        symbol_dict_conflicts=list(payload.get("symbol_dict_conflicts") or []),
        score=float(payload.get("score") or 0.0),
    )


def build_repair_patch(
    report: Any = None,
    *,
    hints: Optional[list[dict]] = None,
    severities: Optional[Sequence[str]] = None,
) -> dict[str, str]:
    """
    Build symbol -> suggested Chinese name patch.

    Prefers explicit hints; otherwise derives from ConsistencyReport.
    Default severities: high + medium (low excluded).
    """
    allowed = {str(s).strip().lower() for s in (severities or ("high", "medium")) if str(s).strip()}
    if not allowed:
        allowed = {"high", "medium"}

    items: list[dict] = []
    if hints is not None:
        items = [h for h in hints if isinstance(h, dict)]
    elif report is not None:
        rep = report_from_dict(report) if not isinstance(report, ConsistencyReport) else report
        items = generate_repair_hints(rep)
        # Also accept pre-serialized hints in dict reports
        if not items and isinstance(report, dict):
            items = [h for h in (report.get("hints") or []) if isinstance(h, dict)]

    patch: dict[str, str] = {}
    for item in items:
        severity = str(item.get("severity") or "medium").strip().lower() or "medium"
        if severity not in allowed:
            continue
        symbol = str(item.get("symbol") or "").strip()
        suggested = str(item.get("suggested") or "").strip()
        if symbol and suggested:
            # Later high-severity / align_with_dict wins if duplicate
            if symbol not in patch or str(item.get("action") or "") == "align_with_dict":
                patch[symbol] = suggested
    return patch


def _backup_file(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    bak = path + ".bak"
    shutil.copy2(path, bak)
    return bak


def _load_json_object(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_object(path: str, data: dict) -> None:
    parent = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".autodoc_term_repair_", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _merge_flat_into_symbol_dictionary(existing: dict, patch: dict[str, str]) -> dict:
    """Merge flat symbol->cn into existing dict, preserving nested sections when present."""
    out = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    nested_sections = (
        "symbols", "globals", "locals", "members", "functions", "macros", "typedefs", "structs", "enums"
    )
    has_section = any(isinstance(out.get(key), dict) for key in nested_sections)
    if has_section:
        symbols = dict(out.get("symbols") or {}) if isinstance(out.get("symbols"), dict) else {}
        for key, value in patch.items():
            symbols[key] = value
        out["symbols"] = symbols
        # Also update top-level flat keys if already present
        for key, value in patch.items():
            if key in out and not isinstance(out.get(key), dict):
                out[key] = value
        return out
    for key, value in patch.items():
        out[key] = value
    return out


def _merge_flat_into_symbol_memory(existing: dict, patch: dict[str, str]) -> dict:
    out = copy.deepcopy(existing) if isinstance(existing, dict) else {"version": 1}
    out.setdefault("version", 1)
    symbols = dict(out.get("symbols") or {}) if isinstance(out.get("symbols"), dict) else {}
    for key, value in patch.items():
        prev = symbols.get(key) if isinstance(symbols.get(key), dict) else {}
        symbols[key] = {
            "cn": value,
            "source": "term_repair",
            "confidence": float((prev or {}).get("confidence") or 1.0),
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
    out["symbols"] = symbols
    return out


@dataclass
class ApplyResult:
    """Result of applying a term-repair patch."""

    dry_run: bool
    patch: dict[str, str]
    applied_count: int
    dict_path: str = ""
    memory_path: str = ""
    dict_backup: str = ""
    memory_backup: str = ""
    wrote_dict: bool = False
    wrote_memory: bool = False

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "applied_count": self.applied_count,
            "patch": dict(self.patch),
            "dict_path": self.dict_path,
            "memory_path": self.memory_path,
            "dict_backup": self.dict_backup,
            "memory_backup": self.memory_backup,
            "wrote_dict": self.wrote_dict,
            "wrote_memory": self.wrote_memory,
        }


def apply_repair_to_symbol_dict(
    patch: dict[str, str],
    *,
    dict_path: str = "",
    memory_path: str = "",
    dry_run: bool = False,
    backup: bool = True,
) -> ApplyResult:
    """
    Merge patch into symbol_dictionary.json and/or autodoc_symbol_memory.json.

    dry_run=True: compute only, no disk writes.
    backup=True: write path.bak before overwrite.
    """
    clean = {
        str(k).strip(): str(v).strip()
        for k, v in (patch or {}).items()
        if str(k).strip() and str(v).strip()
    }
    result = ApplyResult(
        dry_run=bool(dry_run),
        patch=clean,
        applied_count=len(clean),
        dict_path=str(dict_path or "").strip(),
        memory_path=str(memory_path or "").strip(),
    )
    if not clean:
        return result

    if result.dict_path:
        if not dry_run:
            if backup and os.path.isfile(result.dict_path):
                result.dict_backup = _backup_file(result.dict_path)
            existing = _load_json_object(result.dict_path)
            merged = _merge_flat_into_symbol_dictionary(existing, clean)
            _write_json_object(result.dict_path, merged)
            result.wrote_dict = True
        else:
            result.wrote_dict = False

    if result.memory_path:
        if not dry_run:
            if backup and os.path.isfile(result.memory_path):
                result.memory_backup = _backup_file(result.memory_path)
            existing = _load_json_object(result.memory_path)
            merged = _merge_flat_into_symbol_memory(existing, clean)
            _write_json_object(result.memory_path, merged)
            result.wrote_memory = True
        else:
            result.wrote_memory = False

    return result


def apply_repair_from_report(
    report: Any,
    *,
    dict_path: str = "",
    memory_path: str = "",
    dry_run: bool = False,
    backup: bool = True,
    severities: Optional[Sequence[str]] = None,
    hints: Optional[list[dict]] = None,
) -> ApplyResult:
    """
    Public entry for GUI/CLI: report|hints -> patch -> write symbol dict/memory.

    Example::

        apply_repair_from_report(
            report_dict,
            dict_path="symbol_dictionary.json",
            memory_path="autodoc_symbol_memory.json",
            dry_run=False,
        )
    """
    if hints is None and isinstance(report, dict) and report.get("hints"):
        hints = list(report.get("hints") or [])
    patch = build_repair_patch(report, hints=hints, severities=severities)
    return apply_repair_to_symbol_dict(
        patch,
        dict_path=dict_path,
        memory_path=memory_path,
        dry_run=dry_run,
        backup=backup,
    )


def write_consistency_report(report: Any, output_path: str) -> str:
    """Write full consistency report JSON (for UI repair / CLI)."""
    rep = report_from_dict(report) if not isinstance(report, ConsistencyReport) else report
    payload = report_to_dict(rep)
    path = os.path.abspath(os.path.expanduser(str(output_path or "").strip()))
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


__all__ = [
    "TermInconsistency",
    "ConsistencyReport",
    "ApplyResult",
    "collect_term_mappings",
    "check_consistency",
    "generate_repair_hints",
    "report_to_dict",
    "report_from_dict",
    "build_repair_patch",
    "apply_repair_to_symbol_dict",
    "apply_repair_from_report",
    "write_consistency_report",
]
