# GUI Workflow

## Launch

Run the authoring application with:

```powershell
.\.venv3.10\Scripts\python -m fpvs_studio.app
```

The installed script entry point is also available as `fpvs-studio`.

Setup's `Detect My Refresh Rate` action and launch preflight use the native configured
mode for the primary/default display plus a temporary fullscreen PsychoPy stability
observation. Windows uses its exact rational display path; KDE Linux uses KScreen's
structured current-mode and VRR data, while Linux X11 uses XRandR. Variable-refresh
configurations remain blocking for timing-sensitive playback.

## Welcome Flow

If no valid FPVS Studio Root Folder is configured, FPVS Studio first shows a
`Set Up FPVS Studio` dialog explaining the root folder before opening the native
folder picker. Canceling the picker returns to the setup dialog; choosing
`Exit FPVS Studio` quits without configuring a root.

The welcome window provides:

- `Create Project`
- `Import New Project`
- `Open Existing Project`
- `Change Root Folder...`

`Change Root Folder...` reopens the guided root-folder setup and native folder picker
without requiring a project to be open. Canceling either step leaves the configured
root unchanged.

Creating a project asks for:

- project name
- parent folder where the project root will be scaffolded

Opening projects reloads the configured FPVS Studio Root Folder and lists current FPVS
project folders discovered beneath that root. Discovery excludes the reserved
`.fpvs-studio` app-metadata subtree, including templates, staging files, and backups.
Recent projects outside the configured root are not included. The dialog can open a
project or move a project folder to the Windows Recycle Bin after an explicit Yes/No
confirmation. The dialog includes a
compact project filter and can copy the selected project folder path. The currently
open project is shown but cannot be deleted from its own open window. When a discovered
folder contains an unreadable or incompatible `project.json`, the dialog keeps Open and
Delete disabled and asks the user to verify the configured FPVS Studio Root Folder and
the project's FPVS Studio version.

Importing a new project from Welcome uses the same `.fpvsbundle` import workflow as
`File > Import > Project Bundle...`. Dropping a local `.fpvsbundle` file onto the
Welcome window starts that project-import workflow for the dropped bundle. The Welcome
surface includes a visible drop hint, shows a modal staged progress surface during the
background import, disables all Welcome actions until the operation finishes, and does
not allow the Welcome window or progress surface to close while the import is active.

