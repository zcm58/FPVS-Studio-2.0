# Configurable FPVS Protocol

Status: Completed

## Goal

Let a project keep the current `6 Hz` base / every-5th-stimulus (`1.2 Hz`)
oddball protocol or select another frame-exact cadence, including `6 Hz` base with
an oddball every 6th stimulus (`1.0 Hz`). Keep the protocol project-wide in the
first implementation and preserve the current `146` oddball cycles per condition
default.

## Timing Contract

Persist the independent protocol inputs:

- `base_hz`: base stimulus presentation rate
- `oddball_every_n`: positive integer stimulus interval between oddballs

Derive rather than persist redundant values:

- `oddball_hz = base_hz / oddball_every_n`
- `frames_per_stimulus = refresh_hz / base_hz`
- `frames_per_oddball = frames_per_stimulus * oddball_every_n`

Compilation always resolves `frames_per_stimulus` to the nearest positive whole frame.
An exact division is reported as exact timing. A non-integral division, including
`59.94 / 6 = 9.99`, is accepted with a visible warning that reports the realized base
and oddball rates produced by the rounded frame count. A condition using 50% blank
timing still requires an even resolved `frames_per_stimulus` so its on/off halves are
integer frame counts. Because `oddball_every_n` is an integer, accepted oddballs always
land exactly on stimulus/frame boundaries.

For the motivating protocol:

| Refresh | Base cadence | Oddball cadence |
| --- | --- | --- |
| 60 Hz | 10 frames at 6 Hz | every 6th / 60 frames / 1 Hz |
| 120 Hz | 20 frames at 6 Hz | every 6th / 120 frames / 1 Hz |
| 240 Hz | 40 frames at 6 Hz | every 6th / 240 frames / 1 Hz |

Changing from every 5th to every 6th while retaining 146 oddball cycles increases
the condition from 730 to 876 stimuli and from about 121.67 to 146 seconds. The UI
must show this derived duration before launch rather than silently changing it.

## Refresh-Rate Policy

The refresh input remains modular and value-agnostic rather than being restricted to a
hard-coded monitor list. The guided control should make `60`, `120`, `144`, and `240 Hz`
easy to select while still accepting a positive custom value such as `59.94 Hz`.

- Exact ratios such as `144 / 6 = 24` compile without a warning.
- Approximate ratios such as `59.94 / 6 = 9.99` resolve to 10 frames per stimulus and
  compile with a persistent authoring/launch warning. The realized base is 5.994 Hz and
  the default every-5th oddball is 1.1988 Hz.
- The warning must distinguish protocol approximation from dropped or late frames.
  Whole-frame scheduling remains uniform; runtime timing QC continues to detect actual
  inconsistent flip timing.
- Values that cannot produce at least one frame per stimulus remain blocking errors.

## User Workflow

Add a compact `FPVS Timing` portion to the Experiment step next to the existing
monitor refresh setting:

- `Base rate`: a positive numeric control with immediate exact/approximate validation
  against the selected refresh rate and configured condition duty-cycle modes.
- `Oddball cadence`: an integer-backed choice formatted like
  `Every 6th stimulus (1.0 Hz)`.
- Read-only summary: frames per stimulus, frames between oddballs, stimuli per
  condition, and approximate condition duration.

Keep the current defaults selected for new and migrated projects. When a refresh,
base rate, oddball cadence, or condition duty-cycle changes, update the choices and
summary immediately. Preserve an existing valid value; if a change makes it invalid,
show a local blocking explanation and disable setup completion/launch rather than
silently substituting a different protocol.

Use project-facing labels that distinguish `Monitor refresh rate`, `Base presentation
rate`, and `Oddball rate`; do not call all three a display rate.

## Model and Persistence

- Add a core-owned `ProtocolSettings` model under `ProjectSettings`, defaulting to
  `base_hz=6.0` and `oddball_every_n=5`.
- Treat `oddball_hz` as a computed value. Do not store both the interval and rate as
  independently editable truth.
- Keep the built-in template as the source of authoring defaults, but stop using its
  fixed cadence as compiler/runtime truth after a project has been created.
- Load older projects that lack `protocol` with the current defaults and cover the
  additive compatibility path with a persisted-project regression test.
