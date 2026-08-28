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
  -> read the platform-native primary/default mode and verify PsychoPy frame stability once
  -> compare the approved exact mode to every compiled refresh target
  -> create trigger backend
  -> engine.open_session(...)
  -> verify active fullscreen resolution against the configured intended display
  -> if fixation accuracy and the participant tutorial are enabled:
       -> run the tutorial once, before the first condition-start screen
  -> for each SessionEntry in order:
       -> execute compiled pre-condition task modules, if any
       -> engine.show_transition_screen(..., continue_key="space")
       -> engine.run_condition(RunSpec, ...)
            -> estimate condition memory and evaluate the pre-upload RAM/DXGI gate
            -> create, prime, and GPU-synchronize exactly one condition cache
            -> evaluate the post-upload RAM/DXGI gate
            -> complete technical warmup, using its final configured frames for the
               fixation-only lead-in
            -> reset input and run-relative timing
            -> present stream frame zero and its condition trigger together
            -> end the last compiled frame with a neutral, trigger-free offset flip
            -> release the condition cache before returning
       -> execute compiled post-condition task modules, if any
       -> if this completed a non-final block:
            -> engine.show_block_break_screen(...)
       -> runtime scores fixation responses
       -> when fixation accuracy task is enabled:
            -> engine.show_condition_feedback_screen(...)
       -> runtime writes per-run artifacts when full export mode is enabled
  -> engine.show_completion_screen(...)
  -> engine.close_session()
  -> runtime writes session artifacts when full export mode is enabled
  -> runtime appends logs/session_condition_history.csv
  -> runtime regenerates logs/participant_summary.xlsx and logs/participant_summary.csv
