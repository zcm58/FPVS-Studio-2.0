# Word-Based FPVS Conditions

Status: Completed

## Summary

Add word-based FPVS conditions alongside the existing image-based conditions. A word
condition uses typed base and oddball word lists stored in the Studio project instead
of folders of image files. The timing, base/oddball schedule, randomization,
fixation-task behavior, trigger timing, session ordering, and runtime launch flow must
apply identically to image and word conditions.

The feature must preserve the current image-based paradigm behavior. Existing projects
that only use image folders should save, reopen, compile, launch, and export with no
behavioral change except for versioned neutral export fields needed to describe both
images and words.

## User Workflow

Users can create a project with any mix of image-based and word-based conditions.

For an image condition, the Conditions setup workflow remains the current folder-based
flow:

- create or select the condition
- choose base images from a folder
- choose oddball images from a folder
- normalize/materialize image assets when required
- launch with the existing image presentation behavior

For a word condition, the user does not choose stimulus folders. Instead, Studio shows
two editable word-list inputs:

- Base Words
- Oddball Words

The first implementation should use a direct, inspectable authoring model: one word or
short phrase per line, stored in the project file. The GUI should trim blank lines,
preserve the authored display text for each non-empty line, show counts for each role,
and report readiness as missing words when either list is empty. While a word editor has
focus, debounce refresh preserves an in-progress blank line so pressing Enter does not
move the cursor back to the previous line.

The user should be able to run sessions containing, for example:

- one image-based faces condition
- one image-based objects condition
- one word-based animal-words condition
- one word-based tool-words condition

The session compiler should still emit one `RunSpec` per condition occurrence, and the
runtime should still iterate a single `SessionPlan` in randomized block order.

## Success Criteria

- Existing image-only projects remain valid and behaviorally unchanged.
- A new word condition can be authored without selecting image folders.
- Word conditions use the same compiled timing fields as image conditions.
- Word conditions use the same base/oddball role schedule and seeded per-role shuffling
  as image conditions.
- Image and word conditions can coexist in one `SessionPlan`.
- Runtime preflight validates image assets only for image events and validates text
  content for word events.
- PsychoPy playback preloads/prepares condition-local image or text stimuli before
  playback and releases condition-local resources after playback.
- Runtime/export artifacts preserve whether each event was an image or word stimulus.
- The implementation does not add GUI fallback modes, alternate non-GUI authoring
  paths, or generated image files for words.
- No implementation phase may broaden this work into configurable protocol timing,
  typography controls, word-list importers, publication-summary exports, or image
  preprocessing refactors.
- Each cross-layer phase has focused regression tests that prove existing image behavior
  still works before the next phase starts.

## Non-Goals

- Do not render words into temporary PNG files to fit the current image-only pipeline.
- Do not support mixed-modality roles inside one condition, such as base images with
  oddball words, unless a future plan explicitly asks for that.
- Do not change the FPVS base frequency, oddball interval, cycle-count semantics,
  fixation scheduling, or trigger timing.
- Do not add font-by-condition, per-word styling, lexical metadata, CSV import, or
  bulk dictionary management in the first implementation.
- Do not move PsychoPy imports outside `src/fpvs_studio/engines/`.
- Do not make runtime inspect editable `ProjectFile` state during playback.
- Do not change `SessionPlan` ordering semantics or make sessions aware of modality
  beyond the embedded `RunSpec` entries.
- Do not rename image-only public controls or exports unless the changed surface must
  describe both images and words.
- Do not change image normalization, materialization, control-condition generation, or
  derived-variant behavior except to skip those image-only paths for word conditions.

## No Silent Fallbacks

This feature must fail loudly instead of substituting behavior when modality data is
missing, inconsistent, or unsupported.

- Do not convert words to images as an emergency path.
- Do not convert images to words, or words to images, when validation fails.
- Do not silently treat unknown modality values as `image` or `word`.
- Do not silently ignore malformed persisted fields except inside an explicit,
  versioned migration path with tests.
- Do not silently drop blank or invalid word entries during model validation. GUI
  editors may ignore empty visual lines before saving, but direct model data with blank
  strings must fail validation.