- Preserve protocol settings through project JSON, portable project bundles, and
  `.fpvsconfig` import/export. Add defaulted protocol fields to interchange schemas so
  existing configs continue to load.
- Decide separately whether condition-template profiles should snapshot protocol
  settings in the first release; project correctness must not depend on that optional
  convenience.

## Core and Runtime Implementation

1. Centralize protocol arithmetic and validation in core. Return frame counts and
   user-facing incompatibility reasons from one public helper.
2. Replace compiler, selected-condition validation, fixation guidance, repeat
   guidance, and project validation reads of `TemplateSpec.base_hz` /
   `TemplateSpec.oddball_every_n` with `ProjectSettings.protocol`.
3. Compile the chosen values into the existing `ConditionRunSpec` fields. Continue
   representing every event and duration in frames.
4. Preserve scheduling, seed behavior, stimulus-pool balancing, fixation realization,
   triggers, session randomization, and asset resolution. Only cadence-derived counts
   and durations change.
5. Keep runtime preflight as an independent defense: recompute compatibility from the
   compiled `RunSpec` and reject inconsistent frame counts before PsychoPy launch.

`RunSpec` already carries `base_hz`, `oddball_every_n`, and `oddball_hz`, and runtime
preflight already validates `RunSpec.condition.base_hz` against compiled frame counts.
The main work is therefore editable-model ownership, replacing template lookups, GUI
binding, and compatibility coverage rather than an engine redesign.

## GUI Implementation

- Add a thin model-bound timing editor and a `ProjectDocument.update_protocol_settings`
  method; keep all compatibility calculations in core.
- Fit the editor within the existing three-column Experiment card at `1120x720`
  without required scrolling or clipping. Rebalance the Display column or use a compact
  summary rather than adding a fourth full-width section.
- Update Review, Home readiness, and launch validation text to include the selected
  base/oddball rates when useful.
- Apply the refresh-rate policy consistently to Setup, bundle-import display
  review, template-profile editing, and any other refresh editor.
- Keep validation non-blocking while editing but block `Next` and launch when the
  combination is invalid.

## Verification

- Model/persistence tests:
  - defaults remain 6 Hz / every 5th / 1.2 Hz;
  - existing project JSON without protocol fields loads with those defaults;
  - project config and bundle round trips preserve configured protocol values.
- Compiler/session tests:
  - 6 Hz / every 6th compiles to a 1 Hz oddball cadence at 60, 120, and 240 Hz;
  - stimulus and trigger onsets use the expected integer frame steps;
  - fixed seeds and role-pool balancing remain deterministic;
  - approximate base/refresh pairs compile to the documented nearest frame count;
  - impossible sub-frame rates and odd-frame 50% blank pairs are rejected.
- Validation/preflight tests:
  - editable validation and runtime preflight agree on accepted combinations;
  - tampered or inconsistent compiled frame counts cannot launch;
  - 144 Hz is exact and 59.94 Hz is accepted with realized-rate warnings.
- Registered pytest-qt coverage in `test_setup_experiment_display.py`:
  - controls bind and persist;
  - derived 1 Hz/frame/duration text updates immediately;
  - invalid combinations expose full, actionable text and block progression;
  - the Experiment step remains unclipped and unscrolled at `1120x720` with longest
    realistic labels and validation states.
- Local verification:
  - `./scripts/verify.ps1 -Scope compiler -Tier focused`
  - `./scripts/verify.ps1 -Scope gui -Tier focused`
  - `./scripts/verify.ps1 -Scope repo -Tier precommit` after the cross-layer change
  - visible manual smoke of the Experiment step and launch readiness; Qt execution
    remains CI-owned unless a safe visible local run is explicitly approved.

## Initial Scope Exclusions

- Per-condition base or oddball rates
- Arbitrary waveform or sinusoidal contrast modulation
- Automatic protocol substitution when the display is incompatible
- A redesign of condition length; the existing oddball-cycle count remains authoritative
- PsychoPy or runtime recomputation from editable project state

## Outcome

Implemented project-wide editable base Hz and integer oddball cadence, nearest
whole-frame compilation, exact 144 Hz support, accepted 59.94 Hz timing with realized
rate warnings, Setup/Home/Run notification UX, project/config/bundle persistence, and
registered GUI plus backend coverage. Focused verification and the repository precommit
gate passed; registered Qt execution remains CI-owned.
