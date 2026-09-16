# FPVS Condition Modifiers

Status: Completed

Proposal approved for implementation on 2026-09-16 on `codex/cognitive-load-fpvs`.
The accompanying GUI mockup is the accepted design reference.
Implementation and scoped verification completed on 2026-09-16.

## Purpose And Scope

Replace the **Pre/Post Tasks** label and fragmented module-first authoring experience
with **FPVS Condition Modifiers** in the existing Conditions workflow. Do not add a
Setup page or change the eight-step Setup structure.

A modifier explains one research instruction as a coherent workflow: its name,
plain-language purpose, ordered before/after steps, the activity maintained during
FPVS, editable settings, and the outputs it records. Researchers should be able to
add backward counting or remembering four images without assembling and linking
several low-level modules themselves. The existing task builder remains available
for custom instructions, screens, questions, and response rules.

Version one includes a local **Built-in / My presets** library, complete local media
storage, and explicit copying into projects. Website downloads, online sharing,
plugins, executable extensions, automatic updates to presets, and a remote preset
registry are outside this version.

## Current Owners And Constraints

- `core/task_models.py`: `TaskModule`, `TaskStep`, `TaskBinding`, typed counting
  settings, compiled task specifications, and response records. `TaskPhase` has
  pre-condition and post-condition phases; it does not execute tasks during FPVS.
- `core/models.py`: project-owned `task_modules` and each condition's ordered
  `pre_task_bindings` / `post_task_bindings`.
- `core/compiler_tasks.py`: `compile_condition_tasks`, binding occurrence rules,
  seeded realization, linked counting start/report validation, and start-gate rules.
- `core/compiler.py`: `compile_session_plan`, selected conditions, session order,
  and concrete `SessionEntry` creation.
- `core/session_plan.py`: each entry's `pre_tasks`, single-condition `RunSpec`, and
  `post_tasks`. Task clocks remain outside the FPVS frame contract.
- `core/task_assets.py`: `copy_task_asset` and contained project media beneath
  `stimuli/task-assets/<task-id>/`.
- `core/condition_template_profiles.py`: the existing app-level local library
  pattern under `<FPVS Studio Root>/.fpvs-studio/templates/`. Condition profiles
  contain condition/settings defaults rather than complete task workflows/media;
  modifier presets need a separate core-owned persisted record there.
- `gui/condition_task_dialog.py` and `gui/document_conditions.py`: current authoring
  and document application boundaries. Reuse `gui/components.py` visual primitives.
- `runtime/task_runner.py`, `runtime/backward_counting.py`, and task exporters:
  execution, response validation/scoring, checkpointing, and export ownership.

Preserve these boundaries. Grouping does not create another task runner or a second
copy of the existing scheduling and scoring rules. “During FPVS” describes a
sustained participant activity; it does not insert screens, Python callbacks, or
response loops into the EEG image schedule.

## Proposed User Flow And Mock Views

### 1. Library And Condition Overview

The existing Conditions action becomes **FPVS Condition Modifiers**. Its summary
shows the selected condition and assigned modifier names. Opening it retains the
current dialog host, with an assigned-modifier list and one readable detail area
rather than several simultaneous deep editors. **Add modifier** opens the library
as a separate selection dialog; the library does not permanently consume editor space.

- **Built-in** offers **Backward counting** and **Remember four images**.
- **My presets** shows named local copies, with a useful empty state and an explicit
  local-library location. Add/remove project assignments separately from deleting a
  saved local preset.
- Each library item displays its purpose, three phase summaries, required media,
  and a short output summary before insertion.
- Applying a library choice first creates a dialog draft. It does not immediately
  alter the project or persist project assets.
- An explicit condition selector lists condition names, existing assignments, and
  the exact pending additions/replacements/removals. Default to the current
  condition. The final action labels the scope, for example **Apply to 3 conditions**.