- Do not silently truncate, wrap, shrink, hyphenate, or otherwise alter word text at
  compile or runtime. If text exceeds the supported first-version bounds, validation
  must fail with a clear message.
- Do not skip missing image files, missing word text, unknown stimulus ids, or
  inconsistent event payloads during preflight or playback.
- Do not continue launch after a mixed-modality condition is detected.
- Do not use broad `try/except` blocks around modality-specific code unless the error is
  re-raised or surfaced as a user-facing validation/preflight/runtime error.
- Do not add compatibility shims that make old image-only assumptions pass by erasing
  modality. Compatibility must be explicit and covered by tests.

## Architecture Intent

The current architecture already has the right high-level shape:

```text
ProjectFile -> compile_run_spec(...) -> RunSpec
ProjectFile + session settings -> compile_session_plan(...) -> SessionPlan
SessionPlan -> runtime preflight/session flow -> engine.run_condition(RunSpec, ...)
```

Keep that shape. The change is to generalize the stimulus payload inside project
models, compiled stimulus events, preflight, engine preparation/drawing, and exports.
It should not create a parallel word-runtime path.

The harness goal is agent legibility: make the modality explicit in repository-local
models, docs, tests, and artifacts so future agents do not need to infer that a path
field sometimes means text. `AGENTS.md` and `ARCHITECTURE.md` should remain maps to the
deeper source-of-truth docs rather than absorbing this whole feature description.

## Task Context Recipe

Before implementing this plan, read these files in order and avoid broad source-tree
searches until a specific phase needs them:

1. `AGENTS.md`
2. `ARCHITECTURE.md`
3. `docs/RUNSPEC.md`
4. `docs/RUNTIME_EXECUTION.md`
5. `docs/GUI_WORKFLOW.md`
6. `src/fpvs_studio/core/AGENTS.md`
7. `src/fpvs_studio/gui/AGENTS.md`
8. `src/fpvs_studio/runtime/AGENTS.md`
9. `src/fpvs_studio/engines/AGENTS.md`

Primary code areas:

- core models/contracts: `src/fpvs_studio/core/models.py`,
  `src/fpvs_studio/core/enums.py`, `src/fpvs_studio/core/run_spec.py`
- compiler: `src/fpvs_studio/core/compiler.py`,
  `src/fpvs_studio/core/compiler_assets.py`,
  `src/fpvs_studio/core/compiler_conditions.py`,
  `src/fpvs_studio/core/compiler_schedules.py`
- runtime: `src/fpvs_studio/runtime/preflight.py`,
  `src/fpvs_studio/runtime/session_export.py`
- engine: `src/fpvs_studio/engines/psychopy_stimuli.py`,
  `src/fpvs_studio/engines/psychopy_engine.py`
- GUI: `src/fpvs_studio/gui/document_conditions.py`,
  `src/fpvs_studio/gui/document_stimuli.py`,
  `src/fpvs_studio/gui/condition_setup_step.py`,
  `src/fpvs_studio/gui/condition_pages.py`,
  `src/fpvs_studio/gui/window_helpers.py`

## Compatibility Lock

Before changing the shared event contract, add or identify tests that lock the current
image behavior:

- image-only project loads with old stimulus-set shape
- image-only `compile_run_spec(...)` emits the same role order, timing, trigger frames,
  and image-path order for a fixed seed
- image-only runtime preflight still rejects missing files
- image-only PsychoPy fake tests still build `ImageStim` objects before playback and
  release condition-local resources after playback
- image-only GUI setup still uses the existing base/oddball folder flow

Do not proceed with word-specific rendering until those image-regression checks exist.
This is the main guardrail for the requirement that word paradigms not affect image
paradigms.

## Model and Contract Plan

### Editable Project Models

Update `src/fpvs_studio/core/models.py` so stimulus sets can represent either
file-backed image stimuli or project-backed word stimuli.

Use one `StimulusSet` model in the first implementation. Do not introduce a separate
polymorphic hierarchy in this implementation. If the single-model approach becomes
demonstrably awkward in tests, stop and update this plan before changing the model
strategy. The expected shape is:

