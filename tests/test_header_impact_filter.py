"""Regression coverage for conservative header-impact expansion."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.update_doc_from_code_diff import (  # noqa: E402
    _changed_header_symbols,
    find_header_impacted_items,
)


def test_changed_header_symbols_keeps_only_diff_identifiers():
    change = {
        "key": "Include/Device.h",
        "old_text": "typedef struct { Uint16 OldState_u16; } Device_t;",
        "new_text": "typedef struct { Uint16 NewState_u16; } Device_t;",
    }
    symbols = _changed_header_symbols(change)
    assert "OldState_u16" in symbols
    assert "NewState_u16" in symbols
    assert "Device_t" not in symbols
    assert "Uint16" not in _changed_header_symbols({
        "old_text": "Uint16 OldState_u16;",
        "new_text": "Uint16 NewState_u16;",
    })


def test_header_impact_requires_function_symbol_reference(tmp_path: Path):
    include = tmp_path / "Include"
    src = tmp_path / "Src"
    include.mkdir()
    src.mkdir()
    (include / "Device.h").write_text(
        "typedef struct { int NewState_u16; } Device_t;\n", encoding="utf-8"
    )
    (include / "Global.h").write_text('#include "Device.h"\n', encoding="utf-8")
    (src / "demo.c").write_text(
        '#include "Global.h"\n'
        'void UsesChanged(void) { int x = NewState_u16; }\n'
        'void DoesNotUseChanged(void) { int y = 0; }\n',
        encoding="utf-8",
    )
    change = {
        "key": "Include/Device.h",
        "old_text": "typedef struct { int OldState_u16; } Device_t;",
        "new_text": "typedef struct { int NewState_u16; } Device_t;",
    }
    items = find_header_impacted_items(
        change,
        new_code=str(tmp_path),
        csu_index={},
        skip_functions=set(),
    )
    assert [item.func_name for item in items] == ["UsesChanged"]
    assert items[0].change["referenced_symbols"] == ["NewState_u16"]
