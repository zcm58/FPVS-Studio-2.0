# Display Refresh Detection and Approved Rates

Status: Completed

## Goal

Replace free-form monitor refresh editing with an approved-rate selector and add a
one-click PsychoPy measurement workflow. Prevent setup progression and runtime launch
from trusting a declared refresh rate that has not been checked against the connected
presentation display.

## User Workflow

- The Experiment step offers `59.94`, `60`, `120`, `144`, and `240 Hz` in a dropdown.
- `Detect My Refresh Rate` opens a temporary fullscreen PsychoPy probe on the default
  presentation display, measures actual frame timing, chooses the nearest approved
  rate within tolerance, applies it, and reports both measured and applied values.
- Detection runs away from the UI thread on the existing persistent presentation
  worker. The button exposes busy, success, unsupported-rate, unavailable, and error
  states without letting worker code touch widgets.
- The Experiment step requires a successful measurement before `Next`. Manually
  changing the selected rate invalidates the prior measurement.
- Runtime preflight independently measures once per session and blocks launch when
  the configured rate materially differs from the connected display or measurement
  cannot produce a stable result.

## Boundaries

- Keep the approved-rate list and rate-matching arithmetic in core validation.
- Keep PsychoPy imports lazy and confined to `src/fpvs_studio/engines/`.
- Add a neutral measurement method to the presentation-engine boundary.
- Keep measurement state machine-specific and transient; persist only the approved
  project target already owned by `DisplaySettings.preferred_refresh_hz`.
- Do not alter compiled frame schedules, session randomization, fixation realization,
  triggers, stimulus assets, or runtime export formats.
- Preserve legacy project loading. Unsupported persisted values remain visible and
  blocking until the user selects or detects an approved rate; do not silently coerce.

## Verification

- Core unit tests cover the approved list, nearest-rate selection, tolerance, and
  rejection of unsupported authored rates.
- Engine unit tests cover PsychoPy measurement success, unstable results, window
  options, and guaranteed probe-window cleanup.
- Runtime unit tests cover one measurement per session, accepted measured drift,
  mismatch blocking, and unavailable measurement blocking.
- Registered pytest-qt coverage covers dropdown values, required verification,
  busy/success/error states, measurement invalidation, 144 Hz exact timing, 59.94 Hz
  warning timing, and no clipping at `1120x720`. PsychoPy and progress tasks are
  monkeypatched; Qt execution remains CI-owned unless explicitly approved locally.
- Run focused core, engine, runtime, GUI, and docs verification, then repository
  precommit because the change crosses shared boundaries.

## Outcome

Implemented the approved-rate selector, transient setup verification, asynchronous
PsychoPy fullscreen measurement, nearest-approved application, unsupported and failure
states, and unconditional launch-time remeasurement. Core, compiler, engine, runtime,
project-I/O, docs, GUI-safe, and repository precommit verification passed. Registered
pytest-qt execution remains CI-owned.