- add `StimulusModality` to `src/fpvs_studio/core/enums.py` with values `image` and
  `word`
- add `modality: StimulusModality = StimulusModality.IMAGE` to `StimulusSet`
- keep existing image fields for image sets:
  - `source_dir: str | None`
  - `resolution`
  - `image_count`
  - `available_variants`
  - `manifest_tag`
- add word-list storage for word sets:
  - `words: list[str] = []`
  - `word_count` as a computed property or helper, not persisted duplicate state
- preserve existing image project compatibility by adding a tested project migration
  that sets missing modality to `image` only for older persisted project data; new
  in-memory or newly saved `StimulusSet` objects must carry explicit modality

Validation rules:

- image stimulus sets require `source_dir`, keep existing source-dir/path validation,
  and keep existing image-count behavior
- word stimulus sets must persist `source_dir=None` and must not require image
  normalization
- word entries must trim surrounding whitespace
- empty lines are ignored by GUI editors before saving, and blank strings passed
  directly to the model are rejected; the persisted list must contain only non-empty
  strings
- reject bidirectional control characters in word text using the same sanitization style
  already used for instructions
- preserve duplicate words as separate authored list entries; do not deduplicate
  because repeated lexical stimuli may be intentional
- set `MAX_WORD_STIMULUS_CHARS = 64` for the first implementation and fail validation
  for longer entries; do not truncate or auto-wrap long entries

### Conditions

Keep `Condition.base_stimulus_set_id` and `Condition.oddball_stimulus_set_id`. This
preserves the current condition/session model and lets mixed image/word sessions work
without special session logic.

Add cross-field validation that a condition's base and oddball sets use the same
modality. The first implementation should reject mixed-modality roles inside a single
condition with a clear validation message.

Condition duplication should preserve the condition modality and copy word lists when
duplicating a word condition. Control-condition creation remains image-only because
derived variants are image preprocessing concepts.

### RunSpec

Generalize `src/fpvs_studio/core/run_spec.py` so `StimulusEvent` can describe both
images and words.

Expected event fields:

- `sequence_index`
- `role`
- `stimulus_modality: StimulusModality`
- `stimulus_id: str`
- `image_path: str | None`
- `text: str | None`
- `on_start_frame`
- `on_frames`
- `off_frames`

Rules:

- image events must have `image_path` and must not have `text`
- word events must have `text` and must not have `image_path`
- `stimulus_id` must be deterministic and unique within one role pool; use set id plus
  original list index for words so duplicate display text remains distinguishable
- timing fields are identical across modalities
- `RunSpec` remains single-condition
- add `ConditionRunSpec.stimulus_modality`; the compiler must reject any condition whose
  event pool would contain mixed modalities
- keep event-level `stimulus_modality` required so exports and future compatibility are
  explicit
- do not keep `image_path` as a required field or put text into a fake path

### Project Config and Migration

Update `.fpvsconfig` import/export only as needed to preserve reproducibility. Existing
image project configs should continue to round-trip. Word conditions should serialize
their typed word lists and modality clearly rather than relying on placeholder stimulus
folders.

Migration should be explicit:

- old stimulus sets without modality become image sets
- old image sets keep their current `source_dir`, `resolution`, `image_count`,
  `available_variants`, and `manifest_tag` values
- old condition references are unchanged
- old `.fpvsconfig` image summaries remain image-only unless a completed word session is
  being exported
- old event exports that only include `image_path` are historical artifacts; do not use
  old export shape as a runtime input or as an inference fallback for new events
- new exports must use neutral fields

Persisted project data should not store generated or absolute paths for word stimuli.
Word lists belong in the editable project model, not under `stimuli/originals/` or the
preprocessing manifest.

## Compiler Plan

Update `src/fpvs_studio/core/compiler.py`, `compiler_assets.py`, `compiler_conditions.py`,
and `compiler_schedules.py` so the compiler resolves role pools by modality.

Image behavior:

