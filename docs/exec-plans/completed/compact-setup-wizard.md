# Compact Setup Wizard

Status: Completed

Completed: 2026-05-08

## Summary

Make Setup use a compact, stable window closer to Welcome/Home by splitting the
overloaded Conditions and Fixation Cross pages instead of squeezing dense pages
into the current five-step layout.

## Key Changes

- Change Setup to a compact window policy:
  - default `1040x680`
  - minimum `960x640`
  - keep Image Resizer on the larger workspace policy
- Replace the current five setup steps with seven short-label steps:
  - `Project`
  - `Conditions`
  - `Images`
  - `Experiment`
  - `Fixation`
  - `Response`
  - `Review`
- Split Conditions:
  - `Conditions`: condition list/actions, name, trigger, instructions
  - `Images`: condition selector, base/oddball image cards, protocol metrics, image readiness
  - image normalization runs when leaving `Images`
- Split Fixation Cross:
  - `Fixation`: enablement, schedule, target count, timing
  - `Response`: accuracy tracking, response key/window, appearance, compact preview
- Update GUI docs and architecture notes for the seven-step compact wizard.

## Verification Plan

- Run focused GUI tests:
  - `python -m pytest -q tests\gui\test_layout_dashboard.py tests\gui\test_conditions_session_fixation.py`
- Run docs harness:
  - `python -m pytest -q tests\unit\test_harness_docs.py`
- Run Ruff on touched Python files.
- Run GUI gate:
  - `.\scripts\check_gui.ps1`

## Verification Results

- `.venv3.10\Scripts\python -m pytest -q tests\gui\test_layout_dashboard.py tests\gui\test_conditions_session_fixation.py`
  - Passed: `76 passed`
- `.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py`
  - Passed: `4 passed`
- `.venv3.10\Scripts\python -m ruff check` on touched GUI/test files
  - Passed
- `.\scripts\check_gui.ps1`
  - Passed: `139 passed`

## Manual Confirmation

- Confirmed Setup uses a compact `1040x680` default and `960x640` minimum, while
  Image Resizer keeps the larger workspace policy.
- Confirmed the wizard exposes seven steps: Project, Conditions, Images, Experiment,
  Fixation, Response, and Review.
- Confirmed Conditions validates condition names/triggers before Images.
- Confirmed Images validates base/oddball folders and still runs normalization before
  advancing.
- Confirmed Home -> Setup -> Home size restoration remains covered by focused GUI tests.
