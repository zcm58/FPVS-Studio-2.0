# Masking condition modifiers

Status: Completed

## User workflow and acceptance

Reproduce the intended Color, Faces, and Number masking experiments as a project
named Masking. The user explicitly approved correcting source defects rather than
copying inconsistent generated-script behavior. Extend FPVS Condition Modifiers so
researchers can author this framework in the GUI, without executable imported code.

Preserve signed floating-point RGB values, native circle geometry, source image
bytes, typography, positions, five-Hz item cadence, one-Hz targets, target-to-mask
SOAs, question wording and immediate response rules. Preserve source copies and
record source corrections and remaining physical-display verification separately.

## Implementation boundaries

- Core owns strict declarative scenes, masking settings, source sampling and frame
  compilation. Compiled stream scenes belong to RunSpec; pre/post questions remain
  SessionEntry tasks. No task clock may change the stream schedule.
- Engines prepare native shapes/images/text and frame draw calls before playback;
  existing runtime trigger transport is unchanged.
- Condition Modifiers owns masking configuration and explicit before/after tasks;
  the GUI edits detached model-backed drafts and exposes reusable authoring.
- New behavior uses explicit schema versions. Existing projects preserve defaults.
- User-specific scripts and copied experiment data stay outside tracked source.

## Verification

1. Audit all three source definitions and assets; record exact source facts and
   approved corrections. Verify original/copy hashes.
2. Test frame schedules, native visual properties, response linking, persistence,
   contained assets and independent modifier assignment. Run focused routes.
3. Compile and preflight the migrated project and verify its source manifest.
4. Run repository precommit. Add registered GUI coverage and a visible acceptance
   checklist; local Qt execution requires the approved safe visible environment.
5. Report physical display/EEG checks separately from source and fake-engine checks.

## Progress

- Initial compiler focused baseline: 249 tests passed.
- Current modifiers cannot express the source's stream timing/native circles.
- Created feature branch `codex/masking-condition-modifiers`.
- Source audit found color-string, stale sampled-symbol, invalid-click scoring and
  editable/generated trigger differences. User chose intended design with fixes.
- Implemented strict native scenes, source presets, exact-frame compilation, native
  task circles/RGB/wraps, grouped task scopes and source-only GUI authoring/readiness.
- Added portable modifier media, configuration/bundle schema gates, durable scene
  plans and full/compact scene/response exports; ordinary serialized plans unchanged.
- Corrected scene preparation, fixation-to-stream handoff and terminal timed-screen
  offset so ordinary warmup and file writes do not extend authored timed screens.
- Migrated all three variants into the configured root as Masking: 9 conditions,
  27 runs. Verified all 168 copied images against 42 originals; no normalization.
- Independent source audit and compiled-plan preflight pass with the user-selected
  80 cm distance, 60.96 cm width and 1920x1080 display at source-design 60 Hz.
- Registered GUI tests and a visible/hardware acceptance path; local Qt, physical
  PsychoPy, serial output and installer/release builds remain unrun.
- Final repo precommit passed: changed-file Ruff/compilation, mypy (200 source files),
  harness/docs audits and 2023 non-Qt tests; 8 Windows symlink checks skipped because
  this account lacks the required privilege. The new portability test now uses the
  existing extended-path helper; an earlier unrelated lock-test failure did not recur.
- Library publication follow-up: clean publishing now enumerates modifier-owned media
  through the same containment helper as project bundles. Added native-image library
  preparation/import regression coverage. The migrated project received its omitted
  empty canonical stimulus manifest; its settings and images were unchanged.
- Published Masking 1.0.0 to the private Experiment Library and verified the live
  service download hash. Catalog metadata blocks stock 1.8.1 with a 1.8.2 version
  floor and explicitly requires the unreleased Masking implementation. Publication
  does not constitute an application release or physical experiment acceptance.
- Publication follow-up verification passed: library focused 167 tests with one
  Windows symlink skip; final repo precommit 2024 tests with eight such skips, plus
  Ruff, compilation, mypy and repository audits.