- keep manifest/filesystem image-path resolution unchanged
- keep `stimulus_variant` behavior unchanged
- keep existing deterministic sorted image paths before seeded shuffling

Word behavior:

- resolve role pools from the stored word lists
- preserve authored display text in compiled events
- use deterministic list order before seeded shuffling
- preserve duplicate entries by identity, not by display text
- reuse the same per-role shuffle-and-cycle schedule used for images

Shared behavior:

- total stimuli, base/oddball role selection, frame timing, fixation event generation,
  and trigger event generation stay modality-neutral
- oddball triggers still fire on oddball stimulus onset frames
- compile errors should mention "stimuli" generically where both modalities apply and
  "images" or "words" only when the problem is modality-specific

## Runtime and Export Plan

Update `src/fpvs_studio/runtime/preflight.py`:

- keep existing display, stimulus timing, fixation timing, and trigger timing checks
- check file existence only for image events
- check non-empty compiled text only for word events
- reject an event whose modality/payload fields are inconsistent
- reject unknown `stimulus_modality` values even if an `image_path` or `text` field is
  present
- reject a reused `stimulus_id` when it maps to a different modality or payload within
  one compiled `RunSpec`; repeated events for the same stimulus id are valid only when
  the payload is identical

Update `src/fpvs_studio/runtime/session_export.py`:

- write neutral event columns that preserve modality:
  - `stimulus_modality`
  - `stimulus_id`
  - `stimulus_value`
  - `image_path`
  - `text`
- keep role and timing columns unchanged
- define `stimulus_value` as `image_path` for images and `text` for words, only for
  spreadsheet convenience
- do not remove old JSON fields without a schema-version/migration decision; prefer
  additive fields while the project remains schema version `1.0.0`

The detailed runtime artifacts under `runs/` remain the source of truth. Publication
summary export work can build on the neutral event fields later, but this plan should
not expand publication-summary scope.

## PsychoPy Engine Plan

Update `src/fpvs_studio/engines/psychopy_stimuli.py` and
`src/fpvs_studio/engines/psychopy_engine.py`.

Image events:

- continue creating `visual.ImageStim`
- continue computing image display size from visual angle
- continue condition-scoped preparation and cleanup

Word events:

- create `visual.TextStim` objects before condition playback
- use a single documented default style in the first implementation:
  - window units remain `pix`
  - centered position
  - foreground color is a single documented default, initially `white`
  - text height is derived once per condition from compiled display geometry using a
    named ratio constant, initially
    `WORD_TEXT_HEIGHT_TO_STIMULUS_WIDTH_RATIO = 0.25`
  - text height is not adjusted dynamically per word
- center words at the same stimulus position currently used for images
- use condition-scoped preparation and cleanup, even if `TextStim` cleanup is lighter
  than image texture cleanup

Playback loop:

- choose the prepared stimulus by event identity
- draw it during `on_frames`
- preserve blank/off-frame behavior exactly as it works for image stimuli
- keep fixation drawing and response polling unchanged

The first implementation should choose one conservative text style and document it.
If labs need configurable font, size, color, case transforms, or phrase wrapping, those
belong in a follow-up plan.

Engine constraints:

- keep a single condition-local prepared-stimulus mapping keyed by `stimulus_id`
- do not key prepared word stimuli by text alone, because duplicate words can exist
- fail playback if a stimulus event references a `stimulus_id` that was not prepared;
  do not skip the draw or substitute another stimulus
- do not import or initialize PsychoPy while opening the authoring GUI
- keep real PsychoPy inspection scripts sandboxed if direct PsychoPy import is needed
  during debugging, because PsychoPy can write profile preferences on import

## GUI Plan

Update the guided setup flow in `src/fpvs_studio/gui/condition_setup_step.py` and the
detailed condition page in `src/fpvs_studio/gui/condition_pages.py`.

Condition authoring:

- add a modality selector with `Images` and `Words`
- default new conditions to `Images` to preserve the current workflow
- when switching an empty condition to `Words`, update the two existing condition-owned
  stimulus sets to word modality instead of creating orphan sets
- when switching an empty word condition back to `Images`, update those sets back to
  image modality and restore empty image-set defaults
