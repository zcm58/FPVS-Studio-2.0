# Setup Wizard Unified UX Refresh

Status: Completed

Completed: 2026-05-07

Progress:

- Phase 1 completed: plan added and current wizard/component inventory reviewed.
- Phase 2 completed: shared setup wizard component layer added.
- Phase 3 completed: wizard shell uses the connected stepper and bottom status strip.
- Phase 4 completed: guided Conditions step now uses the left/main/right setup
  workspace, source cards, protocol defaults, and reusable setup checklist.
- Phase 5 completed: remaining setup steps align with the shared wizard language where
  useful, and `Stimuli` now appears before `Conditions` to support future image
  preparation workflow integration.
- Phase 6 completed: final polish and verification pass completed.

## Purpose

Refresh the FPVS Studio Setup Wizard into a cohesive, polished, Windows-native
PySide6 wizard experience using the provided Conditions-step mockup as the primary
visual target and design-system seed.

This is a GUI/UX refactor only. It must not change project schema, project document
shape, compiler behavior, runtime behavior, preprocessing behavior, PsychoPy launch
behavior, export contracts, generated file formats, validation semantics, or the
order of any processing steps.

The Conditions step mockup is the canonical target for:

- top wizard shell structure
- connected horizontal progress stepper
- three-zone workspace layout
- right-side protocol/checklist summary panels
- ready/error status badges
- source image cards
- footer action layout
- copy tone for guided versus advanced timing controls

All other setup steps should use the same visual language, spacing, typography, and
panel conventions, while keeping each step's content appropriate to its purpose.

## Non-Negotiable Boundaries

- Windows-only PySide6 implementation.
- No CustomTkinter.
- Do not modify black-box modules:
  - `Main_App/Legacy_App/**`
  - `Tools/SourceLocalization/**`
- Call only public APIs or thin adapters around public APIs.
- Do not change processing order.
- Do not change backend field names or serialized project document keys.
- Keep raw model field `stimulus_variant` unchanged.
- Keep existing mutation path through project document/controller services.
- Do not introduce hard-coded user paths.
- All file/folder reads and writes must remain under the active project root and
  standard project subfolders.
- No UI-thread blocking.
- Long work must use Qt worker patterns with signals.
- No worker may touch widgets directly.
- No `print`.
- No silent catches.
- Use structured logging with operation context.
- Keep stable object names where existing tests rely on them.

## Visual Target Summary

The mockup shows a calm, spacious, lightly bordered Windows desktop wizard. The page
is visually divided into:

1. Native app/menu chrome.
2. Centered wizard title and progress stepper.
3. Main setup workspace.
4. Footer navigation/action bar.
5. Thin bottom status/help strip.

The Setup Wizard header should show:

- `Setup Wizard`
- `Step X of 7: Step Name`

The stepper labels, in order:

1. `Project Details`
2. `Stimuli`
3. `Conditions`
4. `Display Settings`
5. `Session Design`
6. `Fixation Cross`
7. `Review`

Stepper visual states:

- Completed: green circular icon with check mark.
- Current: blue circular icon with white number and bold blue label.
- Upcoming: light circle with muted label.
- Connector lines span between step groups.
- No pill-style progress labels.

Required stable object names:

- `setup_wizard_progress_header`
- `setup_wizard_progress_steps`

Add clear child object names for tests:

- `setup_wizard_step_1_project_details`
- `setup_wizard_step_2_stimuli`
- `setup_wizard_step_3_conditions`
- `setup_wizard_step_4_display_settings`
- `setup_wizard_step_5_session_design`
- `setup_wizard_step_6_fixation_cross`
- `setup_wizard_step_7_review`

## Main Workspace Layout

The Conditions step uses a three-zone workspace:

1. Left rail: condition navigation and condition actions.
2. Main editor: selected condition details and image sources.
3. Right rail: protocol defaults and setup checklist.

Preferred structure:

- Outer vertical layout:
  - header/title area
  - progress stepper
  - workspace
  - footer bar
  - bottom help/status bar
- Workspace horizontal layout:
  - optional left rail
  - main editor
  - optional right rail

Not every step needs all three columns. The Conditions step must closely match the
mockup. Other steps should reuse the visual language without forced redesign.

## Shared Components To Add Or Enhance

Add reusable wizard-specific components through `src/fpvs_studio/gui/components.py`.
Keep project state, validation, compiler behavior, and runtime behavior out of this
component layer.

### `SetupProgressStepper`

Render the seven setup steps as a connected horizontal progress indicator.

Responsibilities:

- Accept step labels and active step index.
- Render completed/current/upcoming states.
- Expose stable object names for tests.
- Preserve accessible text/tooltips.
- Avoid hard-coded per-step geometry.
- Re-render safely when active step changes.

### `SetupWorkspaceFrame`

Provide the standard setup page workspace surface.

Responsibilities:

- Host left rail, main editor, and right rail.
- Allow steps to omit left or right rails.
- Apply standard margins, gaps, and responsive behavior.
- Prevent nested card visual clutter.
- Keep main content aligned with side panels.

