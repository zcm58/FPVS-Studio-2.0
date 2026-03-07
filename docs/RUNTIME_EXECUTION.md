# Runtime Execution

Phase 4 introduces the first real execution path from `SessionPlan` to PsychoPy.

## Ownership split

- core compiles neutral contracts
  - `ProjectFile`
  - `RunSpec`
  - `SessionPlan`
  - execution-result models in `core.execution`
- runtime owns execution orchestration
  - preflight
  - session flow
  - trigger backend wiring
  - fixation-response scoring
  - export writers
- engines own rendering/presentation
  - window lifecycle
  - text screens
  - frame-accurate playback
  - keyboard polling

## Session flow

The runtime worker now drives sessions like this:

```text
SessionPlan
  -> preflight every RunSpec
  -> create trigger backend
  -> engine.open_session(...)
  -> for each SessionEntry in order:
       -> engine.show_transition_screen(...)
       -> engine.run_condition(RunSpec, ...)
       -> runtime scores fixation responses
       -> runtime writes per-run artifacts
  -> engine.show_completion_screen(...)
  -> engine.close_session()
  -> runtime writes session artifacts
```

The engine never receives `ProjectFile`. It only receives one compiled
`RunSpec`, the project root for asset resolution, and runtime-only launch
options.

## PsychoPy engine

The PsychoPy implementation:

- keeps imports lazy inside `psychopy_engine.py`
- opens one `visual.Window` per launched session
- reuses that window across all runs in the `SessionPlan`
- shows transition/completion text screens
- preloads image stimuli before each condition
- executes the compiled frame schedule directly from `RunSpec`
- draws the fixation cross continuously and switches color on compiled
  `FixationEvent` windows
- polls response keys and escape
- records frame intervals and runtime metadata

## Trigger behavior

Serial trigger I/O is still deferred.

For this phase:

- runtime passes a logged trigger backend through the engine seam
- engine observes compiled `TriggerEvent` entries during playback
- trigger attempts are recorded with frame/time metadata
- default/test execution uses the null backend

This leaves a clear place to attach real on-flip serial emission later without
changing `RunSpec` or `SessionPlan`.

## Fixation logging

The engine captures raw response key presses.

Runtime then scores them against compiled `FixationEvent` windows and exports:

- one fixation-event log with hit/miss outcomes
- one raw/scored response log
- compiled fixation event timing preserved in the exported fixation rows

That keeps the scoring logic testable without requiring PsychoPy.

## Exports

Per session:

- `session_plan.json`
- `session_summary.json`
- `runtime_metadata.json`
- `conditions.csv`
- `events.csv`
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`
- `warnings.log`

Per run:

- `runspec.json`
- `run_summary.json`
- `runtime_metadata.json`
- `display_report.json`
  - a display-compatibility report derived from the compiled run timing
- `events.csv`
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`
- `warnings.log`

## Test mode

`test_mode` remains a runtime-only launch setting and is the only supported
launch mode in the current Phase 4 backend.

In the current v1 runtime it means:

- PsychoPy runs windowed instead of fullscreen
- trigger output stays on the logged null backend
- completion screens auto-dismiss quickly
- launch entry points reject `test_mode=False` until the non-test path is
  explicitly hardened

The rest of the compile, preflight, session flow, and export path still runs.

## Current deferrals

Still deferred after Phase 4:

- real serial-port trigger I/O
- GUI project editor
- advanced response-task variants beyond fixation
- more sophisticated balancing/counterbalancing beyond compiled `SessionPlan`
- non-PsychoPy presentation backends
