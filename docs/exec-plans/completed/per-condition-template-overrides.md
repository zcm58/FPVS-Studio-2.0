# Per-Condition Template Overrides

Status: Completed

## Summary

Allow authors to choose the image-timing template for each condition from the Conditions
setup page. The project-level image-timing selector remains the default for new
conditions, but individual conditions can override that default so one project can mix
Continuous Images and 50% Blank Images conditions.

Implementation outcome: the first pass exposes built-in timing modes only, persists no
condition-level profile provenance, keeps Target Stimulus Repeats project-wide, and makes
project-level default changes future-only unless the existing explicit apply-to-all
button is used.

## Problem

The current guided workflow treats the Project image-timing selector as the user-facing
source of truth for condition duty-cycle mode. Changing that selector standardizes all
existing conditions to the selected profile. That is clean for simple projects, but it
does not support experiments where different conditions intentionally use different
temporal structures, such as continuous-image control conditions mixed with 50% blank
task conditions.

The core model already stores timing fields on each `Condition`, including
`duty_cycle_mode`, `sequence_count`, and `oddball_cycle_repeats_per_sequence`. The
workflow gap is primarily authoring: users cannot clearly inspect, change, or preserve a
condition-specific template choice from the Conditions setup page.

## User Workflow

Authors still choose a default image-timing template while creating or setting up a
project. That default seeds new conditions and stays visible as the project-level
default.

On the Conditions setup page:

- each condition row shows its current timing template, for example `Continuous Images`
  or `50% Blank Images`
- selecting a condition opens condition details that include a timing-template control
  near the condition identity and stimulus settings
- changing one condition's timing template updates only that condition
- adding a new condition uses the current project default unless the user explicitly
  changes that condition
- a project with mixed timing modes clearly communicates that state in the Conditions
  step and Review step

The Project step should no longer imply that changing the project default is the only
source of truth for all conditions. If the project default is changed after conditions
already exist, the UI should offer an explicit choice:

- apply the new default to all existing conditions
- keep existing per-condition choices and use the new default only for future conditions

## Scope

First implementation scope:

- built-in timing-template choice per condition for Continuous Images and 50% Blank
  Images
- project-level default remains available and still seeds condition defaults
- condition-level overrides affect only condition timing fields currently owned by
  `Condition`
- compile, validation, and runtime behavior continue to consume the resolved
  condition-level fields already embedded in each compiled `RunSpec`
- project files remain compatible with existing persisted `Condition.duty_cycle_mode`
  values

Out of scope for the first pass:

- per-condition display geometry, fullscreen behavior, background color, refresh rate, or
  fixation-task settings
- arbitrary base frequency or oddball interval editing beyond existing template/profile
  defaults
- a separate condition-template library schema for partial per-condition overrides
- changing the frame-accurate scheduling behavior of continuous or 50% blank playback

## Design Direction

Treat the project-level condition template as a default, not as a permanent global lock.
The persisted source of truth for launch should remain each `Condition`'s resolved timing
fields. The GUI may expose those fields as a friendly template selector, but the compiler
should not need to reach back into the app-level template library at launch time.

Recommended model/API shape:

- keep `ProjectSettings.condition_profile_id` and `condition_defaults` as project-level
  defaults
- continue storing resolved timing fields directly on each `Condition`
- consider adding a nullable `Condition.condition_profile_id` only if the UI needs to
  show provenance for custom templates; do not require it for built-in Continuous/Blank
  behavior because `duty_cycle_mode` is already sufficient for launch
- add document-layer helpers such as `update_condition_timing_template(condition_id,
  profile_or_mode)` so widgets do not duplicate condition-default application rules
- keep `apply_condition_template_profile_to_settings()` for project defaults, and add a
  separate helper for applying only `ConditionTemplateDefaults.condition` to one
  condition

## GUI Plan

Conditions setup page:

- add a compact timing-template selector for the selected condition
- show the current timing template in each condition row or row subtitle
- keep the existing project-wide Target Stimulus Repeats control, but clarify whether it
  is project default, selected condition value, or both before implementation
- if Target Stimulus Repeats remains project-wide, do not silently overwrite mixed
  per-condition timing choices
- ensure word conditions and image conditions both display timing choices consistently;
  the duty-cycle rendering path still applies to both modalities unless a later plan
  distinguishes word timing

Project step:

- relabel the image-timing selector as the default timing template for new conditions
- when existing conditions are present and the user changes the default, prompt with a
  clear apply-to-all vs future-only choice
- avoid hidden automatic standardization of existing conditions after this feature lands

Review/Home:

- show a concise mixed-timing summary when conditions do not all share the same template
- keep launch readiness based on existing validation and compiler checks

## Core And Runtime Plan

- validation should continue checking each condition's `duty_cycle_mode` against the
  template's supported modes and frame compatibility
- `compile_run_spec()` and `compile_session_plan()` should continue to derive
  `on_frames` and `off_frames` from each condition's resolved `duty_cycle_mode`
- runtime should need no new branching beyond the compiled `RunSpec` fields
- `.fpvsconfig` export/import should preserve per-condition timing fields and, if added,
  any optional condition-level profile provenance
- old projects without condition-level provenance should load unchanged because they
  already include resolved condition timing fields

## Migration And Compatibility

Existing projects should load without migration. Their condition timing fields already
represent the behavior that will launch.

For projects created before this feature:

- the project-level default should be inferred from `settings.condition_profile_id` or
  `settings.condition_defaults`
- each condition should be treated as having its own resolved timing choice based on
  `condition.duty_cycle_mode`
- if all conditions match the project default, the UI may present the project as uniform
- if conditions differ, the UI should present the project as mixed without rewriting any
  condition

## Risks

- The phrase "template" currently covers more than duty-cycle mode in condition-template
  profiles. The first implementation must avoid accidentally making display or fixation
  settings per-condition.
- Existing "apply defaults to all conditions" behavior can become destructive once mixed
  timing is supported. The UX must make bulk application explicit.
- Validation messages should identify the specific condition whose timing is incompatible
  with the selected refresh rate.
- Tests should guard against silent regression to global standardization.

## Verification

Unit tests:

- applying a timing template to one condition changes only that condition
- changing the project default can preserve existing conditions
- changing the project default can explicitly apply to all conditions
- compiler produces continuous frames for one condition and 50% blank frames for another
  in the same session
- project config export/import preserves mixed condition timing

GUI tests:

- Conditions setup displays per-condition timing selectors
- selecting a condition shows its current timing mode
- changing one condition leaves sibling conditions unchanged
- Project default change prompts or otherwise requires an explicit apply-to-all choice
- Review/Home summarizes mixed timing without clipping in the compact `1120x720` window

Runtime/preflight tests:

- mixed continuous and blank conditions launch through the same session plan path
- unsupported refresh/frame combinations point to the affected condition

Docs:

- update `ARCHITECTURE.md`, `docs/GUI_WORKFLOW.md`, `docs/RUNSPEC.md`, and
  `docs/SESSION_PLAN.md` when implementation begins
- update this plan while active if the chosen persistence shape differs from the
  recommended direction above

## Open Questions

- Should custom user-created condition-template profiles be selectable per condition in
  the first implementation, or should the first UI expose only the two built-in timing
  modes?
- Should Target Stimulus Repeats become per-condition in the same feature, or remain a
  project default with a separate future plan?
- Is a condition-level `condition_profile_id` worth persisting for provenance, or is
  resolved `duty_cycle_mode` sufficient for launch and audit needs?
