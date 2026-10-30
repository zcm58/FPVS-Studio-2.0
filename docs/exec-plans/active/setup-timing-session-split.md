# Separate Setup timing/display and session pages

Status: Active

Date: 2026-10-30

## Approved brief

The experiment author needs to configure timing and the display, then review session
randomization and totals before continuing. The supplied screenshot shows the current
Timing & Session page crowding the timing table, display settings and session controls
onto one surface. Split those tasks while preserving Studio's frameless forms and
shared components. The primary action remains **Next**.

The user approved this split and visible GUI verification in the current session.
Use synthetic projects in the approved visible environment; no offscreen Qt execution.

## Scope and boundaries

- Use eight steps: Project, Conditions, Timing & Display, Session, Image Size
  (Character Size for native AB), Fixation, Response, Review.
- Keep `experiment` as Timing's internal key and preserve timing/display/runtime
  aliases. Make `session` the separate Session key, including Home/Review links.
- Timing & Display retains the frequency/duration/presentation-count table plus
  refresh, verification and background. Session owns seeds, condition order, totals,
  and AB/masking repeats/start key through the existing model-bound editors.
- Fit all steps at `1120x820` without required scrolling or clipping. Timing's
  bounded width is 1040 px for FPVS or 880 px for AB; Session uses 760 px.
- Preserve timing drafts, atomic order saves, display verification gates and
  existing session behavior. Change no core/runtime contracts or persisted schema.
- Retain **Condition order...** beside Timing's table commands: a saved-order/count
  mismatch can block navigation, so the same dialog must open without flushing the
  count draft and save the repair atomically. Session keeps the primary order controls.

## Implementation and acceptance

1. Split page composition and navigation, retaining the existing editor owners.
   Verify sequential Next/Back, ready-project step jumps, earliest-incomplete entry,
   Review edit links, and current timing aliases.
2. Update registered GUI coverage for all eight pages and both themes at `1120x820`.
   Include long condition names, expanded Seed details, unequal durations,
   timing-validation errors, display busy/failure/verified states, and AB/masking
   managed repeats. Preserve navigation's existing pending-edit flush and confirm
   Session totals update after timing/count edits. Condition-order Save retains its
   existing atomic draft behavior.
3. Run GUI and docs focused verification, then repo precommit. Run registered Qt
   coverage in the approved visible environment and inspect real screenshots at
   `1120x820`, with expanded seeds and recovery states. Save/reopen synthetic FPVS,
   AB and masking projects to check persistence without changing their behavior.

## Changed implementation and test files

Implementation under `src/fpvs_studio/gui/`: `setup_wizard_page.py`, `components.py`,
`condition_timing_table.py`, `condition_pages.py`, `document_conditions.py`,
`design_setup_step.py`, and `experiment_designer_dialog.py`. The last four carry
visible-text renames only. The table retains the order-dialog shortcut and recomputes
styled row heights on first show.

Coverage under `tests/gui/`: `helpers.py`, `test_setup_wizard_shell.py`,
`test_setup_experiment_display.py`, `test_setup_review.py`,
`test_randomization_controls.py`, `test_condition_order_dialog.py`,
`test_condition_timing_table.py`, and `test_setup_project_details.py`.

## Evidence

- [x] GUI focused verification: 114 tests passed.
- [x] Docs focused verification: 10 tests passed.
- [ ] Repo precommit verification.
- [ ] Approved visible GUI coverage and screenshot inspection.
- [ ] Navigation, draft recovery, Review links and save/reopen acceptance.

The current-checkout precommit run is blocked by six existing E501 errors in
untracked scratch files. Final verification in the clean integration checkout is
planned. Record the remaining results here before moving the plan to `completed/`
and updating the planning index.
