# Cognitive Decline Word Recognition And Test Scope

Status: Completed

## Summary

Restore the declarative task flow omitted from the migrated Cognitive Decline Word
Recognition condition, using the archived `3_imagerecognition.psyexp` as behavioral
evidence. Extend source-only Experiment Test Mode with a per-launch condition selector
so the restored flow can be exercised without running every condition.

## Source Fidelity

The active PsychoPy flow for the linked Word Recognition experiment is:

1. An object-recognition introduction acknowledged with Space.
2. An exact-layout study screen showing Pen, Lamp, Microwave, and Chair.
3. Four repetitions of the same eight-item recognition grid. Only the four studied
   words are clickable; each accepted click ends that repetition and is followed by a
   fixed one-second `correct` screen. Duplicate correct choices across repetitions are
   permitted because the source does not enforce unique selections.
4. A fixation-task reminder that acts as the participant's condition-start gate.
5. A two-second blue fixation cross before the condition trigger and first FPVS frame.
6. A post-stream recall prompt followed by the source's fixed one-second thanks screen.

Preserve the source wording, exact degree-based positions and one-degree text height,
allowed inputs, four module repetitions, and one-second feedback duration, including
source spelling/count inconsistencies. Do not reinterpret the task into a scientifically
different corrected-response or unique-selection workflow. Author every migrated Word
Recognition task step with Open Sans so its headings, prompts, word labels, response
surfaces, feedback, and footers reproduce the source font rather than inheriting the
Arial compatibility default.

## Migrated Project Update

- Update only the configured Cognitive Decline project through current `ProjectFile`
  and serializer contracts; do not move or alter legacy PsychoPy sources.
- Add project-contained text-only `TaskModule` definitions and bind them only to the
  Word Recognition condition with `every_entry` occurrence.
- Let the final pre-task reminder replace the ordinary Studio condition start gate.
- Add the condition-level two-second pre-stream fixation override so the condition
  trigger and first FPVS stimulus still begin together after the source-equivalent
  fixation interval.
- Preserve stimuli, condition timing, trigger codes, session randomization, and all
  unrelated project state.
- Record an audit mapping the archived source routines to Studio modules without
  copying participant, result, or protected IRB files.
- Keep a recoverable copy of the pre-update project JSON in the project's migration
  records before overwriting the canonical `project.json`.

## Experiment Test Mode Workflow

- The existing confirmation dialog adds an expanding `Condition to run` selector.
- `All conditions (current behavior)` is selected for every new launch dialog.
- Individual entries use project order and stable condition IDs while displaying
  numbered condition names.
- The selection is ephemeral and applies only to the accepted launch. It is not written
  to `QSettings` or `ProjectFile`, and no dedicated selector field is added to `RunSpec`
  or `SessionPlan`; the ordinary compiled plan contains only the selected entries.
- Selecting one condition compiles that condition once per configured block. Existing
  first/every/last task-binding scopes, seeded scheduling algorithms, task flow,
  preflight, timing QC, and export contracts remain in force. Exact seeds and schedules
  may differ because filtering changes session-RNG consumption.
- Production launches always compile all conditions. Cancel exits before compilation,
  preflight, or runtime launch and leaves no stale condition selection.
- Full-project launch validation remains the readiness gate; isolated validation of an
  otherwise incomplete project is outside this feature.

## GUI Acceptance

- Keep the selector inside `TestModeLaunchConfirmationDialog`, shared by Home and Run
  launch paths.
- Use a `700x380` minimum/default dialog budget and the existing component/theme system.
- Long condition names may elide in the combo box only when the complete selected label
  remains available through its tooltip.
- Registered pytest-qt coverage checks the default All state, selected stable ID,
  acknowledgement gate, cancellation, both launch surfaces, long-name access, and
  visible child bounds at the documented size.

## Boundaries

- Reuse `compile_session_plan(..., condition_ids=...)`; do not add runtime filtering or
  mutate an already compiled plan.
- Runtime and engines continue to consume an ordinary `SessionPlan`; no runtime test
  Boolean, dedicated selection field, or PsychoPy import outside the engine layer.
