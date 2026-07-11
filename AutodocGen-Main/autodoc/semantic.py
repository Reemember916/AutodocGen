"""Semantic provider abstraction and structured-RAG default implementation."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

from ._legacy_support import legacy_backend
from . import utils
from .models import SymbolEvidence, SymbolInference
from .semantic_pack import build_function_semantic_pack


class SemanticProvider(Protocol):
    name: str

    def build_function_pack(self, func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
        ...


def _unique_texts(items: list[str], *, limit: int = 10) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


_GENERIC_CONCEPT_SUFFIXES = (
    "检测",
    "判定",
    "获取",
    "更新",
    "记录",
    "处理",
    "计算",
    "控制",
    "监测",
    "状态",
    "标志",
    "结果",
    "故障",
    "输出",
    "输入",
    "信号",
    "命令",
    "请求",
    "电流",
    "电压",
    "温度",
    "功率",
    "速度",
    "转速",
    "位置",
    "角度",
    "位图",
    "数据",
    "变量",
    "通道",
    "电源",
    "限幅",
    "限流",
    "值",
    "位",
    "有效",
)
_SKIP_PROJECT_TOKENS = {
    "u8",
    "u16",
    "u32",
    "u64",
    "i8",
    "i16",
    "i32",
    "i64",
    "f32",
    "f64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "int8",
    "int16",
    "int32",
    "int64",
    "void",
    "const",
    "static",
    "true",
    "false",
    "null",
    "valid",
    "invalid",
}
_GENERIC_PROJECT_ALIASES = {
    "current",
    "cur",
    "calc",
    "func",
    "data",
    "state",
    "result",
    "update",
    "get",
    "set",
    "read",
    "write",
    "pack",
    "handle",
    "check",
    "test",
    "init",
    "over",
    "under",
    "limt",
    "limit",
    "value",
    "valid",
    "invalid",
    "input",
    "output",
    "duty",
    "break",
    "speed",
    "temp",
    "flag",
    "err",
    "id",
    "follow",
    "receive",
    "record",
    "combine",
    "in",
    "out",
}


def _extract_alias_tokens(text: str) -> list[str]:
    legacy = legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return []
    tokens: list[str] = []
    for token in legacy_backend()._split_ident_tokens(value):
        if _is_useful_project_token(token):
            tokens.append(token)
    for match in re.findall(r"\b[A-Z]{1,6}\d{1,3}\b", value):
        if _is_useful_project_token(match):
            tokens.append(match)
    for match in re.findall(r"\b[A-Z]{2,}(?:_[A-Z0-9]+)*\b", value):
        if _is_useful_project_token(match):
            tokens.append(match)
    compact_matches = re.findall(r"[A-Z]{1,6}\d{1,3}(?![a-z])", value)
    for match in compact_matches:
        if _is_useful_project_token(match):
            tokens.append(match)
    return _unique_texts(tokens, limit=12)


def _is_useful_project_token(token: str) -> bool:
    text = str(token or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower in _SKIP_PROJECT_TOKENS:
        return False
    if re.fullmatch(r"\d+", text):
        return False
    if len(text) <= 1 and not re.search(r"[A-Z]\d|\d[A-Z]", text):
        return False
    return True


def _is_project_alias_token(token: str) -> bool:
    text = str(token or "").strip()
    if not _is_useful_project_token(text):
        return False
    lower = text.lower()
    if lower in _GENERIC_PROJECT_ALIASES:
        return False
    if re.search(r"\d", text):
        return True
    if text.isupper() and len(text) >= 2:
        return True
    if len(text) <= 4:
        return True
    return False


def _normalize_concept_text(text: str) -> str:
    legacy = legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return ""
    value = value.replace("_", "").replace("/", "").replace("\\", "")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"^[\-\.:：,，、;；/()（）]+", "", value)
    value = re.sub(r"[\-\.:：,，、;；/()（）]+$", "", value)
    return value


def _trim_project_concept_phrase(text: str) -> str:
    value = _normalize_concept_text(text)
    if not value:
        return ""
    for suffix in _GENERIC_CONCEPT_SUFFIXES:
        if value.endswith(suffix) and len(value) > len(suffix) + 1:
            value = value[: -len(suffix)]
            break
    value = re.sub(r"(?:输入|输出|读回|综合|相关|功能)$", "", value)
    value = re.sub(r"(?:A|B|C|D)$", "", value) if re.search(r"\d[A-D]$", value) else value
    return _normalize_concept_text(value)


def _extract_leading_concept_phrase(text: str) -> str:
    value = _normalize_concept_text(text)
    if not value:
        return ""
    trimmed = _trim_project_concept_phrase(value)
    if trimmed and len(trimmed) >= 2:
        return trimmed
    match = re.match(r"^([\u4e00-\u9fffA-Za-z0-9\-]{2,12})", value)
    if match:
        return _trim_project_concept_phrase(match.group(1)) or match.group(1)
    return ""


def _common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    prefix = values[0]
    for item in values[1:]:
        limit = min(len(prefix), len(item))
        idx = 0
        while idx < limit and prefix[idx] == item[idx]:
            idx += 1
        prefix = prefix[:idx]
        if not prefix:
            break
    return prefix


def _derive_concept_from_texts(texts: list[str]) -> str:
    normalized = [_normalize_concept_text(text) for text in texts if _normalize_concept_text(text)]
    if not normalized:
        return ""
    prefix = _trim_project_concept_phrase(_common_prefix(normalized))
    if prefix and (len(prefix) >= 3 or bool(re.search(r"\d", prefix))):
        return prefix
    leading = [_extract_leading_concept_phrase(text) for text in normalized]
    leading = [text for text in leading if len(text) >= 2]
    if leading:
        counts = Counter(leading)
        best_count = max(counts.values())
        top_items = [text for text, count in counts.items() if count == best_count]
        top_items.sort(key=lambda item: (-len(item), item))
        best = top_items[0]
        if best_count >= 2 or len(leading) == 1:
            return best
    short_texts = [text for text in normalized if 2 <= len(text) <= 10]
    if short_texts:
        return Counter(short_texts).most_common(1)[0][0]
    return ""


def _project_concept_seeds(base_pack: dict[str, Any]) -> list[str]:
    legacy = legacy_backend()
    seeds: list[str] = []

    def add_from_ident(text: str) -> None:
        for token in _extract_alias_tokens(utils._safe_strip(text)):
            if _is_project_alias_token(token):
                seeds.append(token)

    add_from_ident(utils._safe_strip(base_pack.get("func_name")))
    add_from_ident(utils._safe_strip(base_pack.get("family_prefix")))
    add_from_ident(utils._safe_strip(base_pack.get("action_suffix")))
    for item in base_pack.get("callee_names") or ():
        add_from_ident(str(item))
    for item in base_pack.get("macro_refs") or ():
        add_from_ident(str(item))
    for item in base_pack.get("member_accesses") or ():
        add_from_ident(str(item))
    for item in base_pack.get("symbol_profiles") or ():
        add_from_ident((item or {}).get("name"))
        add_from_ident((item or {}).get("producer_call"))
    return _unique_texts(seeds, limit=24)


def _build_project_concepts(base_pack: dict[str, Any], func_data: Optional[dict[str, Any]], cfg: Optional[Any] = None) -> list[dict[str, Any]]:
    legacy = legacy_backend()
    file_context = (func_data or {}).get("file_context") or {}
    module_key = utils._safe_strip(base_pack.get("module_key"))
    family_prefix = utils._safe_strip(base_pack.get("family_prefix"))
    seed_tokens = _project_concept_seeds(base_pack)
    primary_aliases = set(_extract_alias_tokens(utils._safe_strip(base_pack.get("func_name"))))
    primary_aliases.update(_extract_alias_tokens(family_prefix))
    if not seed_tokens:
        return []

    evidence_map: dict[str, list[dict[str, str]]] = {token: [] for token in seed_tokens}

    def add_evidence(token: str, text: str, *, source: str, alias: str = "") -> None:
        tok = utils._safe_strip(token)
        cn_text = _normalize_concept_text(text)
        if (not tok) or (not cn_text):
            return
        bucket = evidence_map.setdefault(tok, [])
        alias_text = utils._safe_strip(alias)
        item = {"text": cn_text, "source": source, "alias": alias_text}
        if item not in bucket:
            bucket.append(item)

    def feed_ident_map(mapping: dict[str, str], source: str) -> None:
        for ident, cn_text in (mapping or {}).items():
            ident_text = utils._safe_strip(ident)
            cn_value = utils._safe_strip(cn_text)
            if not ident_text or not cn_value:
                continue
            ident_tokens = {token for token in _extract_alias_tokens(ident_text) if _is_project_alias_token(token)}
            for token in seed_tokens:
                if token in ident_tokens:
                    add_evidence(token, cn_value, source=source, alias=ident_text)

    feed_ident_map(dict(file_context.get("member_symbol_map") or {}), "file_member")
    feed_ident_map(dict(file_context.get("symbol_map") or {}), "file_symbol")
    feed_ident_map(dict(file_context.get("func_cn_map") or {}), "file_func")

    for record in legacy._project_title_index_items():
        rec_module = utils._safe_strip(record.get("module_key"))
        rec_family = utils._safe_strip(record.get("family_prefix"))
        if module_key and rec_module == module_key:
            scope_bonus = "module_title"
        elif family_prefix and rec_family == family_prefix:
            scope_bonus = "family_title"
        else:
            scope_bonus = "project_title"
        func_name = utils._safe_strip(record.get("func_name"))
        title_text = utils._safe_strip(record.get("resolved_title") or record.get("comment_func_cn"))
        desc_text = utils._safe_strip(record.get("resolved_desc") or record.get("comment_desc"))
        rec_tokens = {token for token in _extract_alias_tokens(func_name) if _is_project_alias_token(token)}
        for token in seed_tokens:
            if token in rec_tokens:
                if title_text:
                    add_evidence(token, title_text, source=scope_bonus, alias=func_name)
                if desc_text:
                    add_evidence(token, desc_text, source=f"{scope_bonus}_desc", alias=func_name)

    for record in legacy._project_symbol_index_items():
        rec_module = utils._safe_strip(record.get("module_key"))
        rec_family = utils._safe_strip(record.get("family_prefix"))
        if module_key and rec_module == module_key:
            scope_bonus = "module_symbol"
        elif family_prefix and rec_family == family_prefix:
            scope_bonus = "family_symbol"
        else:
            scope_bonus = "project_symbol"
        symbol = utils._safe_strip(record.get("symbol"))
        cn_text = utils._safe_strip(record.get("existing_cn"))
        rec_tokens = {token for token in _extract_alias_tokens(symbol) if _is_project_alias_token(token)}
        for token in seed_tokens:
            if token in rec_tokens and cn_text:
                add_evidence(token, cn_text, source=scope_bonus, alias=symbol)

    concepts: list[dict[str, Any]] = []
    for token, evidences in evidence_map.items():
        scoped_evidences = [item for item in evidences if str((item or {}).get("source") or "").startswith("file_")]
        if not scoped_evidences:
            scoped_evidences = [item for item in evidences if str((item or {}).get("source") or "").startswith("module_")]
        if not scoped_evidences:
            scoped_evidences = [item for item in evidences if str((item or {}).get("source") or "").startswith("family_")]
        if not scoped_evidences:
            scoped_evidences = list(evidences)
        texts = [str((item or {}).get("text") or "") for item in scoped_evidences]
        concept = _derive_concept_from_texts(texts)
        if not concept or len(concept) < 2:
            continue
        alias_digits = "".join(ch for ch in token if ch.isdigit())
        if alias_digits and not all(ch in concept for ch in alias_digits):
            continue
        same_module = sum(1 for item in evidences if str((item or {}).get("source") or "").startswith("module_"))
        same_family = sum(1 for item in evidences if str((item or {}).get("source") or "").startswith("family_"))
        local_hits = sum(1 for item in evidences if str((item or {}).get("source") or "").startswith("file_"))
        confidence = 0.38 + min(0.18, 0.04 * len(evidences)) + min(0.18, 0.06 * same_module) + min(0.10, 0.05 * local_hits)
        if same_family:
            confidence += min(0.10, 0.04 * same_family)
        concept_record = {
            "alias": token,
            "concept": concept,
            "confidence": min(0.98, round(confidence, 3)),
            "evidence_count": len(evidences),
            "is_primary": token in primary_aliases,
            "evidence_samples": [
                f"{utils._safe_strip((item or {}).get('alias'))} -> {utils._safe_strip((item or {}).get('text'))}"
                if utils._safe_strip((item or {}).get("alias"))
                else utils._safe_strip((item or {}).get("text"))
                for item in scoped_evidences[:4]
            ],
        }
        concepts.append(concept_record)

    concepts.sort(
        key=lambda item: (
            -int(bool(item.get("is_primary"))),
            -float(item.get("confidence", 0.0) or 0.0),
            -int(item.get("evidence_count", 0) or 0),
            utils._safe_strip(item.get("alias")),
        )
    )
    return concepts[:8]


def _lookup_title_hint(func_name: str, module_key: str = "", source_file: str = "") -> str:
    legacy = legacy_backend()
    target_func = utils._safe_strip(func_name)
    target_module = utils._safe_strip(module_key)
    target_source = utils._safe_strip(source_file)
    if not target_func:
        return ""
    for record in legacy._project_title_index_items():
        if utils._safe_strip(record.get("func_name")) != target_func:
            continue
        if target_source and utils._safe_strip(record.get("source_file")) == target_source:
            return utils._safe_strip(record.get("resolved_title") or record.get("comment_func_cn"))
        if target_module and utils._safe_strip(record.get("module_key")) == target_module:
            return utils._safe_strip(record.get("resolved_title") or record.get("comment_func_cn"))
    for record in legacy._project_title_index_items():
        if utils._safe_strip(record.get("func_name")) == target_func:
            return utils._safe_strip(record.get("resolved_title") or record.get("comment_func_cn"))
    return ""


def _build_role_summary(func_name: str, comment_desc: str, family_prefix: str = "", action_suffix: str = "") -> str:
    legacy = legacy_backend()
    if legacy._is_noop_comment(comment_desc) or legacy._looks_like_logic_noise_comment(comment_desc):
        comment_desc = ""
    compact = legacy._extract_compact_function_title(comment_desc)
    if compact:
        return legacy._apply_domain_title_hint(compact, func_name)
    short_title = legacy._compose_short_function_title(func_name, comment_desc, "")
    if short_title:
        return short_title
    guess = "".join(
        utils._safe_strip(legacy._guess_cn_from_ident(piece))
        for piece in (family_prefix, action_suffix)
        if utils._safe_strip(piece)
    )
    return guess or utils._safe_strip(func_name)


def _build_callee_summary(record: dict[str, Any]) -> dict[str, Any]:
    legacy = legacy_backend()
    func_name = utils._safe_strip(record.get("func_name"))
    module_key = utils._safe_strip(record.get("module_key"))
    source_file = utils._safe_strip(record.get("source_file"))
    family_prefix = utils._safe_strip(record.get("family_prefix"))
    action_suffix = utils._safe_strip(record.get("action_suffix"))
    comment_desc = utils._safe_strip(record.get("comment_desc"))
    if legacy._is_noop_comment(comment_desc) or legacy._looks_like_logic_noise_comment(comment_desc):
        comment_desc = ""
    title_hint = _lookup_title_hint(func_name, module_key=module_key, source_file=source_file)
    role_summary = _build_role_summary(
        func_name,
        comment_desc,
        family_prefix=family_prefix,
        action_suffix=action_suffix,
    )
    return {
        "func_name": func_name,
        "module_key": module_key,
        "family_prefix": family_prefix,
        "action_suffix": action_suffix,
        "title_hint": title_hint or role_summary,
        "role_summary": role_summary,
        "comment_desc": comment_desc,
        "ret_type": utils._safe_strip(record.get("ret_type")),
        "written_params": [utils._safe_strip(x) for x in (record.get("written_params") or ()) if utils._safe_strip(x)][:4],
        "return_symbols": [utils._safe_strip(x) for x in (record.get("return_symbols") or ()) if utils._safe_strip(x)][:4],
        "conditions": [utils._safe_strip(x) for x in (record.get("condition_signatures") or ()) if utils._safe_strip(x)][:3],
    }


def _lookup_callee_summaries(base_pack: dict[str, Any], cfg: Optional[Any] = None) -> list[dict[str, Any]]:
    legacy = legacy_backend()
    semantic_maps = legacy._project_semantic_record_maps()
    module_key = utils._safe_strip(base_pack.get("module_key"))
    out: list[dict[str, Any]] = []
    for callee in list(base_pack.get("callee_names") or [])[:6]:
        callee_name = utils._safe_strip(callee)
        if not callee_name:
            continue
        record = legacy._lookup_project_semantic_record(
            func_name=callee_name,
            module_key=module_key,
            semantic_maps=semantic_maps,
        )
        if not record:
            record = legacy._lookup_project_semantic_record(
                func_name=callee_name,
                semantic_maps=semantic_maps,
            )
        if record:
            out.append(_build_callee_summary(record))
        else:
            out.append(
                {
                    "func_name": callee_name,
                    "module_key": "",
                    "family_prefix": "",
                    "action_suffix": legacy._identifier_action_suffix(callee_name),
                    "title_hint": utils._safe_strip(legacy._guess_cn_from_ident(callee_name)),
                    "role_summary": utils._safe_strip(legacy._guess_cn_from_ident(callee_name)),
                    "comment_desc": "",
                    "ret_type": "",
                    "written_params": [],
                    "return_symbols": [],
                    "conditions": [],
                }
            )
    return out


def _build_project_terms(base_pack: dict[str, Any], callee_summaries: list[dict[str, Any]]) -> list[str]:
    legacy = legacy_backend()
    terms: list[str] = []
    for piece in (
        legacy._guess_cn_from_ident(utils._safe_strip(base_pack.get("family_prefix"))),
        legacy._guess_cn_from_ident(utils._safe_strip(base_pack.get("action_suffix"))),
        utils._safe_strip(base_pack.get("role_summary")),
    ):
        if piece:
            terms.append(piece)
    for item in (callee_summaries or []):
        for piece in (
            utils._safe_strip((item or {}).get("title_hint")),
            utils._safe_strip((item or {}).get("role_summary")),
            utils._safe_strip((item or {}).get("comment_desc")),
        ):
            if piece and len("".join(piece.split())) <= 16:
                terms.append(piece)
    return _unique_texts(terms, limit=8)


def _attach_producer_semantics(symbol_profiles: list[dict[str, Any]], callee_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {
        str((item or {}).get("func_name") or "").strip(): dict(item or {})
        for item in (callee_summaries or [])
        if str((item or {}).get("func_name") or "").strip()
    }
    out: list[dict[str, Any]] = []
    for item in (symbol_profiles or []):
        payload = dict(item or {})
        producer_call = str(payload.get("producer_call") or "").strip()
        if producer_call and producer_call in by_name:
            payload["producer_semantic"] = dict(by_name[producer_call])
        out.append(payload)
    return out


def _augment_pack(
    base_pack: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    func_data: Optional[dict[str, Any]] = None,
    include_graph: bool = False,
) -> dict[str, Any]:
    legacy = legacy_backend()
    pack = dict(base_pack or {})
    callee_summaries = _lookup_callee_summaries(pack, cfg)
    pack["callee_summaries"] = callee_summaries
    pack["project_terms"] = _build_project_terms(pack, callee_summaries)
    pack["symbol_profiles"] = _attach_producer_semantics(list(pack.get("symbol_profiles") or []), callee_summaries)
    pack["project_concepts"] = _build_project_concepts(pack, func_data, cfg)
    if include_graph:
        pack["call_graph_hints"] = _unique_texts(
            [
                f"{utils._safe_strip((item or {}).get('func_name'))}:{utils._safe_strip((item or {}).get('title_hint') or (item or {}).get('role_summary'))}"
                for item in callee_summaries
            ],
            limit=8,
        )
    return pack


@dataclass
class StructuredSemanticProvider:
    name: str = "structured"

    def build_function_pack(self, func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
        base_pack = build_function_semantic_pack(func_data, cfg)
        return _augment_pack(base_pack, cfg, func_data=func_data, include_graph=False)


@dataclass
class LspProvider(StructuredSemanticProvider):
    name: str = "lsp"

    def build_function_pack(self, func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
        base_pack = build_function_semantic_pack(func_data, cfg)
        return _augment_pack(base_pack, cfg, func_data=func_data, include_graph=False)


@dataclass
class GraphProvider(StructuredSemanticProvider):
    name: str = "graph"

    def build_function_pack(self, func_data: dict[str, Any], cfg: Optional[Any] = None) -> dict[str, Any]:
        base_pack = build_function_semantic_pack(func_data, cfg)
        return _augment_pack(base_pack, cfg, func_data=func_data, include_graph=True)


def get_semantic_provider(cfg: Optional[Any] = None) -> SemanticProvider:
    legacy = legacy_backend()
    provider_name = utils.cfg_get_str(cfg, "semantic_provider", "structured").strip().lower()
    if provider_name == "lsp":
        return LspProvider()
    if provider_name == "graph":
        return GraphProvider()
    return StructuredSemanticProvider()


def _should_refresh_semantic_index(project_root: str, semantic_path: str, cfg: Optional[Any] = None) -> bool:
    return bool(legacy_backend()._should_refresh_semantic_index(project_root, semantic_path, cfg))


def _rebuild_project_semantic_index(project_root: str, cfg: Optional[Any] = None) -> dict[str, Any]:
    return dict(legacy_backend()._rebuild_project_semantic_index(project_root, cfg) or {})


def _sync_runtime_semantic_index(path: str, payload: dict[str, Any]) -> None:
    legacy = legacy_backend()
    with legacy._NAMING_INDEX_LOCK:
        legacy._PROJECT_SEMANTIC_INDEX_PATH = path
        legacy._PROJECT_SEMANTIC_INDEX_DATA = dict(payload or {})


def init_project_semantic_index(project_root: str, cfg: Optional[Any] = None) -> None:
    legacy = legacy_backend()
    semantic_path, semantic_data = load_project_semantic_index(project_root)
    if project_root and _should_refresh_semantic_index(project_root, semantic_path, cfg):
        semantic_data = _normalize_semantic_index_payload(_rebuild_project_semantic_index(project_root, cfg))
        legacy._save_json_sidecar(semantic_path, semantic_data, ".autodoc_semantic_index_")
    _sync_runtime_semantic_index(semantic_path, semantic_data)


def _safe_strip(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _default_project_semantic_index_path(project_root: str) -> str:
    root = os.path.abspath(os.path.expanduser(_safe_strip(project_root))) if project_root else ""
    if not root:
        return os.path.abspath("autodoc_semantic_index.json")
    return os.path.join(root, "autodoc_semantic_index.json")


def _normalize_semantic_symbol_profile(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    out = {
        "name": _safe_strip(record.get("name")),
        "decl_type": _safe_strip(record.get("decl_type")),
        "direction": _safe_strip(record.get("direction")),
        "role": _safe_strip(record.get("role")),
        "producer_call": _safe_strip(record.get("producer_call")),
        "producer_arg_tags": [
            _safe_strip(item) for item in (record.get("producer_arg_tags") or ()) if _safe_strip(item)
        ],
        "consumer_patterns": [
            _safe_strip(item) for item in (record.get("consumer_patterns") or ()) if _safe_strip(item)
        ],
        "sink_patterns": [
            _safe_strip(item) for item in (record.get("sink_patterns") or ()) if _safe_strip(item)
        ],
        "dataflow_roles": [
            _safe_strip(item) for item in (record.get("dataflow_roles") or ()) if _safe_strip(item)
        ],
        "usage_patterns": [
            _safe_strip(item) for item in (record.get("usage_patterns") or ()) if _safe_strip(item)
        ],
        "paired_symbols": [
            _safe_strip(item) for item in (record.get("paired_symbols") or ()) if _safe_strip(item)
        ],
    }
    return {key: value for key, value in out.items() if value not in ("", [], None)}


def _normalize_semantic_index_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    out = {
        "id": _safe_strip(record.get("id")),
        "source_file": _safe_strip(record.get("source_file")),
        "module_key": _safe_strip(record.get("module_key")),
        "func_name": _safe_strip(record.get("func_name")),
        "family_prefix": _safe_strip(record.get("family_prefix")),
        "action_suffix": _safe_strip(record.get("action_suffix")),
        "ret_type": _safe_strip(record.get("ret_type")),
        "comment_desc": _safe_strip(record.get("comment_desc")),
        "callee_names": [
            _safe_strip(item) for item in (record.get("callee_names") or ()) if _safe_strip(item)
        ],
        "macro_refs": [
            _safe_strip(item) for item in (record.get("macro_refs") or ()) if _safe_strip(item)
        ],
        "condition_signatures": [
            _safe_strip(item) for item in (record.get("condition_signatures") or ()) if _safe_strip(item)
        ],
        "member_accesses": [
            _safe_strip(item) for item in (record.get("member_accesses") or ()) if _safe_strip(item)
        ],
        "return_exprs": [
            _safe_strip(item) for item in (record.get("return_exprs") or ()) if _safe_strip(item)
        ],
        "return_symbols": [
            _safe_strip(item) for item in (record.get("return_symbols") or ()) if _safe_strip(item)
        ],
        "written_params": [
            _safe_strip(item) for item in (record.get("written_params") or ()) if _safe_strip(item)
        ],
        "read_params": [
            _safe_strip(item) for item in (record.get("read_params") or ()) if _safe_strip(item)
        ],
        "symbol_profiles": [],
    }
    for item in (record.get("symbol_profiles") or ()):
        profile = _normalize_semantic_symbol_profile(item)
        if profile:
            out["symbol_profiles"].append(profile)
    if not out["id"]:
        return {}
    return out


def _normalize_semantic_index_payload(data: Any) -> dict[str, Any]:
    out = {"version": 1, "items": []}
    if not isinstance(data, dict):
        return out
    items = []
    for item in (data.get("items") or []):
        normalized = _normalize_semantic_index_record(item)
        if normalized:
            items.append(normalized)
    out["items"] = items
    if data.get("updated_at"):
        out["updated_at"] = str(data.get("updated_at"))
    return out


def load_project_semantic_index(project_root: str):
    path = _default_project_semantic_index_path(project_root)
    if not os.path.isfile(path):
        return path, _normalize_semantic_index_payload({})
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return path, _normalize_semantic_index_payload({})
    return path, _normalize_semantic_index_payload(data)


def project_semantic_index_items(*, backend_module=None) -> list[dict[str, Any]]:
    backend = backend_module or legacy_backend()
    with backend._NAMING_INDEX_LOCK:
        data = dict(getattr(backend, "_PROJECT_SEMANTIC_INDEX_DATA", {}) or {})
    return list((_normalize_semantic_index_payload(data) or {}).get("items") or [])


def project_semantic_record_maps(
    *,
    backend_module=None,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_file_func: dict[tuple[str, str], dict[str, Any]] = {}
    by_func: dict[str, list[dict[str, Any]]] = {}
    for record in project_semantic_index_items(backend_module=backend_module):
        record_id = _safe_strip(record.get("id"))
        if record_id:
            by_id[record_id] = record
        source_file = _safe_strip(record.get("source_file"))
        func_name = _safe_strip(record.get("func_name"))
        if source_file and func_name:
            by_file_func[(os.path.abspath(source_file), func_name)] = record
        if func_name:
            by_func.setdefault(func_name, []).append(record)
    return by_id, by_file_func, by_func


def lookup_project_semantic_record(
    *,
    record_id: str = "",
    source_file: str = "",
    func_name: str = "",
    module_key: str = "",
    semantic_maps: Optional[tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[str, list[dict[str, Any]]]]] = None,
    backend_module=None,
) -> dict[str, Any]:
    by_id, by_file_func, by_func = semantic_maps or project_semantic_record_maps(backend_module=backend_module)
    record_id = _safe_strip(record_id)
    if record_id and record_id in by_id:
        return dict(by_id[record_id])

    source_file = _safe_strip(source_file)
    func_name = _safe_strip(func_name)
    module_key = _safe_strip(module_key)
    if source_file and func_name:
        hit = by_file_func.get((os.path.abspath(source_file), func_name))
        if hit:
            return dict(hit)

    if func_name:
        candidates = list(by_func.get(func_name) or [])
        if module_key:
            module_hit = next((item for item in candidates if _safe_strip(item.get("module_key")) == module_key), None)
            if module_hit:
                return dict(module_hit)
        if len(candidates) == 1:
            return dict(candidates[0])
    return {}


def lightweight_semantic_record_from_body(
    *,
    func_name: str = "",
    source_file: str = "",
    module_key: str = "",
    family_prefix: str = "",
    ret_type: str = "",
    comment_desc: str = "",
    body: str = "",
    cfg: Optional[Any] = None,
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    return _normalize_semantic_index_record(
        backend._lightweight_semantic_record_from_body(
            func_name=func_name,
            source_file=source_file,
            module_key=module_key,
            family_prefix=family_prefix,
            ret_type=ret_type,
            comment_desc=comment_desc,
            body=body,
            cfg=cfg,
        )
    )


def resolve_current_function_semantic_record(
    func_data: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    record = _normalize_semantic_index_record((func_data or {}).get("semantic_record"))
    if record:
        return record

    func_info = (func_data or {}).get("func_info") or {}
    file_context = (func_data or {}).get("file_context") or {}
    func_name = _safe_strip(func_info.get("func_name"))
    source_file = _safe_strip(file_context.get("source_file"))
    module_key = _safe_strip(file_context.get("module_key"))
    semantic_maps = project_semantic_record_maps(backend_module=backend)
    body = utils._safe_text((func_data or {}).get("body"))
    if body and func_name:
        built = {}
        if source_file:
            project_root = _safe_strip(getattr(cfg, "project_root", "") if cfg is not None else "")
            rel_root = project_root or os.path.dirname(source_file)
            built = backend._build_function_semantic_record(
                rel_root,
                source_file,
                {
                    "comment_info": dict((func_data or {}).get("comment_info") or {}),
                    "func_info": dict(func_info or {}),
                    "body": body,
                    "file_context": dict(file_context or {}),
                },
                cfg,
            ) or {}
        if built:
            return _normalize_semantic_index_record(built)
        return lightweight_semantic_record_from_body(
            func_name=func_name,
            source_file=source_file,
            module_key=module_key,
            family_prefix=_safe_strip(file_context.get("family_prefix")),
            ret_type=_safe_strip(func_info.get("ret_type")),
            comment_desc=_safe_strip(((func_data or {}).get("comment_info") or {}).get("desc")),
            body=body,
            cfg=cfg,
            backend_module=backend,
        )

    return lookup_project_semantic_record(
        source_file=source_file,
        func_name=func_name,
        module_key=module_key,
        semantic_maps=semantic_maps,
        backend_module=backend,
    )


def resolve_symbol_owner_semantic_record(
    symbol_record: dict[str, Any],
    cfg: Optional[Any] = None,
    *,
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    owner_semantic = _normalize_semantic_index_record((symbol_record or {}).get("owner_semantic"))
    if owner_semantic:
        return owner_semantic

    source_file = _safe_strip((symbol_record or {}).get("source_file"))
    owner_func = _safe_strip((symbol_record or {}).get("owner_func"))
    module_key = _safe_strip((symbol_record or {}).get("module_key"))
    body = utils._safe_text((symbol_record or {}).get("body"))
    if body:
        return lightweight_semantic_record_from_body(
            func_name=owner_func,
            source_file=source_file,
            module_key=module_key,
            family_prefix=_safe_strip((symbol_record or {}).get("family_prefix")),
            ret_type=_safe_strip((symbol_record or {}).get("owner_ret_type")),
            comment_desc=_safe_strip((symbol_record or {}).get("comment_desc")),
            body=body,
            cfg=cfg,
            backend_module=backend,
        )
    return lookup_project_semantic_record(
        source_file=source_file,
        func_name=owner_func,
        module_key=module_key,
        backend_module=backend,
    )


def resolve_current_symbol_semantic_profile(symbol_record: dict[str, Any]) -> dict[str, Any]:
    profile = _normalize_semantic_symbol_profile((symbol_record or {}).get("symbol_profile"))
    if profile:
        return profile
    return _normalize_semantic_symbol_profile(
        {
            "name": _safe_strip((symbol_record or {}).get("symbol")),
            "scope": _safe_strip((symbol_record or {}).get("scope")),
            "decl_type": _safe_strip((symbol_record or {}).get("decl_type")),
            "role": _safe_strip((symbol_record or {}).get("role")),
            "direction": _safe_strip((symbol_record or {}).get("direction")),
            "producer_call": _safe_strip((symbol_record or {}).get("producer_call")),
            "producer_arg_tags": tuple((symbol_record or {}).get("producer_arg_tags") or ()),
            "consumer_patterns": tuple((symbol_record or {}).get("consumer_patterns") or ()),
            "usage_patterns": tuple((symbol_record or {}).get("usage_patterns") or ()),
            "paired_symbols": tuple((symbol_record or {}).get("paired_symbols") or ()),
        }
    )


def build_project_glossary(
    file_symbols: Optional[dict[str, str]] = None,
    *,
    backend_module=None,
) -> dict[str, str]:
    backend = backend_module or legacy_backend()
    result = dict(getattr(backend, "DOMAIN_GLOSSARY", {}) or {})
    result.update(getattr(backend, "SYMBOL_DICTIONARY_RUNTIME", {}) or {})
    if file_symbols:
        result.update(file_symbols)
    return result


def candidate_concepts_from_evidence(evidence, *, backend_module=None) -> tuple[str, ...]:
    backend = backend_module or legacy_backend()
    concepts: list[str] = []
    family_cn = backend._bit_family_cn_from_text(evidence.producer_call) or backend._bit_family_cn_from_text(" ".join(evidence.producer_args))
    sym_lower = utils._safe_strip(evidence.symbol).lower()
    dataflow_roles = set(evidence.dataflow_roles or ())
    if "state_snapshot" in dataflow_roles or ("previous_snapshot" in dataflow_roles and "state_value" in dataflow_roles):
        concepts.append("状态快照")
        concepts.append("上拍状态")
    if "output_limit" in dataflow_roles:
        if any(tag in sym_lower for tag in ("brk", "break")):
            concepts.append("制动限幅值")
            concepts.append("制动限流值")
        if any(tag in sym_lower for tag in ("limit", "limt", "lmt")):
            concepts.append("限幅值")
            concepts.append("限制值")
    if "clamp_result" in dataflow_roles and "限幅值" not in concepts:
        concepts.append("限幅值")
    if "state_output" in dataflow_roles:
        concepts.append("状态输出值")
    if "results_bit32" in set(evidence.producer_arg_tags or ()):
        if family_cn and any(p in set(evidence.consumer_patterns or ()) for p in ("compared_to_static_prev", "used_in_change_detection")):
            concepts.append(f"{family_cn}结果快照")
        if family_cn:
            concepts.append(f"{family_cn}结果位图")
            concepts.append(f"{family_cn}结果")
    if evidence.producer_call and any(tag in evidence.producer_call.lower() for tag in ("stateget", "statusget")):
        concepts.append("状态值")
    decl_lower = utils._safe_strip(evidence.decl_type).lower()
    if any(tag in sym_lower for tag in ("trycnt", "retry", "try_cnt")):
        concepts.append("尝试次数")
    if "eval" in decl_lower or (evidence.producer_call and "evalget" in evidence.producer_call.lower()):
        guessed = utils._safe_strip(backend._guess_cn_from_ident(evidence.producer_call or evidence.decl_type))
        if guessed:
            guessed = guessed.replace("获取", "").replace("Get", "")
            if guessed and not guessed.endswith("结果"):
                guessed = f"{guessed}结果"
            if guessed:
                concepts.append(guessed)
    if evidence.producer_call == "RedunDataGet":
        tags = set(evidence.producer_arg_tags or ())
        if "riu" in tags:
            concepts.append("RIU链路状态")
        elif "ccdl" in tags:
            concepts.append("CCDL链路状态")
        elif "kzzz" in tags and "left" in tags:
            concepts.append("左吊舱链路状态")
        elif "kzzz" in tags and "right" in tags:
            concepts.append("右吊舱链路状态")
        elif "kzzz" in tags:
            concepts.append("吊舱链路状态")
    if evidence.paired_symbols and sym_lower.startswith(("l_s_", "s_")):
        for paired in (evidence.paired_symbols or ()):
            paired_name = utils._safe_strip(paired)
            paired_lower = paired_name.lower()
            paired_family = backend._bit_family_cn_from_text(paired_name)
            if paired_family:
                concepts.append(f"上拍{paired_family}结果快照")
                concepts.append(f"上拍{paired_family}结果")
            if "riu" in paired_lower:
                concepts.append("上拍RIU链路状态")
            if "ccdl" in paired_lower:
                concepts.append("上拍CCDL链路状态")
            if "kzzz" in paired_lower and "left" in paired_lower:
                concepts.append("上拍左吊舱链路状态")
            if "kzzz" in paired_lower and "right" in paired_lower:
                concepts.append("上拍右吊舱链路状态")
    normalized_hint = utils._safe_strip(evidence.normalized_comment_hint)
    if normalized_hint:
        concepts.append(normalized_hint)
    if "results" in set(evidence.producer_arg_tags or ()) and "结果" not in concepts:
        concepts.append("检测结果")
    if "counter_value" in dataflow_roles:
        guessed = utils._safe_strip(backend._guess_cn_from_ident(evidence.symbol))
        if guessed.endswith("计数"):
            concepts.append(guessed)
        elif guessed.endswith("次数"):
            concepts.append(guessed)
    deduped: list[str] = []
    for concept in concepts:
        text = utils._safe_strip(concept)
        if (not text) or backend._looks_like_bad_canonical_name(text, raw_ident=evidence.symbol) or text in deduped:
            continue
        deduped.append(text)
    return tuple(deduped[:6])


def count_symbol_evidence_kinds(evidence, candidate_cn: str = "", *, backend_module=None) -> int:
    backend = backend_module or legacy_backend()
    count = 0
    if evidence.preferred_cn:
        count += 1
    if evidence.memory_cn:
        count += 1
    if evidence.decl_type:
        count += 1
    if evidence.usage_patterns:
        count += 1
    if evidence.consumer_patterns:
        count += 1
    if evidence.sink_patterns:
        count += 1
    if evidence.dataflow_roles:
        count += 1
    if evidence.neighbor_symbols:
        count += 1
    if evidence.paired_symbols:
        count += 1
    if evidence.source_comment_hints:
        count += 1
    if evidence.producer_call or evidence.producer_args:
        count += 1
    if candidate_cn and candidate_cn not in (evidence.preferred_cn, evidence.memory_cn):
        count += 1
    return count


def _guess_cn_uses_only_allowed_acronyms(text: str, *, backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(text)
    if not value:
        return False
    words = re.findall(r"[A-Za-z]{2,}", value)
    if not words:
        return True
    allowed = {
        "CPU",
        "DSP",
        "FPGA",
        "GPIO",
        "NMI",
        "PIE",
        "RIU",
        "SCI",
        "SPI",
        "CCDL",
        "KZZZ",
        "PBIT",
        "PUBIT",
        "IFBIT",
        "MBIT",
        "FLASH",
        "CRC",
        "CAN",
    }
    for cn in getattr(backend, "_IDENT_CN_MAP", {}).values():
        token = utils._safe_strip(cn)
        if re.fullmatch(r"[A-Z][A-Z0-9]{1,}", token):
            allowed.add(token)
    return all(word == word.upper() and word.upper() in allowed for word in words)


def _symbol_guess_from_ident(symbol: str, guessed: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(guessed)
    if not value:
        return ""
    tokens = [utils._safe_strip(token).lower() for token in backend._split_ident_tokens(symbol)]
    if tokens and tokens[-1] in {"valid", "ok", "pass", "flag", "flg"}:
        if not value.endswith(("标志", "状态")):
            value = f"{value}标志"
    return value


def _accept_symbol_guess_from_ident(symbol: str, guessed: str, *, role: str = "", backend_module=None) -> bool:
    backend = backend_module or legacy_backend()
    value = utils._safe_strip(guessed)
    if not value:
        return False
    if backend._looks_like_bad_canonical_name(value, raw_ident=symbol):
        return False
    if role == "计数器" and value in {"节拍", "时基", "时钟"}:
        return False
    if re.search(r"[A-Za-z]{2,}", value):
        if not _guess_cn_uses_only_allowed_acronyms(value, backend_module=backend):
            return False
        return backend._candidate_ident_semantic_coverage(value, symbol) >= 1
    return True


def _memory_candidate_overridden_by_ident_guess(
    candidate: str,
    symbol: str,
    guessed: str,
    *,
    backend_module=None,
) -> bool:
    backend = backend_module or legacy_backend()
    candidate_text = utils._safe_strip(candidate)
    guessed_text = utils._safe_strip(guessed)
    if not candidate_text or not guessed_text:
        return False
    if candidate_text not in {"状态快照", "上拍状态", "标志位", "数据指针", "缓存值", "状态值", "无效", "有效"}:
        return False
    return (
        backend._candidate_ident_semantic_coverage(candidate_text, symbol) == 0
        and backend._candidate_ident_semantic_coverage(guessed_text, symbol) >= 2
        and _accept_symbol_guess_from_ident(symbol, guessed_text, backend_module=backend)
    )


def infer_symbol_semantics_rule(evidence, *, backend_module=None):
    backend = backend_module or legacy_backend()
    symbol = evidence.symbol
    if not symbol:
        return SymbolInference(symbol="", kind=evidence.kind)
    guessed = _symbol_guess_from_ident(
        symbol,
        backend._guess_cn_from_ident(symbol, glossary=getattr(backend, "DOMAIN_GLOSSARY", {})),
        backend_module=backend,
    )

    preferred_cn = utils._safe_strip(evidence.preferred_cn)
    if preferred_cn and (not backend._looks_like_generic_local_cn_name(preferred_cn)) and (not backend._looks_like_bad_canonical_name(preferred_cn, raw_ident=symbol)):
        return SymbolInference(
            symbol=symbol,
            kind=evidence.kind,
            candidate_cn=preferred_cn,
            role="显式术语",
            confidence=0.99,
            evidence_kinds=max(1, count_symbol_evidence_kinds(evidence, preferred_cn, backend_module=backend)),
            persist_scope="graded",
            reason="preferred_cn",
        )

    memory_cn = utils._safe_strip(evidence.memory_cn)
    if (
        memory_cn
        and (not _memory_candidate_overridden_by_ident_guess(memory_cn, symbol, guessed, backend_module=backend))
        and (not backend._looks_like_generic_local_cn_name(memory_cn))
        and (not backend._looks_like_bad_canonical_name(memory_cn, raw_ident=symbol))
    ):
        return SymbolInference(
            symbol=symbol,
            kind=evidence.kind,
            candidate_cn=memory_cn,
            role="项目记忆",
            confidence=0.95,
            evidence_kinds=max(1, count_symbol_evidence_kinds(evidence, memory_cn, backend_module=backend)),
            persist_scope="graded",
            reason="memory_cn",
        )

    if evidence.kind == "macros":
        role = backend._infer_macro_role(symbol)
    else:
        role = backend._infer_symbol_role(evidence)

    candidate_concepts = list(candidate_concepts_from_evidence(evidence, backend_module=backend))
    if role in {"缓存值", "返回值"} and any(
        utils._safe_strip(text).endswith("快照") or utils._safe_strip(text).startswith("上拍")
        for text in candidate_concepts
    ):
        role = "上一周期值"

    hinted = backend._derive_candidate_cn_from_evidence(evidence)
    if _memory_candidate_overridden_by_ident_guess(hinted, symbol, guessed, backend_module=backend):
        hinted = ""
    candidate_cn = ""
    if evidence.kind == "members" and re.fullmatch(r"mem(\d+)", symbol, flags=re.IGNORECASE):
        num = re.fullmatch(r"mem(\d+)", symbol, flags=re.IGNORECASE).group(1)  # type: ignore[union-attr]
        candidate_cn = f"成员变量{num}"
    elif evidence.kind == "macros":
        if hinted and not backend._looks_like_bad_canonical_name(hinted, raw_ident=symbol):
            candidate_cn = hinted
        else:
            candidate_cn = backend._default_macro_cn_for_role(symbol, role)
    elif hinted and not backend._looks_like_bad_canonical_name(hinted, raw_ident=symbol):
        candidate_cn = hinted
    elif (
        guessed
        and _accept_symbol_guess_from_ident(symbol, guessed, role=role, backend_module=backend)
    ):
        candidate_cn = guessed
    else:
        candidate_cn = backend._default_cn_for_role(role)
    if guessed and role == "计数器":
        if guessed in {"节拍", "计数"} or len(re.sub(r"\s+", "", guessed)) <= 2:
            candidate_cn = backend._default_cn_for_role(role)
        else:
            guessed_counter = guessed.replace("节拍", "计数")
            if guessed_counter and not backend._looks_like_bad_canonical_name(guessed_counter, raw_ident=symbol):
                if candidate_cn in {"", "计数器", guessed}:
                    candidate_cn = guessed_counter

    evidence_kinds = count_symbol_evidence_kinds(evidence, candidate_cn, backend_module=backend)
    confidence = 0.0
    if candidate_cn:
        confidence = 0.62
        if evidence.kind == "macros":
            confidence = 0.72
        if hinted:
            confidence = max(confidence, 0.84)
        if evidence.producer_call:
            confidence = max(confidence, 0.82)
        if evidence.producer_arg_tags:
            confidence = max(confidence, 0.84)
        if evidence.consumer_patterns:
            confidence = max(confidence, 0.84)
        if "returned" in evidence.usage_patterns or any(p.startswith("call_source:") for p in evidence.usage_patterns):
            confidence = max(confidence, 0.84)
        if guessed:
            confidence = max(confidence, 0.75)
        if evidence.owner_type or evidence.neighbor_symbols:
            confidence = max(confidence, 0.78)
        if evidence_kinds >= 3:
            confidence = max(confidence, 0.82)
    persist_scope = "session_only" if evidence.kind == "macros" else backend._strict_symbol_persist_scope(confidence, evidence_kinds)
    return SymbolInference(
        symbol=symbol,
        kind=evidence.kind,
        candidate_cn=candidate_cn,
        role=role,
        confidence=confidence,
        evidence_kinds=evidence_kinds,
        persist_scope=persist_scope,
        reason="rule",
    )


def build_symbol_inference_prompt(evidence, cfg: Optional[Any] = None, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    candidate_concepts = list(candidate_concepts_from_evidence(evidence, backend_module=backend))
    payload = {
        "symbol": evidence.symbol,
        "kind": evidence.kind,
        "decl_type": evidence.decl_type,
        "owner_type": evidence.owner_type,
        "producer_call": evidence.producer_call,
        "producer_args": list(evidence.producer_args),
        "producer_arg_tags": list(evidence.producer_arg_tags),
        "consumer_patterns": list(evidence.consumer_patterns),
        "sink_patterns": list(evidence.sink_patterns),
        "dataflow_roles": list(evidence.dataflow_roles),
        "paired_symbols": list(evidence.paired_symbols),
        "usage_patterns": list(evidence.usage_patterns),
        "neighbor_symbols": list(evidence.neighbor_symbols),
        "normalized_comment_hint": evidence.normalized_comment_hint,
        "preferred_cn": evidence.preferred_cn,
        "memory_cn": evidence.memory_cn,
        "candidate_concepts": candidate_concepts,
    }
    if backend._is_small_model_strict_mode(cfg):
        return f"""只输出JSON。
