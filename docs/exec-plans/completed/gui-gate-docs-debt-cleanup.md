# GUI Gate And Documentation Debt Cleanup

## Summary

Restore the GUI gate as a useful signal and bring debt/workflow docs back in line with
the current Home/Setup Wizard workflow. This cleanup updated stale tests and docs only;
it did not reintroduce hidden serial/display controls or change project/runtime
contracts.

## Completed Changes

- Updated stale GUI tests to assert current behavior:
  - mixed-resolution raw import succeeds without a modal validation error;
  - launch settings carry backend serial settings;
  - launch uses the default display (`display_index=None`) and fixed fullscreen mode.
- Updated `docs/GUI_WORKFLOW.md` and `docs/FRONTEND.md` to describe current raw import,
  normalization, hidden serial/display controls, and shared Welcome/Home launch surface.
- Updated `docs/TECH_DEBT.md` and `docs/exec-plans/tech-debt-tracker.md` so gate status
  and active debt candidates reflect the current repository state.

## Verification

- `python -m pytest -q tests\gui\test_assets_run_launch.py`: 12 passed.
- `python -m pytest -q tests\unit\test_harness_docs.py`: 4 passed.
- Ruff on touched Python tests: passed.
- `git diff --check`: passed with CRLF warnings only.
- `.\scripts\check_gui.ps1`: 135 passed.

## Manual Confirmation

Confirmed before moving this plan to completed:

- The stale GUI-gate failures were removed.
- Documentation describes the implemented GUI behavior instead of older serial/display
  controls or strict raw import blocking.
- No public schema, project JSON, `RunSpec`, `SessionPlan`, or runtime export format
  changes were made.