- when switching a condition with existing images or words, block the switch in the
  first implementation with a clear message; do not implement destructive conversion
  until a later explicit workflow plan approves it

Image mode:

- preserve the existing Base Images and Oddball Images folder cards
- preserve normalization/materialization behavior
- preserve image repeat guidance

Word mode:

- show Base Words and Oddball Words editors
- use one word or short phrase per line
- show per-role counts
- show readiness and validation messages for missing base or oddball words
- disable image-only actions such as image normalization and control-condition creation
  when the selected condition is word-based
- commit pending word-list edits before save, compile, readiness refresh, or condition
  selection changes

Shared setup:

- condition name, trigger code, Target Stimulus Repeats, participant instructions, duty-cycle
  mode, session settings, fixation settings, and launch behavior remain shared
- update user-facing copy from "images" to "stimuli" only where the workflow truly
  applies to both modalities
- keep image-specific copy in image-only controls

## Documentation Plan

Update docs only when implementation changes land:

- `ARCHITECTURE.md`
  - context map and package responsibility notes for modality-aware stimuli
- `docs/RUNSPEC.md`
  - neutral stimulus event contract
- `docs/RUNTIME_EXECUTION.md`
  - modality-aware preflight/export behavior
- `docs/GUI_WORKFLOW.md`
  - condition setup workflow for image and word conditions
- nested `AGENTS.md` files only if task recipes or boundaries change

Keep `AGENTS.md` concise. It should point agents to the updated source-of-truth docs
rather than embedding the whole feature plan.

## Implementation Phases

### Phase 1: Contract Design and Migration

- Add modality-aware project models.
- Add migration/default behavior for existing image projects.
- Add compatibility-lock tests for current image scheduling and image model loading.
- Add model tests for image compatibility and word-list validation.
- Add a small fixture project with one image condition and one word condition.

Verification:

- model serialization tests pass
- existing image project fixtures still load
- image compatibility-lock tests pass before any engine or GUI work starts
- `python -m pytest -q tests\unit\test_harness_docs.py` passes if docs are touched

### Phase 2: Compiler and RunSpec Generalization

- Generalize `StimulusEvent`.
- Add modality-aware role-pool resolution.
- Keep image path scheduling unchanged.
- Add word scheduling tests that assert identical timing and deterministic seeded order.

Verification:

- compiler tests for image-only projects still pass
- compiler tests for word-only and mixed sessions pass
- tests assert `on_start_frame`, `on_frames`, `off_frames`, role placement, and trigger
  frames are identical for equivalent image and word conditions
- tests assert duplicate word display text compiles to distinct deterministic
  `stimulus_id` values

### Phase 3: Runtime Preflight and Exports

- Add payload-aware preflight checks.
- Update run and session event exports with neutral modality columns.
- Add tests for missing image files, valid word events, and invalid empty text events.

Verification:

- runtime preflight tests pass
- session export tests confirm mixed image/word event rows are explicit and stable
- old image-only export expectations are updated only for additive neutral columns, not
  changed timing or role semantics

### Phase 4: PsychoPy Rendering

- Add condition-scoped text stimulus preparation.
- Draw image or text stimuli through a shared event dispatch path.
- Keep current image cleanup behavior unchanged.
- Add fake-PsychoPy coverage for `ImageStim` and `TextStim`.

Verification:

- fake engine tests prove image events still prepare/draw images
- fake engine tests prove word events prepare/draw text
- cleanup tests cover normal completion, abort, and playback exception paths

### Phase 5: GUI Authoring

- Add condition modality selector.
- Add word-list editors and readiness state.
- Preserve image folder import behavior.
- Disable image-only actions for word conditions.
- Add focused pytest-qt smoke tests.

Verification:

- image condition setup smoke tests still pass
- word condition setup can create, edit, save, reopen, and compile word lists
- mixed image/word session readiness works
- blocked modality switching for populated conditions is covered by a focused GUI or
  document-facade test

### Phase 6: Docs and Quality Gate

