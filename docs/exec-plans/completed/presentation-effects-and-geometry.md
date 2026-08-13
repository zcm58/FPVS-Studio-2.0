# Runtime Presentation Effects and Native Geometry

Status: Completed

## Outcome

Add an engine-neutral presentation configuration system that supports the eligible
PsychoPy paradigms without generating duplicate stimulus files. FPVS timing, role
cadence, balanced stimulus scheduling, fixation scheduling, fullscreen launch, and
trigger semantics remain unchanged.

The Setup Wizard remains a six-step, `1120x720` workflow. Dense presentation controls
live in a reusable dialog reached from compact project-default and condition actions.

## Approved Product Decisions

- Presentation settings apply to image and word modalities.
- Project defaults may be overridden by a condition and then independently by its
  Base and Oddball roles.
- Runtime transforms are `none`, horizontal mirror, vertical mirror, and 180-degree
  rotation. They are distinct from file-backed preprocessing variants.
- Transforms happen at presentation time; no transformed stimulus files are written.
- Word height supports fixed or balanced-randomized values in degrees of visual angle
  or fractions of active-window height.
- Base and Oddball word-height schedules are independently seeded and never perturb
  stimulus selection order.
- The experiment font is the current Windows Studio default, frozen as Arial; it is
  not user-selectable.
- Word color and x/y position are authorable. Position uses degrees or window-height
  fractions; colors are opaque hex sRGB.
- Image geometry supports Exact Box, Contain, Cover, and Natural Aspect. Exact Box is
  used for audited PsychoPy replication and may intentionally stretch an image.
- A configurable fixation-only lead-in runs after the Space gate and before condition
  frame zero. Its default is two seconds for new projects and zero for migrated legacy
  projects.
- The first stimulus and condition trigger remain aligned on stream frame zero, with
  no blank flip between the lead-in and stream.
- Existing padded-image and materialized-transform migrations remain unchanged until
  manually converted.
- Normal event exports remain unchanged. The compiled `RunSpec` necessarily carries
  resolved presentation values consumed by the engine, but no replay artifact or new
  per-event participant-export columns are added.
- Pre/post-condition questionnaires and recognition tasks remain deferred.
- Studio retains balanced without-replacement stimulus selection, its current fixation
  scheduling, and forced-fullscreen GUI launch policy.

## Contract Design

Persist explicit project presentation defaults plus atomic condition/common and
Base/Oddball overrides. Resolution order is:

```text
project presentation defaults
  -> condition common override
  -> condition Base or Oddball override
```

Atomic groups are transform, image geometry, text-height schedule, text position, and
text color. A group override replaces its inherited group instead of merging individual
fields.

Compilation emits role-specific resolved presentation specs and a resolved text height
on each word event. Image events retain source paths; the engine calculates final image
rendering from compiled geometry and source dimensions. Lead-in time compiles to whole
frames outside `DisplayRunSpec.total_frames`.

The project schema advances additively. Loading a legacy project converts its existing
project-wide image width to Natural Aspect, computes an equivalent fixed word height
from the legacy width-based renderer, leaves condition overrides empty, and selects a
zero-second lead-in. New project scaffolds use the same visual defaults plus a
two-second lead-in. No stimuli or manifests are rewritten during migration.

## Implementation Boundaries

- `core/` owns persisted settings, inheritance, validation, deterministic style
  schedules, compilation, and migration.
- `preprocessing/` continues to own imported files and derived variants. Native
  presentation transforms and geometry do not enter manifests.
- `runtime/` validates compiled presentation contracts and otherwise preserves session
  orchestration.
- `engines/` maps compiled transforms and geometry to PsychoPy and renders the
  fixation-only lead-in without changing frame-zero timing.
- `gui/` edits model state through document services and uses neutral core helpers for
  effective settings and previews.

## Work Breakdown

1. Add enums/models, schema migration, resolution helpers, compiler contracts, and
   boundary-aware shuffled bags for both stimuli and randomized word heights.
2. Add runtime preflight checks and PsychoPy preparation/rendering for transforms,
   word styles, and all geometry modes.
3. Split the existing technical warmup so its final frames display the configured
   fixation lead-in, then reset input/run timing at the stream boundary.
4. Add project-default and condition/role presentation editor entry points, a reusable
   draft-based dialog with live preview, and the Fixation lead-in control.
5. Carry presentation defaults through condition templates and `.fpvsconfig` import /
   export without resetting explicit condition overrides.
6. Update contract and workflow documentation.

## Verification

- Core model/migration/serialization tests, including old projects retaining zero
  lead-in and current geometry.
- Compiler tests for inheritance, every transform/geometry mode, independently seeded
  balanced word sizes, RNG isolation, and no pool-boundary repeats.
- Validation/preflight tests for invalid dimensions, non-finite values, duplicate or
  undersized randomized lists, colors, and modality payloads.
- PsychoPy unit tests for constructor properties, glyph mirroring, unit conversion,
  exact/contain/cover/natural geometry, in-memory cover cropping, preload-only object
  creation, cleanup, and lead-in/trigger boundary timing.
- Registered pytest-qt coverage for the dialog, Setup entry points, inheritance resets,
  previews, validation states, and all six steps at `1120x720`.
- Local focused verification for core, compiler, runtime, engine, GUI, and docs, then
  `./scripts/verify.ps1 -Scope repo -Tier precommit`.
- Qt execution remains CI-owned unless a safe visible local run is explicitly approved.
- Manual lab smoke: mirror directions, word font/size/position, all image geometry
  modes, exact two-second cross, frame-zero trigger, and timing QC at supported refresh
  rates.

### Completion evidence

- Core, compiler, project-I/O, runtime, engine, preprocessing, GUI-static, and docs
  focused verification passed. The compiler suite includes a 10,000-item scheduling
  regression and constrained duplicate/cross-role cases.
- End-to-end schedule construction for 12,500 events benchmarks below 0.2 seconds for
  both unique and duplicate-heavy pools on the development machine, while preserving
  balanced role bags and avoiding immediate repeats whenever a valid ordering exists.
- Repository precommit passed after final integration, including Ruff, compilation,
  mypy, documentation/guardrail audits, and the safe non-Qt test suite.
- Nine launch-ready schema `1.0.0` projects on the configured external Studio root were
  loaded, migrated in memory, validated, compiled, and preflighted without rewriting
  `project.json`; their compatibility lead-in remained zero. The pre-existing `mcctr`
  project remains incomplete because four stimulus sets contain no imported images.
- Registered pytest-qt coverage was added for the presentation editor, Setup entry
  points, inheritance, native rectangles, controls, template defaults, and the six-step
  `1120x720` shell. Per repository policy it remains CI-owned; visible lab smoke remains
  the final hardware/display check.

## Residual Risks

- Arial is stable for the Windows-only product target but differs from the legacy
  Dyslexia experiment's Open Sans; this is an intentional Studio-policy choice.
- Cover requires an in-memory central crop during preparation; it must never create
  project files or crop during the timed frame loop.
- Large word lists combined with several height values create more preloaded TextStim
  objects. Preparation must finish before visible playback and release all objects after
  each condition.
- Existing materialized transforms and padded migrations remain valid but will not be
  rewritten automatically.
