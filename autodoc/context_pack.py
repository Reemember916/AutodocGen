"""Task-specific AI context packs built from semantic packs and RAG hits."""

from __future__ import annotations

from typing import Any, Optional

from ._legacy_support import legacy_backend
from . import naming as naming_utils
from . import utils as utils_module
from .semantic import get_semantic_provider


def _fallback_project_concepts(semantic: dict[str, Any]) -> list[dict[str, Any]]:
    backend = legacy_backend()
    concepts = list(semantic.get("project_concepts") or [])
    if concepts:
        return concepts[:6]
    fallback: list[dict[str, Any]] = []
    for text in list(semantic.get("project_terms") or [])[:6]:
        value = utils_module._safe_strip(text)
        if not value:
            continue
        fallback.append({"alias": value, "text": value, "source": "project_terms"})
    return fallback


def _compact_example(record: dict[str, Any]) -> dict[str, Any]:
    backend = legacy_backend()
    return {
        "func_name": utils_module._safe_strip(record.get("func_name")),
        "module_key": utils_module._safe_strip(record.get("module_key")),
        "family_prefix": utils_module._safe_strip(record.get("family_prefix")),
        "action_suffix": utils_module._safe_strip(record.get("action_suffix")),
        "title": utils_module._safe_strip(record.get("resolved_title")),
        "desc": utils_module._safe_strip(record.get("resolved_desc") or record.get("comment_desc")),
    }


def _compact_symbol_example(record: dict[str, Any]) -> dict[str, Any]:
    backend = legacy_backend()
    return {
        "symbol": utils_module._safe_strip(record.get("symbol")),
        "owner_func": utils_module._safe_strip(record.get("owner_func")),
        "module_key": utils_module._safe_strip(record.get("module_key")),
        "role": utils_module._safe_strip(record.get("role")),
        "decl_type": utils_module._safe_strip(record.get("decl_type")),
        "existing_cn": utils_module._safe_strip(record.get("existing_cn")),
        "existing_usage": utils_module._safe_strip(record.get("existing_usage")),
        "producer_call": utils_module._safe_strip(record.get("producer_call")),
        "producer_arg_tags": [str(x) for x in (record.get("producer_arg_tags") or ()) if utils_module._safe_strip(x)],
        "consumer_patterns": [str(x) for x in (record.get("consumer_patterns") or ()) if utils_module._safe_strip(x)],
        "sink_patterns": [str(x) for x in (record.get("sink_patterns") or ()) if utils_module._safe_strip(x)],
        "dataflow_roles": [str(x) for x in (record.get("dataflow_roles") or ()) if utils_module._safe_strip(x)],
    }


