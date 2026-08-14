# Cross-Platform Experiment Test Mode

Status: Active

## Goal

Replace the source-only Linux experiment verification mode with a source-only,
cross-platform mode supported on both Windows and Linux. The mode must let developers
exercise the real compiled fullscreen PsychoPy session without requiring lab trigger
hardware, participant data entry, or connected-display refresh verification.

## User workflow

- In a non-packaged Windows or Linux run, Settings exposes `Experiment Test Mode`.
- Enabling it applies to the currently open document and subsequent project windows.
- Launch requires an explicit acknowledgement and uses reserved participant ID `0`.
- The launch uses logged null-trigger output, skips the Sophia/BioSemi recording gate,
  and skips the connected-display refresh query/measurement.
- Fullscreen presentation, compilation, asset preflight, frame schedules, condition and
  task flow, timing warmup/QC, and normal exports remain active.
- Packaged builds and unsupported operating systems do not expose or honor the mode.

## Boundaries

- Keep the preference in application settings and document launch state, not ProjectFile,
  RunSpec, or SessionPlan.
- Keep runtime policy explicit through LaunchSettings; do not reintroduce the retired
  runtime `test_mode` control field.
- Do not mutate authored trigger settings or display settings.
- Keep participant-facing acknowledgement and summaries in the GUI layer.

## Verification

- Unit tests cover explicit refresh-verification disabling and invalid launch settings.
- Non-Qt document tests cover unchanged authored triggers plus null-trigger launch
  overrides.
- Registered pytest-qt tests cover Windows/Linux availability, settings persistence,
  acknowledgement, participant-prompt replacement, launch wiring, and layout fit.
- Run GUI and runtime focused verification, repository precommit, and GitHub Actions on
  the feature branch and merged default branch.

## Assumptions

- "Cross-platform" means the two supported development hosts: Windows and Linux.
- The source-only guard remains a safety boundary so an installed lab build cannot
  silently bypass hardware and display checks.
