"""Project file scanning helpers — directory walking, file collection, module ID computation."""

from __future__ import annotations

import glob
import os
from typing import Any, Optional, Sequence


def walk_filtered(root_dir: str, exclude_dirs: Optional[Sequence[str]] = None):
    """
    os.walk wrapper: filters subdirectories by exclude_dirs (case-insensitive).
    Only used for project scanning/indexing — avoids Debug/Release directories.
    """
    excludes = {str(d).strip().lower() for d in (exclude_dirs or []) if str(d).strip()}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if excludes:
            dirnames[:] = [d for d in dirnames if d.lower() not in excludes]
        yield dirpath, dirnames, filenames


def iter_subdirs(root_dir: str, max_depth: int = 6, exclude_dirs: Optional[Sequence[str]] = None) -> list[str]:
    """
    Return root_dir and its subdirectory list (for include search paths).
    max_depth: root_dir is depth 0; e.g. 1 means only root_dir and its direct children.
    """
    if not root_dir or not os.path.isdir(root_dir):
        return []
    max_depth = max(0, int(max_depth))

    root_abs = os.path.abspath(root_dir)
    root_norm = os.path.normpath(root_abs)
    root_sep_count = root_norm.count(os.sep)

    excludes = {str(d).strip().lower() for d in (exclude_dirs or []) if str(d).strip()}

    out: list[str] = []
    for dirpath, dirnames, _ in os.walk(root_abs):
        if excludes:
            dirnames[:] = [d for d in dirnames if d.lower() not in excludes]

        cur_norm = os.path.normpath(os.path.abspath(dirpath))
        depth = cur_norm.count(os.sep) - root_sep_count
        if depth > max_depth:
            dirnames[:] = []
            continue

        out.append(os.path.abspath(dirpath))

        if depth == max_depth:
            dirnames[:] = []

    # deduplicate (preserve order)
    seen: set[str] = set()
    uniq: list[str] = []
    for d in out:
        if d in seen:
            continue
        seen.add(d)
        uniq.append(d)
    return uniq


def find_files_by_patterns(root_dir, patterns):
    result = []
    for p in patterns:
        full = os.path.join(root_dir, p)
        result.extend(glob.glob(full))
    return sorted(result)


__all__ = ["walk_filtered", "iter_subdirs", "find_files_by_patterns"]
