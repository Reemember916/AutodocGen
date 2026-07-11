"""Terminology consistency checker for generated documentation."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Any, Optional


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


__all__ = [
    "TermInconsistency",
    "ConsistencyReport",
    "collect_term_mappings",
    "check_consistency",
    "generate_repair_hints",
]
