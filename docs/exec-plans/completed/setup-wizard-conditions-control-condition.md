# Setup Wizard Conditions Control Condition

## Summary

Rework setup so selecting image folders is treated as part of condition creation rather
than as a separate guided Stimuli step. Most users arrive with source image folders
already prepared and only need to define conditions, assign base/oddball folders, and
complete display/session/fixation settings. Derived image variants remain useful for
control conditions, but they should be optional and lower in the visual hierarchy.

This implementation removes the guided Stimuli/Assets Readiness step from the setup
wizard and adds an optional `Create Control Condition...` workflow inside Conditions.
Control conditions reuse the selected condition's existing base and oddball stimulus
sets and differ by `Condition.stimulus_variant`, so no project schema, compiler,
runtime, or generated-folder import workflow is introduced.

## User Problem And Workflow Intent

The current wizard asks users to visit a Stimuli step before Conditions even though the
actual required image selection happens when defining condition base and oddball image
folders. This makes the setup flow feel like users must manage assets before they know
which condition those assets belong to.

The intended workflow is:

1. Create or open a project.
2. Enter project details.
3. Create each condition.
4. For each condition, choose base and oddball image folders.
5. Optionally create a control condition from an already configured condition.
6. Finish display, session, fixation, and review.

The optional control-condition workflow is for users who want a condition using the same
stimulus set with a derived variant such as grayscale, 180 degree rotation, or
phase-scrambled images. It should be discoverable but not prominent.

## Current-State Findings

- `SetupWizardPage` currently uses a seven-step `_WIZARD_STEPS` sequence with `Stimuli`
  before `Conditions`.
- The guided Stimuli step is `AssetsReadinessEditor`; it is non-blocking and mostly
  exposes variant/materialization status.
- The actual required image selection already lives in `ConditionSetupStep` and
  `ConditionsPage` through base/oddball folder import buttons.
- `Condition.stimulus_variant` already exists and compiler asset resolution already uses
  it to select original or generated variant paths.
- `DocumentStimulusMixin.materialize_assets()` already materializes project-supported
  variants using preprocessing and updates the manifest/project stimulus sets.
- `duplicate_condition()` currently creates empty base/oddball stimulus sets; that is
  correct for normal duplication but not for a control condition that should reuse source
  stimuli.

## Target Wizard Flow

The guided setup wizard should have six steps:

1. Project Details
2. Conditions
3. Display Settings
4. Session Design
5. Fixation Cross
6. Review

Implementation details:

- Remove `Stimuli` from `_WIZARD_STEPS`.
- Remove `AssetsReadinessEditor` from the guided `step_stack`.
- Remove Stimuli-specific valid/status/blocker branches because there is no guided
  Stimuli step.
- Remove `stimuli` from the advanced button mapping.
- Keep `AssetsPage` available as an internal support surface only if existing code still
  needs it; do not expose it as a guided wizard step.
- Update docs and tests from seven steps to six.

## Optional Control-Condition UX

Add a low-priority action to the guided Conditions step:

- Label: `Create Control Condition...`
- Placement: near existing condition list utilities, styled as a secondary action.
- Enabled only when the selected condition has imported base and oddball image folders.
- Disabled when no condition is selected or either stimulus role has zero images.

Clicking the action opens a themed dialog that uses the existing component layer and
PySide6 only. The dialog:

- Shows the selected source condition name.
- Provides a variant selector with:
  - `Grayscale`
  - `180 degree rotated`
  - `Phase-scrambled`
- Provides an editable new condition name with a variant-specific default:
  - `{Source Name} Grayscale Control`
  - `{Source Name} 180 Degree Rotated Control`
  - `{Source Name} Phase-Scrambled Control`
- Uses standard OK/Cancel dialog behavior.

After creation:

- The new condition is selected in the guided Conditions list.
- If the chosen variant is missing for either reused stimulus set, the GUI runs existing
  materialization through the current `ProgressTask` pattern.
- Any materialization error is surfaced with the existing error dialog pattern.

## Document-Layer Behavior

Add a `ProjectDocument` method through `DocumentConditionMixin`:

```python
create_control_condition(
    source_condition_id: str,
    *,
    variant: StimulusVariant,
    name: str | None = None,
) -> str
```

Behavior:

- Validate that the source condition exists.
- Reject `StimulusVariant.ORIGINAL`.
- Copy the source condition metadata, including timing, instructions, duty cycle, and
  other condition settings.
- Reuse `base_stimulus_set_id` and `oddball_stimulus_set_id` from the source condition.
- Set `stimulus_variant` to the selected derived variant.
- Assign a unique condition id.
- Assign a unique display name based on the provided name or the default variant label.
- Assign the next trigger code and final order index.
- Reindex conditions through existing helper behavior.

Non-goals:

- Do not add new fields to `ProjectFile`, `Condition`, or `StimulusSet`.
- Do not create separate generated folders as new imported stimulus sets.
- Do not alter compiler/runtime/session contracts.

## Preprocessing And Materialization Boundary

Control-condition creation remains a project-model edit. Variant file generation remains
owned by preprocessing.

Materialization rules:

- The GUI checks whether the selected variant is present in both reused stimulus sets'
  `available_variants`.
- If either role is missing the variant, call `ProjectDocument.materialize_assets()`
  through `ProgressTask`.
- Ensure the selected variant is included in project supported variants before
  materialization, preserving `original`.
- Do not block the UI thread.
- Do not let worker code touch widgets directly.

## GUI Component Requirements

- Use `fpvs_studio.gui.components` helpers for button roles and dialog/card styling where
  existing helpers apply.
- Keep the control action visually secondary.
- Do not introduce custom stylesheets for shared concepts.
- Do not add top-level tabs.
- Do not import PsychoPy.
- Keep Conditions as the primary setup area for image folder selection.

## Tests And Verification

Add or update tests for:

- Setup wizard has six steps and Conditions follows Project Details.
- No guided Stimuli step appears in wizard progress/list state.
- Control-condition action is disabled until the selected condition has imported base and
  oddball images.
- Creating control conditions for grayscale, 180 degree rotated, and phase-scrambled
  variants:
  - creates a new condition
  - reuses source base/oddball stimulus set ids
  - sets the selected `stimulus_variant`
  - assigns a new trigger code and order index
  - selects the new condition in the GUI
- Missing selected variants trigger the existing materialization path without blocking the
  UI thread.
- Existing condition creation, duplication, image import, and launch readiness tests still
  pass.

Verification commands:

```powershell
python -m pytest -q tests\gui\test_layout_dashboard.py tests\gui\test_conditions_session_fixation.py
python -m pytest -q tests\unit\test_project_service.py tests\unit\test_compiler.py tests\unit\test_preprocessing_assets.py
python -m pytest -q tests\unit\test_harness_docs.py
python -m ruff check src\fpvs_studio\gui src\fpvs_studio\core tests
.\scripts\check_gui.ps1
```

## Manual Alignment Checklist

Before moving this plan to completed, manually confirm:

- Wizard step count is six.
- Conditions is the second guided step.
- Image folder selection remains inside Conditions.
- Control-condition creation is optional and visually secondary.
- Control conditions reuse stimulus sets and differ by `stimulus_variant`.
- The implementation does not add schema, compiler, runtime, or PsychoPy changes.

## Completion

When implementation and verification pass, move this file to:

`docs/exec-plans/completed/setup-wizard-conditions-control-condition.md`
