# GUI Workflow

## Launch

Run the authoring application with:

```powershell
.\.venv3.10\Scripts\python -m fpvs_studio.app
```

The installed script entry point is also available as `fpvs-studio`.

## Welcome Flow

If no valid FPVS Studio Root Folder is configured, FPVS Studio first shows a
`Set Up FPVS Studio` dialog explaining the root folder before opening the native
folder picker. Canceling the picker returns to the setup dialog; choosing
`Exit FPVS Studio` quits without configuring a root.

The welcome window provides:

- `Create Project`
- `Import New Project`
- `Open Existing Project`

Creating a project asks for:

- project name
- parent folder where the project root will be scaffolded

Opening projects reloads the configured FPVS Studio Root Folder and lists current FPVS
project folders discovered beneath that root. Recent projects outside the configured
root are not included. The dialog can open a project or move a project folder to the
Windows Recycle Bin after an explicit Yes/No confirmation. The dialog includes a
compact project filter and can copy the selected project folder path. The currently
open project is shown but cannot be deleted from its own open window.

Importing a new project from Welcome uses the same `.fpvsbundle` import workflow as
`File > Import > Project Bundle...`. Dropping a local `.fpvsbundle` file onto the
Welcome window starts that project-import workflow for the dropped bundle. The Welcome
surface includes a visible drop hint, shows a modal staged progress surface during the
background import, and disables its project actions until the operation finishes.

Condition-template profiles are app-level metadata for the configured FPVS Studio Root
Folder. They are stored under `.fpvs-studio/templates/condition_templates.json`, keeping
template storage out of the top-level folder list used for experiment projects.
The Settings dialog can reopen the root-folder setup guide, manage condition templates,
and choose whether launched sessions write full `runs/` folders or compact summary logs
only. It also exposes the default-on Sophia Mode launch gate used before runtime
launch, plus a separate option to hide the Home ticker without disabling the launch
confirmation.

## Main Window

The authoring window is organized around two user-facing modes:

- `Home`
  - daily-use launch surface for ready projects
  - keeps the main `File` and `Tools` menus available while preserving the same centered
    launch-card placement used by the menu-free home surface
  - a centered project card with project title, description, launch readiness badge, condition count, block
    count, fixation cross status, accuracy tracking status, project open/create
    actions, including create, import, and open, setup editing, and a prominent centered
    `Launch Experiment`
  - uses the same shared launch-surface frame as Welcome so the outer window and
    inner card styling stay aligned across the two launch surfaces
  - ready projects show `Edit Setup` as a secondary action for intentional edits
  - incomplete projects keep the same setup button slot but relabel it `Complete Setup`
    and style it as the primary enabled action
  - `Complete Setup` opens the guided setup workflow at the earliest incomplete step
    using the existing setup-step completion checks
  - when launch is disabled, the Home card, launch button tooltip, and status tip show
    the first actionable setup blocker
  - when Sophia Mode and its ticker display option are enabled, Home shows a green
    horizontally scrolling `SOPHIA MODE ENABLED` ticker at the top of the launch panel
  - returning from app-expanded Setup restores the compact Home footprint unless
    the user manually resized the larger setup window
  - opening a project builds Home first; the Setup Wizard, Run / Runtime page, Image
    Resizer, and bundle processing pages are created only when the user requests those
    workflows
