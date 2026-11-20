# Cognitive Load FPVS

## Author a new cognitive-load study

Choose **Create manually > FPVS-Oddball** and set up the image or word conditions.
Add a condition pre-task to each load condition. For backward counting, open
**FPVS Condition Modifiers** from **Setup > Conditions**, expand **Advanced modifiers**,
and assign **Backward counting** to the load conditions. The modifier includes the
start prompt, endpoint question, and optional session baseline.

## Existing Cognitive Load FPVS projects

Existing projects open with their saved category, conditions, and tasks. The original
scaffold created three placeholder image conditions with **No load** and **Cognitive load**
variants. The six entries ran once in randomized order. Each pair initially shared
its base and oddball sources and timing. In an existing scaffold, replace those
sources in **Setup > Conditions** and review both variants before collecting data.
You can edit each variant’s sources and timing independently.

The scaffold defaults to 6 Hz, an oddball every fifth image, and 108 cycles for 90 seconds of
image presentation at a compatible display rate. Timing & Display controls adjust
that duration. Fixation response monitoring and the tutorial are disabled, with a
visible fixation cross and zero pre-stream lead-in. These are editable study defaults.
The six variants use condition trigger codes 1–6. The ordinary oddball marker is 55.

The scaffold used locally generated 512×512 PNGs of circles, squares, and triangles
with ordinary hashes, resolution metadata, and project-relative manifest paths.
These placeholders require replacement with experimental stimuli before collection.

## Simran & Sarah pilot settings

The existing **Simran & Sarah Pilot** project uses three randomized session blocks
of its six conditions. Each entry contains one 40-second stream (48 oddball cycles
at 6 Hz, every fifth item oddball). These project-specific edits do not change the
built-in scaffold or reusable modifier defaults.

Counting assignments subtract 3 from an inclusive random starting range of
1000–2000. The active 30-second baseline is retained. Each of the nine load entries
has its own starting number and an immediate endpoint question after the stream,
before any other post-condition task.

The pilot enables exactly one fixation target per stream, with
`target_onset_window` spanning 10–3 seconds before stream offset. Every condition
and displayed fixation reminder includes the participant instruction:

> There will be a cross at the center of the screen. The cross will change colors
> only ONCE throughout each condition. Press the space bar when you see the color change

Counting and recognition-memory instructions remain alongside this shared wording.
The compiler resolves the optional onset window to concrete frame events; see
[RunSpec](RUNSPEC.md#fixationevent).

## Reusable condition modifiers

Open **FPVS Condition Modifiers** from Setup > Conditions. **Backward counting**
keeps the baseline, start instruction, and endpoint question together. Edit the
subtraction step, number range, optional baseline duration, participant wording, and
condition assignments in one place. New defaults remain subtract 13, 120 seconds,
and an inclusive starting range of 1000–9999. Existing saved settings are retained.

The original scaffold assigned counting to the three load variants. Its requested baseline
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

1. At 760×500 and 800×500, verify the **FPVS-Oddball** and disabled **Standard FPVS (Coming Soon)**
   cards. Create an FPVS-Oddball with load and no-load conditions. Assign **Backward counting**
   to the load condition and check that saving retains the assignment.
2. Open an existing scaffold at Setup 1120×820 and inspect its six conditions, shared
   initial sources, 90-second durations and fixation defaults. Open FPVS Condition
   Modifiers at its documented minimum size and check the longest labels, settings, and
   assignment scope for clipping.
3. Shorten baseline and image duration in a disposable copy. Run a hardware-free test
   through baseline and both variants. Check Space gates, timed baseline offset,
   whole-number entry/Enter, immediate endpoint prompt and absence of counting during
   no-load. Repeat with a selected condition, invalid answer, and Escape at each phase.
4. Inspect full/compact task exports for start, decrement, endpoint, duration and
   estimates. Production display/trigger timing still requires physical acceptance.
