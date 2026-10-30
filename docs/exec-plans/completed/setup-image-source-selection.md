# Setup Image Source Selection

Status: Completed

## Workflow and boundaries

The author selects a condition, chooses its Base and Oddball image folders, then
continues Setup. Reuse `SetupSourceCard` for folder, count, resolution and full-path
access. Remove image thumbnails, cycle authoring and animated previews from this
Setup surface. Preserve saved timing, source import/normalization, native AB Design,
word authoring, modifiers and the optional standalone visual designer.

## Implementation and acceptance

1. Replace the embedded image designer with a source-only widget using the existing
   worker-backed fresh-source importer and document adoption path.
2. Cover condition isolation, picker cancellation, replacement, import failure/retry,
   busy navigation and absent preview work. Check empty/populated/busy/error states
   at the `1000x600` content budget and full `1120x820` wizard in both themes.
3. Update current workflow/routing docs and run GUI/docs focused verification plus
   repo precommit. Registered Qt coverage is maintained but not run without an
   explicitly approved visible environment. Manual smoke: choose folders for two
   conditions, switch back, replace one pool, cancel a picker, inspect long-path
   details and proceed to Timing without changing saved timing.

## Progress

- Baseline GUI focused verification passed (98 tests).
- Current branch and user-owned untracked output inspected; those paths are preserved.
- Implemented the source-only editor, removed Setup preview construction and timing
  drafts, and updated workflow/routing guidance. Native AB and standalone design
  remain separate. Condition modality changes replace stale image controls.
- Registered GUI coverage checks source selection, condition/role isolation, picker
  cancellation, fresh replacement, error/retry, busy navigation/close, missing sources,
  absent preview work, modality switching and long-name tooltips. Layout coverage
  targets empty/populated/error/importing states at `1000x600` in both themes and
  the complete `1120x820` wizard. These Qt tests were not run; visual acceptance and
  the manual smoke path above remain pending in an approved visible environment.

## Verification

- Final GUI focused: Ruff, compilation and 98 non-Qt tests passed.
- Docs focused: hygiene and 10 tests passed; final plan-location check rerun after
  completion. Changed-file whitespace checks passed.
- Mypy passed for all 260 source files, then for the two changed editor modules after
  the modality guard. Repository garbage-collection/boundary checks passed.
- Standard repo precommit stopped on pre-existing untracked-file Ruff E501 findings
  in `.codex-tmp/cognitive-load-library-2026-10-29/prepare.py` and
  `src/fpvs_studio/engines/standalone_contrast_example.py`. Those files were not edited.
- Running the remaining precommit checks with only those files excluded from
  changed-file lint produced 4,226 passed, 36 failed, 13 skipped and 24 passed subtests.
  Failures were outside the changed GUI: Windows hardlink/junction permissions,
  packaging PowerShell timeout and long fixture paths. The two long-path-sensitive
  runtime/preprocessing tests passed when rerun under a shorter temporary root.
  The repo-wide gate is therefore not claimed as passing.
- The Program Files Git executable could not start in this environment. Verification
  used the working bundled Git through a process-local PATH override.

## Changed files

- GUI: `src/fpvs_studio/gui/image_sources_editor.py`,
  `src/fpvs_studio/gui/design_setup_step.py`, `src/fpvs_studio/gui/setup_wizard_page.py`,
  `src/fpvs_studio/gui/AGENTS.md`.
- Registered coverage: `tests/gui/test_design_setup_step.py`,
  `tests/gui/test_setup_wizard_shell.py`, `tests/gui/test_experiment_categories_gui.py`.
- Current guidance: `ARCHITECTURE.md`, `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`,
  `docs/EXPERIMENT_CATEGORIES.md`, `docs/VISUAL_EXPERIMENT_DESIGNER.md`,
  `docs/agent/agent-index.md`, `docs/PLANS.md`, and this completed plan.