- Keep modular-task font choice in the existing task contract: `TaskStep` supports only
  Arial and Open Sans, defaults to Arial for existing data, and carries that choice
  through `TaskStepSpec` and `ResolvedTaskStep`. This additive default does not require
  a schema bump and does not change `RunSpec` or the FPVS frame clock.
- Treat bundled Open Sans and its SIL Open Font License as release-facing application
  assets. Do not turn a task font choice into a project-relative path or depend on a
  machine-local Open Sans installation.
- Keep project paths relative and rooted beneath the active project. This feature adds
  no file dialog, working-directory fallback, or hard-coded project path.
- Do not run Qt locally without user approval. Do not launch real PsychoPy during tests.

## Verification

- Core/compiler tests prove a selected condition remains once per configured block and
  retains task occurrence semantics.
- Document tests prove selected IDs reach session compilation without altering normal
  launch defaults.
- Registered GUI tests cover the dialog and both Home/Run launch paths; local GUI scope
  remains non-Qt and CI runs the registered pytest-qt modules.
- Core, runtime, engine, and GUI tests cover the Arial compatibility default, the
  Arial/Open Sans editor round trip, font propagation through compiled and resolved
  task steps, and consistent use on every PsychoPy task text surface. Asset/packaging
  checks verify that the Open Sans font and OFL license remain bundled.
- Validate, compile, and preflight the updated Cognitive Decline project at 60 Hz with a
  neutral validation engine, and verify the selected Word Recognition entries contain
  the restored pre/post task specs, Open Sans on every task step, and the two-second
  lead-in.
- Run focused GUI, compiler/core, project-I/O, and documentation scopes followed by the
  repository precommit tier.

## Outcome

- The configured Cognitive Decline project now binds six text-only task modules with
  seven total steps to Word Recognition on every entry: introduction, exact study
  display, the four-repeat recognition/feedback pair, reminder/start gate, post-stream
  recall, and thanks. The source's wording, coordinates, target-only selection behavior,
  repeat behavior, two-second blue lead-in, and known spelling/count quirks are retained.
- Modular task steps now carry an Arial/Open Sans font contract through authoring,
  compilation, runtime resolution, PsychoPy rendering, and GUI preview. Arial remains
  compatible by default; the licensed regular Open Sans face is packaged with the app
  and runtime rejects a silent renderer fallback.
- Experiment Test Mode now offers All conditions by default or one condition in project
  order. Both Home and Run launch paths pass the ephemeral scope into normal session
  compilation, so a selected condition runs once per configured block with ordinary
  task-occurrence, timing, preflight, and export behavior.
- The configured project remains schema `1.2.0`. Its original project file is retained
  as `migration/project-before-word-recognition-task-20260828.json`, and
  `migration/word_recognition_task_mapping.json` records source hashes, routine mapping,
  preserved quirks, font/license hashes, and the updated-project hash.

## Verification Results

- Configured-project validation at 60 Hz: 10 expected repeat-balance warnings and zero
  errors. The selected Word Recognition plan compiled 2 entries, the full project
  compiled 8 entries, and both passed deep asset preflight with a neutral task-capable
  engine.
- Focused core: 99 passed and 1 Windows symlink-privilege skip; compiler: 82 passed;
  runtime: 155 passed; engine: 162 passed; project I/O: 48 passed.
- Focused GUI: changed-file Ruff and Python compilation passed. Registered pytest-qt
  coverage was added but intentionally not run locally under repository policy.
- Font hardening: 32 runtime/task tests passed; focused packaging passed 13 tests; live
  registration confirmed the bundled Open Sans face in both PsychoPy renderers.
- Repository precommit: Ruff, Python compilation, mypy across 130 source files,
  repository/docs audits, and 607 unit tests passed; the same Windows symlink test was
  skipped.
- Residual manual verification: exercise the Test Mode selector and the migrated task in
  a visible GUI, then run a short fullscreen Word Recognition session on the intended
  lab display before release.

## Non-Goals

No task-authoring redesign, arbitrary PsychoPy code import, block-count override,
partial-project validation mode, production condition filtering, stimulus migration,
or participant/result-data access is included.
