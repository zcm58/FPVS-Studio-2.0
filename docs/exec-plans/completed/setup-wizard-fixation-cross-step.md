# Split Fixation Cross Into Its Own Guided Wizard Step

## Summary

Rework Setup Wizard from four guided steps to five guided steps:
`Project Details`, `Conditions`, `Experiment Settings`, `Fixation Cross`, and
`Review`. Experiment Settings should contain only display/session logistics.
Fixation Cross becomes a first-class guided setup step with grouped controls and a
GUI-only live preview of the configured cross.

## User Workflow

Users should configure display refresh/background and session structure quickly on
Experiment Settings, then move to a dedicated Fixation Cross step for the fixation
accuracy task. The Fixation Cross step should be easier to read than the compressed
three-column version and should show what the configured cross will look like.

## Implementation Boundaries

- Keep the existing uncommitted horizontal-clipping fixes where useful:
  - main window minimum size `1366 x 820`
  - width-safe setup stepper labels
  - pinned wizard navigation row
  - no hidden horizontal overflow
- Do not change project schema, compiler/runtime contracts, PsychoPy behavior, or
  persisted model fields.
- Route all setting changes through the existing `ProjectDocument` update methods.
- Keep Conditions advanced access unchanged.

## GUI Changes

- Add `("fixation", "Fixation Cross")` before Review in `_WIZARD_STEPS`.
- Remove the fixation editor from the Experiment Settings step.
- Add a guided Fixation Cross step using `FixationSettingsEditor`.
- Keep the existing Behavior, Timing, Response, and Appearance sections visible and
  grouped.
- Add a live preview panel that reflects:
  - default fixation color
  - change fixation color
  - cross size
  - line width
  - selected display background color
- The preview is GUI-only and does not alter runtime rendering or scoring.

## Tests And Verification

- Update pytest-qt coverage for:
  - five wizard steps with Fixation Cross before Review
  - Experiment Settings contains only Display and Session controls
  - Fixation Cross step exposes grouped controls and preview
  - preview updates when appearance values change
  - no horizontal clipping at `1366 x 820` or `1440 x 920`
  - Back/Next visible at default size
- Run:
  - `tests\gui\test_layout_dashboard.py`
  - `tests\gui\test_conditions_session_fixation.py`
  - `python -m pytest -q tests\unit\test_harness_docs.py`
  - `python -m ruff check src\fpvs_studio\gui tests\gui`
  - `git diff --check`

## Completion

After implementation and verification, move this file to
`docs/exec-plans/completed/setup-wizard-fixation-cross-step.md` and commit with:

`Split fixation cross setup step`
