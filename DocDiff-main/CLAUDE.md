# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

DocDiff compares two software design documents (`.docx`) or C source trees and generates a formal Chinese change-order Word document (“软件文档更改说明书” / “软件代码更改说明书”). It is a small pure-Python app (no packaging layout); modules are imported by package path from the repo root.

Python 3.10+ recommended (developed on 3.13). Win7 EXE builds target Python 3.8.x.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Document change order (defaults: 12.docx, 123.docx → 更改单_测试版.docx)
python3 cli.py
python3 cli.py --mode docx --old old.docx --new new.docx --out out.docx

# Code change order (.c / .h dirs or single files)
python3 cli.py --mode code --old <old_dir_or_file> --new <new_dir_or_file> --out 代码更改单.docx

# Diagnostics
python3 cli.py --mode docx --old a.docx --new b.docx --out out.docx --dump-ast ast.json
python3 cli.py --mode docx --old a.docx --new b.docx --out out.docx --dump-match match.json
python3 cli.py --mode docx ... --fuzzy-threshold 0.80   # stricter section fuzzy pairing (0~1, default 0.72)
python3 cli.py --mode docx ... --json-out changes.json --doc-no WG-001 --version V1.0 --author 张三
python3 cli.py --mode docx ... --tickets samples/问题单台账_示例.csv
python3 cli.py --write-ticket-template 问题单台账.csv
python3 cli.py --mode docx ... --problem-start 10 --no-table-key
python3 -m unittest tests.test_tickets
python3 cli.py --mode code --old old/ --new new/ --out out.docx --json-out changes.json
python3 cli.py --mode code ... --hide-c-gap-marker   # omit "... (省略未改动片段) ..." between C hunks

# GUI
python3 gui_app.py

# Tests (stdlib unittest; pytest also works if installed)
python3 -m unittest tests.test_h3_fallback tests.test_section_matching tests.test_phase1_matching tests.test_phase2_render tests.test_tickets
python3 -m unittest tests.test_section_matching.SectionMatchingTests.test_footnote_title_noise_pairs_as_modify_not_add_delete
python3 tests/test_h3_fallback.py

# Win7 one-file GUI EXE (run on Win7 + Python 3.8)
build_win7.bat   # → dist\DocDiffWin7.exe via PyInstaller 5.13.2
```

Dependencies: `python-docx`, `lxml` only. No project lint/format config. `.gitignore` ignores `*.docx` outputs and `.venv`.

Fixture dirs under `tests/` (`c_h_rule_case`, `c_function_granularity_case`, `complex_code_case`) are sample old/new trees for manual code-diff checks, not automated unit tests.

## Architecture

Two parallel pipelines share the CLI/GUI entry points.

### Document pipeline (`--mode docx`)

```
.docx → build_ast → collect_changes → render_change_order → 更改单.docx
```

| Layer | Module | Role |
|-------|--------|------|
| Extract | `extractor/reader.py`, `extractor/text_extract.py` | Walk docx body in order; pull paragraph + textbox text |
| AST | `canonical/normalize.py`, `model/ast.py` | Build `DocumentAST` of sections/segments/blocks |
| Diff | `diff/collect_changes.py`, `diff/block_diff.py` | Match sections; emit 新增/删除/修改 |
| Render | `render/change_order.py` | Write change-order docx (metadata, uniform tables, optional 问题单挂接); `changes_to_jsonable` |
| Tickets | `tickets/tickets.py` | Load CSV/JSON/XLSX 问题单台账（序号/问题/问题单编号）；按序号挂到「问题N」 |

**AST model** (`model/ast.py`): `DocumentAST` → `Section` → `Segment` → `Block`.

- **Section**: preferably H4; if an H3 has body/tables and no H4 children, that H3 becomes the leaf section (`pending_section` fallback in `build_ast`).
- **Section matching** (`diff/collect_changes.py` → `build_section_pairs`): multi-phase —
  (1) unique parenthetical doc-id (`D/R_…`, `SDD-001-003`, `REQ_12_3`, …),
  (2) duplicate doc-id disambiguation via normalized leaf title / content (`uid_title`),
  (3) normalized `section.key` (strips trailing footnote digits, unifies fullwidth parens/spaces),
  (4) fuzzy title+content score (default ≥ 0.72; prefer same parent path; configurable via `--fuzzy-threshold`),
  else true add/delete.
  Title-only noise (footnote digits) does not emit a「章节标题」change. Whitespace/fullwidth-only body noise is ignored in `diff_segments`.
  Use `--dump-match` for pair method/score and unmatched nearest candidates.
- **Segment**: `_MAIN`, `a`–`z` (fullwidth letters), or `1`/`12`/`（3）` style numbers via `SUB_RE` in `normalize.py`.
- **Block**: `para` or `table`; tables stored as tab-joined row text, with `raw` python-docx object kept for row-level render.

Heading detection is style-name flexible (Heading/标题/custom `NN_N` / outlineLvl) and can treat short bold lines containing a doc-id as H4.

Change records are dicts: `{type, key, seg, old, new, match_method?, match_score?}` where `old`/`new` are `Segment` (or synthetic `_TITLE` for title-only edits). Render only outputs changed paragraph blocks and changed table rows (header row kept by default).

### Code pipeline (`--mode code`)

```
dirs/files → collect_code_changes → render_code_change_order → 代码更改单.docx
```

| Module | Role |
|--------|------|
| `code_diff/collect_code_changes.py` | Walk trees by relative path; default exts `.c`/`.h` only (`DEFAULT_CODE_EXTS`) |
| `render/code_change_order.py` | Title “软件代码更改说明书”; group by file path |

- **`.c`**: function-level extract (brace matching after masking comments/strings), align functions by body core text (not name alone, so renames pair as 修改), then line-range snippets with optional gap markers.
- **`.h`**: whole-file line diff; changed ranges capped (contiguous preview).
- File/dir: both sides file, or both sides directory; mixed types raise `ValueError`.

Code change dicts use `old_text`/`new_text` strings (not AST segments), plus optional `language` / `change_kind`.

### Entry points

- `cli.py`: `run_diff` / `run_code_diff` / diagnostics; argparse (`--dump-match`, `--fuzzy-threshold`, `--json-out`, `--doc-no/--version/--author/--date`, `--problem-start`, `--no-table-key`); GUI imports these.
- `gui_app.py`: tkinter UI, background thread, modes docx/code; docx mode exposes fuzzy threshold, metadata fields, table key-column toggle.
- `docx_diff_changeform.py`: older standalone prototype; **not** on the main path—prefer the modular pipeline above.
- `DocDiff_Win7_Minimal/`: trimmed copy of the same layout for Win7 packaging; keep core modules in sync with root after matching/render changes (copy `diff/`, `canonical/normalize.py`, `render/change_order.py`, `cli.py`, `gui_app.py` at minimum).
- `landing/`: static product page; unrelated to the Python pipeline.

## Domain constraints (affect correctness)

Documents are assumed to be structured software design specs:

- Word Heading 1–4 (or compatible styles).
- Stable H4 ids in parentheses when possible (`D/R_…`, `SDD-…`, `REQ_…`); missing ids fall back to key/fuzzy.
- Intra-section bullets `a)~z)` or `1)` / `（1）` for segment split.
- Table diff is text-signature based (joined cell text); merged cells / complex borders are imperfect.

When debugging missed sections or bad matches, use `--dump-ast` then `--dump-match`, and inspect `canonical/normalize.py` heading logic and `diff/collect_changes.py` pairing phases.
