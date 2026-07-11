# Source Understanding Pipeline Design

Date: 2026-06-22

## Goal

Raise AutoDocGen output quality from rule-based C-to-Chinese draft generation to evidence-driven design-document generation. Each generated function section should be grounded in source evidence: normalized comments, AST nodes, expression structure, variable bindings, and quality metadata.

The immediate production target is the PROJECT-2007-0613 project, where current single-function generation succeeds but shows these defects:

- Function descriptions can degrade to `无。` even when source comments contain usable descriptions.
- Bitwise expressions such as `x & 0xFFU` can be mistranslated as logical “且 0xFF”.
- Multi-variable declarations can bind shared inline comments to the wrong variable.
- Empty `else { /* no deal to do */ }` blocks and low-value initializations leak into the generated logic.
- Complex communication/control functions are rendered as line-by-line translations instead of design intent.

## Current State

The current pipeline is mostly text/rule driven:

1. `autodoc.parse._parse_c_file_base()` strips inactive preprocessor regions, finds comments, finds functions, and extracts bodies.
2. `parse_single_comment_block()` parses comment blocks using label regexes.
3. `pipeline.prepare_design_context()` builds local variables, parameters, name maps, LSP facts, and semantic packs.
4. `logic.generate_logic_from_body()` splits the function body into line records, attaches comments, and emits Chinese logic lines.
5. `render.py` writes the final `FunctionDesign` to docx.

Tree-sitter exists in the project, but current function extraction still treats regex parsing as the primary behavior. The existing Tree-sitter design from 2026-06-01 added cross-checking, not replacement.

The CLI path sets `ai_assist=False`, so the observed PROJECT results are mostly static rule output.

## Recommended Approach

Implement a staged, low-risk replacement of brittle text parsing with structured source understanding. Do not rewrite the whole generator at once. Add focused components and route only proven data through them.

### Stage 1: Comment Normalization

Add `autodoc/comment_normalizer.py`.

Responsibilities:

- Accept raw block or line comments.
- Strip decorative comment markup.
- Recognize label variants:
  - `【功能描述】...`
  - `[功能描述] ...`
  - `功能描述: ...`
  - `功能说明: ...`
  - `输入参数说明`, `输出参数说明`, `返回`, `其他说明`
- Support label text on the same line or following lines.
- Preserve multi-line function descriptions.
- Ignore separator-only blocks such as `/* ***** */`.
- Produce normalized fields with evidence line offsets where available.

Output shape:

```python
@dataclass(frozen=True)
class NormalizedComment:
    func_name: str = ""
    func_cn_name: str = ""
    desc: str = ""
    input_desc: str = ""
    output_desc: str = ""
    other_desc: str = ""
    return_desc: str = ""
    evidence: tuple[CommentEvidence, ...] = ()
```

`parse_single_comment_block()` should delegate to the normalizer and preserve its public dict contract.

Acceptance cases from PROJECT:

- `TimeCountInit` keeps `时间计数初始化`.
- `FdataAverage` extracts the full average/filtering behavior instead of `无。`.
- `Comm422FrameCheck` extracts `检测对应通道接收缓冲区是否存在有效报文` and return semantics.

### Stage 2: AST Expression Rendering

Add a small C expression IR backed by Tree-sitter, not a full compiler front-end.

Initial IR node kinds:

- `IdentifierExpr`
- `LiteralExpr`
- `CallExpr`
- `SubscriptExpr`
- `FieldExpr`
- `UnaryExpr`
- `BinaryExpr`
- `ParenthesizedExpr`

Add `autodoc/c_expr.py` or equivalent module with:

```python
def parse_c_expression(expr_text: str) -> ExprIR | None

def render_expr_cn(expr: ExprIR, name_map: dict[str, str], rules: DomainRules) -> RenderedExpr
```

Initial rendering rules:

- `x & 0xFFU` -> `x 的低 8 位`.
- `(~sum + 1U) & 0xFFU` -> `低 8 位补码校验和` when the context is checksum-like.
- `buffer[i]` preserves index meaning when the index is named or inferable.
- `struct_array[channel].member[offset]` preserves base, channel, member, and offset instead of collapsing to `当前项`.

This stage should be used first inside condition and assignment rendering paths, not across the entire project.

Acceptance cases from PROJECT:

- `Comm422FrameCheck` no longer emits `且 0xFF` for byte masking.
- Checksum expression is described as low-eight-bit two's-complement checksum.
- Candidate frame offset `l_ii_u16` remains visible in frame-buffer expressions.

