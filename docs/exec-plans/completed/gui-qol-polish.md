# GUI QOL Polish

Status: Completed

## Summary

Implement six small quality-of-life improvements across the GUI and harness. These
changes should make routine authoring, image preparation, launch review, and test
iteration easier without changing project schemas, compiler contracts, runtime
contracts, persisted formats, or update packaging behavior.

This is deliberately not a broad redesign. Each task should be implemented as a narrow
change with focused GUI coverage or harness verification.

## User Workflows

- After optimizing images, a user can open or copy the output folder without manually
  retyping the result path.
- After a launch completes or aborts, a user can open or copy the run output folder
  from the runtime feedback surface.
- When Home disables `Launch Experiment`, a user can hover or inspect the button to
  see the first actionable blocker.
- In Manage Projects, a user can filter a long project list and copy the selected
  project path.
- When Image Resizer cannot run, the page explains why the optimize action is disabled.
- During development, GUI and broad pytest runs fail boundedly instead of hanging
  indefinitely.

## Boundaries

- Keep GUI behavior thin and backend-driven.
- Do not change `ProjectFile`, `RunSpec`, `SessionPlan`, execution export models, or
  persisted project JSON.
- Do not add new runtime launch options or expose hidden display/fullscreen/serial
  controls.
- Do not implement the planned patch update workflow here. That remains separate in
  `docs/exec-plans/planned/patch-update-workflow.md`.
- Prefer existing shared GUI components and button role helpers from
  `src/fpvs_studio/gui/components.py`.
- Keep any OS folder opening behind a small GUI helper or local page helper that can be
  tested without launching external applications.
- For file/folder copy actions, use Qt clipboard APIs so tests can assert clipboard
  contents headlessly.

## Implementation Steps

### 1. Image Resizer Output Actions

Add actions after successful image optimization:

- `Open Output Folder`
- `Copy Output Folder`

Suggested files:

- `src/fpvs_studio/gui/image_resizer_page.py`
- `tests/gui/test_layout_dashboard.py` or a new focused image-resizer GUI test

Implementation notes:

- Keep the actions disabled or hidden until a successful result provides an output
  directory.
- Reuse the already-known `ImageFolderOptimizationResult.output_dir`; do not re-scan
  output files.
- If opening a folder needs platform integration, isolate it so tests can monkeypatch
  the call instead of opening Explorer.
- Keep the existing result text, but make the path actionable.

Verification:

- Test that actions start disabled/hidden.
- Test that success enables or shows both actions.
- Test that copy writes the exact output directory path to the clipboard.
- Test that open emits or calls the isolated folder-opening seam with the output path.

### 2. Run Output Actions

Add actions to the run/runtime feedback area after launch completion or abort:

- `Open Run Folder`
- `Copy Run Folder`

Suggested files:

- `src/fpvs_studio/gui/run_page.py`
- `tests/gui/test_assets_run_launch.py`
- `tests/gui/test_layout_dashboard.py` if layout assertions need updating

Implementation notes:

- Use `LaunchSummary.output_dir` when available.
- Keep actions unavailable before a launch result exists.
- Do not change launch flow, participant prompts, duplicate participant handling, or
  runtime execution.
- The actions should work for both completed and aborted launches when `output_dir` is
  present.

Verification:

- Extend existing launch success and abort tests to assert the path actions become
  available.
- Assert copying writes the launch output directory to the clipboard.
- Assert the open-folder seam receives the launch output directory.

### 3. Disabled Home Launch Reason

When Home disables `Launch Experiment`, surface the first actionable blocker through
tooltip and status tip text.

Suggested files:

- `src/fpvs_studio/gui/home_page.py`
- `tests/gui/test_layout_dashboard.py`

Implementation notes:

- Use the existing `LauncherReadinessReport.status_summary` or first relevant
  readiness item.
- When the project is ready, restore the normal launch tooltip/status tip from the
  bound action.
- Do not add visible Home copy for ready projects. The current Home surface keeps the
  ready summary hidden.

Verification:

- Extend the incomplete Home launch-state test to assert the disabled button tooltip
  names the blocker.
