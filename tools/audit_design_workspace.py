#!/usr/bin/env python3
"""AI-audit a design_workspace.json: feed LSP facts + design entries to an LLM
and capture review_suggestions back into the workspace.

Usage:
  python3 tools/audit_design_workspace.py <workspace.json> [--only pending] [--max N]

For each function with review_status == "pending", this tool:
  1. Reads the function's design entry (title, description, io, locals, logic)
  2. Reads LSP facts (types, member accesses, calls) if present
  3. Asks the configured LLM to flag quality issues (term drift, generic logic,
     bad symbol guesses, term/usage mismatch) and suggest improvements
  4. Writes suggestions back into entry["review_suggestions"]

Use --apply to set review_status == "approved" automatically when no issues
are found (human can flip to "rejected" if suggestions need work).
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import threading
import time
from typing import Any


AUDIT_PROMPT = """你是嵌入式 C 软件详细设计文档的资深审查员。请基于以下输入，严格审查每个函数的设计质量。

【审查目标】
1. **术语一致性**：函数标题/描述/参数/局部变量的中文命名是否一致，是否符合嵌入式领域习惯。
2. **类型精确性**：局部变量的中文用途是否与其 C 类型匹配（如 `unsigned int*` 应说明指针含义）。
3. **成员访问准确性**：结构体成员访问的中文翻译是否合理（owner_type 是否真正匹配该成员所属结构）。
4. **逻辑完整性**：逻辑步骤是否完整（未省略关键中间动作），是否过于泛化（"设置变量"/"处理数据"等）。
5. **参数翻译质量**：参数的中文名是否准确表达了参数意图（输入/输出/输入输出方向）。
6. **回归收口**：未收口为中文的符号名（即 review_status: pending 且仍含英文 ident）需要重新命名。

【输出格式】严格 JSON 数组，每个元素对应一个函数：
```json
[
  {{
    "func_key": "file.c::funcName",
    "status": "approve|needs_revision|reject",
    "issues": [
      {{"code": "term_drift|generic_logic|bad_symbol_guess|type_mismatch|missing_field", "severity": "info|warn|error", "message": "具体问题描述"}}
    ],
    "suggested_changes": {{
      "title": "（可选）建议修改的标题",
      "description": "（可选）建议修改的功能说明",
      "io_elements": {{"ident1": {{"name": "新名称"}}, "ident2": {{"name": "新名称"}}}},
      "local_elements": {{"ident1": {{"name": "新名称", "usage": "新用途"}}}}
    }}
  }}
]
```

【函数设计】
{design_json}

【LSP 事实】
{lsp_facts_json}

只输出 JSON 数组，不要其他说明。
"""


def _build_audit_prompt(entries: list[dict[str, Any]]) -> str:
    """Build a single batched audit prompt for all pending entries."""
    designs = []
    lsp_facts = []
    for entry in entries:
        key = f"{os.path.basename(entry.get('source_file', ''))}::{entry.get('func_name', '')}"
        designs.append({"func_key": key, **{
            k: entry.get(k) for k in
            ("title", "description", "prototype", "io_elements", "local_elements", "logic_lines", "req_id")
        }})
        lsp_facts.append({"func_key": key, "lsp_facts": entry.get("lsp_facts") or {}})
    return AUDIT_PROMPT.format(
        design_json=json.dumps(designs, ensure_ascii=False, indent=2),
        lsp_facts_json=json.dumps(lsp_facts, ensure_ascii=False, indent=2),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="Path to design_workspace.json")
    parser.add_argument("--only", choices=["pending", "all"], default="pending",
                        help="Which entries to audit (default: pending)")
    parser.add_argument("--max", type=int, default=20,
                        help="Max entries per audit batch (default: 20)")
    parser.add_argument("--apply", action="store_true",
                        help="Set review_status=approved when no issues found")
    args = parser.parse_args()

    workspace_path = os.path.abspath(args.workspace)
    if not os.path.exists(workspace_path):
        print(f"ERROR: workspace file not found: {workspace_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from autodoc.design_workspace import load_workspace
    from autodoc import ai as ai_utils
    from autodoc import config as cfgmod
    from autodoc.utils import resolve_api_key

    workspace = load_workspace(workspace_path)
    funcs = workspace.get("functions") or {}
    targets = []
    for key, entry in funcs.items():
        if args.only == "pending" and entry.get("review_status") != "pending":
            continue
        targets.append((key, entry))
    if not targets:
        print(f"no {args.only} entries to audit in {workspace_path}")
        return 0
    print(f"auditing {len(targets)} entries (batch_size={args.max})")

    # Build config
    cp = configparser.ConfigParser()
    ini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "autodocgen.ini")
    cp.read(ini_path)
    sec = cp["ai"] if "ai" in cp.sections() else {}
    extra = json.loads(cp["advanced"]["extra_params_json"]) if "advanced" in cp.sections() else {}
    while isinstance(extra, str):
        extra = json.loads(extra)
    extra_params = {str(k): str(v) for k, v in extra.items()}

    cfg = cfgmod.GenConfig(
        ai_assist=True, ai_mode=1, ai_provider="openai",
        ai_model=sec.get("ai_model", "claude-haiku-4-5-20251001"),
        ai_api_base=sec.get("ai_api_base", ""),
        ai_api_key=resolve_api_key(sec.get("ai_api_key", "")),
        ai_max_tokens=int(sec.get("ai_max_tokens", 16384)),
        ai_temperature=0.1, ai_top_p=0.5,
        ai_workers=int(sec.get("ai_workers", 8)),
        ai_read_timeout=float(sec.get("ai_read_timeout", 30.0)),
        no_proxy=True, ai_logic_format="json", ai_logic_policy="hybrid",
        verbose=False, gui_log=lambda *a, **k: None,
        stop_event=threading.Event(),
        extra_params=extra_params,
    )
    ai_utils._AI_AUTH_CIRCUIT_OPEN_KEYS.clear()
    ai_utils._AI_RESPONSE_CACHE.clear()

    audited = 0
    suggested_total = 0
    issues_total = 0
    t0 = time.time()
    for batch_start in range(0, len(targets), args.max):
        batch = targets[batch_start:batch_start + args.max]
        entries = [e for _, e in batch]
        prompt = _build_audit_prompt(entries)
        print(f"  batch [{batch_start + 1}..{batch_start + len(batch)}] auditing...")
        js = ai_utils.call_llm_json(prompt, cfg, log_title="design_workspace_audit", log_preview=False, log_full_output=False)
        if not isinstance(js, list):
            print(f"    WARN: AI returned non-list response, skipping batch")
            continue
        by_key = {item.get("func_key"): item for item in js if isinstance(item, dict)}
        for key, entry in batch:
            suggestion = by_key.get(key)
            if not suggestion:
                continue
            issues = suggestion.get("issues") or []
            suggested = suggestion.get("suggested_changes") or {}
            entry["review_suggestions"] = list(issues) + ([suggested] if suggested else [])
            suggested_total += 1
            issues_total += len(issues)
            status = suggestion.get("status")
            if args.apply and status == "approve" and not issues:
                entry["review_status"] = "approved"
            audited += 1

    # Write back
    with open(workspace_path, "w", encoding="utf-8") as f:
        json.dump(workspace, f, ensure_ascii=False, indent=2)
    elapsed = time.time() - t0
    print(f"done: audited={audited} suggestions={suggested_total} issues={issues_total} wall={elapsed:.1f}s")
    print(f"workspace updated: {workspace_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
