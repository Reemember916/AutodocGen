#!/usr/bin/env python3
"""Convert approved entries in a design_workspace.json to a revision_profile.json.

Usage:
  python3 tools/workspace_to_revision.py <workspace.json> [-o revision.json]

Only functions with review_status == "approved" are included.
The output revision_profile.json is consumed by autodoc/revision.py when
`revision_profile=<path>` is set in autodocgen.ini.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="Path to design_workspace.json")
    parser.add_argument("-o", "--output", default="", help="Output revision_profile.json path")
    parser.add_argument("--include-pending", action="store_true",
                        help="Include pending entries too (default: only approved)")
    args = parser.parse_args()

    workspace_path = os.path.abspath(args.workspace)
    if not os.path.exists(workspace_path):
        print(f"ERROR: workspace file not found: {workspace_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from autodoc.design_workspace import load_workspace, workspace_to_revision_profile

    workspace = load_workspace(workspace_path)
    if args.include_pending:
        # Override: include pending too (with no locked_names unless human edited)
        funcs = workspace.get("functions") or {}
        for key, entry in funcs.items():
            if entry.get("review_status") == "pending":
                entry["review_status"] = "approved"

    profile = workspace_to_revision_profile(workspace)

    # Stats
    funcs = workspace.get("functions") or {}
    total = len(funcs)
    approved = sum(1 for e in funcs.values() if e.get("review_status") == "approved")
    rejected = sum(1 for e in funcs.values() if e.get("review_status") == "rejected")
    pending = total - approved - rejected

    out_path = args.output or (os.path.splitext(workspace_path)[0] + ".revision_profile.json")
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"workspace: {workspace_path}")
    print(f"  total={total} approved={approved} rejected={rejected} pending={pending}")
    print(f"revision_profile: {out_path}")
    print(f"  functions_in_profile={len(profile.get('functions') or {})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