```

The engine never receives `ProjectFile`. It only receives one compiled
`RunSpec`, the project root for asset resolution, and runtime-only launch
options.

Modular task clocks are separate from the FPVS clock. Runtime expands module repeats
outside step repeats, renders questionnaire questions one at a time, evaluates bounded
branch rules, validates raw engine input, applies authored retry policies, and records
module repetition, step repetition, and attempt indices separately. A required timeout
or invalid response ends the task flow after its configured attempts. Model validation
and session preflight reject no-duplicate repeat plans unless their fixed required
selection count can be satisfied from distinct choice-grid, questionnaire-option, or
rating-tick pools across every module and step repetition; runtime repeats this check
before rendering as a defense against unvalidated compiled copies. A pre-task or
post-pre-task transition abort creates a start-aborted run result containing every
response collected so far. A post-task abort leaves a successfully completed FPVS run
marked complete while recording the separate task-flow abort stage and ending the
session.

Task assets are preflighted as contained project-relative paths before participant
screens open. Routine preflight checks existence; deep preflight also decodes task
images. The selected engine must advertise the neutral modular-task rendering seam.

Default launch settings require connected-display refresh verification. Preflight first
asks a runtime-owned platform adapter for the primary/default display's configured
native mode, then asks the engine for one fullscreen observation per session. Windows
continues to use `QueryDisplayConfig`; its exact fraction is authoritative for approved-
rate selection, so `60000/1001` maps to `59.94 Hz` while `60/1` maps to `60 Hz`.
KDE Linux uses `kscreen-doctor --json` to select the enabled priority output, resolve
its current mode, and read its VRR policy. Linux X11 uses the active primary XRandR
mode. Floating Linux mode metadata maps to the nearest approved FPVS rate only within
the existing measurement tolerance. PsychoPy validates stable delivery and material
agreement on both platforms; it does not replace the native query. Missing or ambiguous
native modes, unsupported Wayland compositors, Windows Dynamic Refresh Rate, KDE
Adaptive Sync/VRR, unstable observation, or a mode-versus-compiled mismatch block
launch. Native queries are read-only and do not alter display settings. This check is
independent of the Setup Wizard's one-click detection, so Home and Run cannot bypass
it, and verification does not modify the compiled frame schedule.

Preflight validates the compiled stimulus payload before playback. Routine participant
launches require image events to reference existing project-relative files, while full
image decoding is reserved for preprocessing/manual deep preflight and engine stimulus
preparation. Word events require non-empty text and do not require filesystem assets.
Unknown modalities, missing payload fields, missing image files, or reused stimulus ids
with conflicting payloads fail before launch instead of falling back to image behavior.

## PsychoPy engine

The PsychoPy implementation:

- keeps imports lazy inside `psychopy_engine.py`
- measures actual refresh with a temporary fullscreen `visual.Window` and
  `getActualFrameRate(...)`, then closes that probe window before session playback opens
- opens one `visual.Window` per launched session
- reuses that window across all runs in the `SessionPlan`
- opens launched playback fullscreen on the default display
- supplies the selected Pyglet screen's native pixel dimensions to both fullscreen
  window constructors instead of inheriting PsychoPy's `800x600` default request;
  detection failure is warning-only because PsychoPy still resolves the actual size
- reports the active window resolution so runtime can block configured visual-angle
  playback when the current display resolution differs from the intended test resolution
- shows Space-required condition-start screens and one final `All done!` / participant-
  thanks screen after every condition has completed; transition headings always use
  generic `Condition X of Y` numbers while authored condition names stay in runtime
  artifacts
- runs fixation-only participant tutorial attempts when runtime asks for practice
- shows a dedicated manual inter-block break screen between non-final blocks
- renders runtime-resolved modular instruction, study, image/text choice-grid,
  questionnaire, raw-key, and fixed-duration feedback screens outside FPVS timing
- uses one stable Arial font for modular task text, honors exact calibrated geometry or
  runtime-created responsive grids, and resolves task images through the contained
  project-path helper before creating stimuli
- starts each task response clock and clears carried keyboard events on the first task
  flip; mouse responses return stable item ids, coordinates, button, and reaction time
- ignores all non-Escape keys on fixed-duration feedback screens so authored durations
  cannot be skipped
- preloads each condition's unique image or word render variants before playback,
  explicitly primes both fixation colors, waits for queued GPU work once, and releases
  condition-local resources before the next condition
- deletes condition-owned textures, masks, PBOs, and legacy display lists, then waits on
  a post-delete `glFinish()` before the next condition may prepare its cache
- verifies production graphics readiness before and after upload using renderer strings,
  conservative unique-image estimates, Windows DXGI budgets, and physical-RAM headroom;
  software renderers and measured insufficient memory block frame zero, while missing or
  ambiguous telemetry proceeds with an exported `unverified` warning
- records readiness, renderer, memory/headroom, synchronization, and cleanup diagnostics
  in `RuntimeMetadata`
- prepares every unique resolved render identity before playback, including runtime
  mirrors/rotation, word height/color/position, and native rectangular image geometry
- performs `cover` cropping centrally in memory during preparation without creating
  derived files
- renders the compiled default-color fixation cross for the exact pre-stream lead-in
  frame count, emits no trigger or task response during that phase, then resets the run
  clock before stream frame zero
- compiles stimulus/fixation draw calls and trigger/onset lookup before frame zero, then
  executes that immutable frame plan without per-frame result-model construction
- draws one of two pre-created fixation stimuli continuously on compiled `FixationEvent`
  windows; the secondary task never changes the FPVS or trigger schedule
- polls response keys and escape
- treats only PsychoPy's PTB and ioHub keyboard backends as timestamp-capable; for those
  backends, it converts each returned flip timestamp into the keyboard clock's time base
  so RT does not depend on the later frame in which a buffered key is retrieved
- discards key timestamps from PsychoPy's `event` backend (and unknown backends) and uses
  frame scoring for the whole condition instead of presenting those values as hardware
  timestamps
- performs one neutral, trigger-free terminal flip and records one duration for every
  completed compiled frame, including the final continuous image or 50%-blank interval
- records frame intervals and runtime metadata; validated execution models and timing QC
  are materialized after playback rather than in the frame loop
- treats strict timing misses as post-run quality-control flags instead of aborting
  playback; `RuntimeMetadata` records `timing_qc_strict_violation`,
  `timing_qc_strict_violation_reason`, `timing_qc_first_bad_phase`,
  `timing_qc_first_bad_frame_index`, and `timing_qc_max_interval_s` for later review

## Trigger behavior

- runtime passes a logged trigger backend through the engine seam
- when serial output is enabled, runtime opens the configured serial port before the
  engine session starts so wrong, missing, busy, or unavailable COM ports fail before
  the participant-facing launch flow begins
- engine observes compiled `TriggerEvent` entries during playback
- the PsychoPy engine uses flip-locked scheduling with `window.callOnFlip(...)`, tying
  marker-write callbacks to the flip that presents the compiled frame
- trigger payloads are validated before playback; the flip callback reads the run clock,
  performs the synchronous prepared hardware write, and appends a primitive log entry.
  Validated `TriggerRecord` construction is deferred until runtime requests records.
- trigger writes are the only experiment callbacks registered on timed image-onset
  flips; secondary fixation timing uses the returned flip timestamp instead
- trigger attempts are recorded with frame/time metadata, backend name, status, and
  failure message when applicable; exported trigger `time_s` values are run-playback
  times and do not include timing warmup frames
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
backend send failures record `error` before the run/session is aborted and exported.
The pre-run COM-port open check verifies OS-level serial availability; it does not prove
that downstream EEG/status-channel cabling is physically correct.

These software checks do not prove physical display onset timing. Lab timing precision
still needs BioSemi/BDF and photodiode validation on the actual machine and display.

## Fixation logging

With PsychoPy's PTB or ioHub keyboard backend, the engine captures raw response-key and
fixation-target flip times in the same keyboard-clock time base. With the `event` backend,
an unknown backend, or incomplete same-clock timing data, runtime scores the whole
condition by frame instead; it never mixes timestamp and frame scoring within a condition.

Runtime then scores them against compiled `FixationEvent` windows and exports:

- one fixation-event log with hit/miss outcomes
- one raw/scored response log with hit/false-alarm classification
- one condition-level fixation summary (targets, hits, misses, false alarms,
  accuracy %, mean RT)
- compiled fixation event timing preserved in the exported fixation rows
- `keyboard_backend` and `fixation_rt_scoring_source` provenance in runtime metadata and
  condition history, plus `rt_scoring_source` on detailed fixation/response rows

That keeps the scoring logic testable without requiring PsychoPy.

Scoring semantics for the fixation accuracy task:

- response key: `space`
- `escape` is reserved for participant/operator abort and is rejected as a response key
- response window: `1.0` second from fixation target onset
- RT and response-window matching use seconds-based hardware timestamps when every
  target and task-key response has complete same-clock data; otherwise the entire run
  falls back to legacy frame scoring rather than mixing time bases
- `fixation_rt_scoring_source` is `hardware_timestamp`, `frame_fallback`, or
  `not_applicable` for a condition; session-level metadata may be `mixed`
- first valid response in-window counts as the target hit
- responses outside open windows are false alarms
- mean RT is computed from hits only
- the optional participant tutorial runs once before the first condition when enabled
  in setup, and disabling it preserves the direct-to-condition launch flow
- tutorial practice requires three total successful detections; missed attempts do not
  reset prior hits
- after five missed tutorial attempts, runtime shows a participant reminder to watch
  the center cross and press Space when the cross changes colors
- after ten missed tutorial attempts, runtime shows a researcher check screen; the
  researcher can press Space to continue without tutorial completion or Escape to abort,
  and continuing records a session warning

## Exports

Launch-time participant metadata:

- the GUI launch prompt collects Participant Number, Age, Sex, Handedness, and
  colorblind status by default for every project
- Sex accepts only `Female` or `Male`; Handedness accepts only `Right handed`,
  `Left handed`, or `Ambidextrous`; colorblind status is a required `Yes` or `No`
  participant answer
- Participant Number remains the required runtime identity and output-folder key
- when colorblind status is `Yes`, runtime uses the accessible fixation color preset
  of white `#FFFFFF` to vermillion `#D55E00` for both the participant tutorial and
  condition playback while leaving the authored project settings unchanged
