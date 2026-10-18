# Behavior-preserving cleanup

Status: Completed

Date: 2026-10-18

## Approved outcome

Implement the ten reviewed cleanup proposals on `cleanup/behavior-preserving-audit`,
verify preserved behavior, report source-line reduction, and merge into the previous
branch, `master`. Remove obsolete local feature branches only after proving their
tips are contained in the merged branch. Preserve unique work and remote branches.

## Scope and constraints

- Remove the unused assets-readiness widget, GUI summary/project-entry helpers,
  scheduling helpers, and export-header wrapper identified by repository-wide usage searches.
- Share image-size control binding without changing layouts, object names, signals,
  sender-sensitive width updates, errors, or persisted settings.
- Share explicit run/session CSV headers and row projections; preserve exact output
  bytes, column/row order, conversion, eager evaluation, and atomic failure behavior.
- Reuse ordered entries within each export invocation and unify weighted reaction-time
  calculation without changing arithmetic order or missing-value rules.
- Remove discarded text-height results and replace fallback transition scans with
  equivalent cadence arithmetic, retaining seeded output and period-one behavior.
- Reuse canonical preprocessing manifest queries while preserving compiler guards.
- Put the existing numeric-step predicate in the neutral core task owner and reuse it
  in runtime and engine; retain its integer special case and tolerance.
- Preserve public compatibility imports, historical schemas/exports, hardware behavior,
  project paths, runtime boundaries, and unrelated files.

## Verification

Run compiler, GUI, runtime, engine, preprocessing and documentation focused checks,
then the complete repository precommit tier. Use exact seeded schedule and export
comparisons and meaningful registered GUI regression coverage. Local Qt execution
requires an explicitly approved safe visible environment; no offscreen execution.
No live hardware, participant presentation, network reporting, or installer execution
is part of this cleanup.

Visible GUI acceptance: open Setup > Image Size and its fullscreen preview at their
documented sizes, edit width and each calibration/distance/aspect field, verify mutual
synchronization and unchanged height-constrained geometry, then verify validation/error
recovery and child-widget bounds. Use synthetic projects and isolated preferences.

## Progress

- [x] Audit proposals and obtain implementation/merge/branch-cleanup authorization.
- [x] Implement all ten proposals and inspect the combined diff.
- [x] Complete focused checks and exact-output regressions.
- [x] Complete repository precommit and independent review; record existing failures.
- [x] Record line counts, verification limits, and merge/branch cleanup.

## Verification evidence

- Production Python diff: 751 lines removed, 330 added, net reduction 421 lines.
  GUI accounts for 275, compiler helpers/scheduling 60, exports 82, and shared numeric
  validation 4. Regression tests and documentation are counted separately.
- Compiler focused: 413 passed; preprocessing: 30; engine: 375; safe GUI: 17;
  runtime: 625 passed with two Windows symlink-privilege skips.
  Compiler comparison against the original source matched 336 seeded schedule or
  exception outcomes. Six frozen schedule regressions preserve boundary cases.
- Export coverage fixes expected CSV bytes independently of production row helpers,
  including UTF-8, quoting/newlines, empty logs, absent scoring metadata and differing
  plan/result order. Numeric coverage exercises the renderer and runtime together.
- Independent source review found no regressions in numeric semantics, Qt sender and
  signal behavior, public widget attributes/layout, CSV ordering/eager evaluation,
  atomic writes, or weighted reaction-time aggregation.
- Repository precommit completed Ruff, compilation, audits and mypy (237 source files).
  The safe suite finished with 3,137 passed, five failed and 11 skipped. All five
  failures were Windows `PermissionError [WinError 5]` at the unchanged bundle-import
  directory rename (`core/project_bundle.py:454`). The skips require Windows symlink
  privileges. This is a completed but not fully passing precommit run.
- A serial rerun of the three affected files passed 48 tests and failed three different
  bundle-import cases; all five original failures passed. The original source from
  `69c078e`, selected via pytest's `pythonpath` while retaining the same workspace tests
  and temporary-path configuration, reproduced two rename failures (49 passed),
  including one identical case from that rerun. Original source/tests in the separate
  baseline archive passed all 51. The locking process is unknown. Review confirmed
  the cleanup adds no file handles and the bundle I/O implementation is unchanged;
  no retry or fallback was introduced to hide this existing intermittent failure.
- Original full-suite failures: `test_publishing_copies_only_declared_content_and_sanitizes_project`,
  `test_publisher_dry_run_validates_without_writing_bundle`,
  `test_library_bundle_uses_com3_and_preserves_source_port[bundle-None]`,
  `test_one_condition_keeps_modifier_baseline_and_source_unchanged`, and
  `test_masking_config_and_bundle_survive_source_deletion_and_relocation`.
- The user explicitly approved visible GUI tests with synthetic projects and isolated
  settings. The final selection passed all 42 cases. Its first run exposed two existing
  1120x720 layout failures; pristine commit `69c078e` reproduced both with scrollbar
  maxima of 1 and 13. Only those test sizes changed to the documented 1120x820 baseline
  (1180x860 expanded), retaining every assertion and all production layout code.
- Automatic approval policy blocked removal of the verified task-owned baseline archive
  with no reason beyond "blocked by policy". It remains outside the repository at
  `C:/Users/zcm58/.codex/tmp/fpvs-gui-baseline-73db68175a9e4882a75473feb381ff08`,
  including the baseline failure log. No further deletion attempts were made.
- Cleanup commit `8041b53` was fast-forward merged into the previous branch, `master`.
  The merged local branches `cleanup/behavior-preserving-audit`,
  `feature/ui-action-discovery` and `feature/ui-responsiveness` were deleted with
  `git branch -d` after verifying their tips were ancestors of master.
  `codex/experiment-library` was preserved because commit `59cee23` is unique and
  not patch-equivalent to master. Remote branches were not changed; nothing was pushed.
