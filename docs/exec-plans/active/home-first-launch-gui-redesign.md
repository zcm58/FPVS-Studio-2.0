# Home-Only Launch Surface With Guided Setup Wizard

Status: Active

## Summary

FPVS Studio now treats `Home` as the daily-use launch surface. Ready projects open to
Home for routine participant sessions. New or incomplete projects open to an in-window
Setup Wizard that guides the user through setup and keeps detailed editors available
only through step-level advanced access.

## Key Changes

- Replace visible top-level setup tabs with a main-window stack:
  - `Home` for launch-ready projects.
  - `Setup Wizard` for new/incomplete projects and `Edit Setup`.
  - No visible top-level tabs for Conditions, Stimuli Manager, or Runtime.
- Use computed readiness only:
  - No persisted approval flag in this pass.
  - Existing validation/readiness logic decides whether a project is ready.
- Add a fixed setup wizard sequence:
  - Project Details
  - Conditions
  - Stimuli
  - Display / Runtime
  - Session / Fixation
  - Review / Ready
- Keep detailed editors internal:
  - Conditions, Stimuli Manager, and Runtime remain instantiated for existing
    document bindings and advanced setup access.
  - Home no longer exposes direct Stimuli Manager or Runtime Settings buttons.
- Preserve backend contracts:
  - No project JSON schema changes.
  - No compiler, runtime, PsychoPy engine, preprocessing, or export contract changes.

## Public Interfaces

- Stable wizard object names:
  - `setup_wizard_page`
  - `setup_wizard_step_list`
  - `setup_wizard_back_button`
  - `setup_wizard_next_button`
  - `setup_wizard_return_home_button`
  - `setup_wizard_advanced_button`
  - `setup_wizard_ready_badge`
- Existing editor/page attributes remain available on `StudioMainWindow` for internal
  bindings and tests, but they are not visible top-level navigation.

## Test Plan

- Navigation:
  - incomplete projects open to Setup Wizard
  - ready projects open to Home
  - `Edit Setup` opens Setup Wizard
  - detailed pages are not in the main workflow stack
- Wizard:
  - step order is stable
  - `Next` is disabled until the current step is complete
  - adding a condition enables the Conditions step
  - `Advanced` exposes the existing detailed editor for the active step
  - `Return Home` switches back to Home without launching
- Launch:
  - Home still exposes `Launch Experiment`
  - launch still prompts for participant number
  - readiness uses existing validation/runtime checks
- Verification:
  - `.\scripts\check_gui.ps1`
  - `.\scripts\check_quality.ps1`

## Assumptions

- Returning users spend most of their time launching an already configured project.
- Setup/editing is intentional and wizard-driven.
- Manual project approval can be added later as a separate product decision.