- Age, Sex, Handedness, and colorblind status are stored in `SessionExecutionSummary`,
  each `RunExecutionSummary`, the session-level `participant_metadata.csv`, and
  project-level `logs/session_condition_history.csv`

Project-level reporting index:

- `logs/session_condition_history.csv`
  - append-only one-row-per-condition-occurrence session history
  - includes participant number, age, sex, handedness, colorblind status, random order
    seed, per-run stimulus shuffle seed, run timing, block/order metadata, abort
    fields, timing-QC metadata, fixation metrics, and block accuracy
  - used for compact reporting and for participant/seed-history lookup when detailed
    run folders are not written

Compact participant summary:

- `logs/participant_summary.xlsx`
  - regenerated after each completed session export from the project-level condition
    history
  - also refreshed on project open or after launch when the condition history is newer
    than either compact summary output
  - one row per participant session
  - excludes admin/test participant IDs `0` and `00`
  - includes PID, age, sex, handedness, colorblind status, session ID, condition
    display-order seed, image/stimulus display-order seeds, total targets, hits,
    false alarms, aborted Y/N, include-in-analysis Y/N, weighted mean accuracy, and
    weighted mean reaction time
  - applies per-column filters, freezes the header row, centers cells, and sizes
    columns to the exported text width
  - weighted mean accuracy is total hits divided by total targets
  - weighted mean reaction time is the hit-weighted mean of condition-level mean RT,
    using each condition's hit count