def build_title_context_pack(
    func_data: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    semantic_pack: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    backend = legacy_backend()
    semantic = dict(semantic_pack or {})
    if not semantic or not semantic.get("project_concepts"):
        semantic = dict(get_semantic_provider(cfg).build_function_pack(func_data, cfg) or {})
    retrieved = naming_utils.retrieve_function_title_context(func_data, cfg)
    return {
        "function_identity": {
            "func_name": utils_module._safe_strip((func_data.get("func_info") or {}).get("func_name")),
            "module_key": utils_module._safe_strip(semantic.get("module_key")),
            "family_prefix": utils_module._safe_strip(semantic.get("family_prefix")),
            "action_suffix": utils_module._safe_strip(semantic.get("action_suffix")),
        },
        "semantic_summary": {
            "role_summary": utils_module._safe_strip(semantic.get("role_summary")),
            "comment_desc": utils_module._safe_strip(semantic.get("comment_desc")),
            "callee_names": list(semantic.get("callee_names") or [])[:6],
            "callee_summaries": list(semantic.get("callee_summaries") or [])[:4],
            "project_terms": list(semantic.get("project_terms") or [])[:6],
            "project_concepts": list(semantic.get("project_concepts") or [])[:6],
            "state_effects": list(semantic.get("state_effects") or [])[:6],
            "conditions": list(semantic.get("conditions") or [])[:4],
            "control_skeleton": list(semantic.get("control_skeleton") or [])[:6],
        },
        "retrieved_examples": [_compact_example(item) for item in (retrieved or [])[:6]],
    }


def build_symbol_context_pack(
    symbol_record: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    semantic_pack: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    backend = legacy_backend()
    semantic = dict(semantic_pack or {})
    owner_semantic = dict((symbol_record or {}).get("owner_semantic") or {})
    if owner_semantic:
        semantic = dict(owner_semantic) if not semantic else {**owner_semantic, **semantic}
    if not semantic or not semantic.get("project_concepts"):
        semantic_func_data = {
            "comment_info": {
                "desc": utils_module._safe_strip((symbol_record or {}).get("comment_desc")),
            },
            "func_info": {
                "func_name": utils_module._safe_strip((symbol_record or {}).get("owner_func")),
                "ret_type": utils_module._safe_strip((symbol_record or {}).get("owner_ret_type")),
            },
            "file_context": {
                "source_file": utils_module._safe_strip((symbol_record or {}).get("source_file")),
                "module_key": utils_module._safe_strip((symbol_record or {}).get("module_key")),
                "family_prefix": utils_module._safe_strip((symbol_record or {}).get("family_prefix")),
            },
            "body": utils_module._safe_strip((symbol_record or {}).get("body")),
        }
        rebuilt = get_semantic_provider(cfg).build_function_pack(semantic_func_data, cfg) or {}
        semantic = dict(owner_semantic or semantic or {})
        semantic.update({k: v for k, v in dict(rebuilt).items() if v})
    symbol = utils_module._safe_strip((symbol_record or {}).get("symbol") or (symbol_record or {}).get("name"))
    profile = {}
    for item in semantic.get("symbol_profiles") or ():
        if utils_module._safe_strip((item or {}).get("name")) == symbol:
            profile = dict(item or {})
            break
    producer_call = utils_module._safe_strip((symbol_record or {}).get("producer_call") or profile.get("producer_call"))
    producer_semantic_summary = {}
    for item in semantic.get("callee_summaries") or ():
        if utils_module._safe_strip((item or {}).get("func_name")) == producer_call:
            producer_semantic_summary = dict(item or {})
            break
    retrieved = naming_utils.retrieve_symbol_context(symbol_record, cfg)
    related_conditions = []
    for cond in semantic.get("conditions") or ():
        text = utils_module._safe_strip(cond)
        if text and symbol and symbol in text:
            related_conditions.append(text)
    return {
        "symbol_identity": {
            "symbol": symbol,
            "module_key": utils_module._safe_strip((symbol_record or {}).get("module_key") or semantic.get("module_key")),
            "family_prefix": utils_module._safe_strip((symbol_record or {}).get("family_prefix") or semantic.get("family_prefix")),
            "owner_func": utils_module._safe_strip((symbol_record or {}).get("owner_func") or semantic.get("func_name")),
        },
        "symbol_profile": {
            "decl_type": utils_module._safe_strip((symbol_record or {}).get("decl_type") or profile.get("decl_type")),
            "role": utils_module._safe_strip((symbol_record or {}).get("role") or profile.get("role")),
            "direction": utils_module._safe_strip(profile.get("direction")),
            "producer_call": utils_module._safe_strip((symbol_record or {}).get("producer_call") or profile.get("producer_call")),
            "producer_arg_tags": list((symbol_record or {}).get("producer_arg_tags") or profile.get("producer_arg_tags") or ())[:6],
            "consumer_patterns": list((symbol_record or {}).get("consumer_patterns") or profile.get("consumer_patterns") or ())[:6],
            "sink_patterns": list((symbol_record or {}).get("sink_patterns") or profile.get("sink_patterns") or ())[:6],
            "dataflow_roles": list((symbol_record or {}).get("dataflow_roles") or profile.get("dataflow_roles") or ())[:6],
            "usage_patterns": list((symbol_record or {}).get("usage_patterns") or profile.get("usage_patterns") or ())[:6],
            "paired_symbols": list((symbol_record or {}).get("paired_symbols") or profile.get("paired_symbols") or ())[:4],
            "canonical_cn": naming_utils.resolve_canonical_symbol_name(symbol, kind="symbols", fallback="", allow_guess=False),
        },
        "owner_semantic_summary": {
            "role_summary": utils_module._safe_strip(semantic.get("role_summary")),
            "state_effects": list(semantic.get("state_effects") or [])[:6],
            "conditions": related_conditions[:4],
            "callee_names": list(semantic.get("callee_names") or [])[:6],
            "project_terms": list(semantic.get("project_terms") or [])[:6],
            "project_concepts": _fallback_project_concepts(semantic),
        },
        "producer_semantic_summary": producer_semantic_summary,
        "retrieved_examples": [_compact_symbol_example(item) for item in (retrieved or [])[:8]],
    }


__all__ = [name for name in globals() if not name.startswith("__")]
