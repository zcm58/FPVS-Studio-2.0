# Experiment Categories

FPVS Studio saves one immutable `ProjectFile.experiment_category` for an entire
experiment. Supported values and behavior are:

| Category | Authoring and playback |
| --- | --- |
| FPVS | Base-only concept; disabled Coming soon choice. Creation and compilation are blocked. |
| FPVS-Oddball | Existing image/word oddball protocols, presentation modes, tasks and runtime behavior. |
| Attentional-Blink | Continuous 10 Hz digit streams with letter targets at 100, 300, and 500 ms SOAs. Existing image-pair designs retain their within-slot ISI editor and playback. |

## Creation and shared Setup

The first page of new-experiment Setup asks only for the category. Nothing is
selected initially. Name, folder and compatible experiment-template choices follow
on the next page; Cancel creates no project. Category becomes locked when the
experiment is created and appears read-only on Project. Changing category requires
creating a new experiment. Templates carry their own category and cannot change an
experiment's category. Editing a template preserves that category and its cadence.

The guided steps are Project, Conditions, Design, Timing, Image Size, Session,
Fixation, Response and Review, fitting `1120x820`. Character Size replaces Image Size
for native letter streams. Conditions handles identity,
participant instructions/tasks and existing oddball word lists. Design embeds the
shared visual image editor and image-folder selection for the selected condition.
Image intake/normalization occurs when advancing from Design. Word-list presentation
rates remain editable in Timing. Shared display, session, fixation and response
surfaces retain their existing ownership.

New AB experiments select **Digits & letter targets** and start with three conditions:

| SOA, onset to onset | Target lag | Intervening digits | T1 slot | T2 slot |
| --- | --- | --- | --- | --- |
| 100 ms | 1 | 0 | 15 | 16 |
| 300 ms | 3 | 2 | 13 | 16 |
| 500 ms | 5 | 4 | 11 | 16 |

Slots are numbered from one. Each native character lasts 100 ms, without blank gaps.
The 20-character cycle lasts two seconds, with four digits after T2. Shared sources
are digits 2–9 and separate uppercase letter pools for T1/T2. T1 defaults to red,
T2 and digits to white, on black. Seeded sampling avoids adjacent repeated digits
and identical letters within a target pair. Sampling is not per-character balanced.
The fixation detection task is disabled for this preset. Existing cycle-repeat and
session defaults are preserved; two seconds is the cycle length, not a recording block.

Design shows shared character sources, editable SOAs, intervening-digit counts, and
a full-cycle timeline with labelled T1/T2 and an onset-to-onset bracket. A quarter-speed
preview illustrates the sequence. Native text height is edited in Character Size;
Timing checks the selected display's exact 10 Hz frame grid. A 60 Hz display uses six
frames per character; 120/240 Hz also fit. 59.94/144 Hz are rejected for this layout,
without silently rounding or alternating character durations.

The shared post-condition questionnaire asks whether any white letters were noticed,
with Yes/No/Unsure answers after each completed condition entry. These are subjective
block reports, not target-identification accuracy or evidence of unconscious processing.
The repeating FPVS extension requires behavioral and physical timing validation.
Both targets repeat at 0.5 Hz; different event markers do not separate their frequency tags.

The **Image pairs (legacy)** template retains 4 Hz, four-slot creation and the
T1/separator/T2 compound slot (50/50/150 ms by default). Existing saved projects keep
their settings and image folders. Blank or image ISI remains available only there.
An experiment cannot mix the letter-stream and within-slot layouts.

Design edits apply before switching conditions, leaving the step or saving. Invalid
drafts remain visible for correction. Folder imports continue to use workers and
update project-owned sources immediately, including long Windows paths. Scientific
timing and source-validation rules stay in core, not widget handlers.
Embedded thumbnail decoding waits until Design is visible; edits and saves on other
pages keep source counts current without starting hidden image jobs.

## Legacy projects and separation

Project schema `1.4.0` adds category ownership. Older files without a category infer
Attentional-Blink when any condition contains AB timing, otherwise FPVS-Oddball.
Opening migrates in memory without rewriting files. The old shared built-in template
ID is not used to infer category.

Incompatible legacy conditions remain recoverable in Setup. Core category checks
block mixed projects at save, configuration export, bundle validation and compilation,
including attempts to compile only a compatible subset. GUI edits cannot introduce
another category or silently convert an old oddball condition into AB timing.

For a mixed AB/oddball project, Conditions offers **Separate oddball conditions...**.
After the user chooses this action, the backend creates a new sibling FPVS-Oddball
experiment, copies project-contained image/task assets, and saves the original with
only its AB conditions. Cadence and condition timing are retained. Source images and
historical run records in the original are untouched; old runs are not attributed to
the new experiment. Existing sibling folders are never overwritten. The new sibling's
`cache/legacy-mixed-project.json` and optional `cache/legacy-mixed-manifest.json` retain
the complete pre-separation authoring snapshot, including dormant T2 associations.
The original project JSON is replaced only after the new experiment is written.
Missing populated folders, missing referenced manifest images and a manifest from
another project stop separation before creating files. Empty draft pools are allowed.
Failed copies leave the original JSON intact and remove only their new destination.

An old FPVS-Oddball project with only dormant T2 assignments offers **Clear unused
T2 assignments...** instead. Confirmation removes those unused associations while
retaining every image file, source set and ordinary setting. Saving remains explicit.

## Ownership and verification

- `core/models.py`, `enums.py`, `migrations.py` and `experiment_categories.py` own
  persisted categories, inference and homogeneous-project checks.
- `core/project_service.py`, `condition_template_profiles.py`, `project_config.py`
  and `project_bundle.py` propagate category through supported creation/interchange.
- `core/project_separation.py` owns explicit legacy separation and rollback.
- GUI creation, document bindings and the shared designer enforce the same rules.
- `core/attentional_blink_presets.py` assembles the default study and visibility task.
  `core/attentional_blink_stream.py` describes the exact character grid;
  `core/compiler_attentional_blink_stream.py` compiles native character events.
- Letter streams use project schema `1.5.0`, `.fpvsconfig` and `RunSpec` `1.3.0`.
  Legacy project and run versions remain supported without changing saved timing.
  Template-library schema `1.2.0` preserves explicit layout in custom profile copies.
- The existing engine text cache and frame loop render character events. Runtime
  revalidates exact coverage and markers, and writes
  `attentional_blink_stream_events_v1.csv` separately from legacy image-pair exports.
  It includes symbols, phases, cycle/slot, requested/achieved SOA, and observed onsets.
  Session exports include block/order; individual run exports join them using `run_id`.

Run focused core/project-I/O verification, the shared precommit tier and registered
category/designer/setup Qt tests in an approved visible environment. Real presentation
and hardware timing verification remain separate from the visible authoring checks.
