#!/usr/bin/env python3
"""Real-world V1.01 vs V1.02 actuator design-doc comparison."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from canonical.normalize import build_ast
from diff.collect_changes import build_match_report, collect_changes
from render.change_order import changes_to_jsonable, render_change_order


def main() -> None:
    old = "/sessions/beautiful-sleepy-clarke/mnt/DocDiff/作动器控制器控制管理软件设计说明(V1.01).docx"
    new = "/sessions/beautiful-sleepy-clarke/mnt/DocDiff/作动器控制器控制管理软件设计说明(V1.02).docx"
    out_dir = "/sessions/beautiful-sleepy-clarke/mnt/outputs"
    # also copy into user DocDiff folder if writable
    user_out = "/sessions/beautiful-sleepy-clarke/mnt/DocDiff"
    os.makedirs(out_dir, exist_ok=True)

    def log(msg: str) -> None:
        print(msg, flush=True)
        with open(os.path.join(out_dir, "run.log"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    open(os.path.join(out_dir, "run.log"), "w").close()
    t0 = time.time()

    log("构建旧版 AST...")
    t = time.time()
    old_ast = build_ast(old)
    log(f"  old sections={len(old_ast.sections)} t={time.time()-t:.1f}s")

    log("构建新版 AST...")
    t = time.time()
    new_ast = build_ast(new)
    log(f"  new sections={len(new_ast.sections)} t={time.time()-t:.1f}s")

    log("匹配报告...")
    t = time.time()
    report = build_match_report(old_ast, new_ast)
    report["old_path"] = old
    report["new_path"] = new
    match_path = os.path.join(out_dir, "match_V101_V102.json")
    with open(match_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(
        f"  methods={report.get('method_counts')} pairs={report.get('pair_count')} "
        f"unmatched_old={len(report.get('unmatched_old') or [])} "
        f"unmatched_new={len(report.get('unmatched_new') or [])} "
        f"t={time.time()-t:.1f}s"
    )

    log("收集变更...")
    t = time.time()
    changes = collect_changes(old_ast, new_ast)
    type_c = Counter(c.get("type") for c in changes)
    method_c = Counter(c.get("match_method") for c in changes)
    log(f"  changes={len(changes)} type={dict(type_c)} match={dict(method_c)} t={time.time()-t:.1f}s")

    meta = {
        "doc_no": "实测-作动器",
        "version": "V1.01→V1.02",
        "author": "DocDiff实测",
        "date": "2026-07-19",
        "old_path": old,
        "new_path": new,
    }
    json_path = os.path.join(out_dir, "changes_V101_V102.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": meta,
                "change_count": len(changes),
                "type_counts": dict(type_c),
                "match_method_counts": dict(method_c),
                "changes": changes_to_jsonable(changes),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log(f"  JSON written: {json_path}")

    # sample first 15 changes for quick human review
    samples = []
    for ch in changes[:20]:
        samples.append(
            {
                "type": ch.get("type"),
                "key": (ch.get("key") or "")[-80:],
                "seg": ch.get("seg"),
                "match_method": ch.get("match_method"),
                "match_score": ch.get("match_score"),
                "old_preview": (changes_to_jsonable([ch])[0].get("old_preview") or "")[:100],
                "new_preview": (changes_to_jsonable([ch])[0].get("new_preview") or "")[:100],
            }
        )
    with open(os.path.join(out_dir, "sample_changes.json"), "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    log("渲染更改单...")
    t = time.time()
    out_docx = os.path.join(out_dir, "更改单_V1.01_to_V1.02.docx")
    render_change_order(changes, out_docx, metadata=meta)
    log(f"  render t={time.time()-t:.1f}s")

    # copy deliverables next to source docs
    try:
        import shutil

        for name in (
            "更改单_V1.01_to_V1.02.docx",
            "match_V101_V102.json",
            "changes_V101_V102.json",
            "sample_changes.json",
            "run.log",
        ):
            src = os.path.join(out_dir, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(user_out, name))
        log(f"  copied to {user_out}")
    except Exception as exc:
        log(f"  copy skip: {exc}")

    log(f"DONE total={time.time()-t0:.1f}s")
    with open(os.path.join(out_dir, "DONE"), "w") as f:
        f.write("ok\n")


if __name__ == "__main__":
    main()