规则:
1. 先判断 role，再决定 candidate_cn。
2. 证据不足时 candidate_cn 返回空字符串。
3. role 只能从 {"/".join(backend._STRICT_SYMBOL_ROLES)} 里选择。
4. candidate_cn 必须是短中文名，不能含英文，不能写用途句。
5. candidate_concepts 非空时优先从中选择，不要被历史注释误导。
6. 不要复述注释，不要解释。
输入:{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}
输出:{{"candidate_cn":"","role":"","confidence":0.0,"reason":""}}"""
    return f"""你是嵌入式软件术语推断助手。请根据给定证据，为未知 C 符号输出保守的中文名称推断。
只返回 JSON，不要解释。

规则：
- 优先准确，不要硬翻。
- 若证据不足，candidate_cn 返回空字符串。
- role 只能从这些值中选择：返回值、缓存值、指针、索引、计数器、上一周期值、当前值、标志、模式、状态、阈值、中间量、换算系数、偏移、时间阈值、寄存器、位标志、宏定义。
- 不能直接复述用途注释或输出长句。
- candidate_concepts 非空时优先从中选择；若注释与 producer/consumer 语义冲突，优先相信 producer/consumer。

输入证据：
{json.dumps(payload, ensure_ascii=False, indent=2)}

输出格式：
{{
  "candidate_cn": "中文名称",
  "role": "角色",
  "confidence": 0.0,
  "reason": "一句短理由"
}}"""


def usage_text_from_inference(inference, cn_name: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    display = utils._safe_strip(cn_name) or utils._safe_strip(inference.candidate_cn) or utils._safe_strip(inference.symbol)
    role = utils._safe_strip(inference.role)
    if role == "返回值":
        return f"存放{display}"
    if role == "缓存值":
        if display.endswith(("状态", "状态值", "结果", "检测结果")):
            return f"存放{display}"
        return f"缓存{display}"
    if role == "指针":
        return f"指向{display}"
    if role == "索引":
        return "索引变量"
    if role == "计数器":
        return f"记录{display}"
    if role in ("上一周期值", "当前值", "阈值", "状态", "模式", "标志"):
        return f"存放{display}"
    if role == "中间量":
        return f"存放{display}" if display else ""
    return f"存放{display}"


def collect_symbol_evidence(
    symbol: str,
    *,
    kind: str = "symbols",
    body: str = "",
    decl_type: str = "",
    owner_type: str = "",
    neighbor_symbols: Optional[Sequence[str]] = None,
    source_comment_hints: Optional[Sequence[str]] = None,
    backend_module=None,
):
    backend = backend_module or legacy_backend()
    ident = utils._safe_strip(symbol)
    real_kind = backend._symbol_kind_for_name(ident, default=kind)
    usage_patterns = backend._extract_symbol_usage_patterns(body, ident)
    producer_kind, producer_call, producer_args = backend._extract_call_assignment_profile(body, ident)
    producer_arg_tags = backend._producer_arg_tags(producer_call, producer_args)
    consumer_patterns = backend._extract_symbol_consumer_patterns(body, ident)
    sink_patterns = backend._extract_symbol_sink_patterns(body, ident)
    preferred_cn = backend._lookup_symbol_dictionary(ident)
    memory_cn = backend._lookup_session_symbol(ident)
    neighbors = tuple(
        item
        for item in (utils._safe_strip(value) for value in (neighbor_symbols or ()))
        if item and item != ident
    )
    hints = tuple(
        item
        for item in (utils._safe_strip(value) for value in (source_comment_hints or ()))
        if item
    )
    normalized_hint = ""
    for hint in hints:
        normalized_hint = backend._normalize_symbol_hint_text(hint)
        if normalized_hint:
            break
    paired_symbols = backend._extract_paired_symbols(ident, neighbors[:8])
    dataflow_roles = backend._extract_symbol_dataflow_roles(
        ident,
        body=body,
        decl_type=utils._safe_strip(decl_type),
        usage_patterns=usage_patterns,
        consumer_patterns=consumer_patterns,
        sink_patterns=sink_patterns,
        producer_call=producer_call,
        producer_arg_tags=producer_arg_tags,
        paired_symbols=paired_symbols,
    )
    return SymbolEvidence(
        symbol=ident,
        kind=real_kind,
        decl_type=utils._safe_strip(decl_type),
        owner_type=utils._safe_strip(owner_type),
        usage_patterns=usage_patterns,
        consumer_patterns=consumer_patterns,
        sink_patterns=sink_patterns,
        dataflow_roles=dataflow_roles,
        neighbor_symbols=neighbors[:8],
        paired_symbols=paired_symbols,
        source_comment_hints=hints[:6],
        normalized_comment_hint=normalized_hint,
        producer_kind=producer_kind,
        producer_call=producer_call,
        producer_args=producer_args[:4],
        producer_arg_tags=producer_arg_tags[:6],
        preferred_cn=utils._safe_strip(preferred_cn),
        memory_cn=utils._safe_strip(memory_cn),
    )



@dataclass(frozen=True)
class LocalSymbolProfile:
    """Compact, explainable evidence used to name one function-local symbol."""

    ident: str
    scope: str = "local"
    decl_type: str = ""
    current_cn: str = ""
    comment_hint: str = ""
    role: str = ""
    rule_cn: str = ""
    confidence: float = 0.0
    candidate_concepts: tuple[str, ...] = ()
    producer_call: str = ""
    producer_args: tuple[str, ...] = ()
    usage_patterns: tuple[str, ...] = ()
    consumer_patterns: tuple[str, ...] = ()
    sink_patterns: tuple[str, ...] = ()
    dataflow_roles: tuple[str, ...] = ()
    member_sources: tuple[str, ...] = ()
    assignment_sources: tuple[str, ...] = ()
    evidence_summary: tuple[str, ...] = ()
    suggested_cn: str = ""
    suggestion_reason: str = ""


def _trim_expr_for_profile(text: str, *, limit: int = 80) -> str:
    value = utils._safe_strip(text)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _collect_local_assignment_sources(body: str, ident: str, *, limit: int = 5, backend_module=None) -> tuple[str, ...]:
    backend = backend_module or legacy_backend()
    name = utils._safe_strip(ident)
    if (not name) or not body:
        return ()
    joined = backend._join_c_line_continuations(body)
    assign_re = re.compile(rf"\b{re.escape(name)}\b\s*(?<![!<>=])=(?!=)\s*([^;]+);")
    out: list[str] = []
    for match in assign_re.finditer(joined):
        expr = _trim_expr_for_profile(match.group(1))
        if not expr or expr in out:
            continue
        out.append(expr)
        if len(out) >= max(1, limit):
            break
    return tuple(out)


def _source_cn_from_assignment_expr(expr: str, *, backend_module=None) -> str:
    backend = backend_module or legacy_backend()
    text = utils._safe_strip(expr)
    if not text:
        return ""
    if re.fullmatch(r"(?:NULL|nullptr|0(?:\.0)?[uUlLfF]*|[{}(),\s]+|0x[0-9A-Fa-f]+[uUlL]*)", text):
        return ""
    text = re.sub(r"^\([^)]*\)\s*", "", text)
    text = re.sub(r"\s*&\s*0x[0-9A-Fa-f]+[uUlL]*\s*$", "", text).strip()
    text = re.sub(r"^\([^)]*\)\s*\(?\s*([A-Za-z_]\w*)\s*\)?$", r"\1", text)
    match = re.fullmatch(r"\(?\s*([A-Za-z_]\w*)\s*\)?", text)
    if match:
        source_ident = match.group(1)
        cn = backend.resolve_canonical_symbol_name(source_ident, kind="symbols", fallback="", allow_guess=True)
        if cn == source_ident:
            cn = ""
        return utils._safe_strip(cn)
    member_match = re.search(r"(?:\.|->)\s*([A-Za-z_]\w*)\s*$", text)
    if member_match:
        member = member_match.group(1)
        cn = backend.resolve_canonical_symbol_name(member, kind="members", fallback="", allow_guess=True)
        return utils._safe_strip(cn)
    return ""


def _looks_like_bit_pack_profile(assignment_sources: Sequence[str], evidence) -> bool:
    if "member_write" not in set(evidence.sink_patterns or ()):
        return False
    if "bitop" not in set(evidence.usage_patterns or ()):
        return False
    for expr in assignment_sources or ():
        text = utils._safe_strip(expr)
        if re.search(r"(?:<<|>>|\|)", text):
            return True
    return False


def _build_local_evidence_summary(evidence, *, assignment_sources: Sequence[str], member_sources: Sequence[str]) -> tuple[str, ...]:
    lines: list[str] = []
    if evidence.producer_call:
        args = ", ".join(evidence.producer_args or ())
        lines.append(f"由 {evidence.producer_call}({args}) 返回")
    for expr in assignment_sources[:3]:
        if evidence.producer_call and expr.startswith(f"{evidence.producer_call}("):
            continue
        lines.append(f"赋值来源: {expr}")
    for expr in member_sources[:3]:
        lines.append(f"成员快照: {expr}")
    if evidence.consumer_patterns:
        lines.append("消费场景: " + ",".join(evidence.consumer_patterns[:4]))
    if evidence.sink_patterns:
        lines.append("输出场景: " + ",".join(evidence.sink_patterns[:4]))
    if evidence.dataflow_roles:
        lines.append("数据流角色: " + ",".join(evidence.dataflow_roles[:5]))
    if evidence.usage_patterns:
        lines.append("用法: " + ",".join(evidence.usage_patterns[:5]))
    return tuple(lines[:8])


def _pick_profile_suggestion(
    item: dict[str, Any],
    *,
    evidence,
    inference,
    candidate_concepts: Sequence[str],
    current_cn: str,
    assignment_sources: Sequence[str] = (),
    backend_module=None,
) -> tuple[str, str]:
    backend = backend_module or legacy_backend()
    ident = utils._safe_strip((item or {}).get("name")) or utils._safe_strip(evidence.symbol)
    comment_hint = utils._safe_strip((item or {}).get("comment_hint"))
    if (
        current_cn
        and not backend._looks_like_generic_local_cn_name(current_cn)
        and not backend._looks_like_low_quality_symbol_cn(current_cn, raw_ident=ident)
        and not backend._looks_like_bad_canonical_name(current_cn, raw_ident=ident)
    ):
        return current_cn, "当前名称"
    candidates: list[tuple[str, str]] = []
    if comment_hint and not backend._looks_like_bad_canonical_name(comment_hint, raw_ident=ident):
        candidates.append((comment_hint, "声明注释"))
    for concept in candidate_concepts:
        text = utils._safe_strip(concept)
        if text and not backend._looks_like_bad_canonical_name(text, raw_ident=ident):
            candidates.append((text, "数据流候选"))
    for expr in assignment_sources[:3]:
        source_cn = _source_cn_from_assignment_expr(expr, backend_module=backend)
        if source_cn and not backend._looks_like_bad_canonical_name(source_cn, raw_ident=ident):
            if any(tag in ident.lower() for tag in ("temp", "tmp")) and not source_cn.endswith(("值", "数据", "结果", "编码")):
                source_cn = f"{source_cn}值"
            candidates.append((source_cn, "赋值来源"))
    if _looks_like_bit_pack_profile(assignment_sources, evidence):
        candidates.append(("打包数据", "位拼装"))
    rule_cn = utils._safe_strip(getattr(inference, "candidate_cn", ""))
    if rule_cn and not backend._looks_like_bad_canonical_name(rule_cn, raw_ident=ident):
        candidates.append((rule_cn, f"规则角色:{utils._safe_strip(getattr(inference, 'role', ''))}"))
    if current_cn and not backend._looks_like_bad_canonical_name(current_cn, raw_ident=ident):
        candidates.append((current_cn, "当前名称"))
    guessed = backend._guess_cn_from_ident(ident, glossary=getattr(backend, "DOMAIN_GLOSSARY", {}))
    if guessed and not backend._looks_like_bad_canonical_name(guessed, raw_ident=ident):
        candidates.append((guessed, "标识符拆词"))

    deduped: list[tuple[str, str]] = []
    for cn, reason in candidates:
        text = utils._safe_strip(cn)
        if not text or any(text == old for old, _ in deduped):
            continue
        deduped.append((text, reason))

    if not deduped:
        return "", "证据不足"

    def score(entry: tuple[str, str]) -> tuple[int, int, int]:
        text, reason = entry
        value = 0
        if reason == "声明注释":
            value += 30
        if reason == "数据流候选":
            value += 24
        if reason == "赋值来源":
            value += 22
        if reason == "位拼装":
            value += 20
        if reason.startswith("规则角色"):
            value += 18
        if reason == "当前名称":
            value += 10
        if reason == "标识符拆词":
            value += 8
        if backend._looks_like_generic_local_cn_name(text):
            value -= 10
        if text.endswith(("快照", "结果位图", "链路状态", "限幅值", "限流值", "状态输出值")):
            value += 4
        if text in {"临时量", "临时值", "缓存值", "当前值", "中间量", "数据"}:
            value -= 8
        coverage = backend._candidate_ident_semantic_coverage(text, ident)
        return value, min(6, int(coverage or 0)), min(12, len(text))

    best_cn, best_reason = max(deduped, key=score)
    return best_cn, best_reason


def build_local_symbol_profile(
    item: dict[str, Any],
    *,
    body: str,
    neighbor_symbols: Sequence[str] = (),
    scope: str = "local",
    comment_desc: str = "",
    cfg: Optional[Any] = None,
    backend_module=None,
) -> LocalSymbolProfile:
    """Build an explainable profile and conservative Chinese-name suggestion for a local/param."""
    backend = backend_module or legacy_backend()
    ident = utils._safe_strip((item or {}).get("name"))
    if not ident:
        return LocalSymbolProfile(ident="", scope=scope)
    current_cn = utils._safe_strip((item or {}).get("cn_name"))
    comment_hint = utils._safe_strip((item or {}).get("comment_hint"))
    source_hints = [comment_hint, utils._safe_strip((item or {}).get("usage")), comment_desc]
    evidence = collect_symbol_evidence(
        ident,
        kind="symbols",
        body=body,
        decl_type=utils._safe_strip((item or {}).get("type")),
        neighbor_symbols=neighbor_symbols,
        source_comment_hints=source_hints,
        backend_module=backend,
    )
    inference = infer_symbol_semantics_rule(evidence, backend_module=backend)
    concepts = candidate_concepts_from_evidence(evidence, backend_module=backend)
    assignment_sources = _collect_local_assignment_sources(body, ident, backend_module=backend)
    try:
        member_sources = backend._extract_symbol_member_sources(body, ident)
    except Exception:
        member_sources = ()
    suggested_cn, reason = _pick_profile_suggestion(
        item,
        evidence=evidence,
        inference=inference,
        candidate_concepts=concepts,
        current_cn=current_cn,
        assignment_sources=assignment_sources,
        backend_module=backend,
    )
    return LocalSymbolProfile(
        ident=ident,
        scope=scope,
        decl_type=utils._safe_strip((item or {}).get("type")),
        current_cn=current_cn,
        comment_hint=comment_hint,
        role=utils._safe_strip(inference.role),
        rule_cn=utils._safe_strip(inference.candidate_cn),
        confidence=float(getattr(inference, "confidence", 0.0) or 0.0),
        candidate_concepts=tuple(concepts),
        producer_call=utils._safe_strip(evidence.producer_call),
        producer_args=tuple(evidence.producer_args or ()),
        usage_patterns=tuple(evidence.usage_patterns or ()),
        consumer_patterns=tuple(evidence.consumer_patterns or ()),
        sink_patterns=tuple(evidence.sink_patterns or ()),
        dataflow_roles=tuple(evidence.dataflow_roles or ()),
        member_sources=tuple(member_sources or ()),
        assignment_sources=tuple(assignment_sources or ()),
        evidence_summary=_build_local_evidence_summary(
            evidence,
            assignment_sources=assignment_sources,
            member_sources=member_sources,
        ),
        suggested_cn=suggested_cn,
        suggestion_reason=reason,
    )


def build_function_local_symbol_profiles(
    local_vars: Sequence[dict],
    params: Sequence[dict] = (),
    *,
    body: str,
    comment_desc: str = "",
    cfg: Optional[Any] = None,
    backend_module=None,
) -> list[LocalSymbolProfile]:
    backend = backend_module or legacy_backend()
    items: list[tuple[str, dict[str, Any]]] = []
    for param in params or ():
        if utils._safe_strip((param or {}).get("name")):
            items.append(("param", dict(param or {})))
    for local in local_vars or ():
        if utils._safe_strip((local or {}).get("name")):
            items.append(("local", dict(local or {})))
    names = [utils._safe_strip(item.get("name")) for _scope, item in items if utils._safe_strip(item.get("name"))]
    profiles: list[LocalSymbolProfile] = []
    for scope, item in items:
        ident = utils._safe_strip(item.get("name"))
        profiles.append(
            build_local_symbol_profile(
                item,
                body=body,
                neighbor_symbols=[name for name in names if name and name != ident],
                scope=scope,
                comment_desc=comment_desc,
                cfg=cfg,
                backend_module=backend,
            )
        )
    return profiles

def infer_symbol_semantics(
    evidence,
    cfg: Optional[Any] = None,
    *,
    backend_module=None,
):
    backend = backend_module or legacy_backend()
    rule_result = infer_symbol_semantics_rule(evidence, backend_module=backend)
    best = rule_result
    if (not getattr(cfg, "ai_assist", False)) or (not getattr(cfg, "symbol_infer_enabled", True)):
        if best.candidate_cn:
            backend._remember_inferred_symbol(
                evidence.symbol,
                best.candidate_cn,
                kind=evidence.kind,
                confidence=best.confidence,
                evidence_kinds=best.evidence_kinds,
                cfg=cfg,
                source=f"rule_{best.reason}",
            )
        return best

    need_ai = (not best.candidate_cn) or best.confidence < 0.82
    if not need_ai:
        backend._remember_inferred_symbol(
            evidence.symbol,
            best.candidate_cn,
            kind=evidence.kind,
            confidence=best.confidence,
            evidence_kinds=best.evidence_kinds,
            cfg=cfg,
            source=f"rule_{best.reason}",
        )
        return best

    js = backend.call_llm_json(build_symbol_inference_prompt(evidence, cfg, backend_module=backend), cfg)
    if isinstance(js, dict):
        js = backend._coerce_dict_keys(
            js,
            ("candidate_cn", "role", "confidence", "reason"),
            aliases={"cn_name": "candidate_cn", "cn": "candidate_cn"},
            max_dist=utils.cfg_get_int(cfg, "max_dist", 2),
            min_ratio=utils.cfg_get_float(cfg, "min_ratio", 0.8),
        )
        ai_cn = utils._safe_strip(js.get("candidate_cn"))
        ai_role = utils._safe_strip(js.get("role")) or best.role
        if ai_role and ai_role not in backend._STRICT_SYMBOL_ROLES:
            ai_role = best.role
        ai_conf = float(js.get("confidence", 0.0) or 0.0)
        ai_reason = utils._safe_strip(js.get("reason")) or "ai"
        if ai_cn and not backend._is_strict_symbol_candidate_rejected(ai_cn, raw_ident=evidence.symbol):
            ai_evidence_kinds = max(best.evidence_kinds, count_symbol_evidence_kinds(evidence, ai_cn, backend_module=backend))
            ai_scope = backend._strict_symbol_persist_scope(ai_conf, ai_evidence_kinds)
            candidate = SymbolInference(
                symbol=evidence.symbol,
                kind=evidence.kind,
                candidate_cn=ai_cn,
                role=ai_role,
                confidence=ai_conf,
                evidence_kinds=ai_evidence_kinds,
                persist_scope=ai_scope,
                reason=ai_reason,
            )
            if candidate.confidence >= best.confidence:
                best = candidate

    if best.candidate_cn:
        backend._remember_inferred_symbol(
            evidence.symbol,
            best.candidate_cn,
            kind=evidence.kind,
            confidence=best.confidence,
            evidence_kinds=best.evidence_kinds,
            cfg=cfg,
            source=f"infer_{best.reason}",
        )
    return best


def infer_scope_symbol_names(
    local_vars: Sequence[dict],
    params: Sequence[dict],
    *,
    body: str,
    func_info: Optional[dict],
    comment_info: Optional[dict],
    in_map: dict[str, str],
    out_map: dict[str, str],
    cfg: Optional[Any],
    backend_module=None,
) -> dict[str, Any]:
    backend = backend_module or legacy_backend()
    results: dict[str, Any] = {}
    local_names = [utils._safe_strip((item or {}).get("name")) for item in (local_vars or [])]
    param_names = [utils._safe_strip((item or {}).get("name")) for item in (params or [])]

    for item in (local_vars or []):
        name = utils._safe_strip((item or {}).get("name"))
        if not name:
            continue
        existing_cn = backend.resolve_canonical_symbol_name(
            name,
            kind="symbols",
            comment_cn=utils._safe_strip((item or {}).get("cn_name")),
            fallback=name,
            allow_guess=False,
        )
        if existing_cn and existing_cn != name and (not backend._looks_like_bad_canonical_name(existing_cn, raw_ident=name)):
            if not utils._safe_strip((item or {}).get("cn_name")):
                item["cn_name"] = existing_cn
            if not utils._safe_strip((item or {}).get("usage")):
                item["usage"] = usage_text_from_inference(
                    SymbolInference(symbol=name, kind="symbols", candidate_cn=existing_cn, role="既有命名"),
                    existing_cn,
                    backend_module=backend,
                )
            continue

        evidence = collect_symbol_evidence(
            name,
            kind="symbols",
            body=body,
            decl_type=utils._safe_strip((item or {}).get("type")),
            neighbor_symbols=[value for value in (local_names + param_names) if value],
            source_comment_hints=[utils._safe_strip((item or {}).get("comment_hint"))],
            backend_module=backend,
        )
        inference = infer_symbol_semantics(evidence, cfg, backend_module=backend)
        results[name] = inference
        if inference.candidate_cn and inference.persist_scope != "off" and not utils._safe_strip((item or {}).get("cn_name")):
            item["cn_name"] = inference.candidate_cn
        if not utils._safe_strip((item or {}).get("usage")):
            item["usage"] = usage_text_from_inference(inference, utils._safe_strip((item or {}).get("cn_name")), backend_module=backend)

    for item in (params or []):
        name = utils._safe_strip((item or {}).get("name"))
        if (not name) or utils._safe_strip(in_map.get(name) or out_map.get(name)):
            continue
        existing_cn = backend.resolve_canonical_symbol_name(name, kind="symbols", fallback=name, allow_guess=False)
        if existing_cn and existing_cn != name and (not backend._looks_like_bad_canonical_name(existing_cn, raw_ident=name)):
            in_map[name] = existing_cn
            results[name] = SymbolInference(
                symbol=name,
                kind="symbols",
                candidate_cn=existing_cn,
                role="既有命名",
                confidence=0.95,
                evidence_kinds=2,
                persist_scope="graded",
                reason="existing",
            )
            continue
        evidence = collect_symbol_evidence(
            name,
            kind="symbols",
            body=body,
            decl_type=utils._safe_strip((item or {}).get("type")),
            neighbor_symbols=[value for value in (local_names + param_names) if value],
            source_comment_hints=[utils._safe_strip((comment_info or {}).get("desc"))],
            backend_module=backend,
        )
        inference = infer_symbol_semantics(evidence, cfg, backend_module=backend)
        results[name] = inference
        if inference.candidate_cn and inference.persist_scope != "off":
            in_map[name] = inference.candidate_cn

    return results


def __getattr__(name: str) -> Any:
    return getattr(legacy_backend(), name)


__all__ = [
    "GraphProvider",
    "LspProvider",
    "SemanticProvider",
    "StructuredSemanticProvider",
    "build_project_glossary",
    "build_symbol_inference_prompt",
    "build_function_semantic_pack",
    "candidate_concepts_from_evidence",
    "count_symbol_evidence_kinds",
    "LocalSymbolProfile",
    "build_function_local_symbol_profiles",
    "build_local_symbol_profile",
    "collect_symbol_evidence",
    "get_semantic_provider",
    "infer_scope_symbol_names",
    "infer_symbol_semantics",
    "infer_symbol_semantics_rule",
    "init_project_semantic_index",
    "load_project_semantic_index",
    "usage_text_from_inference",
]
