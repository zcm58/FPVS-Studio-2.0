# Participant Electrode Exclusion Launch Prompt

Status: Planned

## Summary

Add a launch-time administrator prompt for electrodes that were physically removed
from the EEG cap before recording. The prompt should appear after the user clicks
`Launch Experiment` and enters participant details, but before the BioSemi
recording confirmation dialog that requires typing `Confirm`.

The first implementation should capture per-participant excluded electrodes in FPVS
Studio and include that metadata in `.fpvsconfig` export so FPVS Toolbox can seed
its manual removed-electrode QC list automatically during project import.

## Current Context

- Launch UI lives in `src/fpvs_studio/gui/run_page.py`.
- `RunPage.launch_test_session()` currently:
  - validates launch readiness,
  - collects `ParticipantLaunchDetails` through `ParticipantNumberDialog`,
  - compiles the session,
  - updates the launch summary,
  - optionally opens `BioSemiRecordingConfirmationDialog`,
  - starts the runtime launch task.
- The required insertion point is after participant details are accepted and before
  `BioSemiRecordingConfirmationDialog` is shown.
- Participant metadata currently stores age, sex, and handedness in
  `fpvs_studio.core.execution.ParticipantMetadata`.
- Studio `.fpvsconfig` export lives in `src/fpvs_studio/core/project_config.py`.
  `ProjectConfigToolbox` already exports Toolbox-oriented `project_title`,
  `event_map`, and `oddball_trigger_code`.
- FPVS Toolbox import is prepared to consume per-participant removed-electrode
  metadata from top-level maps such as `manual_removed_electrodes` or
  participant-level fields such as `manual_removed_electrodes`,
  `removed_electrodes`, `excluded_electrodes`, or
  `physically_removed_electrodes`.

## User Workflow

1. The experiment administrator clicks `Launch Experiment`.
2. FPVS Studio shows the existing participant information dialog.
3. After valid participant information is entered, FPVS Studio shows a new
   electrode-exclusion prompt for that participant.
4. The prompt lets the administrator record electrodes that were physically
   removed or unplugged before recording.
5. The administrator can leave the list blank and continue.
6. If Sophia Mode is enabled, FPVS Studio then shows the existing recording
   confirmation dialog.
7. Runtime launch behavior remains unchanged after the confirmation gate.
8. Later `.fpvsconfig` export includes the participant electrode exclusion map so
   FPVS Toolbox can import it into manual removed-electrode mode.

## UX Requirements

- The prompt should be explicit that it is for electrodes physically removed from
  the cap before recording, not electrodes that merely "looked funny."
- The dialog should be compact and fast because it is in the launch path.
- The primary input can start as a comma-separated electrode list with examples
  such as `FT7, P9, Oz`.
- Include a clear `None removed` or blank-list path so administrators can continue
  without inventing entries.
- Normalize casing in the saved/exported metadata where possible, while preserving
  unknown labels rather than rejecting them unless validation has a strong reason to
  block launch.
- Cancellation should abort the launch before Sophia Mode confirmation and before the
  runtime task starts.
- If the participant already has saved excluded electrodes, the prompt should
  prefill them and allow edits.

## Data Contract

Prefer a small core-owned launch metadata model rather than keeping this only in
widgets. Candidate shape:

```json
{
  "manual_removed_electrodes": {
    "0007": ["FT7", "P9"]
  }
}
```

Implementation should decide whether this lives:

- in project-level launch/admin metadata under `logs/` or project state, and
- in exported `.fpvsconfig` under a top-level `manual_removed_electrodes` map,
  a `toolbox.manual_removed_electrodes` map, or participant-level entries.

The exported shape must remain easy for FPVS Toolbox to consume. If the config
schema changes, update `CONFIG_SCHEMA_VERSION` only if the current Pydantic model
cannot accept the new optional field compatibly.

## Implementation Boundary

- GUI owns the prompt and launch-path placement.
- Core owns validation/normalization models for participant electrode exclusions.
- Runtime should not use electrode exclusions for presentation behavior.
- PsychoPy engines should remain untouched.
- `RunSpec` and `SessionPlan` should not carry electrode exclusions because they do
  not affect stimulus timing or runtime rendering.
- `.fpvsconfig` export/import should serialize and validate the new optional
  metadata without copying runtime artifacts.
- The prompt should not alter Sophia Mode confirmation semantics.

## Suggested Files

- `src/fpvs_studio/gui/run_page.py`
  - Add a compact dialog and call it between `_collect_launch_participant_details()`
    and `_confirm_biosemi_recording_started()`.
- `src/fpvs_studio/core/models.py` or a small focused core helper
  - Add electrode-label parsing/normalization if not already present.
- `src/fpvs_studio/core/project_config.py`
  - Add optional manual removed-electrode metadata to `.fpvsconfig` export and
    import models.
- `src/fpvs_studio/runtime/session_export.py`
  - Consider whether compact participant summaries should include an audit column
    for removed electrodes. This is useful, but not required for Toolbox handoff if
    `.fpvsconfig` export is the source.
- `docs/GUI_WORKFLOW.md`
  - Document the new launch prompt after implementation.

## Tests

- GUI test in `tests/gui/test_run_page_launch.py`:
  - launch opens the electrode exclusion prompt after participant details,
  - cancelling it blocks runtime launch,
  - accepting it proceeds to Sophia Mode confirmation when that setting is enabled,
  - existing participant entries prefill the dialog.
- Core/project-config tests in `tests/unit/test_project_config.py`:
  - `.fpvsconfig` export includes participant electrode exclusions,
  - read/write round trip preserves the map,
  - import accepts blank lists and normalizes comma-separated labels.
- Runtime launcher tests should remain unchanged except for any explicit metadata
  plumbing needed to persist launch audit rows.

## Assumptions

- This feature records administrator knowledge; it is not an automatic electrode
  detector.
- A blank list is meaningful and can mean "reviewed, none removed."
- Electrode exclusions are participant-specific and should use the same participant
  number captured at launch.
- The first pass can use one comma-separated text field rather than a full electrode
  picker.
- FPVS Toolbox remains responsible for applying the imported list to preprocessing
  QC and interpolation.

## Open Questions

- Should Studio persist the list immediately when launch is cancelled later at the
  Sophia Mode confirmation step?
- Should exported `.fpvsconfig` include the map at top level, inside `toolbox`, or
  both for maximum downstream compatibility?
- Should participant summaries include a visible removed-electrodes audit column, or
  should the first implementation keep this only in config export metadata?
