# Masking condition modifiers

Masking is an FPVS Condition Modifier for brief repeated targets followed by delayed
masks. It uses ordinary FPVS item and oddball rates, with independent, exact target,
base and mask windows inside each item slot. It does not use the Attentional-Blink
letter-stream compiler.

## Authoring

Open Setup > Conditions > FPVS Condition Modifiers > Add modifier and choose
Masking: Color, Faces or Number. Settings exposes SOA, target/base/mask duration,
background RGB, and native source editing. Faces requires real base and target images;
each target must be mapped to an identification answer. Source images are staged until
Apply and become project-owned media. Edit the pre/post screens through the existing
task editor. Defaults are a source-based starting point, not a hidden import routine.

The explicit masking timing action sets a 5 Hz item rate, every-fifth-item target,
40 cycles per run, and three repetitions. It affects project timing and clearly
describes that scope. Merely opening the editor does not change those values.
Native sources belong to the modifier; ordinary Base/Oddball folders are inactive
while it is assigned. Removing it restores ordinary source validation. Shared edits,
copy-for-condition, Cancel, and preset behavior follow the existing modifier rules.

All selected masking conditions run in variant groups, with randomized group order.
Each group contains one independently shuffled pass through its SOAs
per session repetition. This preserves the source's three randomized triplets rather
than shuffling all nine ordinary runs together. Enabling catches adds one extra
full-length sequence at a randomly selected position in each variant block. Its mask
timing is independently sampled from that block's selected SOAs. All ordinary SOA
passes and the catch finish before moving to the next variant. The delivered
Masking 1.3.0 project has twelve actual conditions: nine ordinary SOA conditions,
each repeated three times, and Color/Faces/Number catch conditions, each presented
once. It therefore retains three blocks of ten trials, or 30 trials total.
The first block can be Color, Faces or Number; chance repeats across launches remain
possible. Mixed launches with ordinary non-masking
conditions are rejected explicitly. The group's introduction runs once, questions
after every stream, and thanks once after the final break/fixation. Authored task flow
suppresses Studio's additional start gates, block breaks and completion page.

Select an ordinary Masking condition in **Setup > Conditions**, then choose **Add Catch
Condition**. This creates a real condition with its own stable ID, name and editable
Trigger Code, sharing the selected condition's modifier sources and task bindings.
The list identifies it as a catch with a random SOA; the visible Catch schedule explains
its once-per-variant behavior. Catch conditions are excluded from ordinary SOA passes
and inserted once into their matching block. With ordinary conditions selected, SOA
sampling uses those selected conditions of the same variant. When a catch is launched
alone, it samples from all ordinary same-variant conditions in the project. Eligible
sources are validated before presentation. The delivered catch codes are Color 10,
Faces 11 and Number 12. Creation prefers those codes and selects an unused marker if
needed; the returned condition's Trigger Code remains authoritative.

Studio 2.0.0 automatic-catch projects remain supported. Their Masking-only **Catch
trials** modifier tab enables an implicit extra sequence and its EEG code; it does
not create a condition row. All selected SOA modifiers of that variant must agree on
automatic catch settings. The tab explains this distinction and directs new authoring
to Add Catch Condition. A variant cannot mix automatic and explicit catches or contain
multiple explicit catch conditions. Creation is disabled with an explanation when
automatic catches are enabled; disable them explicitly before adding a visible catch.
It never rewrites other modifiers automatically. Apply, Cancel, shared assignments,
independent copies and local presets retain their existing draft behavior.

Catch sequences omit every target flash while preserving the base/mask stream,
overlays, static fixation and total duration. They carry no target identity. The four
identification choices remain available, but catch identity accuracy is unscored.
PAS measures perceived presence: **No experience** is a correct rejection on a fully
presented catch; a higher PAS rating is a false alarm. Edit modifier screens to explain
possible absence before using catches. Adding a catch does not rewrite custom
instructions. The delivered project explicitly explains possible absence, honest
visibility ratings, guessing on the separate identity question, and blinking/resting
during breaks.