### Stage 3: Variable Meaning Binding

Improve local variable extraction and comment binding.

Rules:

- Use AST declarator lists to split multi-variable declarations.
- Split shared inline comments by Chinese/ASCII separators when counts match variables:
  - `，`
  - `、`
  - `/`
  - `,`
- Bind split comment parts positionally.
- Fall back to identifier conventions only when comment binding is absent or low confidence:
  - `min` -> `最小值`
  - `max` -> `最大值`
  - `sum` -> `累加和` or `数据和`
  - `cnt/count` -> `计数`
  - `idx/index/ii/jj` -> `索引`
- Preserve a source/confidence field internally so later stages can prefer high-confidence names.

Acceptance cases from PROJECT:

- `l_min_f` -> `最小值`, not `最大值`.
- `l_max_f` -> `最大值`.
- `l_sum_f` -> `数据和值` or `累加和`.
- `l_ii_u16` and `l_jj_u16` do not both collapse into indistinguishable logic when loop nesting matters.

### Stage 4: Logic IR and Noise Reduction

Introduce a logic IR between source parsing and Chinese rendering.

Initial step kinds:

- `IfStep`
- `ElseIfStep`
- `ElseStep`
- `ForStep`
- `AssignmentStep`
- `CallStep`
- `ReturnStep`
- `BreakStep`

Each step should retain source line evidence and structured expressions.

Add a quality/noise pass before rendering:

- Remove empty `else` branches created by `no deal to do` comments.
- Suppress low-value declaration initializations unless they establish a return default, state default, or error default.
- Collapse repeated initialization text when one occurrence is only declaration boilerplate.
- Preserve loop-scoped resets when semantically meaningful, rendering them as loop-scoped actions.

Acceptance cases from PROJECT:

- `FdataAverage` omits empty `ELSE` / `END IF` noise.
- `Comm422FrameCheck` keeps per-candidate `l_headErrCnt_u16 = 0U` as loop-scoped reset, but does not repeat meaningless setup lines.
- Generated logic reads like design intent, not raw line translation.

### Stage 5: Domain Rules

Add a small, explicit rule set for embedded/control/communication idioms. Keep it deterministic and evidence-based.

Suggested modules:

- `autodoc/domain_rules/bit_ops.py`
- `autodoc/domain_rules/comm_frame.py`
- `autodoc/domain_rules/timer.py`
- `autodoc/domain_rules/watchdog.py`

Initial rules:

- Byte mask: `x & 0xFFU` -> low-eight-bit value.
- Two's-complement checksum: `(~sum + 1U) & 0xFFU` -> low-eight-bit complement checksum.
- Timer delta calls -> elapsed time checks.
- Watchdog feed/toggle calls -> internal/external watchdog feed behavior.

Rules must only fire when the source pattern matches. Do not infer domain behavior without source evidence.

## Data Flow

```text
C source
  -> inactive-preprocessor stripping
  -> comment_normalizer
  -> Tree-sitter function/expression extraction
  -> variable meaning binding
  -> logic IR
  -> domain-rule enrichment
  -> noise reduction
  -> Chinese renderer
  -> quality audit
  -> docx renderer
```

Existing dict-based contracts can remain at module boundaries until the new data classes are proven. The first implementation should adapt normalized outputs back into existing `comment_info`, `local_vars`, and logic-line structures.

## Error Handling

- If Tree-sitter is unavailable or expression parsing fails, fall back to current behavior for that expression only.
- A normalizer failure must not block document generation; it should return empty fields and record a low-confidence reason.
- Domain rules must be pure and deterministic. A rule failure should degrade to generic expression rendering.
- New stages should emit verbose diagnostics behind existing `cfg.verbose` / `utils.vlog` paths.

## Quality Audit

Extend existing quality metadata to flag:

- Missing function description while raw comment evidence exists.
- Bitwise operators rendered as logical conjunction text.
- Empty `ELSE` blocks in final logic.
- Duplicate adjacent initialization lines.
- Low-confidence variable names used in tables or logic.

The audit should not block generation by default. It should make unsafe output visible.

## Testing Plan

Add focused unit tests before wiring broad behavior:

1. Comment normalizer tests using real PROJECT comment blocks.
2. Expression parser/render tests for bit masks, checksum, array indexing, and member access.
3. Variable binding tests for multi-variable declarations with split comments.
4. Logic cleanup tests for empty `else`, declaration initialization filtering, and loop-scoped reset preservation.
5. Regression tests that generate or build `FunctionDesign` for:
   - `TimeCountInit`
   - `FdataAverage`
   - `Comm422FrameCheck`

