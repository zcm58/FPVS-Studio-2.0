# Fixation Task Accuracy Excel Export

Status: Completed

## Summary

Rename the fixation-results surface from `Fixation Cross Data` to the more accurate
`Fixation Task Accuracy`, and let researchers export the currently displayed pooled
results to a user-selected Excel workbook without changing project data.

## User Workflow

- Open `View > Fixation Task Accuracy...` for the active project's pooled fixation-task
  results.
- Choose `Export Excel...`, select a destination with the native save dialog, and keep
  the dialog responsive while the workbook is written in the background.
- Treat save-dialog cancellation as a no-op. Report export success or failure in the
  dialog without discarding already loaded results.

## Workbook Contract

- Export one flat, machine-readable worksheet named `Fixation Task Accuracy` with a
  single header row, one overall record, and one record per displayed condition.
- Keep counts, accuracy, and reaction-time values numeric; place units in headers. Store
  identifiers and condition names as literal text even when they resemble formulas.
- Apply an auto-filter across the full populated table and center every populated cell
  horizontally and vertically.
- Preserve Excel's default colors and fills. Use only usability formatting that does
  not encode data, such as sensible column widths, number formats, and a frozen header.
- Append `.xlsx` when the selected filename does not already end in `.xlsx`; do not
  replace another suffix in the selected name.

## Implementation Boundary

- Keep aggregation in the existing GUI-neutral fixation reporting service. The dialog
  exports its already loaded typed summary and does not reparse logs.
- Use the repository's existing runtime Excel dependency and write only to the explicit
  path chosen by the user. Do not modify project logs or add a working-directory
  fallback.
- Run the write through the existing GUI background-task pattern. Loading and export
  are mutually exclusive, and project handoff or application shutdown must not destroy
  an active worker.
- Keep internal module and object names stable where renaming them would add churn; the
  requested terminology change applies to the user-facing GUI and current workflow
  documentation.

## Tests And Acceptance

- Runtime unit tests inspect the generated workbook for exact rows, numeric cells,
  filter range, centered alignment, default fills, sheet name, and suffix handling.
- Registered pytest-qt coverage checks renamed labels, export-button enabled states,
  save-dialog cancellation and selected paths, background success and recoverable
  failure, and the busy lifecycle guard.
- The dialog continues to fit its documented `720x480` minimum without clipping.
- Safe focused verification and repository precommit checks pass. Registered Qt
  execution remains CI-owned unless a safe visible local run is approved.

## Non-Goals

No scoring change, new source data, charts, custom workbook color theme, participant
drill-down, CSV export, automatic overwrite policy, or change to existing session/group
export schemas is included.

## Completion

Completed on 2026-08-28. The implementation renamed the user-facing view, added a
cancel-safe native save workflow and background workbook writer, preserved loaded data
through export failures, and extended project-handoff guards across both load and export
workers. The workbook uses a flat filtered table with centered, wrapped literal text,
typed numeric metrics, default colors and fills, readable sizing, and collision-safe
suffix appending. Runtime, GUI-safe, docs, and repository precommit verification passed;
registered pytest-qt execution and the visible minimum-size smoke remain CI/release
checks under repository policy.

## Verification

```powershell
./scripts/verify.ps1 -Scope runtime -Tier focused
./scripts/verify.ps1 -Scope gui -Tier focused
./scripts/verify.ps1 -Scope docs -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```