Masking 1.3.0 replaces the delivered project's dense instruction paragraph with separate
editable text items: a clear heading, left-aligned content sections and a distinct
Space prompt. The old variant-block heading, including “Faces block”, is removed.
This is a project revision; built-in Masking factory instructions and other saved
projects are unchanged. Instruction steps now expose their display-item table and
preview in the task editor. `TaskDisplayItem.text_alignment` supports left, center and
right alignment within the item's width; X/Y remain the center anchor. Text size,
position, width, color and the step's font remain editable. The redesign preserves
instruction/fixation ordering and the existing response and continuation behavior.

Since Studio 1.9.2, Masking refreshes its seed on every GUI compilation, including retries
after an interrupted session. Each ordinary trial independently samples its target, so chance
repeats remain possible. Explicit core compilation seeds still reproduce a session.
Other experiment families retain their existing seed behavior.

Compilation places each inter-run break's trailing timed fixation immediately before
the next stream, keeping the same visible order and the authored screen properties.
The moved fixation retains its task/modifier identity, while its response record
belongs to the next run's pre-condition phase.
The group's final break/fixation stays before thanks. Engine preparation and previous
run exports therefore finish before the timed fixation starts. Scene playback uses
that prepared cache without adding ordinary blank warmup frames. Timed no-input
records are checkpointed after the stream; participant answers remain immediately
durable. A terminal timed screen ends with a neutral offset before export work.

## Source design and approved migration corrections

At 60 Hz the source design has 12-frame item slots. Base/mask onset is 1, 3 or 6
frames into the slot, lasting six frames. A target occurs at the beginning of every
fifth slot for one frame. There are 200 slots, 40 target flashes and 2400 frames per
ordinary run. A catch retains all 200 slots and 2400 frames, with zero target flashes.
One target is sampled per ordinary run and remains fixed. Faces/Number base and mask
sampling rejects immediate repetitions, including across consecutive runs.

Masking 1.2.0 restored the middle SOA to **50 ms**, retained in 1.3.0, giving windows at
**1, 3 or 6 frames** (16.666667/50/100 ms). The preceding 1.1.0 revision used 33.333333 ms for the
middle SOA. Signed RGB values, circle geometry, source image bytes and other within-run
timing remain unchanged. The face block retains 26 base objects and four exemplars
for each of four emotions; this revision does not expand the pool. Instructions retain
target identification, static red fixation, and keeping eyes open during stimulation,
with breaks for blinking/rest.

Native scene visuals retain signed RGB triples without conversion to eight-bit hex,
authored units, geometry, outlines, fonts and interpolation. The Color preset uses
5-degree base, target and mask circles. The source mixed 5 cm bases with 5-degree
targets/masks: nearly equal at the default 57 cm viewing distance, but the latter
become about 40% wider at 80 cm. Matching all three roles in degrees corrects this
source defect and keeps their relative sizes stable when display calibration changes.
Previously saved projects retain their explicit geometry; correcting the preset does
not silently rewrite custom sources. The migrated Masking project was repaired too.
Number uses native Arial Black text and a gray rectangle behind each base/mask letter.
Faces preserves original JPEG bytes and the authored square 5-by-5-degree display.
Implicit source text wraps are stored explicitly before conversion to pixel units:
one window-height for instructions/breaks/thanks and 15 degrees for option labels.

The user chose the intended design with source defects corrected: parse color-string
triples, sample symbols before drawing/logging, score the valid option click, require
fresh clicks consistently, and synchronize nominal SOAs to display frames. The source
editable files define condition-start markers 1/2/3 for Color/Faces/Number. The migrated
project uses the user-requested nine unique codes instead: Color 1/2/3, Faces 4/5/6,
and Number 7/8/9, each in ascending SOA order (16.6667/50/100 ms in 1.3.0).
Catch codes 10/11/12 identify the target-absent Color/Faces/Number sequences; their
sampled SOA is saved with the trial. In 1.3.0 these codes belong to the three actual
catch conditions. Each condition's saved code becomes its flip-locked stream-start marker and survives
session randomization. Projects without `MaskingSettings.event_triggers` retain this
start-only behavior, including the published Masking 1.3.0 project.
No source CSV format or historical jitter equivalence is claimed.

| Variant | 16.6667 ms | 50 ms | 100 ms | Catch (sampled SOA) |
| --- | --- | --- | --- | --- |
| Color | 1 | 2 | 3 | 10 |
| Faces | 4 | 5 | 6 | 11 |
| Number | 7 | 8 | 9 | 12 |