Do not retain a checkbox whose indirect effect is silently changing a shared
module on other conditions. Shared definitions must expose every affected condition
and the pending change before application. Applying to only the current condition
copies a shared definition when necessary so unrelated assignments remain intact.

### 2. Modifier Editor

The header contains the modifier name and a short purpose. **Overview**, **Settings**,
and **Preview** tabs replace the always-present preview pane. Overview includes a
compact **Before FPVS -> During FPVS -> After FPVS** summary and **Recorded data**.
Only the selected tab occupies the main detail area; Preview earns its space when
the researcher requests it, including a clear incomplete-assets state.

For counting, the preview explains the optional session baseline, starting-number
prompt, counting interval, and final-number response. For memory, it shows the
study screen, maintaining the four images in memory, and recognition response.
Explain the baseline's session scope separately from each condition's before phase.

Present ordinary settings first. **Advanced steps** opens the existing task-builder
capabilities for instructions, layouts, response types, repeats, and bounded branches.
Retain explicit before/after ordering. Built-in linked steps have clear placement
constraints: counting start is the final before step and endpoint is the first after
step. Extra generic steps must fit around those constraints; reject an invalid
reorder rather than silently moving authored content.

The footer distinguishes **Save as local preset**, **Apply to condition(s)**, and
**Cancel**. The output summary explains what is collected without displaying
implementation field names as the main participant-authoring language.

### 3. Save As Local Preset

Saving is a deliberate separate action with a name, optional description, included
image count, and **Save local preset** button. Built-ins remain factory defaults;
editing one produces an editable local copy. Updating an existing local preset names
that target explicitly rather than replacing an unrelated same-named record.

After saving, show **Saved locally; project changes are still pending**. Canceling
the outer modifier editor discards its project draft; a separately confirmed local
preset save remains saved. State this distinction beside the Save action and in the
post-save status so Cancel has no surprising hidden persistence effect.

Applying to the project does not automatically update the library. A library edit
does not propagate into projects that previously used it. Use the existing document
dirty/save lifecycle after project application; do not silently save the whole project.

### 4. Existing / Custom Modifier View

Existing tasks appear as **Existing custom tasks**, with their original names,
before/after sequence, settings, and advanced editor. This is a presentation grouping,
not evidence that the application has inferred their purpose or linked phases.

Do not relabel an imported study as the new generic memory preset or automatically
correct its recognition rules, repetitions, source images, response keys, scoring,
timing, or instructions. Any conversion to a new built-in is an explicit replacement
shown in the scope review. Opening and canceling preserves the original project.

## Built-in Workflows And Defaults

### Backward Counting

One modifier manages baseline, load-start, and endpoint modules internally. The
researcher edits the subtraction step, starting-number range, optional baseline,
baseline duration, instructions, and assigned conditions. They should not need to
invent matching counting-link IDs or attach baseline modules to no-load conditions.

- New-preset arithmetic defaults retain the existing subtract-13 and inclusive
  1000-9999 starting range. The existing factory baseline is 120 seconds; the new
  built-in may retain that starting default rather than introducing an unrelated
  protocol change. Baseline is an explicit optional setting, enabled in the starter.
- Always load saved values. In particular, preserve the user's existing **30-second**
  baseline; neither opening the editor nor grouping existing tasks resets it to 120.
- Baseline and load subtraction settings match by default. The baseline has one
  displayed duration shared across assigned conditions. FPVS counting duration is
  derived from each condition's compiled stream duration; changing baseline duration
  does not change image timing.
- The baseline runs once at the beginning of the selected session whenever at least
  one selected counting assignment requests it. It precedes the first image stream,
  including when the first randomized condition has no counting load.
- A no-load-only selected test has no baseline requirement from an unselected new
  counting assignment. Existing legacy baseline bindings retain their saved behavior.
- The start prompt replaces the ordinary readiness gate. Counting begins with images
  and ends at their offset; endpoint entry follows immediately, outside counting time.
