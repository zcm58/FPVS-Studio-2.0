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
  -> verify active fullscreen resolution against the configured intended display
  -> if fixation accuracy and the participant tutorial are enabled:
       -> run the tutorial once, before the first condition-start screen
  -> for each SessionEntry in order:
       -> engine.show_transition_screen(..., continue_key="space")
       -> engine.run_condition(RunSpec, ...)
       -> if this completed a non-final block:
            -> engine.show_block_break_screen(...)
       -> runtime scores fixation responses
       -> when fixation accuracy task is enabled:
            -> engine.show_condition_feedback_screen(...)
       -> runtime writes per-run artifacts
  -> engine.show_completion_screen(...)
  -> engine.close_session()
  -> runtime writes session artifacts
  -> runtime appends logs/session_condition_history.csv
```

The engine never receives `ProjectFile`. It only receives one compiled
`RunSpec`, the project root for asset resolution, and runtime-only launch
options.

Preflight validates the compiled stimulus payload before playback. Image events require
existing project-relative files. Word events require non-empty text and do not require
filesystem assets. Unknown modalities, missing payload fields, or reused stimulus ids
with conflicting payloads fail before launch instead of falling back to image behavior.

## PsychoPy engine

The PsychoPy implementation:

- keeps imports lazy inside `psychopy_engine.py`
- opens one `visual.Window` per launched session
- reuses that window across all runs in the `SessionPlan`
- opens launched playback fullscreen on the default display
- reports the active window resolution so runtime can block configured visual-angle
  playback when the current display resolution differs from the intended test resolution
- shows Space-required condition-start screens and completion text screens; transition
  headings always use generic condition numbers while authored condition names stay in
  runtime artifacts
- runs fixation-only participant tutorial attempts when runtime asks for practice
- shows a dedicated manual inter-block break screen between non-final blocks
- preloads each condition's unique image or word stimuli before playback and releases
  condition-local resources when the condition ends
- executes the compiled frame schedule directly from `RunSpec`
- draws the fixation cross continuously and switches color on compiled
  `FixationEvent` windows
- polls response keys and escape
- records frame intervals and runtime metadata

## Trigger behavior

- runtime passes a logged trigger backend through the engine seam
- engine observes compiled `TriggerEvent` entries during playback
- the PsychoPy engine uses flip-locked scheduling with `window.callOnFlip(...)`, tying
  marker-write callbacks to the flip that presents the compiled frame
- trigger attempts are recorded with frame/time metadata, backend name, status, and
  failure message when applicable
- new FPVS Studio projects default to BioSemi-compatible serial output on `COM3`;
  condition starts use each condition's configured trigger code and every oddball onset
  uses project trigger code `55`
- the `oddball_onset` marker code is locked to `55`; a nonstandard oddball marker code
  is only valid when the project or `.fpvsconfig` explicitly records
  `allow_nonstandard_oddball_trigger_code=true` in response to user direction
- raw runtime launch settings can still disable serial output and use the logged null
  backend when `serial_enabled` is false
- serial-port execution writes single-byte marker codes to the configured COM port and
  baudrate

Project trigger settings such as COM port, baudrate, pulse width, reset code, and reset
delay are mapped into runtime-only launch options. They are not stored in `RunSpec` or
`SessionPlan`. The BioSemi serial backend writes exactly one byte per normal event with
`bytes([code])`, where event codes are `1` through `255`. Code `0` is reserved for
manual reset, and manual reset is disabled by default because the BioSemi USB Trigger
Interface auto-resets markers.

Configured serial failures do not silently fall back to null output. Missing `pyserial`,
COM open failures, and write failures surface as runtime errors before or during
playback depending on when they are discovered. A marker is recorded as `sent` only after
the backend write path succeeds; disabled/null output records `skipped_disabled`, and
backend send failures record `error` before the exception is raised.

These software checks do not prove physical display onset timing. Lab timing precision
still needs BioSemi/BDF and photodiode validation on the actual machine and display.

## Fixation logging

The engine captures raw response key presses.

Runtime then scores them against compiled `FixationEvent` windows and exports:

- one fixation-event log with hit/miss outcomes
- one raw/scored response log with hit/false-alarm classification
- one condition-level fixation summary (targets, hits, misses, false alarms,
  accuracy %, mean RT)
- compiled fixation event timing preserved in the exported fixation rows

That keeps the scoring logic testable without requiring PsychoPy.

Scoring semantics for the fixation accuracy task:

- response key: `space`
- response window: `1.0` second from fixation target onset
- first valid response in-window counts as the target hit
- responses outside open windows are false alarms
- mean RT is computed from hits only
- the optional participant tutorial runs once before the first condition when enabled
  in setup, and disabling it preserves the direct-to-condition launch flow

## Exports

Launch-time participant metadata:

- the GUI launch prompt collects Participant Number, Age, Sex, and Handedness by
  default for every project
- Sex accepts only `Female` or `Male`; Handedness accepts only `Right handed`,
  `Left handed`, or `Ambidextrous`
- Participant Number remains the required runtime identity and output-folder key
- Age, Sex, and Handedness are stored in `SessionExecutionSummary`,
  each `RunExecutionSummary`, the session-level `participant_metadata.csv`, and
  project-level `logs/session_condition_history.csv`

Project-level reporting index:

- `logs/session_condition_history.csv`
  - append-only one-row-per-condition-occurrence session history
  - includes participant number, age, sex, handedness, random order seed, run timing,
    block/order metadata, abort fields, fixation metrics, and block accuracy
  - used for reporting convenience; the detailed audit source remains the
    session/run artifacts under `runs/`

Per session:

- `session_plan.json`
- `session_summary.json`
- `runtime_metadata.json`
- `participant_metadata.csv`
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

Run and session `events.csv` exports include neutral stimulus columns:
`stimulus_modality`, `stimulus_id`, `stimulus_value`, `image_path`, and `text`.
`stimulus_value` is a spreadsheet convenience field derived from `image_path` for image
events and `text` for word events; role and frame timing columns stay unchanged.

Studio `.fpvsconfig` export is a separate summary/interchange file built from the editable
project, stimulus manifest, and optionally an existing completed session directory. A
completed `.fpvsconfig` preserves the session seed, realized condition order, per-run
stimulus shuffle seeds, trigger schedule, display geometry, and stimulus-generation
provenance so another lab can recreate the setup. It does not replace the authoritative
artifacts under `runs/`, and runtime does not consume `.fpvsconfig` during playback.

## Test mode

`test_mode` remains a runtime-only launch setting and is the only supported
launch mode in the current Phase 4 backend.

In the current v1 runtime it means:

- runtime launch still flows through the test-mode seam and test-mode metadata
- GUI launch currently fixes PsychoPy test-mode playback to fullscreen presentation
- session order is randomized within each block using the current random order seed
- every condition waits for the participant to press Space before playback starts
- trigger output follows the project's trigger settings; new projects default to
  BioSemi-compatible serial output on `COM3`, and oddball onset output is locked to
  marker code `55` unless the project records an explicit nonstandard-code override
- completion screens auto-dismiss quickly
- launch entry points reject `test_mode=False` until the non-test path is
  explicitly hardened

The rest of the compile, preflight, session flow, and export path still runs.

## Current deferrals

Still deferred after Phase 4:

- GUI project editor
- advanced response-task variants beyond fixation
- more sophisticated balancing/counterbalancing beyond compiled `SessionPlan`
- non-PsychoPy presentation backends

## BioSemi Hardware Checklist

Use this manual checklist when validating a real lab rig:

- connect the BioSemi USB Trigger Interface
- confirm the COM port in Windows Device Manager
- start ActiView
- send test values `1`, `2`, `4`, `8`, `16`, `32`, `64`, and `128`
- confirm ActiView displays the expected trigger/status values
- run one FPVS condition
- confirm `condition_start` and `oddball_onset` markers appear in the BDF/status channel
- compare trigger timing to a photodiode for at least one run when timing precision matters
