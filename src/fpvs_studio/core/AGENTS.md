# AGENTS.md

## Scope of this directory

`src/fpvs_studio/core/` contains engine-neutral domain logic.

This directory is the most important foundation in the repo. It should remain importable without PySide6, PsychoPy, or hardware-specific dependencies.

## Required responsibilities

- persistent project/data models
- dedicated `RunSpec` schemas in `run_spec.py`
- dedicated `SessionPlan` schemas in `session_plan.py`
- dedicated execution-result schemas in `execution.py`
- enums and type aliases
- template metadata
- app-level condition-template profile storage under the configured FPVS Studio root
  in `.fpvs-studio/templates/`
- JSON serialization
- validation
- project scaffolding helpers
- compilation of editable project state into a neutral `RunSpec`
- migration/versioning placeholders

## Modeling rules

- Use **Pydantic v2** for persisted models and validation.
- Set `extra="forbid"` on persisted schemas unless there is a strong reason not to.
- Include `schema_version` in persisted top-level files.
- Keep model names explicit and stable.
- Use enums instead of loose strings when possible.
- Store persisted paths as project-relative strings, not absolute machine-local paths.
- Keep editable project schemas in `models.py`, single-run execution schemas in `run_spec.py`, and multi-run session schemas in `session_plan.py`.
- Derived/read-only values can be exposed as computed properties, but do not duplicate state unless it is needed for export compatibility.

## v1 model expectations

At minimum, the core layer should define models for:

- `ProjectFile`
- `ProjectMeta`
- `ProjectSettings`
- `ProtocolSettings`
- `DisplaySettings`
- `FixationTaskSettings`
- `TriggerSettings`
- `StimulusSet`
- `Condition`
- `TemplateSpec`
- `RunSpec`
- `SessionPlan`
- `RunExecutionSummary`
- `SessionExecutionSummary`
- `ParticipantMetadata`
- `RuntimeMetadata`
- `FixationResponseRecord`
- `ResponseRecord`
- `TriggerRecord`
- `SessionBlock`
- `SessionEntry`
- `InterConditionTransitionSpec`
- `DisplayRunSpec`
- `ConditionRunSpec`
- `StimulusEvent`
- `FixationStyleSpec`
- `FixationEvent`
- `TriggerEvent`
- `DisplayValidationReport`
- `ProjectManifest` / `StimulusManifest`-related models as appropriate

## Validation expectations

Implement friendly, explicit validation for:

- supported source extensions: `.jpg`, `.jpeg`, `.png`
- non-empty condition names
- integer event trigger codes in the `1`-`255` range; code `0` is reserved for explicit
  manual reset and must not be accepted as a normal event marker
- response keys that are non-empty and do not use `escape`, which is reserved for abort
- `changes_per_sequence >= 0`
- target duration > 0 when fixation task enabled
- `oddball_cycle_repeats_per_sequence >= 1`
- image conditions have configured base/oddball image stimulus sources
- word conditions have non-empty base/oddball word lists
- valid duty-cycle mode
- display compatibility:
  - accept authored monitor refresh targets only from the core-owned approved list
    (`59.94`, `60`, `120`, `144`, and `240 Hz`)
  - keep measured-versus-configured tolerance arithmetic engine-neutral while leaving
    the hardware measurement itself behind the engine boundary
  - resolve `refresh_hz / base_hz` to the nearest positive whole frame count
  - report non-integral ratios as approximate timing with requested and realized rates
  - `blank_50` also requires an even resolved frame count per cycle

## Timing representation

For v1, keep protocol defaults explicit while allowing project-level edits:

- `base_hz = 6.0`
- `oddball_every_n = 5`
- default `oddball_cycle_repeats_per_sequence = 146`

Represent timing in frames after display validation/compilation. Do not use sleep-based millisecond scheduling as a design primitive.

## Compiler guidance

A minimal compiler in this phase should be able to:

- take validated project state plus a target refresh rate/display choice
- compile one selected condition into one `RunSpec`
- compile one multi-condition session into one `SessionPlan`
- keep execution-result/export contracts engine-neutral in `execution.py`
- derive per-stimulus frames plus on/off frames from duty-cycle mode
- build the explicit base/oddball role sequence
- assign deterministic stimulus payloads: project-relative image paths for image
  conditions, authored text for word conditions
- preserve `RunSpec` as a single-condition contract when building `SessionPlan`
- convert fixation timing fields from ms to frames and emit concrete fixation events
- compile fixation accuracy-task settings into `RunSpec` (response key/window,
  participant tutorial flag, and realized target count), while keeping `RunSpec`
  single-condition
- when randomized fixation target-count mode is enabled, select realized counts during session compilation with session-seed determinism and no immediate repetition across consecutive ordered runs
- emit trigger events without implementing hardware I/O
- keep the `oddball_onset` trigger code locked to `55` by default; nonstandard
  oddball marker codes require explicit user direction and the persisted
  `allow_nonstandard_oddball_trigger_code` override

## Hard restrictions

- No PySide6 imports here.
- No PsychoPy imports here.
- No direct filesystem writes except in explicit serializer/project-service modules.
- No image manipulation code here.
