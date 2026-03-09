# AGENTS.md

## Scope of this directory

`src/fpvs_studio/runtime/` owns the separate-process runtime orchestration, session preflight, and session-export writers.

The runtime should consume neutral `RunSpec` and `SessionPlan` contracts, add machine-specific launch settings, select an engine, and write neutral run/session exports.

## Current phase expectations

This phase should establish:

- launcher/worker module structure
- session-plan iteration and transition flow above the engine seam
- runtime-side preflight for assets and timing
- run/test mode handling
- trigger backend wiring/logging
- session export writers
- engine selection plumbing
- real session execution flow against the engine seam

## Responsibilities

- read `RunSpec` and `SessionPlan`
- keep runtime-only launch options out of `RunSpec`
- select engine by name
- preflight all referenced assets before launch
- open/close one engine session per launched session
- show instruction/transition screens via the engine
- insert inter-block pause flow via the engine for non-final blocks
- call `engine.run_condition(RunSpec, ...)`
- score fixation responses from raw key logs
- apply fixation accuracy scoring windows/false-alarm logic and build condition-level accuracy/RT summaries
- trigger participant-facing end-of-condition feedback via the engine when the fixation accuracy task is enabled
- aggregate run results into a session result
- write run/session export artifacts
- preserve clear separation from GUI code

## Restrictions

- No PySide6 imports here.
- Keep PsychoPy usage indirect through the engine layer.
- Avoid mixing file format concerns with engine logic.
- Do not push runtime-only settings like display index or serial port back into core `RunSpec` models.
- Keep runtime-only launch settings such as fullscreen in runtime launch settings instead of GUI or core contracts.
- Do not move session randomization or compilation logic out of core and into runtime.

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

Use simple, explicit writer utilities and keep them easy to test.
