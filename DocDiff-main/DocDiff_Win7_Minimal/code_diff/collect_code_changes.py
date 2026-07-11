import difflib
import re
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_CODE_EXTS = {
    ".c",
    ".h",
}

_CONTROL_KWS = {"if", "for", "while", "switch", "else", "do"}


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _iter_files(root: Path, exts) -> Dict[str, Path]:
    files = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        files[rel] = p
    return files


def _truncate_lines(lines: List[str], max_lines: int) -> str:
    if not lines:
        return ""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[:max_lines] + ["... (内容已截断) ..."])


def _build_change(
    change_type: str,
    rel_path: str,
    seg: str,
    old_text: str,
    new_text: str,
):
    return {
        "type": change_type,
        "key": rel_path,
        "seg": seg,
        "old_text": old_text,
        "new_text": new_text,
    }


def _mask_c_text(text: str) -> str:
    chars = list(text)
    n = len(chars)
    i = 0
    while i < n:
        if i + 1 < n and chars[i] == "/" and chars[i + 1] == "/":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i < n and chars[i] != "\n":
                chars[i] = " "
                i += 1
            continue

        if i + 1 < n and chars[i] == "/" and chars[i + 1] == "*":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i + 1 < n and not (chars[i] == "*" and chars[i + 1] == "/"):
                if chars[i] != "\n":
                    chars[i] = " "
                i += 1
            if i + 1 < n:
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
            continue

        if chars[i] in ('"', "'"):
            quote = chars[i]
            chars[i] = " "
            i += 1
            while i < n:
                if chars[i] == "\\":
                    chars[i] = " "
                    if i + 1 < n:
                        if chars[i + 1] != "\n":
                            chars[i + 1] = " "
                        i += 2
                        continue
                    i += 1
                    continue
                if chars[i] == quote:
                    chars[i] = " "
                    i += 1
                    break
                if chars[i] != "\n":
                    chars[i] = " "
                i += 1
            continue

        i += 1

    return "".join(chars)


def _find_matching_brace(masked: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(masked)):
        c = masked[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _extract_func_meta(header: str):
    # 先移除函数头区域中的注释，避免把注释内容拼进函数签名。
    no_comments = re.sub(r"/\*.*?\*/", " ", header, flags=re.S)
    no_comments = re.sub(r"//.*", " ", no_comments)

    filtered = []
    for line in no_comments.splitlines():
        if line.strip().startswith("#"):
            continue
        filtered.append(line)

    collapsed = " ".join("\n".join(filtered).replace("\n", " ").split())
    if not collapsed:
        return None, None

    if re.match(r"^(if|for|while|switch|else|do)\b", collapsed):
        return None, None
    if re.match(r"^(typedef|enum|struct|union)\b", collapsed):
        return None, None

    m = re.search(r"([A-Za-z_]\w*)\s*\([^;{}]*\)\s*$", collapsed)
    if not m:
        return None, None

    name = m.group(1)
    if name in _CONTROL_KWS:
        return None, None

    signature = collapsed
    signature = re.sub(r"\s+", " ", signature).strip()
    signature = re.sub(r"__attribute__\s*\(\(.*\)\)\s*$", "", signature).strip()
    return name, signature


def _extract_c_functions(text: str):
    masked = _mask_c_text(text)
    funcs = []

    i = 0
    depth = 0
    n = len(masked)

    while i < n:
        ch = masked[i]

        if ch == "{":
            if depth == 0:
                boundary = max(masked.rfind(";", 0, i), masked.rfind("}", 0, i))
                start = boundary + 1
                header = text[start:i]
                name, signature = _extract_func_meta(header)
                if name:
                    end = _find_matching_brace(masked, i)
                    if end != -1:
                        fn_start = start
                        refs = list(re.finditer(rf"\b{re.escape(name)}\b\s*\(", header))
                        if refs:
                            last_ref = refs[-1]
                            line_start = header.rfind("\n", 0, last_ref.start()) + 1
                            fn_start = start + line_start

                        body = text[fn_start : end + 1].strip("\n")
                        funcs.append(
                            {
                                "name": name,
                                "signature": signature,
                                "start": fn_start,
                                "end": end + 1,
                                "body": body,
                            }
                        )
                        i = end + 1
                        depth = 0
                        continue
            depth += 1
            i += 1
            continue

        if ch == "}":
            depth = max(0, depth - 1)
            i += 1
            continue

        i += 1

    return funcs


def _index_functions(funcs):
    mapping = {}
    order = []
    counter = {}
    for fn in funcs:
        name = fn["name"]
        idx = counter.get(name, 0) + 1
        counter[name] = idx
        key = name if idx == 1 else f"{name}#{idx}"
        mapping[key] = fn
        order.append(key)
    return mapping, order


def _function_core_text(fn) -> str:
    """
    用于函数对齐的核心文本：
    - 去掉首行函数声明，减少“仅改函数名”导致的错配。
    - 保留函数主体逻辑文本。
    """
    body = (fn.get("body", "") or "").strip("\n")
    lines = body.splitlines()
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0].strip()
    return "\n".join(lines[1:]).strip()


