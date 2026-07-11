# Review Workspace Design

Date: 2026-06-23

## Goal

Add a low-risk human review foundation for AutoDocGen by generating a structured ReviewBundle and an offline, read-only HTML review package alongside the existing docx output. The first version must not change generated Word content. It prepares stable IDs, source hashes, evidence hooks, and quality metadata so later human edits and AI-assisted patch proposals can be audited and replayed.

## Problem

AutoDocGen currently renders directly from parser/pipeline outputs into `.docx`. That is acceptable for final delivery, but weak for human review:

- Reviewers cannot see which source lines support each generated paragraph or logic line.
- Manual edits in Word or HTML cannot be replayed after regeneration.
- AI prompts have no stable block IDs or evidence contract, so proposed edits cannot be safely accepted/rejected.
- HTML output, if added directly as a second renderer, would risk becoming an unstructured parallel document format.

## Design Principle

The editable/reviewable unit is not HTML. The source of truth is a structured `ReviewBundle` JSON. HTML is only a read-only view over that bundle in this phase.

```text
C source / parser / pipeline
  -> FunctionDesign
  -> ReviewBundle JSON
  -> offline HTML review package
  -> existing docx renderer unchanged
```

## Scope For v1

Build:

- `ReviewBundle` data model.
- A builder that converts existing function design data into review blocks.
- A deterministic offline HTML renderer for review.
- CLI/config plumbing to emit the review package.
- Tests for bundle shape, block IDs, HTML escaping, and non-regression of docx generation paths.

Do not build yet:

- In-browser editing.
- AI chat or prompt assistant.
- Patch replay.
- GUI embedded browser.
- clang evidence provider.
- Full Evidence Model replacement.

## User-Facing Behavior

A generation run can optionally produce:

```text
<output-stem>_review/
  index.html
  review_bundle.json
```

The HTML is offline and self-contained enough to open from disk. It shows:

1. Function list.
2. Document preview blocks.
3. Source/evidence metadata when available.
4. Quality flags when available.
5. Stable `data-block-id` attributes for every reviewable block.

The existing `.docx` output remains the formal deliverable.

## CLI / Config

Add optional review output controls to `GenConfig.extra_params` first, with CLI flags if the plumbing is small and low-risk:

```text
--review-output {off,html}
--review-dir PATH
```

Rules:

- Default is `off`.
- `html` writes `review_bundle.json` and `index.html`.
- If `--review-dir` is omitted, derive from docx path: `<output-stem>_review`.
- Invalid paths raise a clear `RenderError` or `ValueError` before partial output is finalized.

## Data Model

Create `autodoc/review_workspace.py` or a small package if the file grows.

Core dataclasses:

```python
@dataclass(frozen=True)
class ReviewSourceRange:
    file: str = ""
    start_line: int = 0
    end_line: int = 0

@dataclass(frozen=True)
class ReviewEvidenceRef:
    kind: str
    ref_id: str = ""
    label: str = ""
    source_range: ReviewSourceRange = field(default_factory=ReviewSourceRange)
    confidence: float = 0.0

@dataclass(frozen=True)
class ReviewQualityFlag:
    code: str
    severity: str = "info"
    message: str = ""
    block_id: str = ""

@dataclass(frozen=True)
class ReviewBlock:
    block_id: str
    function_id: str
    kind: str
    title: str = ""
    text: str = ""
    rows: tuple[dict[str, str], ...] = ()
    source_range: ReviewSourceRange = field(default_factory=ReviewSourceRange)
    evidence: tuple[ReviewEvidenceRef, ...] = ()
    quality_flags: tuple[ReviewQualityFlag, ...] = ()
    confidence: float = 1.0
    editable: bool = True

@dataclass(frozen=True)
class ReviewFunction:
    function_id: str
    name: str
    title: str = ""
    source_file: str = ""
    source_hash: str = ""
    blocks: tuple[ReviewBlock, ...] = ()

@dataclass(frozen=True)
class ReviewBundle:
    schema_version: int
    project_root: str = ""
    output_docx: str = ""
    functions: tuple[ReviewFunction, ...] = ()
    quality_flags: tuple[ReviewQualityFlag, ...] = ()
```

Each dataclass exposes `to_dict()` via a small helper, not by leaking Python object internals.

## Block ID Rules

Block IDs must be deterministic for the same function and same section order:

