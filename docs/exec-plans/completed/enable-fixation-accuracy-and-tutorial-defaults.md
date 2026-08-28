# Enable Fixation Accuracy And Tutorial Defaults

Status: Completed 2026-08-28

## Summary

Enable the fixation color-change task, its response-accuracy scoring, and the participant
tutorial by default for new FPVS Studio projects. Migrate existing project files once so
projects created under earlier schemas receive the same enabled state without making the
settings impossible to turn off afterward.

## User Workflow

- A newly created project starts with fixation color changes, fixation-task accuracy,
  and the participant tutorial enabled.
- Opening a schema `1.0.0`, `1.1.0`, or `1.2.0` project enables all three settings in
  memory through the normal project loader.
- Loading alone does not rewrite `project.json`. The next ordinary save persists the
  current schema and the migrated values.
- After migration, users may disable accuracy or the tutorial and save that choice; a
  current-schema project must not silently turn either setting back on.

## Persisted Contract

- Advance only the editable `ProjectFile` schema to `1.3.0`. Keep `RunSpec`,
  `SessionPlan`, execution-result, project-config, and bundle-manifest schema versions
  unchanged unless their own serialized shape changes.
- Set `FixationTaskSettings.enabled`, `accuracy_task_enabled`, and
  `participant_tutorial_enabled` defaults to `true`.
- During project migration, set those three booleans to `true` while preserving target
  counts, timing, colors, response keys, presentation settings, and all other authored
  state. The sole compatibility repair is changing a legacy zero target duration to the
  current 300 ms default because an enabled fixation task requires a positive duration.
- Preserve explicit values in a current `1.3.0` project. An explicitly selected custom
  condition-template profile may still override defaults during new-project creation.

## Boundaries

- Use the existing `core.migrations` and `core.serialization` project-loading seam.
- Do not scan the configured FPVS Studio root, rewrite unopened projects, or introduce
  a working-directory or hard-coded path fallback.
- Do not change fixation scheduling, scoring, tutorial runtime flow, or compiled schema
  versions.

## Tests And Acceptance

- Model and project-service tests cover the new defaults for direct and scaffolded new
  projects.
- Migration tests cover explicit disabled values in schemas `1.0.0`, `1.1.0`, and
  `1.2.0`, source-payload immutability, unchanged unrelated settings, and the `1.3.0`
  result.
- A save/reload test proves a user can disable accuracy/tutorial after migration and
  retain that choice in a current-schema project.
- Project I/O, core, docs, and repository precommit verification pass.

## Non-Goals

No target-count migration, schedule change beyond the required zero-duration repair,
automatic bulk disk rewrite, tutorial-flow redesign, or forced re-enablement on every
load is included.

## Verification

```powershell
./scripts/verify.ps1 -Scope core -Tier focused
./scripts/verify.ps1 -Scope project-io -Tier focused
./scripts/verify.ps1 -Scope docs -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

## Completion

Implemented the default changes and the one-time `ProjectFile` 1.3 migration. Project
schema versioning is isolated from unchanged persisted contracts, legacy disabled
projects with a zero target duration receive the required 300 ms compatibility repair,
and current-schema opt-outs remain stable. Core, project-I/O, documentation, and
repository precommit verification cover the completed behavior.