- `Setup Wizard`
  - in-window setup flow for new/incomplete projects and intentional edits
  - ordered steps: Project, Conditions, Experiment, Fixation, Response, Review
  - `Next` is disabled until the active step is complete, with a compact footer hint
    naming the current blocker
  - the top progress indicator is a compact connected numbered stepper with
    completed/current/upcoming states, without redundant complete-state status bars
  - when a user opens setup from a ready project's `Edit Setup` action, the numbered
    stepper is clickable and can jump directly to any setup step; first-time setup
    still advances through the gated `Next` flow
  - the wizard uses the compact Welcome/Home-sized default window while keeping
    guided steps free of Advanced buttons and vertical scrolling
  - guided steps use a shared setup step surface for consistent width, margins,
    and alignment inside the wizard card
  - all six setup steps must fit inside the compact `1120x720` setup window
    without bottom clipping, visible child widgets outside their parent bounds,
    or required vertical scrolling
  - the wizard avoids generic footer/status copy; individual step cards should
    only show information needed for the current decision
  - Project uses a focused centered card, keeping the project folder path compact
    and secondary; project name and description are required before continuing to
    Conditions; the card uses a single-column form without a redundant readiness
    subsection, and template actions sit below the full-width image-timing selector so
    their labels remain visible at the compact setup size
  - the Project image-timing selector is the default timing template for new
    conditions; it is backed by condition-template profiles, defaults to Continuous
    Images, and does not rewrite existing conditions unless the user explicitly applies
    the selected template to all conditions
  - Project exposes `Enable participant tutorial?`, which controls whether the
    participant sees the fixation response tutorial before the first condition
  - Experiment combines display, image-size, and session settings in one compact centered card
  - the Display column exposes an approved monitor-refresh dropdown (`59.94`, `60`,
    `120`, `144`, or `240 Hz`), `Detect My Refresh Rate`, project-wide base rate,
    integer oddball cadence, derived oddball rate/frame counts/condition duration, and
    presentation background (`Black` or `Dark Gray`); setup requires a successful
    PsychoPy fullscreen measurement before `Next`, changing the dropdown clears the
    prior verification, and 59.94 Hz retains its visible requested-versus-realized
    whole-frame timing warning; current launches always use PsychoPy, fullscreen
    session playback, and the default display without exposing those as choices
  - the Image Size column exposes project-wide image visual-angle width in degrees,
    approximate viewing distance in cm, physical screen width in cm, intended test
    display resolution in pixels, and an optional current-primary-screen resolution
    mode; the full-screen preview includes a side control panel for live edits to those
    same values, and source image resolution remains independent from on-screen playback
    size; new projects default to the display geometry of 5.0 deg image
    width, 80.0 cm viewing distance, 52.03 cm screen width, and 1920 x 1080 px
    resolution
  - new projects default the fixation cross appearance to the ACR-matched 27 px cross
    size and 2 px line width
  - the Session column exposes repeats per condition and the fixed Space start key;
    condition names remain internal during participant transition screens, and condition
    order is always randomized automatically for each launch
  - the Conditions step uses compact condition rows showing each condition's current
    timing template and a combined condition
    setup surface for condition list actions, name, trigger code, participant
    instructions, modality, and base/oddball stimulus authoring; the metadata form keeps
    repeat controls and participant instructions fully visible, while image source-card
    headings stay top-anchored above enlarged count/resolution summaries
  - each selected condition exposes an advanced timing selector for Continuous Images
    or 50% Blank Between Images; changing it updates only that condition
  - image conditions use the existing base/oddball image source cards; word conditions
    use typed Base Words and Oddball Words editors with one word or short phrase per line
  - word editors save only non-empty lines while preserving the focused editor's
    in-progress blank line during debounce/refresh, so pressing Enter keeps the cursor
    on the new line
  - Conditions shows project-wide Target Stimulus Repeats and per-condition base/oddball
    repeat-balance guidance; repeat-balance issues are warnings and do not block save
    or launch
  - raw image-folder import is permissive; folders with mixed or non-square image sizes are not
    rejected at selection time
  - when users leave Conditions, FPVS Studio checks selected condition images for
    mixed sizes, non-square sizes, or file types through a progress task; inconsistent
    folders can be normalized to square PNG copies at `512x512` or `256x256` before
    moving on
  - the Conditions step includes a secondary `Create Control Condition...` action for
    optional grayscale, 180 degree rotated, or phase-scrambled control conditions that
    reuse the selected condition's existing base and oddball image folders
  - control-condition creation, image normalization, and image materialization are
    image-only paths and are disabled or skipped for word conditions
  - raw timing fields such as `Cycles / Repeat` are hidden from the guided workflow
    while the friendly per-condition timing-template choice remains available
  - Conditions is complete when every condition has a descriptive name, trigger
    code of 1 or higher, and configured base/oddball stimuli for its modality
  - Fixation keeps color changes enabled and exposes schedule, capped target counts,
    and timing
  - Response exposes accuracy tracking, response key/window, appearance, and a live
    preview on the current display background
  - Review is a card-only decision point: users can `Save and Return Home` or
    `Return Home Without Saving`; returning without saving always asks for confirmation
