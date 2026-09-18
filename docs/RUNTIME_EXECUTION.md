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
Task fonts are not project assets: runtime carries the authored Arial or Open Sans enum
from `TaskStepSpec` into every `ResolvedTaskStep`. Missing font values from compatible
project data resolve to Arial; Open Sans is supplied by FPVS Studio rather than a
machine-local font installation.

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
Sinusoidal contrast runs additionally require image events and the compiled neutral-gray
background; runtime rejects incompatible compiled copies instead of treating their
full-cycle on/off timing as continuous presentation.

Attentional-Blink runs use the native character-stream contract. Preflight checks
its exact frame grid, target onsets and markers. Retired within-slot image-pair
RunSpecs are rejected before asset/display checks, and the direct engine entry point
also rejects them before opening a window. Historical records remain decodable.

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
- applies each task step's Arial or Open Sans choice to every modular-task text surface,
  including headings, prompts, item/option labels, editable response text, validation,
  submit controls, and footers; bundled Open Sans is registered for both PsychoPy text
  renderers before use
- honors exact calibrated geometry or runtime-created responsive grids and resolves
  task images through the contained project-path helper before creating stimuli
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
- derives the core-defined sinusoidal contrast samples once from the compiled frame
  count, then applies them through preselected image operations; 4, 5, 6, and other
  base rates use their resolved cycle lengths without a nominal-frequency lookup
- draws one of two pre-created fixation stimuli continuously on compiled `FixationEvent`
  windows; the secondary task never changes the FPVS or trigger schedule
- when compiled `fixation.show_cross` is false, creates and draws no fixation stimuli,
  including cache priming, lead-in and terminal offset; any lead-in duration remains
  a blank interval, and stimulus/target/trigger timing is unchanged
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
- normal GUI launches always enable serial output, regardless of legacy project
  `triggers.enabled` or `triggers.backend` values; the configured port and baudrate
  remain in use
- runtime launch settings default to serial output. `serial_enabled=false` requires
  explicit `experiment_test_mode=true` or `pilot_mode=true`; otherwise launch fails
  before playback. Missing/busy ports or failed writes never select null output
- serial-port execution writes single-byte marker codes to the configured COM port and
  baudrate

Unset, null, blank and whitespace-only port settings resolve to `COM3`; explicit
nonempty ports are preserved. This also repairs the empty port stored by early
Library bundles without requiring those projects to be reimported. The shared
serial adapter owns resolution, and launch options record the resolved port.
The logged wrapper requires an explicit backend and a matching backend name;
omitting a backend cannot silently construct null output. The PsychoPy playback
entry point also rejects a missing backend before opening its session.
The shared backend contract defaults `emits_hardware_triggers` to false; the serial
adapter explicitly reports true and logging wrappers preserve that capability.
Playback independently rejects a log-only backend unless an explicit boolean test or
pilot flag is true, including callers that bypass runtime's factory. Preflight and
playback also reject an empty trigger schedule instead of silently running without markers.

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

## Fixation task accuracy query and export

The GUI-neutral runtime reporting query for `View > Fixation Task Accuracy...` reads only
the active project's `logs/session_condition_history.csv`. The caller supplies the
active project root, and the service resolves its `logs/` directory through the shared
`core.paths.logs_dir` project-path helper. It does not inspect detailed `runs/` folders,
use the process working directory as a fallback, regenerate participant summaries, or
write project data. The GUI runs this query in a background task so opening the view
does not block the UI thread.

The query shares the established group-summary inclusion and weighting semantics:

- participant IDs `0` and `00` are excluded
- if any row for a participant session is aborted, that whole session is excluded;
  separate included sessions for the same participant remain separate contributions
- overall and per-condition weighted accuracy is
  `100 * sum(hit_count) / sum(total_targets)`; false alarms remain separately scored and
  do not reduce this accuracy value
- overall mean reaction time is
  `sum(mean_rt_ms * hit_count) / sum(hit_count)` over rows with hits; no included hits
  produces `N/A`, not zero
- condition rows are grouped by stable `condition_id` and use the latest nonblank logged
  condition name, so renaming a condition does not split its history

Missing history and history with no target-bearing included sessions return the normal
`No fixation data yet` result. Unreadable or malformed history returns a recoverable
error result rather than changing the file. A populated result reports the distinct
included participant-session count and condition rows with included-session and
hits/targets totals. This query is a read-only projection: it changes neither fixation
scoring nor existing session/group CSV/XLSX schemas or either run-export mode.

