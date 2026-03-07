# RunSpec Contract

`RunSpec` is the compiled execution plan for one FPVS condition run.

It stays intentionally separate from:

- editable project models in `ProjectFile`
- multi-condition session ordering in `SessionPlan`
- runtime execution results in `core.execution`

## Compile flow

```text
project.json -> ProjectFile -> compile_run_spec(...) -> RunSpec
project.json + session settings -> compile_session_plan(...) -> SessionPlan
SessionPlan -> runtime session flow -> engine.run_condition(RunSpec, ...)
```

## Why `RunSpec` is separate

- runtime should not inspect editable project state during playback
- engines should consume one neutral condition contract at a time
- all timing should be explicit before runtime starts
- future engine swaps should not require project schema churn
- multi-condition flow should remain above `RunSpec`, not inside it

## Timing model

All execution timing in `RunSpec` is represented in frames.

For v1:

- `frames_per_stimulus = refresh_hz / 6.0`
- `continuous`
  - `on_frames = frames_per_stimulus`
  - `off_frames = 0`
- `blank_50`
  - `on_frames = frames_per_stimulus / 2`
  - `off_frames = frames_per_stimulus / 2`
  - `frames_per_stimulus` must be even

Runtime and engines must consume these compiled frame counts directly. They do
not recompute protocol logic from `ProjectFile`.

## Main fields

### `DisplayRunSpec`

- refresh rate
- background color
- per-stimulus frame count
- on/off frame split
- duty cycle
- total frame count

### `ConditionRunSpec`

- condition identity and name
- template id
- instructions text
- fixed v1 protocol constants
- total oddball cycles
- total stimuli
- condition trigger code

### `StimulusEvent`

Each event contains:

- sequential event index
- role: `base` or `oddball`
- project-relative image path
- `on_start_frame`
- `on_frames`
- `off_frames`

### `FixationStyleSpec`

The style spec now contains everything runtime/engines need to render the
fixation task without consulting editable project models:

- default and target colors
- response keys
- cross size in pixels
- cross line width in pixels
- target duration in frames

### `FixationEvent`

Each fixation event contains a concrete target onset and duration in frames.

### `TriggerEvent`

Trigger events remain generic and frame-based. Runtime/engine execution observes
them now, while real serial I/O remains deferred behind the trigger backend
boundary.

## Export relationship

Runtime writes one `display_report.json` and one scored `fixation_events.csv`
next to each executed `RunSpec`.

- `display_report.json` reflects compatibility of the compiled frame timing
- `fixation_events.csv` preserves each compiled fixation event's frame window
  plus the realized hit/miss outcome

## Asset resolution

`RunSpec.stimulus_sequence[*].image_path` uses project-relative POSIX paths.

When a project root and preprocessing manifest are available, the compiler
resolves real source or derived asset paths from the manifest. Runtime preflight
verifies those files before launch, and the presentation engine resolves them
relative to the project root during playback.

## v1 scheduling policy

The compiler currently emits a deterministic schedule:

- oddball every 5th stimulus
- sorted image paths
- manifest-backed variant resolution when available
- simple round-robin image assignment
- deterministic fixation spacing from the configured per-sequence count and gap
  constraints
- a trigger event at frame 0 when a condition trigger code is present

`RunSpec` must remain single-condition even as execution/export behavior gets
richer around it.