- `Tools > Image Resizer`
  - in-window utility for optimizing an arbitrary folder of source images
  - primary action is `Optimize Images for FPVS`
  - outputs center-cropped PNG copies at `512x512` by default, with secondary
    `256x256` and `1024x1024` choices
  - suggests a sibling output folder named `<source-folder>-fpvs-optimized`
  - explains why optimization is unavailable when required folders are missing or
    invalid
  - after a successful batch, exposes `Open Output Folder` and `Copy Output Folder`
  - does not update project conditions, stimulus sets, manifests, compiler
    contracts, runtime contracts, or PsychoPy behavior

Detailed Conditions remains available internally for existing document bindings, but it
is no longer exposed as a wizard advanced step and does not expose duty-cycle editing.
Session controls are directly visible in Experiment Settings, and
Fixation and Response are guided setup pages. The Run / Runtime page remains a launch, readiness, and session-preview
surface, not a display-engine configuration step.
Run / Runtime feedback exposes `Open Run Folder` and `Copy Run Folder` after a launch
completion or abort when the runtime summary includes an output directory. In compact
summary export mode, the runtime summary has no run-folder output path, so those buttons
stay hidden and completion text points users to the project `logs/` summary files.
Participant summary files are refreshed after launch and before manual group-summary
export, not as a blocking project-open prerequisite.
Launching an experiment opens a modal participant-information prompt. By default every
project collects Participant Number, Age, Sex, Handedness, and colorblind status before
runtime starts.
Participant Number remains the output-folder identity and duplicate-history lookup key;
Sex is limited to `Female` or `Male`, and Handedness is limited to `Right handed`,
`Left handed`, or `Ambidextrous`; colorblind status is a required `Yes` or `No`
selection. When colorblind status is `Yes`, runtime uses the accessible fixation preset
of white `#FFFFFF` to vermillion `#D55E00` for the participant tutorial and condition
playback without changing the authored project colors. The additional fields are written
as runtime participant metadata for the launched session. Launch compiles the session
and runs routine preflight checks after participant details are collected, so the prompt
appears before any project image-set scan. When the app-level Sophia Mode setting is
enabled, launch then shows a blocking NERD Lab administrator check that
requires typing `Confirm` before the runtime task starts; cancelling that check returns
to FPVS Studio without starting the experiment.

The Stimuli Manager remains an internal support page for variant/materialization
behavior, not a guided setup step or visible top-level tab during normal use. Its raw
source-folder import path is permissive like guided Conditions import; strict inspection
and materialization still surface invalid or inconsistent source details before runtime
launch. Word stimulus rows are shown for readiness context but cannot use image-folder
import, inspection, or materialization actions.