def _align_c_functions(old_funcs: List[dict], new_funcs: List[dict]):
    """
    基于函数主体序列对齐，避免函数改名被判成删除+新增。
    返回按“新文件顺序优先”的动作列表：
    - ("pair", old_fn, new_fn)
    - ("del", old_fn, None)
    - ("add", None, new_fn)
    """
    old_seq = [_function_core_text(fn) for fn in old_funcs]
    new_seq = [_function_core_text(fn) for fn in new_funcs]
    sm = difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False)

    ops = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                ops.append(("pair", old_funcs[i1 + k], new_funcs[j1 + k]))
            continue

        if tag == "replace":
            common = min(i2 - i1, j2 - j1)
            for k in range(common):
                ops.append(("pair", old_funcs[i1 + k], new_funcs[j1 + k]))
            for k in range(common, i2 - i1):
                ops.append(("del", old_funcs[i1 + k], None))
            for k in range(common, j2 - j1):
                ops.append(("add", None, new_funcs[j1 + k]))
            continue

        if tag == "delete":
            for k in range(i1, i2):
                ops.append(("del", old_funcs[k], None))
            continue

        if tag == "insert":
            for k in range(j1, j2):
                ops.append(("add", None, new_funcs[k]))

    return ops


def _extract_changed_ranges(old_lines: List[str], new_lines: List[str]):
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    old_ranges = []
    new_ranges = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in {"replace", "delete"} and i1 < i2:
            old_ranges.append((i1, i2))
        if tag in {"replace", "insert"} and j1 < j2:
            new_ranges.append((j1, j2))

    return old_ranges, new_ranges


def _render_changed_ranges(
    lines: List[str],
    ranges: List[Tuple[int, int]],
    max_contiguous_lines: int = 0,
    gap_marker: str = "... (省略未改动片段) ...",
) -> str:
    if not ranges:
        return ""

    out = []
    for idx, (start, end) in enumerate(ranges):
        chunk = lines[start:end]

        if max_contiguous_lines > 0 and len(chunk) > max_contiguous_lines:
            chunk = chunk[:max_contiguous_lines] + ["... (内容已截断，至更改末尾) ...", chunk[-1]]

        out.extend(chunk)
        if idx < len(ranges) - 1 and gap_marker:
            out.append(gap_marker)

    return "\n".join(out)


def _snippet_from_diff_with_context(old_text: str, new_text: str, max_lines: int):
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    old_changed = []
    new_changed = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "delete"}:
            old_changed.extend(range(i1, i2))
        if tag in {"replace", "insert"}:
            new_changed.extend(range(j1, j2))

        # 插入/删除场景下，为“未变化一侧”补充插入点附近上下文，便于前后对照。
        if tag == "insert" and old_lines:
            old_changed.extend([max(0, i1 - 1), min(len(old_lines) - 1, i1)])
        if tag == "delete" and new_lines:
            new_changed.extend([max(0, j1 - 1), min(len(new_lines) - 1, j1)])

    def pick(lines: List[str], changed: List[int]) -> str:
        if not changed:
            return ""
        start = max(min(changed) - 1, 0)
        end = min(max(changed) + 1, len(lines) - 1)
        return _truncate_lines(lines[start : end + 1], max_lines)

    return pick(old_lines, old_changed), pick(new_lines, new_changed)


def _collect_c_changes(rel_path: str, old_text: str, new_text: str, gap_marker: str) -> List[dict]:
    if old_text == new_text:
        return []

    old_funcs = _extract_c_functions(old_text) if old_text else []
    new_funcs = _extract_c_functions(new_text) if new_text else []

    changes: List[dict] = []

    for action, old_fn, new_fn in _align_c_functions(old_funcs, new_funcs):
        seg = (new_fn or old_fn).get("signature", "未知函数")

        if action == "del":
            changes.append(_build_change("删除", rel_path, seg, old_fn["body"], ""))
            continue

        if action == "add":
            changes.append(_build_change("新增", rel_path, seg, "", ""))
            continue

        if old_fn["body"] != new_fn["body"]:
            old_lines = old_fn["body"].splitlines()
            new_lines = new_fn["body"].splitlines()
            old_ranges, new_ranges = _extract_changed_ranges(old_lines, new_lines)
            old_snippet = _render_changed_ranges(old_lines, old_ranges, max_contiguous_lines=0, gap_marker=gap_marker)
            new_snippet = _render_changed_ranges(new_lines, new_ranges, max_contiguous_lines=0, gap_marker=gap_marker)
            changes.append(_build_change("修改", rel_path, seg, old_snippet, new_snippet))

    if changes:
        return changes

    old_snippet, new_snippet = _snippet_from_diff_with_context(old_text, new_text, 10)
    return [_build_change("修改", rel_path, "全局区域", old_snippet, new_snippet)]


