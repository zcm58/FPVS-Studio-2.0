# Home-First Launch Workflow GUI Rework

Status: Active

## Summary

Keep the first tab named `Home`, but reshape it around the returning-user workflow:
open FPVS Studio, select an existing/recent project, and launch the experiment in one
or two clicks. First-time setup becomes a guided workflow, while detailed editors
remain available for deeper changes.

## Key Changes

- Add recent-project support through the GUI/controller layer.
  - Store recently opened/created project roots in `QSettings`.
  - Show recent valid projects on the welcome screen.
  - Cap recent projects at 8, most recent first.
  - Ignore missing/stale project folders when rendering.
- Keep the first main tab named `Home`.
  - Make `Home` the launch-first hub.
  - Primary action remains `Launch Experiment`.
  - Secondary actions: `Open Project`, `Create New Project`, `Save`, `Edit Setup`,
    `Stimuli Manager`, and `Runtime Settings`.
  - Preserve the participant-number prompt before launch.
- Convert `Setup Dashboard` into a guided setup surface.
  - Rename the tab to `Setup Guide`.
  - Show ordered setup steps: Project Details, Conditions, Stimuli,
    Session/Fixation, Runtime, Validate/Ready.
  - Each step shows status, summary, and an action button that navigates to the
    existing detailed editor/page.
  - Do not duplicate project state or validation logic in the guide.
- Keep existing focused pages.
  - `Conditions`, `Stimuli Manager`, and `Runtime` remain available.
  - No changes to project JSON schema, compiler contracts, runtime launch contracts,
    PsychoPy engine behavior, or exports.

## Public Interfaces

- Add GUI/controller helpers for loading, recording, pruning, and opening recent
  project roots.
- Add stable object names:
  - `welcome_recent_projects_panel`
  - `welcome_recent_project_list`
  - `home_launch_experiment_button`
  - `home_edit_setup_button`
  - `setup_guide_step_list`
  - `setup_guide_ready_badge`

## Test Plan

- Recent projects:
  - creating/opening a project records it as recent
  - welcome screen renders recent valid projects
  - clicking a recent project opens it
  - stale project folders are omitted
- Home launch workflow:
  - first tab label remains `Home`
  - `Home` exposes primary `Launch Experiment`
  - launch still prompts for participant number
  - secondary actions navigate to setup, stimuli, runtime, open, create, and save flows
- Setup guide:
  - `Setup Guide` replaces `Setup Dashboard`
  - setup steps reflect current project readiness
  - step action buttons navigate to existing editors/pages
  - existing detailed editing flows remain functional
- Verification:
  - `.\scripts\check_gui.ps1`
  - `.\scripts\check_quality.ps1`

## Assumptions

- Returning users should usually use `Home` as the launch hub.
- The first tab stays named `Home`, not `Launch`.
- Participant number remains required before experiment launch.
- Guided setup uses existing editors and document services rather than introducing a
  second project-state path.
