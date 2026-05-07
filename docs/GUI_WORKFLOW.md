# GUI Workflow

## Launch

Run the authoring application with:

```powershell
.\.venv\Scripts\python -m fpvs_studio.app
```

The installed script entry point is also available as `fpvs-studio`.

## Welcome Flow

The welcome window provides:

- `Create New Project`
- `Open Existing Project`
- `Manage Projects`
- a recent-projects list when valid recent projects are available

Creating a project asks for:

- project name
- parent folder where the project root will be scaffolded

Opening a project currently selects an existing project directory and resolves
its `project.json` through the backend document layer.

Managing projects reloads the configured FPVS Studio Root Folder and lists current FPVS
project folders discovered on disk, plus valid recent projects. The dialog can open a
project or move a project folder to the Windows Recycle Bin after an explicit Yes/No
confirmation. The currently open project is shown but cannot be deleted from its own
open window.

## Main Window

The authoring window is organized around two user-facing modes:

- `Home`
  - daily-use launch surface for ready projects
  - project title, description, launch readiness badge, condition count, block
    count, fixation task status, accuracy task status, project open/create/save
    actions, setup editing, and a prominent centered `Launch Experiment`
  - `Edit Setup` opens the guided setup workflow
- `Setup Wizard`
  - in-window setup flow for new/incomplete projects and intentional edits
  - ordered steps: Project Details, Conditions, Experiment Settings, Fixation Cross, Review
  - `Next` is disabled until the active step is complete
  - the top progress indicator is a compact connected numbered stepper with
    completed/current/upcoming states, without a redundant `Step X of 5` text line
  - the wizard keeps the step content full-width while the progress stepper is
    centered and compact; the guided steps do not expose an Advanced button or
    vertical scrolling
  - the wizard shell includes a thin bottom status strip for shared setup/runtime
    context; individual step cards should not repeat generic instructional copy
  - Project Details uses a focused centered card inside the full-width wizard,
    keeping the project folder path compact and secondary; project name and
    description are required before continuing to Conditions
  - the Project Details condition template selector is the user-facing source of
    truth for condition duty-cycle mode; existing conditions are standardized
    when the selected template changes
  - Experiment Settings combines display and session settings in one compact centered card
  - the Display column exposes only display refresh rate and presentation background
    (`Black` or `Dark Gray`); current launches always use PsychoPy, alpha test-mode,
    fullscreen playback, and the default display without exposing those as choices
  - the Session column exposes repeats per condition, session seed, condition
    randomization, and the fixed Space start key
  - Fixation Cross is its own guided step and exposes fixation color-change behavior,
    timing, response, appearance, and a live preview on the current display background
  - the Conditions step uses a simplified condition setup surface for condition
    name, trigger code, participant instructions, and base/oddball image folders
  - the Conditions step uses the shared setup workspace pattern: condition list on
    the left, selected-condition editor and image source cards in the center, and
    protocol defaults plus setup checklist on the right
  - the Conditions step owns image folder selection; users choose base and oddball
    folders while creating each condition
  - when users leave Conditions, FPVS Studio checks selected condition images for
    mixed sizes or file types; inconsistent folders can be normalized to PNG copies
    at `512x512` or `256x256` before moving on
  - the Conditions step includes a secondary `Create Control Condition...` action for
    optional grayscale, 180 degree rotated, or phase-scrambled control conditions that
    reuse the selected condition's existing base and oddball image folders
  - guided Conditions copy uses `Image Version` for stimulus variant selection; raw
    timing fields such as `Cycles / Repeat` are hidden from the guided workflow
  - the Conditions step is complete only when every condition has a user-provided
    descriptive name, a trigger code of 1 or higher, and imported base and oddball
    image folders
  - `Return Home` asks for confirmation when setup is incomplete
- `Tools > Image Resizer`
  - in-window utility for optimizing an arbitrary folder of source images
  - primary action is `Optimize Images for FPVS`
  - outputs center-cropped PNG copies at `512x512` by default, with secondary
    `256x256` and `1024x1024` choices
  - suggests a sibling output folder named `<source-folder>-fpvs-optimized`
  - does not update project conditions, stimulus sets, manifests, compiler
    contracts, runtime contracts, or PsychoPy behavior

Detailed Conditions remains available internally for existing document bindings, but it
is no longer exposed as a wizard advanced step and does not expose duty-cycle editing.
Session controls are directly visible in Experiment Settings, and
Fixation Cross is a guided setup page. The Run / Runtime page remains a launch, readiness, and session-preview
surface, not a display-engine configuration step.
The Stimuli Manager remains an internal support page for variant/materialization
behavior, not a guided setup step or visible top-level tab during normal use.

The `File` menu exposes manage-projects and settings actions. Moving a project to the
Recycle Bin remains a controller-owned filesystem operation guarded by `project.json`
validation, confirmation, a post-action path check, and a disk refresh of the manage
list after each attempt. The `Tools` menu exposes standalone utilities such as Image
Resizer; these utilities may use preprocessing services but must not silently mutate the
active project.

