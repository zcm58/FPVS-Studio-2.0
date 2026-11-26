# Retire Condition Templates from Setup

Status: Completed

Date: 2026-11-26

## Outcome

Setup still starts at **1. Project**. Remove its **Experiment Template** row,
**Apply Template To All Conditions** action, and template manager entry. Users create a
project by selecting its experiment category and entering its details, then
author conditions and timing through the existing Setup steps.

Retire the same feature from **Create Project** and **Settings → Workspace** so
users can complete the workflow without choosing or managing a condition
template. Whole-project Library and bundle workflows are outside this removal.

## Implementation

1. In `gui/project_overview_page.py`, remove template selection, management and
   bulk application. Remove the associated state, refresh logic and layout
   sizing code. Keep project metadata and the remaining experiment controls
   in their current sections. Reconnect keyboard tab order and retain all Setup
   steps, validation and navigation.
2. In `gui/create_project_dialog.py` and `gui/controller.py`, remove the
   template chooser, required-selection validation and profile lookup from
   project creation. Use the existing category-based starter path. Before
   changing the call, compare each category's current default selection with
   the no-profile path in `core/project_service.py`. Where they differ,
   preserve the current default explicitly, including Attentional Blink's
   letter-stream starter, the initial condition rows and ordinary Oddball
   timing. Keep the existing validation for name, destination and category.
3. Remove the manager action from `gui/settings_dialog.py` and its supporting
   copy from root-folder setup. Trace callers through the controller,
   `main_window.py`, `home_page.py` and `setup_wizard_page.py` before
   removing obsolete callbacks and template-list caching. Remove the manager
   and profile editor, along with their private helpers and styles, after
   confirming they have no surviving users. Keep shared condition editors and
   any built-in profile data or application logic needed for starter defaults.
4. Preserve existing project settings, including saved profile provenance and
   timing overrides. Opening, editing and saving an older project must work
   even without its original template library. Leave template library files
   on disk and preserve project and bundle schemas. Trace template library
   initialization and normalization before removing any call. Keep any
   compatibility paths with surviving callers.
5. Update [GUI Workflow](../../GUI_WORKFLOW.md) and the
   [GUI package guide](../../../src/fpvs_studio/gui/AGENTS.md) where they
   describe the retired controls or tests. Review current onboarding and
   support copy for references to template selection or management.

## Verification

- Update registered Qt smoke cases for Project overview, Create Project,
  Workspace settings and Setup navigation. Remove tests dedicated to the
  retired dialogs, preserving coverage of shared Attentional Blink editors
  through their surviving entry points.
- Compare default starter settings and initial conditions for FPVS Oddball
  and Attentional Blink with the baseline. Exercise manual condition creation,
  editing and save/reopen. Open a saved project with a custom profile ID and
  per-condition timing overrides while its source library is unavailable.
  Round-trip it through save and bundle reopen, and compare compiled plans
  with the same inputs and seeds for exact schedule, randomization and
  fixation-event parity. Confirm that existing template library files are
  neither deleted nor rewritten by the removal.
- Run focused source and docs checks, then the repository precommit tier for
  the shared creation and Setup changes. Record source and visible results
  separately.
- In an approved visible Windows session, create an FPVS-Oddball project,
  then open a saved Attentional-Blink project. For both,
  traverse Project to Conditions and back by keyboard, edit a condition,
  then save and reopen. Check Project, Create Project and Workspace at
  minimum and default window sizes for clipping, empty layout gaps and focus
  order. Confirm that the former template commands are absent and manual
  authoring remains reachable.

The New Project dialog offers FPVS-Oddball and shows Standard FPVS as coming
soon. Attentional Blink and Cognitive Load continue to open from their saved
projects. Their programmatic desktop starter paths retain their category defaults.

## Verification on November 26, 2026

- The affected non-Qt project and compiler selection passed 239 tests. Desktop
  starter parity covers FPVS-Oddball, Attentional Blink and Cognitive Load.
  The profiled bundle round trip produced identical compiled session JSON with
  fixed seeds and preserved the condition timing override and fixation events.
- Focused GUI source verification passed 197 tests and the docs check passed
  13 tests. Verification configuration accepted the updated Qt registry.
- The approved visible Windows selection passed 55 cases across the Setup,
  Create Project, category and Welcome workflows. A direct Workspace check
  confirmed the remaining controls fit at 860 × 560 and 1000 × 680 in Light
  and Dark. The broader Qt selection reproduced 15 existing Settings footer
  and condition-test failures on the unchanged main branch. Four temporary
  Settings-access errors passed on an isolated rerun.
