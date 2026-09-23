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

All selected masking conditions run in variant groups, ordered by the first condition
of each variant. Each group contains one independently shuffled pass through its SOAs
per session repetition. This preserves the source's three randomized triplets rather
than shuffling all nine runs together. Mixed launches with ordinary non-masking
conditions are rejected explicitly. The group's introduction runs once, questions
after every stream, and thanks once after the final break/fixation. Authored task flow
suppresses Studio's additional start gates, block breaks and completion page.

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
run. One target is sampled per run and remains fixed. Faces/Number base and mask
sampling rejects immediate repetitions, including across consecutive runs.

Native scene visuals retain signed RGB triples without conversion to eight-bit hex,
original units, geometry, outlines, fonts and interpolation. The color source uses
5 cm base circles and 5 degree target/mask circles; that distinction is preserved.
Number uses native Arial Black text and a gray rectangle behind each base/mask letter.
Faces preserves original JPEG bytes and the authored square 5-by-5-degree display.
Implicit source text wraps are stored explicitly before conversion to pixel units:
one window-height for instructions/breaks/thanks and 15 degrees for option labels.

The user chose the intended design with source defects corrected: parse color-string
triples, sample symbols before drawing/logging, score the valid option click, require
fresh clicks consistently, and synchronize nominal SOAs to display frames. The source
editable files define condition-start markers 1/2/3 for Color/Faces/Number. They become
flip-locked stream-start markers; no base/target/mask onset markers are added. Existing
hardware transport is unchanged. The ordinary oddball marker setting stays 55 and is
unused by masking. No source CSV format or historical jitter equivalence is claimed.

The delivered project's display geometry was explicitly selected by the user:
80 cm viewing distance, 60.96 cm screen width and 1920x1080 at 60 Hz. It replaces the
source's uncalibrated testMonitor profile. Numeric source colors and geometry do not
establish optical equivalence on an unmeasured monitor.

## Ownership, schemas and results

- `core/masking.py` owns modifier settings and exact frame compatibility;
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

Masking requires project schema 1.7.0, config 1.5.0, preset 1.1.0, RunSpec 1.4.0,
and SessionPlan 1.3.0. Existing ordinary payloads omit unused extensions and retain
their previous schema and seeded compilation. Older installed builds cannot load
Masking; use the source feature branch until a release is built.

## Verification and visible acceptance

Run compiler, project-io, runtime, engine and GUI focused routes, then repo precommit.
Tests independently check source frame windows, fixed targets, no-repeat continuity,
three shuffled SOA passes, spatial option randomization, answer linkage, exact RGB,
native constructors, copy/relocation, stale schema rejection, and task/session flow.

Registered GUI tests require a user-approved visible environment. Check both themes
at the modifier dialog's 1100x720 minimum, source editor's documented minimum and
Setup's 1120x820: all three presets, long image paths, source/answer editing, Apply,
Cancel, shared assignment, copy, preset reload and modifier removal. Confirm Home
is ready with complete masking pools and that ordinary source editors do not claim
to control those visuals. Physical acceptance must verify Open Sans/Arial Black,
circle edges and hit testing, the 1/3/6-frame SOAs, final break/cross, and EEG start
markers on the intended monitor and serial device. No offscreen Qt or physical
PsychoPy playback is part of the default local check.