The `File` menu groups manage-projects, `Import` and `Export` submenus, settings, and
help/update actions with native separators. `Import > Project Bundle...` first shows a
review dialog with bundle identity, manifest file count/size, the receiving project path,
collision-safe naming guidance, and included/excluded content. Confirming the review imports a
`.fpvsbundle` into a new project folder under the configured FPVS Studio Root Folder,
verifies archive paths and hashes in an app-owned staging folder, resolves
project-folder collisions, and shows staged verify/base-stimuli/oddball-stimuli/project
setup progress. Imports started from an open project use the embedded processing page;
imports started from Welcome use the same page inside a modal progress dialog. The
progress surface uses a wide, single-card layout with flat source/destination and
activity sections so paths, status copy, and all four stage labels remain visible. The
configured Studio root is persisted and loaded as an absolute path; import destinations
never fall back to the application working directory. Legacy relative root settings are
discarded so the root-folder setup flow can collect an explicit location again. The
display confirmation dialog compares imported settings with Qt-detected refresh,
resolution, and physical screen width, preserves editable local values, and exposes
explicit `Open with Imported Values` and `Apply & Open Project` actions. The visual-angle
target remains imported, and PsychoPy stays behind the engine boundary.
`Import > Project Config...` creates a new
Studio project shell under the configured FPVS Studio Root Folder from a `.fpvsconfig`
setup handoff; it does not merge into the current project and does not copy original
stimulus images. The config import dialog accepts `.fpvsconfig`, legacy `.config`, and
`.json` files. `Export > Project Bundle...` first asks for the project name embedded in
the portable copy and shows the resulting import-folder slug and suggested bundle
filename. Changing that name rewrites only the archived project and stimulus-manifest
identity; the open project and its folder remain unchanged. Export then validates the
saved project, checks project-relative stimulus paths, performs a compile dry run at the
preferred refresh rate or 60 Hz, hashes the final archived payload, and writes one
portable `.fpvsbundle` archive containing `project.json`, `stimuli/manifest.json`, and
the project `stimuli/` files while excluding `cache/`, `logs/`, and `runs/`. While the archive is being created, the
main window switches to an embedded processing screen with source/destination context,
an indeterminate activity spinner, and staged validation/stimulus/write status. A
successful export stays on a persistent completion page showing the bundle path,
packaged-file count, exclusions, and `Copy Path`, `Open Folder`, and `Done` actions;
`Done` restores the previous authoring surface.
`Export > FPVS Toolbox Config...`
writes a JSON-backed `.fpvsconfig` setup handoff with project title, condition trigger
mapping, display/session settings, and Toolbox-oriented `event_map` metadata.
`Export > Completed Project Config...` writes the same setup handoff plus a summary of
the latest completed session's order, seeds, trigger schedule, display geometry, and
stimulus-manifest provenance. The default setup export filename is the compact project
title in lowercase with spaces and punctuation removed, such as
`semanticcategories.fpvsconfig` for `Semantic Categories`; completed exports append
`-completed`. `Export > Group
Summary...` manually writes an Excel workbook from the current participant summary rows,
with a first row aggregating rows marked `Include In Analysis = Y` and participant rows
remaining visible underneath for filtering/audit. `Tutorials` opens the
public MkDocs quickstart site in the system browser. Settings shows the current app
version from `pyproject.toml` during source-tree runs and from package metadata in
bundled installs, and exposes the app-level run export mode. Full run export mode is the
default and writes detailed `runs/` folders after launch; compact mode skips those
folders and keeps only project-level summary logs. Settings also exposes default-on
Sophia Mode, which requires administrators to confirm that BioSemi recording is active
by typing `Confirm` before launch can continue. Settings can hide the Sophia Mode Home
ticker independently, without disabling that confirmation gate.
Moving a project to the Recycle Bin remains a controller-owned filesystem operation
guarded by `project.json` validation, confirmation, a post-action path check, and a disk
refresh of the manage list after each attempt. `Check for Updates` queries GitHub
Releases without blocking the GUI, shows current/latest versions and release notes,
downloads the matching Windows installer with progress, supports this-launch-only
`Remind Me Later`, and asks before closing FPVS Studio to launch the installer. Manual
update-check failures show a clear try-again-later message. A silent startup update
check runs once after the Welcome window is shown; it stays silent unless an update is
available. The Home page keeps full project descriptions in project data but shows a
bounded preview under the project title to avoid launch-surface clipping. The `Tools`
menu exposes standalone utilities such as Image Resizer; these utilities may use
preprocessing services but must not silently mutate the active project.

## GUI Implementation Map

- Shared GUI components and reusable theme styles live in
  `src/fpvs_studio/gui/components.py`.
- Welcome and Home use the shared `LaunchSurfaceFrame` helper for the full-window
  launch card, border styling, and first-paint background.
- Shared Setup Wizard presentation components include the connected progress stepper,
  shared setup step surface, workspace frame, side panels, metric strips, source
  cards, and reusable setup checklist panel used by compact guided pages.
