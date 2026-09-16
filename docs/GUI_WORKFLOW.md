# GUI Workflow

## Bug reporting

File > Request a Feature opens a separate text-only draft using the same reporting
workflow and window sizes, with a 4,000-character counter and copy/save actions.
It collects no logs. Both submission actions remain disabled until service setup.

File > Report a Bug opens a native report editor at 860x760 (minimum 760x680).
File is the only reporting entry point; Welcome, root-folder setup, and error
dialogs have no reporting button. Details and Diagnostics support editing/excluding logs,
copying, and saving a text report without a project. Drafts are stored locally
for seven days. Online submission is explicitly unavailable until the service
is configured; no Cloudflare/GitHub infrastructure is created by the desktop app.
See [Bug reporting](BUG_REPORTING.md) for configuration, retention, acceptance,
and the HTTP contract. Qt jobs remain app-owned and never block the GUI thread.

## Frameless Setup layout and copy

The eight-step wizard uses one task heading, without duplicate card headings. Project
has a centered 760 px form; Timing & Session share an 880 px form; Size is 760 px.
Review remains 880 px, and Conditions/Design retain wider working areas. Content is
vertically centered between the stepper and bottom navigation. Project and Timing
stack labels above fields; denser forms align labels beside the input column.
Timing & Session has two labeled, frameless groups aligned along their tops. Existing
Session shortcuts and Review links open this combined step.