- Outputs retain starting number, subtraction step, raw endpoint, planned/observed
  interval durations, fractional estimated steps and remainder, rate, and a valid
  baseline comparison when available. They do not assert observed arithmetic accuracy.

### Remember Four Images

This is a **new generic proposal**, not a faithful reconstruction or scientific
validation of the migrated cognitive-decline/Creatine study. The migrated source
includes recognition before FPVS, repetition, restricted clickability/selection
behavior, and a post-FPVS key advance. Preserve those existing tasks as authored.

The proposed starter has four target images and four distinct foil images:

1. **Before:** present the four targets together in a readable 2-by-2 study layout.
   Proposed starter timing is self-paced with Space to continue; offer editable
   fixed-duration study timing and editable instructions. Do not infer a validated
   study duration from the historical source.
2. **During:** retain the four target images in memory while watching the unchanged
   FPVS stream. Show this instruction before the stream; add no during-stream screen.
3. **After:** show all eight target/foil choices in a randomized recognition grid.
   The participant selects exactly four unique images, can revise the selection,
   then presses **Submit**. All eight choices are selectable. The default has one
   scored response, no correctness retry, and no automatic correctness feedback.

Prepare real target/foil assets before the preset becomes runnable. A starter with
missing images stays visibly incomplete; placeholders must not masquerade as supplied
experimental stimuli. Editable content includes images, prompts, study timing, and
supported layouts; advanced custom workflows retain the broader existing builder.

Core realizes the per-entry target set and both phase orders once with a dedicated
deterministic seed, then compiles the linked study and recognition screens from that
same realization. Even with four fixed targets in the first version, retain explicit
target identity across phases. Do not independently sample each phase or add a
general stimulus-pool subsystem unless approved scope requires it.

Record presented target/foil identities and order, selected identities, response time,
completion/abort status, number of targets selected out of four, and exact-set
correctness. Define count and exact-set semantics explicitly; selecting all eight
cannot be accepted. A missed or aborted response is not silently scored as zero.

## Baseline Ownership: Assessment And Recommendation

The current `FIRST_SESSION_ENTRY` occurrence filter works only when its binding
exists on the condition selected for that entry. The present cognitive-load scaffold
therefore binds baseline on all six conditions. Extending that as the authoring rule
would recreate a hidden attach-to-all requirement and make selected-condition tests
fragile.

An independent `SessionPlan` pre-session task list would express the concept directly,
but also requires a new runtime flow, response identity, export path, and interaction
with the existing task runner. That is larger than needed for this first version.

Recommend explicit project-owned modifier baseline requirements, resolved by the
session compiler into existing compiled tasks:

1. After condition selection, collect baseline requirements from selected counting
   assignments. A condition without a counting assignment contributes no requirement.
2. Deduplicate shared requirements and validate their settings. Version one supports
   one compatible counting baseline per selected session. Conflicting requested
   subtraction steps, durations, or start ranges produce an actionable error naming
   the affected assignments. Do not pick the first or last silently.
3. After actual session ordering, prepend the one realized baseline to the first
   concrete `SessionEntry.pre_tasks`, before that entry's own task flow. Do not add
   persisted bindings to every condition and do not mutate the project during compile.
4. Carry sufficient modifier/baseline provenance in compiled results to identify a
   session baseline even when the hosting first entry is a no-load condition. Keep
   existing run/condition identity available for compatible task exports.
5. Reuse the task runner and existing counting calculations. The current runtime
   baseline lookup is keyed by subtraction step; the new compiler's single-compatible
   baseline rule prevents ambiguous overwrite for new modifiers. Do not silently
   reinterpret legacy baseline records or comparisons.

If legacy bindings coexist with a new baseline request, preserve each legacy module
and detect ambiguity explicitly. Require an explicit resolution of overlapping
baseline requests instead of dropping an existing task or executing duplicates
without explanation. Legacy-only projects continue through their current compiler
path unchanged.

## Contracts, Persistence, And Compatibility

