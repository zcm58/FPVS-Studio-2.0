# Randomized Session Order Run Log

## Summary

Make randomized condition order the fixed current workflow, protect against reusing
completed-session seeds, and add a project-level CSV log for condition-level run
reporting. The detailed `runs/` exports remain the audit source of truth; the new
`logs/session_condition_history.csv` is a compact reporting index.

## Implementation Scope

- Remove the visible `Randomize conditions within each block` checkbox from current
  GUI session surfaces while keeping `SessionSettings.randomize_conditions_per_block`
  enabled internally.
- Rename and clarify the session seed UI as the random order seed. The seed controls
  condition order within every block.
- Preserve in-memory seed randomization on project open without dirtying `project.json`.
- Generate and verify new seeds against completed, non-aborted prior sessions only.
  Aborted or incomplete launches do not permanently consume a seed.
- Add append-only `logs/session_condition_history.csv` with one row per condition
  occurrence in each block.
- Keep all new filesystem writes inside the active project root using existing path
  helpers.

## CSV Rows

Each row records:

- `logged_at_utc`, `project_id`, `project_name`
- `participant_number`, `session_id`, `session_seed`
- `session_started_at`, `session_finished_at`, `output_dir`
- `block_index`, `index_within_block`, `global_order_index`
- `condition_id`, `condition_name`, `run_id`
- `run_started_at`, `run_finished_at`, `completed_frames`
- `run_aborted`, `abort_reason`
- `total_targets`, `hit_count`, `miss_count`, `false_alarm_count`
- `accuracy_percent`, `mean_rt_ms`, `block_accuracy_percent`

## Verification Checklist

- Unit tests cover completed-session seed discovery, aborted/incomplete seed exclusion,
  unused seed generation, and condition-history CSV append behavior.
- GUI tests cover hidden randomization checkbox, random order seed wording, project-open
  seed randomization, `New Seed` skip behavior, and review wording.
- Docs are updated after implementation to describe the actual final behavior.
- Move this file to `docs/exec-plans/completed/` after verification.

## Completion Notes

- Current GUI surfaces no longer expose a randomization checkbox; condition order is
  always randomized within each block.
- `ProjectDocument` generates in-memory random order seeds on project open without
  dirtying `project.json`, skips seeds already used by completed sessions, and replaces
  a consumed active seed before compilation/launch.
- Runtime session export appends `logs/session_condition_history.csv` with one row per
  planned condition occurrence.
- Documentation now describes `runs/` as the detailed source of truth and the project
  log as a reporting index.

## Non-Goals

- Do not change `project.json` schema.
- Do not remove legacy session fields from persisted models.
- Do not replace the existing `runs/` detailed artifact bundle.
- Do not add participant demographics beyond the existing participant number.