- `logs/participant_summary.csv`
  - companion plain-CSV export with the same columns as the workbook

Manual group summary:

- `group_summary.xlsx`
  - created only when the user chooses `File > Export Group Summary...`
  - defaults to the project `logs/` folder when it already exists, but can be saved to
    any user-selected `.xlsx` path
  - refreshes the participant summary before export so the workbook is based on the
    current project-level condition history
  - writes one `Group Summary` sheet with a first aggregate row and participant/session
    rows underneath for filtering/audit
  - aggregate metrics include only rows marked `Include In Analysis = Y`
  - includes export-time `Generated At UTC`, included/excluded session counts, total
    targets, hits, false alarms, weighted mean accuracy, and hit-weighted mean reaction
    time
  - applies per-column filters, freezes the header row, centers cells, and sizes
    columns to the exported text width

Run export modes:

- `Full runs folder`
  - default app setting
  - writes the detailed `runs/P<participant>/` session folder and per-condition run
    folders
  - keeps the Run page `Open Run Folder` and `Copy Run Folder` actions available after
    launch
- `Compact summaries only`
  - app setting from `File > Settings...`
  - skips detailed `runs/` session and run artifact folders
  - still appends `logs/session_condition_history.csv` and regenerates
    `logs/participant_summary.xlsx` and `logs/participant_summary.csv`
  - when modular tasks collect responses, appends raw participant/session-keyed rows to
    `logs/task_responses.csv`; an opaque journal under
    `logs/.task-response-checkpoints/` protects partial responses during execution and
    is removed only after the compact CSV is finalized
  - returns no run-folder output path, so Run page folder actions stay hidden

Per session, full export mode:

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
- `task_responses.csv`
- `warnings.log`

Per run, full export mode:

- `runspec.json`
- `run_summary.json`
- `runtime_metadata.json`
- `display_report.json`
  - a display-compatibility report derived from the compiled run timing, including
    exact/approximate status and realized base/oddball rates when the requested cadence
    does not divide evenly into the monitor refresh