The dialog can pass the already loaded typed summary to the runtime Excel writer after
the user selects a destination. The writer creates one flat `Fixation Task Accuracy`
worksheet with a single header row, one overall row, and one row per condition. Counts,
accuracy, and reaction time remain numeric with units in their headers; identifiers and
condition names remain literal text even when they resemble formulas. The full table has
column filters, all populated cells are centered and wrapped, and colors and fills remain
Excel defaults; column widths, number formats, condition-row heights, and a frozen header
improve navigation without encoding data. When the selected filename does not already
end in `.xlsx`, the writer appends `.xlsx` without replacing another suffix. It touches
only that explicit destination and never rewrites project logs or summary artifacts.

## Repeat participant sessions

Setup > Project exposes `Allow repeat participant sessions`, persisted as
`ProjectSettings.allow_repeated_participant_sessions` (false when omitted). The GUI
blocks a reused PID until that project option is enabled. An enabled project confirms
the next session number before launch. The same guard is used by Home and Run.

Runtime owns visit identity through `participant_sessions.py`. Its read-only preview
and authoritative reservation consider historical full summaries, condition history,
legacy bare/P-prefixed folders and `_runN` suffixes, new numbered folders, and prior
reservation markers. Aborted/partial visits count, and PID text retains leading zeros.
After preflight, runtime exclusively creates a permanent reservation under
`logs/.participant-sessions/P<PID>/session-N.json` before playback. A stale confirmed
number or another launch's reservation blocks launch instead of replacing data.
Failed or crashed launches can leave unused numbers; those numbers are never recycled.

Each new full export uses `runs/P<PID>_session<NN>/` (for example,
`P0012_session01` and `P0012_session02`) and exclusively creates its output folder.
Compact exports use the same numbering without creating detailed run folders.
Existing folders and raw historical recordings stay in place. New run/session results
carry an optional positive `participant_session_number`; missing legacy values remain
readable. Reporting and task-checkpoint identity distinguish participant session
numbers even if a caller reuses the same compiled session plan. This does not change
the compiled session ID, frame schedules, randomization, or fixation scoring.

Reporting appends the numbered-session field while retaining the earlier columns.
Participant and group summaries expose `Session Number`; historical visits receive
deterministic inferred numbers when a summary is regenerated, without rewriting their
raw recordings. New participant metadata also snapshots the reviewed manually removed
electrodes. The project PID map remains the latest prefill, while an earlier visit's
snapshot stays with that visit. Missing historical electrode snapshots stay unknown.
CSV header migration and shared report writes hold an OS lock under
`logs/.reporting.lock`; process exit releases ownership, and concurrent writers wait
up to 30 seconds before reporting a timeout. Reading old history to regenerate a
summary does not rewrite that history. A future append upgrades its header while
preserving existing rows and column values.

## Exports

Launch-time participant metadata:

- the GUI launch prompt collects Participant Number, Age, Sex, Handedness, and
  colorblind status by default for every project
- Sex accepts only `Female` or `Male`; Handedness accepts only `Right handed`,
  `Left handed`, or `Ambidextrous`; colorblind status is a required `Yes` or `No`
  participant answer