### `SetupSidePanel`

Reusable right-column card for:

- protocol defaults
- step summaries
- setup checklist
- readiness summaries
- derived metrics

### `SetupChecklistPanel`

Enhance the existing reusable checklist panel.

Visual target:

- Card title such as `Setup Checklist`.
- Divider line under the title.
- Rows with left status mark, label, and optional right-aligned status.
- Complete rows use green check marks and green status text.
- Incomplete rows use clear red/missing status.

Checklist rows must be display-only. The owning page supplies simple state values.

### `SetupSourceCard`

Reusable base/oddball image source summary card.

Each card includes:

- title, such as `Base Images`
- readiness badge
- project-relative folder display
- image count
- resolution
- variants/image versions
- choose-folder button

The card must emit user intent only. Existing pages/controllers still call
`ProjectDocument.import_condition_stimulus_folder(...)`.

### `SetupMetricStrip`

Reusable compact metric rows for derived values:

- estimated duration
- base rate
- oddball rate
- oddball interval
- total oddball cycles
- refresh rate
- block count
- planned run count

## Conditions Step Target

The Conditions step is the primary high-fidelity target.

### Left Rail

Card title:

`Condition List`

Subtitle:

`Create, remove, and reorder conditions.`

Actions:

- `+ Add Condition`
- `Duplicate`
- `Remove`

The left rail keeps existing condition creation, duplication, and removal behavior.
Visible condition order remains organizational only and must not change runtime
randomization semantics.

Suggested object names:

- `setup_conditions_left_panel`
- `setup_conditions_condition_list`
- `setup_conditions_add_button`
- `setup_conditions_duplicate_button`
- `setup_conditions_remove_button`

### Main Editor

Main title row:

- `Selected Condition`
- readiness badge
- right-aligned metadata such as condition id and trigger code

Fields:

- `Condition Name`
- `Trigger Code`
- `Participant Instructions`

Image sources:

- `Base Images` source card
- `Oddball Images` source card

Suggested object names:

- `setup_conditions_main_panel`
- `setup_conditions_name_input`
- `setup_conditions_trigger_input`
- `setup_conditions_instructions_input`
- `setup_conditions_image_sources`
- `setup_conditions_base_source_card`
- `setup_conditions_oddball_source_card`
- `setup_conditions_choose_base_button`
- `setup_conditions_choose_oddball_button`

### Right Rail

Top panel: `Protocol Defaults`

Rows:

- `Timing Template:` -> `50% Blank Between Images`
- `Image Version:` -> `Original`
- `Estimated Duration:` -> derived value
- `Base Rate:` -> derived value
- `Oddball Rate:` -> derived value

Action:

- `Edit Advanced Timing`

Helper:

- `Most projects should keep these defaults.`

Second panel: `Setup Checklist`

Rows:

- `Name`
- `Trigger`
- `Base Images`
- `Oddball Images`

Suggested object names:

- `setup_conditions_protocol_defaults_panel`
- `setup_conditions_edit_advanced_timing_button`
- `setup_conditions_checklist_panel`

## Guided Language And Timing Copy

The guided wizard should show derived meaning first and raw timing knobs only in
Advanced.

Guided UI:

- Replace `Stimulus Variant` with `Image Version`.
- Do not show `Cycles / Repeat` in normal guided setup screens.

Backend:

- Keep raw model field `stimulus_variant` unchanged.
- Do not rename serialized keys.
- Do not alter saved project document format.

Advanced timing UI may rename or explain visible labels:

- `Condition Repeats` -> `Condition Runs`
- `Cycles / Repeat` -> `Oddball cycles per run`

Derived values to prioritize:

- estimated condition duration
- base rate
- oddball rate
- oddball interval
- total oddball cycles
- timing template
- image version

## Footer And Status Strip

Footer actions remain:

- `Return Home`
- `Advanced`
- `Back`
- `Next`

Required stable object names:

- `setup_wizard_back_button`
- `setup_wizard_next_button`
- `setup_wizard_return_home_button`
- `setup_wizard_advanced_button`

The bottom help/status strip is intentionally reintroduced as shell chrome because
the selected mockup includes it. It should not become repeated instructional copy
inside each step.

Suggested object names:

- `setup_wizard_status_strip`
- `setup_wizard_status_message`
- `setup_wizard_runtime_mode_label`

## Per-Step Direction

All steps share the same wizard shell, progress stepper, footer, tokens, and panel/card
language.

- `Project Details`: project name, description, project folder, condition template,
  with right-side checklist.
- `Stimuli`: image preparation, source inspection, resize/convert entry point,
  variant generation, and readiness guidance. This step comes before `Conditions`
  so users can normalize image folders before assigning them to conditions.
- `Conditions`: condition naming, trigger codes, participant instructions, and explicit
  base/oddball folder assignment. Keep this step focused on experiment structure.
- `Display Settings`: refresh rate, fullscreen, launch/display target, compatibility
  summary.
