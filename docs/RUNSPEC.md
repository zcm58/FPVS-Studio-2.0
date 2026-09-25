# RunSpec Contract

`RunSpec` is the compiled execution plan for one FPVS condition run.

Modular pre/post condition tasks are deliberately excluded. They compile onto the
containing `SessionEntry`, so questionnaire clocks, retries, response collection, and
branching cannot mutate FPVS frame or trigger schedules. `compile_run_spec(...)`
therefore remains a compatible stream-only API.

It stays intentionally separate from:

- editable project models in `ProjectFile`
- multi-condition session ordering in `SessionPlan`
- runtime execution results in `core.execution`

## Compile flow

```text
project.json -> ProjectFile -> compile_run_spec(...) -> RunSpec
project.json + session settings -> compile_session_plan(...) -> SessionPlan
SessionPlan -> runtime session flow -> engine.run_condition(RunSpec, ...)
```

Both compilation entry points validate the entire project's locked experiment
category before selecting conditions. FPVS Oddball Paradigm cannot contain active AB timing
or T2 assignments; Attentional-Blink cannot contain ordinary oddball conditions.
Selecting a compatible subset cannot bypass this check. FPVS remains an unsupported
placeholder. See [Experiment categories](EXPERIMENT_CATEGORIES.md) for legacy
classification and explicit separation. Compiled contract versions are unchanged.

## Why `RunSpec` is separate

- runtime should not inspect editable project state during playback
- engines should consume one neutral condition contract at a time
- all timing should be explicit before runtime starts
- future engine swaps should not require project schema churn
- multi-condition flow should remain above `RunSpec`, not inside it

## Timing model

Native masking scenes use the additional `scene_stream` contract with independent
inclusive onset/exclusive offset frame windows and ordered native visual draws.
They do not also carry a legacy stimulus sequence. A target-absent catch uses
RunSpec 1.5.0 with `scene_stream.is_catch_trial=True`, `target_id=None` and no target
events, while retaining the stream's duration and base/mask timing. Ordinary masking
runs retain RunSpec 1.4.0. Catch placement and SOA selection belong to session compilation;
catch detection scoring belongs to runtime. See [Masking](MASKING.md) for the complete
schema, trigger and result contracts.

All execution timing in `RunSpec` is represented in frames.

For a project-selected base rate:

- `frames_per_stimulus` is the nearest positive whole frame count to
  `refresh_hz / requested_base_hz`
- `continuous`
  - `on_frames = frames_per_stimulus`
  - `off_frames = 0`
- `blank_50`
  - `on_frames = frames_per_stimulus / 2`
  - `off_frames = frames_per_stimulus / 2`
  - `frames_per_stimulus` must be even
- `sinusoidal`
  - image-only; the image is drawn for every frame in the cycle
  - `on_frames = frames_per_stimulus`
  - `off_frames = 0`
  - contrast for local frame `k` is sampled from
    `0.5 * (1 - cos(2*pi*k/frames_per_stimulus))`, with odd-frame samples normalized
    so their displayed peak is exactly `1.0`
  - the background must be neutral gray (`#808080`)

Exact ratios such as 144 Hz / 6 Hz compile without a warning. Non-integral ratios
such as 59.94 Hz / 6 Hz compile to the nearest whole-frame cadence and produce a
display warning with realized base and oddball rates. Runtime timing QC reports actual
dropped or late flips separately from this protocol approximation.

Authored monitor refresh rates are limited to the core-owned approved list: 59.94, 60,
120, 144, and 240 Hz. Connected-display measurement is machine-specific runtime state
and is not persisted in `RunSpec`; runtime preflight compares an engine measurement to
the compiled refresh target before playback.

Runtime and engines must consume these compiled frame counts directly. They do
not recompute protocol logic from `ProjectFile`.

The editable project stores project-wide `base_hz` and integer `oddball_every_n`
settings plus duty-cycle mode per condition. Project-level
condition-template profiles only seed defaults for authoring. Mixed Continuous Images,
50% Blank Between Images, and image-only Contrast Modulation sessions compile into
separate `RunSpec` entries with each condition's resolved frame counts. The contrast
envelope is derived from that count, so 4, 5, 6, and other supported requested base
rates do not require mode-specific tables.

### Retired image-pair records

`AttentionalBlinkRunSpec` and the old project settings remain decodable for historical
records. Their within-slot T1/ISI/T2 design is unsupported: category validation blocks
compilation, runtime preflight rejects old runs, and direct engine launch rejects them
before opening a window. No image-pair compiler or ISI authoring route remains.
Native character streams use `AttentionalBlinkStreamRunSpec` and onset-to-onset SOAs.

## Main fields

### `DisplayRunSpec`

- refresh rate
- background color
- explicit presentation/duty-cycle mode
- per-stimulus frame count
- on/off frame split
- duty cycle
- total frame count

