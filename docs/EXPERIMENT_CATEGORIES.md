# Experiment Categories

FPVS Studio saves one immutable `ProjectFile.experiment_category` for an entire
experiment. Supported values and behavior are:

| Category | Authoring and playback |
| --- | --- |
| FPVS | Base-only concept; disabled Coming soon choice. Creation and compilation are blocked. |
| FPVS-Oddball | Existing image/word oddball protocols, presentation modes, tasks and runtime behavior. |
| Attentional-Blink | Image-only target pairs with editable T1 and separator ISI; T2 fills the remaining normal slot. |

## Creation and shared Setup

The first page of new-experiment Setup asks only for the category. Nothing is
selected initially. Name, folder and compatible experiment-template choices follow
on the next page; Cancel creates no project. Category becomes locked when the
experiment is created and appears read-only on Project. Changing category requires
creating a new experiment. Templates carry their own category and cannot change an
experiment's category. Editing a template preserves that category and its cadence.

The guided steps are Project, Conditions, Design, Timing, Image Size, Session,
Fixation, Response and Review, fitting `1120x720`. Conditions handles identity,
participant instructions/tasks and existing oddball word lists. Design embeds the
shared visual image editor and image-folder selection for the selected condition.
Image intake/normalization occurs when advancing from Design. Word-list presentation
rates remain editable in Timing. Shared display, session, fixation and response
surfaces retain their existing ownership.

The designer has no experiment-type tabs. Only Attentional-Blink shows T1/ISI/T2
controls; the old backward-masking preview is no longer exposed. New AB experiments
default to 4 Hz and four normal slots per repeating cycle: three Base slots followed
by one T1/separator/T2 slot. Within the 250 ms pair slot, defaults are 50/50/150 ms.
Existing sequence-repeat and session defaults are preserved. Each new AB condition
starts with AB timing and three independent empty image pools. Empty draft pools do
not prevent editing another condition; all required pools must be ready to launch.
The current appearance contract shares target overrides between T1 and T2, with
each target's source dimensions used during compilation.

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
- `RunSpec`, `SessionPlan` and runtime schemas retain their existing versions;
  compiled target-pair events and engine frame scheduling are unchanged.

Run focused core/project-I/O verification, the shared precommit tier and registered
category/designer/setup Qt tests in an approved visible environment. Real presentation
and hardware timing verification remain separate from the visible authoring checks.
