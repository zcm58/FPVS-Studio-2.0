# Frontend

FPVS Studio's frontend is the Windows-focused PySide6 GUI. There is no web frontend in
the active app.

## Public GUI Surface

- Start GUI work from `../src/fpvs_studio/gui/AGENTS.md`.
- Use `../src/fpvs_studio/gui/components.py` for shared widgets, button roles, labels,
  status badges, and theme helpers.
- Use `../src/fpvs_studio/gui/design_system.py` for tokens and tiny text helpers.
- Keep detailed behavior and test guidance in `GUI_WORKFLOW.md`.

## Skill Routing for GUI Work

For substantial interface changes, use the brief, research and review criteria in
[agent UI design guidance](design-docs/agent-ui-design.md). The owning AGENTS.md files
carry concise local rules; keep this document's existing product contracts authoritative.

FPVS Studio's frontend remains PySide6. Global UI skills may help agents reason about
the product experience, but implementation must keep using PySide6 widgets, the shared
component layer, Qt worker patterns, and registered pytest-qt coverage.

- Use `.agents/skills/pyside6-gui-cleanup` for widget refactors, dialog polish, shared
  component usage, status/error UX, worker/threading checks, and QAction import cleanup.
- Use `.agents/skills/pytest-qt-smoke` when GUI behavior changes need focused smoke
  coverage.
- Use `diagnose` before editing when a GUI test hangs, a modal blocks, a worker thread
  does not finish, or a layout/runtime regression is reported. Start from a single
  pytest node or focused script with an explicit timeout.
- Use `impeccable` / `delight`, `frontend-design`, or `ui-ux-pro-max` only for concrete
  PySide6 product-design questions such as Setup Wizard density, Home launch hierarchy,
  button role clarity, empty/error state wording, or visual consistency with
  `gui.components`.
- If those global UI skills suggest web, React, Tailwind, browser animation, mobile, or
  deployment patterns, translate only the relevant design intent into existing PySide6
  components and discard the stack-specific advice.
- Use `web-design-guidelines` only for `../docs-site/` or MkDocs web documentation UI,
  not for the desktop authoring app.

GUI verification uses `./scripts/verify.ps1 -Scope gui -Tier focused`
plus a documented visible manual smoke path. Registered pytest-qt coverage is retained
for an optional approved visible `full` run; use the repo precommit tier when GUI work
touches multiple layers.