The display contract also carries the calibrated screen geometry used to resolve
degrees of visual angle. Role-specific image boxes and word presentation rules live in
the condition presentation spec described below rather than being inferred by the
engine from a project-wide square size.

### `ConditionRunSpec`

- condition identity and name
- legacy title-display flag retained for compatibility; participant transition screens
  still use generic condition numbers
- stimulus modality: `image` or `word`
- template id
- instructions text
- fixed v1 protocol constants
- total oddball cycles
- total stimuli
- condition trigger code

### `StimulusEvent`

Each event contains:

- sequential event index
- role: `base` or `oddball`
- stimulus modality: `image` or `word`
- deterministic stimulus id
- project-relative image path for image events
- display text for word events
- a compiled text-height value for word events
- `on_start_frame`
- `on_frames`
- `off_frames`
- optional AB `phase`: `base`, `t1`, `separator`, or `t2`
- optional AB `slot_index`, shared by the three events in a target-pair slot

Image events must carry `image_path` and no `text`. Word events must carry `text` and
no `image_path`. Runtime preflight and playback treat any inconsistent modality/payload
pair as an error.

### `AttentionalBlinkRunSpec`

`RunSpec.attentional_blink` is absent for standard conditions. When enabled it carries
the requested T1 and ISI milliseconds, resolved `t1_frames`, `isi_frames`, `t2_frames`,
the T2 marker code, and `t2_presentation`. Event roles remain `base` for Base/separator
images and `oddball` for T1/T2; `phase` distinguishes the two targets. Each event has
its own resolved `on_frames` and zero `off_frames`.

Use `core.run_spec.event_presentation(run_spec, event)` to resolve presentation.
T2 inherits the condition's Oddball transform/geometry rules but carries its own
source resolution. Rendering, graphics-budget estimation, and deep asset preflight
must use that T2 geometry instead of assuming every `oddball` event uses T1's source.

### Presentation specs

`RunSpec.presentation` contains resolved Base and Oddball presentation rules. The
compiler has already applied project-default, condition, and role-level inheritance, so
runtime and engines never inspect editable project settings.

Each role specifies one runtime transform: none, horizontal mirror, vertical mirror, or
180-degree rotation. These transforms are presentation properties and do not create or
select generated image files. They remain separate from preprocessing variants such as
grayscale and phase scrambling.

Image roles compile one of four geometry modes:

- `exact_box`: use the authored width and height, including intentional stretching
- `contain`: preserve source aspect ratio inside the authored box
- `cover`: preserve source aspect ratio and crop centrally to fill the box
- `natural_aspect`: author one dimension and derive the other from the source image

Word roles compile the fixed Studio experiment font, an opaque color, x/y position,
and the unit used by text height and position. A fixed or balanced-randomized authored
height rule is resolved before playback; each word event carries its resolved height.
The engine never changes font geometry in the timed frame loop.

Projects loaded from schema 1.0 retain an internal compatibility marker for the old
word-height calculation's intermediate pixel rounding. It is not an authoring unit and
is cleared when the user authors a native text-height rule.

`RunSpec.pre_stream_fixation_frames` is a separate fixation-only phase after the
participant's Space gate and before stream frame zero. It is not part of
`DisplayRunSpec.total_frames`, and no stimulus, response target, or trigger is scheduled
inside it. The first image/word and condition-start trigger still begin together at
stream frame zero.

When `FixationStyleSpec.show_cross` is false, this lead-in is a blank interval of
the same duration. The engine also omits the cross during stimulus playback and
the terminal offset frame, including stimulus-resource priming.

### `FixationStyleSpec`

The style spec now contains everything runtime/engines need to render the
fixation task without consulting editable project models:

- default and target colors
- `show_cross` (defaults to true when absent from older files); false prohibits
  fixation events, accuracy responses and the participant fixation tutorial
- response keys
- whether the participant fixation tutorial should run before the first condition
- cross size in pixels
- cross line width in pixels
- target duration in frames

Launch-time participant accessibility can derive an execution-only `RunSpec` copy with
white `#FFFFFF` default and vermillion `#D55E00` target fixation colors when the
participant reports colorblindness. This does not mutate editable project settings.

### `FixationEvent`

Each fixation event contains a concrete target onset and duration in frames.

### `TriggerEvent`

Trigger events remain generic and frame-based. The compiler emits the condition
marker on the first stimulus onset frame and oddball markers on each oddball
stimulus onset frame. Runtime and engines observe these frame markers while
serial-port details stay behind the trigger backend boundary.

For AB pairs, `t1_onset` retains the existing Oddball marker (55 by default, including
the explicit nonstandard-code override). `t2_onset` uses the authored T2 code (56 by
default). The separator has no target marker. T2's code must differ from T1 and all
condition-start codes in the project. Runtime verifies one target marker at each
compiled T1/T2 onset; marker delivery remains flip-locked.

