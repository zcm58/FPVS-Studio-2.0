# Visual FPVS Experiment Designer

Updated: 2026-09-09. The experimental branch implements a shared, category-specific
image designer and custom within-slot attentional-blink playback. The primary editor
is embedded in Setup > Design. Backward masking is historical research context and
has no current GUI. Physical display/trigger verification remains separate from
visible authoring checks.

## Current Designer Workflow

Choose FPVS-Oddball or Attentional-Blink when creating an experiment. The category
is fixed for that experiment; see [Experiment Categories](EXPERIMENT_CATEGORIES.md)
for creation, templates and legacy separation rules. The designer has no category
switcher, mode tabs or backward-masking controls.

Use Setup > Conditions for condition names, modality, instructions and tasks, then
Setup > Design for image folders and the repeating sequence. Design includes a
condition selector and the shared `ExperimentDesignerWidget`. Its compact layout is
budgeted at `1000x600` inside the nine-step `1120x820` wizard. The optional standalone
`ExperimentDesignerDialog` hosts the same widget at `1040x760` minimum and `1400x920`
default; it does not implement a separate authoring flow. Word conditions retain
their existing word-list editors in Conditions and cadence settings in Timing.

FPVS-Oddball shows Base and Oddball source cards. Attentional-Blink shows
Base, T1, ISI and T2 sources, plus the expanded target slot and T1/ISI controls.
Thumbnails are decoded on a worker from imported images; no example image is substituted for a missing
source. Drag or click a thumbnail to add a role. Folder buttons are separate hit
targets. They import into fresh project-owned source sets so changing folders does
not merge old and new images. Short folder names appear beneath the previews, with
full paths available through tooltips and accessible descriptions. Folder imports
immediately update this condition's document draft and copy files into its project;
the project file is saved through the normal Setup save action. Explicitly discarding
an unapplied design restores timing and cycle settings from the document while
preserving imported image pools. Standalone Cancel follows the same timing-only rule.
Windows import, inspection, thumbnail decoding and asset checks use extended-length
filesystem paths, preserving original filenames and bytes even in deeply nested project
folders. This filesystem detail never enters persisted project-relative image paths.

The Repeating stream overview shows equal-duration slots. A valid AB cycle has at least one Base
slot followed by exactly one target pair. Its three overview thumbnails are labeled
Schematic and remain readable even with a short T1 duration. A connector and
Inside the target pair heading identify the expanded view and its slot number.
Only the expanded target slot shows proportional
T1, separator, and T2 phases. Edit T1 and ISI; T2 fills the remaining normal slot.
Zero/negative phases and overfull slots cannot be applied. Choose Image or Blank screen
using the visible two-option ISI control. Base, T1, T2 and image ISI
have separate folder controls and independent pools. Blank uses the configured display
background while preserving fixation behavior. Existing files without the new ISI
mode retain their base-source separator through an explicit legacy reference migration. Each source block represents
a pool, not a prescribed fixed image order. Delete, Alt+Left/Right and the context menu
provide alternatives to dragging for removing or moving selected slots.

New AB experiments default to 4 Hz and three Base slots plus a target pair. Opening
the designer preserves an existing experiment's saved cadence, cycle and condition
timing:

```text
Base 250 ms | Base 250 ms | Base 250 ms | T1 50 ms -> separator 50 ms -> T2 150 ms
0           250           500           750         800                850    1000
```

This is four normal slots and six phase onsets per one-second cycle (five image
onsets when the ISI is blank). Each target
recurs at 1 Hz; T1-to-T2 onset separation is 100 ms. Increasing ISI reduces T2 exposure
because the enclosing slot remains fixed. This is a user-selected custom design,
not a claim that the timing reliably produces an attentional blink.

**Preview at ¼ speed** illustrates the authored sequence at 4x slower speed. Editing,
closing, or stopping cancels its timer. **Timing & display details** opens a separate
small dialog with optional display refresh and achieved frame timing; only AB shows
the T2 marker. FPVS-Oddball's 50% Blank mode previews both image and blank phases.
Its Contrast Modulation preview explicitly states that contrast modulation is omitted
from the slowed sequence illustration.
This calculation does not measure or change display settings. At 60 Hz, the default
slot compiles to 15 frames: 3 T1 + 3 separator + 9 T2. T2 takes remaining whole frames;
compilation rejects any phase shorter than one achieved frame. Real display verification
remains in Setup > Timing.

**Next** is the embedded editor's single primary action. It applies this condition's
AB settings and the project-wide cadence atomically; in FPVS-Oddball it applies the
ordinary cycle and cadence. The optional standalone editor retains **Use this design**.
Save from Setup
as usual. Pending edits are applied before switching conditions, leaving Design or
saving. Invalid edits remain available for correction; the error replaces the invalid
target-slot visualization without growing the compact layout. An explicit discard
action restores the document's timing. Other AB conditions are validated against
changed cadence, but their empty draft pools do not prevent editing the current
condition. Each selected image condition needs its own required pools before advancing
through Design. Image readiness checks and normalization follow Design.

