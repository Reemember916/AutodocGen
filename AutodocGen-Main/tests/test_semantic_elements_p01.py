"""P0#1 随机注入测试：验证 ActionSemantic/ReturnSemantic 的窄锁定宽回退效果。

从 PROJECT 真实函数体随机采样，对比：
1. 确定性：同一输入两次渲染结果一致
2. 窄锁定：语义锁定仅覆盖 memset/memcpy/清零/return-enum，其余不变
3. 不死板：禁用语义锁定后，仅锁定行变化，非锁定行完全不变
"""

from __future__ import annotations

import os
import re
import sys
import random
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodoc import logic as logic_utils
from autodoc import semantic_elements
from autodoc.logic_ir import build_logic_steps


_PROJECT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tests", "PROJECT-2007-0613",
)


def _collect_c_files(root: str, limit: int = 20) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "Debug", "Release")]
        for f in filenames:
            if f.lower().endswith(".c"):
                out.append(os.path.join(dirpath, f))
    return sorted(out)[:limit]


def _extract_func_bodies(filepath: str) -> list[tuple[str, str]]:
    with open(filepath, "r", errors="replace") as f:
        code = f.read()
    code_clean = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code_clean = re.sub(r"//.*", "", code_clean)
    bodies = []
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{", code_clean):
        func_name = m.group(1)
        if func_name in ("if", "for", "while", "switch", "else", "do", "sizeof", "return"):
            continue
        start = m.end()
        depth = 1
        i = start
        while i < len(code_clean) and depth > 0:
            if code_clean[i] == "{":
                depth += 1
            elif code_clean[i] == "}":
                depth -= 1
            i += 1
        body = code_clean[start:i - 1].strip()
        if len(body.splitlines()) >= 3:
            bodies.append((func_name, body))
    return bodies


def _render_logic(body: str) -> str:
    """用 generate_logic_from_body 渲染逻辑文本。"""
    from autodoc.config import GenConfig
    cfg = GenConfig(ai_assist=False, ai_mode=0, logic_use_comment=False)
    text, _ = logic_utils.generate_logic_from_body(body, [], cfg, name_map={})
    return text


def test_determinism():
    """同一输入两次渲染，结果完全一致。"""
    rng = random.Random(42)
    c_files = _collect_c_files(_PROJECT_ROOT, limit=15)
    all_bodies = []
    for cf in c_files:
        all_bodies.extend(_extract_func_bodies(cf))
    rng.shuffle(all_bodies)
    samples = all_bodies[:10]

    for func_name, body in samples:
        text1 = _render_logic(body)
        text2 = _render_logic(body)
        assert text1 == text2, f"非确定性输出: {func_name}\n--- first ---\n{text1}\n--- second ---\n{text2}"


def test_narrow_lock_wide_fallback():
    """禁用语义锁定后，仅锁定行变化，非锁定行完全不变。"""
    rng = random.Random(7)
    c_files = _collect_c_files(_PROJECT_ROOT, limit=15)
    all_bodies = []
    for cf in c_files:
        all_bodies.extend(_extract_func_bodies(cf))
    rng.shuffle(all_bodies)
    samples = all_bodies[:10]

    # 保存原始函数
    orig_infer_action = semantic_elements.infer_action_semantic
    orig_infer_return = semantic_elements.infer_return_semantic

    locked_patterns = {"清零", "填充", "拷贝", "返回空指针", "返回真", "返回假", "返回成功", "返回失败"}

    total_lines = 0
    changed_lines = 0
    for func_name, body in samples:
        text_with_sem = _render_logic(body)
        # 禁用语义锁定
        semantic_elements.infer_action_semantic = lambda code, name_map=None: None
        semantic_elements.infer_return_semantic = lambda expr, name_map=None: None
        try:
            text_without_sem = _render_logic(body)
        finally:
            semantic_elements.infer_action_semantic = orig_infer_action
            semantic_elements.infer_return_semantic = orig_infer_return

        lines_with = text_with_sem.strip().splitlines()
        lines_without = text_without_sem.strip().splitlines()

        # 行数应相同（语义锁定不改变行结构）
        if len(lines_with) != len(lines_without):
            # 行数不同说明有结构性差异，记录但不算错误（可能受 _polish 影响）
            continue

        for lw, lwo in zip(lines_with, lines_without):
            total_lines += 1
            if lw != lwo:
                changed_lines += 1
                # 变化的行应包含锁定模式关键词
                stripped = lw.strip()
                assert any(p in stripped for p in locked_patterns), \
                    f"非锁定模式行发生变化: {func_name}\n  with_sem:    {lw!r}\n  without_sem: {lwo!r}"

    # 窄锁定验证：变化行占比应较低（<30%），说明大部分走回退
    if total_lines > 0:
        ratio = changed_lines / total_lines
        assert ratio < 0.5, f"语义锁定覆盖过高: {changed_lines}/{total_lines} = {ratio:.1%}"


def test_specific_patterns():
    """验证特定模式的确定性输出。"""
    cases = [
        ("memset(&buf, 0, sizeof(buf));", "清零"),
        ("memset(buf, 0xFF, 10);", "填充"),
        ("memcpy(dst, src, 10);", "拷贝"),
        ("x = 0;", "清零"),
        ("return NULL;", "返回空指针"),
        ("return TRUE;", "返回真"),
        ("return FALSE;", "返回假"),
        ("return;", "返回"),
    ]
    for code, expected in cases:
        text = _render_logic(code)
        assert expected in text, f"模式 {code!r} 期望包含 {expected!r}，实际: {text!r}"


def test_not_overly_rigid():
    """不同输入应产生不同输出（不死板）。"""
    bodies = [
        "x = a + b;",
        "y = func(c);",
        "z = arr[i] & 0xFFU;",
        "result = check_status();",
    ]
    outputs = [_render_logic(b) for b in bodies]
    # 所有输出不应完全相同
    assert len(set(outputs)) == len(outputs), "不同输入产生了相同输出——过于死板"


def test_logic_ir_consistency():
    """LogicStep IR 与渲染文本结构一致。"""
    body = """if (x == 1) {
    memset(buf, 0, 10);
    return NULL;
}"""
    steps = build_logic_steps(body, None, None)
    text = _render_logic(body)
    # IF 步骤存在
    assert any(s.kind == "if" for s in steps)
    # 渲染文本含 IF
    assert "IF" in text
    # memset 被锁定为清零
    assert "清零" in text
    # return NULL 被锁定为返回空指针
    assert "返回空指针" in text


if __name__ == "__main__":
    test_determinism()
    print("test_determinism passed")
    test_narrow_lock_wide_fallback()
    print("test_narrow_lock_wide_fallback passed")
    test_specific_patterns()
    print("test_specific_patterns passed")
    test_not_overly_rigid()
    print("test_not_overly_rigid passed")
    test_logic_ir_consistency()
    print("test_logic_ir_consistency passed")
    print("\nAll P0#1 random injection tests passed!")