### Optional target, mask and catch-slot markers

The modifier's optional `event_triggers` object enables within-sequence markers.
`mask_onset_code` defaults to 56 and `catch_slot_onset_code` to 57. Target onset
uses the existing project `oddball_trigger_code` (55 by default, with its existing
explicit nonstandard-code policy). Codes must be distinct from each other and from
condition/automatic-catch start codes. Omitting the object preserves legacy behavior.

| Event | Default code | Frame in each target slot |
| --- | --- | --- |
| Sequence start | Condition's saved code (1–12 in Masking) | Stream frame 0, once |
| Actual target/oddball onset | 55 | Slot start, ordinary sequences only |
| Mask onset | 56 | Slot start plus SOA frames, ordinary and catch sequences |
| Omitted target's scheduled onset | 57 | Slot start, catch sequences only |

At 60 Hz in the delivered design, target slots begin at frames 48, 108, ..., 2388.
Their masks begin 1, 3 or 6 frames later. Ordinary sequences contain one start marker
and 40 pairs of 55 then 56; catches contain one start marker and 40 pairs of 57 then
56. Code 57 never represents a displayed target or replaces the catch condition's
start code. Base slots, target offsets, questions and answers receive no new markers.
The full 30-sequence design therefore schedules 2,430 events: 30 starts, 1,080 targets,
1,200 masks and 120 omitted-target slots.

Compilation changes only the generic `TriggerEvent` list. The existing engine emits
each event through its display-flip callback and existing trigger backend; scene
frames, stimulus sampling, participant questions, scoring and hardware pulse behavior
remain unchanged. Separate events support target/mask EEG alignment, but do not by
themselves separate overlapping neural responses or establish optical timing.

The delivered project's display geometry was explicitly selected by the user:
80 cm viewing distance, 60.96 cm screen width and 1920x1080 at 60 Hz. It replaces the
source's uncalibrated testMonitor profile. Numeric source colors and geometry do not
establish optical equivalence on an unmeasured monitor.

## Ownership, schemas and results

- `core/masking.py` owns modifier settings, explicit catch creation/validation and exact frame compatibility;
  `masking_presets.py` owns editable native defaults and explicit timing setup.
- `compiler_masking.py` owns seeded sampling and frame events;
  `scene_models.py` is the engine-neutral visual/event contract. `RunSpec.scene_stream`
  is single-condition; pre/post tasks remain on `SessionEntry`.
- `engines/psychopy_scenes.py` prepares native visuals and draw calls before playback,
  reusing condition-local resource ownership. Tasks use native circles and explicit
  opt-in linear-degree geometry; old tasks retain their previous geometry and defaults.
- `task_assets.py`, modifier presets and project interchange own contained source
  copies. Every masking image belongs beneath the first pre-task's asset directory.
- Runtime owns task input, scoring and durable scene/task provenance. Planned event
  timestamps must never be reported as observed display times.

Masking without catches retains project schema 1.7.0, config 1.5.0, RunSpec 1.4.0 and
SessionPlan 1.3.0. Legacy automatic catches use project/config **1.8.0/1.6.0**. Explicit
`Condition.masking_catch` flags and non-centered task text require project/config
**1.9.0/1.7.0**. False condition flags and default-centered text alignment are omitted
from legacy payloads. Projects saved at a newer supported schema retain that version.

Both catch representations compile to the existing **RunSpec 1.5.0** catch scene;
ordinary runs retain 1.4.0. Sessions with catches but no non-centered task text use
**SessionPlan 1.4.0**. Compiled non-centered task text requires **SessionPlan 1.5.0**.
Modifier presets containing it require **1.2.0**; centered Masking presets, including
legacy automatic catches, retain 1.1.0. Strict schema/settings guards reject unsupported
behavior in older readers instead of silently dropping it.

Opt-in `event_triggers` requires project/config **1.10.0/1.8.0** and modifier preset
**1.3.0**. Generic compiled trigger events need no new RunSpec or SessionPlan schema.
The marker-enabled project requires Studio 2.2.0; Studio 2.1.0 does not support these
new authoring settings. Masking 1.4.0 uses this capability while retaining the prior
stimulus timing, block randomization and participant questions.