Condition-template profiles are app-level metadata for the configured FPVS Studio Root
Folder. They are stored under `.fpvs-studio/templates/condition_templates.json`, keeping
template storage out of the top-level folder list used for experiment projects.
The Settings dialog can reopen the root-folder setup guide, manage condition templates,
and choose whether launched sessions write full `runs/` folders or compact summary logs
only. It also exposes the default-on Sophia Mode launch gate used before runtime
launch, plus a separate option to hide the Home ticker without disabling the launch
confirmation. Source-tree Windows and Linux runs additionally expose Experiment Test
Mode for explicit no-hardware verification launches; packaged builds hide it.

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
  - Experiment combines display, presentation-default, image-size, and session settings
    in one compact centered card; a compact `Configure Presentation...` action opens the
    reusable presentation editor instead of expanding the wizard card
  - the Display column exposes an approved monitor-refresh dropdown (`59.94`, `60`,
    `120`, `144`, or `240 Hz`), `Detect My Refresh Rate`, project-wide base rate,
    integer oddball cadence, derived oddball rate/frame counts/condition duration, and
    presentation background (`Black` or `Dark Gray`); setup requires a successful
    PsychoPy fullscreen measurement before `Next`, changing the dropdown clears the
    prior verification, and 59.94 Hz retains its visible requested-versus-realized
    whole-frame timing warning; current launches always use PsychoPy, fullscreen
    session playback, and the default display without exposing those as choices
  - the Image Size column exposes calibrated display geometry and a concise summary of
    the project presentation defaults,
    approximate viewing distance in cm, physical screen width in cm, intended test
    display resolution in pixels, and an optional current-primary-screen resolution
    mode; the full-screen preview includes a side control panel for live edits to those
    same values, and source image resolution remains independent from on-screen playback
    size; new projects default to the display geometry of 5.0 deg image
    width, 80.0 cm viewing distance, 52.0 cm screen width, and 1920 x 1080 px
    resolution
  - new projects default the fixation cross appearance to the ACR-matched 27 px cross
    size and 2 px line width
  - the Session column exposes repeats per condition and the fixed Space start key;
    condition names remain internal during participant transition screens, and condition
    order is always randomized automatically for each launch
  - the Conditions step uses compact condition rows showing each condition's current
    timing template and a combined condition
    setup surface for condition list actions, name, trigger code, participant
    instructions, modality, and base/oddball stimulus authoring; its frameless two-column
    workspace keeps repeat controls and participant instructions fully visible, uses one
    responsive field column whose minimum width is set by the Advanced Timing selector,
    places repeat guidance behind a compact lower-right information action, and keeps
    image source-card headings top-anchored above enlarged count/resolution summaries
  - each selected condition exposes a compact `Presentation...` action for inherited
    condition, Base-role, and Oddball-role settings; the draft-based dialog supports
    reset-to-inherited controls and a live representative-stimulus preview
  - each selected condition also exposes `Pre/Post Tasks...` with a compact saved-flow
    summary; its reusable dialog keeps separate ordered pre-condition and post-condition
    module lists without adding a seventh wizard step
  - task modules can contain ordered instruction/content, study display, choice grid,
    questionnaire, raw-key response, and timed-feedback steps; whole modules and
    individual choice steps can repeat, and bindings can run on every, first, or last
    occurrence of a condition; a pre-condition binding can explicitly replace the
    standard condition start screen when its authored reminder already serves that role
  - study and choice displays default to responsive grids and can opt into exact
    center-origin PsychoPy geometry; exact items support degrees of visual angle or
    fractions of window height, per-item position and size, selectable/scored targets,
    one-valid-choice completion, duplicate choices across repeats, explicit submission,
    retries, and randomized display order
  - questionnaires support ordered single choice, multiple choice, short text, long
    text, numeric, and rating items, including required/optional responses, selection
    and numeric bounds, option randomization, stable IDs, scores/correctness, and bounded
    forward conditional routes; participant-facing previews remain authoring aids rather
    than runtime substitutes
  - task images are staged in the dialog and copied into
    `stimuli/task-assets/<task-id>/` only when `Apply Tasks` succeeds; Cancel leaves both
    the project model and task-asset tree unchanged, and editing a shared reusable module
    cannot silently alter another condition
  - runtime presentation transforms are none, horizontal mirror, vertical mirror, and
    180-degree rotation for both images and words; these write no stimulus files and
    stay distinct from file-backed grayscale/phase-scrambled variants
  - image geometry supports Exact Box, Contain, Cover, and Natural Aspect; word
    presentation supports fixed or balanced-randomized height in degrees or window
    height, fixed Arial rendering, opaque color, and authored position
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
  - raw image-folder import is permissive; folders with mixed or rectangular image
    sizes are not rejected at selection time
  - when users leave Conditions, FPVS Studio checks selected condition images for mixed
    sizes or unsupported runtime formats through a progress task; uniform rectangular
    sets are valid native inputs, while inconsistent folders can still be normalized to
    project-local PNG copies before moving on
  - the Conditions step includes a secondary `Create Control Condition...` action;
    mirrored/rotated controls use runtime transforms with the original folders, while
    grayscale and phase-scrambled controls retain file-backed derived variants
  - control-condition creation, image normalization, and image materialization are
    image-only paths and are disabled or skipped for word conditions
  - raw timing fields such as `Cycles / Repeat` are hidden from the guided workflow
    while the friendly per-condition timing-template choice remains available
  - Conditions is complete when every condition has a descriptive name, trigger
    code of 1 or higher, and configured base/oddball stimuli for its modality
  - Fixation keeps color changes enabled and exposes schedule, capped target counts,
    timing, and the fixation-only lead-in shown after Space but before condition onset;
    new projects default to randomized 8–13 color changes per condition, a 300 ms color
    change duration, and a two-second lead-in, while migrated legacy projects retain zero
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
runtime starts. The same dialog includes the optional
`Input manually removed electrodes (optional)` text box for electrodes physically
removed or unplugged before recording. Comma-, semicolon-, or line-separated entries
are normalized to stable uppercase labels and saved under that participant number in
the project's top-level `manual_removed_electrodes` map in `project.json`; an empty list
records that the administrator reviewed the field and reported none removed. Returning
participants prefill the saved list for review and correction.
Participant Number remains the output-folder identity and duplicate-history lookup key;
Sex is limited to `Female` or `Male`, and Handedness is limited to `Right handed`,
`Left handed`, or `Ambidextrous`; colorblind status is a required `Yes` or `No`
selection. When colorblind status is `Yes`, runtime uses the accessible fixation preset
of white `#FFFFFF` to vermillion `#D55E00` for the participant tutorial and condition
playback without changing the authored project colors. The age, sex, handedness, and
colorblind fields are written as runtime participant metadata for the launched session.
The manually removed electrode list remains editable project metadata and does not alter
`RunSpec`, `SessionPlan`, or playback behavior. Accepting the participant dialog persists
its participant entry before compilation and before the Sophia Mode gate. Launch then
compiles the session and runs routine preflight checks after participant details are
collected, so the prompt appears before any project image-set scan. When the app-level
Sophia Mode setting is enabled, launch then shows a blocking NERD Lab administrator
check that
requires typing `Confirm` before the runtime task starts; cancelling that check returns
to FPVS Studio without starting the experiment.