Timing keeps refresh, Verify display and background controls. Successful frame math
and SOA recaps are available through the refresh tooltip, with measured monitor detail
on the verification status tooltip. Errors, approximate-timing warnings and verification
state remain visible. Conditions removes repeated AB stream/SOA explanations and
redundant rate text from each list entry; participant instructions and task controls
remain unchanged. Optional task interpretation is available on the task button.
Review summarizes the native AB character height and digit/letter stream, without
image-geometry wording.
See [Frontend](FRONTEND.md#setup-text-hierarchy) for the descriptive-text policy.

## Launch

Run the authoring application with:

```powershell
.\.venv3.10\Scripts\python -m fpvs_studio.app
```

The installed script entry point is also available as `fpvs-studio`.

Setup's `Verify display` action and launch preflight use the native configured
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

Creating an experiment first asks only for its category: FPVS Oddball Paradigm or
Attentional-Blink. Standard FPVS is a disabled Coming soon choice. Name, parent folder and
compatible template follow on a second page. Category is locked when the experiment
is created; changing it requires a new experiment. See
[Experiment categories](EXPERIMENT_CATEGORIES.md) for persistence and legacy separation.

The creation dialog has a `760x500` minimum and `800x500` default size. Its second
page, **Name your experiment**, groups Project Name, Experiment Template and Save
Location vertically. The selected template's description stays visible below its
selector; changing the template or returning from Manage Templates refreshes it.
Save Location remains editable and exposes the full path by tooltip. A **New folder**
hint previews the project folder name beneath that location without creating files.
Back sits at the lower left, with the standard Create Experiment/Cancel pair at the
lower right. Keyboard navigation follows the field order.

Opening projects reloads the configured FPVS Studio Root Folder and lists current FPVS
project folders discovered beneath that root. Discovery excludes the reserved
`.fpvs-studio` app-metadata subtree, including templates, staging files, and backups.
Recent projects outside the configured root are not included. The dialog can open a
project, rename its display name, or move a project folder to the Windows Recycle Bin
after an explicit Yes/No confirmation. **Rename...** pre-fills the selected name and
saves only name/update-time metadata. Folder names, experiment IDs, stimuli and run
records stay in place. The currently open project's title updates immediately, while
other unsaved edits remain unsaved. Empty names are rejected; Cancel and failed writes
preserve the original file. Renaming retains the selected project and clears the search
filter so the new name remains visible. The dialog includes a
compact project filter and can copy the selected project folder path. The currently
open project is shown but cannot be deleted from its own open window. When a discovered
folder contains an unreadable or incompatible `project.json`, the dialog keeps Open and
Delete and Rename disabled and asks the user to verify the configured FPVS Studio Root Folder and
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

Cognitive Load FPVS creation, placeholder replacement, reusable backward-counting
task controls and visible acceptance are documented in
[Cognitive Load FPVS](COGNITIVE_LOAD_FPVS.md).

### Experimental visual cycle designer

New Attentional-Blink experiments open a three-condition burst designer in
Setup > **Design**: shared **Presentation rate (Hz)** and **Bursts per SOA** fields,
letter distractor/T1 digit/T2 digit sources, editable onset-to-onset SOAs, and a
labelled target-focused timeline. Default SOAs are 100/300/500 ms at 10 Hz, with 0/2/4
intervening letters. The default 24 bursts per SOA yields 120 seconds of EEG per SOA
and 72 bursts in a shuffled session. Home shows the total burst count and T1/T2
recall tracking; Timing & Session uses the same persisted burst count.
Character Size edits native text height. Timing validates exact
frame compatibility. The post-condition questionnaire button reuses the condition
task editor. See [Experiment Categories](EXPERIMENT_CATEGORIES.md) for the current contract.

The rate accepts positive finite decimal values and stays a draft until Next/Apply.
Rate, burst count, character sources, colors and SOAs are validated and saved together. Existing
SOAs are preserved when the rate changes; incompatible values stay visible for
correction. The timeline, character duration, cycle duration and quarter-speed preview
follow the draft rate. New burst studies keep their five-second duration when the
rate changes. Editable decimal SOAs retain full precision when reopened.
Extremely slow/fast rates outside the animation timer's range retain a static timeline
with an explanation; this does not change the authored rate or runtime validation.

Visible acceptance at `1120x820`, in both themes: open an AB study, enter 20 Hz,
confirm 50 ms characters, 100 characters per five-second burst and unchanged SOAs.
Change bursts per SOA to 20; confirm 100 seconds per SOA and 60 total bursts.
Apply, save and reopen to confirm persistence in Design, Timing & Session and Home.
On a saved legacy native study, 7.5 Hz with SOAs `133.33333333333334`, `400`, and
`666.6666666666666` ms remains supported when frame-compatible; new five-second
bursts reject rates that cannot represent their duration and target positions exactly.
Enter zero or an incompatible SOA
and verify that the error remains visible, preview stops, and the saved project is
unchanged. Display timing remains subject to the existing exact-frame check.

### Attentional Blink accuracy

**View > T1 and T2 Accuracy...** loads the active AB project's saved burst
records through a worker. The compact SOA summary shows recorded condition trigger
codes, correct/answered counts, and separate T1 and T2 accuracy percentages; the
chronological table retains participant, visit, burst number, targets, responses,
correctness, EEG time and incomplete/aborted state. **Export Excel...** writes the
loaded data to the chosen workbook path using the same backend summary.
The default SOA/trigger rows are 100 ms / 1, 300 ms / 3 and 500 ms / 5. Historical
custom codes are shown from recorded data. Other experiment categories retain
**View > Fixation Task Accuracy...**. Tools contains Image Resizer.
Test sessions (participant IDs `0`/`00`) record and display accuracy and are marked
in the burst table and workbook. The SOA summary includes their completed answers.

New recall tasks accept typed answers, submitted with Enter or **Next**. Before
every burst, the participant sees "Press space when you're ready to continue."
and must press Space. In a visible presentation check, submit T1 with Enter and
T2 with Next, verify Enter cannot start the next burst, then use Space to continue.

Visible acceptance: open the dialog at its `920x600` minimum and `1080x680` default
in both themes. Exercise no-data, populated, loading, export and error states.
Verify long participant/session names remain accessible, table scrolling exposes
all columns, and buttons fit. Confirm a partially answered burst retains T1 when
the participant aborts at T2, then inspect its workbook row. Registered Qt tests
cover these surfaces; they require an approved visible environment to run locally.
Open an AB project, trigger the T1 and T2 Accuracy View item, and confirm its
three SOA rows and codes. Open an Oddball project and confirm the same View menu
position opens Fixation Task Accuracy. Check all seven summary columns at both sizes.

For image experiments, Setup > **Design** embeds the visual designer for the selected condition.
FPVS Oddball Paradigm uses Base/Oddball sources and a repeating image cycle.
Attentional-Blink uses its native character/SOA editor; image pairs and the ISI editor
are no longer available. Archived image-pair projects show an unsupported-design
explanation instead of an editor. See [Experiment Categories](EXPERIMENT_CATEGORIES.md).

Folder imports run on workers and immediately update the condition using a fresh
project-contained source set; old/new folders are never merged. Timing edits apply
before leaving Design, switching conditions or saving, with all AB conditions
validated against a changed project-wide cadence. Invalid edits stay visible for
correction; explicitly discarding a draft preserves completed folder imports.
Preview slowly uses a cancellable animation. Timing &
display details opens a separate small dialog with requested/achieved frame timing
and T2 marker; preview refresh is never treated as display measurement.

Normal experimental playback supports the
custom AB compound slot, dedicated T2 and ISI assets, and separate target onset records.
Visible acceptance must cover both categories, both themes, realistic long names/paths,
folder-picker cancellation, changed sources, invalid/sub-frame timing, draft switching,
apply/discard, pending workers and preview stop/close. The eight-step wizard must fit
`1120x820`. The optional standalone designer retains `1040x760` minimum and
`1400x920` default dimensions bounded by available screen space.

Registered GUI coverage is not a claim of visual acceptance until run in an approved
visible environment.

### Existing Home and Setup flow

The authoring window is organized around two user-facing modes:

- `Home`
  - daily-use launch surface for ready projects
  - keeps the main `File`, `View`, and `Tools` menus available in that order while
    preserving the same centered launch-card placement used by the menu-free home
    surface
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
  - ordered steps: Project, Conditions, Design, Timing & Session, Image Size, Fixation, Response, Review
  - `Next` is disabled until the active step is complete, with a compact footer hint
    naming the current blocker; Project and Conditions also offer `Show field` to
    focus the missing input, with image/word-specific source wording
  - the top progress indicator is a compact connected numbered stepper with
    completed/current/upcoming states, without redundant complete-state status bars
  - when a user opens setup from a ready project's `Edit Setup` action, the numbered
    stepper is clickable and can jump directly to any setup step; first-time setup
    still advances through the gated `Next` flow
  - the wizard uses the compact Welcome/Home-sized default window while keeping
    guided steps free of Advanced buttons and vertical scrolling
  - all guided steps use the Design page's frameless shell, left-aligned task heading,
    step count, and stable progress/navigation positions; content is vertically centered with
    bounded form widths, and the bottom navigation has no horizontal divider
  - all eight setup steps must fit inside the compact `1120x820` setup window
    without bottom clipping, visible child widgets outside their parent bounds,
    or required vertical scrolling
  - the wizard avoids generic footer/status copy; individual step cards should
    only show information needed for the current decision
  - Project uses a focused frameless form, keeping the project folder path compact
    and secondary; project name and description are required before continuing to
    Conditions; the card uses a single-column form without a redundant readiness
    subsection, and template actions sit below the full-width image-timing selector so
    their labels remain visible at the compact setup size
  - Project displays the experiment category read-only. Its image-timing selector
    contains compatible condition-template profiles, defaulting to Continuous Images
    for FPVS Oddball Paradigm or Attentional-Blink for AB, and does not rewrite existing conditions unless the user explicitly applies
    the selected template to all conditions
  - Project exposes `Enable participant tutorial?`, which controls whether the
    participant sees the fixation response tutorial before the first condition; it is
    enabled by default for new projects and by the one-time migration of older projects
  - Timing and Session share one step with two frameless groups, Display and Session; Image Size retains `Configure Presentation...`
    for the full draft-based presentation editor
  - Timing exposes an approved monitor-refresh dropdown (`59.94`, `60`,
    `120`, `144`, or `240 Hz`), `Verify display`, derived rate/frame counts/condition duration, and
    presentation background (`Black`, `Dark Gray`, or `Neutral Gray`); Neutral Gray is
    required when any image condition uses Contrast Modulation. Image cadence is edited
    in Design; Timing retains cadence fields for word conditions. Setup requires a successful
    PsychoPy fullscreen measurement before `Next`; a visible notice explains the
    fullscreen check before activation. Changing the dropdown clears the
    prior verification, and 59.94 Hz retains its visible requested-versus-realized
    whole-frame timing warning; current launches always use PsychoPy, fullscreen
    session playback, and the default display without exposing those as choices
  - the Image Size step exposes calibrated display geometry and a concise summary of
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
  - the Session step exposes repeats per condition and the fixed Space start key;
    condition names remain internal during participant transition screens, and condition
    order is always randomized automatically for each launch
  - the Conditions step uses compact condition rows showing each condition's current
    timing template and a combined condition
    setup surface for condition list actions, name, trigger code, participant
    instructions, modality, and word-list authoring; its frameless two-column
    workspace separates an `All conditions` repeat target beneath the list from the
    `This condition` editor and participant instructions, uses one
    responsive field column whose minimum width is set by the Advanced Timing selector,
    places oddball repeat guidance behind a compact lower-right information action.
    Conditions fills the available height with a 16-pixel inset above and below.
    The condition list, instructions and word editors grow with the window. Ready
    conditions omit the list hint so the list and editor share the same top edge;
    incomplete and legacy-repair guidance remains visible when needed.
    Visible acceptance: use six populated conditions at 1120x820, then enlarge to
    1120x960 and 1448x1086. Check aligned list/editor tops, growing text editors,
    the three image-mode labels and two word-mode labels, and no page scrolling.
    Changing a populated condition between Images and Words shows a Yes/No warning
    (No by default). Yes clears that condition's base/oddball selections and opens
    empty lists of the chosen type; No restores the selector and keeps the selections.
    Pending word edits are committed before confirmation. Other conditions sharing
    the sources and image files on disk are preserved. Empty conditions switch directly.
    Image pools and timeline editing live in Design. AB hides modality, ordinary
    presentation-mode choices and oddball repeat-balance controls, retaining names,
    instructions, task bindings and appearance settings. Mixed legacy projects expose
    an explicit separation action here and cannot advance until category conflicts
    are resolved
  - each selected condition exposes a compact `Project defaults` / `Custom settings`
    action for inherited condition and role settings; AB shares its target appearance
    overrides between T1 and T2. The draft-based dialog supports
    reset-to-inherited controls and a live representative-stimulus preview
  - each selected condition exposes `FPVS Condition Modifiers` with a saved-flow
    summary. The dialog groups counting or memory across before/during/after FPVS,
    with Overview, Settings, Participant preview, explicit condition assignments,
    and a Built-in / My presets library. Local preset saves and project Apply are
    separate actions. See [Condition modifiers](CONDITION_MODIFIERS.md).
  - The modifier dialog fits a `1100x720` minimum and `1120x760` default. The existing
    advanced task editor remains available for custom pre/post steps. Its modules
    stay on the left, selected step occupies the center, and preview stays on the
    right. Empty phases explain how to add a module. **Module settings** opens
    naming, occurrence, repetition and step-order
    controls; **Back to step** returns to the selected step. Step settings use Content,
    Text & layout, Response and, for choice grids, Choices pages. Questionnaires split
    Question, Answers and Rules into focused pages. Lists, tables and text fields still
    support their normal data navigation for long authored content. Full module, step
    and question names are available through tooltips. Apply/Cancel remain in the footer
  - task modules can contain ordered instruction/content, study display, choice grid,
    questionnaire, raw-key response, and timed-feedback steps; whole modules and
    individual choice steps can repeat, and bindings can run on every, first, or last
    occurrence of a condition; a pre-condition binding can explicitly replace the
    standard condition start screen when its authored reminder already serves that role
  - every task-step editor exposes a `Font family` choice of Arial or Open Sans; Arial
    remains the default for existing and newly added steps, while the bundled Open Sans
    face is used by both the authoring preview and runtime task screen when selected;
    the choice applies to all text belonging to that step
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
  - each selected FPVS Oddball Paradigm image condition exposes an advanced presentation selector for
    Continuous Display, 50% Blank, or Sinusoidal Contrast Modulation; word conditions
    expose only the first two, and changing the selection updates only that condition
  - image conditions use the category-specific source shelf in Design; oddball word conditions
    use typed Base Words and Oddball Words editors with one word or short phrase per line
  - word editors save only non-empty lines while preserving the focused editor's
    in-progress blank line during debounce/refresh, so pressing Enter keeps the cursor
    on the new line
  - FPVS Oddball Paradigm Conditions shows project-wide Target Stimulus Repeats and per-condition base/oddball
    repeat-balance guidance; repeat-balance issues are warnings and do not block save
    or launch
  - raw image-folder import is permissive; folders with mixed or rectangular image
    sizes are not rejected at selection time
  - when users leave Design, FPVS Studio checks condition images for mixed
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
  - Conditions is complete when category conflicts are resolved and every condition
    has a descriptive name, trigger code of 1 or higher and, for words, configured
    Base/Oddball lists. Design requires all image pools and valid sequence timing
  - Attentional-Blink exposes **Show fixation cross** in Fixation. Turning it off
    disables fixation color changes, accuracy responses and the participant tutorial.
    Appearance/task controls become inactive, the preview and Review show that the
    cross is off, and any configured lead-in becomes a blank interval. The choice
    applies to native letter-stream AB experiments and persists
    with the project. Existing projects default to showing the cross.
  - FPVS Oddball Paradigm Fixation keeps color changes enabled and exposes schedule, capped target counts,
    timing, and the fixation-only lead-in shown after Space but before condition onset;
    new projects default to randomized 8–13 color changes per condition, a 300 ms color
    change duration, and a two-second lead-in, while migrated legacy projects retain zero
  - Response exposes accuracy tracking, response key/window, appearance, and a live
    preview on the current display background; accuracy tracking is enabled by default
    for new projects and by the one-time migration of older projects
  - Review presents its summaries in a card, with `Save and Return Home` and
    `Return Home Without Saving` in the bottom navigation alongside Back;
    returning without saving always asks for confirmation
- `View > Fixation Task Accuracy...` for FPVS / FPVS Oddball projects
  - opens a compact view of the active project's pooled fixation-task results
  - loads `logs/session_condition_history.csv` in the background through the runtime
    reporting boundary, keeping log parsing and aggregation out of GUI widgets
  - shows overall weighted accuracy, hit-weighted mean reaction time, included
    participant-session count, and condition rows with included sessions, hits/targets,
    and pooled weighted accuracy
  - shows `No fixation data yet` when history is missing or has no target-bearing
    included sessions; unreadable or malformed history produces a recoverable error
    state and leaves project data unchanged
  - groups renamed conditions under their stable condition identity and exposes long
    display names without clipping; detailed inclusion and weighting rules are defined
    in `RUNTIME_EXECUTION.md`
  - `Export Excel...` opens the native save dialog and writes the currently displayed
    summary to the selected `.xlsx` path in the background; cancelling makes no changes,
    and export errors leave the loaded results available
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
Timing & Session, Image Size, Fixation, and Response are separate guided setup pages.
Existing `session` navigation links open Timing & Session; its internal key is `experiment`.
The Run / Runtime page remains a launch, readiness, and session-preview surface,
not a display-engine configuration step.
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
Setup > Project includes `Allow repeat participant sessions`, disabled by default for
projects without an explicit setting. Both Home and Run check participant history in
a worker after participant entry. A previously used PID, including an aborted visit,
is blocked when repeat sessions are disabled. When enabled, the operator confirms
`Start Session N`; declining returns to FPVS Studio without launching. Earlier visit data is
preserved. Runtime checks the selected number again after preflight, so a competing
launch cannot overwrite or silently change the confirmed visit. Session 1 is assigned
to the first visit, and launch results show the assigned session number. Runtime
numbering/report compatibility is documented in
[Runtime execution](RUNTIME_EXECUTION.md#repeat-participant-sessions).
The confirmation fits `600x260`; Setup remains `1120x820`. Visible acceptance should
save/reopen the repeat-session checkbox, launch a fresh PID, repeat with accept and
cancel, and confirm disabled reuse is blocked on both Home and Run. Check long PID
text and a multi-digit session number, then verify full and compact exports and an
aborted visit advance the next number. Active history checks/playback block closing
or switching projects. Registered GUI tests cover these states; ordinary local
verification excludes Qt execution.
Participant Number remains the participant identity and duplicate-history lookup key;
Sex is limited to `Female` or `Male`, and Handedness is limited to `Right handed`,
`Left handed`, or `Ambidextrous`; colorblind status is a required `Yes` or `No`
selection. When colorblind status is `Yes`, runtime uses the accessible fixation preset
of white `#FFFFFF` to vermillion `#D55E00` for the participant tutorial and condition
playback without changing the authored project colors. The age, sex, handedness, and
colorblind fields are written as runtime participant metadata for the launched session.
The manually removed electrode list remains editable project metadata, and each new
visit stores a reviewed snapshot in its execution metadata. It does not alter
`RunSpec`, `SessionPlan`, or playback behavior. Accepting the participant dialog persists
its participant entry before compilation and before the Sophia Mode gate. Launch then
compiles the session and runs routine preflight checks after participant details are
collected, so the prompt appears before any project image-set scan. When the app-level
Sophia Mode setting is enabled, launch then shows a blocking NERD Lab administrator
check that
requires typing `Confirm` before the runtime task starts; cancelling that check returns
to FPVS Studio without starting the experiment.

When Experiment Test Mode is enabled, launch first applies the same full-project
validation gate as a production launch, then replaces participant collection with an
explicit acknowledgement and a `Condition to run` selector. The selector defaults to
`All conditions (current behavior)` each time the dialog opens; choosing one numbered
condition passes its stable condition ID only to that accepted launch. The selection is
not saved in app settings or the project, and no dedicated selector field is added to
compiled contracts; the resulting ordinary `SessionPlan` contains only the compiled
condition entries. A selected condition still runs once per configured block with its
ordinary pre/post tasks, timing, preflight, and output behavior. Test mode uses reserved
participant ID `0`, skips manual-electrode
project updates, suppresses the Sophia/BioSemi gate, uses logged null-trigger output,
and disables connected-display refresh verification. Fullscreen playback, frame
schedules, task flow, timing warmup/QC, and normal test exports remain unchanged.
Production launches do not expose the selector and continue to compile all conditions.
Participant summaries already exclude reserved IDs `0` and `00`.

The Stimuli Manager remains an internal support page for variant/materialization
behavior, not a guided setup step or visible top-level tab during normal use. Its raw
source-folder import path is permissive like guided Conditions import; strict inspection
and materialization still surface invalid or inconsistent source details before runtime
launch. Word stimulus rows are shown for readiness context but cannot use image-folder
import, inspection, or materialization actions.

The top-level menu order is `File`, `View`, `Tools`. The `File` menu groups
manage-projects, `Import` and `Export` submenus, settings, and help/update actions with
native separators. `View` offers `T1 and T2 Accuracy...` for Attentional Blink and
`Fixation Task Accuracy...` for other categories; the action is disabled
with other project actions during bundle processing. `Import > Project Bundle...` first
shows a review dialog with bundle identity, manifest file count/size, the receiving
project path, collision-safe naming guidance, and included/excluded content. Confirming
the review imports a
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
remaining visible underneath for filtering/audit. The wired `Tutorials` action remains
available internally but is temporarily hidden from the File menu until the public
tutorial section is complete. Settings shows the current app
version from `pyproject.toml` during source-tree runs and from package metadata in
bundled installs, and exposes the app-level run export mode. Full run export mode is the
default and writes detailed `runs/` folders after launch; compact mode skips those
folders and keeps only project-level summary logs. Settings also exposes default-on
Sophia Mode, which requires administrators to confirm that BioSemi recording is active
by typing `Confirm` before launch can continue. Settings can hide the Sophia Mode Home
ticker independently, without disabling that confirmation gate. In source and installed builds on Windows
and Linux, Settings also exposes Experiment Test Mode with a detailed tooltip that
names every skipped hardware/participant check and every timing behavior that remains.
Moving a project to the Recycle Bin remains a controller-owned filesystem operation
guarded by `project.json` validation, confirmation, a post-action path check, and a disk
refresh of the manage list after each attempt. `Check for Updates` delegates to the
independent updater through `HelperClient`, without blocking the GUI. It shows
current/latest versions, release notes, and the candidate patch/full installer, downloads
and verifies the package with progress, and supports this-launch-only `Remind Me Later`.
Discovery and download do not scan installed payload files; final patch compatibility
belongs to the native installer. A newer release without a trusted installer SHA-256
digest is still shown as available, with an explanation that in-app installation is
unavailable and a release-page link; it is not reported as up to date. Manual
update-check failures show a clear try-again-later message. A silent startup metadata
check runs once after the Welcome window is shown; it stays silent unless an update is
available. Independently, normal application startup schedules offline update-cache
housekeeping before root-folder onboarding, even with no configured project root or
network connection. Cache ownership and retention rules belong to the backend; see
`docs/PACKAGING.md`.

Updater workers belong to an application-level lifecycle coordinator, not the dialog
that requested them. Close, window X, and Escape cancel a busy operation and keep the
dialog responsive in `Canceling...` until the worker thread really finishes. Incomplete
downloads are discarded and retries start from zero. Application quit and last-window
closure also cancel outstanding jobs and defer final exit without a GUI-thread wait;
parent-window destruction cannot destroy a running updater thread. Cache checks run in
workers; helper subprocesses own release/download work and installation coordination. The
Install action becomes available only after the download worker thread finishes;
confirmation and any project Save prompt run on the GUI thread before the final
handoff worker starts. The staged helper authenticates the package and the registered
Studio process, then requires explicit acceptance of its ready nonce. Studio quits only
after acceptance and local worker completion. The helper waits for that identified
process to exit, installs under a separate installation lock, and restarts Studio once
after successful setup. It never force-closes Studio or edits project data. A canceled
or failed handoff keeps Studio open; setup failure opens the repair path without restart.

The update dialog has a `680x600` minimum and `760x620` default size. Its action grid
keeps long button labels visible at both sizes. Versions and status text wrap; release
notes and error details use an intentionally bounded, selectable preview with the full
value in a tooltip, and the full release page remains available by button.

The bundled **FPVS Studio Update & Repair** Start Menu entry uses the same dialog in a
separate process, at a `680x660` minimum and `760x680` default. Its full-installer repair
action supports the currently installed version and requires all Studio windows to close
before installation. It works independently of Studio's authoring/runtime dependencies.
The managed install-progress dialog has a `620x340` minimum and `700x380` default. It
shows waiting, package verification, installing, restart, cancellation, or failure states;
long error details remain accessible in a read-only scrolling field. Cancel is available
before setup begins and disabled after explicit installation commitment. Late cancellation
cannot turn a failed installation into a false cancellation message. Failure exposes
**Open Update & Repair**; successful installation closes the progress window after restart.
Helper staging, trust, locks, and native installation contracts are in `docs/PACKAGING.md`.

The Home
page keeps full project descriptions in project data but shows a
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
- In-app update presentation lives in `src/fpvs_studio/gui/update_dialog.py` and calls
  `updates/helper_client.py` through workers. `gui/updater_window.py` owns standalone
  Update & Repair and managed install progress, reusing the existing component layer.
  `src/fpvs_studio/updater_main.py` selects backend pipe, standalone, or apply mode.
  Protocol, staging, registered identity, package trust, and installation coordination
  stay in `updates/helper_*`; complete patch checks and file replacement remain in Inno.
- App-owned updater worker/cancellation lifetime lives in
  `src/fpvs_studio/gui/update_lifecycle.py`; `application.py` owns startup and the final
  asynchronous shutdown drain. These contain no cache-retention or installer-trust rules.
- Startup offline cache-housekeeping and one-shot metadata-check orchestration live in
  `src/fpvs_studio/gui/controller.py`; housekeeping errors are nonfatal/logged, and the
  metadata check should stay silent unless a newer release is available.
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
- configuring fixation settings, with the fixation accuracy task (Space within 1.0 s of
  each fixation color change) and participant tutorial enabled by default while remaining
  independently user-configurable
- configuring fixed or randomized fixation target counts per condition run; compiled
  color changes are balanced across the full condition with seeded jitter and
  deterministic no-immediate-repeat behavior across consecutive compiled runs
- checking for app updates from `File > Check for Updates`
- reviewing the active project's pooled fixation accuracy and reaction-time history from
  `View > Fixation Task Accuracy...` without modifying logs or scoring, with an optional
  Excel export written only to the user-selected destination
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
- Experiment Test Mode in source and installed builds on Windows and Linux composes those settings
  to disable serial and connected-refresh checks while preserving fullscreen playback,
  compilation, asset checks, timing QC, task flow, and exports; its per-launch selector
  defaults to all conditions and may instead compile one condition without changing its
  configured block count or pre/post tasks

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

Add or update registered pytest-qt coverage for changed GUI behavior. Ordinary local
verification excludes registered Qt modules before import and runs backend, boundary,
lint, and compilation checks:

```powershell
./scripts/verify.ps1 -Scope gui -Tier focused
```

Do not set `QT_QPA_PLATFORM=offscreen`. Registered Qt tests run only through the optional
`full` tier with `FPVS_ALLOW_QT_TESTS=1`, explicit user approval, and a safe visible
environment. There is no GitHub test workflow to run them automatically.

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
  project details, `test_setup_conditions.py` for condition identity and the Design
  import/normalization handoff, `test_design_setup_step.py` and
  `test_experiment_designer.py` for embedded editing, and
  `test_experiment_categories_gui.py` for category-specific controls,
  `test_setup_experiment_display.py` for display/session/image-size settings,
  `test_setup_review.py` for review/return behavior, `test_home_launch_surface.py`
  for Home, `test_run_page_launch.py` for launch wiring, and
  `test_image_resizer_page.py` for the utility page

Local handoff must document a visible manual smoke path for the changed workflow and
state whether registered Qt coverage was not run or ran in an explicitly approved
visible environment.

Updater visible/manual smoke (run only in an approved visible Windows session):

1. Open `File > Check for Updates` and inspect the `680x600` minimum and `760x620`
   default sizes with long versions, release notes, and error details. Check every action
   label, wrapped status, the full-detail tooltip, and release-page action without resizing.
2. Using controlled offline callbacks (as in `tests/gui/test_update_dialog.py`), exercise
   current, newer/trusted, newer/missing-digest, busy, canceled, and failed states. A
   missing digest must disable Download/Install while preserving the newer-version copy.
   Verify progress beyond 2 GiB with synthetic byte counts, not a large real download.
3. Hold fake metadata/download/verification work open, then use Close, X, and Escape.
   Check that cancellation is visible, controls stay responsive, and the dialog closes
   only after worker completion. Repeat with application quit, last-window closure,
   parent destruction, and first-run root-picker cancellation. No running-thread warning
   or hidden updater job may remain; temporary root-picker transitions must not quit.
4. Stub installer launch and confirmation/save prompts. Confirm that neither hashing nor
   launching occurs on the GUI thread, Install stays disabled until download-thread
   completion, declining/canceling never launches, and an accepted fake handoff quits only
   after its worker finishes. Closing/destroying a prompt must not start a hidden launch.
5. With offline service callbacks, inspect **Update & Repair** at `680x660` and `760x680`.
   Check same-version full repair, unavailable metadata, package progress, and all button
   labels without clipping. Close before deferred startup and while work is pending.
6. Exercise the independent apply dialog at `620x340` and `700x380` with fake callbacks.
   Check long failure details, waiting/cancellation, success, and the repair transition.
   Simulate setup commitment before the GUI receives its phase signal, then cancel and
   return a failed setup result: it must show failure/repair and never claim cancellation
   before installation. Do not execute a real installer for this GUI check.

The registered updater module contains deterministic fake-worker cases for these paths;
source/lint/compilation checks do not validate real Qt event delivery or visible layout.
Actual installer/upgrade lifecycle checks remain separately documented in
`docs/PACKAGING.md`; this smoke must not launch a real installer or clean a real cache.
The completed independent-updater plan records verification performed and remaining installed
or clean-PC acceptance; implementing these surfaces does not establish those results.

## Setup Design And Manual Acceptance

The shared component owner supplies theme-aware form fields, keyboard focus states,
validation text, dialog headers, and button roles. Settings groups preferences into
Workspace, Participant runs, and Development; preferences still save immediately.
Its minimum/default size is `700x520` for packaged builds and `700x610` for source runs.
Presentation (`900x600` minimum) and FPVS Condition Modifiers retain staged Apply/Cancel behavior.
Native dropdown/spinner affordances and system file pickers remain available.

Review uses factual summaries for project, conditions/task bindings, Design, Timing, Image Size,
Session, and Fixation/Response, with effective tutorial status in Project. Edit actions
follow ready-project step-jump permissions. Review's completion actions use the shared
bottom navigation outside the summary frame: Return Home Without Saving on the left,
Back and Save and Return Home on the right. Other steps retain Return Home, Back, and
Next in that row. Saving returns Home with the existing nonmodal status-bar confirmation;
returning without saving explains that edits remain in memory until the project closes.
Design uses the task-specific Design your sequence header. Next applies a valid
design draft before the existing image-readiness handoff; there is no second Apply
button on that page. The source shelf, schematic stream and proportional target-pair
detail follow [Visual Experiment Designer](VISUAL_EXPERIMENT_DESIGNER.md).
Fixation displays the effective smallest count limit, identifies the limiting condition,
and explains count adjustments caused by changed durations; full per-condition limits
remain accessible in the tooltip.

For visible acceptance on Windows, walk all eight steps at `1120x820` in both themes,
then repeat at the normal expanded size and available 125/150% scaling. Include long
condition names and source paths, image and word conditions, missing-field recovery,
verification busy/failure/verified states, and unequal condition durations. Inspect
Settings, Presentation, and FPVS Condition Modifiers at their documented sizes; check keyboard
focus and popup controls. Save/reopen to verify persistence, and confirm Cancel leaves
staged dialogs unchanged. The implementation's registered Qt coverage is separate from
this manual review and is not run by ordinary local verification.


### Attentional Blink Pilot Study Mode

For an open AB study on Windows/Linux, Settings > Enable Pilot Study Mode
(Attentional Blink) enables local pilots with the standard participant number, age,
sex, handedness and colorblindness form. It defaults off, persists for this computer,
and takes precedence over Test Mode only in AB. Other categories retain Test Mode's
existing behavior. The participant dialog identifies a pilot without EEG hardware.
Repeat-visit rules still apply to entered participant numbers.

Pilot uses null triggers, skips Sophia recording confirmation and connected-display
refresh/graphics verification, and preserves fullscreen playback and compiled timing.
T1/T2 accuracy includes pilots; Bursts over time marks them Pilot. Hover the participant
cell for demographics; Export Excel includes flat demographics and Pilot columns.
The Settings minimum/default is 700 x 680 when Pilot is available (otherwise unchanged).