- Raw color, spacing, width, and text-elision tokens live in
  `src/fpvs_studio/gui/design_system.py`; page modules should prefer component
  helpers instead of local stylesheets for shared UI concepts.
- Session structure widgets live in `src/fpvs_studio/gui/session_structure_page.py`.
- Fixation-task widgets live in `src/fpvs_studio/gui/fixation_settings_page.py`.
- `src/fpvs_studio/gui/session_pages.py` is a compatibility export facade for those
  session/fixation page classes.
- Guided setup composition lives in `src/fpvs_studio/gui/setup_wizard_page.py`; it
  uses existing document services and editor widgets rather than duplicating project
  state.
- Display and image-size settings editing lives in
  `src/fpvs_studio/gui/runtime_settings_page.py`; refresh/background controls stay
  separate from visual-angle geometry controls.
- Feature-sized GUI workflow reworks should create or update an execution plan in
  `docs/exec-plans/active/` before implementation.
- Condition-template management lives in
  `src/fpvs_studio/gui/condition_template_manager_dialog.py`.
- The condition-template profile editor lives in
  `src/fpvs_studio/gui/condition_template_profile_editor_dialog.py`.
- First-run and Settings root-folder onboarding lives in
  `src/fpvs_studio/gui/root_folder_setup_dialog.py`; the controller owns folder
  selection and settings persistence.
- App-level Settings preferences, including run export mode, live in
  `src/fpvs_studio/gui/settings_dialog.py`; the controller persists them with
  `QSettings` and injects runtime-only launch choices into the open document.
- Project management lives in `src/fpvs_studio/gui/manage_projects_dialog.py`; it uses
  shared component-layer cards, path labels, status badges, and button role helpers while
  leaving project discovery and deletion side effects in the controller.
- In-app update presentation lives in `src/fpvs_studio/gui/update_dialog.py`; release
  parsing, version comparison, installer download, and installer launch helpers stay in
  `src/fpvs_studio/updates/`.
- Startup update-check orchestration lives in `src/fpvs_studio/gui/controller.py`; it
  should stay silent unless a newer release is available.
- Standalone image resizing lives in `src/fpvs_studio/gui/image_resizer_page.py`; it uses
  the shared component layer and delegates batch work to preprocessing through Qt workers.
- Bundle review and Welcome-hosted progress dialogs live in
  `src/fpvs_studio/gui/bundle_import_dialog.py`; shared embedded progress and persistent
  export-result pages live in `src/fpvs_studio/gui/processing_page.py`.

## GUI Theme and Components

Use `fpvs_studio.gui.components` as the public starting point for shared page shells,
section cards, status badges, path labels, action-button roles, and reusable stylesheet
helpers.

New GUI work should:

- import shared widgets such as `SectionCard`, `NonHomePageShell`, `StatusBadgeLabel`,
  and `PathValueLabel` from `gui.components`
- use role helpers such as `mark_primary_action`, `mark_secondary_action`, and
  `mark_launch_action` instead of setting shared button properties inline
- add reusable styling through a named helper in `gui.components`, not a page-local
  `setStyleSheet(...)`
- keep project, compiler, preprocessing, runtime, and engine behavior outside the
  component/theme layer

## Supported Authoring Tasks

The current GUI supports:

- creating a new project scaffold
- opening and editing an existing project
- importing a complete project from an `.fpvsbundle` file from Welcome, Home, or the
  File menu
- opening known or recent projects from `Open Existing Project`
- managing known projects and moving project folders to the Recycle Bin after confirmation
- saving and reopening project state
- launching ready projects from Home without exposing setup tabs
- completing or revisiting project setup through the Setup Wizard
- configuring repeats per condition; condition order is randomized automatically for
  each launch and condition starts are fixed to `Press Space to begin`
- configuring display refresh rate and choosing a black or dark-gray presentation
  background
- configuring fixation settings, including an optional fixation accuracy task
  (Space within 1.0 s of each fixation color change) and optional participant tutorial
  before the first condition
- configuring fixed or randomized fixation target counts per condition run; compiled
  color changes are balanced across the full condition with seeded jitter and
  deterministic no-immediate-repeat behavior across consecutive compiled runs