The regression assertions should check behavior, not exact prose. Examples:

- `FdataAverage` description contains average/removing max/min semantics.
- `Comm422FrameCheck` logic contains low-eight-bit/checksum semantics and does not contain `且 0xFF`.
- Final logic does not contain bare empty `ELSE` blocks.

## Scope Boundaries

This design does not require:

- Full C type checking.
- Full preprocessor expansion.
- Replacing the Word renderer.
- Enabling AI by default.
- Rewriting GUI behavior.
- Building a whole-program data-flow engine.

AI, when enabled later, should only summarize or polish low-confidence structured evidence. It must not become the source of truth.

## Rollout Plan

1. Stage 1 ships first because it fixes the highest-visibility production defect with low risk.
2. Stage 2 is opt-in internally for selected expression paths, then expanded.
3. Stage 3 updates local variable tables after targeted tests pass.
4. Stage 4 changes logic generation output and should be guarded by regression tests over PROJECT samples.
5. Stage 5 rules are added incrementally as evidence-backed cases appear.

## Success Criteria

On the PROJECT-2007-0613 sample functions:

- All three sample functions generate docx without errors.
- `FdataAverage` and `Comm422FrameCheck` no longer output `功能说明: 无。` when source comments provide descriptions.
- `Comm422FrameCheck` no longer mistranslates byte masks as logical `且 0xFF`.
- `FdataAverage` local variable table does not misassign `l_min_f` as maximum-value usage.
- Generated logic contains no bare empty `ELSE` branch from `no deal to do`.
- Existing simple-function output for `TimeCountInit` does not regress.


## Next Roadmap: Semantic Elements / Evidence / AST Migration

The 2026-06-22 implementation fixed the immediate PROJECT production defects while preserving the existing rule-based pipeline. The next phase should not be a one-shot rewrite. Add semantic elements and evidence in shadow/gated paths first, then migrate proven rendering paths behind feature flags.

### Current Baseline After 2026-06-22

- Comment normalization is implemented and wired into the parser contract.
- A lightweight `ExprIR` exists in `autodoc/c_expr.py` for byte masks, checksum expressions, subscript/member access, and selected assignment/condition paths.
- Local variable binding handles multi-declarator comments, identifier-token fallbacks, custom typedef pointer compatibility, and `ii`/`jj` preservation.
- Final logic cleanup removes empty `ELSE` noise, preserves loop resets, handles `DO WHILE` / `SWITCH CASE`, and remaps AI unknown indexes after cleanup.
- Final PROJECT focused regressions pass, and full pytest passed before merging to `main`.

### Migration Principle

Do not replace regex/string rules directly with a new AST generator. First create source evidence and semantic element records beside the existing output. Only switch a path when the evidence/semantic path has tests, PROJECT sample coverage, and a fallback to current behavior.

AI must not be a final text generator for processing logic. If AI is enabled, it may only propose constrained semantic fields such as labels, roles, relations, and action types. Deterministic renderers own the final GJB-style text.

Processing logic style:

- Keep control skeletons such as `IF`, `ELSE IF`, `ELSE`, `FOR`, `WHILE`, `SWITCH`, `CASE`, `RETURN`, `BREAK`, `NEXT`, and `END IF`.
- Use short condition/action phrases, not free-form natural-language paragraphs.
- Do not summarize across multiple logic statements inside detailed logic. Summary belongs in function description or an explicit overview section.
- Render examples should prefer `IF 报文头等于 RS422 帧头 1 时` over explanatory prose such as `当候选报文帧头有效时，继续进行后续帧校验`.

### Phase A: Semantic Element Inference + Deterministic GJB Renderer

Add a small semantic-element layer between expression/logic structure and Chinese rendering:

```python
SemanticElement
ConditionSemantic
ActionSemantic
ReturnSemantic
```

Rules:

- Rule/comment/AST/clang/AI sources may propose semantic elements.
- The final renderer consumes semantic elements and emits fixed GJB-style phrases.
- AI output must be schema-validated and limited to fields such as `label`, `role`, `relation`, `action`, `confidence`, and `evidence_ids`.
- Invalid or unsupported AI semantic proposals are discarded and the existing rule fallback is used.

Initial vertical slice: IF condition semantics.

Example:

```text
Input expression: RS422_COMM_FRAME_HEAD_1 == (buf[i] & 0xFFU)
Semantic: left_label=报文头低8位, relation=equals, right_label=RS422帧头1
Render: IF 报文头低8位等于RS422帧头1时
```

Acceptance:

- Without AI, existing rule logic can produce semantic elements for common equality, mask, macro, subscript, and field conditions.
- With AI, AI only fills schema fields and never returns final logic text.
- `Comm422FrameCheck` frame-head / low-eight-bit conditions stay concise and do not become explanatory paragraphs.
- Existing PROJECT docx generation does not regress.

### Phase B: Evidence Model Shadow Mode

Add `autodoc/evidence/` with minimal data classes:

```python
SourceRange
FunctionEvidence
CommentEvidence
VariableEvidence
ExpressionEvidence
LogicStepEvidence
RenderedLineEvidence
```

Requirements:

- Produces JSON/debug evidence for each generated function.
- Does not change docx output.
- Tracks source ranges, confidence, fallback reason, and source subsystem (`regex`, `tree_sitter`, `clang`, `rule`, `comment`).
- Covers `TimeCountInit`, `FdataAverage`, and `Comm422FrameCheck` first.


### Phase C: Clang Evidence Provider Shadow Mode

Add a clang/clangd evidence provider without making clang a hard dependency.

Inputs:

- `compile_commands.json` when available.
- Existing CCS conversion script output.
- Existing LSP/clangd compatibility headers and facts modules.

Outputs:

- Compile command health.
- Diagnostics.
- Symbol/type facts.
- Typedef pointer/type information.
- Definition/reference availability.

Rules:

- Clang unavailable or low-quality diagnostics must not block generation.
- Clang facts can raise confidence or explain parser disagreements, but do not override existing output until a later gated phase.

### Phase D: AST-backed Expression IR

Upgrade `autodoc/c_expr.py` so Tree-sitter expression nodes are the preferred input and the existing string parser is fallback.

Initial coverage:

- identifiers and literals
- calls
- subscript expressions
- field and pointer-field expressions
- unary and binary expressions
- casts and parentheses
- comparisons, logical ops, bitwise ops, shifts

Acceptance:

- Existing low-eight-bit/checksum regressions pass.
- Unsupported expressions degrade to current rendering for that expression only.
- Fallback/raw renderings never mix raw C operators into confident Chinese rule output.

### Phase E: LogicStep IR Shadow Mode

Add `autodoc/logic_ir.py` with a structured step sequence built from function bodies:

- `IfStep`, `ElseIfStep`, `ElseStep`
- `ForStep`, `WhileStep`, `DoWhileStep`
- `SwitchStep`, `CaseStep`, `DefaultStep`
- `AssignmentStep`, `CallStep`, `ReturnStep`, `BreakStep`

Each step retains:

- source range / line
- attached comments
- expression IR
- scope depth
- confidence
- fallback reason

Shadow-mode acceptance:

- PROJECT sample functions produce complete step sequences.
- Empty else, declaration defaults, loop resets, and switch/case regions are structurally identifiable.
- Existing rendered docx output remains unchanged.

### Phase F: Gradual Renderer Cutover

Switch rendering in small order:

1. `ReturnStep`
2. simple `AssignmentStep`
3. `CallStep`
4. `IfStep` / `ElseIfStep` conditions
5. `ForStep` / loop headers
6. `SwitchStep` / `CaseStep`

Rules:

- Each cutover must keep the old renderer as fallback.
- Each cutover needs focused unit tests plus PROJECT sample verification.
- Unknown AI replacement should use stable step IDs, not rendered line indexes.

### Phase G: Domain Rule Modules

Move proven deterministic domain rules into explicit modules:

```text
autodoc/domain_rules/bit_ops.py
autodoc/domain_rules/comm_frame.py
autodoc/domain_rules/timer.py
autodoc/domain_rules/watchdog.py
```

Each rule returns a domain meaning with evidence and confidence. Rules must only fire on source patterns they can prove.

### Phase H: Quality Audit

Extend quality metadata to report:

- output lines with no source evidence
- low-confidence variable names
- clang/tree-sitter/parser disagreement
- raw C leakage
- bitwise-as-logical risk
- fallback-heavy functions
- AI replacements without stable evidence IDs

The audit should warn by default, not block generation.

### Non-goals For The Next Cycle

- No full C compiler replacement.
- No mandatory clang dependency.
- No wholesale rewrite of `logic.py` in one PR.
- No AI-generated final processing-logic text; AI may only propose validated semantic elements.
- No Word renderer rewrite.