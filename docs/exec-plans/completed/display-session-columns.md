# Display and Session columns

Status: Completed

## Workflow and acceptance

Combine Display and Session into step 4, labeled Display & Session. Timing stays
step 3; Image/Character Size, Fixation, Response and Review become steps 5–8.
Use a 1040 px combined workspace in the existing 1120x820 minimum/default window,
with Display on the left and the wider Session column on the right. Reuse the shared
section heading styles, with no explanatory subtitles. All controls and text must fit
in both themes without required scrolling, including saved-order actions, failed
refresh checks and legacy random-pattern repair. Dropdown text must remain complete.

Keep existing editors/document bindings, optional refresh checking, common display
frame-grid validation and deferred timing drafts. Accept the display target and apply
timing drafts on Next from the combined step. Back returns to Timing with drafts intact.
The display/runtime/session shortcuts all open the combined step; separate Review
summaries retain their matching field content and open that same page.

## Verification

- Update registered Qt coverage for both columns, eight-step navigation, all experiment
  categories, Review links, keyboard traversal and no clipping at 1120x820 in both themes.
- Exercise the longest selector text and busy, error, saved-order and repair states.
  Use existing fake controllers, dialogs, workers and engines.
- Update safe non-Qt navigation regressions; run GUI focused, repository precommit and
  documentation focused checks. Qt execution remains unperformed without explicit
  approval for a safe visible environment.

## Progress

- Combined step 4 uses the existing frameless cards with Display on the left and
  Session on the right. Both column titles are visible; participant-choice headings
  use compact semibold field styling. Keyboard traversal crosses into Session.
- Eight-step navigation, existing shortcuts and Review links now reach the combined
  page. Timing drafts survive Back and apply on its Next; exact common-refresh
  validation and optional refresh checking are preserved.
- Registered Qt coverage now checks both themes at 1120x820, complete dropdown/button
  text, saved/inactive orders, combined refresh/legacy-pattern errors, busy states,
  keyboard traversal, category-specific controls and the full navigation path.
- GUI focused passed (153 safe tests), including 33 navigation/lifecycle regressions;
  documentation focused passed (13 tests). Ruff, changed-file compilation, source
  mypy and precommit audits passed. Repository precommit passed: 4625 tests passed,
  13 skipped because Windows symlink creation is unavailable. Focused GUI checks
  and changed-source mypy also passed after the final keyboard-traversal adjustment.
- Visible Qt/manual acceptance remains unperformed under the repository's
  approved-environment requirement.

## Visible manual smoke path (not performed)

At 1120x820, open Timing, stage a frequency edit and continue to Display & Session.
Confirm Display is left of Session, both headings align, complete selector/button text
fits, and all required controls remain visible. Change refresh and session choices,
return to Timing, then accept the combined step and verify the stored values. Test
saved/inactive condition orders, optional check failure/busy states and pattern repair.
Walk all eight steps and both Review links in both themes; repeat with native AB and
masking projects. Runtime/engine windows must be stubbed or separately approved.

## Changed files

- `src/fpvs_studio/gui/setup_wizard_page.py`
- `tests/unit/test_gui_launch_lifecycle.py`
- Registered GUI tests: `tests/gui/test_attentional_blink_stream_designer.py`,
  `test_components.py`, `test_condition_order_dialog.py`, `test_condition_task_dialog.py`,
  `test_condition_timing_table.py`, `test_randomization_controls.py`,
  `test_setup_experiment_display.py`, `test_setup_project_details.py`,
  `test_setup_review.py`, `test_setup_wizard_shell.py` (all under `tests/gui/`).
- Current contracts/navigation: `AGENTS.md`, `ARCHITECTURE.md`, `docs/FRONTEND.md`,
  `docs/GUI_WORKFLOW.md`, `docs/PLANS.md`, `docs/agent/agent-index.md`,
  `src/fpvs_studio/gui/AGENTS.md` and this plan.
