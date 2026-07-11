# Incremental GUI Mode Design

Date: 2026-06-01

## Goal

Expose the existing incremental generation path in the GUI. The feature should let users opt in to generating only changed functions while keeping full generation as the default behavior.

## Current State

`GenConfig` already has an `incremental: bool = False` field.

`autodoc.pipeline.run_project_generation()` already accepts an `incremental` argument and loads `.autodoc/incremental_state.json` when incremental generation is enabled.

The missing link is GUI configuration: `incremental=True` is not passed from GUI controls into the generation path.

## Recommended Approach

Add a GUI checkbox for incremental mode, default off.

When checked, the GUI passes `incremental=True` into `GenConfig` and then into the project generation runner. When unchecked, behavior remains identical to current full generation.

## Alternatives Considered

### Config File Only

This avoids UI work, but it hides the feature from GUI users and makes the mode easy to forget.

### Default On

This improves repeat-run speed, but it risks surprising users during first runs, cache corruption, or cases where a full refresh is expected.

### CLI Only

This is smaller but does not solve the GUI gap described in `TODO.md`.

## UI Behavior

The checkbox label is `增量模式`.

The checkbox is unchecked by default.

The setting applies only to project generation. Single-file generation should remain unchanged unless it already flows through the same project-generation configuration path.

## Data Flow

1. User checks `增量模式` in the GUI.
2. GUI builds `GenConfig(incremental=True)`.
3. Runner passes the setting to project generation.
4. `run_project_generation(..., incremental=True)` loads existing incremental state.
5. Changed functions are regenerated and unchanged functions are reused according to existing pipeline behavior.
6. Pipeline saves the updated incremental state after a successful run.

## Error Handling

If incremental state is missing, unreadable, or invalid, the existing pipeline fallback behavior should apply. The GUI should not add a second cache parser.

If generation is stopped by the user, incremental state should not be saved unless the existing pipeline already permits it.

## Test Plan

Add focused tests that verify:

- `GenConfig.incremental` defaults to `False`.
- GUI/runner config construction can pass `incremental=True`.
- `run_project_generation()` continues to accept the `incremental` argument.

Manual check:

- Start GUI.
- Confirm `增量模式` appears unchecked.
- Check it and start project generation.
- Confirm logs or behavior show incremental generation is active.

## Scope Boundaries

This change does not rewrite the incremental algorithm.

This change does not change cache file format.

This change does not enable incremental mode by default.
