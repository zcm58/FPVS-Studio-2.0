# One pseudorandom condition-order editor

Status: Completed

## Workflow and acceptance

Keep one Setup entry, Edit condition order in Display & Session. Name its modal
Pseudorandom Condition Order Editor. Provide one short instruction for selecting and
moving a presentation, plus clear Generate new order and Save order actions. Preserve
700x520 minimum / 780x620 default sizes, long-name tooltips, both themes and worker states.
Remove the Timing shortcut. Timing still checks presentation feasibility; order-only
conflicts are handled in Session so the sole editor stays reachable. Keep staged timing
and count edits until the existing atomic order-save path succeeds. Genuine timing/count
errors retain their Timing correction path. No core, persisted-format or engine changes.

## Verification

Update registered modal and wizard tests for one entry, title/copy, minimum-size fit,
saved-order repair from Session, keyboard traversal, atomic drafts and stale/busy errors.
Add safe navigation/conflict classification regressions. Run GUI/docs focused and repo
precommit checks without Qt. Visible Qt/manual smoke remains unperformed unless approved.

## Visible smoke path (not performed)

At 1120x820 in both themes, visit Timing, stage counts that invalidate a saved order,
and continue to Display & Session. Confirm the sole Edit condition order button opens
the named dialog. At both dialog sizes, select/move a presentation, generate another
candidate and save. Check equal or adjacent duplicate validation, failed/stale saves,
cancellation, source retention, full button text and long-name tooltips. Confirm Next
stays in Session for an order-only problem and genuine timing errors return to Timing.

## Progress

- Renamed modal and actions, added concise arrangement instructions, and removed the
  Timing button/signal. Display & Session retains the only editor entry.
- Split saved-order validity from Timing count feasibility. Session displays/focuses
  order repair; genuinely invalid timing/count drafts keep their Timing path. Atomic
  Save/clear, current-signature checks and generation worker ownership are preserved.
- Registered Qt tests updated for both sizes/themes, one entry, keyboard traversal,
  stale/busy states and persisted/staged order repair. They remain unrun without
  approval for a safe visible environment.
- Safe lifecycle/navigation tests passed (43), including six core-backed conflict
  classification states. GUI focused passed (155 before the final eight classification/
  routing cases); documentation focused passed (13). Ruff, compilation, full source
  mypy and precommit audits passed.
- Full safe precommit: 4642 passed, 13 Windows symlink skips, one failure in unchanged
  `test_project_bundle_update.py::test_separate_installed_newer_copy_does_not_block_update_of_current_project`.
  Windows denied a temporary import-staging directory rename (`WinError 5`). The whole
  isolated bundle-update module then passed (33). No unrelated import implementation
  was changed. The full run remains recorded as failed, not a clean full-suite pass.

## Changed files

- GUI: `src/fpvs_studio/gui/condition_order_dialog.py`, `condition_timing_table.py`,
  `randomization_editor.py`, `setup_wizard_page.py` (all under the same GUI directory).
- Coverage: `tests/gui/test_condition_order_dialog.py`,
  `tests/gui/test_setup_experiment_display.py`, `tests/unit/test_gui_launch_lifecycle.py`.
- Contracts/navigation: `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, `docs/PLANS.md`,
  `src/fpvs_studio/gui/AGENTS.md` and this plan.