def _collect_h_changes(rel_path: str, old_text: str, new_text: str) -> List[dict]:
    if old_text == new_text:
        return []

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_ranges, new_ranges = _extract_changed_ranges(old_lines, new_lines)

    old_snippet = _render_changed_ranges(old_lines, old_ranges, max_contiguous_lines=10)
    new_snippet = _render_changed_ranges(new_lines, new_ranges, max_contiguous_lines=10)

    change_type = "修改"
    if old_text and not new_text:
        change_type = "删除"
    elif new_text and not old_text:
        change_type = "新增"

    return [_build_change(change_type, rel_path, "头文件", old_snippet, new_snippet)]


def collect_code_changes(
    old_root: str,
    new_root: str,
    include_exts: Tuple[str, ...] = tuple(sorted(DEFAULT_CODE_EXTS)),
    max_preview_lines: int = 10,
    c_gap_marker: str = "... (省略未改动片段) ...",
) -> List[dict]:
    old_base = Path(old_root)
    new_base = Path(new_root)

    if not old_base.exists():
        raise FileNotFoundError(f"旧版本路径不存在: {old_root}")
    if not new_base.exists():
        raise FileNotFoundError(f"新版本路径不存在: {new_root}")

    exts = {x.lower() for x in include_exts} if include_exts else set()

    if old_base.is_file() and new_base.is_file():
        old_text = _read_text(old_base)
        new_text = _read_text(new_base)
        if old_text == new_text:
            return []
        rel = new_base.name
        ext = new_base.suffix.lower()
        if ext == ".c":
            return _collect_c_changes(rel, old_text, new_text, c_gap_marker)
        if ext == ".h":
            return _collect_h_changes(rel, old_text, new_text)
        old_snippet, new_snippet = _snippet_from_diff_with_context(old_text, new_text, max_preview_lines)
        return [_build_change("修改", rel, "全局区域", old_snippet, new_snippet)]

    if old_base.is_file() != new_base.is_file():
        raise ValueError("旧版本和新版本路径类型不一致，需同时为文件或目录")

    old_files = _iter_files(old_base, exts)
    new_files = _iter_files(new_base, exts)

    all_paths = sorted(set(old_files.keys()) | set(new_files.keys()))
    changes: List[dict] = []

    for rel in all_paths:
        old_path = old_files.get(rel)
        new_path = new_files.get(rel)

        if old_path and not new_path:
            old_text = _read_text(old_path)
            ext = old_path.suffix.lower()
            if ext == ".c":
                changes.extend(_collect_c_changes(rel, old_text, "", c_gap_marker))
            elif ext == ".h":
                changes.extend(_collect_h_changes(rel, old_text, ""))
            else:
                old_snippet, _ = _snippet_from_diff_with_context(old_text, "", max_preview_lines)
                changes.append(_build_change("删除", rel, "全局区域", old_snippet, ""))
            continue

        if new_path and not old_path:
            new_text = _read_text(new_path)
            ext = new_path.suffix.lower()
            if ext == ".c":
                changes.extend(_collect_c_changes(rel, "", new_text, c_gap_marker))
            elif ext == ".h":
                changes.extend(_collect_h_changes(rel, "", new_text))
            else:
                _, new_snippet = _snippet_from_diff_with_context("", new_text, max_preview_lines)
                changes.append(_build_change("新增", rel, "全局区域", "", new_snippet))
            continue

        old_text = _read_text(old_path)
        new_text = _read_text(new_path)
        if old_text != new_text:
            ext = new_path.suffix.lower()
            if ext == ".c":
                changes.extend(_collect_c_changes(rel, old_text, new_text, c_gap_marker))
            elif ext == ".h":
                changes.extend(_collect_h_changes(rel, old_text, new_text))
            else:
                old_snippet, new_snippet = _snippet_from_diff_with_context(old_text, new_text, max_preview_lines)
                changes.append(_build_change("修改", rel, "全局区域", old_snippet, new_snippet))

    return changes
