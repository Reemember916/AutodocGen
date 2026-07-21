"""Human review decisions and revision-profile conversion."""

from __future__ import annotations

import json
import os
from typing import Any

from .review_workspace import (
    ReviewBundle,
    review_bundle_fingerprint,
    review_bundle_from_dict,
    review_function_key,
)


SCHEMA_VERSION = 1
_VALID_STATUSES = {"pending", "approved", "needs_revision", "rejected"}


def _safe_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _logic_text(value: Any) -> str:
    return str(value if value is not None else "").expandtabs(4).rstrip()


def bundle_fingerprint(bundle: ReviewBundle) -> str:
    return review_bundle_fingerprint(bundle)


def load_review_bundle(path: str) -> ReviewBundle:
    with open(os.path.abspath(os.path.expanduser(path)), encoding="utf-8") as f:
        return review_bundle_from_dict(json.load(f))


def load_review_decisions(path: str) -> dict[str, Any]:
    with open(os.path.abspath(os.path.expanduser(path)), encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("review decisions must be a JSON object")
    version = int(data.get("schema_version") or 0)
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported review decisions schema_version: {version}")
    decision_kind = _safe_text(data.get("decision_kind"))
    if decision_kind and decision_kind != "generation_review":
        raise ValueError(f"unsupported review decision_kind: {decision_kind}")
    functions = data.get("functions")
    if not isinstance(functions, dict):
        raise ValueError("review decisions must contain a functions object")
    return data


def resolve_review_bundle_path(
    decisions_path: str,
    *,
    explicit_bundle: str = "",
    output_docx: str = "",
    review_dir: str = "",
) -> str:
    candidates: list[str] = []
    if explicit_bundle:
        candidates.append(explicit_bundle)
    decisions_abs = os.path.abspath(os.path.expanduser(decisions_path))
    candidates.append(os.path.join(os.path.dirname(decisions_abs), "review_bundle.json"))
    if review_dir:
        candidates.append(os.path.join(os.path.abspath(os.path.expanduser(review_dir)), "review_bundle.json"))
    if output_docx:
        base = os.path.splitext(os.path.abspath(os.path.expanduser(output_docx)))[0]
        candidates.append(os.path.join(base + "_review", "review_bundle.json"))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise FileNotFoundError(
        "未找到 review_bundle.json；请将 generation_review_decisions.json 放到审查目录，"
        "或显式指定 review bundle 路径"
    )


def _decision_functions(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(key): dict(value)
        for key, value in (data.get("functions") or {}).items()
        if isinstance(value, dict)
    }


def review_decisions_to_revision_profile(
    bundle: ReviewBundle,
    decisions: dict[str, Any],
    *,
    allow_stale: bool = False,
) -> dict[str, Any]:
    decision_functions = _decision_functions(decisions)
    bundle_functions = {review_function_key(bundle, fn): fn for fn in bundle.functions or ()}
    expected_fingerprint = _safe_text(decisions.get("bundle_fingerprint"))
    actual_fingerprint = bundle_fingerprint(bundle)
    if expected_fingerprint and expected_fingerprint != actual_fingerprint and not allow_stale:
        raise ValueError("审查决策与 review bundle 不匹配，拒绝应用过期决策")

    patches: dict[str, dict[str, Any]] = {}
    stale: list[str] = []
    unknown: list[str] = []
    status_counts = {status: 0 for status in sorted(_VALID_STATUSES)}

    for key, decision in decision_functions.items():
        status = _safe_text(decision.get("status") or "pending")
        if status not in _VALID_STATUSES:
            raise ValueError(f"invalid review status for {key}: {status}")
        status_counts[status] += 1
        fn = bundle_functions.get(key)
        if fn is None:
            unknown.append(key)
            continue
        decision_hash = _safe_text(decision.get("source_hash"))
        if decision_hash and decision_hash != _safe_text(fn.source_hash):
            stale.append(key)
            if not allow_stale:
                continue
        if status != "approved":
            continue

        source_file = _safe_text(decision.get("source_file") or fn.source_file)
        func_name = _safe_text(decision.get("function") or fn.name or fn.function_id)
        patch: dict[str, Any] = {
            "function": func_name,
            "file": source_file,
        }
        for source_key, target_key in (
            ("title", "function_name"),
            ("description", "description"),
            ("return_desc", "return_desc"),
        ):
            if source_key in decision:
                value = _safe_text(decision.get(source_key))
                if value:
                    patch[target_key] = value

        locked: dict[str, dict[str, str]] = {}
        for element in decision.get("io_elements") or ():
            if not isinstance(element, dict):
                continue
            ident = _safe_text(element.get("ident"))
            display = _safe_text(element.get("name"))
            if ident and display:
                locked[ident] = {"display": display}
        for element in decision.get("local_elements") or ():
            if not isinstance(element, dict):
                continue
            ident = _safe_text(element.get("ident"))
            display = _safe_text(element.get("name"))
            usage = _safe_text(element.get("usage"))
            if ident and display:
                locked[ident] = {"display": display}
                if usage:
                    locked[ident]["usage"] = usage
        if locked:
            patch["locked_names"] = locked

        if "logic_lines" in decision:
            patch["logic_lines"] = [
                _logic_text(line)
                for line in (decision.get("logic_lines") or ())
                if _logic_text(line).strip()
            ]
        patches[key] = patch

    if unknown and not allow_stale:
        raise ValueError("审查决策包含未知函数: " + ", ".join(unknown[:5]))
    if stale and not allow_stale:
        raise ValueError("源码已变化，以下审查决策已过期: " + ", ".join(stale[:5]))

    return {
        "schema_version": 1,
        "source_review": {
            "bundle_fingerprint": actual_fingerprint,
            "status_counts": status_counts,
            "stale_functions": stale,
            "unknown_functions": unknown,
        },
        "functions": patches,
    }


def write_revision_profile_from_review(
    *,
    bundle_path: str,
    decisions_path: str,
    output_path: str,
    allow_stale: bool = False,
) -> dict[str, Any]:
    bundle = load_review_bundle(bundle_path)
    decisions = load_review_decisions(decisions_path)
    profile = review_decisions_to_revision_profile(bundle, decisions, allow_stale=allow_stale)
    target = os.path.abspath(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return profile


__all__ = [
    "SCHEMA_VERSION",
    "bundle_fingerprint",
    "load_review_bundle",
    "load_review_decisions",
    "resolve_review_bundle_path",
    "review_decisions_to_revision_profile",
    "review_function_key",
    "write_revision_profile_from_review",
]