Keep project task definitions and ordered bindings authoritative for execution.
Introduce only the modifier identity/grouping, sustained-activity kind, assignment
scope, optional baseline requirement, and linked memory realization semantics needed
by these workflows. Avoid a second independently editable list of the same task order.
Names and descriptions accompany the grouping rather than becoming executable code.

Presets are separate versioned core-owned records beneath the existing app template
root, with their own contained image assets. Reuse strict Pydantic validation,
explicit serialization, atomic writes, and existing path-containment patterns.
`ConditionTemplateProfile` is not repurposed into a full workflow schema.

Applying a preset copies the complete selected definition and media into the project,
allocates collision-safe task/modifier IDs, and remaps all internal references,
including counting link IDs and image paths. Saved project paths remain relative.
The project must compile and bundle successfully after its source library is removed
or the project moves to another computer. No participant data belongs in a preset.

Validate the entire draft and assets before committing the project application. Stage
asset copies so Cancel or a failed apply leaves the project document and project
media unchanged; clean only staging files created by that operation. A local preset
save includes its own copies rather than references to another project's images.

New records are additive with absent-field defaults preserving legacy behavior. Decide
the exact project/config/bundle version change with a compatibility test before coding;
do not assert that older strict-schema readers understand new fields. Unsupported
export targets must fail explicitly rather than silently discard modifier semantics.
Do not change `RunSpec` frame timing or existing task phase values for this feature.

Version one permits **one declared sustained activity per condition**: backward
counting or image memory. Arbitrary supported before/after generic steps may surround
it. Adding an incompatible second activity produces an explicit conflict and offers
a reviewed replacement; do not combine the instructions or disable one automatically.
Legacy content remains executable without guessing whether free text describes an
undeclared sustained task. Existing linked IDs, timing, response rules, and content
remain intact until the researcher explicitly edits them.

## Implementation Sequence

1. Capture legacy fixtures and finalize the two built-in semantics. Define the small
   grouping/preset records and compatibility policy; verify load/save round trips.
2. Implement local preset persistence and transactional project/media copying in core.
   Verify rename/collision, missing-media, containment, cancellation, and portability.
3. Add modifier-aware compilation: baseline resolution, conflict validation, and one
   linked memory realization. Verify unchanged `RunSpec` schedules and legacy seeds.
4. Rework the existing GUI host, assignment scope, phase summaries, local save action,
   and advanced/legacy access. Keep document application atomic and GUI work nonblocking.
5. Add necessary runtime memory scoring/provenance and export fields through existing
   owners. Verify partial-response checkpointing and baseline identity.
6. Complete routed verification and visible acceptance, then update current scoped
   workflow/architecture docs and archive this plan only when implemented.

Implementation preserves existing authored tasks and saved settings. Detailed
current behavior is documented in [Condition modifiers](../../CONDITION_MODIFIERS.md).

## Verification And Acceptance

Implementation progress on 2026-09-16:

- Grouping/factories, typed counting adoption, selected baseline resolution, linked
  memory compilation, runtime scoring, and response provenance are implemented.
- Local presets and transactional project media use complete contained copies;
  independent review findings for failed-read rollback and long Windows project
  paths were fixed with regression coverage.
- Modifier projects/configs use schema 1.6.0/1.4.0. Legacy serialization omits empty
  grouping, while the bundle envelope and FPVS RunSpec remain unchanged.
- Core focused verification: 437 passed, one unavailable symlink privilege skip.
  Project I/O focused: 144 passed. Docs focused: nine passed.
- The GUI groups complete workflows, stages edits and image choices, exposes exact
  condition scope, and saves independent local presets. Shared-copy isolation,
  separate baseline settings, and custom memory keys/layouts have regression coverage.
- Independent review findings were fixed: unrelated edits preserve custom values,
  copying an edited shared modifier restores other conditions' original definition,
  and memory images randomize across authored exact-layout slots.
