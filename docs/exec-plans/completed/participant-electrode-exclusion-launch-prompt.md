# Participant Electrode Exclusion Launch Prompt

Status: Completed

## Summary

Add an optional text field to the existing launch-time participant-information dialog
for electrodes that were physically removed from the EEG cap before recording. Persist
the normalized list per participant in `project.json` so a later FPVS Toolbox integration
can seed its manual removed-electrode QC list objectively.

## Completion

- Added the optional electrode field to the existing participant launch dialog with
  returning-participant prefill and an explicit physical-removal tooltip.
- Added the optional per-participant `manual_removed_electrodes` map to `ProjectFile`;
  existing projects default to an empty map, and accepted blank entries persist as an
  empty list.
- Added stable uppercase, trim, separator, and duplicate normalization while preserving
  unknown electrode labels.
- Persisted accepted launch entries to the active project's `project.json` before
  compilation and Sophia Mode confirmation, while keeping dialog cancellation
  side-effect free.
- Kept runtime, engine, `RunSpec`, `SessionPlan`, and `.fpvsconfig` contracts unchanged.

Verification completed with core, GUI-safe, project-I/O, and docs focused scopes plus
the repository precommit tier (359 safe unit tests, Ruff, compilation, mypy, repository
audits, and docs hygiene). Registered pytest-qt coverage was added to the existing launch
module and remains CI-owned under the repository's Qt policy.

## Current Context

- Launch UI lives in `src/fpvs_studio/gui/run_page.py`.
- `RunPage.launch_session()` currently:
  - validates launch readiness,
  - collects `ParticipantLaunchDetails` through `ParticipantNumberDialog`,
  - compiles the session,
  - updates the launch summary,
  - optionally opens `BioSemiRecordingConfirmationDialog`,
  - starts the runtime launch task.
- The new field belongs in `ParticipantNumberDialog`, so all launch-time participant
  details remain one quick administrator step.
- Participant metadata currently stores age, sex, and handedness in
  `fpvs_studio.core.execution.ParticipantMetadata`.
- Editable persisted project state lives in `fpvs_studio.core.models.ProjectFile` and
  is saved through the GUI document service.

## User Workflow

1. The experiment administrator clicks `Launch Experiment`.
2. FPVS Studio shows the existing participant information dialog.
3. The same dialog includes `Input manually removed electrodes (optional)` and lets
   the administrator enter electrodes that were physically removed or unplugged.
4. The administrator can leave the list blank and continue.
5. Accepting the dialog stores the participant-specific list in `project.json` before
   later launch gates run.
6. If Sophia Mode is enabled, FPVS Studio then shows the existing recording
   confirmation dialog.
7. Runtime launch behavior remains unchanged after the confirmation gate.
8. A later FPVS Toolbox integration can read the persisted project map and add the
   entries to Toolbox manual electrode exclusions during processing.

## UX Requirements

- The prompt should be explicit that it is for electrodes physically removed from
  the cap before recording, not electrodes that merely "looked funny."
- The existing participant dialog should remain compact and fast because it is in the
  launch path.
- The primary input can start as a comma-separated electrode list with examples
  such as `FT7, P9, Oz`.
- The text box must display `Input manually removed electrodes (optional)` and accept
  a blank list without requiring a separate `None removed` control.
- Normalize casing in the saved/exported metadata where possible, while preserving
  unknown labels rather than rejecting them unless validation has a strong reason to
  block launch.
- Cancelling the participant dialog should remain side-effect free and abort before
  Sophia Mode confirmation and runtime startup.
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

Add the optional top-level map to `ProjectFile`, defaulting to `{}` so existing projects
load unchanged. Keys use the accepted participant-number string and values use stable,
de-duplicated uppercase labels. An explicit empty list means the administrator reviewed
the field and reported none removed.

## Implementation Boundary

- GUI owns the field and launch-path placement.
- Core owns validation/normalization models for participant electrode exclusions.
- The GUI document service owns persisting accepted participant entries to the active
  project's `project.json`.
- Runtime should not use electrode exclusions for presentation behavior.
- PsychoPy engines should remain untouched.
- `RunSpec` and `SessionPlan` should not carry electrode exclusions because they do
  not affect stimulus timing or runtime rendering.
- `.fpvsconfig` export/import remains unchanged in this implementation; it is the later
  FPVS Toolbox handoff seam.
- The prompt should not alter Sophia Mode confirmation semantics.

## Suggested Files

- `src/fpvs_studio/gui/run_page.py`
  - Add the optional field to `ParticipantNumberDialog`, prefill existing participant
    entries, and persist accepted details before later launch gates.
- `src/fpvs_studio/core/models.py` or a small focused core helper
  - Add electrode-label parsing/normalization if not already present.
- `src/fpvs_studio/gui/document.py`
  - Update and save the active project map through the existing validated document
    mutation seam.
- `docs/GUI_WORKFLOW.md`
  - Document the new launch prompt after implementation.

## Tests

- GUI test in `tests/gui/test_run_page_launch.py`:
  - the participant dialog exposes the required optional input without clipping,
  - cancelling remains side-effect free,
  - accepting persists normalized values and proceeds to Sophia Mode confirmation,
  - existing participant entries prefill the dialog.
- Core/model tests in `tests/unit/test_models.py` and document tests:
  - project JSON round trip preserves the participant map,
  - parsing accepts blank, comma-, semicolon-, and line-separated labels,
  - casing and duplicates normalize predictably.
- Runtime launcher tests should remain unchanged except for any explicit metadata
  plumbing needed to persist launch audit rows.

## Assumptions

- This feature records administrator knowledge; it is not an automatic electrode
  detector.
- A blank list is meaningful and can mean "reviewed, none removed."
- Electrode exclusions are participant-specific and should use the same participant
  number captured at launch.
- The first pass uses one text field rather than a full electrode picker.
- FPVS Toolbox remains responsible for applying the imported list to preprocessing
  QC and interpolation.

## Deferred Work

- Decide the FPVS Toolbox `.fpvsconfig` export/import shape when that integration is
  implemented.
- Decide whether participant summary exports should expose a removed-electrodes audit
  column.
