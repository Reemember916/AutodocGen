"""S4: narrow semantic locks for logic rendering."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.semantic_elements import (  # noqa: E402
    infer_action_semantic,
    infer_return_semantic,
    render_action_semantic,
    render_return_semantic,
)


def test_memset_clear_and_fill():
    name_map = {"buf": "缓冲区"}
    a = infer_action_semantic("memset(buf, 0, 16);", name_map)
    assert a is not None and a.action == "clear"
    assert "清零" in render_action_semantic(a)
    b = infer_action_semantic("memset(buf, 0xFF, 16);", name_map)
    assert b is not None and b.action == "fill"


def test_memcpy_and_memmove():
    name_map = {"dst": "目标", "src": "源"}
    a = infer_action_semantic("memcpy(dst, src, n);", name_map)
    assert a is not None and a.action == "copy"
    text = render_action_semantic(a)
    assert "拷贝" in text and "源" in text and "目标" in text
    b = infer_action_semantic("memmove(dst, src, n);", name_map)
    assert b is not None and b.action == "copy"


def test_assign_clear_and_bool_flags():
    name_map = {"flag": "就绪标志", "cnt": "计数"}
    a = infer_action_semantic("cnt = 0;", name_map)
    assert a is not None and a.action == "clear"
    b = infer_action_semantic("flag = TRUE;", name_map)
    assert b is not None and b.action == "set_true"
    assert "真" in render_action_semantic(b)
    c = infer_action_semantic("flag = FALSE;", name_map)
    assert c is not None and c.action == "set_false"
    assert "假" in render_action_semantic(c)


def test_return_null_true_error_codes():
    assert render_return_semantic(infer_return_semantic("NULL")) == "返回空指针"
    assert render_return_semantic(infer_return_semantic("TRUE")) == "返回真"
    assert render_return_semantic(infer_return_semantic("E_TIMEOUT")) == "返回超时"
    assert render_return_semantic(infer_return_semantic("RET_OK")) == "返回成功"
    # Unknown free-form expression → no lock
    assert infer_return_semantic("foo + 1") is None