- Extend the ready Home launch test to assert the launch button is enabled and does
  not keep a stale blocker tooltip.

### 4. Manage Projects Filter And Copy Path

Add project-list filtering and a selected-path copy action.

Suggested files:

- `src/fpvs_studio/gui/manage_projects_dialog.py`
- `tests/gui/test_welcome_settings_flow.py`

Implementation notes:

- Add a compact filter field above the project list.
- Filter by project name and root path.
- Keep the original entries list as the source of truth; filtering should not mutate
  controller-owned project discovery.
- Preserve disabled open/delete behavior for entries that cannot be opened or deleted.
- Add `Copy Path` for the selected project, enabled only when a project is selected.

Verification:

- Test filtering by project name.
- Test filtering by a path substring.
- Test clearing the filter restores all entries.
- Test copy writes the selected root path to the clipboard.
- Test open/delete enablement still follows the selected filtered entry.

### 5. Image Resizer Disabled Reason

Explain why `Optimize Images for FPVS` is unavailable.

Suggested files:

- `src/fpvs_studio/gui/image_resizer_page.py`
- `tests/gui/test_layout_dashboard.py`

Implementation notes:

- Reuse the existing status badge and result label instead of adding another visible
  instruction block.
- Suggested reasons:
  - source folder is not selected
  - output folder is not selected
  - source folder no longer exists
  - source folder is not a folder
  - output folder must be different from the source folder
- Do not add fallback behavior that guesses a new output folder after the user has
  explicitly selected one.

Verification:

- Test the initial disabled state explains that source/output folders are needed.
- Test the identical source/output case explains the path conflict.
- Test the success path still shows the optimization result instead of a stale disabled
  reason.

### 6. Bounded Pytest Timeout Harness

Make common pytest runs fail boundedly instead of hanging indefinitely.

Suggested files:

- `pyproject.toml`
- `docs/GUI_WORKFLOW.md`
- `docs/QUALITY_SCORE.md` or `docs/TECH_DEBT.md` if the documented gate changes
- `tests/unit/test_harness_docs.py`

Implementation notes:

- The repo already depends on `pytest-timeout`; prefer a simple config-level timeout
  unless an existing gate script is the better local convention.
- Keep the timeout generous enough for GUI tests and Windows CI variability.
- If a global timeout is too risky for the broad suite, make the GUI gate enforce
  `--timeout` consistently and document that decision.
- Use the repo interpreter documented in memory and GUI guidance when verifying locally:
  `.\.venv3.10\Scripts\python`.

Verification:

- Run `.\.venv3.10\Scripts\python -m pytest --collect-only -q`.
- Run a focused GUI test with the intended timeout behavior.
- Run `python -m pytest -q tests\unit\test_harness_docs.py` after docs changes.
- Run `.\scripts\check_gui.ps1` if GUI test command docs or gate scripts change.

## Suggested Order

1. Implement the two Image Resizer tasks together because they touch the same page and
   tests.
2. Implement Run output actions.
3. Implement the Home disabled launch reason.
4. Implement Manage Projects filtering and copy path.
5. Implement the pytest timeout harness change.

This order keeps related GUI edits together while leaving the harness change isolated.

## Completion Criteria

- All six tasks above are implemented.
- Relevant GUI smoke tests cover each visible behavior.
- Harness docs and plan inventory remain current.
- `python -m pytest -q tests\unit\test_harness_docs.py` passes after documentation
  updates.
- Focused GUI tests for touched surfaces pass.
- Any skipped or failing check is documented with the exact command and reason in the
  implementation handoff.

## Completion Notes

- Image Resizer now explains unavailable optimization states, and successful results
  expose output-folder open/copy actions.
- Run / Runtime feedback now exposes run-folder open/copy actions after completed or
  aborted launches when the launch summary includes an output directory.
- Home disabled launch buttons surface the first actionable blocker through tooltip and
  status tip text, and ready projects restore the normal launch tooltip.
- Manage Projects now filters by project name or root path and can copy the selected
  project path.
- Common pytest runs are bounded by the repo-level `pytest-timeout` configuration in
  `pyproject.toml`.
