# Modular Condition Tasks and Creatine Replication

Status: Completed

## Objective

Add a reusable, declarative pre-condition and post-condition task system without
changing FPVS frame scheduling, then use it to reproduce the active PsychoPy workflow
for Creatine Conditions 1 and 2. Creatine Conditions 3 through 5 remain ordinary FPVS
conditions. Symbols is explicitly out of scope.

## Participant Workflow

Runtime owns this order for every applicable session entry:

1. participant tutorial, when enabled and not already completed
2. compiled pre-condition tasks
3. the existing condition start gate, unless one pre-task explicitly replaces it
4. the configured fixation-only lead-in
5. FPVS frame zero, including the existing condition-onset trigger
6. compiled post-condition tasks
7. fixation feedback, block break, or session completion

Task clocks and responses remain separate from the timed `RunSpec`. No task may alter
stimulus events, oddball cadence, fixation realization, or trigger timing inside the
FPVS stream.

## Creatine Source Parity

Conditions 1 and 2 require this active source flow:

- introductory instruction acknowledged with Space
- four-item study display acknowledged with Space
- an eight-option recognition grid repeated four times, ending each repetition after
  one valid mouse click
- a fixed one-second `correct` message after every recognition response
- the existing FPVS reminder acknowledged with Space
- two seconds of blue fixation before FPVS playback
- the existing FPVS stream and trigger schedule
- a post-stream prompt acknowledged by one of `y`, `n`, `left`, `right`, or `space`
- a fixed one-second completion message

Condition 1 uses Apple, Calculator, Glasses, and Purse image targets plus four image
foils. Condition 2 uses Pen, Lamp, Microwave, and Chair text targets plus Bowl,
Dragonfly, Giftbow, and Notebook foils. The legacy protocol's inconsistencies are
replicated explicitly rather than hidden: its prompt says select all four although one
click ends each of four repetitions; only targets are selectable; feedback is always
`correct`; duplicate selections are allowed; and the post prompt says five items after
four were shown while collecting only an advance key.

## Architecture and Contracts

- Persist reusable project-owned task modules and ordered condition bindings in the
  editable project schema.
- Compile resolved pre/post task specs onto `SessionEntry`; keep `RunSpec` unchanged as
  the single timed FPVS contract.
- Use stable task, step, question, option, and measure identifiers.
- Support occurrence scopes for every entry, first occurrence, and last occurrence.
- Provide declarative steps for instruction/content, study displays, image/text choice
  grids, questionnaires, raw-key responses, and timed feedback.
- Questionnaire questions support single choice, multiple choice, short/long text,
  numeric values, and rating scales, with required/min/max/range validation.
- Optional correctness, scoring, retries, repeat count, option randomization, and a
  bounded validated conditional-rule vocabulary remain data, never Python or scripts.
- Add neutral task execution/result contracts. Runtime owns sequencing, validation,
  retries, branching, abort handling, and checkpointing; engines only render a
  compiled step and return neutral input.

## Assets, Interchange, and Privacy

- Copy task media beneath `stimuli/task-assets/<task-id>/` and persist only validated
  project-relative POSIX paths.
- Reject missing, absolute, escaping, or symlink-escaping assets during validation and
  preflight.
- Include definitions and task assets in project bundles and `.fpvsconfig` round trips.
- Never put participant responses in project files, templates, configs, bundles,
  application logs, error dialogs, or participant/group summaries.
- Write task responses incrementally to participant/session research artifacts, with
  stable IDs, realized option order, values, RT, timing, repetition, validity,
  correctness/score when authored, and partial-abort state.
- Escape spreadsheet-formula prefixes and bound authored and collected text lengths.

## GUI

Keep the six-step Setup Wizard. Add a condition-level `Pre/Post Tasks...` action and a
compact summary. Use one reusable dialog with Pre-condition and Post-condition tabs,
ordered module controls, type-specific editing, validation, and participant preview.
The surface must fit the existing 1120x720 setup workflow without required shell
scrolling or clipping. Register pytest-qt coverage but leave local Qt execution to CI.

## Compatibility

Use an additive schema migration. Existing projects and templates receive empty task
collections and retain identical playback. Preserve the direct stream-only execution
API while production session execution uses compiled task flows. Do not rewrite a
legacy project merely by opening it.

## Milestones

- [x] Add core task models, schema migration, validation, session compilation, paths,
      config/bundle support, and unit tests.
- [x] Add runtime orchestration, task results, incremental/full/compact exports,
      preflight, abort behavior, and unit tests.
- [x] Add neutral engine task rendering for all questionnaire primitives and focused
      fake/PsychoPy tests.
- [x] Add the six-step-compatible authoring dialog, condition summaries, previews,
      document bindings, and registered pytest-qt coverage.
- [x] Convert Creatine Conditions 1 and 2 with project-local target/foil assets while
      leaving Conditions 3 through 5 task-free.
- [x] Verify Creatine task order and behavior against both source `.psyexp` files,
      confirm unchanged triggers 5/6 and oddball 55, and deep-preflight all assets.
- [x] Run focused scopes, repo precommit, documentation verification, and document the
      remaining visible GUI/lab hardware smoke path.

## Acceptance Criteria

- Old projects compile and execute with no task screens.
- Task definitions cannot mutate `RunSpec` frame or trigger schedules.
- Missing or unsafe task assets fail before participant flow.
- Required answers, repeats, feedback, timeouts, branching, and aborts are deterministic
  and covered with a fake engine.
- Partial responses survive aborts and raw answers do not leak into summaries or
  portable project artifacts.
- Creatine Conditions 1 and 2 follow the active PsychoPy flow exactly, including its
  documented quirks, while Conditions 3 through 5 bypass task execution.
- The final Creatine fixation lead-in remains two seconds and condition triggers 5 and
  6 remain aligned with FPVS frame zero; oddball trigger 55 remains unchanged.

## Result

FPVS Studio schema `1.2.0` now supports project-owned pre/post task modules, condition
bindings, exact or responsive layouts, study and choice screens, questionnaire
questions, raw-key collection, timed feedback, repeats, validation, scoring, bounded
branching, portable task media, and dedicated research-response exports. Existing
projects migrate to empty task collections and retain stream-only behavior.

The Creatine Studio project reproduces the active Conditions 1 and 2 source workflow,
including its four one-click recognition/feedback repetitions and literal legacy
prompts, while Conditions 3 through 5 remain task-free. Deep verification passed for
all five runs, 3,676 mapped FPVS stimuli, and 12 task assets with no hash, decode,
dimension, path, timing, trigger, or geometry mismatch. Repository precommit passed
486 unit tests with one environment-limited Windows symlink test skipped. Registered
pytest-qt, visible lab-display, and live serial/photodiode checks remain external gates.
