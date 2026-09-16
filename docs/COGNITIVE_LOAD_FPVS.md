# Cognitive Load FPVS

## Create and replace the scaffold

Choose **Cognitive Load FPVS** when creating an experiment. The built-in template
creates three placeholder image conditions, each represented by a **No load** and
**Cognitive load** variant. These six entries run once in randomized order. Each pair
initially shares its base/oddball image sources and timing. Replace those sources in
Setup > Design and check both variants before collecting data; subsequent edits to
condition timing or source assignments remain ordinary independent condition edits.

The default is 6 Hz, an oddball every fifth image, and 108 cycles: 90 seconds of
image presentation at a compatible display rate. Timing & Session controls adjust
that duration. Fixation response monitoring and the tutorial are disabled, with a
visible fixation cross and zero pre-stream lead-in. These are editable study defaults.
The six variants use condition trigger codes 1–6; the ordinary oddball marker is 55.

Placeholder circles, squares, and triangles are generated locally as 512×512 PNGs
with ordinary hashes, resolution metadata, and project-relative manifest paths.
They are scaffolding assets, not validated experimental stimuli.

## Reusable condition modifiers

Open **FPVS Condition Modifiers** from Setup > Conditions. **Backward counting**
keeps the baseline, start instruction, and endpoint question together. Edit the
subtraction step, number range, optional baseline duration, participant wording, and
condition assignments in one place. New defaults remain subtract 13, 120 seconds,
and an inclusive starting range of 1000–9999. Existing saved settings are retained.

The new scaffold assigns counting to the three load variants. Its requested baseline
runs once before the first selected session entry, even when randomization places a
no-load condition first. A no-load-only test has no baseline request from unselected
modifiers. Existing standalone baseline bindings retain their saved occurrence rules.
The load-start prompt remains the final before step and the endpoint the first after
step; compilation rejects incomplete or misplaced pairs.

The same modifier can be applied to other experiments or saved as a local preset.
**Remember four images** supplies another generic sustained activity. See
[Condition modifiers](CONDITION_MODIFIERS.md) for library storage, staged Apply/Cancel,
legacy compatibility, memory behavior, and visible acceptance.

## Results and interpretation

For a completed counting interval with a valid endpoint:

`estimated_steps = (start_number - endpoint) / subtraction_step`

The raw endpoint, fractional estimate and integer remainder are retained; values are
not rounded into a purported number of correct subtractions. For example, starting
at 1053 and ending at 793 while subtracting 13 yields 20 estimated steps. Ending at
790 yields approximately 20.23, with remainder 3. Neither endpoint verifies the
participant's intermediate arithmetic.

Rates divide estimated steps by the planned counting duration. A baseline-rate ratio
compares the load rate with a positive baseline rate using the same subtraction step.
Baseline and load durations may differ. Aborted intervals and missing/invalid answers
retain their records without an estimated performance value. Planned and observed
durations are distinguished in results; response-entry time is outside counting time.

Counting fields are stored with ordinary task response records in JSON/JSONL and
`task_responses.csv`. Full mode writes run/session artifacts; compact mode writes
project `logs/` task records. Incremental checkpoints preserve partial work on abort.
Use participant/session/run/condition identity and the counting role to distinguish
baseline, start and endpoint rows. Raw endpoints do not enter general participant or
group summary workbooks, application logs, project templates, or portable bundles.

## Ownership and verification

- `core/cognitive_load_presets.py`: paired defaults; `core/project_service.py`: creation.
- `preprocessing/cognitive_load_placeholders.py`: placeholder assets and manifests.
- `core/task_models.py`, `core/backward_counting.py`, `core/compiler_tasks.py`: neutral
  settings, screen generation, seeded realization and linked task compilation.
- `core/condition_modifiers.py`, `core/modifier_presets.py`: workflow grouping and library;
  `runtime/task_runner.py` and
  runtime counting helpers: flow, calculations and checkpoints.

Run core/compiler/runtime/project-io focused verification and repo precommit after
cross-layer changes. Registered GUI tests are not run in ordinary local verification.

Visible acceptance in a safe Windows session:

1. Create the category at the creation dialog's 760×500 size. Check all category
   choices and template details; cancel a second creation and check no project exists.
2. At Setup 1120×820 inspect all six conditions, shared initial sources, 90-second
   durations and fixation defaults. Open FPVS Condition Modifiers at its documented
   minimum size and check the longest labels, settings, and assignment scope for clipping.
3. Shorten baseline and image duration in a disposable copy. Run a hardware-free test
   through baseline and both variants. Check Space gates, timed baseline offset,
   whole-number entry/Enter, immediate endpoint prompt and absence of counting during
   no-load. Repeat with a selected condition, invalid answer, and Escape at each phase.
4. Inspect full/compact task exports for start, decrement, endpoint, duration and
   estimates. Production display/trigger timing still requires physical acceptance.
