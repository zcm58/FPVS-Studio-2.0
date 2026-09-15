# AGENTS.md

## Scope of this directory

`src/fpvs_studio/runtime/` owns the separate-process runtime orchestration, session preflight, and session-export writers.

The runtime should consume neutral `RunSpec` and `SessionPlan` contracts, add machine-specific launch settings, select an engine, and write neutral run/session exports.

## Current phase expectations

This phase should establish:

- launcher/worker module structure
- session-plan iteration and transition flow above the engine seam
- runtime-side fail-fast preflight for assets, timing, and launch hardware
- normal session-mode result assembly with explicit presentation and timing-QC options
- trigger backend wiring/logging with serial availability checked before participant
  launch screens
- session export writers
- participant and seed-history lookup
- atomic participant visit reservation across full and compact exports, preserving
  legacy and aborted output and numbering each execution separately from compilation
- engine selection plumbing
- real session execution flow against the engine seam

## Responsibilities

- read `RunSpec` and `SessionPlan`
- keep runtime-only launch options out of `RunSpec`
- select engine by name
- preflight compiled stimulus payloads before launch: image events must point to
  existing project-relative files, while word events must carry non-empty text
- reject a compiled sinusoidal run unless it is image-based and uses the required
  neutral-gray presentation background
- query the primary/default configured display mode through the platform adapter before
  launch, preserving exact Windows rational selection and KDE Linux VRR rejection
- honor an explicit `verify_refresh_rate=false` runtime option for explicit
  local experiment testing in source and installed builds without weakening normal launch defaults
- leave full image decoding to preprocessing/manual deep preflight or engine stimulus
  preparation; routine participant launch preflight must not decode the whole image set
- when serial output is enabled, open the configured port before `engine.open_session`
  so missing, busy, or unavailable ports fail before participant-facing flow begins
- open/close one engine session per launched session
- show instruction/transition screens via the engine
- sequence compiled pre-condition and post-condition task modules around each
  `RunSpec`; validate responses, repeats, retries, and branches in runtime while the
  engine renders only one neutral task step at a time
- insert inter-block pause flow via the engine for non-final blocks
- call `engine.run_condition(RunSpec, ...)`
- score fixation responses from raw key logs
- keep `escape` reserved for abort; do not accept it as a configured response key
- apply fixation accuracy scoring windows/false-alarm logic and build condition-level accuracy/RT summaries
- trigger participant-facing end-of-condition feedback via the engine when the fixation accuracy task is enabled
- run the participant fixation tutorial once before the first condition when the
  compiled fixation accuracy and tutorial settings are enabled
- aggregate run results into a session result
- write run/session export artifacts
- record trigger writes as `sent` only after the backend write succeeds; write failures
  must be exported as `error` records and abort the current run/session cleanly
- keep trigger timestamps run-playback-relative; do not include timing warmup frames in
  exported trigger `time_s`
- append project-level reporting indexes under `logs/`; write detailed execution
  artifacts under `runs/` only when full run export mode is enabled
- checkpoint experimental task responses incrementally, preserve partial responses on
  abort, and keep raw task answers out of application logs and summary workbooks
- `attentional_blink_report.py` checkpoints native burst targets and per-question
  answers before proceeding, including in compact mode. Its read-only query returns
  immutable burst rows and separate T1/T2 SOA denominators; completed stream answers
  remain included after a later task/session abort. Test IDs 0/00 are included and
  explicitly marked in GUI/CSV/Excel. Typed recall uses the compiled exact answer
  after trimming surrounding whitespace for scoring while preserving raw text.
  Its explicit Excel export contains SOA, participant/session, and burst
  tables. Raw recall answers stay out of general participant/group summaries.
- regenerate the compact project-level `logs/participant_summary.xlsx` and companion
  `logs/participant_summary.csv` after session exports so researchers have one
  spreadsheet-friendly participant/session summary
- provide a manual group-summary workbook export from the participant summary rows,
  excluding rows where `Include In Analysis` is `N` from aggregate metrics while
  keeping those rows visible for filtering/audit
- provide a read-only pooled fixation-data query from the active project's condition
  history, sharing participant-session inclusion and weighting semantics without
  regenerating summaries or changing project data, plus an explicit-path Excel writer
  for the already loaded typed result
- preserve clear separation from GUI code
- keep participant visit numbers and reviewed electrode snapshots in execution
  metadata; never add repeat-visit bookkeeping to compiled timing contracts

## Restrictions

- No PySide6 imports here.
- Keep PsychoPy usage indirect through the engine layer.
- Avoid mixing file format concerns with engine logic.
- Do not push runtime-only settings like display index or serial port back into core `RunSpec` models.
- Keep runtime-only launch settings such as fullscreen in runtime launch settings instead of GUI or core contracts.
- Do not move session randomization or compilation logic out of core and into runtime.
- Do not add null-trigger fallback after a configured serial backend fails to open or
  write.

## Export guidance

Even if the exporter is skeletal in this phase, define a stable shape for:

- `runspec.json`
- `run_summary.json`
- `session_summary.json`
- `runtime_metadata.json`
- `conditions.csv`
- `events.csv`
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`
- `attentional_blink_stream_events_v1.csv` for native AB characters, including
  symbol/phase/cycle, requested/achieved SOA and planned/observed onsets; retain legacy
  image-pair event headers. Revalidate complete exact-grid character coverage and
  target/condition markers in preflight before using the shared text frame loop.
- `display_report.json`
- detailed `task_responses.csv` and structured task results in full export mode
- project-level `logs/task_responses.csv` in compact export mode
- project-level `logs/session_condition_history.csv`
- project-level `logs/participant_summary.csv`
- project-level `logs/participant_summary.xlsx`
- manual group summary workbook exports, defaulting to `group_summary.xlsx`
- manual fixation task accuracy workbook exports to a user-selected `.xlsx` path
- `logs/attentional_blink_bursts_v1.jsonl` is the append-only source for latest native
  recall burst records in full/compact modes; `attentional_blink_bursts_v1.csv` is its
  session-finalized companion. Full mode additionally writes per-run/session JSON and
  CSV. An interrupted final journal write produces a visible query warning; refuse
  further append until that unfinished line is explicitly repaired, preserving all
  existing data. `session_finalized=False` identifies live/interrupted checkpoints.
- manual attentional blink accuracy workbook exports to a user-selected `.xlsx` path
- app-selected run export mode: full writes detailed `runs/` artifacts, compact writes
  only project-level summary logs
- full task sessions write `task_responses.csv` and per-run append-only
  `task_responses.jsonl`; compact task sessions persist raw responses beneath `logs/`
  without creating a `runs/` folder

Use simple, explicit writer utilities and keep them easy to test.


AB pilot launches retain full participant metadata and explicit pilot identity in
runtime metadata and incremental burst records. Dedicated CSV/Excel exports flatten
the demographics; older journals remain readable. See `docs/RUNTIME_EXECUTION.md`.
