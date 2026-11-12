# Experiment monitor selection

Status: Completed

## Workflow and acceptance

At each Windows experiment launch, discover the connected desktop monitors in a
worker. With multiple monitors, offer a concise selector with the Windows primary
monitor selected. Continue uses that monitor for refresh advice, native preflight,
the PsychoPy probe and fullscreen playback; Cancel ends launch before participant
entry. A single monitor requires no selection prompt. Selection is per launch and
does not change Windows settings or portable project data. Home, Run and interrupted
condition re-runs share the selection flow. Explicit Check refresh rate also allows
checking the intended monitor without changing the default for later launches.

The operator's primary action is Continue. Reuse shared dialog styling, with monitor
identity, pixel dimensions and a primary marker in the selector. Minimum size is
520 × 220; default is 560 × 240. Registered Qt tests cover both sizes, primary and
alternate selection, cancellation, one-monitor bypass, detection errors and duplicate
requests. Required labels and buttons must fit without truncation.

## Boundaries and implementation

- Runtime enumerates Windows monitors and queries the selected native mode.
- LaunchSettings carries transient Windows device identity, outside compiled contracts.
- Engines map the selected identity to Pyglet's screen ordering immediately before
  window creation; missing or ambiguous selections fail explicitly.
- GUI workers discover monitors; GUI callbacks own choices and participant flow.
- Preserve existing refresh recommendation changes and macOS primary-only source policy.

## Verification

Run native and fake-engine unit regressions, focused GUI/runtime/engine verification,
then repository precommit. Do not execute Qt locally without explicit approval.
Visible smoke: launch with one monitor (no selector), attach a second (primary
preselected), choose each monitor and confirm fullscreen placement, cancel and retry,
change the Windows primary monitor and repeat. Check refresh rate on the alternate
monitor and test disconnection before launch. Physical display acceptance is separate
from fake-adapter checks.

## Implementation record

The selector now uses Windows device names instead of assuming Qt, Windows and
Pyglet screen lists have matching indices. Both probe and playback explicitly use
Pyglet and resolve the current index from that identity. Existing numeric launch
indices are pinned once before preflight. The default engine path explicitly resolves
the Windows primary monitor. Cancellation and concurrent display/preflight requests
are guarded before participant entry; no choice is persisted.

Production files changed:

- `src/fpvs_studio/gui/monitor_selection_dialog.py`
- `src/fpvs_studio/gui/main_window.py`
- `src/fpvs_studio/gui/run_page.py`
- `src/fpvs_studio/gui/runtime_settings_page.py`
- `src/fpvs_studio/gui/refresh_recommendation_dialog.py`
- `src/fpvs_studio/gui/document_runtime.py`
- `src/fpvs_studio/runtime/windows_display.py`
- `src/fpvs_studio/runtime/display_mode.py`
- `src/fpvs_studio/runtime/display_refresh.py`
- `src/fpvs_studio/runtime/launcher.py`
- `src/fpvs_studio/engines/psychopy_window.py`
- `src/fpvs_studio/engines/psychopy_metadata.py`

Coverage files changed:

- `tests/gui/test_monitor_selection_dialog.py`
- `tests/gui/test_monitor_launch_integration.py`
- `tests/gui/test_refresh_recommendation_dialog.py`
- `tests/gui/test_condition_recovery_dialog.py`
- `tests/gui/conftest.py`
- `tests/qt_test_files.txt`
- `tests/unit/test_windows_monitor_selection.py`
- `tests/unit/test_document_display_selection.py`
- `tests/unit/test_psychopy_engine.py`

Canonical documentation updated: `ARCHITECTURE.md`, `docs/agent/agent-index.md`,
`docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, `docs/RUNTIME_EXECUTION.md`,
`docs/ENGINE_INTERFACE.md`, `docs/PLANS.md`, and this plan. The existing uncommitted
Windows refresh-recommendation work is preserved and integrated.

## Verification results

- GUI focused: 180 passed; engine focused: 629 passed.
- Runtime focused: 1,123 passed, four Windows symlink-permission skips.
- Docs focused: 13 passed plus documentation hygiene checks.
- Repository precommit with four workers: 6,155 passed, 34 platform/permission
  skips; changed-file Ruff/compilation, 287-source Windows mypy, nine-target Darwin
  mypy, repository audits and documentation checks passed.
- A read-only native query on this host detected one primary `DISPLAY1`, 1920 × 1080
  at fixed 60 Hz. No display setting was changed and no presentation window opened.
- Registered Qt coverage was not executed, following the repository's local Qt
  policy. The tests cover 520 × 220 and 560 × 240, long realistic display labels,
  changed primary monitor, cancellation, errors, retries, concurrent requests and
  Home/Run/recovery/probe routing. Native probes, runtime launches, participant
  dialogs and Windows Settings are faked in GUI coverage. Visible multi-monitor,
  fullscreen placement and DPI/layout acceptance remain unperformed; follow the
  manual smoke path above in an approved visible session.
- `git diff --check` passed. The verification harness cleans its task-owned temporary
  data; unrelated existing edits and retained user output were preserved.
