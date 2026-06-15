# Compact Versus Full Run Export Mode

Status: Completed

## Summary

Add an app-level Settings toggle that lets users choose whether participant launches
write the full detailed `runs/` artifact tree or only compact project-level summary
exports.

## User Workflow

Users open `File > Settings...` and choose the run export mode:

- full exports, the current default, keep writing the detailed `runs/<participant>/`
  session and per-condition artifacts
- compact exports skip detailed run/session artifact folders and update the compact
  project-level reporting files under `logs/`

The manual `File > Export Group Summary...` workflow remains based on the participant
summary rows generated from project-level history.

## Implementation Boundary

- Store the choice as an app-level `QSettings` preference, not in `ProjectFile`,
  `RunSpec`, or `SessionPlan`.
- Thread the preference into runtime through `LaunchSettings`.
- Preserve full export as the default.
- In compact mode, keep runtime execution, scoring, trigger handling, condition
  feedback, and session history rows unchanged.
- Do not create the detailed `runs/` output folder in compact mode.
- Keep duplicate-participant and unused-seed checks aware of compact sessions by
  reading project-level history when detailed session summaries are absent.

## Tests

- Runtime tests for full default behavior and compact summary-only behavior.
- Participant-history tests for compact history rows.
- pytest-qt Settings tests for displaying and persisting the app-level toggle.
- GUI launch tests confirming the persisted setting reaches `LaunchSettings`.

## Assumptions

- Compact mode may still write small project-level `logs/` CSV/XLSX files because they
  are the source for participant and group summaries.
- Detailed run artifacts remain available by switching the app setting back to full
  before launch.