- Update architecture/runtime/runspec/gui docs.
- Run relevant focused gates.
- Run broader quality checks when the implementation spans core, runtime, engine, and
  GUI.

Verification:

- `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py`
- targeted unit and GUI tests from phases above
- `.\scripts\check_quality.ps1` before completion if the final patch crosses all
  planned layers

## Tests

Minimum expected automated coverage:

- compatibility-lock test: current image `compile_run_spec(...)` schedule is unchanged
  for a fixed seed
- model test: existing image stimulus sets default to image modality
- model test: word stimulus sets trim/reject invalid entries
- model test: duplicate word entries are preserved as separate stimuli
- model test: unknown modality and over-length word entries fail validation
- model test: image condition cannot accidentally lose image fields during save/reopen
- validation test: base and oddball sets in one condition must share modality
- compiler test: image condition schedule remains unchanged from current expected output
- compiler test: word condition schedule uses the same base/oddball timing and seeded
  role shuffling
- compiler/session test: mixed image and word conditions compile into one `SessionPlan`
- preflight test: image events require files
- preflight test: word events do not require files
- preflight test: malformed modality payloads fail clearly
- preflight test: stimulus-id payload collisions and unknown stimulus modality values
  fail clearly
- export test: run/session `events.csv` rows include modality and payload fields
- export test: `stimulus_value` is derived from `image_path` for images and `text` for
  words
- fake-PsychoPy test: image stimuli still use `ImageStim`
- fake-PsychoPy test: word stimuli use `TextStim`
- fake-PsychoPy test: abort/error cleanup remains condition-scoped
- GUI test: image condition folder workflow remains available
- GUI test: word condition editors persist base and oddball words
- GUI test: image-only control-condition action is unavailable for word conditions

## Risks and Decisions

- The highest-risk area is accidental image regression because current contracts use
  `image_path` everywhere. Mitigation: preserve image scheduling tests before changing
  shared event shape, then assert old image outputs still match expected timing and
  path order.
- Export compatibility needs an explicit decision. Prefer additive neutral columns and
  schema-versioned JSON changes over reusing `image_path` for words.
- Text rendering defaults need a first-version decision. Start with one global,
  documented PsychoPy `TextStim` style rather than adding condition-level typography
  controls.
- Switching condition modality can destroy authored stimuli if handled casually. Block
  or confirm destructive switches; do not silently convert populated image sets into
  empty word lists or populated word lists into empty folders.
- Word lists are project data, not preprocessing assets. Keep them out of the image
  manifest/materialization path unless a later feature adds explicit word-list import
  provenance.
- The previous plan left field names partly open. This tightened plan chooses
  `stimulus_modality`, `stimulus_id`, `image_path`, and `text`; implementation agents
  should not invent a second naming scheme without first updating this plan.
- The most likely silent-regression risk is an implementation that catches modality
  errors and falls back to image behavior. Treat that as a bug. All modality mismatches,
  unknown ids, missing payloads, and unsupported text should fail validation, preflight,
  or playback with an explicit error.

## Stop Conditions

Pause implementation and update this plan before proceeding if any of these become
necessary:

- changing `SessionPlan` ordering or block semantics
- changing FPVS timing constants or duty-cycle behavior
- adding user-configurable word font, color, size, wrapping, or case transformations
- importing word lists from CSV/XLSX/TXT files
- converting populated image conditions to word conditions or populated word conditions
  to image conditions
- altering image preprocessing/manifests for reasons unrelated to skipping word sets
- changing publication-summary exports rather than only runtime event artifacts
- needing to support words longer than `MAX_WORD_STIMULUS_CHARS`

## Assumptions

- "Oddball" is the intended category name for what may be informally called "on-ball."
- A word stimulus is plain display text, not an image generated from text.
- One word or short phrase per line is sufficient for the first user-facing editor.
- Base and oddball roles within one condition should use the same modality.
- Mixed-modality sessions are required; mixed-modality roles inside a single condition
  are not required.
- Current image-based paradigms are the compatibility baseline and must not change.
- Duplicate words may be intentional and should be preserved unless the user later asks
  for duplicate detection or warnings.