## GUI Implementation Map

- Shared GUI components and reusable theme styles live in
  `src/fpvs_studio/gui/components.py`.
- Shared Setup Wizard presentation components include the connected progress stepper,
  workspace frame, right-side panels, metric strips, source cards, and reusable setup
  checklist panel.
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
- Display settings editing lives in `src/fpvs_studio/gui/runtime_settings_page.py`;
  it is intentionally limited to refresh rate and background color.
- Feature-sized GUI workflow reworks should create or update an execution plan in
  `docs/exec-plans/active/` before implementation.
- Condition-template management lives in
  `src/fpvs_studio/gui/condition_template_manager_dialog.py`.
- The condition-template profile editor lives in
  `src/fpvs_studio/gui/condition_template_profile_editor_dialog.py`.
- Project management lives in `src/fpvs_studio/gui/manage_projects_dialog.py`; it uses
  shared component-layer cards, path labels, status badges, and button role helpers while
  leaving project discovery and deletion side effects in the controller.
- Standalone image resizing lives in `src/fpvs_studio/gui/image_resizer_page.py`; it uses
  the shared component layer and delegates batch work to preprocessing through Qt workers.

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

Phase 5 currently supports:

- creating a new project scaffold
- opening and editing an existing project
- reopening recent projects from the welcome screen
- managing known projects and moving project folders to the Recycle Bin after confirmation
- saving and reopening project state
- launching ready projects from Home without exposing setup tabs
- completing or revisiting project setup through the Setup Wizard
- configuring session block order and stored seed; condition starts are fixed to
  `Press Space to begin`
- configuring display refresh rate and choosing a black or dark-gray presentation
  background
- configuring fixation settings, including an optional fixation accuracy task
  (Space within 1.0 s of each fixation color change)
- configuring fixed or randomized fixation target counts per condition run with
  deterministic no-immediate-repeat behavior across consecutive compiled runs
- authoring multiple conditions
- importing base and oddball image folders
- normalizing inconsistent condition image folders to project-local PNG copies
- using `Tools > Image Resizer` to create standalone FPVS-ready PNG copies
- creating optional derived-variant control conditions from existing condition stimuli
- materializing original, grayscale, rot180, and phase-scrambled variants
- validating and compiling the multi-condition session plan
- running the current test-mode launch path with fullscreen PsychoPy playback
  and manual inter-block continue screens

## Runtime Scope

The run page intentionally exposes `Launch Test Session`, not a generic
production launch button.

Current honest behavior:

- runtime launch still requires `test_mode=True`
- launched PsychoPy playback opens fullscreen on the default display
- each condition waits for `Space` before playback starts
- non-final blocks show a separate `Press Space to continue` break screen
- PsychoPy remains behind the runtime and engine layers
- serial trigger model fields remain in backend contracts, but serial trigger settings
  are not exposed in the current GUI
- GUI startup itself still does not initialize PsychoPy
- non-test validation remains deferred

## Fixation Accuracy Task

When enabled in `Fixation & Session`:

- each fixation color change is treated as a response target
- the participant responds with `Space` within `1.0` second of target onset
- runtime shows a participant-facing end-of-condition feedback screen with:
  - accuracy percentage and hits/total
  - mean RT (ms, or N/A when no hits)
  - false alarms

This engagement task is orthogonal to FPVS stimulus timing and does not change
base/oddball scheduling.

## GUI Test Guidance

When iterating on GUI tests:

- keep Qt headless with `QT_QPA_PLATFORM=offscreen`
- disable plugin autoload to avoid unrelated third-party pytest plugins
- run one GUI test node at a time
- use `pytest-timeout`
- monkeypatch modal dialogs and runtime launch calls
- do not let tests open real `QFileDialog`, `QMessageBox`, or launch the real
  PsychoPy runtime
- use named helpers in `tests/gui/helpers.py` for common setup such as creating a
  project window, preparing compile-ready stimuli, configuring fixation controls,
  finding condition-template rows, and building fake runtime summaries

Recommended invocation:

```powershell
$env:PYTHONPATH = "src"
$env:TMP = "$PWD\build\tmp"
$env:TEMP = "$PWD\build\tmp"
$env:TMPDIR = "$PWD\build\tmp"
$env:APPDATA = "$PWD\build\appdata"
$env:LOCALAPPDATA = "$PWD\build\localappdata"
$env:USERPROFILE = "$PWD\build\userprofile"
$env:HOME = "$PWD\build\home"
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

New-Item -ItemType Directory -Force build\tmp, build\appdata, build\localappdata, build\userprofile, build\home | Out-Null

.\.venv\Scripts\python -m pytest `
  --disable-plugin-autoload `
  -p pytestqt.plugin `
  -p pytest_timeout `
  --basetemp=build\pytest_tmp `
  --maxfail=1 `
  --timeout=45 `
  -vv -s `
  tests\gui\test_welcome_settings_flow.py::test_welcome_window_smoke
```
