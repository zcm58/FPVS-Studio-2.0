# Production Runtime Mode

Status: Completed

## User Workflow

Launching an experiment from Home or the Run page uses the normal session runtime. The
application no longer labels or gates this supported path as `test_mode=True`.

## Behavior-Preservation Contract

Removing the mode seam must not change an authored or compiled experiment. In
particular, the change does not alter project data, session compilation, condition or
block order, stimulus frame schedules, base/oddball cadence, fixation realization,
response scoring, trigger events, fullscreen selection, display verification, timing
warmup, missed-frame thresholds, participant gates, exports, or the duration of the
completion screen.

The current active-use launch values that were previously selected indirectly by
`test_mode=True` become explicit runtime settings:

- fullscreen playback remains enabled by GUI launch callers;
- strict timing remains enabled;
- warmup timing misses remain report-only for GUI launches;
- the timing miss threshold remains four expected frame intervals for GUI launches;
- the timing warmup remains 240 frames;
- the completion screen remains visible for 0.5 seconds; and
- optional windowed engine sessions retain the existing 1280x720 default size.

Only mode labeling changes: new summaries use `run_mode="session"`, and the retained
backward-compatible `RuntimeMetadata.test_mode` export field is always `false`.
Previously written run/session artifacts remain readable.

## Boundaries

- Keep runtime-only settings out of `RunSpec` and `SessionPlan`.
- Do not change compilation, frame scheduling, fixation, trigger, or scoring code.
- Replace conditional presentation behavior with named runtime settings rather than a
  new production/test Boolean.
- Keep the `RuntimeMetadata.test_mode` field for v1 export compatibility; do not use it
  as control flow.
- Update GUI method names and user-facing copy so supported launches are described as
  experiments or sessions, not test-mode runs.

## Verification

- Launcher tests prove normal settings are accepted without a mode flag and that the
  engine-facing options preserve the active GUI launch policy.
- Runtime and engine tests prove summaries are session-mode, metadata is non-test, the
  completion timeout is unchanged, and window construction is unchanged.
- Existing compiler, runtime flow, fixation, trigger, refresh, and export tests remain
  unchanged in behavioral expectations except for corrected mode metadata.
- Run focused runtime, engine, GUI-safe, and docs verification, followed by repo
  precommit verification.