Masking 1.4.0 is the current Library listing; 1.3.0 was unlisted while its historical
release assets were retained. See the [release record](exec-plans/completed/masking-1.4-release.md)
for artifact checks and the unrun GUI/hardware acceptance boundaries.

The Masking 1.3.0 Library project requires **Studio 2.1.0** for visible catch conditions
and aligned instruction text. The preceding Masking 1.2.0 remains a Studio 2.0.0
automatic-catch project. Project-only revisions do not otherwise require
the newest Studio release: the minimum version reflects the features actually used.

New sessions write `logs/masking_trials_v2.csv`, joining each attempted trial's compiled target
(including face image path or text/RGB), expected and selected answer, correctness,
reaction time, SOA, seed and EEG code with `is_catch_trial`, PAS rating/selection,
PAS validity/abort/response-time evidence and `detection_outcome`. Existing
`masking_trials_v1.csv` files remain untouched. The v2 table is written in both export modes on session
finalization, including graceful aborts. Absent/aborted answers have blank correctness;
valid wrong ordinary identity answers have `False`. Catch rows have blank target and
expected-answer fields, zero target flashes, and blank identity correctness regardless
of the selected option. Explicit catch rows retain their own condition ID/name and
trigger code; the sampled source SOA is recorded separately. PAS detection is separate
from identity correctness:

- A fully presented catch with PAS 1 yields `correct_rejection`; PAS 2–4 yields
  `false_alarm`. Partial catch exposure is unscored.
- An ordinary run with at least one completed target flash yields `miss` for PAS 1
  or `hit` for PAS 2–4. These labels describe reported presence, not identification accuracy.
- Missing, invalid or aborted PAS responses have blank detection outcomes.

`target_presented` and `target_flashes_completed` describe completed-frame evidence,
not measured optical onset. The existing compiled
plan checkpoint is saved before input; response JSONL journals flush immediately
after each response, preserving evidence even before this joined CSV is finalized.

## Verification and visible acceptance

Run compiler, project-io, runtime, engine and GUI focused routes, then repo precommit.
Tests independently check source frame windows, fixed targets, no-repeat continuity,
three shuffled SOA passes, spatial option randomization, answer linkage, exact RGB,
native constructors, copy/relocation, stale schema rejection, and task/session flow.
Catch coverage checks one extra sequence per complete variant block, random insertion
and SOA selection, absent targets with retained timing/masks, distinct markers,
unscored identity and PAS detection outcomes with incomplete/aborted exposure. Explicit
condition tests cover twelve saved rows versus thirty runs, standalone catch source
selection, legacy automatic-catch compatibility and rejection of double-catch designs.
Task text tests cover alignment propagation, centered-payload compatibility, native
constructor arguments and project/preset/session schema guards.

Registered GUI tests require a user-approved visible environment. Check both themes
at the modifier dialog's 1100x720 minimum, source editor's documented minimum and
Setup's 1120x820: all three presets, long image paths, source/answer editing, Apply,
Cancel, shared assignment, copy, preset reload and modifier removal. At both 1100x720
and 1120x760, inspect all four Masking tabs and the Catch trials enabled/disabled states,
trigger persistence, matching-SOA guidance and participant-instruction reminder.
The tab must remain hidden for other modifier kinds. In Setup Conditions, inspect Add
Catch Condition, the actual saved rows and editable markers, the visible scheduling
summary, and disabled-action explanations when an automatic or explicit catch already
exists. Verify save/reopen and unchanged shared modifiers. In the task editor, inspect
Instruction display items, left/center/right alignment, hierarchy and the Space prompt;
Apply/Cancel must preserve authored content and geometry. Confirm Home
is ready with complete masking pools and that ordinary source editors do not claim
to control those visuals. Physical acceptance must verify Open Sans/Arial Black,
circle edges and hit testing, the restored 1/3/6-frame SOAs, target-absent catches,
final break/cross, and EEG start markers 1–12 on the intended monitor and serial device.
Registered Qt and visible/manual acceptance remain unrun for this revision; focused
non-Qt checks do not establish visible layout or physical timing/EEG acceptance.
No offscreen Qt or physical PsychoPy playback is part of the default local check.