- `Session Design`: block count, randomization/order behavior, seed, transition
  behavior.
- `Fixation Cross`: fixation enabled, accuracy task enabled, appearance/timing summary,
  feasibility/readiness checklist.
- `Review`: grouped readiness, blockers, warnings, final validation status.

## Component Architecture

UI components:

- render state
- emit user-intent signals
- expose object names
- show non-blocking UX notices when instructed by controller/page

Controller/services:

- own project state
- perform validation
- mutate project document
- resolve project paths
- start long tasks
- handle backend operations

The wizard should derive display state from the active project document and existing
validation/readiness services. Do not create a second independent validation model
inside widgets.

## Project Path Discipline

Rules:

- Display project-relative paths where suitable.
- Resolve absolute paths only through the active project root.
- Prevent path traversal outside project root.
- Do not embed user-specific paths in UI code, tests, or defaults.
- Do not assume a fixed drive letter or project name.
- Dialog Cancel does nothing and does not clear existing values.

## Error UX And Logging

Errors should be non-blocking unless existing behavior requires a modal confirmation.

Use:

- status bar message
- inline validation state where appropriate
- structured logger entries

Do not use:

- `print`
- silent `except`
- broad unqualified catches
- modal dialogs for routine validation noise unless existing UX already does so

## Accessibility And Keyboard Behavior

Requirements:

- Logical tab order through condition list, actions, fields, source buttons, advanced
  timing, and footer actions.
- Buttons must have accessible names matching visible labels.
- Icon-only elements must have tooltips or accessible names.
- Selected condition row must have visible focus state.
- Inputs should preserve focus during state refresh where possible.
- Color must not be the only readiness indicator; keep labels like `Ready`, `Complete`,
  and `Missing`.

## Implementation Phases

### Phase 1 - Plan And Inventory

Create this active exec plan and inventory the current wizard shell, progress header,
Conditions step, shared component module, theme tokens, document mutation path, image
source selection path, advanced timing entry point, and test object-name expectations.

### Phase 2 - Shared Component Layer

Add or enhance shared setup components:

- `SetupProgressStepper`
- `SetupWorkspaceFrame`
- `SetupSidePanel`
- `SetupChecklistPanel`
- `SetupSourceCard`
- `SetupMetricStrip`

Add focused pytest-qt tests for these components.

### Phase 3 - Wizard Shell Refresh

Replace current top progress pills with `SetupProgressStepper`.

Preserve:

- wizard title
- current step subtitle
- footer buttons
- navigation behavior
- stable object names

Add/refine:

- bottom help/status strip
- shell spacing
- high-DPI-safe layout behavior

### Phase 4 - Conditions Step Refresh

Rebuild the Conditions step layout to match the mockup.

Preserve:

- existing field values
- existing mutation behavior
- existing validation semantics
- existing image source selection behavior
- advanced timing entry point

### Phase 5 - Remaining Step Alignment

Update remaining steps to share shell/component language. Do not force identical
layouts. Use the three-zone pattern only where appropriate.

Include the planned wizard-order change when the image preparation plan becomes
active: `Stimuli` should become step 2 and `Conditions` should become step 3.
That change must preserve existing condition mutation behavior and should not
silently resize images to satisfy validation.

### Phase 6 - Polish, Edge Cases, And Verification

Polish spacing, alignment, button sizes, focus states, badges, disabled states, empty
states, high-DPI scaling, and keyboard tab order.

## Test Plan

Add focused pytest-qt coverage for shared wizard components:

- `SetupProgressStepper`
- `SetupChecklistPanel`
- `SetupSourceCard`
- `SetupMetricStrip`

Add Setup Wizard tests:

- progress stepper uses connected numbered/check states
- Conditions step has left condition list
- Conditions step has main selected-condition editor
- Conditions step has right protocol/checklist panels
- wizard step order is Project Details, Stimuli, Conditions, Display Settings,
  Session Design, Fixation Cross, Review
- Stimuli step can point users toward image preparation when mixed resolutions are
  detected without hiding validation errors
- non-step object names remain stable; step object names should reflect the new order
- `Stimulus Variant` no longer appears in guided Setup Wizard UI
- `Image Version` appears in guided Setup Wizard UI
- `Cycles / Repeat` no longer appears in guided Setup Wizard UI
- Advanced timing still exposes or explains existing backend fields
- footer actions remain stable
- bottom help/status strip appears

Verification commands:

```powershell
python -m ruff check src tests
python -m pytest -q tests\unit\test_harness_docs.py
.\scripts\check_gui.ps1
.\scripts\check_quality.ps1
```

Run focused pytest-qt tests while iterating.

## Assumptions

- The referenced Conditions-step mockup is the visual target and design-system seed.
- Phase 2 and Phase 3 may land before the full Conditions-step rebuild.
- The bottom status/help strip is acceptable as shell chrome, but redundant per-step
  instructional copy should stay out of the content cards.
- Advanced controls remain available, but ordinary users should see defaults and
  derived meaning first.
