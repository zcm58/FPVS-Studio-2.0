# Core Guidance

Core owns engine-neutral authoring models, validation, compilation and explicit
project services. It must import without Qt, PsychoPy or hardware dependencies.

## Owners and Contracts

- `models.py`, `migrations.py`: persisted editable state and in-memory migration.
- `run_spec.py`, `session_plan.py`, `execution.py`: run, session and result schemas.
  Read the relevant section of `docs/RUNSPEC.md` or `docs/SESSION_PLAN.md`.
- `compiler.py` and compiler helpers: scheduling, asset resolution, frame timing and
  compile-time fixation realization; runtime owns execution/scoring.
- `task_models.py`, `condition_modifiers.py`, `modifier_presets.py`: declarative tasks,
  assignment changes and independent local presets. Preserve unaffected bindings.
- `paths.py`, `project_service.py`, serialization/config/bundle services: portable I/O.
  `project_bundle_update.py` owns reviewed same-folder replacement/backups/rollback;
  ordinary imports never replace existing projects. See `docs/EXPERIMENT_LIBRARY.md`.
- `recording_hardware.py`: versioned hardware declarations, never measured qualification.
- `data_sharing.py`: strict neutral wire models and read-only protocol fingerprints;
  consent, credentials and outbox I/O belong outside core.
- Manifest schemas belong to `preprocessing/models.py`, with persistence in
  `preprocessing/manifest.py`; core consumes their neutral contracts.

## Invariants

- Use Pydantic v2, explicit schema versions and `extra="forbid"` for persisted models
  unless a documented contract requires otherwise. Avoid duplicated derived state.
- Preserve immutable project categories and existing migration/save compatibility;
  `experiment_categories.py` and `project_separation.py` own explicit legacy repair.
- Persist project-relative paths. Task media lives in `stimuli/task-assets/<task-id>/`;
  validate lexical and resolved containment before copy, compile, bundle or import.
- Compile one condition per `RunSpec`, sessions as `SessionPlan`, and pre/post tasks
  on session entries. Task clocks, answers and branches never change FPVS scheduling.
- `condition_timing.py`, `session_ordering.py` and `randomization.py` own effective
  frequency/duration, occurrence order and independent seed domains. Preserve seeded
  realization and occurrence identity; use frames, never sleep-based scheduling.
- Core owns approved refresh targets and ratio arithmetic. Native AB requires an exact
  frame grid; ordinary FPVS reports requested/realized rates. `blank_50` needs even
  frames; sinusoidal mode is image-only with neutral gray and a frame-derived envelope.
- Normal event codes are integers 1–255; zero is manual reset. Keep `escape` reserved
  for abort. The oddball marker defaults to `55`; nonstandard codes require explicit
  user direction and persisted `allow_nonstandard_oddball_trigger_code`.
- Keep opt-in native AB frame -1 markers and exported timing compatibility. Full marker
  semantics live in `docs/RUNSPEC.md`, not a second compiler implementation.
- Filesystem writes belong only to explicit persistence/project/asset services. Image
  manipulation belongs to preprocessing. Do not implement hardware I/O here.

Run the selected `core`, `compiler` or `project-io` focused route; use repo precommit
for shared contracts. Choose relevant model/validation tests rather than loading a
historical model inventory.