- Participant Number remains the required participant identity; each visit also has
  its own participant session number
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
  - includes PID, age, sex, handedness, colorblind status, session ID/number, condition
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
  - writes the detailed `runs/P<participant>_session<NN>/` session folder and per-condition run
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
- `attentional_blink_events.csv` when AB runs have execution results
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
- `attentional_blink_events.csv` for an AB run
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`
- `task_responses.csv`
- `task_responses.jsonl` (append-only partial-response checkpoint)
- `warnings.log`

Compact sessions checkpoint each completed run beneath
`logs/.task-response-checkpoints/` before post-condition tasks and feedback, and
update that run's checkpoint after its task flow completes. These atomic `.run.json`
files retain neutral execution results without raw task answers; task answers remain
in the existing incremental task journal. Each run is written independently, so later
bursts do not repeatedly rewrite all previous runs. A final `.session.json` checkpoint
records session completion or explicit interruption. Successful finalization removes
the checkpoints only after research tables and derived summaries have been written.
Interrupted or failed exports retain them for recovery; the runtime still raises the
original presentation or cleanup error if subsequent finalization also fails.

Numbered condition-history, task-response and AB-event commits are retry-safe under
the project reporting lock. They identify an execution by participant, visit and
session, plus run/response/event identity, rather than by the compiled session ID alone.
Atomic table replacement preserves legacy unnumbered rows and prior row order.
Derived participant CSV/XLSX generation happens after research commits; an unavailable
workbook is reported as an export error without undoing completed results. Retrying
the same numbered commit or regenerating summaries does not duplicate research rows.
Workbook replacements preserve the previous file on write failure. Historical session
plans are read for seed backfill only when the corresponding CSV seed is missing.

Task response exports contain stable task/step/question ids, realized option order,
module and step repetition, retry attempt, raw value, RT, mouse details, validity,
timeout/abort state, and optional correctness/score. Participant-entered text that
could be interpreted as a spreadsheet formula is apostrophe-prefixed in CSV while the
JSON/JSONL research record retains the raw value. Raw task responses are deliberately
absent from participant/group summaries, condition-history rows, project files,
templates, configs, and portable project bundles.

Backward-counting modules additionally attach typed start/decrement/endpoint,
interval completion and duration, estimated steps, remainder, rate and eligible
baseline-rate comparison to those records. See [Cognitive Load FPVS](COGNITIVE_LOAD_FPVS.md)
for interpretation and abort semantics. These estimates do not verify intermediate
arithmetic or change FPVS frame/trigger scheduling.

Condition modifiers add grouping/session-baseline provenance and typed image-memory
records to the same task responses. Recognition records target/foil identity, both
orders, image paths, selected targets out of four, exact-set correctness, completion,
and RT. Incomplete responses remain unscored; study and partial selections survive
abort checkpoints. Existing compact CSV headers are migrated before appending new
columns. See [Condition modifiers](CONDITION_MODIFIERS.md) for the workflow and
project/preset ownership boundaries.

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

### Attentional Blink recall results

`core.execution.AttentionalBlinkBurstRecord` is the versioned record for one burst
and its two answers. `runtime.attentional_blink_report` owns recording, read-only
queries and the explicit Excel writer; engines continue to return neutral task
input and actual stimulus onset times.

New studies bind `ab-recall` after each five-second entry. Core resolves
`t1-recall` and `t2-recall` text answer keys from that entry's actual compiled
target pair. Runtime scores them independently through the ordinary task scorer.
The participant types a digit or **unsure** on each separate screen, then presses
Enter or clicks **Next**. Raw text is preserved; scoring compares the trimmed text
with the expected digit. Saved single-choice recall tasks remain supported.
An explicit unknown answer counts as incorrect; missing, invalid or aborted
answers have null correctness and are excluded from that target's denominator.
Each SOA summary shows its separate T1/T2 answer counts. T2 recall is unconditional
on T1 correctness; the individual records support additional analyses.

Both full and compact modes write the durable
`logs/attentional_blink_bursts_v1.jsonl` journal. It checkpoints target identities
and SOA before presentation, completed stream timing before the questions, and
each answer before the next question. `load_attentional_blink_data(project_root)`
reads the latest complete checkpoint per participant, visit, session and run
without modifying the project. This preserves T1 after a T2 abort and allows
inspection of interrupted sessions. An incomplete final journal write is reported
to the researcher; malformed records are not silently accepted.

Finalization regenerates `logs/attentional_blink_bursts_v1.csv` with one row per
burst. Full mode also writes session and per-run CSV/JSON copies. Generic
`task_responses.csv`/`.jsonl` exports remain available. The dedicated burst record
contains participant/visit/session/run identity, session/run seeds, condition and
trigger code, requested/achieved/observed SOA, presented digits, both responses,
correctness, response times, and completion/abort state.

`burst_number` is the one-based chronological entry number within the session;
`soa_repetition` counts entries within that SOA. `cumulative_stimulus_s` records
EEG stream time only, excluding response screens and breaks. Session/run start
timestamps retain their separate wall-clock meaning. Missing observed SOA means
actual target onset timestamps were unavailable; compiled timing is not used as
a substitute for physical measurement.

View > **T1 and T2 Accuracy...** shows SOA summaries and chronological
burst records. `write_attentional_blink_accuracy_xlsx(summary, output_path)` exports
**Accuracy by SOA**, **Participant SOA**, **Bursts** and **Read me** worksheets.
The pooled SOA rates are descriptive and answer-weighted; participant/visit rows
and individual bursts preserve the repeated-measure structure for analysis.
The GUI and workbook SOA summaries show sorted condition trigger codes from the
recorded bursts, including custom codes or multiple codes recorded at one SOA.
The View action continues to open Fixation Task Accuracy for non-AB categories.
Completed streams with valid answers remain eligible when a later answer/session
is aborted. Test IDs `0`/`00` are included in accuracy and explicitly identified in
the GUI and CSV/Excel exports, including records from older journals. General
fixation-report inclusion flags do not change this dedicated
recall report. Raw answers stay out of general participant summary workbooks.

### Attentional-blink event exports

Native letter streams use a separate `attentional_blink_stream_events_v1.csv` in
full run/session output and compact project logs. Its versioned rows add the actual
character, `base`/`t1`/`t2` phase, cycle and slot, requested/achieved SOA, and planned
plus observed timing. A missing flip timestamp stays unavailable. Session exports
carry block/order context; individual run exports join to that context using `run_id`.
The existing text cache and frame loop handle native events, and preflight verifies
exact-grid exposures, complete cycles, digit/target roles, and condition/T1/T2 markers.
Post-condition task responses retain their separate clocks and exports. The default
Yes/No/Unsure question has neither a correctness label nor a recognition accuracy score.

The following image-pair export schema is retained for historical records only.
New image-pair compilation and playback are blocked.

AB run results carry optional `RunExecutionSummary.attentional_blink_onsets` records.
Each observed image onset includes its sequential event index, phase, global slot
index, frame index, and `time_s`. The engine captures the returned display-flip
timestamp at every Base, T1, separator, and T2 onset. `time_s` is relative to the
**first stream flip**, excluding warmup and pre-stream fixation. If that first flip
has no timestamp, all relative onset times remain unavailable. A missing timestamp
on a later onset leaves only that onset's time unavailable; planned timing or a
fallback clock is never substituted. Existing trigger and fixation timestamp fields
keep their established clock origins and must not be assumed to share this zero.

`attentional_blink_events.csv` is written beside each full AB run and in the full
session folder. Both full and compact sessions also append these rows to
`logs/attentional_blink_events.csv`; compact mode does not create a `runs/` folder.
The table joins the complete compiled sequence to observed onset records and includes:

- project, session, run, condition, and participant identifiers
- event index, global slot index, phase, and project-relative image path
- planned onset frame, duration frames, refresh rate, onset seconds, and duration ms
- requested and achieved T1/ISI/T2 durations, plus achieved onset-to-onset separation
  (`planned_soa_ms`)
- `presented`, `actual_onset_s`, and run-aborted status

An event not reached before abort has `presented=False` and an empty actual time.
An observed event with an unavailable timestamp has `presented=True` and an empty
actual time. These software-flip records do not measure the panel's emitted-light
onset or establish whether a participant recognized either target.

Standard runs omit the optional AB result field and produce no AB event table.
Their existing `events.csv`, fixation scoring, trigger scheduling, and export columns
remain unchanged. Editable `.fpvsconfig` and portable project bundles preserve the
AB settings and T2 source reference; bundles include the referenced image assets.

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
- recording launches always use BioSemi-compatible serial output with the project's
  port and baudrate (new projects default to `COM3`); oddball onset output is locked to
  marker code `55` unless the project records an explicit nonstandard-code override
- completion screens retain the explicit 0.5-second auto-dismiss duration
- GUI launches use report-only timing misses, a `1.5`-frame-interval miss threshold,
  strict post-settle warmup QC, a 240-frame timing warmup, and production graphics-memory
  verification

Source-tree Windows and Linux runs can enable the app-level Experiment Test Mode. The
GUI supplies reserved participant ID `0`, omits participant metadata and manual-electrode
updates, and skips the Sophia/BioSemi recording gate. After the ordinary full-project
launch validation succeeds, the test confirmation defaults to all conditions and may
instead pass one stable condition ID into session compilation for that launch only. A
selected condition is still compiled once per configured block and keeps its normal
pre/post tasks, timing, asset preflight, and output behavior. The selection is not
saved in the project or app settings and has no dedicated compiled field; the resulting
ordinary `SessionPlan` records only the compiled entries. Production launches continue
to compile all conditions. The document launch adapter keeps the authored trigger
settings unchanged while creating `LaunchSettings` with `serial_enabled=false`,
`experiment_test_mode=true`,
`verify_refresh_rate=false`, and
`verify_graphics_memory=false`. Fullscreen playback, compilation, asset preflight,
condition/task flow, frame timing, timing warmup/QC, and normal test exports remain
active, but the result does not claim graphics-hardware qualification. The preference
is available in source and installed builds and is not persisted in ProjectFile,
RunSpec, or SessionPlan.

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


### AB pilot execution identity

`LaunchSettings.pilot_mode` is runtime-only and is copied to `RuntimeMetadata.pilot_mode`.
The AB-only GUI preference selects the same local hardware options as explicit testing
while retaining the normal demographic and participant visit flow. Every AB burst
checkpoint adds `is_pilot_session` and a `ParticipantMetadata` snapshot, so even a
partial pilot retains demographics and answered targets in compact mode. Old journal
rows default to non-pilot with empty demographics. Dedicated CSV/Excel output flattens
metadata into participant columns; JSON retains the typed nested structure. Pilot
does not change accuracy inclusion or the reserved test-ID convention.
