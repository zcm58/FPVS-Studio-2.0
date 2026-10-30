# Separate Setup timing/display and session pages

Status: Completed

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
   `1120x820`, with expanded seeds and recovery states. Use the existing save/reopen
   and model-preservation regressions for FPVS, AB and masking projects.

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
- [x] Repo precommit: 4,372 tests and 24 subtests passed; 13 Windows symlink-privilege skips.
  Mypy passed for all 261 source files; harness and documentation audits passed.
- [x] Approved visible GUI coverage: 164 tests passed across seven separate processes.
  A further 17 integration checks passed against the combined latest-master candidate.
- [x] Native Windows screenshots inspected at `1120x820`, 100% scaling, in both themes.
  Checks include three complete timing rows, mixed image/word conditions, display
  verification guidance and expanded seed details. Other scaling factors were not inspected.
- [x] Next/Back, ready-project jumps, Review links, seed-error recovery, count blockers
  and atomic saved-order/count repair passed. Save/reopen and category-preservation
  regressions preserve existing editor/model behavior.

The current-checkout precommit run is blocked by six existing E501 errors in
untracked scratch files. The complete precommit run passed in a clean, short-path
integration worktree containing both the latest master and the current feature work.
An earlier nested worktree exceeded Windows fixture path limits; the same failing
compiler case and the full suite passed at the shorter path without source changes.
An earlier long GUI batch timed out while processing palette changes. All seven
modules subsequently passed in fresh visible processes with a 90-second per-test limit.

Automatic approval review rejected cleanup of the generated capture-project folders,
stating "blocked by policy". Those temporary `build/test_env/setup-split-visual*`
folders remain. Screenshots and the precommit log are retained as verification evidence.

## Light-mode native title bar follow-up (2026-10-30)

The native Windows caption already followed Qt's application mode. Existing Main and
Setup styles could retain the previous mode, however, and the shared Setup heading
could remain white after entering light mode. Main now uses the existing palette
observer, passes the resolved palette to an existing Setup page from `event()` after
Qt handles `ApplicationPaletteChange`, and the shared shell observes palette changes.
Native minimize/maximize/close controls remain Windows-owned.

Registered Main/Welcome checks exercise dark/light/dark with complete application
color schemes and palettes, readable heading/menu text, existing Home/Setup, native
Windows 11 dark-caption state, maximize/restore and normal window-button flags.
Both original defects reproduced in controls: the old Main helper stayed dark in
light mode, and the old shell helper kept the light-mode heading white. The five
final visible cases passed, including unchanged-style caching and all eight steps
at `1120x820` in both themes. Native full-window captures were inspected at 100%
scaling; client-only `QWidget.grab()` captures are insufficient for caption acceptance.

The safe backend suite passed again: 4,372 tests and 24 subtests passed, with 13
Windows symlink-privilege skips. Final GUI-only event/header refinements were covered
by the visible cases plus refreshed focused/static checks, rather than repeating the
unchanged backend suite. GUI focused passed 136 tests, docs focused passed ten, and
mypy over 261 files, GC, Ruff and compilation passed. The follow-up changes are in
`gui/components.py`, `gui/main_window.py`, the registered shell/Welcome test modules,
and the current frontend/workflow contracts.