- Engine focused verification: 254 passed. GUI focused Ruff/compilation passed;
  mypy passed all 177 source files. Verification configuration and diff checks passed.
- Repo precommit passed style, compilation, mypy, harness, and docs checks. Its unit
  run recorded 1,691 passed and seven Windows symlink-privilege skips, with one
  existing process-startup timeout. The final targeted rerun passed 44 tests with
  one symlink skip, including every reporting-lock case, the new exact-layout
  regression, and modifier/preset tests.
- User-approved visible Windows checks passed all 85 scoped cases: 13 modifier,
  22 existing task-editor, 33 Setup Conditions, and 17 Setup shell cases. Actual
  1100x720 and 1120x760 sizes, both themes, and final PNGs were reviewed. Setup
  coverage uses the documented 1120x820 eight-step contract. Final screenshots and
  the 63-case combined-run XML are retained under `build/modifier-gui-review/`;
  temporary test directories were cleaned.
- Full PsychoPy participant playback and physical display/trigger timing were not
  exercised; retain the intended-machine acceptance path below.

### Core, Compilation, And Runtime

- A preset round trip includes every referenced image. Apply works after library
  deletion; config/bundle round trips preserve the workflow and project-relative paths.
- Existing projects and migrated study fixtures retain task order, instructions,
  clickability, repetitions, scoring, readiness gates, seeds, and source media. Opening
  the new UI does not transform them into the new memory workflow.
- A counting session with a randomized no-load first entry has exactly one requested
  baseline before its first image stream. Repeated load conditions and multiple assigned
  conditions do not duplicate it. Test baseline disabled, selected load only, selected
  no-load only, incompatible baseline settings, and legacy/new overlap explicitly.
- Saved 30-second baseline and other authored values survive open/apply/save/reload.
  Load duration follows compiled stream time, never the baseline duration control.
- Memory study and recognition share exact target identities. Order is deterministic
  for a seed, all four targets appear among eight choices, all choices are selectable,
  repeated selections do not increase the count, and Submit requires four unique
  choices. Verify zero through four target hits and exact-set correctness.
- Task response time excludes FPVS and study time. Count interval completion uses the
  existing stream boundary. Aborted study, FPVS, and recognition retain partial output
  without fabricated answers or accuracy; endpoint entry time stays outside counting.
- Existing stimulus frame counts, base/oddball sequences, trigger schedules, fixation
  realization, and session ordering remain identical for equivalent projects/seeds.
  Modifier RNG draws do not consume the scheduling RNG sequence.
- Exports distinguish session baseline from first-condition load, include modifier and
  trial target/foil provenance, preserve existing raw task response fields, and exclude
  participant responses from local presets/configs/bundles.

### GUI And Visible Review

Use existing components and registered pytest-qt coverage for changed behavior.
Ordinary local verification remains non-Qt; visible Qt/manual checks require a safe
user-approved environment, never offscreen local execution.

Review the dialog at **1100x720 minimum** and **1120x760 default**, and its Conditions
entry/summary within Setup at **1120x820**. Check Built-in, empty/populated My presets,
counting with/without baseline, memory missing/complete images, scope review, preset
save/update, validation failures, legacy/custom access, and long names/instructions.
Required controls and primary actions must fit without clipping or required scrolling;
intentional list scrolling and elision require an accessible full-value path.

Verify keyboard navigation, visible focus, readable phase/selection states, changing
selection before Submit, explicit assignment scope, unsaved draft indicators, Cancel,
and the separately saved preset status. A preview must not consume an execution seed,
reserve a participant session, or write participant output.

Run core/compiler/project-io/runtime focused routes as their owners change, GUI focused
non-Qt verification plus registered coverage, and repo precommit after shared changes.
Run `./scripts/verify.ps1 -Scope docs -Tier focused` after updating the canonical
workflow and plan records. Passing source checks does not establish visible PsychoPy
behavior or physical display/trigger acceptance.