When Experiment Test Mode is enabled, launch replaces participant collection with an
explicit acknowledgement and reserved participant ID `0`, skips manual-electrode
project updates, suppresses the Sophia/BioSemi gate, uses logged null-trigger output,
and disables connected-display refresh verification. Compilation, routine asset
preflight, fullscreen playback, frame schedules, task flow, timing warmup/QC, and test
exports remain unchanged. Participant summaries already exclude reserved IDs `0` and
`00`.

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
target remains imported, and PsychoPy stays behind the engine boundary. Detected refresh
measurements are mapped to the nearest approved FPVS refresh rate when they are within
tolerance; unsupported measurements are shown for review without writing an invalid
refresh target. Closing or pressing Escape cannot bypass the two explicit open actions.
It leaves the imported project available under the configured Studio root without
opening it, so the user can reopen it later through `Open Existing Project`.
`Import > Project Config...` creates a new
Studio project shell under the configured FPVS Studio Root Folder from a `.fpvsconfig`
setup handoff; it does not merge into the current project or carry the FPVS base and
oddball stimulus image libraries. Modular-task definitions are included, and their
comparatively small task media are embedded with hashes so import can reconstruct the
project-contained `stimuli/task-assets/` tree without machine-local paths. The config
import dialog accepts `.fpvsconfig`, legacy `.config`, and `.json` files.
`Export > Project Bundle...` first asks for the project name embedded in
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
mapping, display/session settings, modular-task definitions and media, and
Toolbox-oriented `event_map` metadata.
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
ticker independently, without disabling that confirmation gate. In source-tree Windows
and Linux runs, Settings also exposes Experiment Test Mode with a detailed tooltip that
names every skipped hardware/participant check and every timing behavior that remains.
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
  shared setup step surface, metric strips, and source cards used by compact guided
  pages.
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
- First-run, Welcome, and Settings root-folder onboarding lives in
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
- configuring inherited image/word presentation rules separately for Base and Oddball,
  including runtime transforms, word-size schedules, position/color, and native image
  geometry
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

- runtime launch uses normal session mode without restoring the retired runtime
  production/test Boolean gate
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
- source-only Experiment Test Mode on Windows and Linux composes those explicit settings
  to disable serial and connected-refresh checks while preserving fullscreen playback,
  compilation, asset checks, timing QC, task flow, and exports

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