- `events.csv`
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`
- `task_responses.csv`
- `task_responses.jsonl` (append-only partial-response checkpoint)
- `warnings.log`

Task response exports contain stable task/step/question ids, realized option order,
module and step repetition, retry attempt, raw value, RT, mouse details, validity,
timeout/abort state, and optional correctness/score. Participant-entered text that
could be interpreted as a spreadsheet formula is apostrophe-prefixed in CSV while the
JSON/JSONL research record retains the raw value. Raw task responses are deliberately
absent from participant/group summaries, condition-history rows, project files,
templates, configs, and portable project bundles.

Run and session `events.csv` exports include neutral stimulus columns:
`stimulus_modality`, `stimulus_id`, `stimulus_value`, `image_path`, and `text`.
`stimulus_value` is a spreadsheet convenience field derived from `image_path` for image
events and `text` for word events; role and frame timing columns stay unchanged.
Resolved presentation details remain available in `runspec.json`, the authoritative
engine input, without adding per-event styling columns or a separate replay artifact.

Studio `.fpvsconfig` export is a separate summary/interchange file built from the editable
project, stimulus manifest, and optionally an existing completed session directory. A
completed `.fpvsconfig` preserves the session seed, realized condition order, per-run
stimulus shuffle seeds, trigger schedule, display geometry, and stimulus-generation
provenance so another lab can recreate the setup. Configs omit FPVS stimulus libraries
but embed hashed modular-task media together with task definitions so those workflows
remain portable. They never contain participant task responses. A config does not
replace the authoritative artifacts under `runs/`, and runtime does not consume
`.fpvsconfig` during playback.

## Session mode

The supported runtime uses normal session mode. `LaunchSettings` has no production/test
Boolean gate; presentation, trigger, connected-refresh verification, and timing-QC
behavior use explicit runtime settings.

In the current v1 runtime:

- runtime summaries use `run_mode="session"`
- the backward-compatible `RuntimeMetadata.test_mode` export field remains present and
  is always `false`; runtime control flow does not read it
- GUI launch fixes PsychoPy playback to fullscreen presentation
- session order is randomized within each block using the current random order seed
- every condition waits for the participant to press Space before playback starts
- trigger output follows the project's trigger settings; new projects default to
  BioSemi-compatible serial output on `COM3`, and oddball onset output is locked to
  marker code `55` unless the project records an explicit nonstandard-code override
- completion screens retain the explicit 0.5-second auto-dismiss duration
- GUI launches use report-only timing misses, a `1.5`-frame-interval miss threshold,
  strict post-settle warmup QC, a 240-frame timing warmup, and production graphics-memory
  verification

Source-tree Windows and Linux runs can enable the app-level Experiment Test Mode. The
GUI supplies reserved participant ID `0`, omits participant metadata and manual-electrode
updates, and skips the Sophia/BioSemi recording gate. The document launch adapter keeps
the authored trigger settings unchanged while creating `LaunchSettings` with
`serial_enabled=false`, `verify_refresh_rate=false`, and
`verify_graphics_memory=false`. Fullscreen playback, compilation, asset preflight,
condition/task flow, frame timing, timing warmup/QC, and normal test exports remain
active, but the result does not claim graphics-hardware qualification. The preference is
unavailable in packaged builds and is not persisted in ProjectFile, RunSpec, or
SessionPlan.

Compilation, session flow, scoring, and export behavior remain independent of the
retired runtime mode gate; test behavior is composed only from explicit launch options.

## Current deferrals

Still deferred after Phase 4:

- GUI project editor
- arbitrary executable/scripted task code and task controls beyond the declarative
  modular primitives
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
- use native resolution and a fixed approved refresh rate; disable Windows Dynamic
  Refresh Rate, VRR/Adaptive Sync, display power saving, overlays, and notifications
- use AC power/high-performance mode and close unrelated GPU- or disk-heavy applications
- confirm `graphics_readiness_status=ready`, condition-cache synchronization/cleanup
  succeeded, and `len(frame_intervals) == completed_frames`
- an `unverified` graphics status no longer aborts playback, but it remains a visible
  warning that the machine's RAM/VRAM headroom could not be fully qualified
- inspect `timing_qc_strict_violation`; a `true` value invalidates the run for timing-
  sensitive analysis even though playback safely reached its terminal boundary
- when no photodiode is available, treat flip timestamps and BDF markers as the strongest
  software evidence only: a flip timestamp marks the software/display-swap boundary and
  a BDF marker confirms marker delivery, but neither proves when the panel emitted light
- if a photodiode becomes available later, validate software flip/trigger alignment and
  panel latency on the intended display before making photon-onset claims
