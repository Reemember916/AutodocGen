"""可插拔问题单匹配策略：rules / llm / hybrid。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence

from tickets.match import (
    DEFAULT_MATCH_MIN_SCORE,
    MatchResult,
    match_tickets_to_changes,
)
from tickets.tickets import Ticket


@dataclass
class MatchContext:
    """匹配运行上下文（策略可读取配置，不强制依赖 CLI）。"""

    min_score: float = DEFAULT_MATCH_MIN_SCORE
    # LLM
    llm_enabled: bool = False
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 60.0
    llm_min_score: float = 0.55  # LLM 结果低于此分丢弃
    llm_only_unmatched: bool = True  # hybrid：仅对规则未挂上的做 LLM
    extra: Dict[str, Any] = field(default_factory=dict)


class MatchStrategy(Protocol):
    name: str

    def match(
        self,
        changes: Sequence[Mapping[str, Any]],
        tickets: Mapping[int, Ticket],
        ctx: MatchContext,
    ) -> List[MatchResult]:
        ...


class RulesMatchStrategy:
    """基于 doc-id / 路径 / 符号 / 关键字 / 相似度的规则匹配。"""

    name = "rules"

    def match(
        self,
        changes: Sequence[Mapping[str, Any]],
        tickets: Mapping[int, Ticket],
        ctx: MatchContext,
    ) -> List[MatchResult]:
        return match_tickets_to_changes(changes, tickets, min_score=ctx.min_score)


class LlmMatchStrategy:
    """调用 OpenAI 兼容 Chat Completions，让模型给出 ticket_seq ↔ change_index 配对。"""

    name = "llm"

    def match(
        self,
        changes: Sequence[Mapping[str, Any]],
        tickets: Mapping[int, Ticket],
        ctx: MatchContext,
    ) -> List[MatchResult]:
        from tickets.llm_match import llm_match_tickets

        return llm_match_tickets(changes, tickets, ctx)


class HybridMatchStrategy:
    """先 rules，再对未匹配子集调用 LLM 补全。"""

    name = "hybrid"

    def __init__(self) -> None:
        self._rules = RulesMatchStrategy()
        self._llm = LlmMatchStrategy()

    def match(
        self,
        changes: Sequence[Mapping[str, Any]],
        tickets: Mapping[int, Ticket],
        ctx: MatchContext,
    ) -> List[MatchResult]:
        rules_hits = self._rules.match(changes, tickets, ctx)
        used_c = {m.change_index for m in rules_hits}
        used_t = {m.ticket_seq for m in rules_hits}

        if not ctx.llm_enabled and not (ctx.llm_api_base or ctx.llm_api_key):
            # 无 LLM 配置时 hybrid ≡ rules
            return rules_hits

        # 剩余 ticket / change
        rest_tickets = {s: tickets[s] for s in tickets if s not in used_t}
        rest_change_indices = [i for i in range(len(changes)) if i not in used_c]
        if not rest_tickets or not rest_change_indices:
            return rules_hits

        # 压缩为子列表，LLM 只看未匹配部分
        sub_changes = [changes[i] for i in rest_change_indices]
        try:
            sub_hits = self._llm.match(sub_changes, rest_tickets, ctx)
        except Exception:
            # LLM 失败不拖垮整条流水线
            return rules_hits

        # 映射回全局 change_index
        extra: List[MatchResult] = []
        for m in sub_hits:
            if m.change_index < 0 or m.change_index >= len(rest_change_indices):
                continue
            global_ci = rest_change_indices[m.change_index]
            if global_ci in used_c or m.ticket_seq in used_t:
                continue
            if m.score < ctx.llm_min_score:
                continue
            used_c.add(global_ci)
            used_t.add(m.ticket_seq)
            reason = m.reason if m.reason.startswith("llm") else f"llm+{m.reason}"
            extra.append(
                MatchResult(
                    change_index=global_ci,
                    ticket_seq=m.ticket_seq,
                    score=m.score,
                    reason=reason,
                )
            )
        return list(rules_hits) + extra


def get_match_strategy(name: str) -> MatchStrategy:
    key = (name or "rules").strip().lower()
    if key in {"rule", "rules", "auto", "default"}:
        return RulesMatchStrategy()
    if key in {"llm", "gpt", "model"}:
        return LlmMatchStrategy()
    if key in {"hybrid", "mix", "rules+llm"}:
        return HybridMatchStrategy()
    raise ValueError(f"未知匹配策略：{name!r}（可选 rules / llm / hybrid）")


def run_match_strategy(
    strategy_name: str,
    changes: Sequence[Mapping[str, Any]],
    tickets: Mapping[int, Ticket],
    ctx: Optional[MatchContext] = None,
) -> List[MatchResult]:
    ctx = ctx or MatchContext()
    strategy = get_match_strategy(strategy_name)
    return strategy.match(changes, tickets, ctx)