Normal event trigger codes must be integers from `1` through `255`. Code `0` is
reserved for reset behavior and is not valid for `condition_start` or
`oddball_onset` events.

## Export relationship

Runtime writes one `display_report.json` and one scored `fixation_events.csv`
next to each executed `RunSpec`.

- `display_report.json` reflects compatibility of the compiled frame timing
- `fixation_events.csv` preserves each compiled fixation event's frame window
  plus the realized hit/miss outcome
- AB runs additionally write `attentional_blink_events.csv`; its planned/observed
  timing fields and compact-export location are defined in
  [Runtime execution](RUNTIME_EXECUTION.md#attentional-blink-event-exports)

## Asset resolution

Image `RunSpec.stimulus_sequence[*].image_path` values use project-relative POSIX paths.

When a project root and preprocessing manifest are available, the compiler
resolves real source or derived asset paths from the manifest. Runtime preflight
verifies those paths are project-relative and exist before launch, and the presentation
engine resolves them relative to the project root during playback.

Launchable image sets must have known, uniform source resolution, but that resolution
may be rectangular. Base and oddball source resolutions may differ because playback
size is controlled by compiled role geometry rather than native image dimensions.
Existing padded-square migrations remain valid and resolve through Natural Aspect until
an explicit audited conversion changes their presentation settings.

Word stimuli are resolved from typed project word lists. They do not create image files,
do not enter the preprocessing manifest, and use the same base/oddball schedule and
frame timing as image stimuli.

## v1 scheduling policy

Native attentional-blink letter streams use `RunSpec` schema `1.3.0` and
`AttentionalBlinkStreamRunSpec`. They compile directly to continuous WORD events
with explicit `base`/`t1`/`t2` phases, absolute slot indices, zero-based cycle indices,
and exactly equal whole-frame exposures. Requested and achieved SOA, target lag,
target positions, cycle size, T2 presentation, and T2 marker are in the stream contract.
T1 uses the resolved oddball presentation color; T2 has its own compiled color.
Default markers are T1=55 and T2=56, distinct from the condition-start marker.
Native streams use seeded random character sampling with adjacent-distractor and
same-pair-target exclusions. They support letter distractors with digit targets
and the legacy inverse arrangement. They do not promise the balanced image-bag policy below.
New burst runs contain exactly one target pair in five seconds (50 characters at
10 Hz), with condition markers 1/3/5 for 100/300/500 ms SOAs. Recall questions are
compiled onto the surrounding `SessionEntry`, not the timed `RunSpec`. Participant
response time separates successive bursts and is not a periodic target frequency.
The layout and exact-grid defaults are defined in [Experiment Categories](EXPERIMENT_CATEGORIES.md).

For ordinary FPVS Oddball Paradigm, the compiler emits a seed-deterministic schedule:

- oddball every project-selected Nth normal slot (every 5th by default)
- manifest-backed variant resolution when available
- sorted image paths or authored word-list order before scheduling
- independently seeded role bags so every authored base entry and every authored
  oddball entry is shown once per role cycle before that role's pool is reshuffled;
  immediate repeated display values are avoided within bags, across bag refills, and
  across Base/Oddball boundaries whenever the remaining authored multiplicities make
  an alternative possible
- independently seeded balanced word-height bags for Base and Oddball roles, also with
  no immediate repeat across bag boundaries; style randomization does not perturb
  stimulus selection order
- balanced seeded-jitter fixation target onsets from the realized target count,
  target duration, and minimum-gap edge/inter-target buffers
- a condition-start trigger event at the first stimulus onset when a condition trigger
  code is present
- an `oddball_onset` trigger event at each oddball stimulus onset, using marker code
  `55`; this code is locked Studio behavior and nonstandard oddball marker codes require
  an explicit user-directed `allow_nonstandard_oddball_trigger_code` override
- deterministic trigger sorting by frame while preserving generated order for
  diagnostics
- a compile-time failure when multiple trigger events land on the same frame, because
  BioSemi serial output writes one marker byte per flip and does not merge codes

`RunSpec` must remain single-condition even as execution/export behavior gets
richer around it.

AB expansion preserves the existing Base/T1 selection bags and uses separately seeded,
balanced ISI-image and T2 bags. Blank ISIs have no image selection. ISI selection
does not change the ordinary Base-slot bag. It does not promise avoidance of image
repeats across the independently selected Base/T1/separator/T2 phase boundaries.

Image or blank ISI: `AttentionalBlinkRunSpec.isi_mode` records the choice, and
`isi_presentation` carries independent ISI source geometry using Base presentation
rules. A blank separator has `is_blank=true`, no image/text payload, and the same
positive `on_frames` interval as an image separator. Engines skip image allocation
and drawing for that phase while preserving background, fixation, timing and target
markers. Preflight rejects blank flags on other phases or modes.