- checking for app updates from `File > Check for Updates`
- authoring multiple conditions
- importing base and oddball image folders
- authoring base and oddball word lists for word-based conditions
- mixing image-based and word-based conditions in one session
- reviewing Target Stimulus Repeats and base/oddball repeat-balance warnings
- normalizing inconsistent condition image folders to project-local PNG copies
- using `Tools > Image Resizer` to create standalone FPVS-ready PNG copies
- creating optional derived-variant control conditions from existing condition stimuli
- materializing original, grayscale, rot180, and phase-scrambled variants
- validating and compiling the multi-condition session plan
- running the supported session launch path with fullscreen PsychoPy playback
  and manual inter-block continue screens

## Runtime Scope

The run page exposes `Launch Experiment`, with tooltip and status text that describe
fullscreen display verification and timing checks.

Current honest behavior:

- runtime launch uses normal session mode without a production/test Boolean gate
- launched PsychoPy playback opens fullscreen on the default display
- display-index and fullscreen launch controls are not exposed in the current GUI;
  launch uses the default display and fullscreen playback
- if the project uses an intended display resolution, launched playback blocks before
  stimulus presentation when PsychoPy reports a different fullscreen resolution
- each condition waits for `Space` before playback starts
- non-final blocks show a separate `Press Space to continue` break screen
- PsychoPy remains behind the runtime and engine layers
- serial trigger model fields remain in backend contracts, but serial trigger settings
  are not exposed in the current GUI
- GUI startup itself still does not initialize PsychoPy
- runtime launch settings keep presentation and timing-QC policies explicit

## Fixation Accuracy Task

When enabled in `Fixation & Session`:

- each fixation color change is treated as a response target
- the participant responds with `Space` within `1.0` second of target onset
- the optional participant tutorial teaches the response task once before the first
  condition and is skipped when disabled
- tutorial practice requires three total successful detections; missed attempts do not
  reset prior hits
- after five missed tutorial attempts, the participant sees a reminder to watch the
  center cross and press Space when the cross changes colors
- after ten missed tutorial attempts, a researcher check screen can continue without
  tutorial completion or abort the launch; continuing records a session warning
- runtime shows a participant-facing end-of-condition feedback screen with:
  - accuracy percentage and hits/total
  - mean RT (ms, or N/A when no hits)
  - false alarms

This engagement task is orthogonal to FPVS stimulus timing and does not change
base/oddball scheduling.

## GUI Test Guidance

Add or update registered pytest-qt coverage for changed GUI behavior, but leave its
execution to CI by default. Ordinary local verification excludes registered Qt modules
before import and runs backend, boundary, lint, and compilation checks:

```powershell
./scripts/verify.ps1 -Scope gui -Tier focused
```

Do not set `QT_QPA_PLATFORM=offscreen` locally. CI owns offscreen configuration and
explicit Qt opt-in through the `full-ci` tier. Local Qt execution requires user approval
and a safe visible environment.

For GUI coverage:

- register every Qt module in `tests/qt_test_files.txt`
- monkeypatch modal dialogs and runtime launch calls
- do not let tests open real `QFileDialog`, `QMessageBox`, or the PsychoPy runtime
- use `tests/gui/helpers.py` for project windows, compile-ready stimuli, fixation
  controls, condition-template rows, and fake runtime summaries
- show changed surfaces at their minimum/default size and cover realistic longest text
  plus important success, empty, busy, validation, and error states
- keep tests organized by focused workflow instead of reading broad files:
  `test_setup_wizard_shell.py` for shell/layout, `test_setup_project_details.py` for
  project details, `test_setup_conditions.py` for condition import/normalization,
  `test_setup_experiment_display.py` for display/session/image-size settings,
  `test_setup_review.py` for review/return behavior, `test_home_launch_surface.py`
  for Home, `test_run_page_launch.py` for launch wiring, and
  `test_image_resizer_page.py` for the utility page

Local handoff must document a visible manual smoke path for the changed workflow and
report registered Qt coverage as CI-pending unless it ran in an explicitly approved
visible environment.
