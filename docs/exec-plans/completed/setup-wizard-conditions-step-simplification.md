# Setup Wizard Conditions Step Simplification

Status: Completed

Completed: 2026-05-06

## Summary

Refactor the Setup Wizard Conditions step so it behaves like a focused condition
setup workflow instead of a dense master-detail editor. Users should configure each
condition's name, trigger code, participant-facing instructions, and base/oddball
image folders in one place because these choices are conceptually linked. Dense FPVS
timing controls move out of the normal guided path.

## Key Changes

- Replace the current embedded full Conditions editor in the wizard step with a
  simplified condition setup surface:
  - condition name
  - trigger code
  - participant instructions
  - base image folder selection
  - oddball image folder selection
- Add condition management actions:
  - `Add Condition`
  - `Duplicate Condition`
  - `Remove Condition`
  - optional drag/drop ordering for user organization only
- Do not present `Move Up` / `Move Down` as primary actions because experiment display
  order is randomized and user-facing order is only organizational.
- Keep per-condition readiness visible with a compact checklist:
  - descriptive name entered
  - trigger code of 1 or higher assigned
  - base images selected
  - oddball images selected
- Move advanced timing and technical controls out of the guided Conditions step:
  - condition repeats
  - cycles per repeat
  - duty cycle
  - stimulus variant
  - template/timing info
- Keep stimulus variant decisions out of this pass. Treat that as a later setup-flow
  decision, likely separate from the Conditions step.
- Flatten the visual hierarchy:
  - avoid nested bordered cards inside the wizard frame
  - use one primary condition list/detail workspace
  - keep action buttons close to the condition list
- Simplify the wizard progress header:
  - keep `Step X of 7`
  - keep the active step name
  - make the progress indicator visually lighter and less dominant

## Boundaries

- No project JSON schema changes.
- No compiler, runtime, PsychoPy engine, preprocessing, export, or session-plan contract
  changes.
- Continue using `ProjectDocument` services for all condition and stimulus mutations.
- Preserve existing condition IDs, trigger code behavior, asset import behavior, and
  launch readiness logic.
- Existing dense condition editor behavior may remain available internally or through
  an `Advanced` entry point, but it should not be the default guided step UI.
- The existing `Stimuli` wizard step remains in the wizard for now. In this pass it
  should not duplicate base/oddball source selection already handled in Conditions;
  revisit its role later when stimulus variant/materialization UX is designed.

## Test Plan

- Conditions step:
  - renders condition name, trigger code, instructions, base folder, and oddball folder
    controls for the selected condition
  - does not show condition repeats, cycles per repeat, duty cycle, or stimulus variant
    in the guided Conditions step
  - supports adding, duplicating, and removing conditions
  - keeps optional drag/drop ordering from changing runtime randomization semantics
- Readiness:
  - `Next` remains disabled until all conditions have descriptive non-default names,
    trigger codes above 0, and both base and oddball folders assigned
  - per-condition checklist items update after editing names, changing trigger codes,
    and importing folders
  - existing launch readiness still uses current backend validation
- Regression:
  - existing condition editor remains available for advanced/internal access if kept
  - project save/reopen preserves all condition and stimulus-source choices
  - no runtime launch contract changes
- Verification:
  - focused pytest-qt tests for the simplified Conditions step
  - `python -m ruff check src tests`
  - `python -m pytest -q tests\unit\test_harness_docs.py`
  - `.\scripts\check_gui.ps1`
  - `.\scripts\check_quality.ps1`

## Assumptions

- Base and oddball image source selection belongs with the condition it defines.
- Display order during experiments remains randomized; any visible condition ordering is
  for author organization only.
- The guided wizard is stricter than the core project model: default `Condition N`
  names, names shorter than 3 characters, and trigger code `0` are incomplete setup.
- FPVS Studio defaults should carry technical timing choices for ordinary users.
- Stimulus variant UX needs a separate design decision and should not be folded into
  this refactor opportunistically.