Folder imports run on workers and block navigation while they mutate source state.
The embedded editor defers thumbnail decoding while hidden. Source counts update
immediately; showing Design loads the latest pending revision. Saving on another
page does not start hidden thumbnail work.
Thumbnail decoding also uses a worker, but does not delay applying or saving valid
source/timing settings. Hidden embedded editors defer decoding until Design is shown;
source counts and timing still refresh immediately. Preview waits for thumbnails.
Switching conditions, closing
or replacing the editor waits until both workers finish; no worker is torn down with
its widget. `DesignSetupStep` exposes pending/apply/discard and import/busy state for
the wizard to enforce these boundaries.

## Research Question and Terminology

The initial request described reduced recognition of T1 after a following mask.
The user subsequently corrected the intended paradigm to attentional blink and
approved the custom within-slot design above, including actual experimental playback.
Attentional blink ordinarily concerns impaired report of a later T2 after attending
to T1 in an RSVP stream. Both T1 and T2 are targets in the implemented AB category.
The original blink study also found that replacing the item immediately after T1
with a blank changed the effect. [Raymond, Shapiro & Arnell, 1992](https://pubmed.ncbi.nlm.nih.gov/1500880/).

- **Target duration:** T1 onset to T1 offset.
- **Interstimulus interval (ISI):** T1 offset to T2 onset. In the custom AB design,
  one selected ISI image or the display background fills this interval.
- **Stimulus onset asynchrony (SOA):** T1 onset to T2 onset.
- For sequential, nonoverlapping images: `SOA = target duration + ISI`.

These endpoints must be visible in the timeline and any future exported metadata.
Mask duration is separate. Timing definitions and experiments show why comparing ISIs
without controlling durations can change the interpretation.
[Macknik & Martinez-Conde, 2007, author review](https://pmc.ncbi.nlm.nih.gov/articles/PMC2864985/);
[Macknik & Livingstone, 1998, primary experiment](https://pubmed.ncbi.nlm.nih.gov/10195130/).

## Evidence That Constrains the Design

An arbitrary second picture is not guaranteed to suppress the first. Target/mask
contrast, duration, composition and spatial relationship matter. Spatially adjacent,
nonoverlapping metacontrast differs from an overlapping pattern mask; masking
functions can have different shapes rather than a universal monotonic recovery.
Choose and pilot the actual assets against the intended target task.
[Öğmen et al., 2006](https://pubmed.ncbi.nlm.nih.gov/17081585/).

FPVS already has relevant timing evidence. Retter and colleagues compared 50-ms
images with 50-ms blanks at 10 Hz, 100-ms images without blanks at 10 Hz, and 50-ms
images without blanks at 20 Hz, while faces remained at 1 Hz. This separates some
duration, gap and rate comparisons; it does not validate a dedicated target-mask
pair or supply an invisibility threshold.
[Retter et al., 2018, author manuscript](https://dial.uclouvain.be/pr/boreal/object/boreal:222114/datastream/PDF_01/view).

Frequency-tagged discrimination is not automatically successful identity recognition
or subjective awareness. A face-category response answers a different question from
recognizing a particular face. Retter et al. related neural responses to behavioral
categorization and explicitly distinguished categorization from extracting all face
information. [Retter et al., 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7339021/).
More recent work related frequency-tagged face signals to correct gender reports,
visibility and confidence under specific contrast conditions; those behavioral
measurements established the relationship rather than assuming it from amplitude.
[Mazancieux, Cleeremans & de Heering, 2026, abstract](https://pubmed.ncbi.nlm.nih.gov/41934781/).

Accordingly, define “recognition” before testing: category discrimination, identity
recognition, or visibility. Include an appropriate behavioral task, potentially in
matched separate blocks so responses do not interrupt the periodic train. Do not
label the preview's expected EEG outcome “recognized” or “unrecognized.” A nonsignificant
frequency response alone is not proof of absent recognition.

## Historical Backward-Masking Preview Model

This section retains the research and timing model from the initial prototype.
It is not a supported experiment category or an accessible GUI preview. Existing
masking arithmetic in `core/experiment_design.py` does not imply current authoring or
playback support.

Preserve a constant T1 onset cadence. For slot length `P`, target duration `D`,
blank gap `G` and independently chosen mask duration `M`, preview:

```text
T1 for D frames -> blank for G frames -> mask for M frames
-> remaining blank for P-D-G-M frames -> next T1
```

Require `D >= 1`, `G >= 0`, `M >= 1`, and `P-D-G-M >= 0` after frame conversion.
Oversized combinations produce an error rather than changing another value. Holding
T1 and T2 durations fixed across ISIs avoids a mask-duration confound. Increasing ISI
shortens the remaining blank, however, changing the mask-to-next-target interval and
therefore the next target's preceding context. This still needs experimental control.

For example, at 120-Hz display refresh, a 24-frame slot gives 5 T1 onsets/second.
A 3-frame target, 3-frame ISI and 6-frame mask leave 12 blank frames: 25-ms target,
25-ms ISI, 50-ms SOA, 50-ms mask and 100-ms remaining blank. This arithmetic explains
the preview; it is not a recommended masking threshold.

Two images per slot yield ten image onsets/second on average here, but their onset
separations alternate between 50 and 150 ms. Do not call that uniform 10-Hz image
presentation. The repeating pair has a 5-Hz cycle. If every fifth T1 is an oddball,
its onset recurrence is 1 Hz, but masks must not themselves carry systematic
category differences at that frequency.

Keep ISI constant within a condition and compare conditions initially. Random gaps
would alter the mask phase and stimulus spectrum. Nonperiodic category appearances
can remove the ordinary category frequency tag even while categorization remains;
event-aligned analysis then needs a distinct method.
[Quek & Rossion, 2017](https://doi.org/10.1016/j.neuropsychologia.2017.08.010).

## Implementation and Acceptance

Use the existing ownership map: editable settings in `core/models.py`, compilation
in `core/compiler.py` and `core/compiler_schedules.py`, frame contracts in
`core/run_spec.py`, authoring in `gui/`, playback in `engines/`, and result assembly
in `runtime/` using `core/execution.py`. Follow the
[execution-plan rules](exec-plans/README.md) before extending these contracts.

`core/attentional_blink.py` owns requested and achieved AB timing;
`core/compiler_attentional_blink.py` expands compound slots. Ordinary cycle mathematics
and the historical masking model remain in `core/experiment_design.py`.
`gui/design_setup_step.py` owns condition selection and pending-edit integration.
`gui/experiment_designer_dialog.py` owns the shared category-locked widget and its
optional standalone host; `gui/experiment_designer_widgets.py` owns native source,
cycle and proportional-slot visuals. Worker source intake and thumbnails use
`gui/designer_sources.py`. Persistent category and legacy rules belong to
[Experiment Categories](EXPERIMENT_CATEGORIES.md).

The compiled AB contract, independent T2 rendering geometry, onset records, and export
format are documented in the linked runtime/contract documents in
[the architecture map](../ARCHITECTURE.md). Existing fixation and response-task
ownership remains unchanged; this feature does not add automatic T1/T2 identification
scoring or claim that a frequency response proves recognition.

Focused tests cover exact frame boundaries, persistence/portable sources, separate
target markers, runtime preflight/rendering/export, and unchanged ordinary schedules.
Registered `test_experiment_designer.py` and `test_design_setup_step.py` coverage includes
coordinate folder clicks for both categories, draft/apply/discard behavior, condition
selection, missing pools, worker/preview lifecycle, long Windows image paths, and exact
embedded/standalone geometry in light and dark themes. Wizard/category integration
coverage checks the complete Setup flow. These checks require an approved visible Qt
environment. Physical display and trigger timing still require a presentation-machine
check. Research claims need an appropriate behavioral task and comparison conditions.

The embedded Design surface has no outer frame. Setup defaults to 1120x820; the
expanded target diagram retains readable thumbnails and spacing. Other Setup steps
retain their existing compact layout. ISI source paths follow the same project-relative
import, manifest, normalization, configuration and bundle lifecycle as T2. Blank
separator events carry `is_blank=true` and no image path; they occupy their compiled
frames without allocating or drawing a stimulus image. CSV phase rows retain the
separator timing with an empty image path. Physical timing still requires display
verification on the experiment computer.

Source controls run left to right as Base, T1, ISI, T2. Source, cycle and timing
groups use spacing instead of nested card borders; individual stimulus blocks and
editable fields retain their visual boundaries. Cadence, T1 duration and ISI duration
are typed numeric entries with unit suffixes, validation and no arrow/wheel stepping.
T2 remains an automatically calculated value, labeled accordingly and displayed as
plain text rather than another editable field.

Setup > Design uses the task-specific title Design your sequence and Step 3 of 9.
Its header, source shelf and timelines share the available workspace width; other
Setup steps retain their existing compact shell. Return Home, Back and Next remain
in the bottom navigation with a Design-only explanation that Next applies changes.
Typed draft changes update navigation validity without applying or saving them.
Visible acceptance also covers the expanded `1448x1086` mockup size, both themes,
image/blank ISI, source-folder hit targets, invalid timing and tiny T1 durations.
