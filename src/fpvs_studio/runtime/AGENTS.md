# AGENTS.md

## Scope of this directory

`src/fpvs_studio/runtime/` owns the separate-process runtime orchestration, session preflight, and session-export writers.

The runtime should consume neutral `RunSpec` and `SessionPlan` contracts, add machine-specific launch settings, select an engine, and write neutral run/session exports.

## Current phase expectations

This phase should establish:

- launcher/worker module structure
- session-plan iteration and transition flow above the engine seam
- runtime-side fail-fast preflight for assets, timing, and launch hardware
- run/test mode handling
- trigger backend wiring/logging with serial availability checked before participant
  launch screens
- session export writers
- participant and seed-history lookup
- engine selection plumbing
- real session execution flow against the engine seam

## Responsibilities

- read `RunSpec` and `SessionPlan`
- keep runtime-only launch options out of `RunSpec`
- select engine by name
- preflight compiled stimulus payloads before launch: image events must point to
  existing project-relative files, while word events must carry non-empty text
- fail corrupt image files during RAM-cache/preload validation before playback starts
- when serial output is enabled, open the configured port before `engine.open_session`
  so missing, busy, or unavailable ports fail before participant-facing flow begins
- open/close one engine session per launched session
- show instruction/transition screens via the engine
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
- append project-level reporting indexes under `logs/` while keeping detailed
  execution artifacts under `runs/` as the source of truth
- regenerate the compact project-level `logs/participant_summary.xlsx` and companion
  `logs/participant_summary.csv` after session exports so researchers have one
  spreadsheet-friendly participant/session summary
- provide a manual group-summary workbook export from the participant summary rows,
  excluding rows where `Include In Analysis` is `N` from aggregate metrics while
  keeping those rows visible for filtering/audit
- preserve clear separation from GUI code

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
- `display_report.json`
- project-level `logs/session_condition_history.csv`
- project-level `logs/participant_summary.csv`
- project-level `logs/participant_summary.xlsx`
- manual group summary workbook exports, defaulting to `group_summary.xlsx`

Use simple, explicit writer utilities and keep them easy to test.