```text
<function-name>.summary.001
<function-name>.prototype.001
<function-name>.params.input.001
<function-name>.locals.001
<function-name>.logic.001
```

Sanitize function names and kinds to ASCII-ish stable slugs where needed. Keep the raw C function name in the block payload.

Do not use rendered line index after AI cleanup as the only ID. Later phases may map AI replacement through stable block IDs.

## Bundle Builder

The builder accepts existing data already available during rendering/generation:

```python
build_review_function(design: FunctionDesign, func_data: dict, cfg: GenConfig) -> ReviewFunction
```

Initial blocks:

- function title / summary
- function prototype
- input parameters table
- output parameters table
- local variables table
- return description
- logic lines

Fallback behavior:

- If source range is unavailable, use empty `ReviewSourceRange`.
- If evidence is unavailable, keep `evidence=()` and `confidence` below 1.0 only when there is a known quality concern.
- Never fail docx generation just because review metadata is incomplete.

## HTML Rendering

Render from `ReviewBundle`, not from raw design objects.

HTML requirements:

- Escape all user/source text with `html.escape`.
- Include `data-block-id` on review block elements.
- Include minimal CSS inline.
- Include no remote resources.
- Include a function sidebar and block list.
- Include a quality flag section.
- Include a JSON download/open hint by linking `review_bundle.json`.

First layout:

```text
┌──────────────┬─────────────────────────────┬──────────────────────┐
│ Functions    │ Generated Design Blocks      │ Evidence / Warnings  │
└──────────────┴─────────────────────────────┴──────────────────────┘
```

It is acceptable for v1 evidence panel to show only block metadata and quality flags; richer source snippets can come after Evidence Model shadow mode.

## Pipeline Integration

Keep the integration narrow:

1. During project/single-file generation, collect `ReviewFunction` objects after `FunctionDesign` is created and before/after `render_function_design()`.
2. Store collection on `cfg` as internal transient state or return it from pipeline helpers if practical.
3. At the end of generation, if review output is enabled, write:
   - `review_bundle.json` atomically.
   - `index.html` atomically or via temp file + replace.
4. Do not alter `render.py` Word behavior except possibly to expose data already available.

## Error Handling

- Review output disabled: zero behavior change.
- Review output enabled and write fails: generation should surface a clear error after docx state is known. Prefer failing loudly over silently pretending review output exists.
- Partial review directory writes should be avoided using temp files for the two final files.
- Unsupported data in rows should be stringified safely.

## Testing Strategy

Use TDD. Add focused tests before production code.

Test groups:

1. `review_workspace` unit tests:
   - dataclasses serialize to stable JSON-compatible dicts.
   - block IDs are deterministic and sanitized.
   - HTML escapes `<`, `>`, `&`, quotes from source/design text.
   - HTML contains `data-block-id` for each block.

2. Pipeline/config tests:
   - default review output is off.
   - enabling review output writes both files to derived directory.
   - generated docx path behavior is unchanged.

3. PROJECT smoke path if practical:
   - Generate one function with review output enabled.
   - Assert `review_bundle.json` includes the function and at least summary/prototype/logic blocks.
   - Assert HTML contains the function name and no raw unescaped script text.

Avoid brittle exact-prose assertions.

## Rollout

1. Land ReviewBundle model and HTML renderer with unit tests.
2. Wire optional output behind config/CLI flag.
3. Verify existing full pytest remains green.
4. Later add patch schema and AI proposal flow only after ReviewBundle IDs are stable.

## Acceptance Criteria

- Default generation behavior and `.docx` output path remain unchanged when review output is off.
- With review output enabled, AutoDocGen writes `review_bundle.json` and `index.html`.
- `review_bundle.json` contains stable function/block IDs and JSON-compatible fields.
- `index.html` is offline, escaped, and includes `data-block-id` for reviewable blocks.
- Existing tests pass.
- At least one PROJECT single-function generation can produce review output without errors.

## Future Phases

After v1:

- Human patch editing: `review_patches.json` with block-level replace/override operations.
- AI patch assistant: user prompt + evidence -> JSON patch proposal -> human accept/reject.
- Patch replay: source hash conflict detection and compatible patch replay.
- GUI integration: open review HTML after generation; later optional local review service.
- Evidence Model integration: richer source ranges, AST nodes, clang facts, confidence scoring.
