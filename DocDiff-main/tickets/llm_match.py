"""LLM 辅助问题单匹配（OpenAI 兼容 Chat Completions HTTP API）。

默认不启用；需配置 api_base + api_key（或环境变量）。
仅使用 stdlib urllib，无额外依赖，便于 Win7/内网部署。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional, Sequence

from tickets.match import MatchResult, _change_fingerprint, _segment_preview
from tickets.tickets import Ticket


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def resolve_llm_config(ctx) -> Dict[str, Any]:
    """从 MatchContext + 环境变量解析 LLM 配置。"""
    api_base = (getattr(ctx, "llm_api_base", None) or "").strip() or _env(
        "DOCDIFF_LLM_API_BASE", _env("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    api_key = (getattr(ctx, "llm_api_key", None) or "").strip() or _env(
        "DOCDIFF_LLM_API_KEY", _env("OPENAI_API_KEY", "")
    )
    model = (getattr(ctx, "llm_model", None) or "").strip() or _env(
        "DOCDIFF_LLM_MODEL", _env("OPENAI_MODEL", "gpt-4o-mini")
    )
    timeout = float(getattr(ctx, "llm_timeout", None) or _env("DOCDIFF_LLM_TIMEOUT", "60") or 60)
    return {
        "api_base": api_base.rstrip("/"),
        "api_key": api_key,
        "model": model,
        "timeout": timeout,
    }


def _truncate(s: str, n: int = 280) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _change_card(idx: int, ch: Mapping[str, Any]) -> dict:
    fp = _change_fingerprint(ch)
    return {
        "change_index": idx,  # 0-based for model; we document this
        "type": ch.get("type"),
        "key": _truncate(str(ch.get("key") or ""), 200),
        "seg": _truncate(str(ch.get("seg") or ""), 80),
        "doc_ids": fp.get("doc_ids") or [],
        "idents": (fp.get("idents") or [])[:12],
        "paths": (fp.get("paths") or [])[:6],
        "preview": _truncate(_segment_preview(ch, side="both"), 320),
    }


def _ticket_card(seq: int, t: Ticket) -> dict:
    return {
        "ticket_seq": seq,
        "ticket_no": t.display_no(),
        "title": _truncate(t.display_title(), 200),
    }


def build_llm_prompt(
    changes: Sequence[Mapping[str, Any]],
    tickets: Mapping[int, Ticket],
) -> str:
    change_cards = [_change_card(i, ch) for i, ch in enumerate(changes)]
    ticket_cards = [_ticket_card(s, tickets[s]) for s in sorted(tickets.keys())]
    payload = {
        "task": "将问题单(ticket)一对一匹配到软件变更(change)。每个 ticket 最多匹配一个 change，每个 change 最多匹配一个 ticket。无法确定则不要硬配。",
        "rules": [
            "优先匹配：文档编号(doc_id，如 D/R_SDD…)、源文件路径、C函数名/符号、章节标题关键字",
            "score 为 0~1 置信度；低于 0.55 请不要输出该配对",
            "reason 用简短中文或英文标签说明依据",
            "只输出 JSON，不要 Markdown 代码围栏",
        ],
        "tickets": ticket_cards,
        "changes": change_cards,
        "output_schema": {
            "matches": [
                {
                    "ticket_seq": "int",
                    "change_index": "int (0-based index into changes)",
                    "score": "float 0..1",
                    "reason": "string",
                }
            ]
        },
    }
    return (
        "你是军工/嵌入式软件配置管理助手，负责把「问题单」关联到「更改单条目」。\n"
        "请根据下列 JSON 数据完成匹配，并严格按 output_schema 返回 JSON 对象。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _chat_completions(
    api_base: str,
    api_key: str,
    model: str,
    user_prompt: str,
    timeout: float = 60.0,
) -> str:
    url = f"{api_base.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": "你只输出合法 JSON 对象，不要附加解释或 Markdown。",
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    # 部分兼容网关支持 json_object
    body["response_format"] = {"type": "json_object"}

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        # 若网关不支持 response_format，去掉重试一次
        if e.code in (400, 404, 422) and "response_format" in body:
            body.pop("response_format", None)
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        else:
            raise RuntimeError(f"LLM HTTP {e.code}: {err_body[:500]}") from e

    parsed = json.loads(raw)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM 无 choices：{raw[:300]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    if isinstance(content, list):
        # 部分多模态返回
        content = "".join(
            (p.get("text") or "") for p in content if isinstance(p, dict)
        )
    return str(content)


def _parse_matches_json(content: str) -> List[dict]:
    text = (content or "").strip()
    if not text:
        return []
    # 去掉 ```json 围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # 尝试截取第一个 {...}
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return []
        obj = json.loads(m.group(0))
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        matches = obj.get("matches") or obj.get("pairs") or obj.get("结果") or []
        if isinstance(matches, list):
            return [x for x in matches if isinstance(x, dict)]
    return []


def llm_match_tickets(
    changes: Sequence[Mapping[str, Any]],
    tickets: Mapping[int, Ticket],
    ctx,
) -> List[MatchResult]:
    """调用 LLM 返回 MatchResult 列表（change_index 相对于传入的 changes 子列表）。"""
    if not changes or not tickets:
        return []

    cfg = resolve_llm_config(ctx)
    if not cfg["api_key"]:
        raise RuntimeError(
            "未配置 LLM API Key。请设置环境变量 DOCDIFF_LLM_API_KEY / OPENAI_API_KEY，"
            "或使用 --llm-api-key。"
        )

    prompt = build_llm_prompt(changes, tickets)
    content = _chat_completions(
        api_base=cfg["api_base"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        user_prompt=prompt,
        timeout=cfg["timeout"],
    )
    rows = _parse_matches_json(content)

    min_score = float(getattr(ctx, "llm_min_score", 0.55) or 0.55)
    n_changes = len(changes)
    valid_ticket_seqs = set(tickets.keys())
    used_c, used_t = set(), set()
    results: List[MatchResult] = []

    # 按 score 降序处理
    scored = []
    for row in rows:
        try:
            t_seq = int(row.get("ticket_seq", row.get("seq", -1)))
            c_idx = int(row.get("change_index", row.get("change", -1)))
            score = float(row.get("score", row.get("confidence", 0.7)))
        except (TypeError, ValueError):
            continue
        reason = str(row.get("reason") or row.get("依据") or "llm").strip() or "llm"
        scored.append((score, c_idx, t_seq, reason))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))

    for score, c_idx, t_seq, reason in scored:
        if t_seq not in valid_ticket_seqs:
            continue
        if c_idx < 0 or c_idx >= n_changes:
            continue
        if c_idx in used_c or t_seq in used_t:
            continue
        if score < min_score:
            continue
        used_c.add(c_idx)
        used_t.add(t_seq)
        if not reason.startswith("llm"):
            reason = f"llm:{reason}"
        results.append(
            MatchResult(
                change_index=c_idx,
                ticket_seq=t_seq,
                score=min(1.0, max(0.0, score)),
                reason=reason[:120],
            )
        )
    return results
