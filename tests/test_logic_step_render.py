"""LogicStep primary render path smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodoc.logic_step_ir import build_logic_steps, render_logic_steps_to_lines  # noqa: E402
from autodoc.pipeline import logic_step_ir_primary  # noqa: E402
from types import SimpleNamespace


BODY = """
{
    unsigned int status = 0U;
    if (status != 0U)
    {
        status = 0U;
    }
    return NULL;
}
"""


def test_render_logic_steps_basic():
    steps = build_logic_steps(BODY, [], None, name_map={"status": "状态"})
    assert steps
    lines = render_logic_steps_to_lines(steps, name_map={"status": "状态"})
    joined = "\n".join(lines)
    assert "IF" in joined or "if" in joined.lower() or any("状态" in ln for ln in lines)
    assert any("返回" in ln for ln in lines)


def test_logic_step_primary_flag():
    assert logic_step_ir_primary(SimpleNamespace(extra_params={"logic_step_ir": "primary"})) is True
    assert logic_step_ir_primary(SimpleNamespace(extra_params={"logic_step_ir": "shadow"})) is False
    assert logic_step_ir_primary(SimpleNamespace(extra_params={})) is False
