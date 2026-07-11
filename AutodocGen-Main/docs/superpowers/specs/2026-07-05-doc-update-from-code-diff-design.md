# Document Update From Code Diff Design

Date: 2026-07-05

## Goal

Add a staged document-update workflow for embedded C projects:

1. Compare an old code tree and a new code tree.
2. Produce a machine-readable function-level change plan.
3. Update an existing AutoDocGen design document only for safe, uniquely matched modified functions.
4. Report new, deleted, renamed, header-related, duplicate, and unmatched items for review.

The first implementation must be conservative. It should make automatic edits only when the target CSU can be matched uniquely and the source function exists in the new code tree.

## Non-Goals For Current Version

- No automatic renumbering of existing CSU IDs.
- No semantic propagation from macro/type changes to all runtime users beyond the include graph.

New/deleted/renamed functions remain review-driven. `apply-review` can execute the reviewer decisions for replacement, insertion, and deletion.

## Workflow

### DocDiff

DocDiff remains responsible for code comparison.

Add JSON output to `DocDiff-main` code mode:

```bash
python3 cli.py --mode code --old OLD_CODE --new NEW_CODE --out code_change.docx --json-out code_changes.json
```

Each change record should keep existing human-readable fields and add machine fields when available:

- `type`: `新增`, `删除`, or `修改`
- `key`: relative file path
- `seg`: display signature or area
- `language`: `c`, `header`, or `text`
- `change_kind`: `new_function`, `deleted_function`, `modified_function`, `new_file`, `deleted_file`, `header_changed`, or `text_changed`
- `function_name`
- `old_function_name`
- `new_function_name`
- `old_signature`
- `new_signature`
- `old_text`
- `new_text`

### AutoDocGen

Add a script:

```bash
python3 tools/update_doc_from_code_diff.py \
  --old-code OLD_CODE \
  --new-code NEW_CODE \
  --old-doc OLD.docx \
  --out NEW.docx \
  --docdiff-root /Users/ree/Downloads/DocDiff-main \
  --mode plan-only
```

Modes:

- `plan-only`: generate reports only.
- `apply-safe`: copy `old-doc` to `out`, then update only safe modified functions.
- `apply-review`: copy `old-doc` to `out`, apply safe modified functions, then apply explicit reviewer decisions from `review_decisions.json`.

Future modes may include `apply-all`.

### GUI

The Qt GUI exposes a "文档增量更新" card on the home page:

- old code directory
- new code directory
- old Word document
- optional `review_decisions.json`
- mode: `plan-only`, `apply-safe`, or `apply-review`

The GUI worker runs the same planner/apply/report pipeline as the CLI and emits the plan, report, review HTML, code diff DOCX, and code diff JSON sidecars.

## Safety Rules

`safe`:

- `modified_function`
- `.c` source exists in the new tree
- old document has exactly one matching CSU for that function name

`review`:

- `new_function`
- `deleted_function`
- `renamed_function`
- `header_impacted_function` with a unique CSU match
- unique CSU match exists, but action would insert or delete content

`manual`:

- raw header changes
- duplicate function names in old document
- no CSU match
- multiple CSU matches
- missing source file
- malformed change record

First version applies only `safe` items. `apply-review` additionally applies explicit `replace_csu`, `insert_after_csu`, and `delete_csu` decisions.

`renamed_function` is detected conservatively by pairing one deleted function and one new function in the same `.c` file when their normalized bodies are highly similar. It is reported for review with the old CSU ID prefilled, so reviewers can choose `replace_csu`.

`header_impacted_function` is detected conservatively by building a project include graph. A changed header marks headers that include it, directly or transitively; `.c` files that include any impacted header contribute their functions for review when the function has a unique old CSU match. Direct source changes are not duplicated as header impact items.

## Matching Strategy

Build a CSU index from the old document:

- Scan Heading 4 paragraphs.
- Extract `D/R_SDD01_...` CSU IDs from the heading text.
- Look ahead for the `a) 函数原型` paragraph and parse the following prototype for the C function name.
- Index by function name.

For each modified function from DocDiff, match by function name. If exactly one CSU is found, the item is safe.

## Apply-Safe Behavior

For each safe item:

1. Resolve new source path from `new-code` + relative file path.
2. Call `autodoc.pipeline.regenerate_csu_in_doc(out_doc, source, func_name, csu_id, cfg, project_root=new_code)`.
3. Record success or failure in the report.

Failures do not stop the whole run. They are marked as `failed` with the exception text.

## Outputs

For every run:

- `OUT.update_plan.json`
- `OUT.update_report.md`
- `OUT.update_review.html`
- DocDiff code change `.docx`
- DocDiff code change `.json`

For `apply-safe`:

- `OUT` copied from old doc and updated in place.

## Testing

Focused checks:

- DocDiff code mode still generates the human `.docx`.
- DocDiff `--json-out` emits machine fields.
- AutoDocGen planner classifies modified/new/deleted/header changes.
- `plan-only` never writes the output doc.
- `apply-safe` copies the old doc before applying edits.

## HTML Review Workflow

Generate a static review page from `update_plan.json`.

The page must not require a server. It embeds the plan JSON and lets a reviewer:

- filter by status/action/reason;
- inspect old/new code snippets;
- choose a decision for review/manual items;
- add notes;
- export `review_decisions.json`.

Initial decisions:

- `skip`
- `manual`
- `replace_csu`
- `insert_after_csu`
- `delete_csu`

The HTML page exports decisions. `apply-review` consumes that JSON:

```bash
python3 tools/update_doc_from_code_diff.py \
  --old-code OLD_CODE \
  --new-code NEW_CODE \
  --old-doc OLD.docx \
  --out REVIEWED.docx \
  --mode apply-review \
  --review-decisions review_decisions.json
```

Conservative execution scope:

- `replace_csu`: executable. It regenerates the selected function from the new source tree and replaces the reviewer-provided target CSU ID.
- `skip`: recorded as skipped when the item was not already applied as safe.
- `manual`: recorded as manually handled outside the tool.
- `insert_after_csu`: executable. It regenerates the selected function as a complete CSU and inserts it after the reviewer-provided anchor CSU ID. If the reviewer leaves the target CSU ID empty, the tool allocates the next CSU ID in the same module by scanning existing IDs. The module function table is synchronized from actual H4 headings after insertion.
- `delete_csu`: executable. It deletes the target CSU heading and its body up to the next H4/H3 heading. The module function table is synchronized from actual H4 headings after deletion.

Module table synchronization preserves the actual CSU IDs found in headings. It does not renumber existing CSU headings automatically.
