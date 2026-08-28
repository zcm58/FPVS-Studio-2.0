# Fixation Cross Data View

Status: Completed

## Summary

Add a `View` menu between `File` and `Tools`. Its first action,
`Fixation Cross Data...`, opens a compact read-only view of the active project's pooled
fixation-task accuracy and reaction-time results.

## User Workflow

- Load results in the background from the active project and show overall weighted
  accuracy, hit-weighted mean reaction time, and included participant-session counts.
- Show a condition table with included sessions, hits/targets, and pooled weighted
  accuracy so condition-level differences are easy to compare.
- Treat missing or zero-target history as a normal `No fixation data yet` state. Show
  unreadable or malformed history as a recoverable error without changing project data.

## Data And Metric Contract

- Read `logs/session_condition_history.csv`; do not depend on detailed `runs/` folders
  or rewrite participant-summary files when the view opens.
- Match the existing group-summary inclusion rule: omit participant IDs `0` and `00`,
  and exclude an entire participant session when any session/run row is aborted.
  Multiple included sessions for one participant remain separate contributions.
- Overall and per-condition weighted accuracy is
  `100 * sum(hit_count) / sum(total_targets)`. False alarms remain separately scored and
  do not reduce this established accuracy metric.
- Overall mean reaction time is
  `sum(mean_rt_ms * hit_count) / sum(hit_count)` over rows with hits. A zero denominator
  displays `N/A`, not `0`.
- Group condition rows by stable `condition_id` and display the latest nonblank logged
  name so renamed conditions do not split their history.

## Implementation Boundary

- Add a small GUI-neutral runtime reporting service that returns typed overall and
  per-condition summaries while sharing the existing export inclusion and weighting
  semantics. GUI widgets must not parse logs or own aggregation logic.
- Expose the query through `ProjectDocument.project_root`, resolving the log with
  `core.paths.logs_dir`; add no file picker, working-directory fallback, or writes.
- Add a focused dialog using shared GUI components and the existing background-task
  pattern. Use a `720x480` minimum and `800x520` default; long condition names must wrap
  or expose their full value by tooltip.
- Wire the action in `StudioMainWindow`, preserve menu order `File`, `View`, `Tools`, and
  disable it with other project actions during bundle processing.
- Preserve runtime scoring, CSV/XLSX schemas, `File > Export Group Summary...`, and both
  run-export modes. Update the focused GUI/runtime workflow docs during implementation.

## Tests And Acceptance

- Runtime unit tests cover unequal target/hit weighting, repeated runs, condition IDs
  and renamed labels, multiple sessions per participant, admin/aborted exclusions,
  zero targets/hits, missing history, malformed history, and active-project isolation.
- Registered pytest-qt coverage checks menu/action wiring plus loading, populated,
  empty, and error states; it also verifies no clipping at `720x480` with a realistic
  long condition name. Update existing exact menu-order assertions and
  `tests/qt_test_files.txt`.
- Manual smoke: open a populated project, choose `View > Fixation Cross Data...`, verify
  the overall values against the project summary and the condition rows against
  `session_condition_history.csv`, then repeat with a project that has no sessions.

## Non-Goals

No inferential statistics, charts, participant drill-down, inclusion editing, live
monitoring, new export format, or fixation-scoring change is included in this first view.

## Completion

Completed on 2026-08-28. The implementation added the GUI-neutral read-only reporting
service, the background-loaded dialog and `View` menu action, project-handoff protection
while its worker is active, current workflow/architecture documentation, focused runtime
tests, and registered pytest-qt coverage for all dialog states and minimum-size layout.
Safe local verification passed; registered Qt execution and the visible smoke path remain
CI/release checks under repository policy.

## Verification

```powershell
./scripts/verify.ps1 -Scope runtime -Tier focused
./scripts/verify.ps1 -Scope gui -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

Run registered Qt coverage only when a safe visible `full` run is explicitly approved.
