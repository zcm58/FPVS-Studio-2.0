# Experiment Categories

FPVS Studio saves one immutable `ProjectFile.experiment_category` for an entire
experiment. Supported values and behavior are:

| Category | Authoring and playback |
| --- | --- |
| Standard FPVS | Base-only concept; disabled Coming soon choice. Creation and compilation are blocked. |
| FPVS Oddball Paradigm | Existing image/word oddball protocols, presentation modes, tasks and runtime behavior. |
| Cognitive Load FPVS | Three paired image conditions with/without backward counting, a session-first baseline and reusable pre/post modules; see [Cognitive Load FPVS](COGNITIVE_LOAD_FPVS.md). |
| Attentional-Blink | Five-second bursts of white letters, green T1 digits and white T2 digits at 100, 300, and 500 ms SOAs. Image pairs are unsupported. |

## Creation and shared Setup

The first page of new-experiment Setup asks only for the category. Nothing is
selected initially. Name, folder and compatible experiment-template choices follow
on the next page; Cancel creates no project. Category becomes locked when the
experiment is created and appears read-only on Project. Changing category requires
creating a new experiment. Templates carry their own category and cannot change an
experiment's category. Editing a template preserves that category and its cadence.

The guided steps are Project, Conditions, Design, Timing & Session, Image Size,
Fixation, Response and Review, fitting `1120x820`. Character Size replaces Image Size
for native letter streams. Conditions handles identity,
participant instructions/tasks and existing oddball word lists. Design embeds the
shared visual image editor and image-folder selection for the selected condition.
Image intake/normalization occurs when advancing from Design. Word-list presentation
rates remain editable in Timing. Shared display, session, fixation and response
surfaces retain their existing ownership.

The fixation cross is off by default. Users can enable it in Setup > Fixation;
opening an existing project preserves its saved choice. Oddball defaults are unchanged.

New AB experiments start with three conditions:

| SOA, onset to onset | Target lag | Intervening letters | T1 slot | T2 slot | Condition trigger |
| --- | --- | --- | --- | --- | --- |
| 100 ms | 1 | 0 | 30 | 31 | 1 |
| 300 ms | 3 | 2 | 28 | 31 | 3 |
| 500 ms | 5 | 4 | 26 | 31 | 5 |

Slots are numbered from one. At the default 10 Hz, each native character lasts 100 ms,
without blank gaps. A burst contains 50 characters and exactly one T1/T2 pair.
T1 is green, T2 and the letter distractors are white, and the background is black.
Each burst draws new target identities; T1 and T2 must differ. Seeded sampling
avoids adjacent repeated distractors. Target sampling is not per-digit balanced.
Fixation detection is disabled. The preset uses 24 bursts per SOA, giving 120 seconds
of EEG per SOA and 72 bursts (360 seconds of stimulus presentation) overall.
Response time is additional. **Bursts per SOA** is editable in the GUI.

Design shows a shared editable presentation rate, character sources, SOAs, intervening-letter counts, and
a target-focused timeline with labelled T1/T2 and an onset-to-onset bracket. A quarter-speed
preview illustrates the sequence. Native text height is edited in Character Size;
Timing checks the selected display's exact frame grid at the authored presentation
rate. Rate edits retain authored SOAs, which must span whole character intervals.
New burst studies retain five seconds when the rate changes; the burst and target
positions must still fall on an exact character grid.
At the default 10 Hz, a 60 Hz display uses six frames per character; 120/240 Hz also
fit, while 59.94/144 Hz do not. Other positive finite rates are supported when exact
for the display, burst duration and authored SOAs. Timing is
never silently rounded or alternated between character durations.

The balanced pool of bursts is shuffled across the whole session. Each burst is
one compiled session entry, followed by **What was the green number?** and
**What was the second number?** Correct answers come from that entry's actual
compiled target digits. Participants type each answer and submit with Enter or
**Next**. Every burst requires Space at the readiness screen. Runtime records and
scores the two answers independently, including in Experiment Test Mode.
The chronological burst number remains available for learning-over-time analyses.
See [runtime reporting](RUNTIME_EXECUTION.md#attentional-blink-recall-results)
for files, partial responses and Excel export.

Existing saved native studies retain their digit distractors, letter targets,
timing, tasks and session settings. They are not silently converted to the new
burst preset. Physical display and trigger timing require hardware validation.

Image-pair AB templates, including saved custom copies, are not offered or applicable.
Old project and RunSpec records remain readable for identification, without rewriting
or deleting their images. They cannot be saved, exported, compiled or run. Create a
new Attentional-Blink experiment; timing and stimuli are never silently converted.
Mixed projects containing retired image pairs cannot use the separation action.

Design edits apply before switching conditions, leaving the step or saving. Invalid
drafts remain visible for correction. Folder imports continue to use workers and
update project-owned sources immediately, including long Windows paths. Scientific
timing and source-validation rules stay in core, not widget handlers.
Embedded thumbnail decoding waits until Design is visible; edits and saves on other
pages keep source counts current without starting hidden image jobs.

## Legacy projects and separation

Project schema `1.4.0` adds category ownership. Older files without a category infer
Attentional-Blink when any condition contains AB timing, otherwise FPVS Oddball Paradigm.
Opening migrates in memory without rewriting files. The old shared built-in template
ID is not used to infer category.

Incompatible legacy conditions remain recoverable in Setup. Core category checks
block mixed projects at save, configuration export, bundle validation and compilation,
including attempts to compile only a compatible subset. GUI edits cannot introduce
another category or silently convert an old oddball condition into AB timing.

For a mixed native letter-stream AB/oddball project, Conditions offers **Separate oddball conditions...**.
After the user chooses this action, the backend creates a new sibling FPVS Oddball Paradigm
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

An old FPVS Oddball Paradigm project with only dormant T2 assignments offers **Clear unused
T2 assignments...** instead. Confirmation removes those unused associations while
retaining every image file, source set and ordinary setting. Saving remains explicit.

## Ownership and verification

- `core/models.py`, `enums.py`, `migrations.py` and `experiment_categories.py` own
  persisted categories, inference and homogeneous-project checks.
- `core/project_service.py`, `condition_template_profiles.py`, `project_config.py`
  and `project_bundle.py` propagate category through supported creation/interchange.
- `core/project_separation.py` owns explicit legacy separation and rollback.
- GUI creation, document bindings and the shared designer enforce the same rules.
- `core/attentional_blink_presets.py` assembles the default burst study and recall task.
  `core/attentional_blink_stream.py` describes the exact character grid;
  `core/compiler_attentional_blink_stream.py` compiles native character events.
- Letter streams use project schema `1.5.0`, `.fpvsconfig` and `RunSpec` `1.3.0`.
  Legacy records remain decodable; retired image-pair layouts cannot run.
  Template-library schema `1.2.0` preserves explicit layout in custom profile copies.
- The existing engine text cache and frame loop render character events. Runtime
  revalidates exact coverage and markers, and writes
  `attentional_blink_stream_events_v1.csv` separately from legacy image-pair exports.
  It includes symbols, phases, cycle/slot, requested/achieved SOA, and observed onsets.
  Session exports include block/order; individual run exports join them using `run_id`.

Run focused core/project-I/O verification, the shared precommit tier and registered
category/designer/setup Qt tests in an approved visible environment. Real presentation
and hardware timing verification remain separate from the visible authoring checks.
