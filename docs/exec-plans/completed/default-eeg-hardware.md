# Computer default EEG hardware

Status: Completed

Date: 2026-10-26

## Authorized workflow

After choosing an FPVS Studio Root Folder, select the default EEG hardware from
the four supported choices. Save this computer's preference, offer changes under
Settings > Recording even without an open project, and let projects explicitly
override it or return to the computer default.

## Scope and precedence

- Use a new QSettings key, `recording/default_configuration`; obsolete global
  transport keys remain ignored. The app's existing local user-profile store owns
  this computer preference, independently of the root folder and project files.
- Explicit `ProjectSettings.recording` wins. An unset project selection inherits
  the current computer default dynamically, including after default changes.
- Opening, importing or inheriting does not rewrite a project or create an override.
  Resetting an override saves only its recording field, preserving other drafts.
- The first prompt chooses hardware only. Keep advanced device/port setup in the
  existing Recording Setup surface; do not guess Brain Products amplifier/rate.
- Runtime handoff snapshots must use the effective hardware without inserting a
  local preference into portable authoring exports. Test/Pilot stays no-output.
- Manual completed export reuses the retained recording snapshot, including compact
  sessions, so later default changes cannot relabel historical EEG. Acquisition-era
  evidence without a completed snapshot is an error; legacy plan-only export remains
  only for histories without acquisition artifacts.
- The broader named-profile/display-selection proposal remains planned.

## UI and recovery

The picker uses existing dialog components at 640x300, with the requested prompt,
an explicit unselected state, Continue and Exit. Root selection precedes hardware;
missing preferences on existing installations show this picker once. Cancel exits
without choosing hardware, retaining the root for the next launch. Invalid saved
preferences require a new choice; persistence failures retain the previous value.
Settings retains its existing size budgets, with computer and project controls
clearly separated in the Recording tab. No discovery or hardware I/O in this prompt.
Welcome exposes Settings directly; all five actions retain its 760x520 minimum and
1120x720 default sizes, with compact controls in its single-column layout.

## Verification

The [2.5.0 release record](../active/release-2.5.0.md) tracks subsequent approved
visible GUI checks and packaging. Results below describe implementation-time checks.

1. Verify root/picker ordering, persistence, invalid/cancel/save failure and all four
   devices with fake preferences and dialogs, including safe non-Qt control-flow tests.
2. Verify override precedence, live inheritance, reset preservation, imported files,
   Test/Pilot and effective runtime/Toolbox handoff with injected preferences.
3. Add registered Qt coverage for picker and Settings states/minimum geometry in both
   themes. Do not run Qt without an approved visible session.
4. Run GUI focused and targeted project-service checks, docs/harness checks and repo precommit. Preserve
   and report unrelated Windows lock intermittency from earlier verification.

## Progress

- Baseline includes the preceding uncommitted TriggerBox discovery/validation work.
- Implementation is complete in source, preserving the preceding TriggerBox work.
- GUI focused: 83 passed. Safe preference/project-service checks: 71 passed.
- Inherited hardware handoff checks: four passed. Completed-config checks: 41 passed.
- New dialogs/layouts have registered Qt coverage, retained for an approved visible
  environment. No Qt, vendor acquisition, hardware triggers or installer was run.
- Updated handoff test seams passed all 57 data-sharing GUI-job tests. The first
  broad run found nine old helper/fake-document interfaces; these were corrected
  without changing production behavior. Final repo precommit passed: 3,445 tests,
  12 Windows symlink skips and 20 passing subtests. Changed-file Ruff/compilation,
  mypy for all 242 source files, harness GC and documentation checks passed.
- No new installer or release was built. Visual/native QSettings and physical EEG
  validation remain separate from the safe checks; the workflow doc has concrete
  visible smoke paths for the picker, Welcome and Settings.

## Files changed for this feature

- `.agents/verification.toml`
- `ARCHITECTURE.md`
- `docs/GUI_WORKFLOW.md`
- `docs/PLANS.md`
- `docs/RUNTIME_EXECUTION.md`
- `docs/agent/agent-index.md`
- `docs/exec-plans/planned/lab-independent-recording-setup.md`
- This execution plan.
- `src/fpvs_studio/core/project_config.py`
- `src/fpvs_studio/core/project_service.py`
- `src/fpvs_studio/gui/AGENTS.md`
- `src/fpvs_studio/gui/components.py`
- `src/fpvs_studio/gui/controller.py`
- `src/fpvs_studio/gui/document.py`
- `src/fpvs_studio/gui/document_runtime.py`
- `src/fpvs_studio/gui/recording_dialog.py`
- `src/fpvs_studio/gui/settings_dialog.py`
- `src/fpvs_studio/gui/welcome_window.py`
- `tests/gui/conftest.py`
- `tests/gui/test_default_recording_setup.py`
- `tests/qt_test_files.txt`
- `tests/unit/test_data_sharing_gui_jobs.py`
- `tests/unit/test_default_recording_preferences.py`
- `tests/unit/test_document_summary_refresh.py`
- `tests/unit/test_project_config.py`
- `tests/unit/test_project_service.py`
- `tests/unit/test_runtime_recording.py`