Library version review makes **Update current project** primary and retains
**Download separately** as a secondary action. The canonical interaction, backup,
Results and recovery contract is [Experiment Library](EXPERIMENT_LIBRARY.md#project-version-checks).

## No-Clipping Baseline

No clipping is an initial GUI design constraint, not a later polish task. Before building
or revising a surface, define its minimum/default size and budget for realistic longest
project names, filesystem paths, button labels, validation messages, status copy, and all
dynamic states. Required controls and text must be visible without user resizing.

Registered pytest-qt coverage must show the surface at that size, process layout events,
and check both child-widget geometry and full text width. Wrapping must have enough
vertical space. Elision is allowed only when deliberate and when the complete value
remains available through a tested tooltip, copy action, or equivalent accessible
interaction.

## GUI Architecture

- First-run startup shows a concise FPVS Studio Root Folder setup guide before the
  native folder picker when no valid root is configured.
- Home is the daily launch surface for ready projects, centered around one launch
  card with create, import, open, setup, readiness, summary metrics, and the primary
  launch action.
- Welcome and Home share the same launch-surface frame/styling so opening a ready
  project keeps a stable outer window and card treatment.
  Home's four project actions use two rows at the `760x520` minimum and one row at
  `1120x720`. Empty optional descriptions are hidden; authored descriptions remain visible.
- Main-window styles use the shared palette observer and refresh the existing Setup
  page's palette. Application theme changes use fresh colors so the client area stays aligned
  with Qt's native Windows title bar and minimize/maximize/close controls.
  Shared cards and fixation-editor local styles refresh through the same palette observer.
- File > Find Action opens searchable existing commands
  with `Ctrl+F`. Conditions has a name/trigger filter that retains the selected
  editor context. Interaction and sizing contracts live in
  [GUI workflow](GUI_WORKFLOW.md#action-discovery-and-condition-search).
- Setup Wizard enforces `1120x820` as its minimum and default size. Its eight steps are
  Project, Conditions, Timing, Display & Session, Image Size (Character Size for native AB),
  Fixation, Response, and Review. All steps share the frameless
  shell, left-aligned task heading, step count, and stable progress
  stepper. Bottom navigation remains at the window edge with no divider. Forms retain
  bounded readable widths. Content is top-aligned at a shared 24 px inset beneath
  the stepper, with a 24 px bottom inset. All steps must fit without clipping or
  required scrolling; the page layout map lives in
  [GUI workflow](GUI_WORKFLOW.md#frameless-setup-layout-and-copy).
- Project uses two aligned sibling cards for Project details and Experiment setup,
  with distinct headings and compact field labels. Its description
  is optional, editable and persisted; refresh preserves pending project-name edits. Idle **Next** stays
  enabled on incomplete steps and reports the current blocking requirement in an
  actionable modal when clicked, preserving the step and drafts. Page opening and
  typing do not trigger dialogs. Image import, normalization and display verification
  still disable Next while busy, with separate concise status; the former
  `To continue` footer and `Show field` action are removed.
- Conditions is a combined guided setup area for condition list/actions, names,
  triggers, instructions, modality selection, Base/Oddball image-folder selection, typed word-list
  authoring, manual condition add/duplicate/edit, and image normalization. It uses compact list
  rows and source cards, separating `All conditions` repeat settings from
  `This condition` fields. Image sources have keyboard-accessible full-path details
  and copy. The highlighted condition's Base Images and Oddball Images buttons open
  folder pickers and use worker-backed fresh-source imports without image previews.
  Instructions use an Edit Instructions dialog with Save/Cancel; empty Save clears
  the instructions and Cancel preserves them. Default and short condition names
  are accepted subject to core's existing nonempty name schema.
  Conditions uses the available vertical space for its list and word editors;
  its details card retains its natural height above the source area. Ready Conditions
  has aligned navigator/editor tops, with search above the list and no routine hint. See
  [GUI workflow](GUI_WORKFLOW.md) for mode labels and sizing acceptance.
  Raw image-folder selection is permissive; uniform rectangular sets are valid native inputs, while inconsistent
  dimensions within a set are handled by the guided normalization flow when advancing
  from Conditions. Image normalization/materialization remain image-only paths. Existing
  conditions retain their variants and runtime transforms. A
  condition-level `FPVS Condition Modifiers` dialog makes simple before/after
  questions the primary actions, opening a blank Yes/No builder directly. Existing
  questions remain editable from the dialog's list. Add Question and numbered-list
  Up/Down controls support multiple questions and independent before/after display
  order, preserved on save and compilation. Counting, Memory, Masking, presets and
  custom tasks live in collapsible Advanced modifiers; response-folder/rebuild
  controls are shown only while it is expanded, with the full CSV path in the folder
  button's tooltip. Question assignment stays in the parent modifier dialog, optional
  help uses tooltips, and a valid preview clears any stale validation error. Assignments and
  detached Apply/Cancel behavior are preserved within the eight-step wizard;
  task media is staged until Apply and stored beneath the active project's
  `stimuli/task-assets/<task-id>/`. Before answers use ordinary task exports; the
  readable root CSV remains after-only. See `CONDITION_MODIFIERS.md` and
  `POST_CONDITION_QUESTIONS.md`.
- Setup has no Design section. Timing retains frequency edits. Saved AB
  settings are preserved; the retained native AB editor and standalone image visual
  editor remain outside the guided workflow.
- Fixation and Response are split guided setup areas: Fixation handles color-change
  schedule/timing, while Response handles accuracy tracking, response key/window,
  appearance, and preview.
- Open Existing Project is the welcome entry point for Manage Projects
  and the first, primary blue action with initial focus and Enter activation.
  Create Project, Import New Project and Change Root Folder remain secondary actions.
  Manage Projects opens known projects or moves project folders to the Windows Recycle Bin with
  confirmation. Import New Project uses the same reviewed `.fpvsbundle` import workflow
  exposed in the File menu, and Welcome accepts dropped local `.fpvsbundle` files while
  keeping modal staged progress visible. Successful bundle exports remain on a persistent
  result page until the user opens/copies the destination or selects Done. Bundle export
  can assign a distinct project name to the portable copy without changing the open
  project, and imports always target the configured absolute FPVS Studio Root Folder.
- Settings uses a flat header/section/control hierarchy without nested cards. Its
  exclusive Light/Dark/Auto toggle applies a persisted computer preference immediately;
  Auto follows the OS theme. Existing root/template, run export, Recording Reminder,
  Test/Pilot, recording, developer and diagnostics workflows retain their eligibility
  and callbacks. App preferences remain outside project files. Shared dialog headers
  and form-control styles also cover the staged Presentation and Condition Modifiers
  editors. Exact layout, persistence/error behavior and sizing acceptance live in
  [Settings appearance and layout](GUI_WORKFLOW.md#settings-appearance-and-layout).
- The current Setup Wizard does not expose Advanced buttons; dense/internal support
  pages should remain behind guided workflows unless a future plan explicitly
  reintroduces them.
- GUI code may coordinate document services and runtime launches, but core validation,
  compilation, session planning, and runtime flow remain outside widgets.
- Keep presentation refreshes demand-driven: hidden Home/Assets/Run pages defer
  document notifications until shown, and closed Find Action refreshes on reopening.
  AB previews share derived descriptions within one edit only. Manage Projects scans
  through the app-owned job lifecycle with loading, close and retry states; see
  [GUI responsiveness](GUI_WORKFLOW.md#authoring-and-project-discovery-responsiveness).
- Settings > Recording exposes project BioSemi/TriggerBox serial-port selection.
  actiCHamp parallel output has a separate hexadecimal address selector with
  metadata-only Windows detection and shared sampling-rate/pulse controls.
  Other serial parameters, display selection and fullscreen policy remain
  backend/runtime contract values outside runtime launch controls.

## Verification

- Run `./scripts/verify.ps1 -Scope gui -Tier focused` locally.
- Document a visible/manual smoke path for the changed surface.
- Add or update registered pytest-qt no-clipping coverage at the documented
  minimum/default size, with realistic long content and relevant dynamic states.
- Setup Wizard layout changes must update compact no-clipping coverage in
  `tests/gui/test_setup_wizard_shell.py` for all eight steps at `1120x820` and affected
  Conditions/dialog coverage. Retained AB-editor tests remain separate from Setup.
- Do not run Qt unless the user approves a safe visible environment. Use the optional
  `full` tier with explicit opt-in, and do not use offscreen execution.
- Run `./scripts/verify.ps1 -Scope repo -Tier precommit` when GUI changes
  touch multiple layers.


## Setup text hierarchy

The user prefers application GUIs without secondary explanatory text. Keep headings,
control labels, essential current status and actionable errors visible; put optional
explanations and technical detail in tooltips instead of subtitles and help paragraphs.
Preserve participant-authored instructions and information needed for the current decision.

Use one task heading per step. Top-aligned content shares a 24 px inset and uses
bounded workspaces. Project, Review and ordinary image geometry use the same 1040 px
cap as the wider setup pages. Field labels belong close
to their controls: Project and Timing use stacked labels, while denser forms align
labels consistently against the input column. Shared form treatment lives in
`components.configure_setup_form`; retain the frameless shell and bottom navigation.

Visible descriptive text must help with the current field, explain a consequential
action, or resolve a current error. Avoid repeating the page title, control label,
completed state or another step's settings. Conditions owns source selection and
the participant-instructions dialog. Timing owns ordinary FPVS shared frequency and
confirmed per-condition overrides, stream-only seconds and total presentation counts,
with a compact Display refresh rate selector for resolving durations on the same page.
It edits the shared display target, synchronized with Display & Session. Display also
owns the optional Check refresh rate action and background.
Timing keeps shared refresh/frequency/cadence controls in one toolbar above a table
that uses the remaining height; native AB retains its dedicated timing surface.
Display & Session has two soft-framed columns with shared section headings; the three
reuse choices use compact semibold field labels. Image geometry uses two cards for
stimulus size and calibration, Response uses three columns for response/appearance/preview,
and Review uses an aligned summary grid with Session spanning two rows. Side-by-side
cards share top and bottom edges, with content anchored at the top. Timing retains the `experiment` key
and timing aliases; display/runtime/session open the combined step. Show a concise verification
result and current errors inline; technical monitor observations remain in tooltips.
Keep **Edit condition order...** only in Display & Session. It opens the
**Pseudorandom Condition Order Editor**, where dragging conditions within fixed block
headers sets the saved order; Alt+Up/Down provides keyboard moves. Timing defers saved-order conflicts to Session
so this sole entry stays reachable; Save order still commits staged timing/counts atomically.
Keep Next's blocking guidance in its click-triggered dialog, without a duplicate
footer hint. Participant-authored instructions
and actual validation rules are preserved.
