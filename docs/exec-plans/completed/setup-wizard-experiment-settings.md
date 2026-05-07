# Combine Setup Wizard Experiment Settings

## Summary

Merge the separate guided `Display Settings`, `Session Design`, and `Fixation Cross`
steps into one guided `Experiment Settings` step. The new step uses a three-column
layout that matches the existing FPVS Studio PySide6 component layer and keeps the
same project model fields, validation rules, runtime contracts, and persisted
project schema.

## User Problem

The current setup wizard spends three full guided steps on settings that are small
and usually quick to review:

- display refresh rate and background color
- session block count, seed, randomization, and Space start behavior
- fixation task enablement and response/appearance settings

This creates sparse pages, unnecessary navigation, and poor use of the available
window width. Users should be able to review and adjust these experiment-level
settings on one page after condition setup and before review.

## Current State Findings

- `src/fpvs_studio/gui/setup_wizard_page.py` defines six guided steps:
  `Project Details`, `Conditions`, `Display Settings`, `Session Design`,
  `Fixation Cross`, and `Review`.
- `DisplaySettingsEditor` already exposes only refresh rate and background color.
- `SessionStructureEditor` already exposes the current supported session controls.
- `FixationSettingsEditor` owns the model-bound fixation controls and already keeps
  compilation/runtime logic outside the GUI.
- Session and fixation currently have advanced guided-step access because their
  guided pages are summaries, not the actual controls.

## Target Wizard Flow

The guided wizard becomes four steps:

1. `Project Details`
2. `Conditions`
3. `Experiment Settings`
4. `Review`

The `Experiment Settings` page contains three equal-width columns:

- `Display`
  - `Refresh (Hz)`
  - `Background`
  - short helper text that the values are used during image presentation
- `Session`
  - `Block count`
  - `Session seed`
  - `Generate New Seed`
  - `Randomize conditions within each block`
  - disabled `Start key` set to `space`
- `Fixation Cross Settings`
  - existing fixation enablement and accuracy controls
  - existing behavior/timing/response/appearance fields, arranged compactly for a
    single column where practical
  - existing feasibility guidance

## GUI Boundary

- Reuse the existing component layer from `fpvs_studio.gui.components`.
- Do not introduce new top-level tabs or modal workflows.
- Keep the page inside the current Setup Wizard shell and step card.
- Preserve existing object names where tests and downstream code already rely on
  them.
- Keep detailed Conditions advanced access because Conditions still has a dense
  advanced editor.
- Remove guided advanced access for the old Session/Fixation steps because those
  controls are now directly available on `Experiment Settings`.

## Backend And Contract Boundary

- Do not change project schema, compiler contracts, runtime contracts, PsychoPy
  boundaries, session-plan behavior, fixation scoring, or preprocessing.
- Keep model field updates routed through `ProjectDocument`.
- Keep display background normalization and refresh validation unchanged.
- Keep session start behavior fixed to Space as implemented today.

## Tests

Update focused GUI tests to verify:

- the setup wizard has four guided steps
- `Experiment Settings` follows `Conditions`
- old guided `Display Settings`, `Session Design`, and `Fixation Cross` steps are
  absent from the progress stepper and hidden step list
- the experiment page exposes display, session, and fixation controls in one page
- the Experiment Settings step has no advanced replacement view
- refresh/background, session, and fixation edits still use the existing bound
  widgets and stay available to tests
- the Conditions image-normalization gate advances to Experiment Settings

Run:

- headless `tests\gui\test_layout_dashboard.py`
- `tests\gui\test_conditions_session_fixation.py`
- `python -m pytest -q tests\unit\test_harness_docs.py`
- `python -m ruff check src\fpvs_studio\gui tests`

## Documentation

Update:

- `ARCHITECTURE.md`
- `docs/GUI_WORKFLOW.md`
- `docs/FRONTEND.md` if needed for the guided workflow summary

## Non-Goals

- No project-schema migration.
- No runtime, compiler, preprocessing, or PsychoPy changes.
- No new settings or configurability.
- No visual redesign outside the guided setup wizard experiment-settings surface.

## Assumptions

- The user-approved mockup means a single guided page with three columns and a
  four-step wizard.
- The existing session/fixation editor widgets remain the source of truth for
  model-bound controls.
- Advanced Conditions remains useful; advanced Session/Fixation is no longer needed
  in the guided wizard once the controls are directly visible.
